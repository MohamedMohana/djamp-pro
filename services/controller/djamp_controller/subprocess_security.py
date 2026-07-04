from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .models import CommandResult
from .paths import _is_relative_to, paths

_ALLOWED_SUBPROCESS_EXECUTABLES = {
    "caddy",
    "caddy.exe",
    "cargo",
    "cargo.exe",
    "certutil",
    "cmd",
    "cmd.exe",
    "conda",
    "conda.exe",
    "djamp-priv-helper",
    "djamp-priv-helper.exe",
    "initdb",
    "initdb.exe",
    "mysqladmin",
    "mysqladmin.exe",
    "openssl",
    "openssl.exe",
    "osascript",
    "pg_isready",
    "pg_isready.exe",
    "powershell",
    "powershell.exe",
    "psql",
    "psql.exe",
    "python",
    "python.exe",
    "redis-cli",
    "redis-cli.exe",
    "security",
    "uv",
    "uv.exe",
}

_DISALLOWED_EXECUTABLE_ROOTS = (
    Path("/Applications/MAMP"),
    Path("/Applications/MAMP PRO"),
)


def _allowed_executable_roots(cwd: Path) -> List[Path]:
    return [
        cwd.expanduser().resolve(),
        paths()["home"].expanduser().resolve(),
        Path.home().expanduser().resolve(),
        Path("/bin"),
        Path("/sbin"),
        Path("/usr/bin"),
        Path("/usr/sbin"),
        Path("/usr/local/bin"),
        Path("/opt"),
        Path("/opt/homebrew"),
        Path("/opt/homebrew/bin"),
        Path("/opt/homebrew/opt"),
    ]


def _disallowed_executable_roots() -> List[Path]:
    return [root.expanduser().resolve() for root in _DISALLOWED_EXECUTABLE_ROOTS]


def _find_allowed_executable(
    executable_name: str,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    try:
        return str(_resolve_allowed_executable_path(executable_name, executable_name, cwd, env))
    except RuntimeError:
        return None


def _resolve_allowed_executable_path(
    executable_token: str,
    executable_name: str,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    search_path = None
    if env:
        search_path = env.get("PATH")
    if not search_path:
        search_path = os.environ.get("PATH", "")

    allowed_roots = _allowed_executable_roots(cwd)
    disallowed_roots = _disallowed_executable_roots()

    explicit = Path(executable_token).expanduser()
    is_explicit_path = explicit.is_absolute() or "/" in executable_token or "\\" in executable_token
    if is_explicit_path:
        try:
            candidate = explicit if explicit.is_absolute() else (cwd / explicit).resolve()
        except Exception as exc:
            raise RuntimeError(f"Invalid executable path: {executable_token}") from exc
        if not candidate.exists() or not candidate.is_file():
            raise RuntimeError(f"Executable not found: {candidate}")
        if not os.access(str(candidate), os.X_OK):
            raise RuntimeError(f"Executable is not executable: {candidate}")
        if any(_is_relative_to(candidate, root) for root in disallowed_roots):
            raise RuntimeError(f"Executable path is blocked: {candidate}")
        if any(_is_relative_to(candidate, root) for root in allowed_roots):
            return candidate
        raise RuntimeError("Executable path is outside allowed roots")

    candidates: List[Path] = []

    for raw_dir in search_path.split(os.pathsep):
        if not raw_dir:
            continue
        try:
            candidates.append((Path(raw_dir).expanduser() / executable_name).resolve())
        except Exception:
            continue

    # Ensure common safe roots are still checked even when PATH is polluted by other toolchains.
    for root in allowed_roots:
        try:
            candidates.append((root / executable_name).resolve())
        except Exception:
            continue

    seen: set[str] = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        if not candidate.exists() or not candidate.is_file():
            continue
        if not os.access(str(candidate), os.X_OK):
            continue
        if any(_is_relative_to(candidate, root) for root in disallowed_roots):
            continue
        if any(_is_relative_to(candidate, root) for root in allowed_roots):
            return candidate

    resolved = shutil.which(executable_name, path=search_path)
    if not resolved:
        raise RuntimeError(f"Executable not found in PATH: {executable_name}")
    resolved_path = Path(resolved).expanduser().resolve()
    if any(_is_relative_to(resolved_path, root) for root in disallowed_roots):
        raise RuntimeError(f"Executable path is blocked: {resolved_path}")
    raise RuntimeError("Executable path is outside allowed roots")


def _sanitize_subprocess_command(command: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> List[str]:
    if not command:
        raise RuntimeError("Command is empty")

    safe_cwd = cwd.expanduser().resolve()

    sanitized: List[str] = []
    for raw in command:
        token = str(raw)
        if not token:
            raise RuntimeError("Command contains an empty argument")
        if "\x00" in token or "\r" in token or "\n" in token:
            raise RuntimeError("Command contains invalid characters")
        if len(token) > 8192:
            raise RuntimeError("Command argument is too long")
        sanitized.append(token)

    executable_token = sanitized[0].strip()
    executable = executable_token.replace("\\", "/").rsplit("/", 1)[-1]
    if not executable:
        raise RuntimeError("Executable is empty")

    if not re.fullmatch(r"[A-Za-z0-9._+-]+", executable):
        raise RuntimeError("Executable contains unsupported characters")

    allowed_name = executable in _ALLOWED_SUBPROCESS_EXECUTABLES or re.fullmatch(
        r"python([0-9]+(\.[0-9]+)*)?(\.exe)?",
        executable,
    )
    if not allowed_name:
        raise RuntimeError(f"Executable is not permitted: {executable}")

    resolved_path = _resolve_allowed_executable_path(executable_token, executable, safe_cwd, env)
    sanitized[0] = str(resolved_path)

    return sanitized


def _run_blocking(
    command: List[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    input_text: Optional[str] = None,
) -> CommandResult:
    try:
        safe_cwd = cwd.expanduser().resolve()
    except Exception as exc:
        return CommandResult(success=False, output="", error=f"Invalid command working directory: {exc}")

    safe_env: Optional[Dict[str, str]] = None
    if env is not None:
        safe_env = {}
        for key, value in env.items():
            k = str(key)
            v = str(value)
            if "\x00" in k or "\x00" in v:
                continue
            safe_env[k] = v

    try:
        safe_command = _sanitize_subprocess_command(command, safe_cwd, safe_env)
    except Exception as exc:
        return CommandResult(success=False, output="", error=f"Unsafe command rejected: {exc}")

    try:
        result = subprocess.run(
            safe_command,
            cwd=str(safe_cwd),
            env=safe_env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
        )
    except Exception as exc:
        return CommandResult(success=False, output="", error=str(exc))


def _prepend_path_env(env: Dict[str, str], prefix: Path) -> None:
    try:
        resolved = str(prefix.expanduser().resolve())
    except Exception:
        return

    current = env.get("PATH", "")
    env["PATH"] = f"{resolved}{os.pathsep}{current}" if current else resolved
