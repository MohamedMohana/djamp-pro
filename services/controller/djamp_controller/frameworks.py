from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from .models import DetectionResult, Project, SUPPORTED_FRAMEWORKS

# Directories that never contain the user's app entrypoint. Pruned during scans
# to keep detection fast on large projects.
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "site-packages",
    ".venv",
    "venv",
    "env",
    "virtualenv",
    "migrations",
    "staticfiles",
    "static",
    "media",
    "dist",
    "build",
    "tests",
    "test",
}

# Typical entrypoint filenames, in preference order for ranking candidates.
_ENTRY_FILENAMES = [
    "main.py",
    "app.py",
    "application.py",
    "server.py",
    "api.py",
    "run.py",
    "asgi.py",
    "wsgi.py",
]

_MAX_SCAN_FILES = 4000
_MAX_FILE_BYTES = 1_000_000

_APP_ASSIGNMENT_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(FastAPI|Flask|Starlette|Quart|Sanic)\s*\(",
    re.MULTILINE,
)
# get_asgi_application()/get_wsgi_application() style factories and plain
# `application = ...` in asgi.py/wsgi.py files.
_GENERIC_APP_RE = re.compile(r"^\s*(application|app)\s*=", re.MULTILINE)

_CLASS_FRAMEWORKS = {
    "FastAPI": "fastapi",
    "Flask": "flask",
    "Starlette": "asgi",
    "Quart": "asgi",
    "Sanic": "asgi",
}

_APP_MODULE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*")


def project_framework(project: Project) -> str:
    framework = (getattr(project, "framework", "") or "").strip().lower()
    return framework if framework in SUPPORTED_FRAMEWORKS else "django"


def validate_app_module(app_module: str) -> str:
    """Validate 'package.module:variable' notation before it reaches a command line."""
    candidate = (app_module or "").strip()
    if not candidate:
        raise ValueError("appModule is empty. Use 'module:app' notation, e.g. 'main:app'.")
    if not _APP_MODULE_RE.fullmatch(candidate):
        raise ValueError(f"Invalid appModule {candidate!r}. Use 'module:app' notation, e.g. 'main:app'.")
    return candidate


def _module_name(project_root: Path, file_path: Path) -> Optional[str]:
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        return None
    parts = list(rel.with_suffix("").parts)
    if not parts:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _iter_python_files(project_root: Path) -> List[Path]:
    """Breadth-first walk so shallow entrypoints are scanned before deep modules."""
    results: List[Path] = []
    queue: List[Path] = [project_root]
    seen = 0
    while queue and seen < _MAX_SCAN_FILES:
        current = queue.pop(0)
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_dir(), p.name))
        except OSError:
            continue
        for entry in entries:
            if seen >= _MAX_SCAN_FILES:
                break
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS and not entry.name.startswith("."):
                    queue.append(entry)
                continue
            if entry.suffix == ".py":
                results.append(entry)
                seen += 1
    return results


def _candidate_rank(project_root: Path, file_path: Path) -> Tuple[int, int]:
    rel = file_path.relative_to(project_root)
    depth = len(rel.parts)
    try:
        name_rank = _ENTRY_FILENAMES.index(file_path.name)
    except ValueError:
        name_rank = len(_ENTRY_FILENAMES)
    return (depth, name_rank)


def _dependency_hints(project_root: Path) -> str:
    """Concatenated dependency manifests, lowercased, for cheap substring hints."""
    chunks: List[str] = []
    for name in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg"):
        candidate = project_root / name
        try:
            if candidate.exists() and candidate.stat().st_size < _MAX_FILE_BYTES:
                chunks.append(candidate.read_text(encoding="utf-8", errors="ignore").lower())
        except OSError:
            continue
    return "\n".join(chunks)


def _find_settings_modules(project_root: Path) -> List[str]:
    settings = []
    for candidate in project_root.rglob("settings.py"):
        if any(part in _SKIP_DIRS for part in candidate.parts):
            continue
        module = _module_name(project_root, candidate)
        if module:
            settings.append(module)
    return sorted(set(settings))


def detect_project(path: str) -> DetectionResult:
    """Detect the web framework used by a project directory.

    Priority: Django (manage.py) > FastAPI/Flask/other app objects found in
    source > generic asgi.py/wsgi.py entrypoints, with dependency manifests as
    a tie-breaker.
    """
    project_root = Path(path).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        return DetectionResult(found=False)

    manage_candidates = [
        candidate
        for candidate in project_root.rglob("manage.py")
        if not any(part in _SKIP_DIRS for part in candidate.parts)
    ]
    if manage_candidates:
        return DetectionResult(
            found=True,
            framework="django",
            managePyPath=str(manage_candidates[0]),
            settingsModules=_find_settings_modules(project_root),
        )

    scored: List[Tuple[Tuple[int, int], str, str]] = []  # (rank, framework, module:var)
    generic: List[Tuple[Tuple[int, int], str, str]] = []

    for file_path in _iter_python_files(project_root):
        try:
            if file_path.stat().st_size > _MAX_FILE_BYTES:
                continue
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        module = _module_name(project_root, file_path)
        if not module:
            continue
        rank = _candidate_rank(project_root, file_path)

        for match in _APP_ASSIGNMENT_RE.finditer(source):
            var_name, class_name = match.group(1), match.group(2)
            framework = _CLASS_FRAMEWORKS[class_name]
            scored.append((rank, framework, f"{module}:{var_name}"))

        if file_path.name in ("asgi.py", "wsgi.py"):
            match = _GENERIC_APP_RE.search(source)
            if match:
                framework = "asgi" if file_path.name == "asgi.py" else "wsgi"
                generic.append((rank, framework, f"{module}:{match.group(1)}"))

    hints = _dependency_hints(project_root)

    if scored:
        scored.sort(key=lambda item: item[0])
        frameworks = {framework for _, framework, _ in scored}
        best_framework = scored[0][1]
        # A FastAPI/Flask dependency hint outranks an ambiguous first hit.
        if len(frameworks) > 1:
            for hinted in ("fastapi", "flask"):
                if hinted in frameworks and hinted in hints:
                    best_framework = hinted
                    break
        app_modules = [candidate for _, framework, candidate in scored if framework == best_framework]
        # Keep other frameworks' candidates too so the UI can offer them.
        app_modules += [candidate for _, framework, candidate in scored if framework != best_framework]
        return DetectionResult(
            found=True,
            framework=best_framework,
            appModules=list(dict.fromkeys(app_modules)),
        )

    if generic:
        generic.sort(key=lambda item: item[0])
        best_framework = generic[0][1]
        app_modules = [candidate for _, _, candidate in generic]
        return DetectionResult(
            found=True,
            framework=best_framework,
            appModules=list(dict.fromkeys(app_modules)),
        )

    return DetectionResult(found=False)
