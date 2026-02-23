"""
Database management module for DJANGOForge
Handles PostgreSQL, MySQL, and Redis operations
"""

import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations for projects"""

    def __init__(self, db_type: str, db_name: str, db_user: str, db_password: str, port: int):
        self.db_type = db_type.lower()
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.port = port
        self.process: Optional[asyncio.subprocess.Process] = None

    def _get_binary_path(self) -> Path:
        """Get path to database binary"""
        djamp_home = Path.home() / ".djamp"

        if self.db_type == "postgres":
            binary_dirs = [djamp_home / "bundles" / "postgres", "/usr/local/bin", "/usr/bin"]
            for dir_path in binary_dirs:
                if dir_path.exists():
                    for binary in ["postgres", "pg_ctl"]:
                        binary_path = dir_path / binary
                        if binary_path.exists() and binary_path.is_file():
                            return binary_path

        elif self.db_type == "mysql":
            binary_dirs = [djamp_home / "bundles" / "mysql", "/usr/local/bin", "/usr/bin"]
            for dir_path in binary_dirs:
                if dir_path.exists():
                    for binary in ["mysqld", "mysql.server"]:
                        binary_path = dir_path / binary
                        if binary_path.exists() and binary_path.is_file():
                            return binary_path

        elif self.db_type == "redis":
            binary_dirs = [djamp_home / "bundles" / "redis", "/usr/local/bin", "/usr/bin"]
            for dir_path in binary_dirs:
                if dir_path.exists():
                    for binary in ["redis-server"]:
                        binary_path = dir_path / binary
                        if binary_path.exists() and binary_path.is_file():
                            return binary_path

        raise FileNotFoundError(f"Database binary not found for {self.db_type}")

    def _get_data_dir(self) -> Path:
        """Get data directory for database"""
        djamp_home = Path.home() / ".djamp" / "data"
        data_dir = djamp_home / self.db_type / self.db_name
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    async def start(self) -> Dict[str, any]:
        """Start database server"""
        try:
            if self.db_type == "postgres":
                return await self._start_postgres()
            elif self.db_type == "mysql":
                return await self._start_mysql()
            elif self.db_type == "redis":
                return await self._start_redis()
            else:
                return {"success": False, "error": f"Unsupported database type: {self.db_type}"}
        except Exception as e:
            logger.error(f"Failed to start {self.db_type}: {e}")
            return {"success": False, "error": str(e)}

    async def _start_postgres(self) -> Dict[str, any]:
        """Start PostgreSQL server"""
        data_dir = self._get_data_dir()

        # Initialize database if needed
        initdb_path = self._get_binary_path().parent / "initdb"
        if not (data_dir / "PG_VERSION").exists():
            await asyncio.create_subprocess_exec(
                str(initdb_path),
                "-D",
                str(data_dir),
                "-U",
                self.db_user,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        # Start PostgreSQL
        binary = self._get_binary_path()
        self.process = await asyncio.create_subprocess_exec(
            str(binary),
            "-D",
            str(data_dir),
            "-p",
            str(self.port),
            "-h",
            "127.0.0.1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        return {"success": True}

    async def _start_mysql(self) -> Dict[str, any]:
        """Start MySQL server"""
        data_dir = self._get_data_dir()

        # MySQL would use mysqld
        binary = self._get_binary_path()
        self.process = await asyncio.create_subprocess_exec(
            str(binary),
            "--datadir",
            str(data_dir),
            "--port",
            str(self.port),
            "--bind-address=127.0.0.1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        return {"success": True}

    async def _start_redis(self) -> Dict[str, any]:
        """Start Redis server"""
        config_file = self._get_data_dir() / "redis.conf"

        # Create basic config
        config_content = f"""
port {self.port}
bind 127.0.0.1
dir {self._get_data_dir()}
"""
        config_file.write_text(config_content)

        binary = self._get_binary_path()
        self.process = await asyncio.create_subprocess_exec(
            str(binary), config_file, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        return {"success": True}

    async def stop(self) -> Dict[str, any]:
        """Stop database server"""
        try:
            if self.process:
                self.process.terminate()
                await self.process.wait()
                self.process = None
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to stop {self.db_type}: {e}")
            return {"success": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, any]:
        """Test database connection"""
        try:
            if self.db_type == "postgres":
                return await self._test_postgres()
            elif self.db_type == "mysql":
                return await self._test_mysql()
            elif self.db_type == "redis":
                return await self._test_redis()
            else:
                return {"success": False, "error": "Unsupported database type"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_postgres(self) -> Dict[str, any]:
        """Test PostgreSQL connection"""
        psql_path = self._get_binary_path().parent / "psql"

        try:
            process = await asyncio.create_subprocess_exec(
                str(psql_path),
                f"postgresql://{self.db_user}:{self.db_password}@127.0.0.1:{self.port}/{self.db_name}",
                "-c",
                "SELECT 1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {"success": True, "output": stdout.decode()}
            else:
                return {"success": False, "error": stderr.decode()}
        except FileNotFoundError:
            return {"success": False, "error": "psql not found"}

    async def _test_mysql(self) -> Dict[str, any]:
        """Test MySQL connection"""
        mysql_path = self._get_binary_path().parent / "mysql"

        try:
            process = await asyncio.create_subprocess_exec(
                str(mysql_path),
                f"-u{self.db_user}",
                f"-p{self.db_password}",
                f"-P{self.port}",
                f"-h127.0.0.1",
                f"-e",
                "SELECT 1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {"success": True, "output": stdout.decode()}
            else:
                return {"success": False, "error": stderr.decode()}
        except FileNotFoundError:
            return {"success": False, "error": "mysql client not found"}

    async def _test_redis(self) -> Dict[str, any]:
        """Test Redis connection"""
        redis_cli_path = self._get_binary_path().parent / "redis-cli"

        try:
            process = await asyncio.create_subprocess_exec(
                str(redis_cli_path),
                "-p",
                str(self.port),
                "ping",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and b"PONG" in stdout:
                return {"success": True, "output": stdout.decode()}
            else:
                return {"success": False, "error": stderr.decode()}
        except FileNotFoundError:
            return {"success": False, "error": "redis-cli not found"}
