# DJANGOForge Build Instructions

## Prerequisites

### Required Tools

- **Node.js** 18.0 or higher
- **npm** 9.0 or higher
- **Rust** stable toolchain (latest)
- **Python** 3.9 or higher
- **OpenSSL** (for certificate generation)

### Platform-Specific Requirements

**macOS:**
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install node python openssl
```

**Windows:**
```powershell
# Install Chocolatey (if not already installed)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -Tls12; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install required tools
choco install nodejs python3 rust openssl
```

**Linux (Ubuntu/Debian):**
```bash
# Install required tools
sudo apt update
sudo apt install -y nodejs npm python3 python3-pip rustc cargo libssl-dev
```

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourorg/djangoforge.git
cd djangoforge
```

### 2. Install Dependencies

```bash
# Install frontend dependencies
npm install

# Install Python dependencies
cd service
pip install -r requirements.txt
cd ..
```

### 3. Setup Development Environment

```bash
# Run the setup script
npm run setup:dev

# This will:
# - Create necessary directories
# - Build Rust backend
# - Install all dependencies
# - Prepare project structure
```

### 4. Run Development Server

```bash
# Terminal 1: Start Tauri dev server
npm run dev

# Terminal 2: Start Python backend service
npm run service:dev
```

The application will open automatically at `http://localhost:1420`.

## Building for Production

### macOS

#### Build Desktop App

```bash
# Build for Apple Silicon (M1/M2/M3)
npm run tauri:build

# Build for Intel Mac
npm run tauri:build -- --target x86_64-apple-darwin

# Build for Universal Binary
npm run tauri:build -- --target universal-apple-darwin
```

The built app will be in: `core/src-tauri/target/release/bundle/dmg/`

#### Create Installer (.pkg)

```bash
# After building the .dmg, you can create a .pkg using packagesbuild
# Requires Packages app: https://s.sudre.free.fr/Software/Packages/about.html
```

### Windows

#### Build Desktop App

```bash
# Build for x64
npm run tauri:build -- --target x86_64-pc-windows-msvc

# Build for x86
npm run tauri:build -- --target i686-pc-windows-msvc
```

The built app will be in: `core/src-tauri/target/release/bundle/msi/`

#### Create Installer

```bash
# The MSI is automatically created during the build process
# For an NSIS installer, configure it in tauri.conf.json
```

### Linux

#### Build Desktop App

```bash
# Build for deb (Debian/Ubuntu)
npm run tauri:build -- --target x86_64-unknown-linux-gnu

# Build for AppImage
npm run tauri:build -- --target x86_64-unknown-linux-gnu -- --format appimage
```

The built app will be in: `core/src-tauri/target/release/bundle/`

## Bundling Binaries

To include bundled database and service binaries:

```bash
# Run the bundle script
npm run bundle:binaries

# This will:
# - Download PostgreSQL binaries for all platforms
# - Download MySQL binaries for all platforms
# - Download Redis binaries for all platforms
# - Download Caddy binary for all platforms
# - Place them in the bundles/ directory
```

**Note:** The bundle script is a placeholder. You'll need to manually download and place the binaries in the correct directories before building.

### Manual Binary Placement

```
bundles/
├── postgres/
│   ├── darwin-arm64/
│   │   ├── bin/postgres
│   │   ├── bin/pg_ctl
│   │   └── ...
│   ├── darwin-x64/
│   └── windows-x64/
│       └── bin/postgres.exe
├── mysql/
│   └── ...
├── redis/
│   └── ...
└── caddy/
    ├── darwin-arm64/
    │   └── caddy
    ├── darwin-x64/
    │   └── caddy
    └── windows-x64/
        └── caddy.exe
```

## Code Signing

### macOS

```bash
# Sign the app
codesign --force --deep --sign "Developer ID Application: Your Name" \
  core/src-tauri/target/release/bundle/macos/DJANGOForge.app

# Notarize the app (requires Apple Developer account)
xcrun notarytool submit \
  core/src-tauri/target/release/bundle/macos/DJANGOForge.dmg \
  --apple-id "your@email.com" \
  --password "app-specific-password" \
  --team-id "TEAM-ID" \
  --wait
```

### Windows

```bash
# Sign the executable
signtool sign \
  /f "certificate.pfx" \
  /p "password" \
  /t http://timestamp.digicert.com \
  core/src-tauri/target/release/bundle/msi/DJANGOForge_0.1.0_x64_en-US.msi
```

## Release Checklist

Before creating a release:

- [ ] Update version in `package.json`, `apps/package.json`, and `core/Cargo.toml`
- [ ] Update changelog in `README.md`
- [ ] Run tests: `npm test`
- [ ] Run linting: `npm run lint`
- [ ] Run type checking: `npm run typecheck`
- [ ] Build for all target platforms
- [ ] Test builds on clean machines
- [ ] Sign binaries (macOS/Windows)
- [ ] Create release notes
- [ ] Upload to GitHub Releases
- [ ] Update download links in documentation

## Troubleshooting Build Issues

### Tauri Build Fails

**Issue:** "Webview2 not found" (Windows)

**Solution:** Install WebView2 Runtime
```powershell
# Download and install from:
# https://developer.microsoft.com/en-us/microsoft-edge/webview2/
```

**Issue:** "Code signing failed" (macOS)

**Solution:** Ensure you have a valid Apple Developer certificate
```bash
# List available certificates
security find-identity -v -p codesigning
```

### Rust Build Fails

**Issue:** "Failed to compile crate"

**Solution:** Update Rust toolchain
```bash
rustup update
rustup update stable
```

### Python Dependencies Fail

**Issue:** "Failed to build wheel"

**Solution:** Install build tools

**macOS:**
```bash
xcode-select --install
```

**Windows:**
```bash
# Install Microsoft C++ Build Tools
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

### Binary Bundling Issues

**Issue:** "Binary not found"

**Solution:** Ensure binaries have correct permissions
```bash
# macOS/Linux
chmod +x bundles/*/darwin-*/bin/*

# Windows - no action needed
```

## Continuous Integration

### GitHub Actions

Create `.github/workflows/build.yml`:

```yaml
name: Build

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - run: npm install
      - run: npm run tauri:build
      - uses: actions/upload-artifact@v3
        with:
          name: macos-build
          path: core/src-tauri/target/release/bundle/dmg/*.dmg

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - run: npm install
      - run: npm run tauri:build
      - uses: actions/upload-artifact@v3
        with:
          name: windows-build
          path: core/src-tauri/target/release/bundle/msi/*.msi

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - run: sudo apt-get install libwebkit2gtk-4.0-dev \
                  build-essential curl wget file libssl-dev \
                  libayatana-appindicator3-dev librsvg2-dev
      - run: npm install
      - run: npm run tauri:build
      - uses: actions/upload-artifact@v3
        with:
          name: linux-build
          path: core/src-tauri/target/release/bundle/deb/*.deb
```

## Additional Resources

- [Tauri Documentation](https://tauri.app/v1/guides/)
- [React Documentation](https://react.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Caddy Documentation](https://caddyserver.com/docs/)
