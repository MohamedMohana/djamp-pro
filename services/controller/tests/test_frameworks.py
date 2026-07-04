import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from djamp_controller.frameworks import detect_project, project_framework, validate_app_module
from djamp_controller.models import Project
from djamp_controller.processes import _build_server_command, _stray_process_pattern


def _make_project(tmp_path: Path, **overrides) -> Project:
    defaults = dict(
        id="f14ce00d-3fd8-47ae-b76c-5ab5c4acb522",
        name="Demo",
        path=str(tmp_path),
        settingsModule="",
        domain="demo.test",
        port=8010,
        runtimeMode="custom",
        customInterpreter="python3",
        createdAt="2026-03-15T00:00:00+00:00",
    )
    defaults.update(overrides)
    return Project(**defaults)


# --- detection -----------------------------------------------------------


def test_detect_django(tmp_path: Path) -> None:
    (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.py").write_text("DEBUG = True\n")

    result = detect_project(str(tmp_path))
    assert result.found
    assert result.framework == "django"
    assert result.managePyPath == str(tmp_path / "manage.py")
    assert "config.settings" in result.settingsModules


def test_detect_fastapi(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n"
    )

    result = detect_project(str(tmp_path))
    assert result.found
    assert result.framework == "fastapi"
    assert result.appModules[0] == "main:app"


def test_detect_fastapi_in_package(tmp_path: Path) -> None:
    pkg = tmp_path / "backend"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "api.py").write_text("from fastapi import FastAPI\napi = FastAPI(title='x')\n")

    result = detect_project(str(tmp_path))
    assert result.found
    assert result.framework == "fastapi"
    assert "backend.api:api" in result.appModules


def test_detect_flask(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from flask import Flask\n\napp = Flask(__name__)\n"
    )

    result = detect_project(str(tmp_path))
    assert result.found
    assert result.framework == "flask"
    assert result.appModules[0] == "app:app"


def test_detect_generic_asgi(tmp_path: Path) -> None:
    (tmp_path / "asgi.py").write_text("application = get_app()\n")

    result = detect_project(str(tmp_path))
    assert result.found
    assert result.framework == "asgi"
    assert result.appModules[0] == "asgi:application"


def test_detect_skips_virtualenvs(tmp_path: Path) -> None:
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    result = detect_project(str(tmp_path))
    assert not result.found


def test_detect_nothing(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not a python project")
    result = detect_project(str(tmp_path))
    assert not result.found


def test_manage_py_wins_over_app_objects(tmp_path: Path) -> None:
    (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    result = detect_project(str(tmp_path))
    assert result.framework == "django"


# --- app module validation -------------------------------------------------


def test_validate_app_module_accepts_dotted_paths() -> None:
    assert validate_app_module(" backend.app.main:app ") == "backend.app.main:app"


@pytest.mark.parametrize("bad", ["", "main", "main:app extra", "main:app;rm -rf /", "-m:app", "a b:c"])
def test_validate_app_module_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_app_module(bad)


def test_project_framework_defaults_to_django(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    assert project_framework(project) == "django"


# --- server command building ------------------------------------------------


def test_build_server_command_fastapi(tmp_path: Path) -> None:
    project = _make_project(tmp_path, framework="fastapi", appModule="main:app", debug=True)
    command, _env = _build_server_command(project)
    assert command == [
        "python3", "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1", "--port", "8010", "--reload",
    ]


def test_build_server_command_flask(tmp_path: Path) -> None:
    project = _make_project(tmp_path, framework="flask", appModule="app:app", debug=False)
    command, _env = _build_server_command(project)
    assert command == [
        "python3", "-m", "flask", "--app", "app:app", "run",
        "--host", "127.0.0.1", "--port", "8010",
    ]


def test_build_server_command_wsgi_uses_uvicorn_wsgi_interface(tmp_path: Path) -> None:
    project = _make_project(tmp_path, framework="wsgi", appModule="wsgi:application", debug=False)
    command, _env = _build_server_command(project)
    assert command == [
        "python3", "-m", "uvicorn", "wsgi:application",
        "--host", "127.0.0.1", "--port", "8010", "--interface", "wsgi",
    ]


def test_build_server_command_django(tmp_path: Path) -> None:
    (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
    project = _make_project(tmp_path, framework="django", settingsModule="config.settings")
    command, _env = _build_server_command(project)
    assert command == ["python3", str(tmp_path / "manage.py"), "runserver", "127.0.0.1:8010"]


def test_build_server_command_requires_app_module(tmp_path: Path) -> None:
    project = _make_project(tmp_path, framework="fastapi", appModule="")
    with pytest.raises(ValueError):
        _build_server_command(project)


def test_stray_pattern_per_framework(tmp_path: Path) -> None:
    fastapi_project = _make_project(tmp_path, framework="fastapi", appModule="main:app")
    assert "uvicorn" in _stray_process_pattern(fastapi_project, 8010)

    flask_project = _make_project(tmp_path, framework="flask", appModule="app:app")
    assert "flask" in _stray_process_pattern(flask_project, 8010)

    (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
    django_project = _make_project(tmp_path, framework="django")
    assert "runserver" in _stray_process_pattern(django_project, 8010)
