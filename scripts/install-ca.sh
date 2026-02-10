#!/bin/bash
# scripts/install-ca.sh

set -e

DJAMP_HOME="$HOME/.djamp"
CA_DIR="$DJAMP_HOME/ca"
CA_CERT="$CA_DIR/djangoforge-root-ca.crt"
CA_KEY="$CA_DIR/djangoforge-root-ca.key"
DAYS=3650

echo "🔐 DJANGOForge - Root CA Installation (macOS)"
echo "============================================"

# Check if CA already exists
if [ -f "$CA_CERT" ]; then
    echo "⚠️  Root CA already exists at $CA_CERT"
    read -p "Regenerate CA? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Create directory
mkdir -p "$CA_DIR"

# Create config file
CONFIG_FILE="$CA_DIR/ca.conf"
cat > "$CONFIG_FILE" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req

[req_distinguished_name]
C = US
ST = State
L = City
O = DJANGOForge
OU = Development
CN = DJANGOForge Root CA

[v3_req]
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
EOF

# Generate Root CA
echo "📝 Generating Root CA certificate..."
openssl req -x509 -newkey rsa:4096 -keyout "$CA_KEY" -out "$CA_CERT" -days "$DAYS" -nodes \
    -config "$CONFIG_FILE" -extensions v3_req

if [ ! -f "$CA_CERT" ]; then
    echo "❌ Failed to generate Root CA"
    exit 1
fi

# Install to macOS Keychain (requires admin)
echo "🔑 Installing Root CA to system keychain..."
echo "⚠️  This requires administrator privileges"
echo "Enter your macOS password when prompted"

if sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CA_CERT"; then
    echo "✅ Root CA installed successfully!"
    echo "📁 Certificate location: $CA_CERT"
    echo "🎉 You can now issue trusted certificates for .test domains"
else
    echo "❌ Failed to install Root CA"
    exit 1
fi
