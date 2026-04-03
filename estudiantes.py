"""
estudiantes.py — Portal de Estudiantes TFG/TFM
Módulo independiente. Llamar desde app.py con mostrar_modulo_estudiantes().
"""
import streamlit as st
import hashlib
import datetime
import io
import os

from modules.marketplace.utils import db_conn, save_upload

AUTORIZACION_VERSION = "v1.0-2026"

PROVINCIAS_ESPAÑA = [
    "Álava", "Albacete", "Alicante", "Almería", "Asturias", "Ávila",
    "Badajoz", "Barcelona", "Burgos", "Cáceres", "Cádiz", "Cantabria",
    "Castellón", "Ciudad Real", "Córdoba", "Cuenca", "Girona", "Granada",
    "Guadalajara", "Guipúzcoa", "Huelva", "Huesca", "Islas Baleares",
    "Jaén", "La Coruña", "La Rioja", "Las Palmas", "León", "Lérida",
    "Lugo", "Madrid", "Málaga", "Murcia", "Navarra", "Ourense", "Palencia",
    "Pontevedra", "Salamanca", "Santa Cruz de Tenerife", "Segovia",
    "Sevilla", "Soria", "Tarragona", "Teruel", "Toledo", "Valencia",
    "Valladolid", "Vizcaya", "Zamora", "Zaragoza", "Ceuta", "Melilla",
]

TIPOLOGIAS = [
    "Vivienda unifamiliar", "Vivienda colectiva", "Mixto", "Otros",
]

SERVICIOS_TARIFAS = {
    "visado":         {"label": "Visado de proyecto",             "minimo": 150},
    "direccion_obra": {"label": "Dirección de obra",              "minimo": 1500},
    "supervision":    {"label": "Supervisión / revisión de proyecto", "minimo": 200},
    "consulta":       {"label": "Consulta técnica",               "minimo": 50},
}

AUTORIZACION_TEXTO = """
AUTORIZACIÓN DE PUBLICACIÓN Y CESIÓN DE USO COMERCIAL
ArchiRapid S.L. — archirapid.com

El/La estudiante firmante, identificado/a con los datos de registro
en la plataforma ArchiRapid, AUTORIZA expresamente a ArchiRapid S.L. a:

1. PUBLICACIÓN: Publicar el proyecto de fin de grado (TFG) o fin de
   máster (TFM) titulado según los datos del registro, en la plataforma
   archirapid.com y sus canales asociados, con fines comerciales.

2. CESIÓN DE USO: Ceder a terceros compradores el uso del proyecto
   en los términos de la modalidad de venta seleccionada:
   - EXCLUSIVO: el proyecto se vende una única vez. Tras la venta,
     se retira de la plataforma automáticamente.
   - MÚLTIPLE: el proyecto puede venderse a varios compradores
     de forma independiente.

3. DISTRIBUCIÓN DE INGRESOS: El precio de venta fijado por el/la
   estudiante se distribuirá conforme al acuerdo de plataforma:
   60% para el/la estudiante autor/a del proyecto.
   40% para ArchiRapid S.L. en concepto de comisión de plataforma,
   gestión, marketing y servicios tecnológicos.

4. AUTORÍA Y RESPONSABILIDAD: El/La estudiante declara ser el/la
   único/a autor/a del proyecto, que el mismo ha sido presentado y
   evaluado favorablemente en su universidad, y que no infringe
   derechos de terceros. ArchiRapid S.L. no asume responsabilidad
   por el contenido técnico del proyecto ni por su viabilidad
   constructiva sin la preceptiva intervención de arquitecto colegiado.

5. AVISO LEGAL TÉCNICO: Los proyectos publicados en ArchiRapid son
   trabajos académicos orientativos. Cualquier uso constructivo
   requiere visado colegial y dirección facultativa conforme a la
   LOE (Ley 38/1999).

6. REVOCACIÓN: El/La estudiante puede solicitar la retirada del
   proyecto en cualquier momento si no ha sido vendido. Una vez
   vendido, la cesión de uso al comprador es irrevocable.

Fecha y hora de aceptación: [TIMESTAMP_UTC]
Identificador único: [HASH_SHA256]
Versión del documento: [VERSION]
"""


# ─── PUNTO DE ENTRADA ────────────────────────────────────────────────────────

def mostrar_modulo_estudiantes():
    """
    Punto de entrada del módulo. Detecta si el usuario es estudiante
    registrado o nuevo y muestra la pantalla correspondiente.
    """
    st.title("🎓 Portal de Estudiantes — Proyectos TFG/TFM")
    st.caption("Publica tu proyecto final y recibe el 60% de cada venta.")

    email = st.session_state.get("user_email", "") or st.session_state.get("client_email", "")

    if not email:
        st.warning("Debes iniciar sesión para acceder al portal de estudiantes.")
        return

    estudiante = _get_estudiante(email)

    if estudiante is None:
        _mostrar_registro(email)
    elif estudiante["estado"] == "pendiente":
        _mostrar_pendiente_aprobacion(estudiante)
    elif estudiante["estado"] == "rechazado":
        _mostrar_rechazado(estudiante)
    elif estudiante["estado"] == "aprobado":
        _mostrar_panel_estudiante(estudiante)


# ─── REGISTRO ────────────────────────────────────────────────────────────────

def _mostrar_registro(email: str):
    st.subheader("📝 Registro como estudiante")
    st.info(
        "Tu registro será revisado por el equipo de ArchiRapid. "
        "Recibirás confirmación en tu email en un plazo de 24-48h."
    )

    with st.form("form_registro_estudiante"):
        nombre = st.text_input("Nombre completo *")
        universidad = st.text_input("Universidad *")
        año_tfg = st.selectbox(
            "Año de presentación del TFG/TFM *",
            options=list(range(datetime.datetime.now().year, 2018, -1)),
        )
        ciudad = st.text_input("Ciudad")
        bio = st.text_area("Breve descripción / especialidad (opcional)", max_chars=300)
        portfolio_url = st.text_input("URL portfolio o LinkedIn (opcional)")

        st.markdown("---")
        st.markdown("**Documento de autorización de publicación**")
        texto_preview = AUTORIZACION_TEXTO.replace(
            "[TIMESTAMP_UTC]", "(se registrará al firmar)"
        ).replace("[HASH_SHA256]", "(generado al firmar)").replace(
            "[VERSION]", AUTORIZACION_VERSION
        )
        st.text_area(
            "Lee el documento completo antes de aceptar:",
            value=texto_preview,
            height=300,
            disabled=True,
        )
        acepta_autorizacion = st.checkbox(
            "Acepto la autorización de publicación y cesión de uso comercial"
        )

        submitted = st.form_submit_button("📨 Enviar solicitud de registro")

        if submitted:
            if not nombre or not universidad:
                st.error("Nombre completo y universidad son obligatorios.")
                return
            if not acepta_autorizacion:
                st.error("Debes aceptar la autorización para registrarte.")
                return
            _procesar_registro(email, nombre, universidad, año_tfg, ciudad, bio, portfolio_url)


def _procesar_registro(email, nombre, universidad, año_tfg, ciudad, bio, portfolio_url):
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    contenido = f"{AUTORIZACION_TEXTO}{email}{ts}{AUTORIZACION_VERSION}"
    hash_val = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    pdf_url = _generar_pdf_autorizacion(hash_val, email, nombre, ts)

    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO estudiantes
            (email, nombre_completo, universidad, año_tfg, ciudad,
             bio, portfolio_url, estado, hash_autorizacion, pdf_autorizacion_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
            ON CONFLICT (email) DO NOTHING
        """, (email, nombre, universidad, año_tfg, ciudad, bio, portfolio_url, hash_val, pdf_url))
        conn.commit()
    except Exception as e:
        st.error(f"Error al registrar: {e}")
        return
    finally:
        conn.close()

    st.success(
        f"✅ Solicitud enviada correctamente. "
        f"Referencia: {hash_val[:16]}... "
        "Te notificaremos por email cuando sea revisada."
    )
    st.rerun()


# ─── ESTADOS INTERMEDIOS ──────────────────────────────────────────────────────

def _mostrar_pendiente_aprobacion(estudiante: dict):
    st.info(
        "⏳ Tu solicitud está pendiente de revisión por el equipo de ArchiRapid. "
        "En breve recibirás confirmación."
    )
    st.caption(f"Registrado el: {str(estudiante.get('created_at', ''))[:10]}")


def _mostrar_rechazado(estudiante: dict):
    st.error(
        "❌ Tu solicitud no ha sido aprobada en esta ocasión. "
        "Contacta con soporte@archirapid.com para más información."
    )


# ─── PANEL ESTUDIANTE APROBADO ────────────────────────────────────────────────

def _mostrar_panel_estudiante(estudiante: dict):
    st.success(f"✅ Bienvenido/a, {estudiante['nombre_completo']}")

    tab1, tab2, tab3 = st.tabs([
        "📁 Mis proyectos",
        "➕ Subir nuevo proyecto",
        "💶 Mis tarifas de servicios",
    ])

    with tab1:
        _mostrar_proyectos_estudiante(estudiante)

    with tab2:
        _mostrar_form_subir_proyecto(estudiante)

    with tab3:
        _mostrar_tarifas_profesional(
            estudiante["email"],
            estudiante["id"],
            tipo="estudiante",
        )


def _mostrar_proyectos_estudiante(estudiante: dict):
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT titulo, precio_venta, modalidad_venta, estado,
                   veces_vendido, activo, created_at
            FROM proyectos_tfg
            WHERE estudiante_id = ?
            ORDER BY created_at DESC
        """, (estudiante["id"],))
        rows = cur.fetchall()
    except Exception as e:
        st.error(f"Error cargando proyectos: {e}")
        return
    finally:
        conn.close()

    if not rows:
        st.info("Aún no has subido ningún proyecto.")
        return

    for r in rows:
        titulo, precio, modalidad, estado, vendido, activo, fecha = (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        )
        icono = "✅" if activo else ("⏳" if estado == "pendiente" else "❌")
        with st.expander(f"{icono} {titulo} — {precio}€"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Precio", f"{precio}€")
            col2.metric("Modalidad", modalidad)
            col3.metric("Veces vendido", vendido or 0)
            st.caption(f"Estado: {estado} | Subido: {str(fecha)[:10]}")


# ─── FORMULARIO SUBIR PROYECTO ────────────────────────────────────────────────

def _mostrar_form_subir_proyecto(estudiante: dict):
    st.subheader("➕ Subir proyecto TFG/TFM")
    st.caption(
        "Solo se acepta UN proyecto activo por estudiante. "
        "Debe ser ejecutable y haber sido presentado en tu universidad."
    )

    with st.form("form_subir_proyecto"):
        titulo = st.text_input("Título del proyecto *")
        descripcion = st.text_area("Descripción del proyecto *", max_chars=500)
        tipologia = st.selectbox("Tipología *", TIPOLOGIAS)
        superficie = st.number_input("Superficie aproximada (m²)", min_value=10.0, step=5.0)

        col1, col2 = st.columns(2)
        with col1:
            provincia = st.selectbox("Provincia del proyecto", PROVINCIAS_ESPAÑA)
        with col2:
            ciudad_proy = st.text_input("Ciudad/Municipio")

        st.markdown("---")
        st.markdown("**Precio y modalidad de venta**")
        col3, col4 = st.columns(2)
        with col3:
            precio = st.number_input(
                "Precio de venta (€) *",
                min_value=50.0, max_value=50000.0, step=50.0,
            )
        with col4:
            modalidad = st.selectbox(
                "Modalidad *",
                ["exclusivo", "multiple"],
                format_func=lambda x: (
                    "Exclusivo (una sola venta)" if x == "exclusivo"
                    else "Múltiple (varias ventas)"
                ),
            )

        st.caption(
            f"💡 Recibirás el **60%** = **{precio * 0.6:.0f}€** por venta. "
            f"ArchiRapid retiene el 40% = {precio * 0.4:.0f}€"
        )

        st.markdown("---")
        st.markdown("**Archivos del proyecto**")
        st.info("Sube los archivos en formato PDF. La imagen de portada puede ser JPG o PNG.")
        archivo_planos   = st.file_uploader("Planos (PDF) *", type=["pdf"])
        archivo_memoria  = st.file_uploader("Memoria descriptiva (PDF)", type=["pdf"])
        archivo_renders  = st.file_uploader("Renders / imágenes (PDF o ZIP)", type=["pdf", "zip"])
        imagen_portada   = st.file_uploader("Imagen de portada *", type=["jpg", "jpeg", "png"])

        st.markdown("---")
        acepta = st.checkbox(
            "Confirmo que este proyecto ha sido presentado y evaluado "
            "favorablemente en mi universidad y soy su único autor/a"
        )

        submitted = st.form_submit_button("📤 Enviar proyecto para revisión")

        if submitted:
            if not titulo or not descripcion or not archivo_planos or not imagen_portada:
                st.error("Título, descripción, planos e imagen de portada son obligatorios.")
                return
            if not acepta:
                st.error("Debes confirmar la autoría del proyecto.")
                return
            _procesar_subida_proyecto(
                estudiante, titulo, descripcion, tipologia,
                superficie, provincia, ciudad_proy, precio, modalidad,
                archivo_planos, archivo_memoria, archivo_renders, imagen_portada,
            )


def _procesar_subida_proyecto(
    estudiante, titulo, descripcion, tipologia,
    superficie, provincia, ciudad, precio, modalidad,
    archivo_planos, archivo_memoria, archivo_renders, imagen_portada,
):
    with st.spinner("Subiendo archivos..."):
        try:
            url_planos  = save_upload(archivo_planos,  prefix="planos_tfg")
            url_memoria = save_upload(archivo_memoria, prefix="memoria_tfg") if archivo_memoria else None
            url_renders = save_upload(archivo_renders, prefix="renders_tfg") if archivo_renders else None
            url_portada = save_upload(imagen_portada,  prefix="portada_tfg")
        except Exception as e:
            st.error(f"Error subiendo archivos: {e}")
            return

    ts = datetime.datetime.utcnow().isoformat() + "Z"
    hash_doc = hashlib.sha256(
        f"{titulo}{estudiante['email']}{ts}{precio}".encode()
    ).hexdigest()

    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO proyectos_tfg
            (estudiante_id, email_estudiante, titulo, descripcion,
             superficie_m2, tipologia, precio_venta, modalidad_venta,
             provincia, ciudad, archivo_planos_url, archivo_memoria_url,
             archivo_renders_url, imagen_portada_url, hash_documento,
             estado, activo, comision_archirapid, comision_estudiante)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', 0, 40.0, 60.0)
        """, (
            estudiante["id"], estudiante["email"], titulo, descripcion,
            superficie, tipologia, precio, modalidad, provincia, ciudad,
            url_planos, url_memoria, url_renders, url_portada, hash_doc,
        ))
        conn.commit()
    except Exception as e:
        st.error(f"Error guardando proyecto: {e}")
        return
    finally:
        conn.close()

    st.success(
        f"✅ Proyecto enviado para revisión. "
        f"Referencia: {hash_doc[:16]}... "
        "El equipo de ArchiRapid lo revisará en 24-48h."
    )
    st.rerun()


# ─── TARIFAS DE SERVICIOS ────────────────────────────────────────────────────

def _mostrar_tarifas_profesional(email: str, proveedor_id: int, tipo: str = "arquitecto"):
    st.subheader("💶 Mis tarifas de servicios")
    st.caption(
        "Define el precio de cada servicio que ofreces. "
        "Los precios mínimos están fijados por ArchiRapid y no pueden modificarse."
    )

    tarifas_actuales = _get_tarifas(email)

    for servicio_key, servicio_info in SERVICIOS_TARIFAS.items():
        tarifa_existente = next(
            (t for t in tarifas_actuales if t["servicio"] == servicio_key), None
        )
        precio_actual = tarifa_existente["precio"] if tarifa_existente else float(servicio_info["minimo"])
        activo_actual = bool(tarifa_existente["activo"]) if tarifa_existente else False

        with st.expander(f"📋 {servicio_info['label']} — mínimo {servicio_info['minimo']}€"):
            col1, col2 = st.columns([2, 1])
            with col1:
                nuevo_precio = st.number_input(
                    f"Tu precio para {servicio_info['label']} (€)",
                    min_value=float(servicio_info["minimo"]),
                    value=float(precio_actual),
                    step=10.0,
                    key=f"tarifa_{servicio_key}_{email}",
                )
            with col2:
                nuevo_activo = st.checkbox(
                    "Ofrecer este servicio",
                    value=activo_actual,
                    key=f"activo_{servicio_key}_{email}",
                )

            if st.button(f"💾 Guardar tarifa", key=f"save_{servicio_key}_{email}"):
                _guardar_tarifa(
                    email, proveedor_id, tipo,
                    servicio_key, nuevo_precio,
                    float(servicio_info["minimo"]), nuevo_activo,
                )
                st.success("Tarifa guardada correctamente.")
                st.rerun()


def _guardar_tarifa(email, proveedor_id, tipo, servicio, precio, minimo, activo):
    conn = db_conn()
    try:
        cur = conn.cursor()
        # Intentar actualizar primero
        cur.execute("""
            UPDATE tarifas_profesionales
            SET precio = ?, activo = ?, updated_at = datetime('now')
            WHERE email = ? AND servicio = ?
        """, (precio, 1 if activo else 0, email, servicio))
        if cur.rowcount == 0:
            # No existía — insertar
            cur.execute("""
                INSERT INTO tarifas_profesionales
                (email, proveedor_id, tipo_profesional, servicio, precio, precio_minimo, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email, proveedor_id, tipo, servicio, precio, minimo, 1 if activo else 0))
        conn.commit()
    finally:
        conn.close()


def _get_tarifas(email: str) -> list:
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT servicio, precio, precio_minimo, activo
            FROM tarifas_profesionales
            WHERE email = ?
        """, (email,))
        rows = cur.fetchall()
        return [
            {"servicio": r[0], "precio": r[1], "precio_minimo": r[2], "activo": r[3]}
            for r in rows
        ]
    except Exception:
        return []
    finally:
        conn.close()


def _get_estudiante(email: str) -> dict | None:
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, nombre_completo, universidad, año_tfg,
                   ciudad, bio, estado, hash_autorizacion, created_at
            FROM estudiantes
            WHERE email = ?
        """, (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id":               row[0],
            "email":            row[1],
            "nombre_completo":  row[2],
            "universidad":      row[3],
            "año_tfg":          row[4],
            "ciudad":           row[5],
            "bio":              row[6],
            "estado":           row[7],
            "hash_autorizacion": row[8],
            "created_at":       row[9],
        }
    except Exception:
        return None
    finally:
        conn.close()


# ─── GENERADOR PDF AUTORIZACIÓN ───────────────────────────────────────────────

def _generar_pdf_autorizacion(hash_val: str, email: str, nombre: str, timestamp: str) -> str:
    """
    Genera PDF de autorización con reportlab y lo sube a Supabase Storage.
    Devuelve URL pública o cadena vacía si falla.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        bold   = ParagraphStyle("bold",  parent=styles["Normal"], fontName="Helvetica-Bold")
        normal = styles["Normal"]
        small  = ParagraphStyle("small", parent=styles["Normal"], fontSize=8)

        story = []
        story.append(Paragraph("ARCHIRAPID — AUTORIZACIÓN DE PUBLICACIÓN", bold))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(f"Hash SHA-256: {hash_val}", small))
        story.append(Paragraph(f"Fecha UTC: {timestamp}", small))
        story.append(Paragraph(f"Estudiante: {nombre} ({email})", small))
        story.append(Spacer(1, 0.5 * cm))

        texto_final = AUTORIZACION_TEXTO.replace(
            "[TIMESTAMP_UTC]", timestamp
        ).replace(
            "[HASH_SHA256]", hash_val
        ).replace(
            "[VERSION]", AUTORIZACION_VERSION
        )

        for linea in texto_final.split("\n"):
            linea = linea.strip()
            if not linea:
                story.append(Spacer(1, 0.2 * cm))
            elif linea.isupper() and len(linea) > 5:
                story.append(Paragraph(linea, bold))
            else:
                story.append(Paragraph(linea, normal))

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f"SHA-256 completo: {hash_val}", small))

        doc.build(story)
        pdf_bytes = buffer.getvalue()

    except Exception:
        return ""

    # Subir a Supabase Storage via REST API (sin SDK)
    try:
        import requests as _req

        SUPABASE_URL = st.secrets.get("SUPABASE_URL", "") or os.getenv("SUPABASE_URL", "")
        SUPABASE_KEY = st.secrets.get("SUPABASE_STORAGE_KEY", "") or os.getenv("SUPABASE_STORAGE_KEY", "")

        if not SUPABASE_URL or not SUPABASE_KEY:
            return ""

        nombre_archivo = (
            f"autorizaciones_estudiantes/"
            f"{email.replace('@', '_')}_{hash_val[:12]}_{timestamp[:10]}.pdf"
        )
        BUCKET = "documentos-legales"
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{nombre_archivo}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/pdf",
        }
        resp = _req.post(url, headers=headers, data=pdf_bytes, timeout=30)
        if resp.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{nombre_archivo}"
    except Exception:
        pass

    return ""
