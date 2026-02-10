"""
Advanced Certificate Generator for KKUx
Supports dynamic fields, multiple languages (RTL/LTR), and per-field styling
"""
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_qr_code(data, x, y, size, c, rotation_angle=0):
    """Generate and draw QR code on canvas"""
    qr_code = qr.QrCodeWidget(data)
    qr_code.barWidth = size
    qr_code.barHeight = size

    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    d = Drawing(width, height, transform=[size / width, 0, 0, size / height, 0, 0])
    d.add(qr_code)

    c.saveState()
    c.translate(x + size / 2, y + size / 2)
    c.rotate(rotation_angle)
    renderPDF.draw(d, c, -size / 2, -size / 2)
    c.restoreState()


def adjust_for_rtl(canvas, text, x, y, font_name, font_size, anchor='right'):
    """Draw RTL text with controllable anchoring"""
    text_width = stringWidth(text, font_name, font_size)
    if anchor == 'left':
        canvas.drawString(x, y, text)
    elif anchor == 'center':
        canvas.drawString(x - (text_width / 2.0), y, text)
    else:
        canvas.drawString(x - text_width, y, text)


def adjust_for_ltr(canvas, text, x, y, font_name, font_size):
    """Draw LTR text normally"""
    canvas.drawString(x, y, text)


def hex_to_rgb(hex_color):
    """Convert hex color (#RRGGBB) to RGB list [0-1 range]"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return [r, g, b]
    return [0, 0, 0]  # Default to black


def register_fonts():
    """Register all available fonts"""
    fonts_dir = os.path.join(BASE_DIR, 'certificates/fonts')
    
    # Available fonts mapping
    font_files = {
        'IBM_Plex_Sans_Arabic_Bold': 'IBMPlexSansArabic-Bold.ttf',
        'IBM_Plex_Sans_Arabic_Regular': 'IBMPlexSansArabic-Regular.ttf',
        'din-next-lt-w23-bold': 'din-next-lt-w23-bold.ttf',
        'GESS': 'GESS.ttf',
        'Bressay-Bold': 'Bressay-Bold.ttf',
        'majallab': 'majallab.ttf',
    }
    
    for font_name, font_file in font_files.items():
        font_path = os.path.join(fonts_dir, font_file)
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            except Exception as e:
                print(f"Warning: Could not register font {font_name}: {e}")


def generate_advanced_certificate(certificate_data, hash_value, template, output_file):
    """
    Generate an advanced certificate with dynamic fields
    
    Args:
        certificate_data (dict): Dictionary of field values
        hash_value (str): Unique hash for the certificate
        template (AdvancedCertificateTemplate): Template object
        output_file (str): Path where PDF should be saved
    """
    # Get template path
    template_path = template.pdf_file.path
    
    # Verify template exists
    if not os.path.exists(template_path):
        raise Exception("ملف القالب غير موجود")
    
    # Load template PDF
    try:
        template_pdf = PdfReader(template_path).pages[0]
    except Exception as e:
        raise Exception(f"خطأ في قراءة ملف PDF للقالب: {str(e)}")
    
    # Determine template page size
    media_box = getattr(template_pdf, 'MediaBox', None)
    if media_box and len(media_box) >= 4:
        try:
            page_width = float(media_box[2]) - float(media_box[0])
            page_height = float(media_box[3]) - float(media_box[1])
        except (TypeError, ValueError):
            page_width, page_height = landscape(A4)
    else:
        page_width, page_height = landscape(A4)
    
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    page_width_cm = page_width / cm
    page_height_cm = page_height / cm
    
    # DEBUG: Print page dimensions
    print(f"\n{'='*60}")
    print(f"DEBUG: PDF Generation - Certificate: {hash_value}")
    print(f"{'='*60}")
    print(f"Page dimensions: {page_width/cm:.2f}cm x {page_height/cm:.2f}cm")
    
    # Register fonts
    register_fonts()
    
    # Get template configuration
    active_fields = template.active_fields
    field_settings = template.field_settings
    qr_settings = template.qr_settings
    
    # Draw each active field
    for field_name, is_active in active_fields.items():
        if not is_active:
            continue
        
        # Get field value
        field_value = certificate_data.get(field_name, '')
        if not field_value:
            continue
        
        # Get field settings
        settings = field_settings.get(field_name, {})
        if not settings.get('enabled', True):
            continue
        
        designer_width_cm = settings.get('base_width_cm', page_width_cm) or page_width_cm
        designer_height_cm = settings.get('base_height_cm', page_height_cm) or page_height_cm
        designer_width_px = settings.get('base_width_px')
        designer_height_px = settings.get('base_height_px')
        x_cm_raw = settings.get('x', 15)
        y_cm_raw = settings.get('y', 10)
        x_px_raw = settings.get('x_px')
        y_px_raw = settings.get('y_px')
        box_width_px = settings.get('box_width_px')
        box_height_px = settings.get('box_height_px')
        font_size_px_stored = settings.get('font_size_px')
        adjusted_x_cm = None
        if x_px_raw is not None and designer_width_px:
            adjusted_x_cm = (x_px_raw / designer_width_px) * page_width_cm
        else:
            scale_x = page_width_cm / designer_width_cm if designer_width_cm else 1
            adjusted_x_cm = x_cm_raw * scale_x
        if y_px_raw is not None and designer_height_px:
            adjusted_y_cm = (y_px_raw / designer_height_px) * page_height_cm
        else:
            scale_y = page_height_cm / designer_height_cm if designer_height_cm else 1
            adjusted_y_cm = y_cm_raw * scale_y
        x = adjusted_x_cm * cm
        base_font_px = settings.get('font_size', 18)
        font_size_px = font_size_px_stored if font_size_px_stored is not None else base_font_px
        if font_size_px_stored is not None and designer_height_px:
            font_height_cm = (font_size_px_stored / designer_height_px) * page_height_cm
            font_size = font_height_cm * (72.0 / 2.54)
        else:
            font_size = font_size_px * (72.0 / 96.0)
        font_name = settings.get('font_name', 'IBM_Plex_Sans_Arabic_Regular')
        font_color = settings.get('font_color', '#000000')
        text_direction = settings.get('text_direction', 'rtl')
        text_anchor = settings.get('text_anchor', 'left')
        
        y_from_top = adjusted_y_cm * cm
        try:
            font_ascent = pdfmetrics.getAscent(font_name)
        except Exception:
            font_ascent = None
        ascent_points = ((font_ascent or 800) / 1000.0) * font_size
        y_with_baseline = y_from_top + ascent_points
        y = page_height - y_with_baseline
        
        print(f"\n--- Field: {field_name} ---")
        if x_px_raw is not None and designer_width_px:
            print(f"  X from left: {adjusted_x_cm:.2f}cm (designer_px {x_px_raw:.2f} / width_px {designer_width_px:.2f})")
        else:
            print(f"  X from left: {adjusted_x_cm:.2f}cm (designer {x_cm_raw:.2f}cm)")
        if y_px_raw is not None and designer_height_px:
            print(f"  Y from top: {adjusted_y_cm:.2f}cm → Y from bottom: {y/cm:.2f}cm (designer_px {y_px_raw:.2f} / height_px {designer_height_px:.2f})")
        else:
            print(f"  Y from top: {adjusted_y_cm:.2f}cm → Y from bottom: {y/cm:.2f}cm (designer {y_cm_raw:.2f}cm)")
        # Set font and color
        try:
            c.setFont(font_name, font_size)
        except Exception:
            # Fallback to default font
            font_name = 'IBM_Plex_Sans_Arabic_Regular'
            c.setFont(font_name, font_size)
        
        # Set color
        rgb = hex_to_rgb(font_color)
        c.setFillColorRGB(*rgb)
        
        # Process text based on direction
        anchor_override = text_anchor
        if text_direction == 'rtl':
            if (box_width_px is not None and designer_width_px and
                    x_px_raw is not None):
                right_px = x_px_raw + box_width_px
                adjusted_x_cm = (right_px / designer_width_px) * page_width_cm
                x = adjusted_x_cm * cm
                anchor_override = 'right'
            # Arabic text - reshape and apply bidi
            reshaped_text = arabic_reshaper.reshape(str(field_value))
            bidi_text = get_display(reshaped_text)
            adjust_for_rtl(c, bidi_text, x, y, font_name, font_size, anchor=anchor_override)
        else:
            # LTR text (English)
            if anchor_override == 'center':
                text_width = stringWidth(str(field_value), font_name, font_size)
                adjust_for_ltr(c, str(field_value), x - (text_width / 2.0), y, font_name, font_size)
            elif anchor_override == 'right':
                text_width = stringWidth(str(field_value), font_name, font_size)
                adjust_for_ltr(c, str(field_value), x - text_width, y, font_name, font_size)
            else:
                adjust_for_ltr(c, str(field_value), x, y, font_name, font_size)
    
    # Add QR code
    qr_base_width = qr_settings.get('base_width_cm', page_width_cm) if qr_settings else page_width_cm
    qr_base_height = qr_settings.get('base_height_cm', page_height_cm) if qr_settings else page_height_cm
    qr_base_width_px = qr_settings.get('base_width_px') if qr_settings else None
    qr_base_height_px = qr_settings.get('base_height_px') if qr_settings else None
    qr_scale_x = page_width_cm / qr_base_width if qr_base_width else 1
    qr_scale_y = page_height_cm / qr_base_height if qr_base_height else 1
    if qr_settings and qr_settings.get('x_px') is not None and qr_base_width_px:
        qr_x = (qr_settings.get('x_px') / qr_base_width_px) * page_width_cm * cm
    else:
        qr_x = (qr_settings.get('x', 6.9) * qr_scale_x) * cm if qr_settings else 6.9 * cm
    if qr_settings and qr_settings.get('y_px') is not None and qr_base_height_px:
        qr_y_from_top = (qr_settings.get('y_px') / qr_base_height_px) * page_height_cm * cm
    else:
        qr_y_from_top = (qr_settings.get('y', 1.2) * qr_scale_y) * cm if qr_settings else 1.2 * cm
    if qr_settings and qr_settings.get('size_px') is not None and qr_base_width_px:
        qr_size = (qr_settings.get('size_px') / qr_base_width_px) * page_width_cm * cm
    else:
        qr_size = (qr_settings.get('size', 5) * qr_scale_x) * cm if qr_settings else 5 * cm
    qr_rotation = qr_settings.get('rotation_angle', 0) if qr_settings else 0
    qr_y = page_height - qr_y_from_top - qr_size
    
    print(f"\n--- QR Code ---")
    if qr_settings and qr_settings.get('x_px') is not None and qr_base_width_px:
        print(f"  X from left: {qr_x/cm:.2f}cm (designer_px {qr_settings.get('x_px'):.2f} / width_px {qr_base_width_px:.2f})")
    else:
        print(f"  X from left: {qr_x/cm:.2f}cm (designer {qr_settings.get('x', 6.9) if qr_settings else 6.9:.2f}cm)")
    if qr_settings and qr_settings.get('y_px') is not None and qr_base_height_px:
        print(f"  Y from top: {qr_y_from_top/cm:.2f}cm → Y from bottom: {qr_y/cm:.2f}cm (designer_px {qr_settings.get('y_px'):.2f} / height_px {qr_base_height_px:.2f})")
    else:
        print(f"  Y from top: {qr_y_from_top/cm:.2f}cm → Y from bottom: {qr_y/cm:.2f}cm (designer {qr_settings.get('y', 1.2) if qr_settings else 1.2:.2f}cm)")
    print(f"{'='*60}\n")
    
    if hash_value != 'preview':
        domain_name = 'certs.kku.edu.sa'
        url = f"https://{domain_name}/validate?hash={hash_value}"
    else:
        url = "https://certs.kku.edu.sa/validate"
    
    try:
        generate_qr_code(url, qr_x, qr_y, qr_size, c, qr_rotation)
    except Exception as e:
        print(f"QR Code generation error: {e}")
    
    # Save the PDF in memory
    c.save()
    
    # Move to the beginning of the BytesIO buffer
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

