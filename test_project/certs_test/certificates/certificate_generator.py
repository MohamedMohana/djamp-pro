import os
import json
from io import BytesIO
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.pdfbase.ttfonts import TTFont
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import landscape
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase.pdfmetrics import stringWidth
import socket

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_qr_code(data, x, y, size, c, rotation_angle=0):
    qr_code = qr.QrCodeWidget(data)
    qr_code.barWidth = size
    qr_code.barHeight = size

    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    d = Drawing(width, height, transform=[size / width, 0, 0, size / height, 0, 0])
    d.add(qr_code)

    c.saveState()  # Save the current state of the canvas
    c.translate(x + size / 2, y + size / 2)  # Move the origin to the center of where the QR code will be
    c.rotate(rotation_angle)  # Rotate the canvas by the specified angle
    renderPDF.draw(d, c, -size / 2, -size / 2)  # Draw the QR code centered at the new origin
    c.restoreState()  # Restore the canvas to its previous state

def adjust_for_rtl(canvas, text, x, y, font_name, font_size):
    text_width = stringWidth(text, font_name, font_size)
    canvas.drawString(x-text_width, y, text)

def generate_certificate(name, course_name, date_text, hash_value, template_name, output_file):
    # Get the template and config
    if template_name == 'temp_template':
        template_path = os.path.join(BASE_DIR, 'media/preview/temp_template.pdf')
        config_path = os.path.join(BASE_DIR, 'media/preview/temp_template.json')
    else:
        # First try to get the template from the database
        from .models_template import CertificateTemplate
        try:
            # Try exact match first
            template_obj = CertificateTemplate.objects.get(name=template_name)
        except CertificateTemplate.DoesNotExist:
            try:
                # Try with spaces replaced by underscores
                template_obj = CertificateTemplate.objects.get(name=template_name.replace(' ', '_'))
            except CertificateTemplate.DoesNotExist:
                # Try with Arabic characters normalized
                clean_name = template_name.replace(' ', '_').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
                try:
                    template_obj = CertificateTemplate.objects.get(name=clean_name)
                except CertificateTemplate.DoesNotExist:
                    raise Exception(f"القالب غير موجود: {template_name}")
        
        # Get the template file path from the model
        template_path = os.path.join(BASE_DIR, 'media', str(template_obj.pdf_file))
        config_path = os.path.splitext(template_path)[0] + '.json'
        
        # Verify files exist
        if not os.path.exists(template_path):
            raise Exception("ملف القالب غير موجود")
            
        if not os.path.exists(config_path):
            raise Exception("ملف إعدادات القالب غير موجود")
        
        # print(f"Using template path: {template_path}")
        # print(f"Using config path: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        return

    try:
        template_pdf = PdfReader(template_path).pages[0]
    except Exception as e:
        return

    # Set up the canvas
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=landscape(A4))

    # Register the custom font specified in the config file
    font_name = config.get('font_name')
    if not font_name:
        return

    # Try to find the font file
    font_file = None
    for ext in ['.ttf']:  # Only use TTF fonts as OTF is not supported
        test_file = f"{font_name}{ext}"
        test_path = os.path.join(BASE_DIR, 'certificates/fonts', test_file)
        if os.path.exists(test_path):
            font_file = test_file
            break
    
    if not font_file:
        # If font not found, use default font
        font_name = 'din-next-lt-w23-bold'
        font_file = 'din-next-lt-w23-bold.ttf'
    
    font_path = os.path.join(BASE_DIR, 'certificates/fonts', font_file)
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    except Exception as e:
        # Use default font as fallback
        font_name = 'din-next-lt-w23-bold'
        font_file = 'din-next-lt-w23-bold.ttf'
        font_path = os.path.join(BASE_DIR, 'certificates/fonts', font_file)
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception as e:
            return

    # Reshape and reverse the Arabic text for correct display
    reshaped_name = arabic_reshaper.reshape(name)
    bidi_name = get_display(reshaped_name)
    reshaped_course_name = arabic_reshaper.reshape(course_name)
    bidi_course_name = get_display(reshaped_course_name)
    reshaped_date_text = arabic_reshaper.reshape(date_text)
    bidi_date_text = get_display(reshaped_date_text)

    font_name = config['font_name']
    font_color = [color / 255 for color in config['font_color']]

    # Add the name
    name_config = config['name']
    c.setFont(font_name, name_config['font_size'])
    c.setFillColorRGB(*font_color)  # change the font color
    adjust_for_rtl(c, bidi_name, name_config['x'] * cm, name_config['y'] * cm, font_name, name_config['font_size'])

    # Add the course name
    course_name_config = config['course_name']
    c.setFont(font_name, course_name_config['font_size'])
    c.setFillColorRGB(*font_color)  # change the font color
    adjust_for_rtl(c, bidi_course_name, course_name_config['x'] * cm, course_name_config['y'] * cm, font_name, course_name_config['font_size'])

    # Add the date text
    date_text_config = config['date_text']
    c.setFont(font_name, date_text_config['font_size'])
    c.setFillColorRGB(*font_color)  # change the font color
    adjust_for_rtl(c, bidi_date_text, date_text_config['x'] * cm, date_text_config['y'] * cm, font_name, date_text_config['font_size'])

    # Add a QR code with the certificate's hash
    qr_code_config = config['qr_code']
    if hash_value != 'preview':
        domain_name = 'certs.kku.edu.sa'
        url = f"http://{domain_name}/validate?hash={hash_value}"
    else:
        url = "Preview"
    generate_qr_code(url, qr_code_config['x'] * cm, qr_code_config['y'] * cm, qr_code_config['size'] * cm, c, qr_code_config['rotation_angle'])

    # Save the PDF in memory
    c.save()

    # Move to the beginning of the StringIO buffer
    packet.seek(0)

    # Create a new PDF with ReportLab
    new_pdf = PdfReader(packet)

    # Merge the new PDF with the template
    merged_page = PageMerge(template_pdf).add(new_pdf.pages[0]).render()

    # Save the merged PDF to a file
    writer = PdfWriter()
    writer.addPage(merged_page)
    with open(output_file, "wb") as f:
        writer.write(f)