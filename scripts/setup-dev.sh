#!/bin/bash
# scripts/setup-dev.sh

set -e

echo "🚀 DJANGOForge Development Setup"
echo "================================="

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi

if ! command -v rustc &> /dev/null; then
    echo "❌ Rust is not installed. Please install Rust first."
    echo "Visit https://rustup.rs/ for installation instructions."
    exit 1
fi

if ! command -v openssl &> /dev/null; then
    echo "❌ OpenSSL is not installed. Please install OpenSSL first."
    exit 1
fi

echo "✅ All prerequisites are installed!"
echo ""

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd apps
npm install
cd ..
echo "✅ Frontend dependencies installed"
echo ""

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
cd service
pip install -r requirements.txt
cd ..
echo "✅ Python dependencies installed"
echo ""

# Create directories
echo "📁 Creating project directories..."
mkdir -p bundles/{postgres,mysql,redis,caddy}/{darwin-arm64,darwin-x64,windows-x64}
echo "✅ Project directories created"
echo ""

# Build Tauri CLI
echo "🔨 Building Tauri CLI..."
cd core
cargo build
cd ..
echo "✅ Tauri CLI built"
echo ""

# Create sample projects directory
echo "📁 Creating sample projects directory..."
mkdir -p djamp-projects
echo "✅ Sample projects directory created"
echo ""

echo "🎉 Development setup complete!"
echo ""
echo "To start the development server:"
echo "  npm run dev"
echo ""
echo "To start the Python backend service:"
echo "  npm run service:dev"
