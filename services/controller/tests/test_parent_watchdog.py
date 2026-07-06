import os
import subprocess
import sys
from pathlib import Path

CONTROLLER_DIR = Path(__file__).resolve().parents[1]

CHILD_SNIPPET = """
import sys, time
sys.path.insert(0, {controller_dir!r})
import run_service

run_service._start_parent_watchdog()
print("ready", flush=True)
time.sleep(30)
"""


def _spawn_child(env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", CHILD_SNIPPET.format(controller_dir=str(CONTROLLER_DIR))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
    )


def test_watchdog_exits_on_stdin_eof() -> None:
    env = dict(os.environ, DJAMP_PARENT_WATCHDOG="1")
    child = _spawn_child(env)
    try:
        assert child.stdout.readline().strip() == b"ready"
        child.stdin.close()  # what the OS does when the desktop app dies
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    assert child.returncode != 0  # exited via self-SIGTERM, not the sleep(30)


def test_watchdog_disabled_without_opt_in() -> None:
    env = dict(os.environ)
    env.pop("DJAMP_PARENT_WATCHDOG", None)
    child = _spawn_child(env)
    try:
        assert child.stdout.readline().strip() == b"ready"
        child.stdin.close()
        try:
            child.wait(timeout=2)
            survived = False
        except subprocess.TimeoutExpired:
            survived = True
        assert survived, "watchdog must not run when the spawner did not opt in"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
