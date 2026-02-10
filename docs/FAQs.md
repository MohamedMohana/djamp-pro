# DJANGOForge Frequently Asked Questions

## General

### What is DJANGOForge?

DJANGOForge is a desktop application that provides a one-click local development environment for Django projects. It handles domain management, HTTPS certificates, bundled databases, reverse proxy routing, and project orchestration automatically.

### Is DJANGOForge free?

Yes! DJANGOForge is open-source and released under the MIT License. You can use it for personal and commercial projects.

### What platforms are supported?

- **macOS:** 11.0+ (Intel and Apple Silicon)
- **Windows:** 10+ (x64 and ARM64)
- **Linux:** Coming soon (Phase 2)

### What are the system requirements?

- Node.js 18+
- Python 3.9+
- Rust toolchain
- OpenSSL
- 4GB RAM minimum
- 500MB disk space (plus project storage)

## Installation

### How do I install DJANGOForge?

1. Download the installer for your platform from the [Releases page](https://github.com/yourorg/djangoforge/releases)
2. Run the installer
3. Launch DJANGOForge
4. Complete the onboarding wizard

### Do I need Docker?

No! DJANGOForge uses embedded binaries for PostgreSQL, MySQL, Redis, and Caddy. Docker is optional and will be supported in Phase 2.

### Can I install multiple versions?

Yes, but we recommend using one installation. Multiple versions may conflict with configuration and data directories.

### How do I uninstall DJANGOForge?

**macOS:**
```bash
# Remove application
rm -rf /Applications/DJANGOForge.app

# Remove data (optional)
rm -rf ~/.djamp

# Remove Root CA (optional)
sudo security delete-certificate -c DJANGOForge
```

**Windows:**
```powershell
# Uninstall via Settings → Apps
# Remove data (optional)
rmdir /s /q %USERPROFILE%\.djamp
```

## Projects

### How do I add a Django project?

1. Click "Add Project" in the sidebar
2. Browse to your Django project directory
3. DJANGOForge will auto-detect settings
4. Configure domain, database, etc.
5. Click "Create Project"

### Can I create a new Django project from template?

Yes! In the "Add Project" wizard, choose "Create from Template" and select from:
- Basic Django project
- REST API template
- GraphQL template
- E-commerce template (Phase 2)

### How do I remove a project?

1. Select the project
2. Scroll to "Danger Zone" at the bottom
3. Click "Delete Project"
4. Confirm deletion

**Note:** This removes the project from DJANGOForge but doesn't delete your project files.

### Can I have multiple projects running at once?

Yes! DJANGOForge supports multiple simultaneous projects. Each project gets its own:
- Port
- Database
- Domain
- Virtual environment

### How do I import existing projects?

Just use the "Add Project" wizard and browse to your existing Django project. DJANGOForge will detect the configuration and set everything up automatically.

## Domains and HTTPS

### What domains can I use?

We recommend using `.test` domains:
- `myapp.test`
- `api.myapp.test`
- `admin.myapp.test`

Other local TLDs:
- `.localhost` (built into browsers)
- `.local` (macOS Bonjour)
- Custom domains pointing to 127.0.0.1

**Important:** Never use `.dev`, `.app`, or other public TLDs for local development!

### Do I need HTTPS?

No, but it's recommended for:
- Realistic production testing
- Service Worker development
- PWA testing
- OAuth callback URLs

### Will certificates work for public domains?

No! DJANGOForge certificates are signed by a local Root CA and only work locally. For public domains, use Let's Encrypt or another public CA.

### Why does my browser show a certificate error?

1. **Root CA not installed:** Install Root CA via Settings
2. **Browser cache:** Restart your browser
3. **HSTS:** Clear HSTS data for the domain (see TROUBLESHOOTING.md)

### Can I use wildcards?

Yes! For example, you can use `*.myapp.test` to match any subdomain. Add this in the project settings.

### How do I disable HTTPS?

1. Go to Project Settings
2. Uncheck "Enable HTTPS"
3. Click Save
4. Restart the project

## Databases

### Which databases are supported?

- **PostgreSQL** (recommended, primary)
- **MySQL** (optional)
- **SQLite** (use your own, not managed by DJANGOForge)
- **Redis** (for caching)

### Does DJANGOForge manage databases?

Yes! For PostgreSQL and MySQL, DJANGOForge:
- Starts/stops the database server
- Creates databases automatically
- Generates connection strings
- Provides connection testing

### Can I use an external database?

Not yet. External database support is planned for Phase 2. For now, use SQLite or let DJANGOForge manage PostgreSQL/MySQL.

### Where is database data stored?

In `~/.djamp/data/{type}/{name}`:
- `~/.djamp/data/postgres/myapp_db/`
- `~/.djamp/data/mysql/myapp_db/`
- `~/.djamp/data/redis/myapp_cache/`

### How do I backup my databases?

Copy the data directory:
```bash
# PostgreSQL
cp -r ~/.djamp/data/postgres ~/backup/

# MySQL
cp -r ~/.djamp/data/mysql ~/backup/

# Redis
cp -r ~/.djamp/data/redis ~/backup/
```

### Can I use pgAdmin or MySQL Workbench?

Yes! Connection details are shown in the project settings. You can connect any database client to the local database.

### What about database migrations?

Run them from the DJANGOForge UI:
1. Select your project
2. Click "Quick Actions"
3. Click "Migrate"

Or run manually:
```bash
cd /path/to/project
source .venv/bin/activate
python manage.py migrate
```

## Development

### How do I run tests?

From the UI:
1. Select project
2. Click "Quick Actions"
3. Click "Run Tests"

Or manually:
```bash
cd /path/to/project
source .venv/bin/activate
python manage.py test
```

### How do I create a superuser?

From the UI:
1. Select project
2. Click "Quick Actions"
3. Click "Collectstatic"

Or manually:
```bash
cd /path/to/project
source .venv/bin/activate
python manage.py createsuperuser
```

### How do I collect static files?

From the UI:
1. Select project
2. Click "Quick Actions"
3. Click "Collectstatic"

Or manually:
```bash
cd /path/to/project
source .venv/bin/activate
python manage.py collectstatic
```

### Can I use Django Debug Toolbar?

Yes! Install it in your project:
```bash
pip install django-debug-toolbar
```

Add to `INSTALLED_APPS` and `MIDDLEWARE` in your settings, then restart the project.

### How do I open a shell in my project?

From the UI:
1. Select project
2. Click "Quick Actions"
3. Click "Shell"

A terminal will open with the virtual environment activated.

### How do I open my project in VS Code?

From the UI:
1. Select project
2. Click "Quick Actions"
3. Click "VS Code"

VS Code will open with the project loaded.

### Can I use other IDEs?

Yes! DJANGOForge can launch any editor. Configure it in Settings:
- VS Code (default)
- PyCharm
- Sublime Text
- Atom
- Custom command

## Configuration

### Where is configuration stored?

In `~/.djamp/config.json`

This file contains:
- Project registry
- Application settings
- Virtual environment paths
- Domain mappings

### Can I edit the config file directly?

We don't recommend it. Use the UI instead. If you do edit manually, make a backup first and ensure JSON is valid.

### How do I change the default Python version?

Go to Settings → Default Python Version and select from available versions (3.8-3.11).

### Can I customize Django settings?

Yes! DJANGOForge generates a `.env` file in your project with all necessary settings. Edit this file directly.

### How do I add environment variables?

1. Go to Project Settings
2. Click "Environment Variables"
3. Add key-value pairs
4. Click Save

These are stored in `.env` and available in your Django application.

## Troubleshooting

### Project won't start

1. Check the Log Viewer for errors
2. Ensure the port is available
3. Verify the virtual environment exists
4. Check that Django has no syntax errors
5. See TROUBLESHOOTING.md for more details

### Database won't start

1. Check port availability
2. Verify data directory permissions
3. Check database logs
4. Try using SQLite instead
5. See TROUBLESHOOTING.md for more details

### HTTPS not working

1. Install Root CA via Settings
2. Regenerate project certificates
3. Restart the browser
4. Check HSTS settings
5. See TROUBLESHOOTING.md for more details

### Domain doesn't resolve

1. Check `/etc/hosts` (macOS/Linux) or `C:\Windows\System32\drivers\etc\hosts` (Windows)
2. Ensure domain is mapped to 127.0.0.1
3. Restart DNS client
4. See TROUBLESHOOTING.md for more details

## Advanced

### Can I customize the reverse proxy?

Yes! DJANGOForge uses Caddy. Edit `~/.djamp/Caddyfile` to customize routing, but be aware it may be overwritten on config changes.

### Can I use a different reverse proxy?

Not yet. Nginx support is planned for Phase 2.

### How do I add custom Django management commands?

Add them to your project's `management/commands/` directory as usual. They'll be available via `python manage.py`.

### Can I use multiple databases per project?

Yes! Configure them in Django settings as usual. DJANGOForge manages the primary database.

### How do I use Docker with DJANGOForge?

Not yet. Docker mode is planned for Phase 2. For now, use embedded binaries or external services.

## Security

### Is it safe to use DJANGOForge?

Yes! DJANGOForge:
- Uses OS keychain for secrets
- Requires admin privileges only for hosts/certs
- Runs in isolated environments
- Doesn't send data externally
- Is open source (auditable)

### Are my passwords safe?

Yes! Database passwords are:
- Stored in OS keychain/credential manager
- Encrypted at rest
- Never logged
- Never transmitted

### What about the Root CA certificate?

The Root CA:
- Is generated locally
- Never leaves your machine
- Can be revoked/removed anytime
- Is only used for local domains
- Cannot be used for public domains

### Can I use DJANGOForge for production?

No! DJANGOForge is for **local development only**. For production:
- Use a real web server (Nginx/Apache)
- Use Let's Encrypt or similar for HTTPS
- Use managed databases (AWS RDS, etc.)
- Use proper deployment tools

## Support and Community

### Where can I get help?

- **GitHub Issues:** https://github.com/yourorg/djangoforge/issues
- **Documentation:** https://docs.djangoforge.com
- **Discord:** https://discord.gg/djangoforge
- **Twitter:** @DJANGOForgeApp

### How can I contribute?

We welcome contributions! See CONTRIBUTING.md for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Is there a roadmap?

Yes! See our [GitHub Projects](https://github.com/yourorg/djangoforge/projects) for the current roadmap.

**Phase 1 (MVP):** Complete ✓  
**Phase 2:** Docker support, external databases, custom reverse proxy  
**Phase 3:** Team collaboration, remote development, plugins

## License

DJANGOForge is released under the MIT License. See LICENSE.md for details.

## Credits

DJANGOForge is built with:
- **Tauri** - Desktop framework
- **React** - Frontend framework
- **FastAPI** - Backend framework
- **Caddy** - Reverse proxy
- **PostgreSQL** - Database
- **Redis** - Cache

Thank you to all contributors and the open-source community!
