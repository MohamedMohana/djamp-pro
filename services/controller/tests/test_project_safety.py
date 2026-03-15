import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from djamp_controller.main import (
    AddProjectPayload,
    AppSettings,
    Project,
    _enforce_domain_policy,
    _sanitize_hostname,
    add_project,
    load_registry_sync,
    patch_project,
)


def _make_project(*, domain: str, domain_mode: str = "local_only") -> Project:
    return Project(
        id="f14ce00d-3fd8-47ae-b76c-5ab5c4acb522",
        name="Demo",
        path=str(Path.home()),
        settingsModule="config.settings",
        domain=domain,
        domainMode=domain_mode,
        createdAt="2026-03-15T00:00:00+00:00",
    )


@pytest.fixture
def isolated_djamp_home(monkeypatch: pytest.MonkeyPatch) -> Path:
    sandbox_root = Path(tempfile.mkdtemp(prefix="djamp-controller-tests-", dir=str(Path.home())))
    monkeypatch.setenv("DJAMP_HOME", str(sandbox_root / ".djamp-home"))
    monkeypatch.setenv("DJAMP_SKIP_HOSTS", "1")
    try:
        yield sandbox_root
    finally:
        shutil.rmtree(sandbox_root, ignore_errors=True)


def test_sanitize_hostname_normalizes_urls() -> None:
    assert _sanitize_hostname(" HTTPS://Example.TEST ") == "example.test"


def test_enforce_domain_policy_rejects_public_domains_by_default() -> None:
    project = _make_project(domain="example.com")

    with pytest.raises(RuntimeError, match="real/public domain"):
        _enforce_domain_policy(project, AppSettings())


def test_enforce_domain_policy_allows_public_override_when_enabled() -> None:
    project = _make_project(domain="example.com", domain_mode="public_override")

    _enforce_domain_policy(project, AppSettings(anyDomainOverrideEnabled=True))


def test_add_project_normalizes_domains_and_allowed_hosts(isolated_djamp_home: Path) -> None:
    project_dir = isolated_djamp_home / "Demo Project"
    project_dir.mkdir()

    created = asyncio.run(
        add_project(
            AddProjectPayload(
                project={
                    "name": "Demo Project",
                    "path": str(project_dir),
                    "settingsModule": "config.settings",
                    "domain": "HTTPS://Example.TEST",
                    "aliases": ["Api.Example.TEST"],
                }
            )
        )
    )

    assert created.domain == "example.test"
    assert created.aliases == ["api.example.test"]
    assert set(created.allowedHosts) == {
        "127.0.0.1",
        "api.example.test",
        "example.test",
        "localhost",
        "www.example.test",
    }

    stored = load_registry_sync().projects[0]
    assert stored.domain == "example.test"
    assert stored.aliases == ["api.example.test"]


def test_patch_project_recomputes_allowed_hosts_from_normalized_domains(
    isolated_djamp_home: Path,
) -> None:
    project_dir = isolated_djamp_home / "Patched Project"
    project_dir.mkdir()

    created = asyncio.run(
        add_project(
            AddProjectPayload(
                project={
                    "name": "Patched Project",
                    "path": str(project_dir),
                    "settingsModule": "config.settings",
                    "domain": "initial.test",
                }
            )
        )
    )

    updated = asyncio.run(
        patch_project(
            created.id,
            {
                "domain": "HTTPS://Renamed.TEST",
                "aliases": ["HTTPS://Api.Renamed.TEST"],
            },
        )
    )

    assert updated.domain == "renamed.test"
    assert updated.aliases == ["api.renamed.test"]
    assert set(updated.allowedHosts) == {
        "127.0.0.1",
        "api.renamed.test",
        "localhost",
        "renamed.test",
        "www.renamed.test",
    }


def test_add_project_rejects_public_domains_without_override(isolated_djamp_home: Path) -> None:
    project_dir = isolated_djamp_home / "Public Project"
    project_dir.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            add_project(
                AddProjectPayload(
                    project={
                        "name": "Public Project",
                        "path": str(project_dir),
                        "settingsModule": "config.settings",
                        "domain": "example.com",
                    }
                )
            )
        )
    assert "real/public domain" in str(exc_info.value.detail)
