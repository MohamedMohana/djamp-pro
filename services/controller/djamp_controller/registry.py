from __future__ import annotations

import asyncio
from pathlib import Path

from .models import Project, Registry
from .paths import _repo_root, ensure_dirs, paths

REGISTRY_LOCK = asyncio.Lock()


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
