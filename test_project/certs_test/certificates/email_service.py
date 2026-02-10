# # import sys
# # sys.path.append('/u01/workspace/APP/blockchain_ar/blockchain_certificates/')

# # from blockchain_certificates import settings


# import os
# import sys
# # Get the current directory of sentemail.py
# current_dir = os.path.dirname(os.path.abspath(__file__))
# # Get the path to the parent directory of sentemail.py
# parent_dir = os.path.dirname(current_dir)
# # Append the parent directory to the system path
# sys.path.append(parent_dir)
# # Import the Django settings
# from blockchain_certificates import settings



# import requests
# import base64

# # def send_email(to, subject, email_body, attachment_path):
# #     try:
# #         with open(attachment_path, "rb") as file:
# #             encoded_content = base64.b64encode(file.read()).decode()

# #         data = {
# #             "wsUsername": settings.KKU_SERVICES_USER,
# #             "wsPassword": settings.KKU_SERVICES_PASS,
# #             "emailFrom": settings.KKU_SERVICES_EMAIL_FROM,
# #             "emailTo": to,
# #             "subject": subject,
# #             "emailBody": email_body,
# #             "attachFile": encoded_content,
# #             "attachName": "Certificate.pdf"
# #         }

# #         #print("Sending email...")
# #         response = requests.post(settings.KKU_SERVICES_EMAIL_SEND_URL, json=data)

# #         if response.status_code != 200:
# #             print("Error sending email:")
# #             print(response.text)
# #             raise Exception("Error sending email: " + response.text)

# #         #print("Email sent successfully!")
# #     except Exception as e:
# #         print("Error: " + str(e))

# # Usage
# #send_email("mmuhanna@kku.edu.sa", "Test Subject", "Test body", "/u01/workspace/APP/blockchain_ar/blockchain_certificates/media/381826559af7b1f6f320c2ed7f72c0cd4b21c0b6a60249cfefcee605a3316e6e.pdf")





# def send_email(to, subject, email_body, attachment_path):
#     try:
#         with open(attachment_path, "rb") as file:
#             encoded_content = base64.b64encode(file.read()).decode()

#         data = {
#             "wsUsername": settings.KKU_SERVICES_USER,
#             "wsPassword": settings.KKU_SERVICES_PASS,
#             "emailFrom": settings.KKU_SERVICES_EMAIL_FROM,
#             "emailTo": to,
#             "subject": subject,
#             "emailBody": email_body,
#             "attachFile": encoded_content,
#             "attachName": "Certificate.pdf"
#         }

#         response = requests.post(settings.KKU_SERVICES_EMAIL_SEND_URL, json=data)

#         if response.status_code != 200:
#             print("Error sending email:")
#             print(response.text)
#             raise Exception("Error sending email: " + response.text)

#         return True

#     except Exception as e:
#         print("Error: " + str(e))
#         return False





import os
import sys
import base64
import requests
# import logging
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from blockchain_certificates import settings

# logger = logging.getLogger(__name__)

def send_email(to, subject, attachment_path, course_name, certificate_link, name, custom_message=None, certificate_hash=None):
    try:
        # Load and render HTML email template
        email_html = render_to_string('emails/certificate_email.html', {
            'name': name,
            'course_name': course_name,
            'certificate_link': certificate_link,
            'custom_message': custom_message,
            'certificate_hash': certificate_hash,
        })

        # Convert HTML email to plain text (some email clients may use this)
        email_plain = strip_tags(email_html)

        # Attach the certificate file
        with open(attachment_path, "rb") as file:
            encoded_content = base64.b64encode(file.read()).decode()

        data = {
            "wsUsername": settings.KKU_SERVICES_USER,
            "wsPassword": settings.KKU_SERVICES_PASS,
            "emailFrom": settings.KKU_SERVICES_EMAIL_FROM,
            "emailTo": to,
            "subject": subject,
            "emailBody": email_html,  # Send HTML content
            "attachFile": encoded_content,
            "attachName": "Certificate.pdf"
        }

        response = requests.post(settings.KKU_SERVICES_EMAIL_SEND_URL, json=data)

        if response.status_code != 200:
            # logger.error(f"Failed to send email to {to}: {response.text}")
            return False

        # logger.info(f"Email successfully sent to {to}")
        return True

    except Exception as e:
        # logger.error(f"Error sending email to {to}: {str(e)}")
        return False


def send_role_notification_email(profile, old_roles):
    """Send professional email notification for role assignment
    
    Args:
        profile: UserProfile instance
        old_roles: List of Role instances (previous roles) or a single Role instance for backwards compatibility
    """
    try:
        # Check if user has email
        if not profile.user.email:
            return False
            
        from django.utils import timezone
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        import datetime
        
        # Handle both old single role and new multiple roles format
        if old_roles is not None and not isinstance(old_roles, (list, tuple)):
            # Backwards compatibility: single role passed
            old_roles = [old_roles] if old_roles else []
        old_roles = old_roles or []
        
        # Calculate duration text
        is_temporary = profile.role_start_date and profile.role_end_date
        if is_temporary:
            duration = profile.role_end_date - profile.role_start_date
            if duration.days >= 30:
                months = duration.days // 30
                duration_text = f"{months} شهر" if months == 1 else f"{months} أشهر"
            else:
                duration_text = f"{duration.days} يوم"
        else:
            duration_text = "دائم"
        
        # Format dates in Arabic
        start_date_formatted = profile.role_start_date.strftime("%d/%m/%Y - %H:%M") if profile.role_start_date else ""
        end_date_formatted = profile.role_end_date.strftime("%d/%m/%Y - %H:%M") if profile.role_end_date else ""
        
        # Get current roles
        current_roles = list(profile.roles.all())
        new_roles_text = ', '.join([r.name_ar for r in current_roles]) if current_roles else 'غير محدد'
        previous_roles_text = ', '.join([r.name_ar for r in old_roles]) if old_roles else 'غير محدد'
        
        # Prepare email context
        context = {
            'name': profile.user.get_full_name() or profile.user.username,
            'new_role': new_roles_text,  # Now shows all current roles
            'previous_role': previous_roles_text,  # Now shows all previous roles
            'supervisor_organization': profile.supervisor_organization,
            'start_date': start_date_formatted,
            'end_date': end_date_formatted,
            'duration_text': duration_text,
            'is_temporary': is_temporary,
            'certificate_system_url': 'https://certs.kku.edu.sa/',
        }
        
        # Load and render HTML email template
        email_html = render_to_string('emails/role_notification_email.html', context)
        
        # Create email subject
        subject = f"إشعار تغيير الصلاحية - {new_roles_text}"
        
        # Create a dummy PDF file content as base64 encoded string
        dummy_pdf_content = "%PDF-1.4\n%âãÏÓ\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 35\n>>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Role Notification) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000018 00000 n \n0000000077 00000 n \n0000000178 00000 n \n0000000457 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n565\n%%EOF"
        encoded_content = base64.b64encode(dummy_pdf_content.encode('utf-8')).decode('utf-8')

        # Send email with dummy PDF attachment (KKU service requires attachment)
        data = {
            "wsUsername": settings.KKU_SERVICES_USER,
            "wsPassword": settings.KKU_SERVICES_PASS,
            "emailFrom": settings.KKU_SERVICES_EMAIL_FROM,
            "emailTo": profile.user.email,
            "subject": subject,
            "emailBody": email_html,
            "attachFile": encoded_content,  # Dummy PDF content
            "attachName": "role_notification.pdf"  # Dummy attachment name
        }
        
        response = requests.post(settings.KKU_SERVICES_EMAIL_SEND_URL_NO_ATTACHMENT, json=data)
        
        if response.status_code != 200:
            return False
            
        return True
        
    except Exception as e:
        return False