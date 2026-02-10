from django.core.management.base import BaseCommand
from django.utils import timezone
from certificates.models_role import UserProfile
from certificates.email_service import send_role_notification_email


class Command(BaseCommand):
    help = 'Check for expired temporary roles and revert them to previous roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Find all profiles with temporary roles that have expired
        expired_profiles = UserProfile.objects.filter(
            is_temporary_role=True,
            role_end_date__lt=timezone.now()
        ).select_related('user').prefetch_related('roles', 'previous_roles')

        if not expired_profiles.exists():
            self.stdout.write(
                self.style.SUCCESS('No expired temporary roles found.')
            )
            return

        expired_count = 0
        for profile in expired_profiles:
            try:
                # Get current and previous roles for display
                current_roles = list(profile.roles.all())
                previous_roles = list(profile.previous_roles.all())
                current_names = ', '.join([r.name_ar for r in current_roles]) if current_roles else "No role"
                previous_names = ', '.join([r.name_ar for r in previous_roles]) if previous_roles else "No role"
                
                if dry_run:
                    self.stdout.write(
                        f'Would expire role for user: {profile.user.get_full_name()} '
                        f'({profile.user.username}) - '
                        f'{current_names} → {previous_names}'
                    )
                else:
                    # Store details for logging
                    username = profile.user.username
                    user_full_name = profile.user.get_full_name()
                    expired_roles = current_roles
                    
                    # Check and expire the role
                    expired_roles_result = profile.check_and_expire_role()
                    
                    if expired_roles_result:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Expired role for user: {user_full_name} ({username}) - '
                                f'{current_names} → {previous_names}'
                            )
                        )
                        
                        # Send notification email about role expiry
                        try:
                            self._send_role_expiry_notification(profile, expired_roles, previous_roles)
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Failed to send expiry notification email to {username}: {str(e)}'
                                )
                            )
                        
                        expired_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Role for user {username} was not expired (check failed)'
                            )
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error processing user {profile.user.username}: {str(e)}'
                    )
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed {expired_count} expired roles.'
                )
            )

    def _send_role_expiry_notification(self, profile, expired_roles, reverted_roles):
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
            self.stdout.write(
                self.style.WARNING(f'Failed to send expiry notification: {str(e)}')
            )
            return False