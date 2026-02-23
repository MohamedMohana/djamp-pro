"""
Django management module for DJANGOForge
Handles Django server operations and management commands
"""

import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List


class DjangoManager:
    """Manages Django server operations"""

    def __init__(self, project_path: Path, venv_path: Path, settings_module: str):
        self.project_path = project_path
        self.venv_path = venv_path
        self.settings_module = settings_module
        self.manage_py = self._find_manage_py()
        self.process: Optional[asyncio.subprocess.Process] = None

    def _find_manage_py(self) -> Path:
        """Find manage.py in project directory"""
        candidates = list(self.project_path.rglob("manage.py"))
        if not candidates:
            raise FileNotFoundError(f"manage.py not found in {self.project_path}")
        return candidates[0]

    def _python_executable(self) -> Path:
        """Get Python executable from venv"""
        if self.venv_path.exists():
            if self.venv_path.is_dir():
                python_path = self.venv_path / "bin" / "python"
            else:
                python_path = self.venv_path / "bin" / "python"

            if python_path.exists():
                return python_path

        return Path("python3")

    def run_command(self, command: str, args: Optional[List[str]] = None) -> dict:
        """Run Django management command"""
        cmd = [str(self._python_executable()), str(self.manage_py), command]
        if args:
            cmd.extend(args)

        env = {"DJANGO_SETTINGS_MODULE": self.settings_module}

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                env={**subprocess.os.environ, **env},
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def migrate(self, args: Optional[List[str]] = None) -> dict:
        """Run Django migrations"""
        return self.run_command("migrate", args)

    def collectstatic(self, args: Optional[List[str]] = None) -> dict:
        """Collect static files"""
        return self.run_command("collectstatic", args)

    def createsuperuser(self, username: str, email: str, password: str) -> dict:
        """Create superuser"""
        return self.run_command(
            "createsuperuser", ["--noinput", f"--username={username}", f"--email={email}"]
        )

    def run_tests(self, args: Optional[List[str]] = None) -> dict:
        """Run Django tests"""
        return self.run_command("test", args)

    async def start_dev_server(self, port: int) -> None:
        """Start Django development server"""
        cmd = [
            str(self._python_executable()),
            str(self.manage_py),
            "runserver",
            f"127.0.0.1:{port}",
        ]

        env = {"DJANGO_SETTINGS_MODULE": self.settings_module}

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(self.project_path),
            env={**asyncio.os.environ, **env},
        )

    async def stop(self) -> None:
        """Stop Django server"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None

    async def is_running(self) -> bool:
        """Check if Django server is running"""
        if not self.process:
            return False
        return self.process.returncode is None


def detect_django_project(path: str) -> dict:
    """Detect if a directory is a Django project"""
    project_path = Path(path)

    if not project_path.exists():
        return {"found": False}

    manage_py_candidates = list(project_path.rglob("manage.py"))
    if not manage_py_candidates:
        return {"found": False}

    manage_py_path = manage_py_candidates[0]
    settings_modules = []

    # Search for settings files
    for entry in project_path.iterdir():
        if entry.is_dir():
            settings_file = entry / "settings.py"
            if settings_file.exists():
                settings_modules.append(f"{entry.name}.settings")

    # Also check for settings.py in root
    settings_file = project_path / "settings.py"
    if settings_file.exists():
        settings_modules.append(f"{project_path.name}.settings")

    return {"found": True, "managePyPath": str(manage_py_path), "settingsModules": settings_modules}
