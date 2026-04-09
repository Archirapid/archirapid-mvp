"""
disclaimer_legal.py — ArchiRapid
Sistema de disclaimer legal obligatorio.
Bloquea acceso a Babylon (diseño IA) y pago de documentación
hasta aceptación explícita con PDF firmado y registro en BD.
"""
import hashlib
import datetime
import os
import io

import streamlit as st

DISCLAIMER_VERSION = "v1.0-2026"

DISCLAIMER_TEXTO = """AVISO LEGAL OBLIGATORIO — HERRAMIENTA DE DISEÑO ASISTIDO POR INTELIGENCIA ARTIFICIAL
ArchiRapid S.L. — CIF: [PENDIENTE] — archirapid.com

─────────────────────────────────────────────────────────────────

1. NATURALEZA DEL SERVICIO Y LIMITACIONES LEGALES

ArchiRapid es una herramienta de diseño asistido por inteligencia artificial con fines
informativos y de prefiguración. Los diseños, planos, memorias, documentos técnicos,
estimaciones de coste y cualquier output generado por esta plataforma constituyen
materiales orientativos y NO tienen validez técnica, urbanística ni jurídica por sí solos.

En ningún caso los contenidos generados por ArchiRapid sustituyen ni pueden sustituir
al proyecto técnico redactado, firmado y visado por un arquitecto colegiado, ni a la
dirección facultativa de obra, conforme exige la Ley 38/1999, de 5 de noviembre,
de Ordenación de la Edificación (LOE), en sus artículos 2, 10 y 12.

2. OBLIGACIÓN LEGAL DE INTERVENCIÓN DE ARQUITECTO

Conforme al artículo 2.2 de la LOE y al Real Decreto Legislativo 7/2015, la redacción
de proyecto técnico y la dirección de obras de edificación requieren la intervención
obligatoria de un arquitecto colegiado con competencia legal acreditada.

El visado colegial del proyecto, exigido por los Colegios Oficiales de Arquitectos en
virtud del Real Decreto 1000/2010, sobre visado colegial obligatorio, es requisito
previo e insustituible para la obtención de licencia de obra y para cualquier trámite
administrativo ante organismos públicos.

Ejecutar cualquier obra sin proyecto técnico visado y sin dirección facultativa
constituye una infracción urbanística grave conforme a la legislación autonómica
aplicable, y puede dar lugar a órdenes de demolición, sanciones económicas y
responsabilidad civil y penal para el promotor.

3. EXENCIÓN DE RESPONSABILIDAD DE ARCHIRAPID

ArchiRapid S.L. queda expresamente exenta de toda responsabilidad derivada del uso
indebido, incompleto o no supervisado de los contenidos generados por la plataforma.
El usuario asume plena y exclusiva responsabilidad por cualquier decisión constructiva,
inversión económica, trámite administrativo o actuación sobre el inmueble que realice
basándose, total o parcialmente, en los outputs de ArchiRapid sin la preceptiva
supervisión y validación de un profesional arquitecto habilitado.

Esta exención de responsabilidad opera conforme al artículo 1255 del Código Civil
y al artículo 6 del Real Decreto Legislativo 1/2007, Ley General para la Defensa
de los Consumidores y Usuarios, en todo lo que no contravenga normas imperativas.

4. INTRUSISMO PROFESIONAL

ArchiRapid no ejerce ni pretende ejercer funciones reservadas por ley a los
arquitectos colegiados. El uso de esta herramienta no constituye ejercicio profesional
de arquitectura. Queda expresamente prohibido al usuario presentar los documentos
generados por ArchiRapid ante organismos públicos como proyectos técnicos visados
o documentos con validez colegial, lo que podría constituir delito de intrusismo
profesional tipificado en el artículo 403 del Código Penal.

5. ARQUITECTOS COLABORADORES DE ARCHIRAPID

ArchiRapid pone a disposición del usuario una red de arquitectos colegiados
colaboradores que pueden asumir la redacción del proyecto técnico, el visado colegial,
la dirección de obra y la supervisión legal de cualquier actuación edificatoria.

Puede acceder a estos servicios desde la plataforma mediante los selectores habilitados
para: Visado de Proyecto, Dirección de Obra y Supervisión Técnica.

Se recomienda encarecidamente contratar estos servicios antes de iniciar cualquier
trámite administrativo o actuación constructiva.

6. ACEPTACIÓN

Al marcar la casilla de aceptación y continuar, el usuario declara haber leído,
comprendido y aceptado íntegramente el presente aviso legal, siendo mayor de edad
y actuando en su propio nombre o con representación acreditada del titular del inmueble.

Fecha y hora de aceptación: [TIMESTAMP_UTC]
Identificador único de aceptación: [HASH_SHA256]
Versión del documento: """ + DISCLAIMER_VERSION


def mostrar_disclaimer_y_bloquear(tipo: str, user_email: str, user_id: str) -> bool:
    """
    Muestra el disclaimer legal. Devuelve True si el usuario ya aceptó
    (en sesión o en BD) o acaba de aceptar. Devuelve False si no acepta.

    tipo: "diseno_ia" | "documentacion_pago"
    """
    session_key = f"disclaimer_aceptado_{tipo}_{user_email}"

    # Si ya aceptó en esta sesión, no volver a mostrar
    if st.session_state.get(session_key):
        return True

    # Verificar en BD si ya aceptó previamente (misma versión)
    if _ya_acepto_en_bd(user_email, tipo, DISCLAIMER_VERSION):
        st.session_state[session_key] = True
        return True

    # Mostrar disclaimer
    st.warning("⚠️ Antes de continuar debes leer y aceptar el aviso legal obligatorio.")

    with st.expander("📋 AVISO LEGAL OBLIGATORIO — Leer antes de continuar", expanded=True):
        texto_display = (
            DISCLAIMER_TEXTO
            .replace("[TIMESTAMP_UTC]", "(se registrará al aceptar)")
            .replace("[HASH_SHA256]", "(se generará al aceptar)")
        )
        st.text(texto_display)

    nombre_completo = st.text_input(
        "Tu nombre completo (para registro legal)",
        key=f"disclaimer_nombre_{tipo}"
    )
    acepta = st.checkbox(
        "He leído íntegramente el aviso legal y lo acepto en su totalidad",
        key=f"disclaimer_check_{tipo}"
    )

    if acepta and nombre_completo and nombre_completo.strip():
        if st.button("✅ Confirmar aceptación y continuar", key=f"disclaimer_btn_{tipo}"):
            try:
                hash_val, pdf_url = _registrar_aceptacion(
                    user_email, user_id, nombre_completo.strip(), tipo
                )
                st.session_state[session_key] = True
                st.success(f"Aceptación registrada. Referencia: {hash_val[:16]}...")
                st.rerun()
            except Exception as _e:
                st.error(f"Error registrando aceptación: {_e}")
    else:
        st.info("Debes introducir tu nombre completo y marcar la casilla para continuar.")

    return False


def _ya_acepto_en_bd(email: str, tipo: str, version: str) -> bool:
    """Comprueba si el usuario ya aceptó esta versión del disclaimer en BD."""
    if not email:
        return False
    try:
        from modules.marketplace.utils import db_conn
        conn = db_conn()
        try:
            row = conn.execute(
                "SELECT id FROM disclaimers_aceptados WHERE email=? AND tipo_disclaimer=? AND version_texto=? LIMIT 1",
                (email, tipo, version)
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except Exception:
        return False


def _registrar_aceptacion(email: str, user_id: str, nombre: str, tipo: str) -> tuple:
    """Genera hash SHA-256, PDF y guarda en BD. Devuelve (hash_val, pdf_url)."""
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    texto_final = (
        DISCLAIMER_TEXTO
        .replace("[TIMESTAMP_UTC]", ts)
    )

    # SHA-256 del texto + email + timestamp
    contenido_hash = f"{texto_final}{email}{ts}{DISCLAIMER_VERSION}"
    hash_val = hashlib.sha256(contenido_hash.encode("utf-8")).hexdigest()

    texto_con_hash = texto_final.replace("[HASH_SHA256]", hash_val)

    # Generar PDF
    pdf_url = _generar_y_subir_pdf(texto_con_hash, hash_val, email, nombre, ts)

    # Guardar en BD
    from modules.marketplace.utils import db_conn
    conn = db_conn()
    try:
        conn.execute(
            """INSERT INTO disclaimers_aceptados
               (user_id, email, nombre_completo, tipo_disclaimer, timestamp_utc,
                hash_sha256, pdf_url, version_texto)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, email, nombre, tipo, ts, hash_val, pdf_url, DISCLAIMER_VERSION)
        )
        conn.commit()
    finally:
        conn.close()

    return hash_val, pdf_url


def _generar_y_subir_pdf(texto: str, hash_val: str, email: str, nombre: str, timestamp: str) -> str | None:
    """
    Genera PDF con reportlab, lo sube a Supabase Storage y devuelve la URL pública.
    Devuelve None si no hay credenciales de Storage configuradas.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2.5*cm, rightMargin=2.5*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        style_title = ParagraphStyle(
            "title", parent=styles["Heading1"],
            fontSize=13, alignment=TA_CENTER, spaceAfter=6
        )
        style_header = ParagraphStyle(
            "header", parent=styles["Normal"],
            fontSize=8, alignment=TA_CENTER, spaceAfter=3, textColor=colors.grey
        )
        style_section = ParagraphStyle(
            "section", parent=styles["Heading2"],
            fontSize=9, spaceBefore=8, spaceAfter=4
        )
        style_body = ParagraphStyle(
            "body", parent=styles["Normal"],
            fontSize=8, leading=11, alignment=TA_JUSTIFY, spaceAfter=4
        )
        style_footer = ParagraphStyle(
            "footer", parent=styles["Normal"],
            fontSize=6, alignment=TA_CENTER, textColor=colors.grey
        )

        story = []
        story.append(Paragraph("ARCHIRAPID — AVISO LEGAL ACEPTADO", style_title))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.darkblue))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Hash SHA-256: {hash_val}", style_header))
        story.append(Paragraph(f"Fecha UTC: {timestamp}", style_header))
        story.append(Paragraph(f"Usuario: {email} — {nombre}", style_header))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 8))

        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea:
                story.append(Spacer(1, 3))
            elif linea.startswith("─"):
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            elif (linea[0].isdigit() and ". " in linea[:4]) or linea.isupper():
                story.append(Paragraph(linea, style_section))
            else:
                safe = linea.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, style_body))

        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph(
            f"Documento generado automáticamente por ArchiRapid | SHA-256: {hash_val[:32]}...",
            style_footer
        ))

        doc.build(story)
        pdf_bytes = buf.getvalue()

        nombre_archivo = (
            f"disclaimers/{email.replace('@', '_').replace('.', '_')}"
            f"_{hash_val[:12]}_{timestamp[:10]}.pdf"
        )
        return _subir_pdf_supabase(pdf_bytes, nombre_archivo)

    except Exception as _e:
        # PDF generation failure no bloquea el flujo
        print(f"[disclaimer] PDF generation error: {_e}")
        return None


def _subir_pdf_supabase(pdf_bytes: bytes, nombre_archivo: str) -> str | None:
    """
    Sube el PDF a Supabase Storage bucket 'documentos-legales' via REST API.
    Devuelve URL pública o None si no hay credenciales configuradas.
    """
    try:
        import streamlit as _st
        supabase_url = _st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL", "")
        supabase_key = _st.secrets.get("SUPABASE_STORAGE_KEY") or os.getenv("SUPABASE_STORAGE_KEY", "")
    except Exception:
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_STORAGE_KEY", "")

    if not supabase_url or not supabase_key:
        return None

    bucket = "documentos-legales"
    url = f"{supabase_url}/storage/v1/object/{bucket}/{nombre_archivo}"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/pdf",
    }
    try:
        import requests as _req
        resp = _req.post(url, headers=headers, data=pdf_bytes, timeout=30)
        if resp.status_code in (200, 201):
            return f"{supabase_url}/storage/v1/object/public/{bucket}/{nombre_archivo}"
    except Exception as _e:
        print(f"[disclaimer] Supabase Storage upload error: {_e}")
    return None


CONTRATO_COMISION_TEXTO = """
CONTRATO DE ENCARGO DE INTERMEDIACIÓN INMOBILIARIA
ArchiRapid S.L. — archirapid.com

Entre ArchiRapid S.L., en adelante LA PLATAFORMA, y el propietario
identificado con los datos de registro, en adelante EL PROPIETARIO,

ACUERDAN:

1. OBJETO: EL PROPIETARIO encarga a LA PLATAFORMA la intermediación
   en la búsqueda de comprador para el inmueble denominado
   [TITULO_FINCA], con precio de salida de [PRECIO]€.

2. COMISIÓN: En caso de formalizarse la compraventa, EL PROPIETARIO
   abonará a LA PLATAFORMA una comisión de intermediación del
   [COMISION_PCT]% sobre el precio de venta final, equivalente
   a [COMISION_EUROS]€ estimados al precio de salida indicado.

3. EXCLUSIVIDAD: El presente encargo no tiene carácter de exclusiva
   salvo pacto expreso por escrito entre las partes.

4. DURACIÓN: El presente contrato tendrá una duración de 12 meses
   desde la fecha de firma, prorrogable por acuerdo mutuo.

5. OBLIGACIONES DE LA PLATAFORMA: ArchiRapid se compromete a
   publicar el inmueble en su plataforma digital, realizar acciones
   de difusión y gestionar las consultas de potenciales compradores.

6. OBLIGACIONES DEL PROPIETARIO: Facilitar documentación veraz del
   inmueble y comunicar a ArchiRapid cualquier operación que pudiera
   realizarse durante la vigencia del contrato.

7. LEGISLACIÓN APLICABLE: El presente contrato se rige por la
   legislación española vigente, en particular la Ley de Ordenación
   del Comercio Minorista y la normativa autonómica aplicable en
   materia de intermediación inmobiliaria.

Fecha y hora de firma: [TIMESTAMP_UTC]
Identificador único del contrato: [HASH_SHA256]
Referencia de finca: [PLOT_ID]
Versión del documento: v1.0-2026
"""


def generar_contrato_comision(
    email: str,
    nombre: str,
    titulo_finca: str,
    precio: float,
    comision_pct: int,
    plot_id: str
) -> tuple:
    """
    Genera PDF del contrato de encargo de intermediación con SHA-256.
    Guarda en Supabase Storage. Registra en disclaimers_aceptados.
    Devuelve (hash_sha256, pdf_url).
    """
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    comision_euros = precio * comision_pct / 100

    texto = (
        CONTRATO_COMISION_TEXTO
        .replace("[TITULO_FINCA]", titulo_finca)
        .replace("[PRECIO]", f"{precio:,.0f}")
        .replace("[COMISION_PCT]", str(comision_pct))
        .replace("[COMISION_EUROS]", f"{comision_euros:,.0f}")
        .replace("[TIMESTAMP_UTC]", ts)
        .replace("[PLOT_ID]", plot_id)
    )

    contenido_hash = f"{texto}{email}{ts}"
    hash_val = hashlib.sha256(contenido_hash.encode("utf-8")).hexdigest()
    texto_final = texto.replace("[HASH_SHA256]", hash_val)

    # Generar PDF con reportlab
    pdf_bytes = b""
    pdf_url = ""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()
        bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8)

        story = []
        story.append(Paragraph("ARCHIRAPID — CONTRATO DE ENCARGO DE INTERMEDIACIÓN", bold))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f"Hash SHA-256: {hash_val}", small))
        story.append(Paragraph(f"Fecha UTC: {ts}", small))
        story.append(Paragraph(f"Propietario: {nombre} ({email})", small))
        story.append(Spacer(1, 0.5*cm))

        for linea in texto_final.split("\n"):
            linea = linea.strip()
            if not linea:
                story.append(Spacer(1, 0.2*cm))
            elif linea.isupper() and len(linea) > 5:
                story.append(Paragraph(linea, bold))
            else:
                story.append(Paragraph(linea, styles["Normal"]))

        doc.build(story)
        pdf_bytes = buffer.getvalue()

        # Subir a Supabase Storage
        nombre_archivo = (
            f"contratos_comision/"
            f"{email.replace('@', '_')}_"
            f"{hash_val[:12]}_{ts[:10]}.pdf"
        )
        pdf_url = _subir_pdf_supabase(pdf_bytes, nombre_archivo) or ""
    except Exception:
        pass

    # Registrar en BD
    try:
        from modules.marketplace.utils import db_conn
        conn = db_conn()
        conn.execute("""
            INSERT INTO disclaimers_aceptados
            (user_id, email, nombre_completo, tipo_disclaimer,
             timestamp_utc, hash_sha256, pdf_url, version_texto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plot_id, email, nombre,
            f"contrato_comision_{comision_pct}pct",
            ts, hash_val, pdf_url, "v1.0-2026"
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return hash_val, pdf_url
