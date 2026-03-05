# DJAMP PRO

DJAMP PRO is a desktop local development environment manager for Django projects, inspired by the “it just works” workflow of MAMP PRO.

It gives you one control panel to run multiple Django apps with custom domains, local HTTPS, managed runtime modes (`uv`, `conda`, system/custom Python), database wiring from `.env`, project actions, and diagnostics.

## Product Status

- Platform focus: macOS (Windows later, Linux optional)
- UI host: Tauri + React
- Controller: FastAPI sidecar
- Reverse proxy: Caddy (managed config + reload)
- Database focus: PostgreSQL local dev workflow
- Current maturity: active MVP+ hardening

## Core Capabilities

- Add existing Django projects from disk
- Auto-detect `manage.py` and settings modules
- Start / stop / restart per project
- Manage multiple projects concurrently (virtual-host style)
- Custom domains + aliases per project
- Local HTTPS certificates for project domains
- Caddy-managed domain routing to each Django runtime port
- Runtime modes:
  - `uv` (recommended)
  - `conda`
  - `system`
  - custom interpreter path
- Database behavior aligned with project `.env`
  - reads DB config from `.env`
  - can create missing PostgreSQL role/database for project
- One-click developer actions
  - migrate
  - collectstatic
  - shell
  - DB shell
  - open in VS Code
- Logs UI
  - Django logs
  - proxy logs
  - database logs
- Environment UI
  - reads and shows `.env` keys with masking for sensitive values

## What Makes It MAMP-Style (for Django)

- Single desktop app to manage local hosts/domains/certs/runtime
- Domain-first workflow (`https://myapp.test`) instead of only localhost:port
- Standard port support model (80/443) with helper-based workflow on macOS
- DB web admin exposed on project domain path:
  - `/phpmyadmin/`
  - `/phpMyAdmin/`
  - `/phpMyAdmin5/`

## Repository Layout

```text
apps/
  desktop/                  # Tauri host + React frontend
services/
  controller/               # FastAPI local sidecar orchestration
  priv-helper/              # macOS privileged helper daemon (Rust)
bundles/                    # Optional bundled binaries (e.g. Caddy)
docs/
  ARCHITECTURE.md
  BUILD.md
  FAQs.md
  TROUBLESHOOTING.md
legacy/                     # Archived old implementation
```

## Architecture Overview

```text
┌───────────────────────────── DJAMP PRO Desktop (Tauri + React) ──────────────────────────────┐
│                                                                                                 │
│  UI (projects/settings/logs/environment)                                                        │
│        │                                                                                        │
│        └── Tauri invoke() commands                                                              │
│                                                                                                 │
└────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                             │
                                             ▼
                              FastAPI Sidecar Controller (127.0.0.1:8765)
                              - Project registry
                              - Runtime orchestration
                              - Caddy config generation/reload
                              - Cert + CA operations
                              - DB provisioning/query helper
                                             │
                        ┌────────────────────┼────────────────────┐
                        ▼                    ▼                    ▼
                   Caddy Proxy           Django Processes       Local DB services
               (domain + TLS routing)     (per project)         (primarily Postgres)
                        │
                        ▼
              Browser on custom local domains
```

## Security Model

DJAMP PRO is designed for least privilege:

- Main app + sidecar run unprivileged
- Privileged operations are isolated to specific flows:
  - trusted certificate install/update
  - `/etc/hosts` modifications
  - standard port forwarding (80/443) on macOS helper path
- Managed hosts entries are scoped between:
  - `# BEGIN DJAMP PRO MANAGED`
  - `# END DJAMP PRO MANAGED`

Important:

- DJAMP PRO is for local development only.
- Do not use it as a public production hosting stack.

## Requirements (macOS)

Required:

- Node.js 18+
- npm
- Python 3.10+
- Rust toolchain (for Tauri/native pieces)

Recommended:

- `uv`
- `psql` + `pg_isready`
- `mysql` + `mysqladmin` (if MySQL workflow needed)
- `code` CLI for VS Code integration

## Quick Start (Development)

### 1) Install root dependencies

```bash
npm install
npm --prefix apps/desktop install
```

### 2) Prepare sidecar virtualenv

```bash
python3 -m venv services/controller/.venv
services/controller/.venv/bin/python -m pip install -r services/controller/requirements.txt
```

### 3) Run desktop app

```bash
npm run dev
```

The Tauri app starts the sidecar automatically (`127.0.0.1:8765`) and watches desktop/frontend changes.

## First Project Flow

1. Click `Add Project`
2. Select project folder (Django root)
3. Detect `manage.py` + settings module
4. Set domain (prefer `.test`)
5. Pick runtime mode (`uv`, `conda`, etc.)
6. Confirm database type
7. Create project entry
8. Click `Start`

When running, open:

- app root: `https://<your-domain>` (or fallback `:8443` when standard ports disabled)
- DB admin: `https://<your-domain>/phpMyAdmin5/`

## Runtime Modes

- `uv`
  - best default for isolated Python package management
- `conda`
  - for existing conda-based teams/projects
- `system`
  - uses system Python in PATH
- `custom`
  - direct explicit interpreter path

## Domains & HTTPS

Domain handling:

- Per-project primary domain + aliases
- Hosts sync through DJAMP PRO managed block
- Caddy routes domain -> Django port

HTTPS handling:

- Local root CA managed by DJAMP PRO
- Per-domain certificates generated locally
- Caddy serves TLS cert/key per project domain

Notes:

- Prefer local dev TLDs (`.test`)
- Public domains can hit HSTS/preload/policy limits
- Browsers may cache TLS state aggressively; regenerate cert and restart if needed

## Standard Ports (80/443)

- DJAMP PRO proxy defaults to internal ports (8080/8443)
- On macOS, helper path can enable standard port behavior (MAMP-style)
- If standard ports are not active, DJAMP PRO opens fallback URL with explicit proxy port

## Database Behavior

DJAMP PRO reads DB credentials from project `.env` when available:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DATABASE_URL`

For PostgreSQL workflow:

- ensures managed local Postgres service routing
- can create missing role/database
- updates managed `.env` block for local host/port alignment

DB admin URL behavior:

- path-style, domain-based routing
  - `/phpmyadmin/`
  - `/phpMyAdmin/`
  - `/phpMyAdmin5/`
- requires project to be running

## Project Actions

Per-project quick actions:

- `Migrate`
- `Collectstatic`
- `Shell`
- `DB Shell`
- `VS Code`

Deletion safety:

- “Delete Project” now opens a destructive-action modal
- requires typing project name exactly before deletion
- prevents accidental one-click deletion

## Logs & Diagnostics

UI log sources:

- Django
- Proxy (Caddy)
- Database

Useful checks:

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/api/projects
```

macOS port checks:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

## Build & Packaging

### Development checks

```bash
npm --prefix apps/desktop run typecheck
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
services/controller/.venv/bin/python -m py_compile services/controller/djamp_controller/main.py
```

### Desktop build

```bash
npm --prefix apps/desktop run build
npm --prefix apps/desktop run tauri:build
```

Installer outputs are produced under Tauri target bundle directories.

## Data Locations

App data root:

- macOS: `~/Library/Application Support/DJAMP PRO/`
- Windows: `%APPDATA%/DJAMP PRO/`

Key files/folders:

- registry: `registry.json`
- certs: `certs/`
- Caddy config: `caddy/Caddyfile`
- logs:
  - `logs/django/`
  - `logs/proxy/`
  - `logs/database/`

## Troubleshooting

### Domain resolves but app does not load

- Ensure project status is `running`
- Check Caddy logs in Logs tab
- Check Django logs for startup errors

### `ERR_NAME_NOT_RESOLVED`

- Re-sync hosts from Settings
- Verify DJAMP PRO managed block in `/etc/hosts`
- Flush DNS cache on macOS:

```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

### TLS warnings / cert issues

- Confirm CA install from Settings
- Regenerate project cert
- Restart project
- Hard refresh browser (`Cmd+Shift+R`)

### DB Admin opens while project stopped

- Fixed in current branch: DB admin now requires running project
- If behavior seems stale, restart app and hard refresh browser

### Helper install appears stuck

Check:

- `/Library/PrivilegedHelperTools/com.djamp.pro.helperd`
- `/Library/LaunchDaemons/com.djamp.pro.helperd.plist`

Logs:

```bash
sudo tail -n 200 /var/log/djamp-pro-helper.log
```

## Known Limitations (Current)

- Windows parity is not yet complete
- DB admin is PostgreSQL-focused in current workflow
- Full phpMyAdmin feature parity is not a goal for PostgreSQL mode
- Production-grade installer signing/notarization pipeline is still pending

## Release Strategy

- Semantic tags (`vMAJOR.MINOR.PATCH`)
- Each release should include:
  - UI/UX changes
  - runtime/controller changes
  - migration or compatibility notes
  - known issues + workaround summary

## Documentation

Additional docs:

- `docs/ARCHITECTURE.md`
- `docs/BUILD.md`
- `docs/FAQs.md`
- `docs/TROUBLESHOOTING.md`
- `docs/INSTALL_MACOS.md`
- `docs/QUICKSTART_5_MIN.md`
- `docs/UNINSTALL.md`

## Community

- Contributing guide: `.github/CONTRIBUTING.md`
- Security policy: `.github/SECURITY.md`
- Support policy: `.github/SUPPORT.md`
- Code of conduct: `.github/CODE_OF_CONDUCT.md`

## License

MIT (see `LICENSE`).
