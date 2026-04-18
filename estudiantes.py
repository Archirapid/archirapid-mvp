"""
estudiantes.py — Portal de Estudiantes TFG/TFM
Módulo independiente con auth propia. Llamar desde app.py con mostrar_modulo_estudiantes().
"""
import streamlit as st
import hashlib
import datetime
import io
import os
import json

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
    "Vivienda unifamiliar aislada",
    "Vivienda unifamiliar adosada / pareada",
    "Vivienda plurifamiliar (bloque)",
    "Mixto residencial + comercial",
    "Equipamiento / edificio público",
    "Oficinas / terciario",
    "Industrial / logístico",
    "Rehabilitación / reforma",
    "Urbanismo / espacio público",
    "Paisajismo",
    "Otros",
]

AÑOS_CARRERA = ["1º Grado", "2º Grado", "3º Grado", "4º Grado", "5º Grado", "Máster", "Doctorado"]

SERVICIOS_TARIFAS = {
    "visado":         {"label": "Visado de proyecto",              "minimo": 150},
    "direccion_obra": {"label": "Dirección de obra",               "minimo": 1500},
    "supervision":    {"label": "Supervisión / revisión de proyecto", "minimo": 200},
    "consulta":       {"label": "Consulta técnica",                "minimo": 50},
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


# ─── COLUMNAS ADICIONALES (idempotente) ──────────────────────────────────────

def _ensure_columns():
    """Añade columnas nuevas si no existen (idempotente, try/except por columna)."""
    conn = db_conn()
    try:
        # Tabla estudiantes — columnas nuevas
        for sql in [
            "ALTER TABLE estudiantes ADD COLUMN password_hash TEXT",
            "ALTER TABLE estudiantes ADD COLUMN telefono TEXT",
            "ALTER TABLE estudiantes ADD COLUMN edad INTEGER",
            "ALTER TABLE estudiantes ADD COLUMN año_carrera TEXT",
        ]:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception:
                pass

        # Tabla proyectos_tfg — columnas nuevas
        for sql in [
            "ALTER TABLE proyectos_tfg ADD COLUMN ejecutable TEXT DEFAULT 'En estudio'",
            "ALTER TABLE proyectos_tfg ADD COLUMN validado INTEGER DEFAULT 0",
            "ALTER TABLE proyectos_tfg ADD COLUMN archivo_cad_url TEXT",
            "ALTER TABLE proyectos_tfg ADD COLUMN archivo_vr_url TEXT",
            "ALTER TABLE proyectos_tfg ADD COLUMN fotos_urls TEXT",
        ]:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


def _get_estudiante_by_email(email: str) -> dict | None:
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, nombre_completo, universidad, año_tfg,
                   ciudad, bio, estado, hash_autorizacion, created_at,
                   password_hash, telefono, edad, año_carrera
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
            "password_hash":    row[10],
            "telefono":         row[11],
            "edad":             row[12],
            "año_carrera":      row[13],
        }
    except Exception:
        return None
    finally:
        conn.close()


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def mostrar_modulo_estudiantes():
    _ensure_columns()

    # Cabecera + botón volver
    hcol, bcol = st.columns([6, 1])
    with hcol:
        st.title("🎓 Portal de Estudiantes — TFG / TFM")
    with bcol:
        if st.button("← Volver", key="est_back_home", use_container_width=True):
            st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
            st.session_state.pop("est_session_logged", None)
            st.session_state.pop("est_session_email", None)
            try:
                del st.query_params["page"]
            except Exception:
                pass
            st.stop()

    st.caption(
        "Publica tu TFG/TFM orientativo y **recibe el 60% de cada venta**. "
        "Los proyectos son trabajos académicos — cualquier uso constructivo requiere visado colegial."
    )

    # Comprobar sesión propia del portal de estudiantes
    logged_in = st.session_state.get("est_session_logged", False)
    session_email = st.session_state.get("est_session_email", "")

    # Si viene del login general de la plataforma, aprovechamos ese email
    if not logged_in:
        general_email = (
            st.session_state.get("user_email", "")
            or st.session_state.get("client_email", "")
        )
        if general_email:
            st.session_state["est_session_email"] = general_email
            st.session_state["est_session_logged"] = True
            logged_in = True
            session_email = general_email

    if not logged_in:
        _mostrar_login_registro()
        return

    estudiante = _get_estudiante_by_email(session_email)

    if estudiante is None:
        _mostrar_registro(session_email)
    elif estudiante["estado"] == "pendiente":
        _mostrar_pendiente_aprobacion(estudiante)
    elif estudiante["estado"] == "rechazado":
        _mostrar_rechazado(estudiante)
    elif estudiante["estado"] == "aprobado":
        _mostrar_panel_estudiante(estudiante)


# ─── LOGIN / REGISTRO DE ACCESO ───────────────────────────────────────────────

def _mostrar_login_registro():
    st.markdown("---")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar sesión", "📝 Registrarse"])

    with tab_login:
        st.subheader("Accede a tu cuenta de estudiante")
        with st.form("est_login_form"):
            email_l = st.text_input("Email *", key="est_login_email")
            pw_l = st.text_input("Contraseña *", type="password", key="est_login_pw")
            ok = st.form_submit_button("Entrar")
        if ok:
            if not email_l or not pw_l:
                st.error("Introduce email y contraseña.")
                return
            est = _get_estudiante_by_email(email_l.strip().lower())
            if est is None:
                st.error("No existe ninguna cuenta con ese email. ¿Quieres registrarte?")
                return
            if est.get("password_hash") != _hash_pw(pw_l):
                st.error("Contraseña incorrecta.")
                return
            st.session_state["est_session_email"] = est["email"]
            st.session_state["est_session_logged"] = True
            st.rerun()

    with tab_reg:
        st.subheader("Crear cuenta de estudiante")
        st.info(
            "Introduce tu email y crea una contraseña para acceder al portal. "
            "A continuación completarás tu ficha de perfil."
        )
        with st.form("est_prereg_form"):
            email_r = st.text_input("Email *", key="est_prereg_email")
            pw_r1 = st.text_input("Contraseña *", type="password", key="est_prereg_pw1")
            pw_r2 = st.text_input("Repetir contraseña *", type="password", key="est_prereg_pw2")
            ok2 = st.form_submit_button("Continuar")
        if ok2:
            if not email_r or not pw_r1 or not pw_r2:
                st.error("Todos los campos son obligatorios.")
                return
            if pw_r1 != pw_r2:
                st.error("Las contraseñas no coinciden.")
                return
            if len(pw_r1) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
                return
            existing = _get_estudiante_by_email(email_r.strip().lower())
            if existing:
                st.warning("Ya existe una cuenta con ese email. Inicia sesión.")
                return
            # Guardar email + hash en session para pasar al formulario de registro
            st.session_state["est_pending_email"] = email_r.strip().lower()
            st.session_state["est_pending_hash"] = _hash_pw(pw_r1)
            st.session_state["est_session_email"] = email_r.strip().lower()
            st.session_state["est_session_logged"] = True
            st.rerun()


# ─── REGISTRO (perfil completo) ───────────────────────────────────────────────

def _mostrar_registro(email: str):
    st.subheader("📝 Completa tu perfil de estudiante")
    st.info(
        "Tu registro será revisado por el equipo de ArchiRapid. "
        "Recibirás confirmación en tu email en 24-48h."
    )

    with st.form("form_registro_estudiante"):
        st.markdown("**Datos personales**")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre completo *")
            telefono = st.text_input("Teléfono de contacto *")
        with col2:
            edad = st.number_input("Edad *", min_value=18, max_value=70, value=22, step=1)
            ciudad = st.text_input("Ciudad de residencia")

        st.markdown("**Datos académicos**")
        col3, col4 = st.columns(2)
        with col3:
            universidad = st.text_input("Universidad / Escuela de Arquitectura *")
            año_tfg = st.selectbox(
                "Año de presentación del TFG/TFM *",
                options=list(range(datetime.datetime.now().year, 2017, -1)),
            )
        with col4:
            año_carrera = st.selectbox("Curso actual / último cursado *", AÑOS_CARRERA)

        st.markdown("**Sobre ti**")
        bio = st.text_area("Breve descripción / especialidad (opcional)", max_chars=400)
        portfolio_url = st.text_input("URL portfolio, LinkedIn o Behance (opcional)")

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
            height=280,
            disabled=True,
        )
        acepta_autorizacion = st.checkbox(
            "Acepto la autorización de publicación y cesión de uso comercial"
        )

        submitted = st.form_submit_button("📨 Enviar solicitud de registro")

    if submitted:
        if not nombre or not universidad or not telefono:
            st.error("Nombre completo, teléfono y universidad son obligatorios.")
            return
        if not acepta_autorizacion:
            st.error("Debes aceptar la autorización para registrarte.")
            return
        _procesar_registro(
            email, nombre, universidad, año_tfg, ciudad, bio, portfolio_url,
            telefono, int(edad), año_carrera,
        )


def _procesar_registro(email, nombre, universidad, año_tfg, ciudad, bio,
                       portfolio_url, telefono, edad, año_carrera):
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    contenido = f"{AUTORIZACION_TEXTO}{email}{ts}{AUTORIZACION_VERSION}"
    hash_val = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    pdf_url = _generar_pdf_autorizacion(hash_val, email, nombre, ts)

    # Recuperar password_hash guardado durante el pre-registro
    pw_hash = st.session_state.pop("est_pending_hash", None)

    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO estudiantes
            (email, nombre_completo, universidad, año_tfg, ciudad,
             bio, portfolio_url, estado, hash_autorizacion, pdf_autorizacion_url,
             password_hash, telefono, edad, año_carrera)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?, ?, ?, ?)
            ON CONFLICT (email) DO NOTHING
        """, (email, nombre, universidad, año_tfg, ciudad, bio, portfolio_url,
              hash_val, pdf_url, pw_hash, telefono, edad, año_carrera))
        conn.commit()
    except Exception as e:
        st.error(f"Error al registrar: {e}")
        return
    finally:
        conn.close()

    st.success(
        f"✅ Solicitud enviada. Referencia: {hash_val[:16]}... "
        "Recibirás confirmación por email en 24-48h."
    )
    st.rerun()


# ─── ESTADOS INTERMEDIOS ──────────────────────────────────────────────────────

def _mostrar_pendiente_aprobacion(estudiante: dict):
    st.info(
        "⏳ Tu solicitud está pendiente de revisión por el equipo de ArchiRapid. "
        "En breve recibirás confirmación."
    )
    st.caption(f"Registrado el: {str(estudiante.get('created_at', ''))[:10]}")
    if st.button("← Volver", key="est_logout_pending", use_container_width=True):
        st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
        st.session_state.pop("est_session_logged", None)
        st.session_state.pop("est_session_email", None)
        try:
            del st.query_params["page"]
        except Exception:
            pass
        st.stop()


def _mostrar_rechazado(estudiante: dict):
    st.error(
        "❌ Tu solicitud no ha sido aprobada en esta ocasión. "
        "Contacta con soporte@archirapid.com para más información."
    )
    if st.button("← Volver", key="est_logout_rechazado", use_container_width=True):
        st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
        st.session_state.pop("est_session_logged", None)
        st.session_state.pop("est_session_email", None)
        try:
            del st.query_params["page"]
        except Exception:
            pass
        st.stop()


# ─── PANEL ESTUDIANTE APROBADO ────────────────────────────────────────────────

def _mostrar_panel_estudiante(estudiante: dict):
    col_w, col_out = st.columns([5, 1])
    with col_w:
        st.success(f"✅ Bienvenido/a, {estudiante['nombre_completo']}")
    with col_out:
        if st.button("← Volver", key="est_logout_panel", use_container_width=True):
            st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
            st.session_state.pop("est_session_logged", None)
            st.session_state.pop("est_session_email", None)
            try:
                del st.query_params["page"]
            except Exception:
                pass
            st.stop()

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
                   veces_vendido, activo, created_at, tipologia,
                   ejecutable, validado
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
        st.info("Aún no has subido ningún proyecto. Usa la pestaña '➕ Subir nuevo proyecto'.")
        return

    for r in rows:
        titulo, precio, modalidad, estado, vendido, activo, fecha = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        tipologia = r[7] if len(r) > 7 else ""
        ejecutable = r[8] if len(r) > 8 else ""
        validado = r[9] if len(r) > 9 else 0
        icono = "✅" if activo else ("⏳" if estado == "pendiente" else "❌")
        badge_val = "🏅 Validado" if validado else "⏳ Pendiente validación"
        with st.expander(f"{icono} {titulo} — {precio}€ · {badge_val}"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Precio", f"{precio}€")
            col2.metric("Modalidad", "Exclusivo" if modalidad == "exclusivo" else "Múltiple")
            col3.metric("Vendido", vendido or 0)
            col4.metric("Ejecutable", ejecutable or "—")
            st.caption(f"Tipología: {tipologia} | Estado: {estado} | Subido: {str(fecha)[:10]}")
            st.caption(f"Tu ganancia por venta: **{precio * 0.6:.0f}€** (60%)")


# ─── FORMULARIO SUBIR PROYECTO ────────────────────────────────────────────────

def _mostrar_form_subir_proyecto(estudiante: dict):
    st.subheader("➕ Subir proyecto TFG/TFM")
    st.caption(
        "Solo se acepta UN proyecto activo por estudiante. "
        "Debe haber sido presentado y evaluado favorablemente en tu universidad."
    )

    with st.form("form_subir_proyecto"):
        st.markdown("**Datos del proyecto**")
        titulo = st.text_input("Título del proyecto *")
        descripcion = st.text_area("Descripción del proyecto *", max_chars=600)

        col1, col2 = st.columns(2)
        with col1:
            tipologia = st.selectbox("Tipología *", TIPOLOGIAS)
            superficie = st.number_input("Superficie aproximada (m²)", min_value=10.0, step=5.0, value=120.0)
        with col2:
            provincia = st.selectbox("Provincia del proyecto", PROVINCIAS_ESPAÑA)
            ciudad_proy = st.text_input("Ciudad/Municipio del proyecto")

        col3, col4 = st.columns(2)
        with col3:
            ejecutable = st.selectbox(
                "¿El proyecto es ejecutable? *",
                ["Sí, es ejecutable", "No (orientativo)", "En estudio"],
                help="Ejecutable = documentación completa para solicitar licencia (con visado de arquitecto)."
            )
        with col4:
            nota_media = st.number_input(
                "Nota obtenida en la universidad (opcional)",
                min_value=0.0, max_value=10.0, step=0.1, value=0.0,
            )

        st.markdown("---")
        st.markdown("**Precio y modalidad de venta**")
        st.info(
            "💡 Precio recomendado por ArchiRapid: **1.900€** para un TFG estándar. "
            "Proyectos más completos (con CAD, memoria, renders) pueden valorarse más."
        )
        col5, col6 = st.columns(2)
        with col5:
            precio = st.number_input(
                "Precio de venta (€) *",
                min_value=500.0, max_value=50000.0, step=50.0, value=1900.0,
            )
        with col6:
            modalidad = st.selectbox(
                "Modalidad de venta *",
                ["exclusivo", "multiple"],
                format_func=lambda x: (
                    "Exclusivo (una sola venta — precio único)"
                    if x == "exclusivo"
                    else "Múltiple (varios compradores independientes)"
                ),
            )

        st.caption(
            f"💶 Recibirás **{precio * 0.6:.0f}€** por venta (60%). "
            f"ArchiRapid retiene {precio * 0.4:.0f}€ (40%)."
        )

        st.markdown("---")
        st.markdown("**Archivos del proyecto**")
        st.caption(
            "Sube todos los archivos que tengas. Cuantos más archivos, más valor y visibilidad tendrá tu proyecto."
        )

        imagen_portada = st.file_uploader(
            "Imagen de portada * (JPG / PNG)", type=["jpg", "jpeg", "png"]
        )
        fotos_extra = st.file_uploader(
            "Fotos adicionales / renders (JPG / PNG — puedes subir varias)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )
        archivo_planos = st.file_uploader(
            "Planos (PDF) *", type=["pdf"]
        )
        archivo_memoria = st.file_uploader(
            "Memoria descriptiva (PDF)", type=["pdf"]
        )
        archivo_cad = st.file_uploader(
            "Archivos CAD / BIM (DWG, DXF, IFC, RVT)", type=["dwg", "dxf", "ifc", "rvt"]
        )
        archivo_vr = st.file_uploader(
            "Tour virtual / Realidad Virtual (MP4, GLB, GLTF)",
            type=["mp4", "glb", "gltf"],
        )
        archivo_zip = st.file_uploader(
            "Paquete completo ZIP (si prefieres subir todo junto)", type=["zip"]
        )

        st.markdown("---")
        acepta = st.checkbox(
            "Confirmo que este proyecto ha sido presentado y evaluado "
            "favorablemente en mi universidad y soy su único/a autor/a"
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
            ejecutable, nota_media,
            imagen_portada, fotos_extra,
            archivo_planos, archivo_memoria,
            archivo_cad, archivo_vr, archivo_zip,
        )


def _procesar_subida_proyecto(
    estudiante, titulo, descripcion, tipologia,
    superficie, provincia, ciudad, precio, modalidad,
    ejecutable, nota_media,
    imagen_portada, fotos_extra,
    archivo_planos, archivo_memoria,
    archivo_cad, archivo_vr, archivo_zip,
):
    with st.spinner("Subiendo archivos... puede tardar unos segundos."):
        try:
            url_portada = save_upload(imagen_portada, prefix="portada_tfg")
            url_planos  = save_upload(archivo_planos,  prefix="planos_tfg")

            url_memoria = save_upload(archivo_memoria, prefix="memoria_tfg") if archivo_memoria else None
            url_cad     = save_upload(archivo_cad,     prefix="cad_tfg")     if archivo_cad     else None
            url_vr      = save_upload(archivo_vr,      prefix="vr_tfg")      if archivo_vr      else None
            url_zip     = save_upload(archivo_zip,     prefix="zip_tfg")     if archivo_zip     else None

            # Fotos extra (lista)
            fotos_list = []
            if fotos_extra:
                for f in fotos_extra:
                    u = save_upload(f, prefix="foto_tfg")
                    if u:
                        fotos_list.append(u)
            fotos_json = json.dumps(fotos_list) if fotos_list else None

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
             estado, activo, comision_archirapid, comision_estudiante,
             ejecutable, validado, archivo_cad_url, archivo_vr_url, fotos_urls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', 0,
                    40.0, 60.0, ?, 0, ?, ?, ?)
        """, (
            estudiante["id"], estudiante["email"], titulo, descripcion,
            superficie, tipologia, precio, modalidad, provincia, ciudad,
            url_planos, url_memoria,
            url_zip,          # archivo_renders_url reutilizado para ZIP si no hay renders separados
            url_portada, hash_doc,
            ejecutable, url_cad, url_vr, fotos_json,
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


# ─── TARIFAS DE SERVICIOS ─────────────────────────────────────────────────────

def _mostrar_tarifas_profesional(email: str, proveedor_id: int, tipo: str = "arquitecto"):
    st.subheader("💶 Mis tarifas de servicios")
    st.caption(
        "Define el precio de cada servicio que ofreces. "
        "Los precios mínimos están fijados por ArchiRapid."
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
                    f"Tu precio (€)",
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

            if st.button("💾 Guardar tarifa", key=f"save_{servicio_key}_{email}"):
                _guardar_tarifa(
                    email, proveedor_id, tipo,
                    servicio_key, nuevo_precio,
                    float(servicio_info["minimo"]), nuevo_activo,
                )
                st.success("Tarifa guardada.")
                st.rerun()


def _guardar_tarifa(email, proveedor_id, tipo, servicio, precio, minimo, activo):
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE tarifas_profesionales
            SET precio = ?, activo = ?, updated_at = datetime('now')
            WHERE email = ? AND servicio = ?
        """, (precio, 1 if activo else 0, email, servicio))
        if cur.rowcount == 0:
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


# ─── GENERADOR PDF AUTORIZACIÓN ───────────────────────────────────────────────

def _generar_pdf_autorizacion(hash_val: str, email: str, nombre: str, timestamp: str) -> str:
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
        ).replace("[HASH_SHA256]", hash_val).replace("[VERSION]", AUTORIZACION_VERSION)

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
