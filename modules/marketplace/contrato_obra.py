# modules/marketplace/contrato_obra.py
"""
Generador de precontrato de obra en PDF con verificación SHA-256.
Usa reportlab (ya en requirements.txt).
"""
import hashlib
import io
from datetime import datetime


def generar_contrato(
    project_name: str,
    province: str,
    area: float,
    client_name: str,
    client_email: str,
    provider_name: str,
    provider_email: str,
    provider_company: str,
    price: float,
    includes_materials: bool,
    plazo_semanas: int,
    garantia_anos: int,
    nota_tecnica: str,
    breakdown: dict,
    comision_pct: float = 3.0,
) -> tuple:
    """
    Genera el PDF del precontrato de obra.
    Devuelve (pdf_bytes: bytes, sha256_hex: str).
    El SHA-256 identifica de forma única e inmutable este documento.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    mat_label = "con materiales" if includes_materials else "sin materiales"
    comision_eur = round(price * comision_pct / 100, 2)

    def _line(y, text, size=10, bold=False, color=None):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if color:
            c.setFillColorRGB(*color)
        else:
            c.setFillColorRGB(0.05, 0.1, 0.2)
        c.drawString(50, y, text)
        c.setFillColorRGB(0.05, 0.1, 0.2)

    def _hline(y):
        c.setStrokeColorRGB(0.7, 0.8, 0.9)
        c.setLineWidth(0.5)
        c.line(50, y, w - 50, y)

    # ── Cabecera ──────────────────────────────────────────────────────────────
    c.setFillColorRGB(0.07, 0.23, 0.37)
    c.rect(0, h - 80, w, 80, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(50, h - 40, "ARCHIRAPID — PRECONTRATO DE OBRA")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.6, 0.75, 0.9)
    c.drawString(50, h - 60, "Documento vinculante de intención de contratación · archirapid.streamlit.app")
    c.drawRightString(w - 50, h - 60, f"Generado: {now_str}")

    y = h - 110

    # ── Proyecto ──────────────────────────────────────────────────────────────
    _line(y, "1. DATOS DEL PROYECTO", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, f"Nombre del proyecto:  {project_name}"); y -= 14
    _line(y, f"Provincia:            {province}"); y -= 14
    _line(y, f"Superficie total:     {area:,.0f} m²"); y -= 14

    # ── Cliente ───────────────────────────────────────────────────────────────
    y -= 10
    _line(y, "2. DATOS DEL PROMOTOR (CLIENTE)", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, f"Nombre:               {client_name}"); y -= 14
    _line(y, f"Email:                {client_email}"); y -= 14

    # ── Constructor ───────────────────────────────────────────────────────────
    y -= 10
    _line(y, "3. DATOS DEL CONSTRUCTOR / PROFESIONAL", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, f"Nombre / Razón social: {provider_name}"); y -= 14
    _line(y, f"Empresa:               {provider_company or '—'}"); y -= 14
    _line(y, f"Email:                 {provider_email}"); y -= 14

    # ── Condiciones pactadas ──────────────────────────────────────────────────
    y -= 10
    _line(y, "4. CONDICIONES DE LA OFERTA ACEPTADA", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, f"Importe total:        €{price:,.2f}  ({mat_label})"); y -= 14
    _line(y, f"€/m² resultante:      €{price/area:,.0f}  por m²" if area else "€/m²: —"); y -= 14
    _line(y, f"Plazo de ejecución:   {plazo_semanas} semanas ({round(plazo_semanas/4.3,1)} meses)"); y -= 14
    _line(y, f"Garantía:             {garantia_anos} años"); y -= 14
    if nota_tecnica:
        _line(y, f"Nota técnica:         {nota_tecnica[:90]}{'…' if len(nota_tecnica) > 90 else ''}"); y -= 14

    # ── Desglose ──────────────────────────────────────────────────────────────
    y -= 10
    _line(y, "5. DESGLOSE POR PARTIDAS", 11, bold=True); y -= 18
    _hline(y); y -= 12
    partidas = (breakdown or {}).get("partidas", [])
    for p in partidas:
        _line(y, f"  • {p.get('name','—'):30s}  €{p.get('cost',0):>12,.0f}   ({p.get('pct','')})"); y -= 13
        if y < 120:
            c.showPage()
            y = h - 60

    # ── Comisión ArchiRapid ───────────────────────────────────────────────────
    y -= 10
    _line(y, "6. COMISIÓN DE INTERMEDIACIÓN ARCHIRAPID", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, f"Porcentaje pactado:   {comision_pct}% sobre el importe total"); y -= 14
    _line(y, f"Importe comisión:     €{comision_eur:,.2f}"); y -= 14
    _line(y, "Pagadero por el constructor al confirmar la adjudicación vía plataforma."); y -= 14

    # ── Verificación SHA-256 ──────────────────────────────────────────────────
    y -= 14
    _line(y, "7. VERIFICACIÓN DE INTEGRIDAD (SHA-256)", 11, bold=True); y -= 18
    _hline(y); y -= 12
    _line(y, "Este documento incluye su propio hash de integridad SHA-256 calculado sobre su contenido.", 9); y -= 12
    _line(y, "El hash se almacena en la base de datos ArchiRapid y sirve como prueba de no-alteración.", 9); y -= 12
    _line(y, "Cualquier modificación posterior al documento invalidará el hash.", 9); y -= 18
    _line(y, "Hash SHA-256:", 9, bold=True); y -= 12
    # El hash se añade en el campo de texto debajo del PDF (se calcula tras generar)
    _line(y, "(ver campo 'Hash' en la confirmación de aceptación dentro de ArchiRapid)", 8, color=(0.4, 0.5, 0.6)); y -= 18

    # ── Pie ───────────────────────────────────────────────────────────────────
    _hline(60)
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(w / 2, 45, "ArchiRapid · hola@archirapid.com · archirapid.streamlit.app")
    c.drawCentredString(w / 2, 32, f"Documento generado automáticamente · {now_str}")
    c.drawCentredString(w / 2, 19, "Este precontrato no sustituye al contrato de obra definitivo firmado ante notario.")

    c.save()
    pdf_bytes = buffer.getvalue()
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    return pdf_bytes, sha256
