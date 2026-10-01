"""Use the application's own logo in every report; never substitute a generic icon."""
import base64
from pathlib import Path


def logo_path():
    candidates = [Path(__file__).resolve().parent / 'logo.png', Path.cwd() / 'logo.png']
    return next((path for path in candidates if path.is_file()), None)


def logo_html():
    path = logo_path()
    if path is None:
        return ''
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'<img src="data:image/png;base64,{encoded}" alt="PerdiaPredict logo" style="width:44px;height:44px;object-fit:contain;vertical-align:middle;margin-inline-end:14px" />'


def draw_report_header(canvas, page_width, page_height, subtitle, lang="en", paragraph=None):
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#0f233f'))
    canvas.rect(0, page_height - 80, page_width, 80, fill=1, stroke=0)
    path = logo_path()
    text_x = 42
    if path is not None:
        canvas.drawImage(ImageReader(str(path)), 42, page_height - 62,
                         width=44, height=44, preserveAspectRatio=True,
                         anchor='c', mask='auto')
        text_x = 100
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 20)
    canvas.drawString(text_x, page_height - 38, 'PerdiaPredict')
    canvas.setFillColor(colors.HexColor('#cbd5e1'))
    canvas.setFont('Helvetica', 9)
    if paragraph is not None:
        from reportlab.lib.styles import ParagraphStyle
        from report_locale import text
        label=subtitle.split(' | ')[0]
        suffix={'ar':'سري','es':'CONFIDENCIAL','hi':'गोपनीय','zh':'保密','fr':'CONFIDENTIEL','de':'VERTRAULICH','tr':'GİZLİ','pt':'CONFIDENCIAL','ru':'КОНФИДЕНЦИАЛЬНО'}.get(lang,'CONFIDENTIAL')
        style=ParagraphStyle('BrandSubtitle',fontName='ReportRegular',fontSize=9,leading=13,textColor=colors.HexColor('#cbd5e1'),alignment=2 if lang=='ar' else 0)
        obj=paragraph(str(text(label,lang))+' | '+suffix,style)
        obj.wrap(page_width-text_x-42,28)
        obj.drawOn(canvas,text_x,page_height-63)
    else:
        canvas.drawString(text_x, page_height - 59, subtitle)
    canvas.setStrokeColor(colors.HexColor('#127382'))
    canvas.setLineWidth(3)
    canvas.line(0, page_height - 80, page_width, page_height - 80)
    canvas.restoreState()
