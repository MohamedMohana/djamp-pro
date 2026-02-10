#!/bin/bash
# test-certs-test.sh
# Complete test script for DJANGOForge with certs_test project

set -e

echo "🚀 DJANGOForge Testing Guide"
echo "==========================="
echo ""

PROJECT_DIR="/Users/mohana/Documents/CODE/opencode/DJAMP/test_project/certs_test"
DOMAIN="certs_test.test"

echo "✅ Prerequisites:"
echo "   - Django project: $PROJECT_DIR"
echo "   - Domain: $DOMAIN"
echo "   - Root CA: ~/.djamp/ca/djangoforge-root-ca.crt"
echo "   - Certificate: ~/.djamp/certs/$DOMAIN.crt"
echo ""

echo "📝 Step 1: Add domain to hosts file"
echo "   Run this command (requires password):"
echo "   sudo sh -c 'echo \"127.0.0.1    $DOMAIN\" >> /etc/hosts'"
echo ""
echo "   Or add this line manually to /etc/hosts:"
echo "   127.0.0.1    $DOMAIN"
echo ""

echo "🔐 Step 2: Install Root CA (if not done)"
echo "   Run this command (requires password):"
echo "   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.djamp/ca/djangoforge-root-ca.crt"
echo ""
echo "   Then verify in Keychain Access > System Certificates > DJANGOForge Root CA > Trust > Always Trust"
echo ""

echo "🔒 Step 3: Certificate already generated:"
echo "   Certificate: ~/.djamp/certs/$DOMAIN.crt"
echo "   Private Key: ~/.djamp/certs/$DOMAIN.key"
echo ""

echo "🚀 Step 4: Start Django Server"
echo "   Run these commands:"
echo ""
echo "   cd \"$PROJECT_DIR\""
echo "   conda activate blockchain"
echo "   python manage.py runserver 0.0.0.0:8001"
echo ""

echo "🌐 Step 5: Test Your App"
echo "   Open in browser:"
echo "   http://$DOMAIN:8001"
echo "   https://$DOMAIN:8001 (after installing CA)"
echo ""

echo "💡 Alternative: Use Caddy for HTTPS"
echo "   Create Caddyfile in project root:"
echo "   $DOMAIN:8001 {"
echo "       tls ~/.djamp/certs/$DOMAIN.crt ~/.djamp/certs/$DOMAIN.key"
echo "       reverse_proxy 127.0.0.1:8001"
echo "   }"
echo ""
echo "   Then start Caddy:"
echo "   caddy run"
echo ""

echo "✨ Quick Test Commands:"
echo ""
echo "# Start Django server:"
echo "cd \"$PROJECT_DIR\" && conda run -n blockchain python manage.py runserver 0.0.0.0:8001"
echo ""
echo "# Test in browser:"
echo "open http://$DOMAIN:8001"
echo ""

echo "✅ Setup Complete! Follow the steps above to test DJANGOForge functionality."
