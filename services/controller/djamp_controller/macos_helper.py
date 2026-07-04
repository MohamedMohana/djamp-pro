from __future__ import annotations

import asyncio
import json
import os
import platform
import shlex
import shutil
import socket
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import CommandResult
from .paths import _repo_root, paths
from .subprocess_security import _find_allowed_executable, _run_blocking

MANAGED_PF_BEGIN = "# BEGIN DJAMP PRO PF"
MANAGED_PF_END = "# END DJAMP PRO PF"

# macOS privileged helper (MAMP-style). Installed once, then used for system-level ops
# without prompting on every hosts/ports change.
MACOS_HELPER_LABEL = "com.djamp.pro.helperd"
MACOS_HELPER_SOCKET = Path("/var/run/djamp-pro/helper.sock")
MACOS_HELPER_BIN = Path("/Library/PrivilegedHelperTools/com.djamp.pro.helperd")
MACOS_HELPER_PLIST = Path(f"/Library/LaunchDaemons/{MACOS_HELPER_LABEL}.plist")


def _run_with_macos_elevation(command: List[str], cwd: Optional[Path] = None) -> CommandResult:
    if platform.system() != "Darwin":
        return CommandResult(success=False, output="", error="Elevation helper is only implemented for macOS")

    shell_cmd = shlex.join(command)
    if cwd is not None:
        shell_cmd = f"cd {shlex.quote(str(cwd))} && {shell_cmd}"

    escaped = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
    osascript_cmd = ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges']
    return _run_blocking(osascript_cmd, paths()["home"])


def _macos_helper_installed() -> bool:
    if platform.system() != "Darwin":
        return False
    return MACOS_HELPER_BIN.exists() and MACOS_HELPER_PLIST.exists()


def _helper_request(payload: Dict[str, Any]) -> Tuple[CommandResult, Optional[Dict[str, Any]]]:
    """Send a single JSON request to the macOS helper daemon over its UNIX socket.

    The helper is expected to be installed as a LaunchDaemon and run as root.
    """
    if platform.system() != "Darwin":
        return CommandResult(success=False, error="Helper is only implemented for macOS"), None

    sock_path = MACOS_HELPER_SOCKET
    if not sock_path.exists():
        return CommandResult(success=False, error="Helper socket not found"), None

    data: bytes = b""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(str(sock_path))
        raw = json.dumps(payload).encode("utf-8")
        s.sendall(raw)
        try:
            s.shutdown(socket.SHUT_WR)
        except Exception:
            pass

        chunks: List[bytes] = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        s.close()
        data = b"".join(chunks)
    except Exception as exc:
        try:
            s.close()
        except Exception:
            pass
        return CommandResult(success=False, error=str(exc)), None

    try:
        resp = json.loads(data.decode("utf-8", errors="ignore") or "{}")
    except Exception as exc:
        return CommandResult(success=False, error=f"Invalid helper response: {exc}"), None

    ok = bool(resp.get("ok"))
    output = str(resp.get("output") or "")
    error = str(resp.get("error") or "")
    helper_data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    return CommandResult(success=ok, output=output, error=error), helper_data


def _helper_hosts_apply(domains: List[str]) -> CommandResult:
    result, _data = _helper_request({"cmd": "hosts_apply", "domains": domains})
    return result


def _helper_hosts_clear() -> CommandResult:
    result, _data = _helper_request({"cmd": "hosts_clear"})
    return result


def _helper_enable_standard_ports(http_target: int, https_target: int) -> CommandResult:
    result, _data = _helper_request(
        {
            "cmd": "standard_ports_enable",
            "http_target_port": int(http_target),
            "https_target_port": int(https_target),
        }
    )
    return result


def _helper_disable_standard_ports() -> CommandResult:
    result, _data = _helper_request({"cmd": "standard_ports_disable"})
    return result


def _friendly_hosts_helper_error(raw_error: Optional[str], hosts_file: Path) -> str:
    text = (raw_error or "").strip()
    if "Permission denied" in text or "os error 13" in text:
        return (
            f"Permission denied updating {hosts_file}. Install/start DJAMP Helper from Settings "
            "to manage hosts without prompts."
        )
    if text:
        return text
    return "DJAMP Helper is not running. Install/start helper from Settings to manage hosts without prompts."


def _disable_macos_pf_redirect_impl() -> CommandResult:
    """Remove the DJAMP PF redirect rules from pf.conf and delete the anchor file (macOS)."""
    if platform.system() != "Darwin":
        return CommandResult(success=True, output="PF redirect not applicable")
    if os.getenv("DJAMP_SKIP_PF") == "1":
        return CommandResult(success=True, output="PF redirect disable skipped via DJAMP_SKIP_PF=1")

    anchor_name = "djamp-pro"
    anchor_path = Path(f"/etc/pf.anchors/{anchor_name}")
    pf_conf = Path("/etc/pf.conf")

    try:
        conf_text = pf_conf.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return CommandResult(success=False, error=f"Unable to read {pf_conf}: {exc}")

    legacy_lines = {
        f'anchor "{anchor_name}"',
        f'load anchor "{anchor_name}" from "{anchor_path}"',
        "# DJAMP PRO",
    }

    lines = conf_text.splitlines()
    new_lines: List[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped == MANAGED_PF_BEGIN:
            skipping = True
            continue
        if skipping:
            if stripped == MANAGED_PF_END:
                skipping = False
            continue
        if stripped in legacy_lines:
            continue
        new_lines.append(line)

    new_conf = "\n".join(new_lines).rstrip() + "\n"
    needs_conf_update = new_conf.strip() != conf_text.strip()

    staged_pf_conf = paths()["home"] / "pf.conf.staged"
    if needs_conf_update:
        staged_pf_conf.write_text(new_conf, encoding="utf-8")

    if not needs_conf_update and not anchor_path.exists():
        return CommandResult(success=True, output="PF redirect already disabled")

    script_parts: List[str] = []
    script_parts.append(f"rm -f {shlex.quote(str(anchor_path))}")
    if needs_conf_update:
        script_parts.append(f"/usr/bin/install -m 644 {shlex.quote(str(staged_pf_conf))} {shlex.quote(str(pf_conf))}")
    script_parts.append(f"/sbin/pfctl -f {shlex.quote(str(pf_conf))}")
    script = "set -e; " + " && ".join(script_parts)

    result = _run_with_macos_elevation(["/bin/sh", "-c", script], cwd=paths()["home"])
    if not result.success:
        return result
    return CommandResult(success=True, output="PF redirect disabled")


async def _disable_macos_pf_redirect() -> CommandResult:
    return await asyncio.to_thread(_disable_macos_pf_redirect_impl)


def _priv_helper_binary() -> Optional[Path]:
    env_path = os.getenv("DJAMP_PRIV_HELPER")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    repo_root = _repo_root()
    candidates = [
        repo_root / "services" / "priv-helper" / "target" / "debug" / "djamp-priv-helper",
        repo_root / "services" / "priv-helper" / "target" / "release" / "djamp-priv-helper",
        repo_root / "services" / "priv-helper" / "target" / "debug" / "djamp-priv-helper.exe",
        repo_root / "services" / "priv-helper" / "target" / "release" / "djamp-priv-helper.exe",
        # Convenience: allow running controller from repo root where artifacts are built in the app target.
        repo_root / "target" / "debug" / "djamp-priv-helper",
        repo_root / "target" / "release" / "djamp-priv-helper",
        repo_root / "target" / "debug" / "djamp-priv-helper.exe",
        repo_root / "target" / "release" / "djamp-priv-helper.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _render_macos_helper_plist() -> str:
    label = MACOS_HELPER_LABEL
    program = str(MACOS_HELPER_BIN)
    log_path = "/var/log/djamp-pro-helper.log"
    # LaunchDaemon plist (system/root). This is intentionally minimal.
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            "<dict>",
            "  <key>Label</key>",
            f"  <string>{label}</string>",
            "  <key>ProgramArguments</key>",
            "  <array>",
            f"    <string>{program}</string>",
            "    <string>daemon</string>",
            "  </array>",
            "  <key>RunAtLoad</key>",
            "  <true/>",
            "  <key>KeepAlive</key>",
            "  <true/>",
            "  <key>StandardOutPath</key>",
            f"  <string>{log_path}</string>",
            "  <key>StandardErrorPath</key>",
            f"  <string>{log_path}</string>",
            "</dict>",
            "</plist>",
            "",
        ]
    )


def _build_macos_helper_binary() -> Tuple[Optional[Path], CommandResult]:
    if platform.system() != "Darwin":
        return None, CommandResult(success=False, error="Helper build is only implemented for macOS")

    cargo = _find_allowed_executable("cargo", _repo_root())
    if not cargo:
        return None, CommandResult(success=False, error="`cargo` was not found in PATH")

    manifest = _repo_root() / "services" / "priv-helper" / "Cargo.toml"
    if not manifest.exists():
        return None, CommandResult(success=False, error=f"Helper Cargo.toml not found: {manifest}")

    build = _run_blocking(
        [cargo, "build", "--manifest-path", str(manifest), "--release"],
        _repo_root(),
    )
    if not build.success:
        return None, CommandResult(success=False, output=build.output, error=build.error or "Helper build failed")

    binary = _repo_root() / "services" / "priv-helper" / "target" / "release" / "djamp-priv-helper"
    if not binary.exists():
        return None, CommandResult(success=False, error=f"Built helper binary not found: {binary}")

    return binary, CommandResult(success=True, output="Helper binary built")


def _install_macos_helper_impl() -> CommandResult:
    if platform.system() != "Darwin":
        return CommandResult(success=False, error="Helper install is only implemented for macOS")

    binary, build_result = _build_macos_helper_binary()
    if not build_result.success or not binary:
        return build_result

    # Stage install artifacts under /tmp to avoid macOS privacy restrictions
    # when privileged shell reads files from user folders like Documents/Desktop.
    stage_dir = Path(tempfile.mkdtemp(prefix="djamp-helper-install-"))
    staged_binary = stage_dir / "djamp-priv-helper"
    staged_plist = stage_dir / f"{MACOS_HELPER_LABEL}.plist"

    try:
        shutil.copy2(binary, staged_binary)
        staged_binary.chmod(0o755)
        staged_plist.write_text(_render_macos_helper_plist(), encoding="utf-8")
    except Exception as exc:
        try:
            shutil.rmtree(stage_dir, ignore_errors=True)
        except Exception:
            pass
        return CommandResult(success=False, error=f"Unable to stage helper install files: {exc}")

    script_parts = [
        f"/usr/bin/install -m 755 -o root -g wheel {shlex.quote(str(staged_binary))} {shlex.quote(str(MACOS_HELPER_BIN))}",
        f"/usr/bin/install -m 644 -o root -g wheel {shlex.quote(str(staged_plist))} {shlex.quote(str(MACOS_HELPER_PLIST))}",
        f"/bin/launchctl bootout system {shlex.quote(str(MACOS_HELPER_PLIST))} >/dev/null 2>&1 || true",
        f"/bin/launchctl bootstrap system {shlex.quote(str(MACOS_HELPER_PLIST))}",
        f"/bin/launchctl kickstart -k system/{shlex.quote(MACOS_HELPER_LABEL)}",
    ]
    script = "set -e; " + " && ".join(script_parts)
    elevated = _run_with_macos_elevation(["/bin/sh", "-c", script], cwd=stage_dir)

    try:
        shutil.rmtree(stage_dir, ignore_errors=True)
    except Exception:
        pass

    if not elevated.success:
        return elevated

    # Wait briefly for the socket to come up.
    deadline = time.time() + 10.0
    last_err = ""
    while time.time() < deadline:
        result, _data = _helper_request({"cmd": "status"})
        if result.success:
            return CommandResult(success=True, output="DJAMP Helper installed and running")
        last_err = result.error or result.output or last_err
        time.sleep(0.2)

    return CommandResult(
        success=False,
        error=(
            "DJAMP Helper appears installed but is not responding. "
            "Check /var/log/djamp-pro-helper.log and `launchctl print system/"
            + MACOS_HELPER_LABEL
            + "`.\n"
            + (last_err or "")
        ),
    )


def _uninstall_macos_helper_impl() -> CommandResult:
    if platform.system() != "Darwin":
        return CommandResult(success=False, error="Helper uninstall is only implemented for macOS")

    script_parts = [
        f"/bin/launchctl bootout system {shlex.quote(str(MACOS_HELPER_PLIST))} >/dev/null 2>&1 || true",
        f"rm -f {shlex.quote(str(MACOS_HELPER_PLIST))}",
        f"rm -f {shlex.quote(str(MACOS_HELPER_BIN))}",
        "rm -rf /var/run/djamp-pro >/dev/null 2>&1 || true",
    ]
    script = "set -e; " + " && ".join(script_parts)
    elevated = _run_with_macos_elevation(["/bin/sh", "-c", script], cwd=paths()["home"])
    if not elevated.success:
        return elevated
    return CommandResult(success=True, output="DJAMP Helper uninstalled")
