from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
import platform
import re
import shlex
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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
from .frameworks import (  # noqa: F401 -- some names are re-exported for compatibility
    detect_project,
    project_framework,
    validate_app_module,
)
from .processes import (  # noqa: F401 -- some names are re-exported for compatibility
    PROJECT_PROCESSES,
    SERVICE_PROCESSES,
    _apply_djamp_project_env,
    _base_env,
    _build_manage_command,
    _build_python_command,
    _build_server_command,
    _conda_env_prefix,
    _conda_python_from_prefix,
    _ensure_django_settings_override,
    _ensure_uv_runtime,
    _find_manage_py,
    _is_port_open,
    _kill_processes_on_port,
    _kill_stray_project_processes,
    _platform_python,
    _resolve_runtime,
    _spawn_background_task,
    _stray_process_pattern,
    _terminate_process,
)
from .proxy import (  # noqa: F401 -- some names are re-exported for compatibility
    CADDY_GITHUB_LATEST,
    _caddy_binary,
    _caddy_result_with_standard_ports,
    _download_file,
    _ensure_caddy_installed,
    _hash_file,
    _reload_caddy,
    _render_caddyfile,
    _sync_standard_ports,
)
from .database import (  # noqa: F401 -- some names are re-exported for compatibility
    MANAGED_ENV_BEGIN,
    MANAGED_ENV_END,
    _display_environment_vars,
    _dotenv_path,
    _ensure_postgres_db_and_role,
    _extract_db_from_dotenv,
    _hydrate_project_db_from_dotenv,
    _is_sensitive_env_key,
    _mask_sensitive_env_value,
    _parse_dotenv_file,
    _parse_psql_result,
    _render_postgres_admin_html,
    _render_psql_result_table,
    _run_postgres_query_text,
    _service_binary,
    _start_service,
    _stop_service,
    _sync_managed_env_block,
    _validate_simple_identifier,
)


def _require_project_id(project_id: str) -> str:
    parsed = _canonical_project_id(project_id)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    return parsed


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


# Backwards-compatible alias; detection now lives in frameworks.py and covers
# Django, FastAPI, Flask, and generic ASGI/WSGI apps.
detect_django = detect_project


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
        if project_framework(project) != "django":
            if not project.appModule.strip():
                detected = detect_project(project.path)
                if detected.found and detected.appModules:
                    project.appModule = detected.appModules[0]
            project.appModule = validate_app_module(project.appModule)
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

    # Validate the framework entrypoint before spawning anything.
    try:
        if project_framework(project) == "django":
            _find_manage_py(project)
        else:
            if not project.appModule.strip():
                detected = await asyncio.to_thread(detect_project, project.path)
                if detected.found and detected.appModules:
                    project.appModule = detected.appModules[0]
                    await _update_project(registry, project)
            validate_app_module(project.appModule)
    except (FileNotFoundError, ValueError) as exc:
        project.status = "error"
        await _update_project(registry, project)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    try:
        _kill_stray_project_processes(_stray_process_pattern(project, project.port))
    except Exception:
        pass

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

    try:
        command, env = await asyncio.to_thread(_build_server_command, project)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        project.status = "error"
        await _update_project(registry, project)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        _kill_stray_project_processes(_stray_process_pattern(project, project.port))
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


async def _run_project_task(
    project_id: str,
    task_args: List[str],
    extra_env: Optional[Dict[str, str]] = None,
    *,
    use_manage_py: bool = True,
) -> CommandResult:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    project_id = project.id
    manage_py = _find_manage_py(project) if use_manage_py else None

    def runner() -> CommandResult:
        if manage_py is not None:
            command, env = _build_manage_command(project, manage_py, task_args)
        else:
            command, env = _build_python_command(project, task_args)
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


async def _project_framework_for(project_id: str) -> tuple[Project, str]:
    registry = await read_registry()
    project = _get_project_or_404(registry, project_id)
    return project, project_framework(project)


@app.post("/api/projects/{project_id}/migrate", response_model=CommandResult)
async def migrate_project(project_id: str) -> CommandResult:
    project, framework = await _project_framework_for(project_id)
    if framework == "django":
        return await _run_project_task(project_id, ["migrate"])

    root = Path(project.path)
    if (root / "alembic.ini").exists():
        return await _run_project_task(project_id, ["-m", "alembic", "upgrade", "head"], use_manage_py=False)
    if framework == "flask" and (root / "migrations").exists():
        try:
            app_module = validate_app_module(project.appModule)
        except ValueError as exc:
            return CommandResult(success=False, error=str(exc))
        return await _run_project_task(
            project_id, ["-m", "flask", "--app", app_module, "db", "upgrade"], use_manage_py=False
        )
    return CommandResult(
        success=False,
        error=(
            "No migration tool detected. Expected a Django project, an alembic.ini "
            "(Alembic), or a Flask-Migrate migrations/ directory."
        ),
    )


@app.post("/api/projects/{project_id}/collectstatic", response_model=CommandResult)
async def collect_static(project_id: str) -> CommandResult:
    _, framework = await _project_framework_for(project_id)
    if framework != "django":
        return CommandResult(success=False, error="collectstatic is only available for Django projects.")
    return await _run_project_task(project_id, ["collectstatic", "--noinput"])


@app.post("/api/projects/{project_id}/createsuperuser", response_model=CommandResult)
async def create_superuser(project_id: str, payload: CreateSuperuserPayload) -> CommandResult:
    _, framework = await _project_framework_for(project_id)
    if framework != "django":
        return CommandResult(success=False, error="createsuperuser is only available for Django projects.")
    env = {
        "DJANGO_SUPERUSER_USERNAME": payload.username,
        "DJANGO_SUPERUSER_EMAIL": payload.email,
        "DJANGO_SUPERUSER_PASSWORD": os.getenv("DJAMP_DEFAULT_SUPERUSER_PASSWORD", "djamp-pro-admin"),
    }
    return await _run_project_task(project_id, ["createsuperuser", "--noinput"], env)


@app.post("/api/projects/{project_id}/test", response_model=CommandResult)
async def run_tests(project_id: str) -> CommandResult:
    _, framework = await _project_framework_for(project_id)
    if framework == "django":
        return await _run_project_task(project_id, ["test"])
    return await _run_project_task(project_id, ["-m", "pytest"], use_manage_py=False)


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
@app.post("/api/utilities/detect-project", response_model=DetectionResult)
async def detect_project_endpoint(payload: Dict[str, str]) -> DetectionResult:
    path = payload.get("path", "")
    return await asyncio.to_thread(detect_project, path)


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

    prefix, _env = await asyncio.to_thread(_resolve_runtime, project)
    interpreter = str(_platform_python(project)) if project.runtimeMode == "uv" else prefix[0]

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
