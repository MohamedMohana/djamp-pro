"""
Transcript Generator for سجل المقررات
Supports dynamic course fields, multiple languages (RTL/LTR), and per-field styling
Based on advanced_generator.py architecture
"""
import os
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
                pass  # Font may already be registered


def generate_transcript(transcript_data, hash_value, template, output_file):
    """
    Generate a transcript with dynamic fields
    
    Args:
        transcript_data (dict): Dictionary of field values
        hash_value (str): Unique hash for the transcript
        template (TranscriptTemplate): Template object
        output_file (str): Path where PDF should be saved
    """
    # Get template path
    template_path = template.pdf_file.path
    
    if not os.path.exists(template_path):
        raise Exception("ملف القالب غير موجود")
    
    try:
        template_pdf = PdfReader(template_path).pages[0]
    except Exception as e:
        raise Exception(f"خطأ في قراءة ملف PDF للقالب: {str(e)}")
    
    # Determine template page size
    # Prefer dimensions from JavaScript (exact match), otherwise read from MediaBox
    if hasattr(template, 'pdf_width_cm') and hasattr(template, 'pdf_height_cm') and \
       template.pdf_width_cm and template.pdf_height_cm:
        # Use exact dimensions from JavaScript
        page_width_cm = float(template.pdf_width_cm)
        page_height_cm = float(template.pdf_height_cm)
        page_width = page_width_cm * cm
        page_height = page_height_cm * cm
    else:
        # Fallback: read from MediaBox
        media_box = getattr(template_pdf, 'MediaBox', None)
        if media_box and len(media_box) >= 4:
            try:
                page_width = float(media_box[2]) - float(media_box[0])
                page_height = float(media_box[3]) - float(media_box[1])
            except (TypeError, ValueError):
                page_width, page_height = landscape(A4)
        else:
            page_width, page_height = landscape(A4)
        page_width_cm = page_width / cm
        page_height_cm = page_height / cm
    
    # Get viewport dimensions if available (for accurate ratio conversion)
    viewport_width_px = getattr(template, 'pdf_width_px', None)
    viewport_height_px = getattr(template, 'pdf_height_px', None)
    
    # Calculate conversion factors from viewport to PDF dimensions
    # These ensure ratios calculated from viewport match exactly with PDF dimensions
    if viewport_width_px and viewport_height_px and page_width_cm and page_height_cm:
        # Calculate pixels per cm based on actual viewport dimensions
        pixels_per_cm_x = viewport_width_px / page_width_cm
        pixels_per_cm_y = viewport_height_px / page_height_cm
    else:
        pixels_per_cm_x = None
        pixels_per_cm_y = None
    
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
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
        
        field_value = transcript_data.get(field_name, '')
        if not field_value:
            continue
        
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

        has_px_metrics = any(
            value is not None and value > 0
            for value in [x_px_raw, y_px_raw, box_width_px, box_height_px, font_size_px_stored]
        )
        
        # Get RATIO values (most accurate positioning method)
        x_ratio = settings.get('x_ratio')
        y_ratio = settings.get('y_ratio')
        width_ratio = settings.get('width_ratio')
        height_ratio = settings.get('height_ratio')
        font_size_ratio = settings.get('font_size_ratio')
        
        # Calculate adjusted X position - prefer ratio, then pixel, then cm
        # Use viewport-based conversion for accuracy
        if x_ratio is not None:
            if pixels_per_cm_x:
                # Convert ratio to pixels using viewport, then to cm
                adjusted_x_px = x_ratio * viewport_width_px
                adjusted_x_cm = adjusted_x_px / pixels_per_cm_x
            else:
                # Fallback: direct ratio multiplication (should work but less accurate)
                adjusted_x_cm = x_ratio * page_width_cm
        elif has_px_metrics and x_px_raw is not None and designer_width_px:
            adjusted_x_cm = (x_px_raw / designer_width_px) * page_width_cm
        else:
            scale_x = page_width_cm / designer_width_cm if designer_width_cm else 1
            adjusted_x_cm = x_cm_raw * scale_x
        
        # Calculate adjusted Y position - prefer ratio, then pixel, then cm
        # Use viewport-based conversion for accuracy
        if y_ratio is not None:
            if pixels_per_cm_y:
                # Convert ratio to pixels using viewport, then to cm
                adjusted_y_px = y_ratio * viewport_height_px
                adjusted_y_cm = adjusted_y_px / pixels_per_cm_y
            else:
                # Fallback: direct ratio multiplication (should work but less accurate)
                adjusted_y_cm = y_ratio * page_height_cm
        elif has_px_metrics and y_px_raw is not None and designer_height_px:
            adjusted_y_cm = (y_px_raw / designer_height_px) * page_height_cm
        else:
            scale_y = page_height_cm / designer_height_cm if designer_height_cm else 1
            adjusted_y_cm = y_cm_raw * scale_y
        
        x = adjusted_x_cm * cm

        effective_width_px = viewport_width_px or designer_width_px
        effective_height_px = viewport_height_px or designer_height_px
        box_width_pt = None
        
        # Calculate box width for RTL adjustment
        if width_ratio is not None and width_ratio > 0:
            if pixels_per_cm_x:
                # Convert ratio to pixels using viewport, then to cm
                box_width_px = width_ratio * viewport_width_px
                box_width_cm = box_width_px / pixels_per_cm_x
            else:
                box_width_cm = width_ratio * page_width_cm
            box_width_pt = box_width_cm * cm
            box_width_px = box_width_cm * (designer_width_px / page_width_cm) if designer_width_px else None
        elif box_width_px is not None and box_width_px > 0 and effective_width_px:
            box_width_pt = (box_width_px / effective_width_px) * page_width
        
        # Calculate font size - prefer ratio, then pixel, then raw
        # NOTE: Font size ratio = fontSize / pdfHeight (both at same scale, so ratio is scale-independent)
        base_font_px = settings.get('font_size', 12)
        
        if font_size_ratio is not None and font_size_ratio > 0:
            # font_size_ratio represents font height as fraction of page height
            # To get font size in points: ratio * page_height_in_points
            page_height_points = page_height_cm * (72.0 / 2.54)
            font_size = font_size_ratio * page_height_points
        elif font_size_px_stored is not None and font_size_px_stored > 0 and designer_height_px:
            # This is effectively the same calculation as ratio
            font_height_cm = (font_size_px_stored / designer_height_px) * page_height_cm
            font_size = font_height_cm * (72.0 / 2.54)
        else:
            # Form input font size is in CSS pixels, convert to points
            font_size_px = font_size_px_stored if font_size_px_stored is not None else base_font_px
            font_size = font_size_px * (72.0 / 96.0)
        
        font_name = settings.get('font_name', 'IBM_Plex_Sans_Arabic_Regular')
        font_color = settings.get('font_color', '#000000')
        text_direction = settings.get('text_direction', 'rtl')
        text_anchor = settings.get('text_anchor', 'left')
        
        # Calculate Y from bottom
        # CRITICAL: In Fabric.js Textbox, 'top' represents the top of the bounding box
        # However, the actual text baseline is typically lower within that box
        # In PDF ReportLab, drawString Y is the BASELINE (bottom of text)
        # Font ascent = how far font extends ABOVE baseline
        # 
        # For Fabric.js Textbox, the 'top' is usually close to the text's visual top
        # To get the baseline, we need to account for the font's ascent
        # But we need to be careful - the top might already account for some of this
        #
        # Testing shows that adding full ascent shifts text down too much
        # So we use a smaller fraction, or the top is already closer to baseline
        y_from_top_pt = adjusted_y_cm * cm
        
        # Fabric.js uses internal heuristics for text metrics (not font metrics),
        # so match its baseline calculation to align step 4 with step 5.
        fabric_font_size_mult = 1.13
        fabric_font_size_fraction = 0.222

        line_box_height_pt = None
        if height_ratio is not None and height_ratio > 0:
            line_box_height_pt = height_ratio * page_height
        elif box_height_px is not None and box_height_px > 0 and effective_height_px:
            line_box_height_pt = (box_height_px / effective_height_px) * page_height

        base_line_height_pt = font_size * fabric_font_size_mult
        if not line_box_height_pt or line_box_height_pt <= 0:
            line_box_height_pt = base_line_height_pt

        leading = line_box_height_pt - base_line_height_pt
        if leading < 0:
            leading = 0
        baseline_offset = (font_size * (1.0 - fabric_font_size_fraction)) + (leading / 2.0)
        y_with_baseline = y_from_top_pt + baseline_offset
        y = page_height - y_with_baseline
        
        # Set font and color
        try:
            c.setFont(font_name, font_size)
        except Exception:
            font_name = 'IBM_Plex_Sans_Arabic_Regular'
            c.setFont(font_name, font_size)
        
        rgb = hex_to_rgb(font_color)
        c.setFillColorRGB(*rgb)
        
        # Process text based on direction
        # CRITICAL: In Fabric.js, for RTL text with textAlign: 'right':
        # - obj.left is the LEFT edge of the bounding box
        # - The text is RIGHT-aligned within the box
        # - So the visual right edge of text is at: left + width
        # For LTR text with textAlign: 'left':
        # - obj.left is where the text STARTS (left edge)
        # - So we use left directly
        
        if text_direction == 'rtl':
            # For RTL text with textAlign: 'right' in Fabric.js:
            # - obj.left is the LEFT edge of the bounding box
            # - The text is RIGHT-aligned within the box
            # - The visual right edge of the text is at: left + width
            # IMPORTANT: We need to use the right edge of the box as the anchor point
            reshaped_text = arabic_reshaper.reshape(str(field_value))
            bidi_text = get_display(reshaped_text)
            actual_text_width = stringWidth(bidi_text, font_name, font_size)
            
            if box_width_pt is not None:
                # The right edge of the box is where the text's right edge aligns in Fabric.js
                # Use this as the anchor point with 'right' anchor
                x_right_edge = x + box_width_pt
                anchor_override = 'right'
            else:
                # No box width - use left + text width as fallback
                x_right_edge = x + actual_text_width
                anchor_override = 'right'
            
            # Use right edge for RTL text to match Fabric.js right-aligned positioning
            adjust_for_rtl(c, bidi_text, x_right_edge, y, font_name, font_size, anchor=anchor_override)
            
        else:
            # LTR text - use left edge directly (text starts at left)
            anchor_override = 'left'
            
            
            # LTR text (English) - draw the text
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

    qr_x_px = qr_settings.get('x_px') if qr_settings else None
    qr_y_px = qr_settings.get('y_px') if qr_settings else None
    qr_size_px = qr_settings.get('size_px') if qr_settings else None
    has_qr_px = any(value is not None and value > 0 for value in [qr_x_px, qr_y_px, qr_size_px])
    
    # Get QR RATIO values
    qr_x_ratio = qr_settings.get('x_ratio') if qr_settings else None
    qr_y_ratio = qr_settings.get('y_ratio') if qr_settings else None
    qr_size_ratio = qr_settings.get('size_ratio') if qr_settings else None
    
    # Calculate QR X position - prefer ratio, then pixel, then cm
    if qr_x_ratio is not None:
        if pixels_per_cm_x:
            # Convert ratio to pixels using viewport, then to cm
            qr_x_px = qr_x_ratio * viewport_width_px
            qr_x_cm = qr_x_px / pixels_per_cm_x
            qr_x = qr_x_cm * cm
        else:
            qr_x = qr_x_ratio * page_width_cm * cm
    elif qr_settings and has_qr_px and qr_x_px is not None and qr_base_width_px:
        qr_x = (qr_x_px / qr_base_width_px) * page_width_cm * cm
    else:
        qr_x = (qr_settings.get('x', 6.9) * qr_scale_x) * cm if qr_settings else 6.9 * cm
    
    # Calculate QR Y position - prefer ratio, then pixel, then cm
    if qr_y_ratio is not None:
        if pixels_per_cm_y:
            # Convert ratio to pixels using viewport, then to cm
            qr_y_px = qr_y_ratio * viewport_height_px
            qr_y_cm = qr_y_px / pixels_per_cm_y
            qr_y_from_top = qr_y_cm * cm
        else:
            qr_y_from_top = qr_y_ratio * page_height_cm * cm
    elif qr_settings and has_qr_px and qr_y_px is not None and qr_base_height_px:
        qr_y_from_top = (qr_y_px / qr_base_height_px) * page_height_cm * cm
    else:
        qr_y_from_top = (qr_settings.get('y', 1.2) * qr_scale_y) * cm if qr_settings else 1.2 * cm
    
    # Calculate QR size - prefer ratio, then pixel, then cm
    if qr_size_ratio is not None and qr_size_ratio > 0:
        # size_ratio is relative to min(width, height) in viewport
        if pixels_per_cm_x and pixels_per_cm_y:
            # Use viewport dimensions for accurate conversion
            min_viewport_dim = min(viewport_width_px, viewport_height_px)
            min_page_dim_cm = min(page_width_cm, page_height_cm)
            pixels_per_cm_min = min_viewport_dim / min_page_dim_cm
            qr_size_px = qr_size_ratio * min_viewport_dim
            qr_size_cm = qr_size_px / pixels_per_cm_min
            qr_size = qr_size_cm * cm
        else:
            # Fallback: use PDF dimensions directly
            min_page_dim = min(page_width_cm, page_height_cm)
            qr_size = qr_size_ratio * min_page_dim * cm
    elif qr_settings and has_qr_px and qr_size_px is not None and qr_base_width_px:
        qr_size = (qr_size_px / qr_base_width_px) * page_width_cm * cm
    else:
        qr_size = (qr_settings.get('size', 4) * qr_scale_x) * cm if qr_settings else 4 * cm
    
    qr_rotation = qr_settings.get('rotation_angle', 0) if qr_settings else 0
    qr_y = page_height - qr_y_from_top - qr_size
    
    # Generate QR code URL
    if hash_value != 'preview':
        domain_name = 'certs.kku.edu.sa'
        url = f"https://{domain_name}/validate?hash={hash_value}"
    else:
        url = "https://certs.kku.edu.sa/validate"
    
    try:
        generate_qr_code(url, qr_x, qr_y, qr_size, c, qr_rotation)
    except Exception as e:
        pass  # Silent fail for QR code errors
    
    c.save()
    packet.seek(0)
    
    new_pdf = PdfReader(packet)
    merged_page = PageMerge(template_pdf).add(new_pdf.pages[0]).render()
    
    writer = PdfWriter()
    writer.addPage(merged_page)
    with open(output_file, "wb") as f:
        writer.write(f)
