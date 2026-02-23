# DJAMP PRO Troubleshooting

## 1) App opens but project actions fail

- Check sidecar health:

```bash
curl -sS http://127.0.0.1:8765/health
```

- If unhealthy, ensure controller deps are installed in:
  - `services/controller/.venv`

## 2) "Permission denied" updating hosts file

Expected when app is not elevated.

- macOS hosts path: `/etc/hosts`
- Windows hosts path: `C:\Windows\System32\drivers\etc\hosts`

Use elevated run for host/trust operations.

## 3) HTTPS cert trusted issues

- Ensure root CA exists under app data cert directory.
- Re-run CA install action from settings.
- Restart browser after trust changes.
- Public-domain overrides may still fail due HSTS/policy.

## 4) Caddy start/reload errors

- Ensure `caddy` exists in `PATH` or bundled binary location.
- Confirm ports are available (80/443 by default).
- Check proxy logs under app data `logs/proxy`.

## 5) Database service won’t start

- Ensure binaries exist in `PATH`:
  - `postgres`
  - `mysqld`
  - `redis-server`
- Review logs under app data `logs/database`.

## 6) Runtime mode issues

- `uv` mode: install `uv` and ensure project venv can be created.
- `conda` mode: ensure `conda` is in `PATH` and env name is valid.
- `system/custom` mode: verify interpreter path/command manually.

## 7) VS Code launch fails

- Ensure `code` command is installed in shell PATH.
- UI fallback opens project folder with OS default opener.

## 8) Validation quick checks

```bash
npm --prefix apps/desktop run typecheck
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
python3 -m compileall -q services/controller/djamp_controller
```
