# 🚀 KKU Advanced Certificates - START HERE

## ✅ What I Built For You

Your **existing system (128,612 certificates) is UNTOUCHED and working perfectly**.

I added a **NEW parallel system** for KKUx with 15 fields, bilingual support, and advanced customization.

---

## 🎯 To Activate The New System (3 Steps):

### **Step 1: Run This Script**
```bash
./SETUP_ADVANCED_SYSTEM.sh
```

This will:
- Add 2 new database tables (for advanced certificates)
- Add 6 new permission fields to your Role table
- Create a new role called "مشرف متقدم"
- **Your 128,612 existing certificates stay safe!**

---

### **Step 2: Give Users Access**
1. Go to: `http://your-site/roles/user/`
2. Edit a user
3. Select role: **"مشرف متقدم"** (Advanced Admin)
4. Save

---

### **Step 3: Start Using It!**
Login with that user, you'll see new menu items:
- 📋 **إدارة القوالب المتقدمة** → Create advanced templates (15 fields!)
- 🎓 **إرسال الشهادات المتقدمة** → Send certificates
- 📂 **إدارة الشهادات المتقدمة** → View all advanced certificates

The validation page `/validate/` now works for BOTH old and new certificates automatically!

---

## 🆕 The 15 New Fields

1. Arabic Name / English Name
2. National ID (Arabic) / National ID (English)
3. Program Name (Arabic) / Program Name (English)
4. Number of Courses (Arabic) / Number of Courses (English)
5. Duration (Arabic) / Duration (English)
6. Overall Grade (Arabic) / Overall Grade (English)
7. GPA (Arabic) / GPA (English)
8. Issue Date (Gregorian)

**All fields are OPTIONAL - you can enable/disable any field per template!**

---

## 🛡️ Is My Data Safe?

**YES!** Here's why:

✅ Your 128,612 certificates are in table: `certificates_certificate` (UNTOUCHED)  
✅ New certificates go to: `certificates_advancedcertificate` (NEW TABLE)  
✅ Different URLs: `/create/` vs `/advanced/certificates/create/`  
✅ Different templates, different views, different everything  
✅ Only added 6 new columns to Role table (all default: FALSE)

**If anything breaks, run: `./ROLLBACK_ADVANCED_SYSTEM.sh`**

---

## 📍 What Files Were Changed?

### **New Files** (won't affect existing system):
```
certificates/constants.py
certificates/models_advanced.py
certificates/forms_advanced.py
certificates/views_advanced.py
certificates/views_advanced_template.py
certificates/advanced_generator.py
certificates/templates/advanced/*.html
create_advanced_role.py
SETUP_ADVANCED_SYSTEM.sh
ROLLBACK_ADVANCED_SYSTEM.sh
check_advanced_setup.py
```

### **Modified Files** (backward compatible):
```
certificates/models_role.py          ← Added 6 permission fields
certificates/urls.py                 ← Added /advanced/* URLs
certificates/views.py                ← Updated validate() function
templates/new_template/sidebar.html  ← Added menu items
```

**Everything else is UNTOUCHED!**

---

## 🎨 How To Create An Advanced Template?

1. Go to: `/advanced/templates/create/`
2. **Step 1:** Upload PDF + name it
3. **Step 2:** Check which fields you want (from 15 available)
4. **Step 3:** Enter example data for preview
5. **Step 4:** Position fields on PDF + choose fonts/colors
6. **Step 5:** Save!

Done! Now you can create certificates using that template.

---

## 📧 How To Send Advanced Certificates?

1. Go to: `/advanced/certificates/create/`
2. Select template
3. **Option A:** Fill form manually (single certificate)
4. **Option B:** Upload Excel (bulk certificates)
5. Click "إنشاء وإرسال"

Certificates will be generated and emailed automatically!

---

## 🔍 Verification Works For Both!

The same URL validates both types:
```
/validate/?hash=YOUR_CERTIFICATE_HASH
```

- If it's an old certificate → Shows old template
- If it's a new advanced certificate → Shows new advanced template
- Magic! ✨

---

## 🚨 Emergency Rollback

If something goes wrong:
```bash
./ROLLBACK_ADVANCED_SYSTEM.sh
```
Type `YES` and everything reverts. Your old system is 100% safe.

---

## 📞 Need Help?

Run this to check everything is installed correctly:
```bash
python check_advanced_setup.py
```

Should show all green checkmarks ✓

---

## 🎉 That's It!

Your old system: **Working perfectly** ✅  
Your new system: **Ready to use** ✅  

No conflicts. No data loss. Both work in parallel.

**Now go create some amazing KKUx certificates!** 🎓

---

**Questions? Just ask! But first, run the setup script.** 😊

