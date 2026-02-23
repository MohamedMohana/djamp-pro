# DJAMP PRO FAQ

## Is DJAMP PRO Docker-based?

MVP is non-Docker by design. It manages local runtimes/services directly.

## Can I run multiple Django projects at once?

Yes. Each project has its own app port and domain mapping.

## Does DJAMP PRO support conda projects?

Yes. Runtime adapters support `uv` default plus `conda` and system/custom interpreters.

## Can I override public domains like `google.com` locally?

Yes, via domain override mode. This is local-only and potentially dangerous.

- Use explicit confirmation.
- Keep rollback available.
- Some domains can still fail due browser HSTS/policy behavior.

## Where is config stored?

OS app-data directory:

- macOS: `~/Library/Application Support/DJAMP PRO/`
- Windows: `%APPDATA%/DJAMP PRO/`

## Why does HTTPS still show warnings sometimes?

Possible causes:

- root CA not trusted yet
- browser cache/HSTS
- policy restrictions for specific public domains

## Does it work without Caddy installed?

Projects can still run directly on their Django port. Domain/HTTPS proxying requires Caddy.

## Is this for production hosting?

No. DJAMP PRO is intended for local development only.
