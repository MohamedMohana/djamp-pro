# DJAMP PRO Build Guide

## Prerequisites

- Node.js 18+
- Rust stable toolchain
- Python 3.9+
- OpenSSL available in `PATH`

## Install dependencies

```bash
cd apps/desktop
npm install

cd ../../services/controller
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Development

Run desktop app (auto-starts controller sidecar):

```bash
cd <path-to-djamp-pro-repo>
npm run dev
```

## Build web assets

```bash
npm --prefix apps/desktop run build
```

## Build desktop bundle

```bash
npm --prefix apps/desktop run tauri:build
```

Output is generated under:

- `apps/desktop/src-tauri/target/release/bundle/`

## Validation checks

```bash
npm --prefix apps/desktop run typecheck
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo check --manifest-path services/priv-helper/Cargo.toml
python3 -m compileall -q services/controller/djamp_controller
```

## Notes

- Full release signing/notarization is not automated yet.
- Production installers should include vetted bundled binaries for Caddy/Postgres/MySQL/Redis.
