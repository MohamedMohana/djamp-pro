from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import List, Optional

from .certificates import _generate_certificate
from .domains import _project_domains
from .macos_helper import (
    MACOS_HELPER_SOCKET,
    _helper_disable_standard_ports,
    _helper_enable_standard_ports,
)
from .models import AppSettings, CommandResult, Project
from .paths import _repo_root, _tail_file, paths
from .processes import SERVICE_PROCESSES, _is_port_open
from .registry import load_registry_sync, save_registry_sync
from .subprocess_security import _find_allowed_executable, _prepend_path_env, _run_blocking

CADDY_GITHUB_LATEST = "https://api.github.com/repos/caddyserver/caddy/releases/latest"


def _caddy_binary() -> Optional[str]:
    env_path = os.getenv("DJAMP_CADDY_BIN")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)

    bundled = paths()["bin"] / ("caddy.exe" if platform.system() == "Windows" else "caddy")
    if bundled.exists():
        return str(bundled)

    if platform.system() == "Darwin":
        arch = platform.machine().lower()
        if arch in ("arm64", "aarch64"):
            local = _repo_root() / "bundles" / "caddy" / "darwin-arm64" / "caddy"
        else:
            local = _repo_root() / "bundles" / "caddy" / "darwin-x64" / "caddy"
        if local.exists():
            return str(local.resolve())

    if platform.system() == "Windows":
        local = _repo_root() / "bundles" / "caddy" / "windows-x64" / "caddy.exe"
        if local.exists():
            return str(local.resolve())

    return _find_allowed_executable("caddy", _repo_root())


def _download_file(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "DJAMP-PRO"})
    with urllib.request.urlopen(request, timeout=60) as response:
        dest.write_bytes(response.read())


def _hash_file(path: Path, algorithm: str) -> str:
    if algorithm == "sha512":
        h = hashlib.sha512()
    elif algorithm == "sha256":
        h = hashlib.sha256()
    else:
        raise ValueError(f"unsupported hash algorithm: {algorithm}")
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_caddy_installed() -> CommandResult:
    existing = _caddy_binary()
    if existing:
        return CommandResult(success=True, output=existing)

    if platform.system() != "Darwin":
        return CommandResult(success=False, error="Automatic Caddy install is only implemented for macOS")

    try:
        request = urllib.request.Request(CADDY_GITHUB_LATEST, headers={"User-Agent": "DJAMP-PRO"})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))

        tag = str(release.get("tag_name") or "").strip()
        version = tag.lstrip("v")
        assets = {a["name"]: a["browser_download_url"] for a in (release.get("assets") or [])}

        arch = platform.machine().lower()
        arch_key = "arm64" if arch in ("arm64", "aarch64") else "amd64"
        tar_name = f"caddy_{version}_mac_{arch_key}.tar.gz"
        sums_name = f"caddy_{version}_checksums.txt"

        tar_url = assets.get(tar_name)
        sums_url = assets.get(sums_name)
        if not tar_url or not sums_url:
            return CommandResult(success=False, error=f"Caddy release assets not found for {tar_name}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            tar_path = tmp / tar_name
            sums_path = tmp / sums_name

            _download_file(tar_url, tar_path)
            _download_file(sums_url, sums_path)

            expected: Optional[str] = None
            for line in sums_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == tar_name:
                    expected = parts[0]
                    break
            if not expected:
                return CommandResult(success=False, error="Unable to verify Caddy checksum (missing entry)")

            algorithm = "sha512" if len(expected) == 128 else "sha256" if len(expected) == 64 else ""
            if not algorithm:
                return CommandResult(success=False, error="Unable to verify Caddy checksum (unknown format)")

            actual = _hash_file(tar_path, algorithm)
            if actual.lower() != expected.lower():
                return CommandResult(success=False, error="Caddy checksum mismatch; download may be corrupted")

            with tarfile.open(tar_path, "r:gz") as tf:
                members = [m for m in tf.getmembers() if m.isfile() and Path(m.name).name == "caddy"]
                if not members:
                    return CommandResult(success=False, error="Caddy binary not found in archive")
                member = members[0]
                tf.extract(member, path=tmp)
                extracted = tmp / member.name

            dest = paths()["bin"] / "caddy"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(extracted), str(dest))
            dest.chmod(0o755)
            return CommandResult(success=True, output=str(dest))
    except Exception as exc:
        return CommandResult(success=False, error=str(exc))


def _render_caddyfile(projects: List[Project]) -> str:
    settings = load_registry_sync().settings
    access_log = paths()["proxy_logs"] / "access.log"
    caddy_log = paths()["proxy_logs"] / "caddy.log"

    def q(path: Path | str) -> str:
        s = str(path)
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f"\"{s}\""

    lines: List[str] = [
        "# DJAMP PRO managed Caddyfile",
        "{",
        f"  http_port {settings.proxyHttpPort}",
        f"  https_port {settings.proxyPort}",
        "  log {",
        f"    output file {q(caddy_log)}",
        "  }",
        "}",
        "",
    ]

    for project in projects:
        domains = _project_domains(project)
        labels = domains if project.httpsEnabled else [f"http://{d}" for d in domains]
        domains_csv = ", ".join(labels)
        if not domains_csv:
            continue

        lines.append(f"{domains_csv} {{")
        lines.append("  log {")
        lines.append(f"    output file {q(access_log)}")
        lines.append("  }")
        if project.httpsEnabled and project.certificatePath:
            key_path = re.sub(r"\.crt$", ".key", project.certificatePath)
            lines.append(f"  tls {q(project.certificatePath)} {q(key_path)}")
        if project.database.type == "postgres":
            lines.append("  @dbadmin path /phpmyadmin /phpmyadmin/ /phpMyAdmin /phpMyAdmin/ /phpMyAdmin5 /phpMyAdmin5/")
            lines.append("  handle @dbadmin {")
            lines.append(f"    rewrite * /api/databases/{project.id}/admin")
            lines.append("    reverse_proxy 127.0.0.1:8765")
            lines.append("  }")
        lines.append(f"  reverse_proxy 127.0.0.1:{project.port}")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


async def _sync_standard_ports(settings: AppSettings) -> Optional[str]:
    """Ensure ports 80/443 route to the DJAMP proxy ports (macOS).

    Instead of PF hacks, DJAMP uses an installed privileged helper (MAMP-style) to bind
    80/443 on loopback and forward to the configured proxy ports. This avoids editing pf.conf.
    """
    if platform.system() != "Darwin":
        return None

    if not MACOS_HELPER_SOCKET.exists():
        if settings.standardPortsEnabled:
            return (
                "DJAMP Helper is not installed/running. "
                "Install it from Settings to enable ports 80/443 without password prompts."
            )
        return None

    if settings.standardPortsEnabled:
        result = await asyncio.to_thread(_helper_enable_standard_ports, settings.proxyHttpPort, settings.proxyPort)
    else:
        result = await asyncio.to_thread(_helper_disable_standard_ports)

    if result.success:
        return None
    return result.error or result.output or "Standard ports sync failed"


async def _reload_caddy(projects: List[Project], allow_privileged: bool = True) -> CommandResult:
    caddy_result = await asyncio.to_thread(_ensure_caddy_installed)
    if not caddy_result.success:
        return caddy_result
    caddy = caddy_result.output

    settings = load_registry_sync().settings

    # Ensure local certificates exist so Caddy never tries ACME for local-only domains.
    try:
        registry = load_registry_sync()
        changed = False
        for project in registry.projects:
            if not project.httpsEnabled:
                continue
            cert_path = Path(project.certificatePath) if project.certificatePath else None
            if cert_path and cert_path.exists():
                continue
            cert_info = _generate_certificate(project.domain, _project_domains(project))
            project.certificatePath = cert_info.certificatePath
            changed = True
        if changed:
            save_registry_sync(registry)
            projects = registry.projects
    except Exception as exc:
        # Certificate generation failures should not hard-crash proxy reload.
        return CommandResult(success=False, error=f"Certificate generation failed: {exc}")

    caddy_file = paths()["caddy_file"]
    caddy_file.write_text(_render_caddyfile(projects), encoding="utf-8")

    # Prefer reload when Caddy is already running.
    reload_cmd = [caddy, "reload", "--config", str(caddy_file), "--adapter", "caddyfile"]
    reload_env = os.environ.copy()
    _prepend_path_env(reload_env, Path(caddy).parent)
    reload_result = _run_blocking(reload_cmd, paths()["home"], reload_env)
    if reload_result.success:
        std_warning = await _sync_standard_ports(settings)
        return _caddy_result_with_standard_ports("reloaded", std_warning, settings, allow_privileged)

    # Start Caddy in-process (no daemonizing) and track it.
    caddy_data = paths()["caddy"] / "data"
    caddy_cfg = paths()["caddy"] / "config"
    caddy_data.mkdir(parents=True, exist_ok=True)
    caddy_cfg.mkdir(parents=True, exist_ok=True)

    log_path = paths()["proxy_logs"] / "caddy-stdout.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(caddy_data)
    env["XDG_CONFIG_HOME"] = str(caddy_cfg)
    env.setdefault("GODEBUG", "x509ignoreCN=0")

    proc = await asyncio.create_subprocess_exec(
        caddy,
        "run",
        "--config",
        str(caddy_file),
        "--adapter",
        "caddyfile",
        cwd=str(paths()["home"]),
        env=env,
        stdout=log_handle,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    SERVICE_PROCESSES["caddy"] = (proc, log_handle)

    await asyncio.sleep(0.8)
    if proc.returncode is not None:
        SERVICE_PROCESSES.pop("caddy", None)
        try:
            log_handle.close()
        except Exception:
            pass
        tail = _tail_file(log_path, 2000)
        return CommandResult(success=False, error=f"Caddy exited early. Recent logs:\n{tail}")

    if _is_port_open(settings.proxyPort) or _is_port_open(settings.proxyHttpPort):
        std_warning = await _sync_standard_ports(settings)
        return _caddy_result_with_standard_ports("started", std_warning, settings, allow_privileged)

    return CommandResult(success=False, error="Caddy started but ports are not listening")


def _caddy_result_with_standard_ports(
    action: str, std_warning: Optional[str], settings: AppSettings, allow_privileged: bool
) -> CommandResult:
    """Shape the reload/start result based on the standard-ports sync outcome."""
    if not std_warning:
        return CommandResult(success=True, output=f"Caddy {action}")
    if allow_privileged:
        if settings.standardPortsEnabled:
            return CommandResult(
                success=False,
                output=f"Caddy {action}",
                error=(
                    f"Proxy is running but standard ports (80/443) are not enabled: {std_warning}\n"
                    f"You can still access projects on https://<domain>:{settings.proxyPort}"
                ),
            )
        return CommandResult(
            success=False,
            output=f"Caddy {action}",
            error=f"Proxy is running but standard ports (80/443) could not be disabled: {std_warning}",
        )
    return CommandResult(
        success=True,
        output=f"Caddy {action} (note: {std_warning} Use https://<domain>:{settings.proxyPort})",
    )
