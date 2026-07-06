from pathlib import Path
import os
import signal
import sys
import threading
import time

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from djamp_controller.main import app  # noqa: E402


def _start_parent_watchdog() -> None:
    """Exit when the desktop app that spawned this controller goes away.

    The desktop app spawns us with a pipe on stdin and keeps the write end for
    its whole lifetime. When the app dies -- Cmd+Q, SIGTERM, SIGKILL, crash,
    or a `tauri dev` rebuild -- the OS closes the pipe and our read returns
    EOF, so we shut down instead of lingering on the controller port with
    stale code. Only active when the spawner opts in via the environment, so
    running this script by hand from a terminal is unaffected.
    """
    if os.environ.get("DJAMP_PARENT_WATCHDOG") != "1":
        return

    def _watch() -> None:
        try:
            while sys.stdin.buffer.read(4096):
                pass
        except Exception:
            pass
        try:
            # Route through uvicorn's SIGTERM handler so lifespan shutdown
            # (stop projects, release standard ports) still runs.
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os._exit(1)
        time.sleep(10)
        os._exit(1)

    threading.Thread(target=_watch, name="djamp-parent-watchdog", daemon=True).start()


if __name__ == "__main__":
    import uvicorn

    _start_parent_watchdog()
    uvicorn.run(app, host="127.0.0.1", port=8765, reload=False, log_level="info")
