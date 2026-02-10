# DJANGOForge Architecture

## Overview

DJANGOForge is a desktop application built with a multi-layered architecture:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DJANGOForge Desktop App                      │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   React Frontend (Tauri)                     │   │
│  │  • Project Dashboard  • Settings  • Logs  • Terminal         │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │ IPC Commands                          │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │                  Rust Tauri Backend                          │   │
│  │  • File System    • Config Storage    • Process Management  │   │
│  │  • OS Integration • Privilege Helper  • Native IPC         │   │
│  └──────────┬─────────────────────────────────────┬─────────────┘   │
│             │                                     │                 │
│             │ REST API                           │ Native Calls    │
│             ▼                                     ▼                 │
│  ┌──────────────────────┐           ┌──────────────────────┐       │
│  │  Python FastAPI      │           │  Rust Privilege      │       │
│  │  Backend Service     │           │  Helper (Elevated)   │       │
│  │  • Django Control    │           │  • /etc/hosts edit   │       │
│  │  • Database Mgmt     │           │  • Root CA install   │       │
│  │  • Certificate Gen   │           │  • Cert Store write  │       │
│  │  • Log Aggregation   │           └──────────────────────┘       │
│  └──┬──────┬──────┬─────┘                                             │
│     │      │      │                                                  │
│     ▼      ▼      ▼                                                  │
│  ┌───────┐ ┌──────┐ ┌──────┐                                       │
│  │ Caddy │ │ PgSQL│ │Redis │  ← Bundled Binaries                   │
│  │Proxy  │ │      │ │      │                                       │
│  └───────┘ └──────┘ └──────┘                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Frontend Layer (React + TypeScript + Vite)

**Location:** `apps/src/`

**Responsibilities:**
- User interface and interaction
- State management
- API communication with Tauri backend

**Key Components:**
- `App.tsx` - Main application container
- `ProjectList.tsx` - List of projects in sidebar
- `ProjectCard.tsx` - Detailed project view
- `AddProjectModal.tsx` - Add new project wizard
- `SettingsPanel.tsx` - Application settings

**API Client:**
- `services/api.ts` - Tauri IPC command wrappers

### 2. Desktop Framework Layer (Tauri + Rust)

**Location:** `core/src/`

**Responsibilities:**
- Native desktop application lifecycle
- OS integration (filesystem, processes, etc.)
- IPC command handling
- Configuration management

**Key Modules:**
- `main.rs` - Tauri application entry point
- `commands/` - IPC command handlers
  - `config.rs` - Project and settings CRUD
  - `process.rs` - Django and process management
  - `privilege.rs` - Certificates and hosts file operations
- `storage/` - Configuration persistence
- `privilege/` - Elevated operations (Root CA, hosts file)

### 3. Backend Service Layer (Python FastAPI)

**Location:** `service/djamp_service/`

**Responsibilities:**
- Django project detection and management
- Database service orchestration
- Certificate generation and management
- Caddy configuration generation
- Log aggregation

**Key Modules:**
- `main.py` - FastAPI application
- `api/` - REST API endpoints
  - `projects.py` - Project CRUD
  - `databases.py` - Database management
  - `certificates.py` - Certificate operations
  - `utilities.py` - Utility endpoints
- `core/` - Business logic
  - `django.py` - Django server control
  - `database.py` - Database management
  - `certificate.py` - Certificate generation
  - `caddy.py` - Caddy config generation

### 4. Bundled Services

**Location:** `bundles/`

**Services:**
- **Caddy** - Reverse proxy with automatic HTTPS
- **PostgreSQL** - Primary database
- **MySQL** - Optional database
- **Redis** - Optional caching

## Data Flow

### Project Creation Flow

```
User clicks "Add Project"
  ↓
AddProjectModal opens
  ↓
User selects project path
  ↓
Tauri: detect_django_project()
  ↓
Python: detect_django_project(path)
  ↓
Returns: manage.py path, settings modules
  ↓
User fills in details (domain, database, etc.)
  ↓
Tauri: add_project(project_data)
  ↓
Rust: ConfigManager.add_project()
  ↓
Project saved to ~/.djamp/config.json
  ↓
UI updates with new project
```

### Project Start Flow

```
User clicks "Start" on project
  ↓
Tauri: start_project(project_id)
  ↓
Python FastAPI: /api/projects/{id}/start
  ↓
Core: Start database (if configured)
  ↓
Core: Start Django server
  ↓
Core: Generate Caddy config
  ↓
Core: Add domain to /etc/hosts
  ↓
Core: Generate SSL certificate (if HTTPS enabled)
  ↓
Core: Start Caddy reverse proxy
  ↓
Status updates to "running"
```

### Certificate Generation Flow

```
User enables HTTPS for project
  ↓
Tauri: generate_certificate(domain)
  ↓
Python: CertificateManager.generate_certificate(domain)
  ↓
Generate private key
  ↓
Generate CSR with Subject Alt Names
  ↓
Sign with Root CA
  ↓
Return: certificate_path, key_path, expires_at
  ↓
Tauri: update_project(https_enabled, certificate_path)
  ↓
Caddy config updated with TLS
  ↓
Caddy reloads with new certificate
```

## Storage Architecture

### Configuration Files

**Location:** `~/.djamp/`

```
~/.djamp/
├── config.json              # Project registry and app settings
├── ca/                      # Root CA certificates
│   ├── djangoforge-root-ca.crt
│   └── djangoforge-root-ca.key
├── certs/                   # Per-domain certificates
│   ├── myapp.test.crt
│   ├── myapp.test.key
│   ├── api.myapp.test.crt
│   └── api.myapp.test.key
├── data/                    # Database data files
│   ├── postgres/
│   │   └── myapp_db/
│   ├── mysql/
│   │   └── myapp_db/
│   └── redis/
│       └── myapp_cache/
├── logs/                    # Application logs
│   ├── django/
│   ├── proxy/
│   └── database/
├── Caddyfile               # Caddy configuration
└── venvs/                  # Python virtual environments
    └── myapp/
```

### Configuration Schema

**config.json:**
```json
{
  "projects": {
    "project_id": {
      "id": "uuid",
      "name": "My Django App",
      "path": "/path/to/project",
      "settings_module": "myapp.settings",
      "domain": "myapp.test",
      "aliases": ["api.myapp.test"],
      "port": 8001,
      "python_version": "3.11",
      "venv_path": "~/.djamp/venvs/myapp",
      "debug": true,
      "https_enabled": true,
      "database": {
        "type": "postgres",
        "port": 5433,
        "name": "myapp_db",
        "username": "myapp_user",
        "password": "encrypted_in_keychain"
      },
      "status": "running",
      "created_at": "2026-02-10T10:00:00Z"
    }
  },
  "settings": {
    "ca_installed": true,
    "default_python": "3.11",
    "proxy_port": 80
  }
}
```

## Security Model

### Privilege Escalation

**macOS:**
- Uses `AuthorizationExecuteWithPrivileges` pattern
- Helper binary handles: hosts file editing, CA certificate installation
- User prompted for password once per session

**Windows:**
- Uses UAC elevation via COM
- Prompted for administrator approval
- Helper process runs with elevated token

### Secret Storage

**macOS:**
- Uses `security` command-line tool
- Secrets stored in System Keychain
- Encrypted at rest

**Windows:**
- Uses Windows Credential Manager
- Stored as generic credentials
- Encrypted with DPAPI

### Certificate Trust

- Root CA generated once per system
- Requires admin privileges to install
- Certificates valid for 1 year (configurable)
- Per-domain certificates signed by Root CA
- Browsers trust automatically (after Root CA installed)

## Process Management

### Django Server

- Runs in project venv
- Uses `python manage.py runserver` for dev
- Optional: Gunicorn/Uvicorn for production-like mode
- Captures stdout/stderr for logging
- Auto-restart on crash (configurable)

### Database Services

- Each project gets isolated database
- Bundled binaries (no Docker required)
- Data stored in `~/.djamp/data/{type}/{name}`
- Automatically started/stopped with project
- Connection strings auto-generated

### Caddy Reverse Proxy

- Single instance for all projects
- Routes domains to project ports
- Handles HTTPS termination
- Graceful reload on config changes
- Supports multiple domains per project

## Logging Architecture

### Log Sources

1. **Django Logs** - Django application output
2. **Proxy Logs** - Caddy access/error logs
3. **Database Logs** - Database server logs
4. **System Logs** - DJANGOForge application logs

### Log Format

```json
{
  "timestamp": "2026-02-10T10:00:00Z",
  "level": "info",
  "source": "django",
  "project_id": "project-uuid",
  "message": "Application started"
}
```

### Log Rotation

- Automatic rotation at 100MB
- Keep last 10 log files
- Configurable in settings

## Extensibility

### Plugin System (Future)

- Custom database engines
- Additional reverse proxy options
- Custom certificate authorities
- Third-party integrations

### API Extensions

- FastAPI can be extended with custom endpoints
- Tauri commands can be added
- React components can be customized
