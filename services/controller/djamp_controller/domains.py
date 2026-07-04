from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from .macos_helper import (
    MACOS_HELPER_SOCKET,
    _friendly_hosts_helper_error,
    _helper_hosts_apply,
    _helper_hosts_clear,
    _priv_helper_binary,
)
from .models import AppSettings, CommandResult, Project, Registry
from .paths import paths
from .subprocess_security import _prepend_path_env, _run_blocking

MANAGED_HOSTS_BEGIN = "# BEGIN DJAMP PRO MANAGED"
MANAGED_HOSTS_END = "# END DJAMP PRO MANAGED"


def _sanitize_hostname(value: str) -> str:
    """Return a safe hostname string for use in hosts/proxy/cert generation.

    We intentionally restrict to ASCII hostnames for MVP to avoid path traversal
    and config injection issues (e.g. writing cert files named with '/' etc).
    """
    raw = (value or "").strip()
    if not raw:
        raise RuntimeError("Domain is empty")

    # Allow users to paste URLs like https://example.test
    if raw.lower().startswith(("http://", "https://")):
        parsed = urlparse(raw)
        raw = parsed.hostname or ""

    host = raw.strip().strip(".").lower()
    if not host:
        raise RuntimeError("Invalid domain")
    if ":" in host:
        raise RuntimeError("Domain must not include a port")
    if any(ch.isspace() for ch in host):
        raise RuntimeError("Invalid domain (contains whitespace)")
    if any(ch in host for ch in ("/", "\\", "\"", "'", "{", "}", "[", "]", "(", ")", ";")):
        raise RuntimeError("Invalid domain (contains unsupported characters)")
    if len(host) > 253:
        raise RuntimeError("Invalid domain (too long)")

    labels = host.split(".")
    for label in labels:
        if not label:
            raise RuntimeError("Invalid domain")
        if len(label) > 63:
            raise RuntimeError("Invalid domain (label too long)")
        if not label[0].isalnum() or not label[-1].isalnum():
            raise RuntimeError("Invalid domain (label must start/end with a letter/number)")
        if not all(ch.isalnum() or ch == "-" for ch in label):
            raise RuntimeError("Invalid domain (only letters, numbers, '-' and '.' are allowed)")

    return host


def _try_sanitize_hostname(value: str) -> Optional[str]:
    try:
        return _sanitize_hostname(value)
    except Exception:
        return None


def _project_domains(project: Project) -> List[str]:
    # Be robust in case a bad value exists in the registry (don't crash the controller).
    domains: List[str] = []
    for raw in [project.domain, *project.aliases]:
        cleaned = _try_sanitize_hostname(raw)
        if cleaned and cleaned not in domains:
            domains.append(cleaned)

    if domains and not domains[0].startswith("www."):
        www = f"www.{domains[0]}"
        if www not in domains:
            domains.append(www)
    return domains


def _is_local_dev_domain(host: str) -> bool:
    # RFC 2606 / RFC 6761 safe defaults
    return host.endswith(".test") or host.endswith(".localhost")


def _enforce_domain_policy(project: Project, settings: AppSettings) -> None:
    """Apply the "public override" guardrails.

    MAMP PRO allows overriding public domains by editing /etc/hosts; DJAMP supports it too,
    but keeps it behind an explicit per-project + global toggle to avoid accidental breakage.
    """
    mode = (project.domainMode or "local_only").strip()
    domains = _project_domains(project)

    if mode == "public_override":
        if not settings.anyDomainOverrideEnabled:
            raise RuntimeError(
                "Public-domain overrides are disabled. Enable Settings -> Allow Public-Domain Overrides first."
            )
        return

    # local_only
    for d in domains:
        if d in ("localhost", "127.0.0.1"):
            continue
        if not _is_local_dev_domain(d):
            raise RuntimeError(
                "This domain looks like a real/public domain. "
                "Use a .test domain, or switch Domain Mode to 'Public-domain override' "
                "and enable it in Settings."
            )


def _flush_macos_dns_cache() -> None:
    if platform.system() != "Darwin":
        return
    # Best-effort; errors are ignored. This helps apply /etc/hosts updates immediately.
    for cmd in (["/usr/bin/dscacheutil", "-flushcache"], ["/usr/bin/killall", "-HUP", "mDNSResponder"]):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass


def _apply_hosts_entries_impl(entries: List[str]) -> CommandResult:
    """Write (or remove, when `entries` is empty) the managed hosts block.

    Tries, in order: no-op preflight, macOS helper daemon, privileged helper
    binary, then a direct write (works when running elevated).
    """
    clearing = not entries
    action = "cleared" if clearing else "updated"

    hosts_file = (
        Path("C:/Windows/System32/drivers/etc/hosts")
        if platform.system() == "Windows"
        else Path("/etc/hosts")
    )

    def render(current: str) -> Tuple[str, List[str]]:
        before, managed, after = _split_hosts_sections(current)
        if clearing:
            return _join_without_section(before, after), managed
        block_lines = [MANAGED_HOSTS_BEGIN, *entries, MANAGED_HOSTS_END]
        return _join_hosts_sections(before, block_lines, after), managed

    # Preflight: if the hosts file is already in the desired state, avoid any privileged execution.
    try:
        if hosts_file.exists():
            current = hosts_file.read_text(encoding="utf-8", errors="ignore")
            new_content, managed = render(current)
            if clearing and not managed:
                return CommandResult(success=True, output="Hosts file already clean")
            if new_content.strip() == current.strip():
                return CommandResult(success=True, output="Hosts file already up to date")
    except Exception:
        # Preflight is best-effort; continue with helper/direct write below.
        pass

    domains = [line.split(" ", 1)[1] for line in entries]

    # Prefer the installed macOS helper daemon (MAMP-style): no repeated password prompts.
    if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
        helper_result = _helper_hosts_clear() if clearing else _helper_hosts_apply(domains)
        if helper_result.success:
            return CommandResult(success=True, output=f"Hosts file {action} via DJAMP Helper")

    helper = _priv_helper_binary()
    if helper:
        helper_command = (
            [str(helper), "hosts", "clear"]
            if clearing
            else [str(helper), "hosts", "apply", *domains]
        )
        helper_env = os.environ.copy()
        _prepend_path_env(helper_env, helper.parent)
        helper_run = _run_blocking(helper_command, paths()["home"], helper_env)
        if helper_run.success:
            _flush_macos_dns_cache()
            return CommandResult(success=True, output=f"Hosts file {action} via privileged helper")

        if platform.system() == "Darwin":
            return CommandResult(
                success=False,
                output=helper_run.output,
                error=_friendly_hosts_helper_error(helper_run.error, hosts_file),
            )

    if not hosts_file.exists():
        return CommandResult(success=False, error=f"Hosts file not found at {hosts_file}")

    try:
        current = hosts_file.read_text(encoding="utf-8", errors="ignore")
        new_content, managed = render(current)
        if clearing and not managed:
            return CommandResult(success=True, output="Hosts file already clean")
        if new_content.strip() == current.strip():
            return CommandResult(success=True, output="Hosts file already up to date")

        # Attempt direct write first (will work when running elevated).
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
                tmp.write(new_content)
                tmp_path = Path(tmp.name)
            os.replace(tmp_path, hosts_file)
            _flush_macos_dns_cache()
            return CommandResult(success=True, output=f"Hosts file {action}")
        except PermissionError:
            if platform.system() != "Darwin":
                raise

        return CommandResult(
            success=False,
            error=(
                f"Permission denied updating {hosts_file}. Install the DJAMP Helper from Settings to apply hosts changes."
            ),
        )
    except PermissionError:
        return CommandResult(
            success=False,
            error=(
                f"Permission denied updating {hosts_file}. Install the DJAMP Helper from Settings (recommended) "
                "or run DJAMP PRO with elevated privileges for hosts changes."
            ),
        )
    except Exception as exc:
        return CommandResult(success=False, error=str(exc))


def _sync_domains_for_registry_impl(registry: Registry) -> CommandResult:
    if os.getenv("DJAMP_SKIP_HOSTS") == "1":
        return CommandResult(success=True, output="Hosts sync skipped via DJAMP_SKIP_HOSTS=1")

    # Build a stable list of desired host entries. Sorting avoids spurious diffs and prompts.
    desired_domains: List[str] = sorted({"localhost", *{d for project in registry.projects for d in _project_domains(project)}})
    return _apply_hosts_entries_impl([f"127.0.0.1 {domain}" for domain in desired_domains])


async def _sync_domains_for_registry(registry: Registry) -> CommandResult:
    # Hosts changes may require privilege elevation and can block for user interaction;
    # run them off the main event loop to keep the API responsive.
    return await asyncio.to_thread(_sync_domains_for_registry_impl, registry)


def _clear_hosts_block_impl() -> CommandResult:
    if os.getenv("DJAMP_SKIP_HOSTS") == "1":
        return CommandResult(success=True, output="Hosts clear skipped via DJAMP_SKIP_HOSTS=1")
    return _apply_hosts_entries_impl([])


async def _clear_hosts_block() -> CommandResult:
    return await asyncio.to_thread(_clear_hosts_block_impl)


def _split_hosts_sections(content: str) -> Tuple[List[str], List[str], List[str]]:
    return _split_marked_sections(content, MANAGED_HOSTS_BEGIN, MANAGED_HOSTS_END)


def _split_marked_sections(content: str, begin_marker: str, end_marker: str) -> Tuple[List[str], List[str], List[str]]:
    lines = content.splitlines()
    begin_idx = -1
    end_idx = -1

    for idx, line in enumerate(lines):
        if line.strip() == begin_marker:
            begin_idx = idx
        if line.strip() == end_marker and begin_idx >= 0:
            end_idx = idx
            break

    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        return lines, [], []

    before = lines[:begin_idx]
    managed = lines[begin_idx : end_idx + 1]
    after = lines[end_idx + 1 :]
    return before, managed, after


def _join_hosts_sections(before: List[str], managed_block: List[str], after: List[str]) -> str:
    return _join_marked_sections(before, managed_block, after)


def _join_marked_sections(before: List[str], marked_block: List[str], after: List[str]) -> str:
    out: List[str] = []
    out.extend(before)
    if out and out[-1].strip() != "":
        out.append("")
    out.extend(marked_block)
    if after:
        out.append("")
        out.extend(after)
    return "\n".join(out).rstrip() + "\n"


def _join_without_section(before: List[str], after: List[str]) -> str:
    out: List[str] = []
    out.extend(before)
    if after:
        if out and out[-1].strip() != "":
            out.append("")
        out.extend(after)
    return "\n".join(out).rstrip() + "\n"
