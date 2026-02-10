from django.db import models
from django.core.validators import FileExtensionValidator
import json
import os

class CertificateTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    pdf_file = models.FileField(
        upload_to='pdf_templates/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    font_name = models.CharField(max_length=100)
    font_color = models.CharField(max_length=20)  # Store as hex color "#RRGGBB"
    name_x = models.FloatField()
    name_y = models.FloatField()
    name_font_size = models.FloatField()
    course_x = models.FloatField()
    course_y = models.FloatField()
    course_font_size = models.FloatField()
    date_x = models.FloatField()
    date_y = models.FloatField()
    date_font_size = models.FloatField()
    qr_x = models.FloatField()
    qr_y = models.FloatField()
    qr_size = models.FloatField()
    qr_rotation = models.FloatField(default=0)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='templates', verbose_name="تم الإنشاء بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_rgb_color(self):
        """Convert hex color to RGB list"""
        color = self.font_color.lstrip('#')
        if len(color) == 6:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            return [r, g, b]
        return [0, 0, 0]  # Default to black if invalid color

    def save(self, *args, **kwargs):
        # Clean the name before saving
        self.name = self.name.replace(' ', '_').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')

        # Ensure unique name by appending a number if necessary
        original_name = self.name
        counter = 1

        while CertificateTemplate.objects.filter(name=self.name).exists():
            self.name = f"{original_name}_{counter}"
            counter += 1        
        
        # Save the model first to handle the file upload
        super().save(*args, **kwargs)
        
        # Generate and save the JSON configuration
        config = {
            "font_name": self.font_name,
            "font_file": f"{self.font_name}.ttf",
            "font_color": self.get_rgb_color(),
            "name": {
                "x": self.name_x,
                "y": self.name_y,
                "font_size": self.name_font_size
            },
            "course_name": {
                "x": self.course_x,
                "y": self.course_y,
                "font_size": self.course_font_size
            },
            "date_text": {
                "x": self.date_x,
                "y": self.date_y,
                "font_size": self.date_font_size
            },
            "qr_code": {
                "x": self.qr_x,
                "y": self.qr_y,
                "size": self.qr_size,
                "rotation_angle": self.qr_rotation
            }
        }

        # Save JSON file next to the PDF template
        pdf_path = self.pdf_file.path
        json_path = os.path.splitext(pdf_path)[0] + '.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def __str__(self):
        return self.name.replace('_', ' ')
        
    def get_display_name(self):
        return self.name.replace('_', ' ')