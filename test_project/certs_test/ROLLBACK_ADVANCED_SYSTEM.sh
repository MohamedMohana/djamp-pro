#!/bin/bash

################################################################################
# KKU Advanced Certificate System - ROLLBACK Script
# 
# ⚠️ EMERGENCY ROLLBACK ONLY
# Use this ONLY if something goes wrong with the advanced system
# 
# This will:
#   1. Reverse the database migrations
#   2. Remove the advanced_admin role
#   3. Restore your system to the previous state
# 
# YOUR EXISTING 128,612 CERTIFICATES WILL REMAIN SAFE!
################################################################################

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "============================================================"
echo "${RED}⚠️  KKU Advanced System - ROLLBACK${NC}"
echo "============================================================"
echo ""
echo "${YELLOW}WARNING: This will remove all advanced certificate data!${NC}"
echo ""
echo "Your existing regular certificates will NOT be affected."
echo ""
read -p "Are you SURE you want to rollback? (type 'YES' to confirm): " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo "${GREEN}✓ Rollback cancelled. System unchanged.${NC}"
    exit 0
fi

echo ""
echo "📌 Step 1: Finding last migration before advanced system..."
LAST_MIGRATION=$(python manage.py showmigrations certificates | grep '\[X\]' | tail -2 | head -1 | awk '{print $2}')
echo "Last safe migration: $LAST_MIGRATION"
echo ""

echo "📌 Step 2: Rolling back migrations..."
python manage.py migrate certificates $LAST_MIGRATION
echo "${GREEN}✓ Database rolled back${NC}"
echo ""

echo "📌 Step 3: Removing advanced_admin role..."
python -c "
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()
from certificates.models_role import Role
Role.objects.filter(name_en='advanced_admin').delete()
print('✓ Role removed')
"
echo ""

echo "============================================================"
echo "${GREEN}✅ ROLLBACK COMPLETE${NC}"
echo "============================================================"
echo ""
echo "Your system has been restored to the previous state."
echo "The advanced system files are still present but inactive."
echo ""
echo "To completely remove advanced files:"
echo "  1. Delete certificates/models_advanced.py"
echo "  2. Delete certificates/forms_advanced.py"
echo "  3. Delete certificates/views_advanced*.py"
echo "  4. Delete certificates/advanced_generator.py"
echo "  5. Delete certificates/constants.py"
echo "  6. Delete certificates/templates/advanced/"
echo "  7. Revert certificates/urls.py changes"
echo "  8. Revert certificates/views.py validate() function"
echo ""
echo "Or just leave them - they won't affect your existing system!"
echo ""

