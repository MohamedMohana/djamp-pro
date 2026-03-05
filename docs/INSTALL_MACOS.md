# DJAMP PRO macOS Installation

## Prerequisites

- macOS 13+
- Node.js 18+
- npm
- Python 3.10+
- Rust stable

## Install from source

```bash
git clone https://github.com/MohamedMohana/djamp-pro.git
cd djamp-pro
npm install
npm --prefix apps/desktop install
python3 -m venv services/controller/.venv
services/controller/.venv/bin/python -m pip install -r services/controller/requirements.txt
npm run dev
```

## Verify app health

```bash
curl -s http://127.0.0.1:8765/health
```

Expected response:

```json
{"status":"healthy"}
```
