"""Bulgarian legal invoice PDF generator using reportlab."""
import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

INVOICES_DIR = os.path.join(os.path.dirname(__file__), "invoices")
os.makedirs(INVOICES_DIR, exist_ok=True)

# Try Cyrillic-capable font; fall back to Helvetica
FONT = "Helvetica"
for font_path in [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]:
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("CyrFont", font_path))
            FONT = "CyrFont"
        except Exception:
            pass
        break


TYPE_LABELS = {"deposit": "Авансова", "final": "Окончателна", "monthly": "Месечна"}


def generate_invoice_pdf(
    invoice_number: str,
    invoice_date: datetime.datetime,
    client_name: str,
    client_company: str | None,
    client_eik: str | None,
    client_mol: str | None,
    client_vat: str | None,
    client_address: str | None,
    project_name: str,
    service_description: str,
    amount: float,
    currency: str,
    invoice_type: str,
    agency_name: str | None = None,
    agency_eik: str | None = None,
    agency_mol: str | None = None,
    agency_vat: str | None = None,
    agency_address: str | None = None,
) -> str:
    agency_name = agency_name or os.getenv("AGENCY_NAME", "Aetherium Web Studio")
    agency_eik = agency_eik or os.getenv("AGENCY_EIK", "")
    agency_mol = agency_mol or os.getenv("AGENCY_MOL", "")
    agency_vat = agency_vat or os.getenv("AGENCY_VAT", "")
    agency_address = agency_address or os.getenv("AGENCY_ADDRESS", "")

    filename = f"{invoice_number.replace('/', '-')}.pdf"
    filepath = os.path.join(INVOICES_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    left = 25 * mm
    right = width - 25 * mm
    top = height - 20 * mm
    lh = 6 * mm

    DARK = HexColor("#1a1a2e")
    GRAY = HexColor("#555555")
    ACCENT = HexColor("#c026d3")

    # ── Agency header ──
    c.setFont(FONT, 20)
    c.setFillColor(ACCENT)
    c.drawString(left, top, agency_name)

    c.setFont(FONT, 10)
    c.setFillColor(GRAY)
    y = top - 8 * mm
    c.drawString(left, y, f"ЕИК: {agency_eik}  |  МОЛ: {agency_mol}")
    y -= lh
    c.drawString(left, y, f"ДДС №: {agency_vat}")
    y -= lh
    c.drawString(left, y, agency_address)

    # ── Invoice title ──
    y -= 15 * mm
    c.setFont(FONT, 16)
    c.setFillColor(DARK)
    label = TYPE_LABELS.get(invoice_type, "")
    c.drawString(left, y, f"ФАКТУРА {label} / INVOICE")

    # ── Number + date ──
    y -= 12 * mm
    c.setFont(FONT, 10)
    c.drawString(left, y, f"Фактура №: {invoice_number}")
    c.drawString(left + 100 * mm, y, f"Дата: {invoice_date.strftime('%d.%m.%Y')}")

    # ── Client ──
    y -= 15 * mm
    c.setFont(FONT, 12)
    c.setFillColor(DARK)
    c.drawString(left, y, "ПОЛУЧАТЕЛ / CLIENT")
    y -= 8 * mm
    c.setFont(FONT, 10)
    c.setFillColor(GRAY)
    c.drawString(left, y, f"{client_name}" + (f" — {client_company}" if client_company else ""))
    if client_eik:
        y -= lh
        c.drawString(left, y, f"ЕИК: {client_eik}  |  МОЛ: {client_mol or ''}")
    if client_vat:
        y -= lh
        c.drawString(left, y, f"ДДС №: {client_vat}")
    if client_address:
        y -= lh
        c.drawString(left, y, client_address)

    # ── Separator ──
    y -= 12 * mm
    c.setStrokeColor(HexColor("#cccccc"))
    c.line(left, y, right, y)

    # ── Service ──
    y -= 12 * mm
    c.setFont(FONT, 10)
    c.setFillColor(DARK)
    c.drawString(left, y, "УСЛУГА / SERVICE")
    c.drawString(left + 100 * mm, y, "СУМА / AMOUNT")
    y -= lh
    c.setStrokeColor(HexColor("#eeeeee"))
    c.line(left, y, right, y)
    y -= 8 * mm
    c.setFont(FONT, 10)
    c.setFillColor(GRAY)
    c.drawString(left, y, f"{service_description} — {project_name}")
    c.drawString(left + 100 * mm, y, f"{amount:,.2f} {currency}")

    # ── Total ──
    y -= 15 * mm
    c.line(left, y, right, y)
    y -= 8 * mm
    c.setFont(FONT, 12)
    c.setFillColor(DARK)
    c.drawString(left, y, "ОБЩО / TOTAL:")
    c.drawString(left + 100 * mm, y, f"{amount:,.2f} {currency}")

    # ── Footer ──
    y = 30 * mm
    c.setFont(FONT, 8)
    c.setFillColor(HexColor("#999999"))
    c.drawString(left, y, "Тази фактура е генерирана автоматично и е валидна без подпис.")
    y -= lh
    c.drawString(left, y, "This invoice was generated automatically and is valid without a signature.")

    c.save()
    return filepath
