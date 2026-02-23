# DJAMP PRO Architecture

## Overview

DJAMP PRO is built as a desktop host + local sidecar pattern:

```text
React UI (Tauri window)
        |
        | invoke()
        v
Rust Tauri Host (apps/desktop/src-tauri)
        |
        | HTTP (localhost)
        v
Python Controller Sidecar (services/controller)
        |
        +--> Django process supervision
        +--> Domain + cert orchestration
        +--> Caddy config generation/reload
        +--> DB service start/stop hooks
        +--> Registry + logs
```

## Components

### 1) Desktop UI (`apps/desktop/src`)

- Project list/details and action buttons
- Add project flow (detects Django path)
- Settings and utility actions
- Calls Tauri commands from `src/services/api.ts`

### 2) Tauri host (`apps/desktop/src-tauri`)

- Starts controller sidecar automatically
- Exposes all app commands (`commands.rs`)
- Proxies UI calls to sidecar HTTP API
- OS launch helpers (browser/editor/shell)

### 3) Controller sidecar (`services/controller`)

- FastAPI API implementation in `djamp_controller/main.py`
- Persists registry in app data directory
- Manages project runtime adapters:
  - `uv`
  - `conda`
  - `system/custom`
- Manages cert creation + root CA status/install calls
- Generates managed hosts mappings and Caddy config
- Exposes log retrieval and utility endpoints

### 4) Privileged helper (`services/priv-helper`)

- Rust CLI for managed hosts-block writes/clear
- Designed to be invoked under elevation when required

## Data model

Registry fields are persisted in JSON and include:

- project identity/path
- Django settings module
- domains + aliases + domain mode
- runtime mode/interpreter metadata
- HTTPS/certificate metadata
- database/cache configuration
- environment variable map
- runtime status

## Security model

- Default execution is least-privilege.
- Hosts/trust-store operations require elevation on macOS/Windows.
- Domain mappings are constrained to managed block markers.
- Local certificates are generated from a local root CA only.
- Public-domain override support is local-only and can still be impacted by browser policy/HSTS.

## Runtime directories

DJAMP PRO stores runtime data under OS app-data conventions:

- macOS: `~/Library/Application Support/DJAMP PRO/`
- Windows: `%APPDATA%/DJAMP PRO/`

Typical contents:

- `registry.json`
- `logs/`
- `certs/`
- `services/`
- `caddy/`

