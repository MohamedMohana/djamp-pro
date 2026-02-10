from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'certificates'

    # To add user directly as a normal user
    def ready(self):
        import certificates.signals  # Registers the signal handlers
