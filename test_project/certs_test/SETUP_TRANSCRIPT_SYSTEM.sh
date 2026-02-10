#!/bin/bash

################################################################################
# KKU Transcript System (سجل المقررات) - Complete Setup Script
# This script will:
#   1. Run database migrations (adds new models + Role fields)
#   2. Update super_admin role with transcript permissions
#   3. Verify the setup
#   4. Display next steps
################################################################################

set -e  # Exit on error

echo "============================================================"
echo "🚀 KKU Transcript System (سجل المقررات) - Setup"
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
echo "  - New table: certificates_transcripttemplate"
echo "  - New table: certificates_transcript"
echo "  - 6 new fields to certificates_role table (all default FALSE)"
echo ""
python manage.py makemigrations certificates
echo "${GREEN}✓ Migrations created${NC}"
echo ""

echo "📌 Step 3: Applying migrations to database..."
python manage.py migrate certificates
echo "${GREEN}✓ Migrations applied${NC}"
echo ""

# 3. Update role permissions
echo "📌 Step 4: Updating role permissions..."
python update_role_permissions.py
echo "${GREEN}✓ super_admin now has transcript permissions${NC}"
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

# 5. Final instructions
echo "============================================================"
echo "${GREEN}✅ TRANSCRIPT SYSTEM SETUP COMPLETE!${NC}"
echo "============================================================"
echo ""
echo "📖 Next Steps:"
echo ""
echo "1. Login as super_admin and check the sidebar for:"
echo "   - مشرف سجلات (Transcript Section)"
echo "     - إرسال السجلات"
echo "     - إدارة السجلات"
echo "     - إدارة قوالب السجلات"
echo ""
echo "2. Create your first transcript template:"
echo "   - Go to: /transcript/templates/create/"
echo "   - Upload PDF, select fields, set course count"
echo ""
echo "3. Create transcripts:"
echo "   - Go to: /transcript/create/"
echo "   - Select template and enter data"
echo ""
echo "4. Verify transcripts work:"
echo "   - Visit: /validate/?hash=YOUR_TRANSCRIPT_HASH"
echo ""
echo "============================================================"
echo "${GREEN}✅ Your existing systems (Certificates + Advanced) are UNTOUCHED!${NC}"
echo "============================================================"
echo ""
echo "🔗 New URLs available:"
echo "   /transcript/templates/          - List templates"
echo "   /transcript/templates/create/   - Create template"
echo "   /transcript/create/             - Create transcripts"
echo "   /transcript/manage/             - Manage transcripts"
echo ""
echo "Happy coding! 🎉"
echo ""
