#!/usr/bin/env python3
import json
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: generate-caddy-config.py <registry.json> <output-caddyfile>")
    raise SystemExit(1)

registry = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output = Path(sys.argv[2])

settings = registry.get("settings", {})
projects = registry.get("projects", [])

lines = [
    "# DJAMP PRO generated Caddyfile",
    "{",
    f"  http_port {settings.get('proxyHttpPort', 80)}",
    f"  https_port {settings.get('proxyPort', 443)}",
    "}",
    "",
]

for project in projects:
    domains = [project.get("domain", "")] + project.get("aliases", [])
    domains = [d for d in domains if d]
    if not domains:
        continue

    lines.append(", ".join(domains) + " {")
    cert = project.get("certificatePath") or ""
    if project.get("httpsEnabled") and cert:
        lines.append(f"  tls {cert} {cert.replace('.crt', '.key')}")
    lines.append(f"  reverse_proxy 127.0.0.1:{project.get('port', 8000)}")
    lines.append("}")
    lines.append("")

output.parent.mkdir(parents=True, exist_ok=True)
output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(f"Wrote {output}")
