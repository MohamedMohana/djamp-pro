from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import html
import json
import os
import platform
import re
import shlex
import shutil
import tarfile
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from urllib.parse import quote_plus, urlparse

from .models import (  # noqa: F401 -- some names are re-exported for compatibility
    AddProjectPayload,
    AppSettings,
    CacheConfig,
    CertificateInfo,
    CommandResult,
    CreateSuperuserPayload,
    CreateVenvPayload,
    DatabaseConfig,
    DetectionResult,
    DomainPayload,
    InstallDependenciesPayload,
    MANAGED_MYSQL_PORT,
    MANAGED_POSTGRES_PORT,
    MANAGED_REDIS_PORT,
    Project,
    ProxyStatus,
    Registry,
    ShellPayload,
    UpdateProjectPayload,
    UpdateSettingsPayload,
)
from .paths import (  # noqa: F401 -- some names are re-exported for compatibility
    APP_NAME,
    _canonical_project_id,
    _is_relative_to,
    _repo_root,
    _safe_log_path,
    _tail_file,
    app_home,
    ensure_dirs,
    paths,
    project_log_path,
    service_log_path,
    utc_now,
)
from .subprocess_security import (  # noqa: F401 -- some names are re-exported for compatibility
    _ALLOWED_SUBPROCESS_EXECUTABLES,
    _DISALLOWED_EXECUTABLE_ROOTS,
    _allowed_executable_roots,
    _disallowed_executable_roots,
    _find_allowed_executable,
    _prepend_path_env,
    _resolve_allowed_executable_path,
    _run_blocking,
    _sanitize_subprocess_command,
)
from .macos_helper import (  # noqa: F401 -- some names are re-exported for compatibility
    MACOS_HELPER_BIN,
    MACOS_HELPER_LABEL,
    MACOS_HELPER_PLIST,
    MACOS_HELPER_SOCKET,
    MANAGED_PF_BEGIN,
    MANAGED_PF_END,
    _build_macos_helper_binary,
    _disable_macos_pf_redirect,
    _disable_macos_pf_redirect_impl,
    _friendly_hosts_helper_error,
    _helper_disable_standard_ports,
    _helper_enable_standard_ports,
    _helper_hosts_apply,
    _helper_hosts_clear,
    _helper_request,
    _install_macos_helper_impl,
    _macos_helper_installed,
    _priv_helper_binary,
    _render_macos_helper_plist,
    _run_with_macos_elevation,
    _uninstall_macos_helper_impl,
)
from .domains import (  # noqa: F401 -- some names are re-exported for compatibility
    MANAGED_HOSTS_BEGIN,
    MANAGED_HOSTS_END,
    _apply_hosts_entries_impl,
    _clear_hosts_block,
    _clear_hosts_block_impl,
    _enforce_domain_policy,
    _flush_macos_dns_cache,
    _is_local_dev_domain,
    _join_hosts_sections,
    _join_marked_sections,
    _join_without_section,
    _project_domains,
    _sanitize_hostname,
    _split_hosts_sections,
    _split_marked_sections,
    _sync_domains_for_registry,
    _sync_domains_for_registry_impl,
    _try_sanitize_hostname,
)
from .certificates import (  # noqa: F401 -- some names are re-exported for compatibility
    _certificate_paths,
    _check_certificate,
    _check_root_ca_status,
    _ensure_root_ca,
    _generate_certificate,
    _get_cert_expiration,
    _install_root_ca,
    _is_root_ca_trusted_macos,
    _normalize_hex,
    _openssl_sha1_fingerprint,
    _root_ca_paths,
    _security_keychain_sha1_hashes,
    _tighten_cert_permissions,
    _uninstall_root_ca,
)
from .registry import (  # noqa: F401 -- some names are re-exported for compatibility
    REGISTRY_LOCK,
    _normalize_project_paths,
    _scrub_project_for_storage,
    _scrub_registry_for_storage,
    default_registry,
    load_registry_sync,
    mutate_registry,
    read_registry,
    save_registry_sync,
    write_registry,
)
from .processes import (  # noqa: F401 -- some names are re-exported for compatibility
    PROJECT_PROCESSES,
    SERVICE_PROCESSES,
    _apply_djamp_project_env,
    _base_env,
    _build_manage_command,
    _conda_env_prefix,
    _conda_python_from_prefix,
    _ensure_django_settings_override,
    _ensure_uv_runtime,
    _find_manage_py,
    _is_port_open,
    _kill_processes_on_port,
    _kill_stray_project_processes,
    _platform_python,
    _spawn_background_task,
    _terminate_process,
)

MANAGED_ENV_BEGIN = "# BEGIN DJAMP PRO MANAGED ENV"
MANAGED_ENV_END = "# END DJAMP PRO MANAGED ENV"
CADDY_GITHUB_LATEST = "https://api.github.com/repos/caddyserver/caddy/releases/latest"


def _require_project_id(project_id: str) -> str:
    parsed = _canonical_project_id(project_id)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    return parsed


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


def _service_binary(name: str) -> Optional[str]:
    if name == "postgres":
        return _find_allowed_executable("postgres", paths()["home"])
    if name == "mysql":
        return _find_allowed_executable("mysqld", paths()["home"])
    if name == "redis":
        return _find_allowed_executable("redis-server", paths()["home"])
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

    if name == "postgres":
        initdb = _find_allowed_executable("initdb", paths()["home"])
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

    # Open the log handle only after all preflight checks so failures above
    # cannot leak a file descriptor; close it if spawning itself fails.
    log_handle = open(service_log_path(name), "a", encoding="utf-8")
    try:
        if name == "postgres":
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
    except BaseException:
        log_handle.close()
        raise

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
    psql = _find_allowed_executable("psql", paths()["home"])
    pg_isready = _find_allowed_executable("pg_isready", paths()["home"])
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
    psql = _find_allowed_executable("psql", paths()["home"])
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


def _startup_controller() -> None:
    ensure_dirs()
    _ = load_registry_sync()


async def _shutdown_controller() -> None:
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


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    _startup_controller()
    try:
        yield
    finally:
        await _shutdown_controller()


app = FastAPI(
    title="DJAMP PRO Controller",
    description="Controller service for DJAMP PRO desktop application",
    version="1.2.3",
    lifespan=app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        _spawn_background_task(_sync_domains_for_registry(refreshed), "sync-domains-after-update")
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
        _spawn_background_task(_sync_domains_for_registry(updated), "sync-domains-after-delete")
        _spawn_background_task(
            _reload_caddy(updated.projects, allow_privileged=False), "reload-caddy-after-delete"
        )
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
    home_prefix = home_root if home_root.endswith(os.sep) else f"{home_root}{os.sep}"
    if resolved != home_root and not resolved.startswith(home_prefix):
        raise HTTPException(status_code=400, detail="Project path must be inside your home directory")

    relative = os.path.relpath(resolved, home_root)
    if relative in ("", "."):
        safe_parts: List[str] = []
    else:
        safe_parts = []
        for part in Path(relative).parts:
            if part in ("", ".", ".."):
                raise HTTPException(status_code=400, detail="Invalid project path")
            if not re.fullmatch(r"[A-Za-z0-9._ -]+", part):
                raise HTTPException(status_code=400, detail="Project path contains unsupported characters")
            safe_parts.append(part)

    project = Path(home_root)
    for part in safe_parts:
        project = project / part
    project = project.resolve()

    if not _is_relative_to(project, Path(home_root)):
        raise HTTPException(status_code=400, detail="Invalid project path")
    if not project.is_dir():
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

    uv_bin = _find_allowed_executable("uv", project)
    if uv_bin:
        result = await asyncio.to_thread(_run_blocking, [uv_bin, "venv", str(venv)], project)
    else:
        py = _find_allowed_executable("python3", project) or _find_allowed_executable("python", project)
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

    uv_bin = _find_allowed_executable("uv", Path(project.path))
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
        # Pass the password via MYSQL_PWD instead of -p<password> so it does
        # not show up in the process list for the lifetime of the session.
        cmd = (
            f"cd {shlex.quote(project.path)} && "
            f"MYSQL_PWD={shlex.quote(db_password)} "
            f"mysql -h 127.0.0.1 -P {int(db_port)} -u {shlex.quote(db_user)} "
            f"{shlex.quote(db_name)}"
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
