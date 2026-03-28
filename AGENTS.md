# DJAMP PRO Agent Guide

## Repository shape

- `apps/desktop`: Tauri desktop app with a React frontend.
- `apps/desktop/src-tauri`: Rust host that bridges the UI to the controller sidecar.
- `services/controller`: FastAPI sidecar that manages Django projects, local proxying, certificates, domains, and service processes.
- `services/priv-helper`: Rust helper for privileged local operations.

## Review priorities

Focus reviews on correctness, regressions, and security before style.

- Treat `services/controller/djamp_controller/main.py` as the highest-risk file.
- Pay close attention to shell command construction, subprocess use, path handling, temp files, network downloads, and filesystem writes.
- In `apps/desktop/src-tauri`, verify that Tauri commands preserve controller API contracts and do not weaken OS-level safety.
- In `services/priv-helper`, flag any privilege boundary change, unsafe file write, or host/port mutation risk.
- In `apps/desktop/src`, verify that UI actions match controller responses and preserve the domain/HTTPS/project lifecycle flows.
- For dependency PRs, prefer small patch updates. Be skeptical of `0.x` minor bumps and anything that changes ESLint, Tauri, React, or build tooling.

## Required validation

When a change touches the desktop app, run:

- `npm --prefix apps/desktop run lint`
- `npm --prefix apps/desktop run typecheck`
- `npm --prefix apps/desktop run build`

When a change touches Rust code, run:

- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- `cargo check --manifest-path services/priv-helper/Cargo.toml`

When a change touches the controller, run:

- `services/controller/.venv/bin/python -m ruff check services/controller`
- `services/controller/.venv/bin/python -m pytest services/controller/tests -q`

For dependency and security changes, also run:

- `npm audit --prefix apps/desktop`

## Reviewer notes

- This is a solo-maintained repo with required CI checks on `main`.
- Prioritize findings with concrete file references and behavior impact.
- Call out missing tests whenever a change affects controller process management, certificate generation, proxy behavior, or dependency/runtime bootstrapping.
