#!/bin/bash
# DJANGOForge Setup Script - Using uv and conda blockchain environment
# This script sets up DJANGOForge to work with your existing project

set -e

PROJECT_DIR="/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test"
PROJECT_NAME="certs_test"
DOMAIN="certs_test.test"
DJANGO_SETTINGS="certs_test.settings"

echo "🚀 DJANGOForge Setup"
echo "==================="
echo ""
echo "Project: $PROJECT_DIR"
echo "Domain: $DOMAIN"
echo "Conda Env: blockchain"
echo ""

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate blockchain

echo "✅ Conda environment 'blockchain' activated"

# Check Django installation
echo ""
echo "📦 Checking Django installation..."
cd "$PROJECT_DIR"
python manage.py --version
echo "✅ Django is ready"

# Create DJANGOForge config directory
echo ""
echo "📁 Creating DJANGOForge directories..."
DJAMP_HOME="$HOME/.djamp"
mkdir -p "$DJAMP_HOME/projects"
mkdir -p "$DJAMP_HOME/logs"

# Create project configuration
PROJECT_ID="test-project-$(date +%s)"
CONFIG_FILE="$DJAMP_HOME/config.json"

# Create minimal config if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
{
  "projects": {},
  "settings": {
    "ca_installed": false,
    "default_python": "3.11",
    "proxy_port": 80
  }
}
EOF
    echo "✅ Created DJANGOForge config"
fi

# Add project to config
echo ""
echo "➕ Adding project to DJANGOForge..."

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "✅ uv found, will use uv for package management"
    UV_ENABLED=true
else
    echo "⚠️  uv not found, will use pip"
    UV_ENABLED=false
fi

# Install Root CA
echo ""
echo "🔐 Installing Root CA..."
echo "This requires administrator privileges"
echo ""
sudo bash /Users/mohana/Documents/CODE/opencode/DJAMP/scripts/install-ca.sh

if [ $? -eq 0 ]; then
    echo "✅ Root CA installed"
else
    echo "❌ Root CA installation failed"
    echo "⚠️  You can still test without HTTPS (http mode)"
fi

# Generate certificate for domain
echo ""
echo "🔒 Generating SSL certificate for $DOMAIN..."
bash /Users/mohana/Documents/CODE/opencode/DJAMP/scripts/generate-cert.sh "$DOMAIN"

if [ $? -eq 0 ]; then
    echo "✅ Certificate generated"
else
    echo "⚠️  Certificate generation failed"
fi

# Add to hosts file
echo ""
echo "🌐 Adding domain to hosts file..."
if ! grep -q "$DOMAIN" /etc/hosts; then
    echo "127.0.0.1    $DOMAIN" | sudo tee -a /etc/hosts
    echo "✅ Domain added to hosts file"
else
    echo "✅ Domain already in hosts file"
fi

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "========================================="
echo "Your project is ready for DJANGOForge"
echo ""
echo "Project Path: $PROJECT_DIR"
echo "Domain: http://$DOMAIN"
echo "Domain (HTTPS): https://$DOMAIN"
echo "Settings: $DJANGO_SETTINGS"
echo "Conda Env: blockchain"
echo ""
echo "To run your project manually:"
echo "  cd $PROJECT_DIR"
echo "  conda activate blockchain"
echo "  python manage.py runserver 0.0.0.0:8001"
echo ""
echo "To test domain:"
echo "  open http://$DOMAIN"
echo "========================================="
