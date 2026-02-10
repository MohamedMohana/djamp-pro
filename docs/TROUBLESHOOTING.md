# DJANGOForge Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### "Node.js not found"

**Symptom:** Error when running `npm install`

**Solution:**
```bash
# Check Node.js version
node --version

# If not installed or version < 18:
# macOS
brew install node

# Windows
choco install nodejs

# Linux
sudo apt install nodejs npm
```

#### "Rust not found"

**Symptom:** Error when building Tauri backend

**Solution:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Then reload your shell
source $HOME/.cargo/env
```

#### "Python 3 not found"

**Symptom:** Error when installing Python dependencies

**Solution:**
```bash
# macOS
brew install python3

# Windows
choco install python3

# Linux
sudo apt install python3 python3-pip
```

#### "OpenSSL not found"

**Symptom:** Cannot generate certificates

**Solution:**
```bash
# macOS
brew install openssl

# Windows
choco install openssl

# Linux
sudo apt install libssl-dev
```

### Project Management Issues

#### "manage.py not found"

**Symptom:** Cannot detect Django project

**Solution:**
- Ensure you're selecting the root directory of your Django project (where `manage.py` is located)
- Check that `manage.py` exists in the selected directory
- Verify the directory is not corrupted

#### "Settings module not found"

**Symptom:** Project detection succeeds but no settings modules listed

**Solution:**
- Check that you have a `settings.py` file in your project directory
- If using a multi-config setup, ensure settings files exist
- Verify the project structure matches Django conventions

#### "Venv creation failed"

**Symptom:** Cannot create virtual environment

**Solution:**
```bash
# Check Python version
python3 --version

# Ensure python3-venv is installed (Linux)
sudo apt install python3-venv

# Try creating venv manually
cd /path/to/project
python3 -m venv .venv
```

#### "Dependencies installation failed"

**Symptom:** Error when installing `requirements.txt`

**Solution:**
- Check that `requirements.txt` exists in the project root
- Try installing manually:
```bash
cd /path/to/project
source .venv/bin/activate
pip install -r requirements.txt
```
- Check for compatibility issues with your Python version

### Runtime Issues

#### "Port already in use"

**Symptom:** Project won't start, port conflict error

**Solution:**
```bash
# Find what's using the port (macOS/Linux)
lsof -i :8001

# Kill the process
kill -9 <PID>

# Windows
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

Alternatively, change the project port in settings.

#### "Django won't start"

**Symptom:** Project status stays "starting"

**Solution:**
- Check Django logs in the Log Viewer
- Verify virtual environment is created and activated
- Ensure all dependencies are installed
- Check Django settings for errors
- Try running manually:
```bash
cd /path/to/project
source .venv/bin/activate
DJANGO_SETTINGS_MODULE=myapp.settings python manage.py runserver 127.0.0.1:8001
```

#### "Database won't start"

**Symptom:** Database service fails to start

**Solution:**
- Check port conflicts
- Verify data directory has correct permissions
- Check database logs
- Try using SQLite instead for testing
- Ensure database binaries are properly bundled

#### "Caddy won't start"

**Symptom:** Reverse proxy not working

**Solution:**
- Check Caddy configuration in `~/.djamp/Caddyfile`
- Verify Caddy binary exists and is executable
- Check Caddy logs
- Ensure ports 80/443 are available (or configure different ports)
- Try manually:
```bash
caddy run --config ~/.djamp/Caddyfile
```

### Certificate and HTTPS Issues

#### "Root CA not found"

**Symptom:** Cannot generate project certificates

**Solution:**
```bash
# Install Root CA
npm run install:ca:mac  # macOS
npm run install:ca:win  # Windows
```

#### "Certificate not trusted by browser"

**Symptom:** Browser shows certificate error despite installing Root CA

**Solution:**
- Restart your browser
- Clear browser cache
- Verify Root CA is in trusted store:
  - **macOS:** Keychain Access → System → Certificates
  - **Windows:** Certificate Manager → Trusted Root Certification Authorities
- Try importing Root CA manually:
  - **macOS:** Double-click `~/.djamp/ca/djangoforge-root-ca.crt` → Always Trust
  - **Windows:** Double-click `.crt` → Install Certificate → Trusted Root

#### "Certificate expired"

**Symptom:** Browser shows certificate expired

**Solution:**
- Regenerate certificate for the domain
- Or regenerate all project certificates:
```bash
# Delete old certificates
rm ~/.djamp/certs/*.crt
rm ~/.djamp/certs/*.key

# Projects will regenerate on next start
```

#### "HSTS preventing access"

**Symptom:** Browser refuses to load site even after disabling HTTPS

**Solution:**
- This is a browser security feature
- Clear HSTS data for the domain:
  - **Chrome:** chrome://net-internals/#hsts
  - **Firefox:** about:preferences#privacy → Manage Data → Clear HSTS
- Use a different domain
- Wait for HSTS to expire (can take up to 1 year)

### Domain Issues

#### "Domain doesn't resolve"

**Symptom:** Cannot access project at custom domain

**Solution:**
```bash
# Check hosts file
# macOS/Linux
cat /etc/hosts

# Windows
type C:\Windows\System32\drivers\etc\hosts

# Look for entry like:
# 127.0.0.1 myapp.test

# If missing, add manually or restart DJANGOForge
```

#### "Permission denied editing hosts file"

**Symptom:** Cannot add domain to hosts file

**Solution:**
- Ensure you're running as administrator/root
- macOS: Enter password when prompted
- Windows: Approve UAC prompt
- Manually edit hosts file with elevated permissions

### Performance Issues

#### "Application is slow"

**Symptom:** DJANGOForge UI is unresponsive

**Solution:**
- Check system resources (CPU, memory)
- Close unused projects
- Reduce log verbosity in settings
- Disable auto-start for projects you don't use immediately
- Check for background processes

#### "Django is slow"

**Symptom:** Project loads slowly

**Solution:**
- Enable DEBUG mode during development
- Optimize Django queries
- Use Django Debug Toolbar
- Consider adding Redis for caching
- Check database performance

### Data Issues

#### "Project disappeared"

**Symptom:** Project no longer shows in the list

**Solution:**
- Check configuration file: `~/.djamp/config.json`
- If corrupted, restore from backup if available
- Recreate the project (data should still be in place)
- Check logs for errors

#### "Database data lost"

**Symptom:** Database is empty after restart

**Solution:**
- Check data directory: `~/.djamp/data/{type}/{name}`
- Ensure database is stopping properly before app closes
- Check database logs for corruption errors
- Restore from backup if available
- Consider enabling automatic backups

### Cross-Platform Issues

#### "Windows-specific errors"

**Symptom:** Issue only occurs on Windows

**Common Windows issues:**
1. Path separators (use `/` or `\\`)
2. Permission issues (run as Administrator)
3. Antivirus blocking operations
4. Firewall blocking ports

**Solutions:**
- Disable antivirus temporarily to test
- Allow DJANGOForge through firewall
- Run as Administrator
- Use WSL2 for better Linux compatibility

#### "macOS-specific errors"

**Symptom:** Issue only occurs on macOS

**Common macOS issues:**
1. Gatekeeper blocking unsigned binaries
2. Keychain access denied
3. SIP (System Integrity Protection) conflicts
4. Xcode command line tools missing

**Solutions:**
- Allow app in System Preferences → Security
- Reinstall Xcode command line tools: `xcode-select --install`
- Check Keychain permissions
- Use correct security entitlements

## Debug Mode

Enable debug mode for detailed logging:

```bash
# macOS/Linux
export DJANGOFORGE_DEBUG=1
npm run dev

# Windows
set DJANGOFORGE_DEBUG=1
npm run dev
```

Check logs:
- Application logs: `~/.djamp/logs/app.log`
- Django logs: `~/.djamp/logs/django/`
- Database logs: `~/.djamp/logs/database/`
- Proxy logs: `~/.djamp/logs/proxy/`

## Getting Help

If you can't resolve an issue:

1. **Search existing issues:** Check GitHub Issues for similar problems
2. **Check documentation:** Review ARCHITECTURE.md and BUILD.md
3. **Enable debug mode:** Get detailed logs to share
4. **Create a minimal reproducible example:** Document the exact steps
5. **Include system information:**
   - Operating system and version
   - DJANGOForge version
   - Python version
   - Node.js version
   - Error messages
   - Relevant logs

**Submit issue:** https://github.com/yourorg/djangoforge/issues

## Known Limitations

1. **HSTS:** Cannot bypass HSTS once set (browser security feature)
2. **Wildcards:** Limited wildcard subdomain support
3. **External databases:** No support for external database connections yet
4. **Docker:** Docker mode not implemented yet (planned for Phase 2)
5. **Multiple Python versions:** Can only use one Python version per project
6. **Database migrations:** Automatic migrations not yet supported

## Recovery Procedures

### Reset All Data

⚠️ **This will delete all projects, databases, and settings**

```bash
# Stop DJANGOForge
# Backup current data if needed
cp -r ~/.djamp ~/.djamp.backup

# Remove DJANGOForge data
rm -rf ~/.djamp

# Restart DJANGOForge
# Fresh installation
```

### Reset Certificates

```bash
# Remove all certificates
rm -rf ~/.djamp/certs
rm -rf ~/.djamp/ca

# Reinstall Root CA
npm run install:ca:mac  # or install:ca:win

# Regenerate project certificates on next start
```

### Reset Configuration

```bash
# Backup config
cp ~/.djamp/config.json ~/.djamp/config.json.backup

# Remove projects section
# Edit ~/.djamp/config.json and remove or modify projects section

# Restart DJANGOForge
```
