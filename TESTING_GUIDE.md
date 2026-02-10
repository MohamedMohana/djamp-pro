# DJANGOForge - Testing Guide for certs_test Project

## ✅ Setup Status

- **Root CA**: Generated at `~/.djamp/ca/djangoforge-root-ca.crt`
- **Certificate**: Generated for `certs_test.test`
- **Django Project**: Located at `/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test`
- **Conda Environment**: `blockchain` (with Django 4.2.14)
- **Python**: Using Python 3.11 via `conda run -n blockchain python3`

## 🚀 How to Test Your Project

### Step 1: Install Root CA (Required for HTTPS)

Run this command (requires your macOS password):

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.djamp/ca/djangoforge-root-ca.crt
```

Then verify:
1. Open **Keychain Access**
2. Go to **System** → **Certificates**
3. Find **DJANGOForge Root CA**
4. Double-click → **Trust** → Set **When using this certificate** to **Always Trust**

---

### Step 2: Add Domain to Hosts File

Run this command (requires your macOS password):

```bash
sudo sh -c 'echo "127.0.0.1    certs_test.test" >> /etc/hosts'
```

---

### Step 3: Start Django Server

```bash
cd "/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test"
conda run -n blockchain python3 manage.py runserver 0.0.0.0:8001
```

---

### Step 4: Open in Browser

**HTTP (no HTTPS needed):**
```
http://certs_test.test:8001
```

**HTTPS (requires Root CA installed):**
```
https://certs_test.test:8001
```

---

## 🧪 Alternative: Start with uv

If you want to use **uv** for dependency management:

```bash
cd "/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test"

# Install with uv (if needed)
conda run -n blockchain uv pip install -r requirements.txt

# Run server
conda run -n blockchain python3 manage.py runserver 0.0.0.0:8001
```

---

## 📝 Django Management Commands

From the project directory:

```bash
cd "/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test"
conda activate blockchain

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test

# Open Django shell
python manage.py shell

# Check project
python manage.py check
```

---

## 🔍 Troubleshooting

### Server won't start?

1. Check if port 8001 is available:
   ```bash
   lsof -i :8001
   ```

2. Kill any process using the port:
   ```bash
   kill -9 <PID>
   ```

3. Check Django settings:
   ```bash
   conda run -n blockchain python3 manage.py check
   ```

### HTTPS not working?

1. Restart your browser
2. Clear browser cache
3. Verify Root CA is in System Keychain with "Always Trust"

### Domain not resolving?

Check `/etc/hosts`:
```bash
cat /etc/hosts | grep certs_test
```

Should show: `127.0.0.1    certs_test.test`

---

## 📊 Project Information

- **Path**: `/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test`
- **Settings**: `certs_test.settings`
- **Domain**: `certs_test.test`
- **Port**: 8001
- **Python Version**: 3.11 (in blockchain env)
- **Django Version**: 4.2.14

---

## ✅ Quick Test

```bash
# Terminal 1: Start server
cd "/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test" && \
  conda run -n blockchain python3 manage.py runserver 0.0.0.0:8001

# Terminal 2: Test it
sleep 3 && curl http://127.0.0.1:8001/
```

---

## 🎯 What to Expect

1. ✅ Django server starts on port 8001
2. ✅ Server responds at `http://127.0.0.1:8001`
3. ✅ Browser opens `http://certs_test.test:8001` after hosts file updated
4. ✅ HTTPS works (green lock) after Root CA installed

---

## 🚦 Next Steps for Full DJANGOForge

Once you've tested manually and confirmed it works:

1. We'll integrate this setup into DJANGOForge UI
2. Add project via GUI with custom domain
3. One-click start/stop from interface
4. Automatic domain and certificate management
5. Log viewer and diagnostics in UI

**For now, test manually with the steps above!**

---

## 📝 Notes

- This setup respects your existing project (no modifications)
- Uses your `blockchain` conda environment
- Supports `uv` for future dependency management
- Certificates are generated locally and trusted after CA install
- Changes are isolated to DJANGOForge directories only

---

**Made with ❤️ for Django development**
