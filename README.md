# DJAMP PRO

DJAMP PRO is a desktop local environment manager for Django projects, inspired by MAMP PRO. It gives you one place to run multiple Django apps with local domains, HTTPS, managed services, and quick project actions.

## Current scope

- Desktop app: Tauri + React (`apps/desktop`)
- Local controller: FastAPI sidecar (`services/controller`)
- Privileged helper (macOS): Rust launch daemon for `/etc/hosts` + 80/443 forwarding (`services/priv-helper`)

## Implemented features

- Add and detect Django projects (`manage.py`, settings module)
- Start / stop / restart per project
- Runtime modes:
  - `uv` (recommended)
  - `conda`
  - `system`
  - `custom interpreter`
- Local domain routing through Caddy
- Local HTTPS certificates signed by DJAMP Root CA
- Managed hosts file block:
  - `# BEGIN DJAMP PRO MANAGED`
  - `# END DJAMP PRO MANAGED`
- macOS helper for MAMP-style behavior:
  - one-time admin install
  - no repeated password prompts for hosts + standard ports
- Postgres/MySQL managed service wiring (when binaries exist)
- DB credentials sourced from project `.env`
- Automatic DB role/database creation for Postgres
- One-click actions:
  - migrate
  - collectstatic
  - shell
  - DB shell
  - open in VS Code
- Logs tab:
  - django
  - proxy
  - database
- Environment tab reads `.env` and masks sensitive values

## Architecture

```text
apps/
  desktop/             # Tauri host + React UI
services/
  controller/          # FastAPI sidecar (orchestration)
  priv-helper/         # macOS privileged helper daemon
bundles/               # optional local binaries (e.g., Caddy)
legacy/                # archived previous implementation
```

## Requirements (macOS)

- Node.js + npm
- Python 3
- Rust toolchain (for Tauri + helper builds)
- OpenSSL
- Optional but recommended:
  - `uv`
  - `psql` / `pg_isready`
  - `mysql` / `mysqladmin`
  - `code` CLI for VS Code

## Dev setup

### 1) Install desktop dependencies

```bash
npm install
npm --prefix apps/desktop install
```

### 2) Install controller dependencies

```bash
python3 -m venv services/controller/.venv
services/controller/.venv/bin/python -m pip install -r services/controller/requirements.txt
```

### 3) Run app

```bash
npm run dev
```

The Tauri app starts the controller automatically on `127.0.0.1:8765`.

## Validation commands

```bash
npm --prefix apps/desktop run typecheck
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
python3 -m compileall -q services/controller/djamp_controller
```

## Domain and HTTPS behavior

- Preferred local domains: `.test` / `.localhost`
- Public-domain override is available, but risky and policy-limited by browser HSTS/preload
- Root CA trust is managed from Settings
- Per-domain certs are generated locally by DJAMP

## Database behavior

DJAMP reads DB values from your project `.env` (for example `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DATABASE_URL`).

- If DB/user does not exist, DJAMP creates them (Postgres flow)
- DJAMP appends a managed `.env` block to keep `DB_HOST`/`DB_PORT` aligned with local managed services
- Environment tab shows `.env` values with masking for sensitive keys
- Use **DB Shell** quick action to open `psql`/`mysql` command shell for the active project

## Security model

- Main app + controller run unprivileged
- Admin rights required only for system operations:
  - trust store updates
  - `/etc/hosts` updates (without helper fallback)
  - binding/forwarding standard ports 80/443
- macOS helper is optional but recommended to avoid repeated prompts
- Restore-on-quit can remove DJAMP host entries and release 80/443

## Troubleshooting

### Start button appears to do nothing

- Open **Logs > Django** and **Logs > Proxy**
- Check the project status API:

```bash
curl -s http://127.0.0.1:8765/api/projects
```

- Verify app server port is listening:

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
```

### Domain does not resolve (`ERR_NAME_NOT_RESOLVED`)

- Sync hosts from Settings
- Verify hosts block contains your domain:

```bash
grep -n "DJAMP PRO MANAGED" /etc/hosts
```

- Flush DNS cache (macOS):

```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

### HTTPS certificate error

- Install Root CA from Settings
- Regenerate cert for the project domain
- Restart project/proxy

### Static files return 404

- Run **Collectstatic**
- Confirm your project serves static under DJAMP override settings
- Verify with:

```bash
curl -k -I https://<domain>/static/<path-to-file>
```

### Helper install stuck / not running

- Re-run install from Settings
- Check helper files:
  - `/Library/PrivilegedHelperTools/com.djamp.pro.helperd`
  - `/Library/LaunchDaemons/com.djamp.pro.helperd.plist`
- Check helper log:

```bash
sudo tail -n 200 /var/log/djamp-pro-helper.log
```

## Build notes

- Dev build:

```bash
npm run dev
```

- Production bundle:

```bash
npm run build
```

Tauri bundling outputs platform installers according to `apps/desktop/src-tauri/tauri.conf.json`.

## Notes for `certs_test`

This repo includes a test project at:

- `test_project/certs_test`

DJAMP now correctly serves static assets for this project through local HTTPS domain routing.
