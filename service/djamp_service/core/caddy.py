"""
Caddy configuration generator for DJANGOForge
Generates Caddyfile for reverse proxy routing
"""

import asyncio
from pathlib import Path
from typing import List, Dict
from jinja2 import Template


CADDYFILE_TEMPLATE = Template("""
# DJANGOForge - Auto-generated Caddy configuration
# Do not edit manually - it will be overwritten

{% for site in sites %}
{{ site.domain }} {
    reverse_proxy {{ site.host }}:{{ site.port }}
    
    {% if site.https_enabled and site.certificate_path and site.key_path %}
    tls {{ site.certificate_path }} {{ site.key_path }}
    {% endif %}
    
    {% if site.static_path %}
    handle /static/* {
        root * {{ site.project_path }}/{{ site.static_path }}
        file_server
    }
    {% endif %}
    
    {% if site.media_path %}
    handle /media/* {
        root * {{ site.project_path }}/{{ site.media_path }}
        file_server
    }
    {% endif %}
}

{% for alias in site.aliases %}
{{ alias }} {
    reverse_proxy {{ site.host }}:{{ site.port }}
    
    {% if site.https_enabled and site.certificate_path and site.key_path %}
    tls {{ site.certificate_path }} {{ site.key_path }}
    {% endif %}
}

{% endfor %}
{% endfor %}
""")


class CaddyManager:
    """Manages Caddy reverse proxy configuration"""

    def __init__(self, caddy_path: Path, caddyfile_path: Path):
        self.caddy_path = caddy_path
        self.caddyfile_path = caddyfile_path

    def generate_config(self, projects: List[Dict]) -> None:
        """Generate Caddyfile from project configurations"""
        sites = []

        for project in projects:
            if not project.get("enabled", True):
                continue

            site = {
                "domain": project["domain"],
                "port": project["port"],
                "host": "127.0.0.1",
                "aliases": project.get("aliases", []),
                "https_enabled": project.get("https_enabled", False),
                "certificate_path": project.get("certificate_path") or "",
                "key_path": (project.get("certificate_path") or "").replace(".crt", ".key"),
                "project_path": project["path"],
                "static_path": project.get("static_path", "static"),
                "media_path": project.get("media_path", "media"),
            }
            sites.append(site)

        # Render template
        config = CADDYFILE_TEMPLATE.render(sites=sites)

        # Write Caddyfile
        self.caddyfile_path.parent.mkdir(parents=True, exist_ok=True)
        self.caddyfile_path.write_text(config or "")

    async def reload(self) -> None:
        """Reload Caddy configuration"""
        import subprocess

        try:
            # Try graceful reload first (SIGUSR1 on Unix)
            process = await asyncio.create_subprocess_exec(
                "pkill",
                "-USR1",
                "caddy",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()

            if process.returncode == 0:
                return
        except Exception:
            pass

        # Fallback: full restart
        await self.restart()

    async def start(self) -> None:
        """Start Caddy server"""
        self.caddyfile_path.parent.mkdir(parents=True, exist_ok=True)

        self.process = await asyncio.create_subprocess_exec(
            str(self.caddy_path),
            "run",
            "--config",
            str(self.caddyfile_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def stop(self) -> None:
        """Stop Caddy server"""
        import subprocess

        process = await asyncio.create_subprocess_exec(
            "pkill", "caddy", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.wait()

    async def restart(self) -> None:
        """Restart Caddy server"""
        await self.stop()
        await asyncio.sleep(1)
        await self.start()
