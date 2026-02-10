# DJANGOForge 🦀

> **Local Django Development Environment Manager**  
> Transform your Django development with automated domain management, trusted HTTPS certificates, bundled databases, and seamless project orchestration.

## 🚀 What is DJANGOForge?

DJANGOForge is a desktop application that provides a one-click local development environment for Django projects, similar to MAMP PRO but for Django. It handles all the complexity so you can focus on coding.

### ✨ Key Features

- **One-Click Project Setup** - Import existing Django projects or scaffold new ones instantly
- **Custom Local Domains** - Use `myapp.test` instead of `localhost:8000`
- **Trusted HTTPS** - Automatic certificate generation with browser-trusted Root CA
- **Bundled Services** - Postgres, MySQL, and Redis included
- **Reverse Proxy** - Caddy handles routing and HTTPS automatically
- **Developer Tools** - One-click migrations, collectstatic, shell, and VS Code integration
- **Cross-Platform** - macOS and Windows support (Linux coming soon)

## 📋 Requirements

- macOS 11+ or Windows 10+
- Node.js 18+ and npm
- Rust toolchain (for building)
- Python 3.9+ (included in bundled service)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DJANGOForge Desktop App                     │
├─────────────────────────────────────────────────────────────────┤
│  React Frontend (Tauri) → Rust Backend → Python FastAPI Service │
│        ↓                   ↓                ↓                   │
│    Project UI      Config & Process    Django & DB Mgmt         │
│                     Management         Certificate Generation  │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Installation

### Development

```bash
# Clone repository
git clone https://github.com/yourorg/djangoforge.git
cd djangoforge

# Install dependencies
npm install
cd service && pip install -r requirements.txt

# Run in development mode
npm run dev
```

### Production Builds

See [BUILD.md](docs/BUILD.md) for detailed build instructions.

## 🎯 Quick Start

1. **Launch DJANGOForge** and complete the onboarding wizard
2. **Add a Django project** or create one from template
3. **Configure your domain** (e.g., `myapp.test`)
4. **Click "Start"** - DJANGOForge handles everything else:
   - Updates hosts file
   - Generates HTTPS certificate
   - Starts database
   - Starts Django server
   - Configures reverse proxy

5. **Open your browser** at `https://myapp.test` 🔒

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Build Instructions](docs/BUILD.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [FAQs](docs/FAQs.md)

## 🛠️ Tech Stack

- **Frontend**: React + TypeScript + Vite
- **Desktop Framework**: Tauri (Rust + WebView)
- **Backend Service**: Python FastAPI
- **Reverse Proxy**: Caddy
- **Databases**: Postgres, MySQL, Redis (bundled binaries)

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Inspired by MAMP PRO and Laravel Valet.

---

**Made with ❤️ for Django developers**
