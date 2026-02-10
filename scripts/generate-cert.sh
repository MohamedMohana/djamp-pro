#!/bin/bash
# scripts/generate-cert.sh

set -e

DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain>"
    exit 1
fi

DJAMP_HOME="$HOME/.djamp"
CA_DIR="$DJAMP_HOME/ca"
CA_CERT="$CA_DIR/djangoforge-root-ca.crt"
CA_KEY="$CA_DIR/djangoforge-root-ca.key"
CERT_DIR="$DJAMP_HOME/certs"
CERT_KEY="$CERT_DIR/$DOMAIN.key"
CERT_CRT="$CERT_DIR/$DOMAIN.crt"

echo "🔐 DJANGOForge - Certificate Generation"
echo "======================================"
echo "Domain: $DOMAIN"

# Check CA exists
if [ ! -f "$CA_CERT" ] || [ ! -f "$CA_KEY" ]; then
    echo "❌ Root CA not found. Run install-ca.sh first"
    exit 1
fi

# Create cert directory
mkdir -p "$CERT_DIR"

# Generate private key
echo "📝 Generating private key..."
openssl genrsa -out "$CERT_KEY" 2048

# Generate CSR
echo "📝 Generating certificate signing request..."
openssl req -new -key "$CERT_KEY" -out "$CERT_DIR/$DOMAIN.csr" \
    -subj "/C=US/ST=State/L=City/O=DJANGOForge/OU=Development/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:www.$DOMAIN"

# Sign with CA
echo "📝 Signing certificate with Root CA..."
openssl x509 -req -in "$CERT_DIR/$DOMAIN.csr" -CA "$CA_CERT" -CAkey "$CA_KEY" \
    -CAcreateserial -out "$CERT_CRT" -days 365 -sha256

# Clean up CSR
rm "$CERT_DIR/$DOMAIN.csr"

echo "✅ Certificate generated successfully!"
echo "📁 Certificate: $CERT_CRT"
echo "🔑 Private key: $CERT_KEY"
