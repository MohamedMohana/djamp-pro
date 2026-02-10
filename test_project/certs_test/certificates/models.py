from django.db import models, IntegrityError
import hashlib
from django.utils.crypto import get_random_string
import json
from django.conf import settings
from django.contrib.auth.models import User
from .models_template import CertificateTemplate
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

def generate_hash():
    return get_random_string(64)

class Certificate(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=300)
    course_name = models.CharField(max_length=200)
    duration = models.CharField(max_length=200)
    date = models.DateField(auto_now_add=True)
    hash_value = models.CharField(max_length=64, unique=True)
    certificate_hash = models.CharField(max_length=64, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    def get_latest_block(self):
        try:
            return self.block_set.latest('timestamp')
        except Block.DoesNotExist:
            return None

    def certificate_date(self):
        return self.date.strftime('%Y-%m-%d')

    def __str__(self):
        return f"{self.name} - {self.course_name}"

class Block(models.Model):
    index = models.IntegerField()
    timestamp = models.IntegerField()
    data = models.TextField()
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, editable=False)
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, default=None)
    certificate_hash = models.CharField(max_length=64, null=True)
    output_file = models.FilePathField(
        path=settings.MEDIA_ROOT,
        null=True
    )

    def compute_hash(self):
        block_string = f"{self.index}{self.timestamp}{self.data}{self.previous_hash}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def save(self, *args, **kwargs):
        self.hash = self.compute_hash()
        super().save(*args, **kwargs)
        self.certificate.certificate_hash = self.hash
        self.certificate.save()

    def __str__(self):
        return f"Block {self.index}: {self.hash}"

@receiver(post_delete, sender=Certificate)
def delete_certificate_pdf(sender, instance, **kwargs):
    """ Delete the certificate PDF when the certificate record is deleted. """
    certificate_hash = instance.certificate_hash
    file_name = f'{certificate_hash}.pdf'
    file_path = os.path.join(settings.MEDIA_ROOT, file_name)

    if os.path.exists(file_path):
        os.remove(file_path)




class UserDetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='details')
    sessionIndex = models.CharField(max_length=256)
    userid = models.CharField(max_length=100)  # Assuming this is the `nationalId` or equivalent
    arabicName = models.CharField(max_length=100)
    arabicFirstName = models.CharField(max_length=100)
    arabicFatherName = models.CharField(max_length=100)
    arabicGrandFatherName = models.CharField(max_length=100)
    arabicFamilyName = models.CharField(max_length=100)
    englishName = models.CharField(max_length=100)
    englishFirstName = models.CharField(max_length=100)
    englishFatherName = models.CharField(max_length=100)
    englishGrandFatherName = models.CharField(max_length=100)
    englishFamilyName = models.CharField(max_length=100)
    nationalityCode = models.CharField(max_length=50)
    arabicNationality = models.CharField(max_length=50)
    nationality = models.CharField(max_length=50)
    dob = models.DateField()
    dobHijri = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    lang = models.CharField(max_length=50)
    preferredLang = models.CharField(max_length=50)
    idVersionNo = models.CharField(max_length=50)
    idExpiryDateHijri = models.DateField()
    idExpiryDateGregorian = models.DateField()
    iqamaExpiryDateHijri = models.DateField()
    iqamaExpiryDateGregorian = models.DateField()
    cardIssueDateHijri = models.DateField()
    cardIssueDateGregorian = models.DateField()
    issueLocationAr = models.CharField(max_length=100)
    issueLocationEn = models.CharField(max_length=100)
    iam_login = models.BooleanField(default=False)

    def __str__(self):
        return self.arabicName