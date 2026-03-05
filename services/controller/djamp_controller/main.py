from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from urllib.parse import quote_plus, urlparse

APP_NAME = "DJAMP PRO"
MANAGED_HOSTS_BEGIN = "# BEGIN DJAMP PRO MANAGED"
MANAGED_HOSTS_END = "# END DJAMP PRO MANAGED"
MANAGED_PF_BEGIN = "# BEGIN DJAMP PRO PF"
MANAGED_PF_END = "# END DJAMP PRO PF"
MANAGED_ENV_BEGIN = "# BEGIN DJAMP PRO MANAGED ENV"
MANAGED_ENV_END = "# END DJAMP PRO MANAGED ENV"
CADDY_GITHUB_LATEST = "https://api.github.com/repos/caddyserver/caddy/releases/latest"

# Default managed service ports (MAMP-style, avoids clobbering system services).
MANAGED_POSTGRES_PORT = 54329
MANAGED_MYSQL_PORT = 33069
MANAGED_REDIS_PORT = 6389

# macOS privileged helper (MAMP-style). Installed once, then used for system-level ops
# without prompting on every hosts/ports change.
MACOS_HELPER_LABEL = "com.djamp.pro.helperd"
MACOS_HELPER_SOCKET = Path("/var/run/djamp-pro/helper.sock")
MACOS_HELPER_BIN = Path("/Library/PrivilegedHelperTools/com.djamp.pro.helperd")
MACOS_HELPER_PLIST = Path(f"/Library/LaunchDaemons/{MACOS_HELPER_LABEL}.plist")


class DatabaseConfig(BaseModel):
    type: Literal["postgres", "mysql", "none"] = "none"
    port: int = MANAGED_POSTGRES_PORT
    name: str = ""
    username: str = ""
    password: str = ""


class CacheConfig(BaseModel):
    type: Literal["redis", "none"] = "none"
    port: int = MANAGED_REDIS_PORT


class Project(BaseModel):
    id: str
    name: str
    path: str
    settingsModule: str
    domain: str
    aliases: List[str] = Field(default_factory=list)
    port: int = 8000
    pythonVersion: str = "3.11"
    venvPath: str = ""
    debug: bool = True
    allowedHosts: List[str] = Field(default_factory=list)
    httpsEnabled: bool = True
    certificatePath: str = ""
    staticPath: str = "static"
    mediaPath: str = "media"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    status: Literal["stopped", "starting", "running", "stopping", "error"] = "stopped"
    environmentVars: Dict[str, str] = Field(default_factory=dict)
    createdAt: str
    runtimeMode: Literal["uv", "conda", "system", "custom"] = "uv"
    condaEnv: str = ""
    customInterpreter: str = ""
    domainMode: Literal["local_only", "public_override"] = "local_only"


class AppSettings(BaseModel):
    caInstalled: bool = False
    defaultPython: str = "3.11"
    autoStartProjects: List[str] = Field(default_factory=list)
    proxyPort: int = 8443
    proxyHttpPort: int = 8080
    anyDomainOverrideEnabled: bool = False
    standardPortsEnabled: bool = True
    restoreOnQuit: bool = True


class Registry(BaseModel):
    projects: List[Project] = Field(default_factory=list)
    settings: AppSettings = Field(default_factory=AppSettings)


class CommandResult(BaseModel):
    success: bool
    output: str = ""
    error: str = ""


class DetectionResult(BaseModel):
    found: bool
    managePyPath: Optional[str] = None
    settingsModules: List[str] = Field(default_factory=list)


class CertificateInfo(BaseModel):
    domain: str
    certificatePath: str = ""
    keyPath: str = ""
    expiresAt: str = ""
    isValid: bool = False


class ProxyStatus(BaseModel):
    proxyHttpPort: int
    proxyPort: int
    standardPortsEnabled: bool
    standardHttpActive: bool
    standardHttpsActive: bool
    proxyHttpActive: bool
    proxyHttpsActive: bool


class UpdateSettingsPayload(BaseModel):
    settings: Dict[str, Any]


class UpdateProjectPayload(BaseModel):
    id: str
    updates: Dict[str, Any]


class AddProjectPayload(BaseModel):
    project: Dict[str, Any]


class DomainPayload(BaseModel):
    domain: str


class CreateVenvPayload(BaseModel):
    path: str
    pythonVersion: str = "3.11"


class InstallDependenciesPayload(BaseModel):
    projectId: str


class ShellPayload(BaseModel):
    project_id: str


class CreateSuperuserPayload(BaseModel):
    projectId: str
    username: str
    email: str


REGISTRY_LOCK = asyncio.Lock()
PROJECT_PROCESSES: Dict[str, Tuple[asyncio.subprocess.Process, Any]] = {}
SERVICE_PROCESSES: Dict[str, Tuple[asyncio.subprocess.Process, Any]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_home() -> Path:
    env = os.getenv("DJAMP_HOME")
    if env:
        return Path(env).expanduser().resolve()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if system == "Windows":
        app_data = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(app_data) / APP_NAME
    return Path.home() / ".config" / "djamp-pro"


def paths() -> Dict[str, Path]:
    home = app_home()
    return {
        "home": home,
        "bin": home / "bin",
        "registry": home / "registry.json",
        "logs": home / "logs",
        "django_logs": home / "logs" / "django",
        "proxy_logs": home / "logs" / "proxy",
        "db_logs": home / "logs" / "database",
        "certs": home / "certs",
        "ca": home / "certs" / "ca",
        "service_data": home / "services",
        "overrides": home / "overrides",
        "overrides_pkg": home / "overrides" / "djamp_overrides",
        "caddy": home / "caddy",
        "caddy_sites": home / "caddy" / "sites",
        "caddy_file": home / "caddy" / "Caddyfile",
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_project_paths(project: Project) -> Project:
    """Normalize project.path and venvPath to absolute paths when possible.

    In packaged builds, users should provide absolute paths (file picker),
    but in development it's common to paste repo-relative paths.
    """
    try:
        root = Path(project.path).expanduser()
        if not root.is_absolute():
            root = (_repo_root() / root).resolve()
        else:
            root = root.resolve()
        project.path = str(root)
    except Exception:
        return project

    # For now, keep venv inside the project (MAMP-like). Relative venvPath values from older registries
    # may be repo-relative; resolving those can create duplicated paths. Normalize to "<project>/.venv".
    try:
        project.venvPath = str((Path(project.path) / ".venv").resolve())
    except Exception:
        pass

    return project


def ensure_dirs() -> None:
    p = paths()
    for key in [
        "home",
        "bin",
        "logs",
        "django_logs",
        "proxy_logs",
        "db_logs",
        "certs",
        "ca",
        "service_data",
        "overrides",
        "overrides_pkg",
        "caddy",
        "caddy_sites",
    ]:
        p[key].mkdir(parents=True, exist_ok=True)


def default_registry() -> Registry:
    return Registry()


def load_registry_sync() -> Registry:
    ensure_dirs()
    registry_file = paths()["registry"]
    if not registry_file.exists():
        data = default_registry()
        registry_file.write_text(data.model_dump_json(indent=2), encoding="utf-8")
        return data

    raw = registry_file.read_text(encoding="utf-8").strip()
    if not raw:
        data = default_registry()
        registry_file.write_text(data.model_dump_json(indent=2), encoding="utf-8")
        return data

    parsed = Registry.model_validate_json(raw)
    return parsed


def save_registry_sync(registry: Registry) -> None:
    ensure_dirs()
    paths()["registry"].write_text(_scrub_registry_for_storage(registry).model_dump_json(indent=2), encoding="utf-8")


def _scrub_project_for_storage(project: Project) -> Project:
    """Remove secrets before persisting project state to disk.

    The project `.env` should remain the source of truth for secrets. This reduces the
    blast radius of leaking `registry.json` (which is stored unencrypted on disk).
    """
    cleaned = project.model_copy(deep=True)
    try:
        cleaned.database.password = ""
    except Exception:
        pass
    # environmentVars may contain secrets; for MVP we don't persist them.
    cleaned.environmentVars = {}
    return cleaned


def _scrub_registry_for_storage(registry: Registry) -> Registry:
    return Registry(
        projects=[_scrub_project_for_storage(p) for p in registry.projects],
        settings=registry.settings.model_copy(deep=True),
    )


async def read_registry() -> Registry:
    async with REGISTRY_LOCK:
        return load_registry_sync()


async def write_registry(registry: Registry) -> None:
    async with REGISTRY_LOCK:
        save_registry_sync(registry)


async def mutate_registry(mutator) -> Registry:
    async with REGISTRY_LOCK:
        current = load_registry_sync()
        updated = mutator(current)
        save_registry_sync(updated)
        return updated


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _canonical_project_id(project_id: str) -> Optional[str]:
    raw = (project_id or "").strip()
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw))
    except (ValueError, TypeError, AttributeError):
        return None


def _require_project_id(project_id: str) -> str:
    parsed = _canonical_project_id(project_id)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    return parsed


def _safe_log_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    for key in ("django_logs", "proxy_logs", "db_logs"):
        root = paths()[key].expanduser().resolve()
        if _is_relative_to(candidate, root):
            return candidate
    raise RuntimeError("Invalid log path")


def project_log_path(project_id: str) -> Path:
    safe_project_id = _canonical_project_id(project_id)
    if not safe_project_id:
        raise ValueError("Invalid project ID")
    return paths()["django_logs"] / f"{safe_project_id}.log"


def service_log_path(service_name: str) -> Path:
    safe_name = (service_name or "").strip().lower()
    if not safe_name or not re.fullmatch(r"[a-z0-9_-]+", safe_name):
        raise ValueError("Invalid service name")
    return paths()["db_logs"] / f"{safe_name}.log"


def _tail_file(path: Path, max_chars: int = 2000) -> str:
    try:
        safe_path = _safe_log_path(path)
    except Exception:
        return ""
    if not safe_path.exists():
        return ""
    try:
        data = safe_path.read_text(encoding="utf-8", errors="ignore")
        return data[-max_chars:]
    except Exception:
        return ""


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def _kill_processes_on_port(port: int) -> None:
    if platform.system() == "Windows" or not shutil.which("lsof"):
        return

    try:
        result = subprocess.run(
            ["lsof", "-ti", f"TCP:{int(port)}"],
            text=True,
            capture_output=True,
            check=False,
        )
        pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        current_pid = os.getpid()
        target_pids = [pid for pid in pids if pid != current_pid]
        for pid in target_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        time.sleep(0.4)

        for pid in target_pids:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        # Best effort cleanup only.
        return


def _kill_stray_project_processes(manage_py: Path, port: int) -> None:
    """Best-effort cleanup for orphaned runserver processes that may not be listening anymore."""
    if platform.system() == "Windows" or not shutil.which("pgrep"):
        return

    pattern = f"{str(manage_py)}.*runserver.*{int(port)}"
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            text=True,
            capture_output=True,
            check=False,
        )
        current_pid = os.getpid()
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.isdigit():
                continue
            pid = int(line)
            if pid == current_pid:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        time.sleep(0.3)
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.isdigit():
                continue
            pid = int(line)
            if pid == current_pid:
                continue
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        return


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    if platform.system() == "Windows":
        proc.terminate()
        await proc.wait()
        return

    # When started with start_new_session=True, proc.pid is the process group leader.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.terminate()

    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
        return
    except asyncio.TimeoutError:
        pass

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()
    await proc.wait()


def _platform_python(project: Project) -> Path:
    if project.venvPath:
        venv = Path(project.venvPath)
    else:
        venv = Path(project.path) / ".venv"

    if platform.system() == "Windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _find_manage_py(project: Project) -> Path:
    root = Path(project.path)
    direct = root / "manage.py"
    if direct.exists():
        return direct

    for candidate in root.rglob("manage.py"):
        return candidate

    raise FileNotFoundError(f"manage.py not found in {project.path}")


def _sanitize_hostname(value: str) -> str:
    """Return a safe hostname string for use in hosts/proxy/cert generation.

    We intentionally restrict to ASCII hostnames for MVP to avoid path traversal
    and config injection issues (e.g. writing cert files named with '/' etc).
    """
    raw = (value or "").strip()
    if not raw:
        raise RuntimeError("Domain is empty")

    # Allow users to paste URLs like https://example.test
    if raw.startswith(("http://", "https://")):
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


def _ensure_django_settings_override(project: Project) -> str:
    """Generate a lightweight settings wrapper to apply DJAMP-specific overrides without editing the project."""
    ensure_dirs()
    pkg_dir = paths()["overrides_pkg"]
    init_py = pkg_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("# Auto-generated by DJAMP PRO\n", encoding="utf-8")

    safe_id = project.id.replace("-", "_")
    module_name = f"djamp_overrides.p_{safe_id}"
    module_path = pkg_dir / f"p_{safe_id}.py"

    hosts = sorted(set(_project_domains(project) + ["localhost", "127.0.0.1"]))
    origins = sorted(set([f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts]))

    def py_list(values: List[str]) -> str:
        return "[" + ", ".join([repr(v) for v in values]) + "]"

    content = "\n".join(
        [
            "# Auto-generated by DJAMP PRO. Do not edit by hand.",
            "from importlib import import_module as _import_module",
            "from pathlib import Path as _Path",
            "",
            f"_base = _import_module({project.settingsModule!r})",
            "for _k in dir(_base):",
            "    if _k.isupper():",
            "        globals()[_k] = getattr(_base, _k)",
            "",
            "# DJAMP overrides",
            f"DEBUG = {bool(project.debug)}",
            "SECURE_SSL_REDIRECT = False",
            f"_DJAMP_ALLOWED_HOSTS = {py_list(hosts)}",
            "try:",
            "    ALLOWED_HOSTS = sorted(set(list(ALLOWED_HOSTS) + _DJAMP_ALLOWED_HOSTS))",
            "except Exception:",
            "    ALLOWED_HOSTS = sorted(set(_DJAMP_ALLOWED_HOSTS))",
            "",
            f"_DJAMP_CSRF_ORIGINS = {py_list(origins)}",
            "try:",
            "    CSRF_TRUSTED_ORIGINS = sorted(set(list(CSRF_TRUSTED_ORIGINS) + _DJAMP_CSRF_ORIGINS))",
            "except Exception:",
            "    CSRF_TRUSTED_ORIGINS = sorted(set(_DJAMP_CSRF_ORIGINS))",
            "",
            "# When HTTPS is disabled locally, make cookies dev-friendly.",
            f"_DJAMP_HTTPS_ENABLED = {bool(project.httpsEnabled)}",
            "if not _DJAMP_HTTPS_ENABLED:",
            "    CSRF_COOKIE_SECURE = False",
            "    SESSION_COOKIE_SECURE = False",
            "",
            "# Keep static handling stable when the base settings build STATIC_* from DEBUG branches.",
            f"_DJAMP_PROJECT_ROOT = _Path({project.path!r})",
            f"_DJAMP_STATIC_DIR = _DJAMP_PROJECT_ROOT / {project.staticPath!r}",
            "_DJAMP_STATIC_ROOT = _DJAMP_PROJECT_ROOT / 'staticfiles'",
            "try:",
            "    _djamp_static_dirs = [str(_p) for _p in list(STATICFILES_DIRS)]",
            "except Exception:",
            "    _djamp_static_dirs = []",
            "if _DJAMP_STATIC_DIR.exists():",
            "    _djamp_static_value = str(_DJAMP_STATIC_DIR)",
            "    if _djamp_static_value not in _djamp_static_dirs:",
            "        _djamp_static_dirs.append(_djamp_static_value)",
            "if _djamp_static_dirs:",
            "    STATICFILES_DIRS = _djamp_static_dirs",
            "STATIC_ROOT = str(_DJAMP_STATIC_ROOT)",
            "",
            "",
        ]
    )
    # Avoid rewriting unchanged content; Django autoreloader watches this file.
    existing = module_path.read_text(encoding="utf-8", errors="ignore") if module_path.exists() else ""
    if existing != content:
        module_path.write_text(content, encoding="utf-8")
    return module_name


def _base_env(project: Project) -> Dict[str, str]:
    env = os.environ.copy()
    env.update(project.environmentVars)
    if project.settingsModule:
        env.setdefault("DJANGO_SETTINGS_MODULE", project.settingsModule)
    # Ensure logs flush promptly even when redirected to files.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _prepend_path_env(env: Dict[str, str], prefix: Path) -> None:
    try:
        resolved = str(prefix.expanduser().resolve())
    except Exception:
        return

    current = env.get("PATH", "")
    env["PATH"] = f"{resolved}{os.pathsep}{current}" if current else resolved


def _apply_djamp_project_env(project: Project, env: Dict[str, str]) -> Dict[str, str]:
    out = dict(env)

    # Settings override module + PYTHONPATH so Django can import it.
    module_name = _ensure_django_settings_override(project)
    out["DJANGO_SETTINGS_MODULE"] = module_name

    overrides_root = str(paths()["overrides"])
    sep = ";" if platform.system() == "Windows" else ":"
    existing = out.get("PYTHONPATH", "").strip()
    out["PYTHONPATH"] = f"{overrides_root}{sep}{existing}" if existing else overrides_root

    # Common DB env var conventions (many projects use python-dotenv without override=True).
    if project.database.type == "postgres":
        # Override any existing values in project.environmentVars to keep managed DB consistent.
        out["DB_NAME"] = project.database.name
        out["DB_USER"] = project.database.username
        out["DB_PASSWORD"] = project.database.password or ""
        out["DB_HOST"] = "127.0.0.1"
        out["DB_PORT"] = str(project.database.port or MANAGED_POSTGRES_PORT)
        if project.database.name and project.database.username:
            out["DATABASE_URL"] = (
                f"postgres://{project.database.username}:{project.database.password or ''}"
                f"@127.0.0.1:{project.database.port or MANAGED_POSTGRES_PORT}/{project.database.name}"
            )
    elif project.database.type == "mysql":
        out["DB_NAME"] = project.database.name
        out["DB_USER"] = project.database.username
        out["DB_PASSWORD"] = project.database.password or ""
        out["DB_HOST"] = "127.0.0.1"
        out["DB_PORT"] = str(project.database.port or MANAGED_MYSQL_PORT)
        if project.database.name and project.database.username:
            out["DATABASE_URL"] = (
                f"mysql://{project.database.username}:{project.database.password or ''}"
                f"@127.0.0.1:{project.database.port or MANAGED_MYSQL_PORT}/{project.database.name}"
            )

    if project.cache.type == "redis":
        out.setdefault("REDIS_HOST", "127.0.0.1")
        out.setdefault("REDIS_PORT", str(project.cache.port or MANAGED_REDIS_PORT))

    return out


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
    "security",
    "uv",
    "uv.exe",
}


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

    search_path = None
    if env:
        search_path = env.get("PATH")
    if not search_path:
        search_path = os.environ.get("PATH")

    resolved = shutil.which(executable, path=search_path)
    if not resolved:
        raise RuntimeError(f"Executable not found in PATH: {executable}")
    resolved_path = Path(resolved).expanduser().resolve()

    allowed_roots = [
        safe_cwd,
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
    if not any(_is_relative_to(resolved_path, root) for root in allowed_roots):
        raise RuntimeError("Executable path is outside allowed roots")
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


def _macos_pf_redirect_configured(http_target_port: int, https_target_port: int) -> bool:
    """Return True when the DJAMP PF redirect rules exist for the given target ports (macOS)."""
    if platform.system() != "Darwin":
        return True

    anchor_name = "djamp-pro"
    anchor_path = Path(f"/etc/pf.anchors/{anchor_name}")
    pf_conf = Path("/etc/pf.conf")

    anchor_content = "\n".join(
        [
            "# DJAMP PRO managed PF redirect (loopback only)",
            f"rdr pass on lo0 inet proto tcp from any to any port 80 -> 127.0.0.1 port {int(http_target_port)}",
            f"rdr pass on lo0 inet proto tcp from any to any port 443 -> 127.0.0.1 port {int(https_target_port)}",
            "",
        ]
    )

    pf_block_lines = [
        MANAGED_PF_BEGIN,
        f'anchor "{anchor_name}"',
        f'load anchor "{anchor_name}" from "{anchor_path}"',
        MANAGED_PF_END,
    ]

    try:
        if not anchor_path.exists() or not pf_conf.exists():
            return False
        existing = anchor_path.read_text(encoding="utf-8", errors="ignore")
        if existing.strip() != anchor_content.strip():
            return False

        conf_text = pf_conf.read_text(encoding="utf-8", errors="ignore")
        if MANAGED_PF_BEGIN in conf_text and MANAGED_PF_END in conf_text:
            _before, managed, _after = _split_marked_sections(conf_text, MANAGED_PF_BEGIN, MANAGED_PF_END)
            if managed and [line.strip() for line in managed] == [line.strip() for line in pf_block_lines]:
                return True
        # Older versions appended lines without markers; accept if present.
        if all(line in conf_text for line in pf_block_lines[1:3]):
            return True
        return False
    except Exception:
        return False


def _ensure_macos_pf_redirect(http_target_port: int, https_target_port: int) -> CommandResult:
    """Redirect standard ports 80/443 on loopback to the configured proxy ports using PF (macOS)."""
    if platform.system() != "Darwin":
        return CommandResult(success=True, output="PF redirect not applicable")
    if os.getenv("DJAMP_SKIP_PF") == "1":
        return CommandResult(success=True, output="PF redirect skipped via DJAMP_SKIP_PF=1")

    anchor_name = "djamp-pro"
    anchor_path = Path(f"/etc/pf.anchors/{anchor_name}")
    pf_conf = Path("/etc/pf.conf")

    anchor_content = "\n".join(
        [
            "# DJAMP PRO managed PF redirect (loopback only)",
            f"rdr pass on lo0 inet proto tcp from any to any port 80 -> 127.0.0.1 port {int(http_target_port)}",
            f"rdr pass on lo0 inet proto tcp from any to any port 443 -> 127.0.0.1 port {int(https_target_port)}",
            "",
        ]
    )

    pf_block_lines = [
        MANAGED_PF_BEGIN,
        f'anchor "{anchor_name}"',
        f'load anchor "{anchor_name}" from "{anchor_path}"',
        MANAGED_PF_END,
    ]

    # If already configured, do nothing (avoid repeated elevation prompts).
    try:
        if anchor_path.exists():
            existing = anchor_path.read_text(encoding="utf-8", errors="ignore")
            if existing.strip() == anchor_content.strip():
                conf_text = pf_conf.read_text(encoding="utf-8", errors="ignore")
                if MANAGED_PF_BEGIN in conf_text and MANAGED_PF_END in conf_text:
                    before, managed, after = _split_marked_sections(conf_text, MANAGED_PF_BEGIN, MANAGED_PF_END)
                    if managed and [line.strip() for line in managed] == [line.strip() for line in pf_block_lines]:
                        return CommandResult(success=True, output="PF redirect already configured")
                # Older versions appended lines without markers; accept if present.
                if all(line in conf_text for line in pf_block_lines[1:3]):
                    return CommandResult(success=True, output="PF redirect already configured")
    except Exception:
        # Best effort only.
        pass

    staged_anchor = paths()["home"] / "pf.anchor.staged"
    staged_anchor.write_text(anchor_content, encoding="utf-8")

    # Ensure pf.conf loads our anchor.
    try:
        conf_text = pf_conf.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return CommandResult(success=False, error=f"Unable to read {pf_conf}: {exc}")

    needs_conf_update = True
    staged_pf_conf = paths()["home"] / "pf.conf.staged"
    try:
        before, _managed, after = _split_marked_sections(conf_text, MANAGED_PF_BEGIN, MANAGED_PF_END)
        new_conf = _join_marked_sections(before, pf_block_lines, after)
        if new_conf.strip() == conf_text.strip():
            needs_conf_update = False
        else:
            staged_pf_conf.write_text(new_conf, encoding="utf-8")
    except Exception as exc:
        return CommandResult(success=False, error=f"Unable to prepare PF configuration: {exc}")

    # Apply changes with a single elevation prompt.
    script_parts: List[str] = []
    script_parts.append(f"/usr/bin/install -m 644 {shlex.quote(str(staged_anchor))} {shlex.quote(str(anchor_path))}")
    if needs_conf_update:
        script_parts.append(f"/usr/bin/install -m 644 {shlex.quote(str(staged_pf_conf))} {shlex.quote(str(pf_conf))}")
    script_parts.append(f"/sbin/pfctl -f {shlex.quote(str(pf_conf))}")
    script_parts.append("/sbin/pfctl -E")
    script = "set -e; " + " && ".join(script_parts)

    result = _run_with_macos_elevation(["/bin/sh", "-c", script], cwd=paths()["home"])
    if not result.success:
        return result
    return CommandResult(success=True, output="PF redirect enabled")


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


def _ensure_uv_runtime(project: Project) -> CommandResult:
    python_path = _platform_python(project)
    project_root = Path(project.path)

    uv_bin = shutil.which("uv")
    if not uv_bin:
        return CommandResult(success=False, error="`uv` is not installed or not in PATH")

    if not python_path.exists():
        venv_path = python_path.parent.parent
        create = _run_blocking([uv_bin, "venv", str(venv_path)], project_root)
        if not create.success:
            return create

    requirements = project_root / "requirements.txt"
    if requirements.exists():
        install = _run_blocking(
            [uv_bin, "pip", "install", "--python", str(python_path), "-r", str(requirements)],
            project_root,
        )
        if not install.success:
            return install

    return CommandResult(success=True)


def _conda_env_prefix(env_name: str) -> Path:
    conda_bin = shutil.which("conda")
    if not conda_bin:
        raise RuntimeError("Conda runtime selected but `conda` is not in PATH")

    info = _run_blocking([conda_bin, "info", "--envs", "--json"], paths()["home"])
    if not info.success:
        raise RuntimeError(info.error or "Unable to query conda environments")

    try:
        data = json.loads(info.output)
    except Exception as exc:
        raise RuntimeError(f"Invalid JSON returned by conda: {exc}") from exc

    root_prefix = data.get("root_prefix") or data.get("conda_prefix")
    if env_name in ("base", "root") and root_prefix:
        return Path(root_prefix)

    envs = data.get("envs") or []
    for raw in envs:
        p = Path(raw)
        if p.name == env_name:
            return p

    raise RuntimeError(f"Conda environment not found: {env_name}")


def _conda_python_from_prefix(prefix: Path) -> Path:
    if platform.system() == "Windows":
        candidates = [prefix / "python.exe", prefix / "Scripts" / "python.exe"]
    else:
        candidates = [prefix / "bin" / "python3", prefix / "bin" / "python"]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise RuntimeError(f"Python interpreter not found in conda env: {prefix}")


def _build_manage_command(project: Project, manage_py: Path, django_args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    mode = project.runtimeMode
    env = _base_env(project)

    if mode == "uv":
        runtime_result = _ensure_uv_runtime(project)
        if not runtime_result.success:
            raise RuntimeError(runtime_result.error or "Failed to initialize uv runtime")

        python_bin = _platform_python(project)
        _prepend_path_env(env, python_bin.parent)
        return ["python", str(manage_py), *django_args], env

    if mode == "conda":
        env_name = project.condaEnv.strip()
        if not env_name:
            raise RuntimeError("Conda runtime selected but condaEnv is empty")

        # Avoid `conda run` for long-lived processes; it often wraps execution in temp scripts
        # and can leave orphaned shells. Resolve the env prefix and run the env's Python directly.
        prefix = _conda_env_prefix(env_name)
        _ = _conda_python_from_prefix(prefix)

        env["CONDA_DEFAULT_ENV"] = env_name
        env["CONDA_PREFIX"] = str(prefix)
        if platform.system() != "Windows":
            _prepend_path_env(env, prefix / "bin")

        return ["python", str(manage_py), *django_args], env

    if mode == "custom":
        custom = project.customInterpreter.strip()
        if not custom:
            raise RuntimeError("Custom runtime selected but customInterpreter is empty")
        parts = shlex.split(custom)
        if len(parts) != 1:
            raise RuntimeError("Custom runtime must be a single Python executable path")
        custom_exec = parts[0].strip()
        if not custom_exec:
            raise RuntimeError("Custom runtime executable is empty")

        exec_name = custom_exec
        if "/" in custom_exec or "\\" in custom_exec:
            custom_path = Path(custom_exec).expanduser().resolve()
            if not custom_path.exists() or not custom_path.is_file():
                raise RuntimeError(f"Custom interpreter not found: {custom_path}")
            _prepend_path_env(env, custom_path.parent)
            exec_name = custom_path.name

        if not re.fullmatch(r"[A-Za-z0-9._+-]+", exec_name):
            raise RuntimeError("Custom interpreter contains unsupported characters")
        return [exec_name, str(manage_py), *django_args], env

    interpreter = shutil.which("python3") or shutil.which("python")
    if not interpreter:
        raise RuntimeError("No Python interpreter found")

    return [Path(interpreter).name, str(manage_py), *django_args], env


def _flush_macos_dns_cache() -> None:
    if platform.system() != "Darwin":
        return
    # Best-effort; errors are ignored. This helps apply /etc/hosts updates immediately.
    for cmd in (["/usr/bin/dscacheutil", "-flushcache"], ["/usr/bin/killall", "-HUP", "mDNSResponder"]):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass


def _sync_domains_for_registry_impl(registry: Registry) -> CommandResult:
    if os.getenv("DJAMP_SKIP_HOSTS") == "1":
        return CommandResult(success=True, output="Hosts sync skipped via DJAMP_SKIP_HOSTS=1")

    # Build a stable list of desired host entries. Sorting avoids spurious diffs and prompts.
    desired_domains: List[str] = sorted({"localhost", *{d for project in registry.projects for d in _project_domains(project)}})
    entries = [f"127.0.0.1 {domain}" for domain in desired_domains]

    hosts_file = (
        Path("C:/Windows/System32/drivers/etc/hosts")
        if platform.system() == "Windows"
        else Path("/etc/hosts")
    )

    # Preflight: if the hosts file is already in the desired state, avoid any privileged execution.
    try:
        if hosts_file.exists():
            current = hosts_file.read_text(encoding="utf-8", errors="ignore")
            before, managed, after = _split_hosts_sections(current)
            if not entries:
                if not managed:
                    return CommandResult(success=True, output="Hosts file already clean")
                new_content = _join_without_section(before, after)
                if new_content.strip() == current.strip():
                    return CommandResult(success=True, output="Hosts file already clean")
            else:
                block_lines = [MANAGED_HOSTS_BEGIN, *entries, MANAGED_HOSTS_END]
                new_content = _join_hosts_sections(before, block_lines, after)
                if new_content.strip() == current.strip():
                    return CommandResult(success=True, output="Hosts file already up to date")
    except Exception:
        # Preflight is best-effort; continue with helper/direct write below.
        pass

    # Prefer the installed macOS helper daemon (MAMP-style): no repeated password prompts.
    if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
        helper_domains = [line.split(" ", 1)[1] for line in entries]
        helper_result = _helper_hosts_clear() if not helper_domains else _helper_hosts_apply(helper_domains)
        if helper_result.success:
            return CommandResult(success=True, output="Hosts file updated via DJAMP Helper")

    helper = _priv_helper_binary()
    if helper:
        helper_domains = [line.split(" ", 1)[1] for line in entries]
        helper_command = (
            [str(helper), "hosts", "clear"]
            if not helper_domains
            else [str(helper), "hosts", "apply", *helper_domains]
        )
        helper_env = os.environ.copy()
        _prepend_path_env(helper_env, helper.parent)
        helper_run = _run_blocking(helper_command, paths()["home"], helper_env)
        if helper_run.success:
            _flush_macos_dns_cache()
            return CommandResult(success=True, output="Hosts file updated via privileged helper")

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
        before, managed, after = _split_hosts_sections(current)
        block_lines = [MANAGED_HOSTS_BEGIN, *entries, MANAGED_HOSTS_END]
        new_content = _join_hosts_sections(before, block_lines, after)
        if new_content.strip() == current.strip():
            return CommandResult(success=True, output="Hosts file already up to date")

        # Attempt direct write first (will work when running elevated).
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
                tmp.write(new_content)
                tmp_path = Path(tmp.name)
            os.replace(tmp_path, hosts_file)
            _flush_macos_dns_cache()
            return CommandResult(success=True, output="Hosts file updated")
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


async def _sync_domains_for_registry(registry: Registry) -> CommandResult:
    # Hosts changes may require privilege elevation and can block for user interaction;
    # run them off the main event loop to keep the API responsive.
    return await asyncio.to_thread(_sync_domains_for_registry_impl, registry)


def _clear_hosts_block_impl() -> CommandResult:
    if os.getenv("DJAMP_SKIP_HOSTS") == "1":
        return CommandResult(success=True, output="Hosts clear skipped via DJAMP_SKIP_HOSTS=1")

    hosts_file = (
        Path("C:/Windows/System32/drivers/etc/hosts")
        if platform.system() == "Windows"
        else Path("/etc/hosts")
    )

    # Preflight: avoid privilege prompts when there's nothing to clear.
    try:
        if hosts_file.exists():
            current = hosts_file.read_text(encoding="utf-8", errors="ignore")
            _before, managed, _after = _split_hosts_sections(current)
            if not managed:
                return CommandResult(success=True, output="Hosts file already clean")
    except Exception:
        pass

    # Prefer the installed macOS helper daemon (MAMP-style): no repeated password prompts.
    if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
        helper_result = _helper_hosts_clear()
        if helper_result.success:
            return CommandResult(success=True, output="Hosts file cleared via DJAMP Helper")

    helper = _priv_helper_binary()
    if helper:
        helper_command = [str(helper), "hosts", "clear"]
        helper_env = os.environ.copy()
        _prepend_path_env(helper_env, helper.parent)
        helper_run = _run_blocking(helper_command, paths()["home"], helper_env)
        if helper_run.success:
            _flush_macos_dns_cache()
            return CommandResult(success=True, output="Hosts file cleared via privileged helper")
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
        before, managed, after = _split_hosts_sections(current)
        if not managed:
            return CommandResult(success=True, output="Hosts file already clean")

        new_content = _join_without_section(before, after)

        # Attempt direct write first (will work when running elevated).
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
                tmp.write(new_content)
                tmp_path = Path(tmp.name)
            os.replace(tmp_path, hosts_file)
            _flush_macos_dns_cache()
            return CommandResult(success=True, output="Hosts file cleared")
        except PermissionError:
            if platform.system() != "Darwin":
                raise

        return CommandResult(
            success=False,
            error=(
                f"Permission denied updating {hosts_file}. Install the DJAMP Helper from Settings to clear hosts changes."
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


def _parse_dotenv_file(path: Path) -> Dict[str, str]:
    """Minimal .env parser for KEY=VALUE lines.

    This is intentionally conservative: it handles comments/blank lines and basic quoting.
    """
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    env: Dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def _dotenv_path(project: Project) -> Path:
    return Path(project.path) / ".env"


def _extract_db_from_dotenv(env: Dict[str, str]) -> Dict[str, Any]:
    """Return DB fields found in .env (best-effort)."""
    out: Dict[str, Any] = {}

    db_name = (env.get("DB_NAME") or env.get("POSTGRES_DB") or "").strip()
    db_user = (env.get("DB_USER") or env.get("POSTGRES_USER") or "").strip()
    db_password = (env.get("DB_PASSWORD") or env.get("POSTGRES_PASSWORD") or "").strip()
    db_host = (env.get("DB_HOST") or "").strip()
    db_port = (env.get("DB_PORT") or "").strip()

    if db_name:
        out["name"] = db_name
    if db_user:
        out["username"] = db_user
    if db_password or "DB_PASSWORD" in env or "POSTGRES_PASSWORD" in env:
        out["password"] = db_password
    if db_host:
        out["host"] = db_host
    if db_port.isdigit():
        out["port"] = int(db_port)

    database_url = (env.get("DATABASE_URL") or "").strip()
    if database_url:
        out["database_url"] = database_url
        try:
            parsed = urlparse(database_url)
            if parsed.scheme in ("postgres", "postgresql"):
                out.setdefault("type", "postgres")
            elif parsed.scheme in ("mysql", "mysql2"):
                out.setdefault("type", "mysql")
            if parsed.hostname:
                out.setdefault("host", parsed.hostname)
            if parsed.port:
                out.setdefault("port", int(parsed.port))
            if parsed.username:
                out.setdefault("username", parsed.username)
            if parsed.password is not None:
                out.setdefault("password", parsed.password)
            if parsed.path and parsed.path != "/":
                out.setdefault("name", parsed.path.lstrip("/"))
        except Exception:
            pass

    return out


def _is_sensitive_env_key(key: str) -> bool:
    upper = (key or "").upper()
    if not upper:
        return False
    if "PASSWORD" in upper or upper.endswith("_PASS"):
        return True
    if "SECRET" in upper or "TOKEN" in upper or "PRIVATE" in upper:
        return True
    if upper.endswith("_KEY") and upper not in {"SECRET_KEY_FALLBACK"}:
        return True
    return upper in {"DB_PASSWORD", "KKU_SERVICES_PASS"}


def _mask_sensitive_env_value(value: str) -> str:
    raw = value or ""
    if len(raw) <= 2:
        return "*" * len(raw)
    if len(raw) <= 6:
        return f"{raw[0]}{'*' * (len(raw) - 2)}{raw[-1]}"
    return f"{raw[:2]}{'*' * (len(raw) - 4)}{raw[-2:]}"


def _display_environment_vars(project: Project) -> Dict[str, str]:
    """Return .env values for UI display with sensitive keys masked."""
    env = _parse_dotenv_file(_dotenv_path(project))
    if project.settingsModule:
        env.setdefault("DJANGO_SETTINGS_MODULE", project.settingsModule)

    visible: Dict[str, str] = {}
    for key in sorted(env.keys()):
        value = env.get(key, "")
        visible[key] = _mask_sensitive_env_value(value) if _is_sensitive_env_key(key) else value
    return visible


def _sync_managed_env_block(project: Project, values: Dict[str, str]) -> CommandResult:
    """Write a DJAMP-managed .env block at the end of the project's .env file.

    This keeps the project as the source of truth (it reads .env), while allowing DJAMP
    to override DB host/port to the managed local services without destroying user config.
    """
    env_path = _dotenv_path(project)
    try:
        current = env_path.read_text(encoding="utf-8", errors="ignore") if env_path.exists() else ""
        before, _managed, after = _split_marked_sections(current, MANAGED_ENV_BEGIN, MANAGED_ENV_END)

        ordered_keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DATABASE_URL"]
        block_lines: List[str] = [MANAGED_ENV_BEGIN]
        for key in ordered_keys:
            if key in values and values[key] is not None:
                block_lines.append(f"{key}={values[key]}")
        block_lines.append(MANAGED_ENV_END)

        new_content = _join_marked_sections(before, block_lines, after)
        if new_content.strip() != current.strip():
            env_path.write_text(new_content, encoding="utf-8")
        return CommandResult(success=True, output=f"Updated {env_path.name}")
    except Exception as exc:
        return CommandResult(success=False, error=f"Failed to update .env: {exc}")


def _hydrate_project_db_from_dotenv(project: Project) -> Project:
    """Update project.database fields from the project's .env (best-effort).

    The .env is treated as authoritative for DB_NAME/DB_USER/DB_PASSWORD to reduce confusion.
    """
    env = _parse_dotenv_file(_dotenv_path(project))
    db = _extract_db_from_dotenv(env)

    # Only apply when we have at least one concrete DB credential.
    if not any(k in db for k in ("name", "username", "password", "database_url")):
        return project

    if "type" in db and project.database.type == "none":
        # If the project did not configure a managed DB, don't change that automatically.
        return project

    if "name" in db and db["name"]:
        project.database.name = str(db["name"])
    if "username" in db and db["username"]:
        project.database.username = str(db["username"])
    if "password" in db and db["password"] is not None:
        project.database.password = str(db["password"])

    # Do not take host/port from .env for managed services; DJAMP manages these.
    return project


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

    cargo = shutil.which("cargo")
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


def _certificate_paths(domain: str) -> Tuple[Path, Path, Path]:
    cert_dir = paths()["certs"]
    cert_dir.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_hostname(domain)
    safe_hash = hashlib.sha256(safe.encode("utf-8")).hexdigest()
    cert = cert_dir / f"{safe_hash}.crt"
    key = cert_dir / f"{safe_hash}.key"
    conf = cert_dir / f"{safe_hash}.cnf"
    return cert, key, conf


def _root_ca_paths() -> Tuple[Path, Path]:
    ca_dir = paths()["ca"]
    ca_dir.mkdir(parents=True, exist_ok=True)
    return ca_dir / "djamp-pro-root-ca.crt", ca_dir / "djamp-pro-root-ca.key"


def _ensure_root_ca() -> CommandResult:
    openssl = shutil.which("openssl")
    if not openssl:
        return CommandResult(success=False, error="`openssl` was not found in PATH")

    ca_cert, ca_key = _root_ca_paths()
    if ca_cert.exists() and ca_key.exists():
        if platform.system() != "Windows":
            # Best-effort permission tightening even when the CA already exists.
            try:
                paths()["ca"].chmod(0o700)
            except Exception:
                pass
            try:
                ca_key.chmod(0o600)
            except Exception:
                pass
            try:
                ca_cert.chmod(0o644)
            except Exception:
                pass
        return CommandResult(success=True, output="Root CA already exists")

    ca_conf = paths()["ca"] / "root-ca.cnf"
    ca_conf.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = dn",
                "x509_extensions = v3_ca",
                "prompt = no",
                "",
                "[dn]",
                "C = US",
                "ST = Local",
                "L = Local",
                "O = DJAMP PRO",
                "OU = Development",
                "CN = DJAMP PRO Root CA",
                "",
                "[v3_ca]",
                "basicConstraints = critical,CA:TRUE,pathlen:0",
                "keyUsage = critical,keyCertSign,cRLSign",
                "subjectKeyIdentifier = hash",
                "authorityKeyIdentifier = keyid:always,issuer",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = [
        openssl,
        "req",
        "-x509",
        "-newkey",
        "rsa:4096",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_cert),
        "-days",
        "3650",
        "-nodes",
        "-config",
        str(ca_conf),
        "-extensions",
        "v3_ca",
    ]
    result = _run_blocking(cmd, paths()["home"])
    if result.success and platform.system() != "Windows":
        # Protect the CA private key (it can sign certs for any hostname).
        try:
            paths()["ca"].chmod(0o700)
        except Exception:
            pass
        try:
            ca_key.chmod(0o600)
        except Exception:
            pass
        try:
            ca_cert.chmod(0o644)
        except Exception:
            pass
    return result


def _generate_certificate(domain: str, alt_domains: Optional[List[str]] = None) -> CertificateInfo:
    ensure = _ensure_root_ca()
    if not ensure.success:
        raise RuntimeError(ensure.error)

    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("`openssl` was not found in PATH")

    primary = _sanitize_hostname(domain)
    cert, key, conf = _certificate_paths(primary)
    ca_cert, ca_key = _root_ca_paths()

    sans = [primary]
    if alt_domains:
        for d in alt_domains:
            cleaned = _try_sanitize_hostname(d)
            if cleaned and cleaned not in sans:
                sans.append(cleaned)

    alt_lines = [f"DNS.{idx + 1} = {value}" for idx, value in enumerate(sans)]
    conf.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = req_distinguished_name",
                "req_extensions = v3_req",
                "prompt = no",
                "",
                "[req_distinguished_name]",
                f"CN = {primary}",
                "",
                "[v3_req]",
                "basicConstraints = critical,CA:FALSE",
                "keyUsage = critical,digitalSignature,keyEncipherment",
                "extendedKeyUsage = serverAuth",
                "subjectAltName = @alt_names",
                "",
                "[alt_names]",
                *alt_lines,
            ]
        ),
        encoding="utf-8",
    )

    csr = cert.with_suffix(".csr")

    run_key = _run_blocking([openssl, "genrsa", "-out", str(key), "2048"], paths()["home"])
    if not run_key.success:
        raise RuntimeError(run_key.error)

    run_csr = _run_blocking(
        [openssl, "req", "-new", "-key", str(key), "-out", str(csr), "-config", str(conf)],
        paths()["home"],
    )
    if not run_csr.success:
        raise RuntimeError(run_csr.error)

    run_sign = _run_blocking(
        [
            openssl,
            "x509",
            "-req",
            "-in",
            str(csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(cert),
            "-days",
            "365",
            "-sha256",
            "-extensions",
            "v3_req",
            "-extfile",
            str(conf),
        ],
        paths()["home"],
    )
    try:
        csr.unlink(missing_ok=True)
        conf.unlink(missing_ok=True)
    except Exception:
        pass

    if not run_sign.success:
        raise RuntimeError(run_sign.error)

    if platform.system() != "Windows":
        try:
            paths()["certs"].chmod(0o700)
        except Exception:
            pass
        try:
            key.chmod(0o600)
        except Exception:
            pass
        try:
            cert.chmod(0o644)
        except Exception:
            pass

    expires = _get_cert_expiration(cert)
    return CertificateInfo(
        domain=primary,
        certificatePath=str(cert),
        keyPath=str(key),
        expiresAt=expires,
        isValid=True,
    )


def _get_cert_expiration(cert_path: Path) -> str:
    openssl = shutil.which("openssl")
    if not openssl:
        return ""
    result = _run_blocking(
        [openssl, "x509", "-enddate", "-noout", "-in", str(cert_path)],
        paths()["home"],
    )
    if not result.success:
        return ""
    return result.output.replace("notAfter=", "").strip()


def _check_certificate(domain: str) -> CertificateInfo:
    safe_domain = _sanitize_hostname(domain)
    cert, key, _ = _certificate_paths(safe_domain)
    if not cert.exists() or not key.exists():
        return CertificateInfo(domain=safe_domain, certificatePath=str(cert), keyPath=str(key), isValid=False)

    openssl = shutil.which("openssl")
    if not openssl:
        return CertificateInfo(
            domain=safe_domain,
            certificatePath=str(cert),
            keyPath=str(key),
            expiresAt="",
            isValid=False,
        )

    validity = _run_blocking([openssl, "x509", "-checkend", "0", "-in", str(cert)], paths()["home"])
    return CertificateInfo(
        domain=safe_domain,
        certificatePath=str(cert),
        keyPath=str(key),
        expiresAt=_get_cert_expiration(cert),
        isValid=validity.success,
    )


def _install_root_ca() -> CommandResult:
    ensure = _ensure_root_ca()
    if not ensure.success:
        return ensure

    ca_cert, _ = _root_ca_paths()
    system = platform.system()

    if system == "Darwin":
        login_keychain = str(Path.home() / "Library" / "Keychains" / "login.keychain-db")
        # Prefer the user keychain to avoid admin prompts (sufficient for local dev trust).
        command = [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            login_keychain,
            str(ca_cert),
        ]
        result = _run_blocking(command, paths()["home"])
        if result.success:
            return result

        # Fallback: install into System keychain (requires admin).
        command = [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            "/Library/Keychains/System.keychain",
            str(ca_cert),
        ]
        result = _run_blocking(command, paths()["home"])
        if result.success:
            return result
        elevated = _run_with_macos_elevation(command, cwd=paths()["home"])
        if elevated.success:
            return elevated
        return CommandResult(
            success=False,
            output=result.output,
            error=elevated.error or result.error,
        )

    if system == "Windows":
        return _run_blocking(["certutil", "-addstore", "-f", "Root", str(ca_cert)], paths()["home"])

    return CommandResult(success=False, error="Automatic trust install is only implemented for macOS and Windows")


def _uninstall_root_ca() -> CommandResult:
    """Remove the DJAMP Root CA from macOS keychains (best-effort)."""
    ca_cert, ca_key = _root_ca_paths()
    if not ca_cert.exists() or not ca_key.exists():
        return CommandResult(success=True, output="Root CA files not found; nothing to uninstall")

    system = platform.system()
    if system != "Darwin":
        return CommandResult(success=False, error="Automatic trust removal is only implemented for macOS")

    security = shutil.which("security")
    if not security:
        return CommandResult(success=False, error="`security` CLI not found")

    common_name = "DJAMP PRO Root CA"
    login_keychain = str(Path.home() / "Library" / "Keychains" / "login.keychain-db")
    system_keychain = "/Library/Keychains/System.keychain"

    def _not_found(text: str) -> bool:
        t = (text or "").lower()
        return "could not be found" in t or "could not be found in the keychain" in t

    ok_login = True
    if Path(login_keychain).exists():
        res = _run_blocking([security, "delete-certificate", "-c", common_name, login_keychain], paths()["home"])
        ok_login = res.success or _not_found(f"{res.output}\n{res.error}")

    ok_system = True
    if Path(system_keychain).exists():
        res = _run_blocking([security, "delete-certificate", "-c", common_name, system_keychain], paths()["home"])
        if res.success or _not_found(f"{res.output}\n{res.error}"):
            ok_system = True
        else:
            elevated = _run_with_macos_elevation([security, "delete-certificate", "-c", common_name, system_keychain])
            ok_system = elevated.success or _not_found(f"{elevated.output}\n{elevated.error}")

    if ok_login and ok_system:
        return CommandResult(success=True, output="Root CA removed from keychains")
    return CommandResult(success=False, error="Failed to remove Root CA from one or more keychains")


def _check_root_ca_status() -> Dict[str, bool]:
    ca_cert, ca_key = _root_ca_paths()
    if not ca_cert.exists() or not ca_key.exists():
        return {"installed": False, "valid": False}

    openssl = shutil.which("openssl")
    valid = True
    if openssl:
        # `openssl x509 -checkend` returns 0 when the cert is NOT expired.
        valid = _run_blocking([openssl, "x509", "-checkend", "0", "-in", str(ca_cert)], paths()["home"]).success

    system = platform.system()
    if system == "Darwin":
        installed = _is_root_ca_trusted_macos(ca_cert)
        return {"installed": installed, "valid": valid}
    if system == "Windows":
        # MVP: we only auto-install on Windows; trust-status detection is best-effort.
        return {"installed": True, "valid": valid}
    return {"installed": True, "valid": valid}


def _normalize_hex(value: str) -> str:
    return "".join([ch for ch in (value or "").upper() if ch in "0123456789ABCDEF"])


def _openssl_sha1_fingerprint(cert_path: Path) -> str:
    openssl = shutil.which("openssl")
    if not openssl or not cert_path.exists():
        return ""
    result = _run_blocking([openssl, "x509", "-noout", "-fingerprint", "-sha1", "-in", str(cert_path)], paths()["home"])
    if not result.success:
        return ""
    # Example: "SHA1 Fingerprint=AA:BB:...".
    for line in (result.output or "").splitlines():
        if "Fingerprint=" in line:
            return _normalize_hex(line.split("Fingerprint=", 1)[1])
    return _normalize_hex(result.output)


def _security_keychain_sha1_hashes(common_name: str, keychain: str) -> List[str]:
    security = shutil.which("security")
    if not security:
        return []
    result = _run_blocking([security, "find-certificate", "-a", "-Z", "-c", common_name, keychain], paths()["home"])
    text = f"{result.output}\n{result.error}".strip()
    hashes: List[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if raw.startswith("SHA-1 hash:"):
            hashes.append(_normalize_hex(raw.split(":", 1)[1]))
    return hashes


def _is_root_ca_trusted_macos(ca_cert: Path) -> bool:
    """Return True when the DJAMP Root CA is present in a macOS keychain (trusted by the OS)."""
    sha1 = _openssl_sha1_fingerprint(ca_cert)
    if not sha1:
        return False

    keychains = [
        "/Library/Keychains/System.keychain",
        str(Path.home() / "Library" / "Keychains" / "login.keychain-db"),
    ]
    for keychain in keychains:
        if not Path(keychain).exists():
            continue
        hashes = _security_keychain_sha1_hashes("DJAMP PRO Root CA", keychain)
        if sha1 in hashes:
            return True
    return False


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

    return shutil.which("caddy")


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
            key_path = project.certificatePath.replace(".crt", ".key")
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
        if std_warning:
            if allow_privileged:
                if settings.standardPortsEnabled:
                    return CommandResult(
                        success=False,
                        output="Caddy reloaded",
                        error=(
                            f"Proxy is running but standard ports (80/443) are not enabled: {std_warning}\n"
                            f"You can still access projects on https://<domain>:{settings.proxyPort}"
                        ),
                    )
                return CommandResult(
                    success=False,
                    output="Caddy reloaded",
                    error=f"Proxy is running but standard ports (80/443) could not be disabled: {std_warning}",
                )
            return CommandResult(
                success=True,
                output=f"Caddy reloaded (note: {std_warning} Use https://<domain>:{settings.proxyPort})",
            )
        return CommandResult(success=True, output="Caddy reloaded")

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
        if std_warning:
            if allow_privileged:
                if settings.standardPortsEnabled:
                    return CommandResult(
                        success=False,
                        output="Caddy started",
                        error=(
                            f"Proxy is running but standard ports (80/443) are not enabled: {std_warning}\n"
                            f"You can still access projects on https://<domain>:{settings.proxyPort}"
                        ),
                    )
                return CommandResult(
                    success=False,
                    output="Caddy started",
                    error=f"Proxy is running but standard ports (80/443) could not be disabled: {std_warning}",
                )
            return CommandResult(
                success=True,
                output=f"Caddy started (note: {std_warning} Use https://<domain>:{settings.proxyPort})",
            )
        return CommandResult(success=True, output="Caddy started")

    return CommandResult(success=False, error="Caddy started but ports are not listening")


def _service_binary(name: str) -> Optional[str]:
    if name == "postgres":
        return shutil.which("postgres")
    if name == "mysql":
        return shutil.which("mysqld")
    if name == "redis":
        return shutil.which("redis-server")
    return None


async def _start_service(name: str) -> CommandResult:
    if name in SERVICE_PROCESSES and SERVICE_PROCESSES[name][0].returncode is None:
        return CommandResult(success=True, output=f"{name} already running")

    if name == "postgres" and _is_port_open(MANAGED_POSTGRES_PORT):
        return CommandResult(success=True, output="postgres already running")
    if name == "mysql" and _is_port_open(MANAGED_MYSQL_PORT):
        return CommandResult(success=True, output="mysql already running")
    if name == "redis" and _is_port_open(MANAGED_REDIS_PORT):
        return CommandResult(success=True, output="redis already running")

    binary = _service_binary(name)
    if not binary:
        return CommandResult(success=False, error=f"{name} binary not found in PATH")

    data_root = paths()["service_data"] / name
    data_root.mkdir(parents=True, exist_ok=True)
    log_handle = open(service_log_path(name), "a", encoding="utf-8")

    if name == "postgres":
        initdb = shutil.which("initdb")
        if not (data_root / "PG_VERSION").exists() and initdb:
            init_result = _run_blocking(
                [
                    initdb,
                    "-D",
                    str(data_root),
                    "--auth-local=trust",
                    "--auth-host=trust",
                ],
                data_root,
            )
            if not init_result.success:
                return init_result

        proc = await asyncio.create_subprocess_exec(
            binary,
            "-D",
            str(data_root),
            "-p",
            str(MANAGED_POSTGRES_PORT),
            "-h",
            "127.0.0.1",
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
        )
    elif name == "mysql":
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--datadir",
            str(data_root),
            f"--port={MANAGED_MYSQL_PORT}",
            "--bind-address=127.0.0.1",
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
        )
    else:
        conf = data_root / "redis.conf"
        conf.write_text(
            "\n".join(["bind 127.0.0.1", f"port {MANAGED_REDIS_PORT}", f"dir {data_root}"]),
            encoding="utf-8",
        )
        proc = await asyncio.create_subprocess_exec(
            binary,
            str(conf),
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
        )

    SERVICE_PROCESSES[name] = (proc, log_handle)
    return CommandResult(success=True, output=f"{name} started")


async def _stop_service(name: str) -> CommandResult:
    if name not in SERVICE_PROCESSES:
        return CommandResult(success=True, output=f"{name} already stopped")

    proc, handle = SERVICE_PROCESSES.pop(name)
    if proc.returncode is None:
        proc.terminate()
        await proc.wait()
    handle.close()
    return CommandResult(success=True, output=f"{name} stopped")


def _validate_simple_identifier(value: str, label: str) -> str:
    v = (value or "").strip()
    if not v:
        raise RuntimeError(f"Missing {label}")
    # Keep it simple/safe for SQL identifiers in MVP.
    if not all(ch.isalnum() or ch == "_" for ch in v):
        raise RuntimeError(f"Invalid {label}: only letters, numbers, and '_' are allowed")
    return v


def _ensure_postgres_db_and_role(project: Project) -> CommandResult:
    psql = shutil.which("psql")
    pg_isready = shutil.which("pg_isready")
    if not psql or not pg_isready:
        return CommandResult(success=False, error="Postgres tools (psql/pg_isready) not found in PATH")

    db_name = _validate_simple_identifier(project.database.name, "database name")
    db_user = _validate_simple_identifier(project.database.username, "database username")
    port = int(project.database.port or MANAGED_POSTGRES_PORT)

    # Wait briefly for Postgres to become ready.
    deadline = time.time() + 4.0
    while time.time() < deadline:
        ready = _run_blocking(
            [pg_isready, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres"],
            paths()["home"],
        )
        if ready.success:
            break
        time.sleep(0.2)

    role_exists = _run_blocking(
        [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_roles WHERE rolname = '{db_user}'"],
        paths()["home"],
    )
    if not role_exists.success:
        return role_exists
    password_sql = ""
    if project.database.password:
        pw = project.database.password.replace("'", "''")
        password_sql = f" PASSWORD '{pw}'"

    if role_exists.output.strip() != "1":
        role_create = _run_blocking(
            [
                psql,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'CREATE ROLE "{db_user}" LOGIN{password_sql};',
            ],
            paths()["home"],
        )
        if not role_create.success:
            return role_create
    elif password_sql:
        # Best-effort: align password with .env when provided.
        alter = _run_blocking(
            [
                psql,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'ALTER ROLE "{db_user}" WITH{password_sql};',
            ],
            paths()["home"],
        )
        if not alter.success:
            return alter

    db_exists = _run_blocking(
        [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"],
        paths()["home"],
    )
    if not db_exists.success:
        return db_exists
    if db_exists.output.strip() != "1":
        db_create = _run_blocking(
            [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{db_name}" OWNER "{db_user}";'],
            paths()["home"],
        )
        return db_create

    return CommandResult(success=True, output="Postgres database ready")


def _run_postgres_query_text(project: Project, query: str) -> CommandResult:
    psql = shutil.which("psql")
    if not psql:
        return CommandResult(success=False, error="psql is not installed or not in PATH")

    safe_query = (query or "").strip()
    if not safe_query:
        return CommandResult(success=False, error="Query is empty")
    if len(safe_query) > 20000:
        return CommandResult(success=False, error="Query is too long")

    db_name = (project.database.name or "postgres").strip() or "postgres"
    db_user = (project.database.username or "postgres").strip() or "postgres"
    db_password = project.database.password or ""
    db_port = int(project.database.port or MANAGED_POSTGRES_PORT)

    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password

    command = [
        psql,
        "-X",
        "-h",
        "127.0.0.1",
        "-p",
        str(db_port),
        "-U",
        db_user,
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-P",
        "pager=off",
        "-f",
        "-",
    ]

    return _run_blocking(command, Path(project.path), env=env, input_text=safe_query)


def _parse_psql_result(output: str) -> Optional[Dict[str, Any]]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    header_line = lines[0]
    if "|" not in header_line:
        return None

    headers = [part.strip() for part in header_line.split("|")]
    if not any(headers):
        return None

    rows: List[List[str]] = []
    row_count: Optional[int] = None

    for line in lines[2:]:
        stripped = line.strip()
        if stripped.startswith("(") and "row" in stripped:
            m = re.search(r"\((\d+)\s+rows?\)", stripped)
            if m:
                row_count = int(m.group(1))
            break

        if "|" not in line:
            continue

        cells = [part.strip() for part in line.split("|")]
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        elif len(cells) > len(headers):
            cells = cells[: len(headers) - 1] + ["|".join(cells[len(headers) - 1 :]).strip()]
        rows.append(cells)

    if row_count is None:
        row_count = len(rows)

    return {
        "headers": headers,
        "rows": rows,
        "row_count": row_count,
    }


def _render_psql_result_table(output: str) -> Tuple[str, int]:
    parsed = _parse_psql_result(output)
    if not parsed:
        return "", 0

    headers: List[str] = parsed["headers"]
    rows: List[List[str]] = parsed["rows"]
    row_count = int(parsed["row_count"])

    head = "<th class='col-actions'>Actions</th>" + "".join(f"<th>{html.escape(col)}</th>" for col in headers)

    if rows:
        body = ""
        for idx, row in enumerate(rows, start=1):
            row_actions = (
                "<td class='row-actions'>"
                "<a href='#'>Edit</a>"
                "<a href='#'>Copy</a>"
                "<a href='#'>Delete</a>"
                "</td>"
            )
            cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
            body += f"<tr><td class='row-index'>{idx}</td>{row_actions}{cells}</tr>"
    else:
        body = (
            "<tr><td class='row-index'>-</td><td class='row-actions empty'>No row actions</td>"
            + f"<td class='empty-cell' colspan='{max(len(headers), 1)}'>No rows returned.</td></tr>"
        )

    shown_from = 0
    shown_to = max(len(rows) - 1, 0) if row_count > 0 else 0
    summary = (
        "<div class='query-ok'>"
        + f"Showing rows {shown_from} - {shown_to} ({row_count} total)."
        + "</div>"
    )

    tools = (
        "<div class='result-tools'>"
        "<span class='tool-chip'>Rows: 25</span>"
        "<span class='tool-chip'>Filter: table</span>"
        "<span class='tool-chip'>Sort: none</span>"
        "</div>"
    )

    table_html = (
        "<div class='result-table-wrap'><table class='result-table'><thead><tr>"
        + "<th class='row-index-head'>#</th>"
        + head
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )

    return summary + tools + table_html, row_count


def _render_postgres_admin_html(
    project: Project,
    tables_output: str,
    query: str = "",
    query_output: str = "",
    query_error: str = "",
) -> str:
    project_name = html.escape(project.name)
    db_name = html.escape((project.database.name or "postgres").strip() or "postgres")
    db_user = html.escape((project.database.username or "postgres").strip() or "postgres")
    db_port = int(project.database.port or MANAGED_POSTGRES_PORT)
    safe_query = html.escape(query)
    safe_tables = html.escape((tables_output or "No tables found").strip() or "No tables found")

    table_names: List[str] = []
    seen: set[str] = set()
    for raw_line in (tables_output or "").splitlines():
        line = raw_line.strip()
        if not line or line.lower() == "table_name":
            continue
        if set(line) <= {"-", "+", "|", " "}:
            continue
        if line.startswith("(") and line.endswith("rows)"):
            continue

        candidate = line
        if "|" in candidate:
            candidate = candidate.split("|", 1)[0].strip()
        if not candidate or "." not in candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        table_names.append(candidate)

    if table_names:
        table_links = "".join(
            (
                "<a class='table-link' href='?query="
                + quote_plus(f"SELECT * FROM {table} LIMIT 100;")
                + "'>"
                + html.escape(table)
                + "</a>"
            )
            for table in table_names
        )
    else:
        table_links = "<div class='empty-note'>No tables detected yet.</div>"

    result_block = "<div class='result-empty'>Run a SQL query to preview results.</div>"
    if query.strip():
        if query_error:
            result_block = (
                "<div class='result-card error'><div class='result-title'>Query Error</div><pre class='result-raw'>"
                + html.escape(query_error.strip() or "Query failed")
                + "</pre></div>"
            )
        else:
            output_text = (query_output or "(No output)").strip() or "(No output)"
            parsed_table, _row_count = _render_psql_result_table(output_text)
            if parsed_table:
                result_block = (
                    "<div class='result-card'><div class='result-title'>Query Result</div>"
                    + parsed_table
                    + "<details class='raw-toggle'><summary>Raw output</summary><pre class='result-raw'>"
                    + html.escape(output_text)
                    + "</pre></details></div>"
                )
            else:
                result_block = (
                    "<div class='result-card'><div class='result-title'>Query Result</div><pre class='result-raw'>"
                    + html.escape(output_text)
                    + "</pre></div>"
                )

    now_query = quote_plus("SELECT NOW();")
    tables_query = quote_plus(
        "SELECT table_schema || '.' || table_name AS table_name "
        "FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY 1;"
    )

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>DJAMP DB Admin - {project_name}</title>
  <style>
    :root {{
      --bg: #eceff3;
      --panel: #ffffff;
      --line: #ccd4df;
      --line-soft: #e5e9f0;
      --text: #283341;
      --muted: #6b7584;
      --brand: #3d6ea7;
      --brand-2: #2f557f;
      --accent: #f2f5f9;
      --danger-bg: #fff0f0;
      --danger-line: #efb0b0;
      --danger-text: #7d2525;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      min-height: 100vh;
    }}

    .topbar {{
      background: linear-gradient(180deg, #f9fafc 0%, #edf1f6 100%);
      border-bottom: 1px solid var(--line);
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 20px;
      font-weight: 700;
      color: #2f3c4d;
      letter-spacing: 0.2px;
    }}

    .brand-badge {{
      width: 28px;
      height: 28px;
      border-radius: 7px;
      background: linear-gradient(145deg, #5aa6ff 0%, #2d4eb3 100%);
      color: #fff;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.25);
    }}

    .meta {{
      font-size: 13px;
      color: var(--muted);
      text-align: right;
    }}

    .tabs {{
      display: flex;
      gap: 6px;
      padding: 10px 18px 0;
      background: #f4f6fa;
      border-bottom: 1px solid var(--line);
    }}

    .tab {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line-soft);
      border-bottom-color: var(--line);
      background: #f7f9fc;
      color: #54657b;
      border-radius: 8px 8px 0 0;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
    }}

    .tab.active {{
      background: #fff;
      color: var(--brand-2);
      border-color: var(--line);
      border-bottom-color: #fff;
    }}

    .layout {{
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 14px;
      padding: 14px;
    }}

    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 1px 0 rgba(0,0,0,.02);
    }}

    .panel-head {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line-soft);
      background: linear-gradient(180deg, #f8fafd 0%, #eef2f8 100%);
      font-size: 14px;
      font-weight: 700;
      color: #334359;
    }}

    .panel-body {{ padding: 12px 14px; }}

    .kv {{
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 6px 8px;
      font-size: 13px;
      margin-bottom: 12px;
    }}
    .kv .k {{ color: var(--muted); }}
    .kv .v {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: 12px; color: #3d4c5f; }}

    .table-list {{
      max-height: calc(100vh - 270px);
      overflow: auto;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fbfcfe;
    }}

    .table-link {{
      display: block;
      padding: 8px 10px;
      color: #3f5064;
      text-decoration: none;
      border-bottom: 1px solid #eef2f7;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }}

    .table-link:hover {{ background: #edf3fb; color: #214c80; }}
    .table-link:last-child {{ border-bottom: 0; }}

    .empty-note {{ padding: 10px; color: #7a8798; font-size: 12px; }}

    .action-row {{ display: flex; gap: 8px; margin-bottom: 10px; }}
    .chip {{
      text-decoration: none;
      border: 1px solid var(--line);
      background: var(--accent);
      color: #425469;
      border-radius: 7px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
    .chip:hover {{ background: #e6edf7; }}

    textarea {{
      width: 100%;
      min-height: 180px;
      resize: vertical;
      border: 1px solid #c5ceda;
      border-radius: 8px;
      padding: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      color: #243345;
      background: #ffffff;
    }}

    .btn {{
      margin-top: 10px;
      border: 1px solid #2a5d98;
      background: linear-gradient(180deg, #4f81be 0%, #2f5d95 100%);
      color: #fff;
      border-radius: 7px;
      padding: 9px 13px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }}
    .btn:hover {{ filter: brightness(1.04); }}

    .result-card {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 10px;
    }}

    .result-card.error {{
      background: var(--danger-bg);
      border-color: var(--danger-line);
      color: var(--danger-text);
    }}

    .result-title {{ font-size: 13px; font-weight: 700; margin-bottom: 8px; color: #3c4d62; }}
    .result-card.error .result-title {{ color: var(--danger-text); }}

    .result-empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 12px;
      color: #78879b;
      background: #fafcff;
      font-size: 13px;
    }}

    .query-ok {{
      border: 1px solid #c6d67a;
      background: linear-gradient(180deg, #eef5bf 0%, #d8e89a 100%);
      color: #4a5d1f;
      border-radius: 7px;
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 10px;
    }}

    .result-tools {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
    .tool-chip {{
      border: 1px solid var(--line-soft);
      background: #f5f8fc;
      color: #4d6078;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 11px;
      font-weight: 600;
    }}

    .result-table-wrap {{ overflow: auto; border: 1px solid var(--line-soft); border-radius: 8px; background: #fff; }}
    .result-table {{ border-collapse: collapse; width: 100%; min-width: 640px; font-size: 12px; }}
    .result-table th {{ background: #eef3f9; color: #32465d; text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line-soft); border-right: 1px solid #e5ebf3; white-space: nowrap; }}
    .result-table td {{ padding: 8px 10px; border-bottom: 1px solid #eef2f7; border-right: 1px solid #f0f3f8; color: #25374c; vertical-align: top; }}
    .result-table tr:nth-child(even) td {{ background: #fbfdff; }}
    .result-table th:last-child, .result-table td:last-child {{ border-right: 0; }}

    .row-index-head, .row-index {{ width: 40px; text-align: center; color: #6e7d90; background: #f7f9fc; }}
    .row-index {{ font-weight: 600; }}
    .col-actions {{ min-width: 160px; }}
    .row-actions {{ white-space: nowrap; min-width: 160px; }}
    .row-actions a {{ color: #2e6aa9; text-decoration: none; margin-right: 10px; font-size: 11px; font-weight: 600; }}
    .row-actions a:hover {{ text-decoration: underline; }}
    .row-actions.empty {{ color: #8695a8; font-size: 11px; }}
    .empty-cell {{ color: #7a8798; font-style: italic; }}

    .raw-toggle {{ margin-top: 10px; }}
    .raw-toggle > summary {{ cursor: pointer; color: #516378; font-size: 12px; font-weight: 600; }}

    .result-raw {{
      margin: 8px 0 0;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fff;
      color: #2a384a;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      max-height: 330px;
      overflow: auto;
    }}

    .footer-raw {{
      margin-top: 12px;
      color: #7f8ca0;
      font-size: 11px;
      border-top: 1px solid var(--line-soft);
      padding-top: 10px;
    }}

    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .table-list {{ max-height: 240px; }}
      .meta {{ text-align: left; }}
      .topbar {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <header class='topbar'>
    <div class='brand'>
      <span class='brand-badge'>DJ</span>
      <span>DJAMP Database Admin</span>
    </div>
    <div class='meta'>
      <div><strong>Project:</strong> {project_name}</div>
      <div><strong>PostgreSQL:</strong> 127.0.0.1:{db_port} &nbsp;|&nbsp; <strong>DB:</strong> {db_name} &nbsp;|&nbsp; <strong>User:</strong> {db_user}</div>
    </div>
  </header>

  <nav class='tabs'>
    <a class='tab active' href='?'>Databases</a>
    <a class='tab' href='?query={now_query}'>SQL</a>
    <a class='tab' href='?query={tables_query}'>Structure</a>
    <a class='tab' href='?'>Status</a>
    <a class='tab' href='?'>Settings</a>
  </nav>

  <div class='layout'>
    <aside class='panel'>
      <div class='panel-head'>Database Overview</div>
      <div class='panel-body'>
        <div class='kv'>
          <div class='k'>Engine</div><div class='v'>PostgreSQL</div>
          <div class='k'>Host</div><div class='v'>127.0.0.1:{db_port}</div>
          <div class='k'>Database</div><div class='v'>{db_name}</div>
          <div class='k'>User</div><div class='v'>{db_user}</div>
        </div>
        <div class='panel-head' style='margin:0 -14px 10px; border-left:0; border-right:0; border-radius:0;'>Tables</div>
        <div class='table-list'>
          {table_links}
        </div>
      </div>
    </aside>

    <main>
      <section class='panel'>
        <div class='panel-head'>Run SQL</div>
        <div class='panel-body'>
          <div class='action-row'>
            <a class='chip' href='?query={now_query}'>SELECT NOW()</a>
            <a class='chip' href='?query={tables_query}'>List Tables</a>
          </div>
          <form method='get'>
            <textarea name='query' placeholder='SELECT * FROM public.auth_user LIMIT 20;'>{safe_query}</textarea>
            <div><button class='btn' type='submit'>Run Query</button></div>
          </form>
        </div>
      </section>

      <section class='panel' style='margin-top: 14px;'>
        <div class='panel-head'>Results</div>
        <div class='panel-body'>
          {result_block}
          <details class='raw-toggle'>
            <summary>Raw table listing output</summary>
            <pre class='result-raw'>{safe_tables}</pre>
          </details>
          <div class='footer-raw'>This UI is PostgreSQL-backed and intentionally local-only for development.</div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>"""


async def _refresh_runtime_states(registry: Registry) -> Registry:
    changed = False
    projects = []
    for project in registry.projects:
        normalized = _normalize_project_paths(project)
        if normalized.model_dump() != project.model_dump():
            project = normalized
            changed = True

        tracked = PROJECT_PROCESSES.get(project.id)
        tracked_alive = False
        if tracked:
            proc, handle = tracked
            if proc.returncode is None:
                tracked_alive = True
            else:
                # Process exited; forget it so status can be derived from the port.
                PROJECT_PROCESSES.pop(project.id, None)
                try:
                    handle.close()
                except Exception:
                    pass

        port_open = _is_port_open(project.port)
        if port_open:
            expected_status = "running"
        elif tracked_alive:
            # A process exists but the server is not accepting connections.
            expected_status = "error"
        else:
            expected_status = "stopped"

        if project.status != expected_status:
            project.status = expected_status
            changed = True
        projects.append(project)

    if changed:
        registry.projects = projects
        save_registry_sync(registry)
    return registry


def _find_settings_modules(project_root: Path) -> List[str]:
    settings = []
    for candidate in project_root.rglob("settings.py"):
        rel = candidate.relative_to(project_root)
        parts = list(rel.parts)
        if parts[-1] == "settings.py":
            parts[-1] = "settings"
        settings.append(".".join(parts))
    return sorted(set(settings))


def detect_django(path: str) -> DetectionResult:
    project_root = Path(path).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        return DetectionResult(found=False)

    manage_candidates = list(project_root.rglob("manage.py"))
    if not manage_candidates:
        return DetectionResult(found=False)

    manage_py = manage_candidates[0]
    settings_modules = _find_settings_modules(project_root)
    return DetectionResult(found=True, managePyPath=str(manage_py), settingsModules=settings_modules)


app = FastAPI(
    title="DJAMP PRO Controller",
    description="Controller service for DJAMP PRO desktop application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()
    _ = load_registry_sync()


@app.on_event("shutdown")
async def shutdown() -> None:
    for project_id in list(PROJECT_PROCESSES.keys()):
        proc, handle = PROJECT_PROCESSES.pop(project_id)
        if proc.returncode is None:
            await _terminate_process(proc)
        try:
            handle.close()
        except Exception:
            pass

    for service in list(SERVICE_PROCESSES.keys()):
        proc, handle = SERVICE_PROCESSES.pop(service)
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
        handle.close()

    # Best-effort stop of the reverse proxy (do not prompt for elevation on shutdown).
    try:
        caddy = _caddy_binary()
        if caddy:
            stop_env = os.environ.copy()
            _prepend_path_env(stop_env, Path(caddy).parent)
            _ = _run_blocking([caddy, "stop"], paths()["home"], stop_env)
    except Exception:
        pass

    # MAMP-style cleanup: release standard ports and optionally restore /etc/hosts.
    try:
        if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
            # Always release ports 80/443 on quit to avoid blocking other local servers.
            _ = _helper_disable_standard_ports()
            if load_registry_sync().settings.restoreOnQuit:
                _ = _helper_hosts_clear()
    except Exception:
        pass


@app.get("/")
async def root() -> Dict[str, str]:
    return {"name": "DJAMP PRO Controller", "status": "running"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/projects", response_model=List[Project])
async def get_projects() -> List[Project]:
    registry = await read_registry()
    refreshed = await _refresh_runtime_states(registry)

    projects: List[Project] = []
    for project in refreshed.projects:
        candidate = project.model_copy(deep=True)
        try:
            candidate = _hydrate_project_db_from_dotenv(candidate)
        except Exception:
            pass
        try:
            candidate.environmentVars = _display_environment_vars(candidate)
        except Exception:
            candidate.environmentVars = {}
        projects.append(candidate)

    return projects


@app.post("/api/projects", response_model=Project)
async def add_project(payload: AddProjectPayload) -> Project:
    incoming = payload.project
    incoming.setdefault("id", str(uuid.uuid4()))
    incoming.setdefault("createdAt", utc_now())
    incoming.setdefault("status", "stopped")

    project = Project.model_validate(incoming)
    project.id = _require_project_id(project.id)
    try:
        project.domain = _sanitize_hostname(project.domain)
        project.aliases = [_sanitize_hostname(a) for a in project.aliases]
        _enforce_domain_policy(project, load_registry_sync().settings)
        project.allowedHosts = sorted(set(_project_domains(project) + ["localhost", "127.0.0.1"]))
        project.path = str(_sanitize_user_project_path(project.path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Make DB credentials consistent with the project .env (common in Django projects).
    try:
        project = _hydrate_project_db_from_dotenv(project)
    except Exception:
        pass
    project = _normalize_project_paths(project)

    def mutator(registry: Registry) -> Registry:
        if any(existing.id == project.id for existing in registry.projects):
            raise HTTPException(status_code=409, detail="Project ID already exists")
        if any(existing.path == project.path for existing in registry.projects):
            raise HTTPException(status_code=409, detail="Project path already registered")
        registry.projects.append(project)
        return registry

    await mutate_registry(mutator)

    # Keep add flow responsive. On macOS, avoid privileged prompts during Add when helper is not installed.
    try:
        updated_registry = await read_registry()
        if platform.system() == "Darwin" and not MACOS_HELPER_SOCKET.exists():
            return project
        _ = await _sync_domains_for_registry(updated_registry)
    except Exception:
        pass
    return project


@app.put("/api/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, project: Project) -> Project:
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="Project ID mismatch")

    def mutator(registry: Registry) -> Registry:
        for idx, existing in enumerate(registry.projects):
            if existing.id == project_id:
                registry.projects[idx] = project
                return registry
        raise HTTPException(status_code=404, detail="Project not found")

    await mutate_registry(mutator)
    return project


@app.patch("/api/projects/{project_id}", response_model=Project)
async def patch_project(project_id: str, payload: Dict[str, Any]) -> Project:
    updated: Optional[Project] = None

    def mutator(registry: Registry) -> Registry:
        nonlocal updated
        for idx, existing in enumerate(registry.projects):
            if existing.id == project_id:
                merged = existing.model_dump()
                merged.update(payload)
                candidate = Project.model_validate(merged)
                candidate = _normalize_project_paths(candidate)
                try:
                    candidate.domain = _sanitize_hostname(candidate.domain)
                    candidate.aliases = [_sanitize_hostname(a) for a in candidate.aliases]
                    _enforce_domain_policy(candidate, registry.settings)
                    candidate.allowedHosts = sorted(set(_project_domains(candidate) + ["localhost", "127.0.0.1"]))
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                try:
                    candidate = _hydrate_project_db_from_dotenv(candidate)
                except Exception:
                    pass
                updated = candidate
                registry.projects[idx] = candidate
                return registry
        raise HTTPException(status_code=404, detail="Project not found")

    await mutate_registry(mutator)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    # Best-effort: keep /etc/hosts in sync when domains/aliases are edited.
    try:
        refreshed = load_registry_sync()
        asyncio.create_task(_sync_domains_for_registry(refreshed))
    except Exception:
        pass
    return updated


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    project_id = project.id

    if project_id in PROJECT_PROCESSES:
        proc, handle = PROJECT_PROCESSES.pop(project_id)
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
        handle.close()

    _kill_processes_on_port(project.port)

    def mutator(registry: Registry) -> Registry:
        registry.projects = [p for p in registry.projects if p.id != project_id]
        return registry

    await mutate_registry(mutator)

    # Best-effort cleanup: update hosts + proxy config after removing a project.
    try:
        updated = load_registry_sync()
        asyncio.create_task(_sync_domains_for_registry(updated))
        asyncio.create_task(_reload_caddy(updated.projects, allow_privileged=False))
    except Exception:
        pass

    return {"message": "Project deleted"}


def _get_project_or_404(registry: Registry, project_id: str) -> Project:
    safe_project_id = _require_project_id(project_id)
    for project in registry.projects:
        if _canonical_project_id(project.id) == safe_project_id:
            return project
    raise HTTPException(status_code=404, detail="Project not found")


async def _update_project(registry: Registry, updated_project: Project) -> None:
    def mutator(current: Registry) -> Registry:
        for idx, existing in enumerate(current.projects):
            if existing.id == updated_project.id:
                current.projects[idx] = updated_project
                return current
        raise HTTPException(status_code=404, detail="Project not found")

    await mutate_registry(mutator)


def _sanitize_error_for_client(message: str) -> str:
    if not message:
        return ""
    lines = [line.strip() for line in message.replace("\r", "\n").splitlines() if line.strip()]
    sensitive_markers = ("traceback", 'file "', " line ", "stack")
    filtered = [line for line in lines if not any(marker in line.lower() for marker in sensitive_markers)]
    if not filtered:
        return "Operation failed. Check DJAMP PRO logs for details."
    return "\n".join(filtered[:5])[:1200]


def _public_command_result(result: CommandResult) -> Dict[str, Any]:
    if result.success:
        return {
            "success": True,
            "output": (result.output or "")[:1200],
            "error": "",
        }
    return {
        "success": False,
        "output": "",
        "error": _sanitize_error_for_client(result.error or result.output),
    }


def _sanitize_user_project_path(raw_path: str) -> Path:
    raw = (raw_path or "").strip()
    if not raw or "\x00" in raw:
        raise HTTPException(status_code=400, detail="Invalid project path")

    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        raise HTTPException(status_code=400, detail="Project path must be an absolute path")

    resolved = os.path.realpath(expanded)
    home_root = os.path.realpath(str(Path.home()))
    try:
        if os.path.commonpath([resolved, home_root]) != home_root:
            raise HTTPException(status_code=400, detail="Project path must be inside your home directory")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project path") from exc

    project = Path(resolved)
    if not project.exists() or not project.is_dir():
        raise HTTPException(status_code=400, detail="Project directory does not exist")

    restricted_roots = [Path("/System"), Path("/Library"), Path("/bin"), Path("/sbin"), Path("/usr")]
    if any(_is_relative_to(project, root) for root in restricted_roots):
        raise HTTPException(status_code=400, detail="Project path points to a restricted system directory")

    return project


@app.post("/api/projects/{project_id}/start")
async def start_project(project_id: str) -> Dict[str, Any]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    project_id = project.id

    # Ensure paths are absolute for reliable process spawning.
    try:
        normalized = _normalize_project_paths(project)
        if normalized.model_dump() != project.model_dump():
            project = normalized
            await _update_project(registry, project)
    except Exception:
        pass

    # Safety: ensure domains are safe/normalized before writing certs/configs/hosts.
    try:
        sanitized_domain = _sanitize_hostname(project.domain)
        sanitized_aliases = [_sanitize_hostname(a) for a in project.aliases]
        project.domain = sanitized_domain
        project.aliases = sanitized_aliases
        _enforce_domain_policy(project, registry.settings)
        project.allowedHosts = sorted(set(_project_domains(project) + ["localhost", "127.0.0.1"]))
        await _update_project(registry, project)
    except Exception as exc:
        project.status = "error"
        await _update_project(registry, project)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    manage_py = _find_manage_py(project)

    tracked = PROJECT_PROCESSES.get(project_id)
    if tracked and tracked[0].returncode is None:
        # If the port is actually open, treat as running; otherwise clean up and try again.
        if _is_port_open(project.port):
            return {"message": "Project already running"}

        proc, handle = PROJECT_PROCESSES.pop(project_id)
        await _terminate_process(proc)
        try:
            handle.close()
        except Exception:
            pass

    if _is_port_open(project.port):
        return {
            "message": (
                f"Port {project.port} is already in use. Stop the conflicting process or change project port."
            )
        }

    # Clean up any previously orphaned processes for this project/port.
    _kill_processes_on_port(project.port)
    _kill_stray_project_processes(manage_py, project.port)

    project.status = "starting"
    await _update_project(registry, project)

    # Keep DB credentials aligned with the project's .env to match typical Django workflows.
    try:
        hydrated = _hydrate_project_db_from_dotenv(project)
        if hydrated.model_dump() != project.model_dump():
            project = hydrated
            await _update_project(registry, project)
    except Exception:
        pass

    # Ensure managed services for the project are running.
    if project.database.type == "postgres":
        project.database.port = MANAGED_POSTGRES_PORT
        # Source DB name/user/password from .env when present, but always point host/port to the managed service.
        db_name = (project.database.name or "").strip()
        db_user = (project.database.username or "").strip()
        db_password = project.database.password or ""
        if not db_name or not db_user:
            # Fall back to simple defaults when the project .env is incomplete.
            safe = "".join(ch for ch in (project.name or "djamp").lower() if ch.isalnum() or ch == "_").strip("_")
            safe = safe or "djamp"
            db_name = db_name or f"{safe}_db"
            db_user = db_user or f"{safe}_user"
            project.database.name = db_name
            project.database.username = db_user

        # Keep env vars aligned with managed service defaults.
        project.environmentVars["DB_NAME"] = db_name
        project.environmentVars["DB_USER"] = db_user
        project.environmentVars["DB_PASSWORD"] = db_password
        project.environmentVars["DB_HOST"] = "127.0.0.1"
        project.environmentVars["DB_PORT"] = str(MANAGED_POSTGRES_PORT)
        project.environmentVars["DATABASE_URL"] = (
            f"postgres://{db_user}:{db_password}@127.0.0.1:{MANAGED_POSTGRES_PORT}/{db_name}"
        )

        # Ensure the project .env points to local managed DB too (many projects force override=True).
        env_sync = _sync_managed_env_block(
            project,
            {
                "DB_HOST": "127.0.0.1",
                "DB_PORT": str(MANAGED_POSTGRES_PORT),
                "DB_NAME": db_name,
                "DB_USER": db_user,
                "DB_PASSWORD": db_password,
                "DATABASE_URL": project.environmentVars["DATABASE_URL"],
            },
        )
        if not env_sync.success:
            # Do not fail start; surface this via logs/warnings and keep going.
            pass

        await _update_project(registry, project)
        db_start = await _start_service("postgres")
        if not db_start.success:
            project.status = "error"
            await _update_project(registry, project)
            raise HTTPException(status_code=500, detail=db_start.error or "Failed to start Postgres service")
        db_ready = await asyncio.to_thread(_ensure_postgres_db_and_role, project)
        if not db_ready.success:
            project.status = "error"
            await _update_project(registry, project)
            raise HTTPException(status_code=500, detail=db_ready.error or "Failed to prepare Postgres database")

    command, env = await asyncio.to_thread(
        _build_manage_command,
        project,
        manage_py,
        ["runserver", f"127.0.0.1:{project.port}"],
    )
    env = _apply_djamp_project_env(project, env)

    log_path = project_log_path(project.id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = open(log_path, "a", encoding="utf-8")
    try:
        log_handle.write(f"\n# DJAMP PRO start {utc_now()}\n# {shlex.join(command)}\n")
        log_handle.flush()
    except Exception:
        pass

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(Path(project.path)),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=log_handle,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )

    PROJECT_PROCESSES[project_id] = (process, log_handle)

    started = False
    deadline = time.time() + 12.0
    while time.time() < deadline:
        if process.returncode is not None:
            break
        if _is_port_open(project.port):
            started = True
            break
        await asyncio.sleep(0.25)

    if not started:
        PROJECT_PROCESSES.pop(project_id, None)
        await _terminate_process(process)
        try:
            log_handle.close()
        except Exception:
            pass
        project.status = "error"
        await _update_project(registry, project)
        tail = _tail_file(log_path, 2000)
        raise HTTPException(
            status_code=500,
            detail=f"Project failed to start. Recent logs:\n{tail}",
        )

    project.status = "running"

    cert_warning: Optional[str] = None
    if project.httpsEnabled:
        try:
            ca_status = _check_root_ca_status()
            if not ca_status.get("installed"):
                # Do not auto-install trust on start; it triggers elevation prompts unexpectedly.
                cert_warning = (
                    "DJAMP PRO Root CA is not trusted yet. "
                    "Go to Settings -> Install Root CA to enable trusted HTTPS."
                )

            alt_domains = [project.domain, *project.aliases]
            www_alias = f"www.{project.domain}".strip()
            if project.domain and not project.domain.startswith("www.") and www_alias not in alt_domains:
                alt_domains.append(www_alias)
                if www_alias and www_alias not in project.allowedHosts:
                    project.allowedHosts.append(www_alias)
            cert_info = await asyncio.to_thread(_generate_certificate, project.domain, alt_domains)
            project.certificatePath = cert_info.certificatePath
        except Exception:
            cert_warning = "Certificate setup failed. Check DJAMP PRO logs for details."

    await _update_project(registry, project)

    # Best effort domain/proxy setup. Project can still run even if this fails.
    hosts_result = await _sync_domains_for_registry(load_registry_sync())
    caddy_result = await _reload_caddy(load_registry_sync().projects, allow_privileged=False)

    return {
        "message": "Project started",
        "hosts": _public_command_result(hosts_result),
        "proxy": _public_command_result(caddy_result),
        "certificateWarning": cert_warning or "",
    }


@app.post("/api/projects/{project_id}/stop")
async def stop_project(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    project_id = project.id

    if project_id in PROJECT_PROCESSES:
        proc, handle = PROJECT_PROCESSES.pop(project_id)
        if proc.returncode is None:
            await _terminate_process(proc)
        try:
            handle.close()
        except Exception:
            pass

    _kill_processes_on_port(project.port)
    try:
        manage_py = _find_manage_py(project)
        _kill_stray_project_processes(manage_py, project.port)
    except Exception:
        pass

    project.status = "stopped"
    await _update_project(registry, project)
    return {"message": "Project stopped"}


@app.post("/api/projects/{project_id}/restart")
async def restart_project(project_id: str) -> Dict[str, str]:
    await stop_project(project_id)
    await start_project(project_id)
    return {"message": "Project restarted"}


async def _run_project_task(project_id: str, django_args: List[str], extra_env: Optional[Dict[str, str]] = None) -> CommandResult:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    project_id = project.id
    manage_py = _find_manage_py(project)

    def runner() -> CommandResult:
        command, env = _build_manage_command(project, manage_py, django_args)
        env = _apply_djamp_project_env(project, env)
        if extra_env:
            env = {**env, **extra_env}

        result = _run_blocking(command, Path(project.path), env)

        log_path = project_log_path(project_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, "a", encoding="utf-8") as log_handle:
                log_handle.write(f"\n# DJAMP PRO task {utc_now()}\n# {shlex.join(command)}\n")
                if result.output:
                    log_handle.write(result.output.rstrip() + "\n")
                if result.error:
                    log_handle.write(f"ERROR: {result.error}\n")
        except Exception:
            pass

        return result

    return await asyncio.to_thread(runner)


@app.post("/api/projects/{project_id}/migrate", response_model=CommandResult)
async def migrate_project(project_id: str) -> CommandResult:
    return await _run_project_task(project_id, ["migrate"])


@app.post("/api/projects/{project_id}/collectstatic", response_model=CommandResult)
async def collect_static(project_id: str) -> CommandResult:
    return await _run_project_task(project_id, ["collectstatic", "--noinput"])


@app.post("/api/projects/{project_id}/createsuperuser", response_model=CommandResult)
async def create_superuser(project_id: str, payload: CreateSuperuserPayload) -> CommandResult:
    env = {
        "DJANGO_SUPERUSER_USERNAME": payload.username,
        "DJANGO_SUPERUSER_EMAIL": payload.email,
        "DJANGO_SUPERUSER_PASSWORD": os.getenv("DJAMP_DEFAULT_SUPERUSER_PASSWORD", "djamp-pro-admin"),
    }
    return await _run_project_task(project_id, ["createsuperuser", "--noinput"], env)


@app.post("/api/projects/{project_id}/test", response_model=CommandResult)
async def run_tests(project_id: str) -> CommandResult:
    return await _run_project_task(project_id, ["test"])


@app.get("/api/settings", response_model=AppSettings)
async def get_settings() -> AppSettings:
    registry = await read_registry()
    return registry.settings


@app.patch("/api/settings", response_model=AppSettings)
async def patch_settings(payload: Dict[str, Any]) -> AppSettings:
    updated: Optional[AppSettings] = None

    def mutator(registry: Registry) -> Registry:
        nonlocal updated
        merged = registry.settings.model_dump()
        merged.update(payload)
        updated = AppSettings.model_validate(merged)
        registry.settings = updated
        return registry

    await mutate_registry(mutator)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    return updated


@app.post("/api/domains/sync", response_model=CommandResult)
async def sync_domains() -> CommandResult:
    registry = await read_registry()
    return await _sync_domains_for_registry(registry)


@app.post("/api/domains/add")
async def add_domain(payload: DomainPayload) -> Dict[str, Any]:
    registry = await read_registry()
    result = await _sync_domains_for_registry(registry)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message": "Domain mappings updated", "domain": payload.domain}


@app.post("/api/domains/remove")
async def remove_domain(payload: DomainPayload) -> Dict[str, Any]:
    registry = await read_registry()
    result = await _sync_domains_for_registry(registry)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message": "Domain mapping removed", "domain": payload.domain}


@app.post("/api/domains/clear", response_model=CommandResult)
async def clear_domains() -> CommandResult:
    return await _clear_hosts_block()


@app.post("/api/proxy/reload", response_model=CommandResult)
async def reload_proxy() -> CommandResult:
    registry = await read_registry()
    return await _reload_caddy(registry.projects, allow_privileged=True)


@app.get("/api/proxy/status", response_model=ProxyStatus)
async def proxy_status() -> ProxyStatus:
    registry = await read_registry()
    settings = registry.settings
    return ProxyStatus(
        proxyHttpPort=settings.proxyHttpPort,
        proxyPort=settings.proxyPort,
        standardPortsEnabled=settings.standardPortsEnabled,
        standardHttpActive=_is_port_open(80),
        standardHttpsActive=_is_port_open(443),
        proxyHttpActive=_is_port_open(settings.proxyHttpPort),
        proxyHttpsActive=_is_port_open(settings.proxyPort),
    )


@app.get("/api/helper/status")
async def helper_status() -> Dict[str, Any]:
    installed = _macos_helper_installed()
    running = False
    standard_http = False
    standard_https = False
    if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
        result, data = await asyncio.to_thread(_helper_request, {"cmd": "status"})
        if result.success:
            running = True
            if data:
                standard_http = bool(data.get("standardHttpActive"))
                standard_https = bool(data.get("standardHttpsActive"))

    return {
        "installed": installed,
        "running": running,
        "socketPath": str(MACOS_HELPER_SOCKET),
        "label": MACOS_HELPER_LABEL,
        "standardHttpActive": standard_http,
        "standardHttpsActive": standard_https,
    }


@app.post("/api/helper/install", response_model=CommandResult)
async def install_helper() -> CommandResult:
    result = await asyncio.to_thread(_install_macos_helper_impl)

    # MAMP-style behavior: once helper is installed, immediately apply
    # current standard-ports preference (80/443 forwarding).
    if result.success:
        try:
            registry = await read_registry()
            warning = await _sync_standard_ports(registry.settings)
            if warning:
                result.output = "\n".join([part for part in [result.output, warning] if part]).strip()
        except Exception as exc:
            result.output = "\n".join(
                [part for part in [result.output, f"Warning: unable to sync standard ports: {exc}"] if part]
            ).strip()

    return result

@app.post("/api/helper/uninstall", response_model=CommandResult)
async def uninstall_helper() -> CommandResult:
    return await asyncio.to_thread(_uninstall_macos_helper_impl)


@app.post("/api/proxy/standard-ports/disable", response_model=CommandResult)
async def disable_standard_ports() -> CommandResult:
    # MAMP-style: release ports 80/443 immediately (no prompts) when the helper is installed.
    if platform.system() == "Darwin" and MACOS_HELPER_SOCKET.exists():
        result = await asyncio.to_thread(_helper_disable_standard_ports)
        if result.success:
            # Persist the setting too so Save & Apply isn't required for this quick action.
            await mutate_registry(
                lambda registry: Registry(
                    projects=registry.projects,
                    settings=AppSettings(**{**registry.settings.model_dump(), "standardPortsEnabled": False}),
                )
            )
        return result

    # Legacy fallback: keep existing behavior (may prompt).
    return await _disable_macos_pf_redirect()


@app.post("/api/certificates/generate", response_model=CertificateInfo)
async def generate_certificate(payload: DomainPayload) -> CertificateInfo:
    try:
        return await asyncio.to_thread(_generate_certificate, payload.domain, [payload.domain, f"www.{payload.domain}"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_client(str(exc)))


@app.get("/api/certificates/{domain}", response_model=CertificateInfo)
async def certificate_status(domain: str) -> CertificateInfo:
    return _check_certificate(domain)


@app.post("/api/certificates/install-ca")
async def install_ca() -> Dict[str, Any]:
    result = await asyncio.to_thread(_install_root_ca)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    await mutate_registry(
        lambda registry: Registry(
            projects=registry.projects,
            settings=AppSettings(**{**registry.settings.model_dump(), "caInstalled": True}),
        )
    )
    return {"message": "Root CA installed"}


@app.post("/api/certificates/uninstall-ca", response_model=CommandResult)
async def uninstall_ca() -> CommandResult:
    result = await asyncio.to_thread(_uninstall_root_ca)
    if result.success:
        await mutate_registry(
            lambda registry: Registry(
                projects=registry.projects,
                settings=AppSettings(**{**registry.settings.model_dump(), "caInstalled": False}),
            )
        )
    return result


@app.get("/api/certificates/ca/status")
async def ca_status() -> Dict[str, bool]:
    return _check_root_ca_status()


@app.post("/api/databases/{project_id}/start")
async def start_database(project_id: str) -> Dict[str, Any]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    db_type = project.database.type

    if db_type == "none":
        return {"message": "No managed database configured"}

    result = await _start_service(db_type)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message": result.output}


@app.post("/api/databases/{project_id}/stop")
async def stop_database(project_id: str) -> Dict[str, Any]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    db_type = project.database.type

    if db_type == "none":
        return {"message": "No managed database configured"}

    result = await _stop_service(db_type)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message": result.output}


@app.post("/api/databases/{project_id}/test", response_model=CommandResult)
async def test_database_connection(project_id: str) -> CommandResult:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    db_type = project.database.type

    if db_type == "none":
        return CommandResult(success=True, output="Using unmanaged database (likely SQLite)")

    if db_type == "postgres":
        cmd = ["pg_isready", "-h", "127.0.0.1", "-p", str(project.database.port or 54329), "-d", "postgres"]
    elif db_type == "mysql":
        cmd = ["mysqladmin", "ping", "-h", "127.0.0.1", "-P", str(project.database.port or 33069)]
    else:
        cmd = ["redis-cli", "-p", str(project.cache.port or 6389), "ping"]

    return await asyncio.to_thread(_run_blocking, cmd, Path(project.path))

@app.get("/api/databases/{project_id}/admin-url")
async def get_database_admin_url(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)

    if project.database.type != "postgres":
        raise HTTPException(status_code=400, detail="Web database admin currently supports PostgreSQL projects only")

    if not _is_port_open(project.port):
        raise HTTPException(status_code=409, detail="Project is not running. Start project first to open DB Admin.")

    protocol = "https" if project.httpsEnabled else "http"
    url = f"{protocol}://{project.domain}"

    proxy_active = _is_port_open(registry.settings.proxyPort if project.httpsEnabled else registry.settings.proxyHttpPort)
    standard_active = _is_port_open(443 if project.httpsEnabled else 80)
    if not proxy_active or not standard_active:
        port = registry.settings.proxyPort if project.httpsEnabled else registry.settings.proxyHttpPort
        url = f"{url}:{port}"

    return {"url": f"{url}/phpMyAdmin5/"}


@app.get("/api/databases/{project_id}/admin", response_class=HTMLResponse)
async def open_database_admin(project_id: str, query: str = "") -> HTMLResponse:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)

    if project.database.type != "postgres":
        raise HTTPException(status_code=400, detail="Web database admin currently supports PostgreSQL projects only")

    if not _is_port_open(project.port):
        raise HTTPException(status_code=409, detail="Project is not running. Start project first to open DB Admin.")

    start_result = await _start_service("postgres")
    if not start_result.success:
        raise HTTPException(status_code=500, detail=start_result.error or "Failed to start managed Postgres service")

    tables_sql = (
        "SELECT table_schema || '.' || table_name AS table_name "
        "FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY 1"
    )
    tables_result = await asyncio.to_thread(_run_postgres_query_text, project, tables_sql)

    query_output = ""
    query_error = ""
    normalized_query = (query or "").strip()
    if normalized_query:
        run_result = await asyncio.to_thread(_run_postgres_query_text, project, normalized_query)
        if run_result.success:
            query_output = run_result.output
        else:
            query_error = run_result.error or run_result.output or "Query failed"

    tables_output = tables_result.output if tables_result.success else (tables_result.error or tables_result.output or "Unable to read table list")

    return HTMLResponse(
        _render_postgres_admin_html(
            project=project,
            tables_output=tables_output,
            query=normalized_query,
            query_output=query_output,
            query_error=query_error,
        )
    )



@app.get("/api/logs/{project_id}/{source}")
async def get_logs(project_id: str, source: str) -> str:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)

    if source == "django":
        path = project_log_path(project.id)
    elif source == "proxy":
        path = paths()["proxy_logs"] / "caddy.log"
    elif source == "database":
        path = service_log_path("postgres")
    else:
        raise HTTPException(status_code=400, detail="Unknown log source")

    try:
        safe_path = _safe_log_path(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not safe_path.exists():
        return ""

    data = safe_path.read_text(encoding="utf-8", errors="ignore")
    return data[-20000:]


@app.post("/api/utilities/detect-django", response_model=DetectionResult)
async def detect_django_project(payload: Dict[str, str]) -> DetectionResult:
    path = payload.get("path", "")
    return await asyncio.to_thread(detect_django, path)


@app.post("/api/utilities/create-venv")
async def create_venv(payload: CreateVenvPayload) -> Dict[str, str]:
    project = _sanitize_user_project_path(payload.path)
    venv = project / ".venv"

    uv_bin = shutil.which("uv")
    if uv_bin:
        result = await asyncio.to_thread(_run_blocking, [uv_bin, "venv", str(venv)], project)
    else:
        py = shutil.which("python3") or shutil.which("python")
        if not py:
            raise HTTPException(status_code=500, detail="No Python interpreter found")
        result = await asyncio.to_thread(_run_blocking, [py, "-m", "venv", str(venv)], project)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {"message": "Virtual environment created"}


@app.post("/api/utilities/install-dependencies", response_model=CommandResult)
async def install_dependencies(payload: InstallDependenciesPayload) -> CommandResult:
    registry = await read_registry()
    project = _get_project_or_404(registry, payload.projectId)
    req = Path(project.path) / "requirements.txt"
    if not req.exists():
        return CommandResult(success=True, output="No requirements.txt found")

    manage_py = _find_manage_py(project)
    command, _ = await asyncio.to_thread(_build_manage_command, project, manage_py, ["--version"])
    interpreter = command[0]

    uv_bin = shutil.which("uv")
    if project.runtimeMode == "uv" and uv_bin:
        result = await asyncio.to_thread(
            _run_blocking,
            [uv_bin, "pip", "install", "--python", interpreter, "-r", str(req)],
            Path(project.path),
        )
    else:
        result = await asyncio.to_thread(
            _run_blocking,
            [interpreter, "-m", "pip", "install", "-r", str(req)],
            Path(project.path),
        )

    return result


@app.post("/api/utilities/{project_id}/shell")
async def open_shell(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)

    if project.runtimeMode == "conda" and project.condaEnv:
        cmd = f"cd {shlex.quote(project.path)} && conda activate {shlex.quote(project.condaEnv)}"
    else:
        cmd = f"cd {shlex.quote(project.path)}"

    return {"message": cmd}


@app.post("/api/utilities/{project_id}/db-shell")
async def open_db_shell(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)

    if project.database.type == "postgres":
        db_name = project.database.name or "postgres"
        db_user = project.database.username or "postgres"
        db_password = project.database.password or ""
        db_port = project.database.port or MANAGED_POSTGRES_PORT
        cmd = (
            f"cd {shlex.quote(project.path)} && "
            f"PGPASSWORD={shlex.quote(db_password)} "
            f"psql -h 127.0.0.1 -p {int(db_port)} -U {shlex.quote(db_user)} -d {shlex.quote(db_name)}"
        )
        return {"message": cmd}

    if project.database.type == "mysql":
        db_name = project.database.name or "mysql"
        db_user = project.database.username or "root"
        db_password = project.database.password or ""
        db_port = project.database.port or MANAGED_MYSQL_PORT
        cmd = (
            f"cd {shlex.quote(project.path)} && "
            f"mysql -h 127.0.0.1 -P {int(db_port)} -u {shlex.quote(db_user)} "
            f"-p{shlex.quote(db_password)} {shlex.quote(db_name)}"
        )
        return {"message": cmd}

    return {"message": f"echo 'No managed database configured for {project.name}'"}


@app.post("/api/utilities/{project_id}/vscode")
async def open_vscode(project_id: str) -> Dict[str, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    return {"message": project.path}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("djamp_controller.main:app", host="127.0.0.1", port=8765, reload=False, log_level="info")
