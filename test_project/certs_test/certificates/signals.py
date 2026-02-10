# # To add user directly as a normal user
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.contrib import messages
from certificates.models_role import UserProfile, Role
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            default_role = Role.objects.get(name_en='user')
        except Role.DoesNotExist:
            default_role = None  # Or handle appropriately if the role is missing
        profile = UserProfile.objects.create(user=instance)
        # Add default role to the new M2M roles field
        if default_role:
            profile.roles.add(default_role)
            # Also set legacy role field for backwards compatibility during migration
            profile.role = default_role
            profile.save()

@receiver(user_logged_in)
def check_user_role_expiry(sender, request, user, **kwargs):
    """
    Check if user's temporary role has expired when they log in.
    This is the most efficient approach - only check when needed.
    """
    try:
        # Only check if user has a profile
        if not hasattr(user, 'profile'):
            return
            
        profile = user.profile
        
        # Check if the role has expired
        if profile.is_temporary_role and profile.is_role_expired():
            # Store the expired roles for notification
            expired_roles = list(profile.roles.all())
            previous_roles = list(profile.previous_roles.all())
            
            # Expire the role and revert to previous
            profile.check_and_expire_role()
            
            # Add a user-friendly message
            if expired_roles:
                expired_names = ', '.join([r.name_ar for r in expired_roles])
                previous_names = ', '.join([r.name_ar for r in previous_roles]) if previous_roles else "المستخدم العادي"
                messages.info(
                    request, 
                    f'تم انتهاء صلاحيتكم المؤقتة "{expired_names}" وتم إرجاعكم إلى "{previous_names}"'
                )
            
            # Send email notification in the background
            try:
                _send_role_expiry_notification(profile, expired_roles, previous_roles)
            except Exception as e:
                logger.warning(f'Failed to send role expiry notification: {e}')
            
            expired_names = ', '.join([r.name_ar for r in expired_roles]) if expired_roles else "No role"
            previous_names = ', '.join([r.name_ar for r in previous_roles]) if previous_roles else "No role"
            logger.info(
                f'Expired role for user: {user.get_full_name()} ({user.username}) - '
                f'{expired_names} → {previous_names}'
            )
                
    except Exception as e:
        logger.error(f'Error checking role expiry for user {user.username}: {e}')
        # Don't break the login process if there's an error

def _send_role_expiry_notification(profile, expired_roles, reverted_roles):
    """Send email notification about role expiry
    
    Args:
        profile: UserProfile instance
        expired_roles: List of Role instances that expired
        reverted_roles: List of Role instances to revert to
    """
    try:
        from django.template.loader import render_to_string
        from django.conf import settings
        import requests
        
        # Handle both list and single role for backwards compatibility
        if expired_roles and not isinstance(expired_roles, (list, tuple)):
            expired_roles = [expired_roles]
        if reverted_roles and not isinstance(reverted_roles, (list, tuple)):
            reverted_roles = [reverted_roles]
        
        expired_names = ', '.join([r.name_ar for r in expired_roles]) if expired_roles else 'غير محدد'
        reverted_names = ', '.join([r.name_ar for r in reverted_roles]) if reverted_roles else 'مستخدم عادي'
        
        # Prepare email context
        context = {
            'name': profile.user.get_full_name() or profile.user.username,
            'expired_role': expired_names,
            'current_role': reverted_names,
            'supervisor_organization': profile.supervisor_organization,
            'certificate_system_url': 'https://certs.kku.edu.sa/',
        }
        
        # Load and render HTML email template
        email_html = render_to_string('emails/role_expiry_notification.html', context)
        
        # Create email subject
        subject = f"انتهاء صلاحية مؤقتة - نظام إدارة الشهادات"
        
        # Send email
        data = {
            "wsUsername": settings.KKU_SERVICES_USER,
            "wsPassword": settings.KKU_SERVICES_PASS,
            "emailFrom": settings.KKU_SERVICES_EMAIL_FROM,
            "emailTo": profile.user.email,
            "subject": subject,
            "emailBody": email_html,
        }
        
        response = requests.post(settings.KKU_SERVICES_EMAIL_SEND_URL, json=data)
        return response.status_code == 200
        
    except Exception as e:
        logger.warning(f'Failed to send expiry notification: {e}')
        return False