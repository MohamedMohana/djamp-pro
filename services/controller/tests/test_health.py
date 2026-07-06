import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from djamp_controller.main import CONTROLLER_VERSION, health, root


def _manifest_version(path: Path) -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match, f"no version field found in {path}"
    return match.group(1)


def test_health_endpoint_contract() -> None:
    assert asyncio.run(health()) == {"status": "healthy", "version": CONTROLLER_VERSION}


def test_root_endpoint_contract() -> None:
    assert asyncio.run(root()) == {"name": "DJAMP PRO Controller", "status": "running"}


def test_controller_version_comes_from_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert CONTROLLER_VERSION == _manifest_version(pyproject)


def test_controller_version_matches_desktop_app() -> None:
    # The desktop app replaces any controller on port 8765 whose /health
    # version differs from its own CARGO_PKG_VERSION, so a drift between the
    # two manifests would make it distrust freshly spawned controllers.
    repo_root = Path(__file__).resolve().parents[3]
    cargo_toml = repo_root / "apps" / "desktop" / "src-tauri" / "Cargo.toml"
    assert CONTROLLER_VERSION == _manifest_version(cargo_toml)
