# DJAMP PRO 5-Minute Quickstart

## 1) Start DJAMP PRO

```bash
npm run dev
```

## 2) Add your Django project

- Click `Add Project`
- Select your Django root directory
- Confirm `manage.py` and settings module detection

## 3) Configure domain

- Set domain to `<project>.test`
- Keep HTTPS enabled

## 4) Start project

- Click `Start`
- Open the generated URL (usually `https://<project>.test`)

## 5) Troubleshoot quickly

```bash
curl -s http://127.0.0.1:8765/health
lsof -nP -iTCP:8443 -sTCP:LISTEN
```
