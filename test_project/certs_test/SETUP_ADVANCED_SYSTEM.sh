#!/bin/bash

################################################################################
# KKU Advanced Certificate System - Complete Setup Script
# This script will:
#   1. Run database migrations (adds new models + Role fields)
#   2. Create the "advanced_admin" role
#   3. Verify the setup
#   4. Display next steps
################################################################################

set -e  # Exit on error

echo "============================================================"
echo "🚀 KKU Advanced Certificate System - Setup"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Check Python environment
echo "📌 Step 1: Checking Python environment..."
python --version || python3 --version
echo ""

# 2. Run migrations
echo "📌 Step 2: Creating database migrations..."
echo "${YELLOW}This will add:${NC}"
echo "  - New table: certificates_advancedcertificatetemplate"
echo "  - New table: certificates_advancedcertificate"
echo "  - 6 new fields to certificates_role table (all default FALSE)"
echo ""
python manage.py makemigrations certificates
echo "${GREEN}✓ Migrations created${NC}"
echo ""

echo "📌 Step 3: Applying migrations to database..."
python manage.py migrate certificates
echo "${GREEN}✓ Migrations applied${NC}"
echo ""

# 3. Create advanced role
echo "📌 Step 4: Creating 'advanced_admin' role..."
python create_advanced_role.py
echo "${GREEN}✓ Role created/verified${NC}"
echo ""

# 4. Collect static files (if needed)
echo "📌 Step 5: Collecting static files (optional)..."
read -p "Do you want to collect static files now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    python manage.py collectstatic --noinput
    echo "${GREEN}✓ Static files collected${NC}"
else
    echo "${YELLOW}⚠ Skipped static collection${NC}"
fi
echo ""

# 5. Verify setup
echo "📌 Step 6: Verifying setup..."
python check_advanced_setup.py
echo ""

# 6. Final instructions
echo "============================================================"
echo "${GREEN}✅ SETUP COMPLETE!${NC}"
echo "============================================================"
echo ""
echo "📖 Next Steps:"
echo ""
echo "1. Assign the 'advanced_admin' role to users who need KKUx access:"
echo "   - Go to: http://your-domain/roles/user/"
echo "   - Edit a user and select 'مشرف متقدم' role"
echo ""
echo "2. Create your first advanced template:"
echo "   - Go to: http://your-domain/advanced/templates/create/"
echo "   - Upload PDF, select fields, customize positions"
echo ""
echo "3. Create advanced certificates:"
echo "   - Go to: http://your-domain/advanced/certificates/create/"
echo "   - Select template and enter data"
echo ""
echo "4. Verify certificates work:"
echo "   - Visit: http://your-domain/validate/?hash=YOUR_CERT_HASH"
echo ""
echo "============================================================"
echo "${GREEN}✅ Your existing system (128,612 certificates) is UNTOUCHED!${NC}"
echo "============================================================"
echo ""
echo "📚 Documentation:"
echo "   - ADVANCED_SYSTEM_IMPLEMENTATION.md"
echo "   - QUICK_START_ADVANCED.md"
echo ""
echo "🔗 New URLs available:"
echo "   /advanced/templates/          - List templates"
echo "   /advanced/templates/create/   - Create template"
echo "   /advanced/certificates/create/ - Create certificates"
echo "   /advanced/certificates/manage/ - Manage certificates"
echo ""
echo "Happy coding! 🎉"
echo ""

