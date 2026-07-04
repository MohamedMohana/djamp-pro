from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .domains import _project_domains
from .frameworks import project_framework, validate_app_module
from .models import (
    MANAGED_MYSQL_PORT,
    MANAGED_POSTGRES_PORT,
    MANAGED_REDIS_PORT,
    CommandResult,
    Project,
)
from .paths import ensure_dirs, paths
from .subprocess_security import _find_allowed_executable, _prepend_path_env, _run_blocking

PROJECT_PROCESSES: Dict[str, Tuple[asyncio.subprocess.Process, Any]] = {}
SERVICE_PROCESSES: Dict[str, Tuple[asyncio.subprocess.Process, Any]] = {}

# Strong references to best-effort background tasks. Without these, the event
# loop only holds a weak reference and a task can be garbage-collected mid-run.
_BACKGROUND_TASKS: set = set()


def _spawn_background_task(coro: Any, label: str) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)

    def _on_done(done: asyncio.Task) -> None:
        _BACKGROUND_TASKS.discard(done)
        if done.cancelled():
            return
        exc = done.exception()
        if exc is not None:
            print(
                f"[djamp-controller] background task '{label}' failed: {exc}",
                file=sys.stderr,
                flush=True,
            )

    task.add_done_callback(_on_done)


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


def _stray_process_pattern(project: Project, port: int) -> str:
    """pgrep -f pattern matching this project's dev-server processes."""
    framework = project_framework(project)
    if framework == "django":
        manage_py = _find_manage_py(project)
        return f"{str(manage_py)}.*runserver.*{int(port)}"

    app_module = re.escape((project.appModule or "").strip())
    if framework == "flask":
        return f"flask.*{app_module}.*{int(port)}"
    return f"uvicorn.*{app_module}.*{int(port)}"


def _kill_stray_project_processes(pattern: str) -> None:
    """Best-effort cleanup for orphaned dev-server processes that may not be listening anymore."""
    if platform.system() == "Windows" or not shutil.which("pgrep"):
        return

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
    if project_framework(project) == "django" and project.settingsModule:
        env.setdefault("DJANGO_SETTINGS_MODULE", project.settingsModule)
    # Ensure logs flush promptly even when redirected to files.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _apply_djamp_project_env(project: Project, env: Dict[str, str]) -> Dict[str, str]:
    out = dict(env)

    if project_framework(project) == "django":
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


def _ensure_uv_runtime(project: Project) -> CommandResult:
    python_path = _platform_python(project)
    project_root = Path(project.path)

    uv_bin = _find_allowed_executable("uv", project_root)
    if not uv_bin:
        return CommandResult(success=False, error="`uv` is not installed or not in PATH")

    if not python_path.exists():
        venv_path = python_path.parent.parent
        create = _run_blocking([uv_bin, "venv", str(venv_path)], project_root)
        if not create.success:
            return create

    requirements = project_root / "requirements.txt"
    uv_lock = project_root / "uv.lock"
    if requirements.exists():
        install = _run_blocking(
            [uv_bin, "pip", "install", "--python", str(python_path), "-r", str(requirements)],
            project_root,
        )
        if not install.success:
            return install
    elif uv_lock.exists():
        # Modern uv-managed projects (pyproject.toml + uv.lock): sync the locked
        # dependencies into the DJAMP-managed venv instead of requirements.txt.
        # --inexact keeps packages DJAMP adds on top (e.g. auto-installed uvicorn)
        # from being uninstalled on the next sync.
        sync_env = os.environ.copy()
        sync_env["UV_PROJECT_ENVIRONMENT"] = str(python_path.parent.parent)
        install = _run_blocking([uv_bin, "sync", "--frozen", "--inexact"], project_root, sync_env)
        if not install.success:
            return install

    return CommandResult(success=True)


def _conda_env_prefix(env_name: str) -> Path:
    conda_bin = _find_allowed_executable("conda", paths()["home"])
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


def _resolve_runtime(project: Project) -> Tuple[List[str], Dict[str, str]]:
    """Resolve the interpreter argv prefix and environment for the project's runtime mode."""
    mode = project.runtimeMode
    env = _base_env(project)

    if mode == "uv":
        runtime_result = _ensure_uv_runtime(project)
        if not runtime_result.success:
            raise RuntimeError(runtime_result.error or "Failed to initialize uv runtime")

        python_bin = _platform_python(project)
        _prepend_path_env(env, python_bin.parent)
        return ["python"], env

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

        return ["python"], env

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

        if "/" in custom_exec or "\\" in custom_exec:
            custom_path = Path(custom_exec).expanduser()
            # Do not resolve symlinks on absolute paths: a venv's bin/python is a
            # symlink to the base interpreter, and resolving it would escape the venv.
            if not custom_path.is_absolute():
                custom_path = custom_path.resolve()
            if not custom_path.exists() or not custom_path.is_file():
                raise RuntimeError(f"Custom interpreter not found: {custom_path}")
            return [str(custom_path)], env

        if not re.fullmatch(r"[A-Za-z0-9._+-]+", custom_exec):
            raise RuntimeError("Custom interpreter contains unsupported characters")
        return [custom_exec], env

    interpreter = shutil.which("python3") or shutil.which("python")
    if not interpreter:
        raise RuntimeError("No Python interpreter found")

    return [Path(interpreter).name], env


def _build_manage_command(project: Project, manage_py: Path, django_args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    prefix, env = _resolve_runtime(project)
    return [*prefix, str(manage_py), *django_args], env


def _build_python_command(project: Project, args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    prefix, env = _resolve_runtime(project)
    return [*prefix, *args], env


def _build_server_command(project: Project) -> Tuple[List[str], Dict[str, str]]:
    """Build the dev-server command for the project's framework."""
    framework = project_framework(project)

    if framework == "django":
        manage_py = _find_manage_py(project)
        return _build_manage_command(project, manage_py, ["runserver", f"127.0.0.1:{project.port}"])

    app_module = validate_app_module(project.appModule)

    if framework == "flask":
        args = ["-m", "flask", "--app", app_module, "run", "--host", "127.0.0.1", "--port", str(project.port)]
        if project.debug:
            args.append("--debug")
        return _build_python_command(project, args)

    # fastapi / asgi / wsgi all run behind uvicorn. --proxy-headers makes apps
    # behind the Caddy proxy see the real scheme/client (https://myapp.test),
    # mirroring what the Django settings override provides for Django projects.
    args = ["-m", "uvicorn", app_module, "--host", "127.0.0.1", "--port", str(project.port), "--proxy-headers"]
    if framework == "wsgi":
        args += ["--interface", "wsgi"]
    if project.debug:
        args.append("--reload")
    return _build_python_command(project, args)


# Dev-server package required per framework. Django's runserver ships with the
# framework itself, but uvicorn/flask CLIs are often missing from a project's
# dependency list even though the app imports fine.
_FRAMEWORK_SERVER_PACKAGES = {
    "fastapi": "uvicorn",
    "asgi": "uvicorn",
    "wsgi": "uvicorn",
    "flask": "flask",
}


def _ensure_server_package(project: Project) -> None:
    """Make the dev server available in the project runtime, MAMP-style.

    For the DJAMP-managed uv venv the missing package is installed
    automatically; for user-managed runtimes (conda/system/custom) we fail
    with the exact command to run instead of touching their environment.
    """
    package = _FRAMEWORK_SERVER_PACKAGES.get(project_framework(project))
    if not package:
        return

    project_root = Path(project.path)
    prefix, env = _resolve_runtime(project)
    # Use the venv python's explicit path for the check: the subprocess sanitizer
    # resolves bare names through PATH with symlink resolution, which would escape
    # the venv (bin/python links to the base interpreter).
    check_prefix = [str(_platform_python(project))] if project.runtimeMode == "uv" else prefix

    def importable() -> bool:
        return _run_blocking([*check_prefix, "-c", f"import {package}"], project_root, env).success

    if importable():
        return

    if project.runtimeMode == "uv":
        uv_bin = _find_allowed_executable("uv", project_root)
        python_bin = _platform_python(project)
        if uv_bin and python_bin.exists():
            install = _run_blocking(
                [uv_bin, "pip", "install", "--python", str(python_bin), package],
                project_root,
            )
            if install.success and importable():
                return

    raise RuntimeError(
        f"'{package}' is not installed in the project's Python runtime. "
        f"Add '{package}' to the project's dependencies (or run `pip install {package}` "
        "in its environment) and start the project again."
    )
