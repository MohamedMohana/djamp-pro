import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from djamp_controller.main import health, root


def test_health_endpoint_contract() -> None:
    assert asyncio.run(health()) == {"status": "healthy"}


def test_root_endpoint_contract() -> None:
    assert asyncio.run(root()) == {"name": "DJAMP PRO Controller", "status": "running"}
