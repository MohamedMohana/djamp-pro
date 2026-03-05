## Summary

Describe what changed and why.

## Type of Change

- [ ] Bug fix
- [ ] Feature
- [ ] Docs update
- [ ] Refactor
- [ ] CI/Build

## Validation

- [ ] `npm --prefix apps/desktop run lint`
- [ ] `npm --prefix apps/desktop run typecheck`
- [ ] `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- [ ] `cargo check --manifest-path services/priv-helper/Cargo.toml`
- [ ] `services/controller/.venv/bin/python -m pytest services/controller/tests -q`

## Checklist

- [ ] Docs updated if needed
- [ ] No unrelated changes
- [ ] Screenshots/logs attached when relevant
