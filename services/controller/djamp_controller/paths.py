from __future__ import annotations

import os
import platform
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

APP_NAME = "DJAMP PRO"


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
