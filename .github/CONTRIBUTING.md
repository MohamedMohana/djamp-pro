# Contributing to DJAMP PRO

Thanks for helping improve DJAMP PRO.

## Scope

Current primary scope:
- macOS local Django development workflow
- Tauri desktop app (`apps/desktop`)
- Controller service (`services/controller`)
- macOS helper (`services/priv-helper`)

## Prerequisites

- Node.js 18+
- npm
- Python 3.10+
- Rust stable toolchain

## Local Setup

```bash
npm install
npm --prefix apps/desktop install
python3 -m venv services/controller/.venv
services/controller/.venv/bin/python -m pip install -r services/controller/requirements.txt
```

## Run in Development

```bash
npm run dev
```

## Validation Before PR

```bash
npm --prefix apps/desktop run lint
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop run build
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo check --manifest-path services/priv-helper/Cargo.toml
services/controller/.venv/bin/python -m pytest services/controller/tests -q
```

## Pull Request Rules

- Keep PRs focused and small.
- Include clear reproduction or rationale.
- Update docs when behavior changes.
- Do not include unrelated refactors.

## Good First Contributions

Look for issues labeled `good first issue` and `help wanted`.
