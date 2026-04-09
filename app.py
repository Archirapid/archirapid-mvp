"""
BLOQUEO DOCUMENTAL - SECCIÓN "PROYECTOS DISPONIBLES"

Esta sección está BLINDADA y protegida contra modificaciones no autorizadas.

INPUTS (lectura):
- Parámetros: client_email (email del cliente logueado)
- Session State: last_search_params_v2 (parámetros de búsqueda previos), client_logged_in (estado de login)
- DB Reads: projects (lista de proyectos), ventas_proyectos (verificación de compras previas)
- Dependencias: get_proyectos_compatibles() (función de filtrado)

OUTPUTS (efectos):
- Session State: last_search_params_v2 (actualización de filtros)
- Query Params: selected_project_v2 (ID de proyecto seleccionado para navegación)
- DB Writes: ventas_proyectos (registro de compras PDF/CAD)
- UI Effects: Grid de proyectos, filtros, mensajes de compra, reruns

ADVERTENCIA: NO modificar lógica interna sin romper contrato.
Cualquier cambio debe pasar por el wrapper render_projects_available(ctx).
Usar solo el wrapper como punto de entrada desde fuera de la sección.
"""

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import os

# Streamlit Cloud: sync secrets → os.environ so all os.getenv() calls work in production
try:
    import streamlit as _st_secrets
    for _sk, _sv in _st_secrets.secrets.items():
        if isinstance(_sv, str):
            os.environ.setdefault(_sk, _sv)
except Exception:
    pass
import json
import threading
import http.server
import socketserver
import time
from pathlib import Path
from src import db as _db
from modules.marketplace.utils import init_db, db_conn
from modules.marketplace.marketplace import get_project_display_image
from modules.ai_house_designer import flow as ai_house_flow
from modules.marketplace.compatibilidad import get_proyectos_compatibles

# Inicializar base de datos — solo UNA VEZ por worker (no en cada rerun)
@_st_secrets.cache_resource(show_spinner=False)
def _init_app_db():
    init_db()
    _db.ensure_tables()
    return True

_init_app_db()

# Configurar página con layout amplio
import streamlit as st
st.set_page_config(layout='wide', initial_sidebar_state="expanded")

# ══════════════════════════════════════════════════════════════════
# SINCRONIZADOR MAESTRO — la URL es la ÚNICA fuente de verdad.
# Corre ANTES de cualquier widget. Un solo rerun por cambio de URL.
# Resuelve: botón Atrás cambia URL pero el radio del sidebar restaura
# la página anterior porque Streamlit rehidrata los widgets primero.
# ══════════════════════════════════════════════════════════════════
_SLUG_TO_PAGE_MASTER = {
    "home":          "🏠 Inicio / Marketplace",
    "admin":         "Intranet",
    "propietarios":  "🏠 Propietarios",
    "gemelo":        "Propietario (Gemelo Digital)",
    "lola":          "💬 Lola",
    "login":         "Iniciar Sesión",
    "registro":      "Registro de Usuario",
    "cliente":       "👤 Panel de Cliente",
    "disenador":     "Diseñador de Vivienda",
    "arquitectos":   "Arquitectos (Marketplace)",
    "proveedor":     "👤 Panel de Proveedor",
    "registro-pro":  "📝 Registro de Proveedor de Servicios",
    "mls":           "🏢 Inmobiliarias MLS",
    "estudiantes":   "🎓 Estudiantes",
    "prefabricadas": "🏠 Portal Prefabricadas",
}

_page_from_url = st.query_params.get("page", "home")
if st.session_state.get("current_page_sync") != _page_from_url:
    # URL cambió (botón Atrás o enlace externo) → forzar estado desde URL
    st.session_state["current_page_sync"] = _page_from_url
    _target = _SLUG_TO_PAGE_MASTER.get(_page_from_url, "🏠 Inicio / Marketplace")
    st.session_state["selected_page"] = _target
    # Borrar la key del widget radio para que Streamlit no restaure el valor antiguo
    st.session_state.pop("_nav_radio", None)
    # Limpiar flags de login si volvemos a home
    if _page_from_url in ("home", ""):
        st.session_state.pop("viewing_login", None)
        st.session_state.pop("login_role", None)
    st.rerun()
# ══════════════════════════════════════════════════════════════════

st.markdown("""
    <style>
        /* 1. Atacar el contenedor raíz de Streamlit */
        #root > div:nth-child(1) > div > div > div > div > section > div {
            padding-top: 0rem !important;
        }

        /* 2. Eliminar márgenes del visualizador de la app */
        .main .block-container {
            padding-top: 0rem !important;
            margin-top: -3rem !important;
        }

        /* 3. Forzar el Header a ser visible y no ocupar espacio */
        header[data-testid="stHeader"] {
            background: transparent !important;
            position: fixed !important;
            top: 0 !important;
            z-index: 999 !important;
        }

        /* 4. Rescatar el botón de 3 puntos por ID */
        [data-testid="stHeader"] > div:first-child {
            display: flex !important;
        }

        /* 5. Compactar el primer bloque de contenido (título) */
        [data-testid="stVerticalBlock"] {
            gap: 0rem !important;
        }

    </style>
""", unsafe_allow_html=True)

# ── CSS responsivo móvil (solo activa en <= 768px, desktop intacto) ───────────
from modules.marketplace.mobile_css import inject as _inject_mobile_css
_inject_mobile_css()

# Ocultar sidebar visualmente (navegación se mantiene funcional vía session_state)
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ===== LOLA WIDGET FLOTANTE (antes de cualquier st.stop()) =====
from lola_widget import render_lola
render_lola()

# ── Browser back/forward: forzar recarga cuando URL cambia via historial ──────
st.components.v1.html("""
<script>
(function(){
  if(window._archirapid_popstate_registered) return;
  window._archirapid_popstate_registered = true;
  window.addEventListener('popstate', function(){
    window.location.reload();
  });
})();
</script>
""", height=0)

# HARDCODE DE ROL PARA PRUEBA
if st.session_state.get('email') == 'asdfg@lkj.com': st.session_state['role'] = 'owner'

# 🛡️ BLINDAJE ABSOLUTO OWNER
if st.session_state.get("role") == "owner":
    from modules.marketplace import owners
    owners.main()
    st.stop()

# === FUNCIONES AUXILIARES V2 ===

def detalles_proyecto_v2(project_id: str):
    """Muestra la página de vista previa de un proyecto arquitectónico - VERSIÓN V2"""
    # Verificar si el usuario está logueado como cliente
    client_logged_in = st.session_state.get("client_logged_in", False)
    client_email = st.session_state.get("client_email", "")

    if client_logged_in and client_email:
        # Usuario registrado: mostrar panel completo con pestaña COMPRA
        from modules.marketplace import client_panel
        client_panel.show_selected_project_panel(client_email, project_id)
    else:
        # Usuario no registrado: mostrar vista previa limitada
        from modules.marketplace.project_detail import show_project_detail_page
        show_project_detail_page(project_id)

def panel_cliente_v2():
    from modules.marketplace import client_panel
    return client_panel.main()


def route_main_panel():
    selected_page = st.session_state.get("selected_page")
    # Bloque de Seguridad: Si el rol es owner, la página DEBE ser Propietarios
    if st.session_state.get('role') == 'owner':
        st.session_state['selected_page'] = "🏠 Propietarios"
    user_role = st.session_state.get("user_role", "buyer")
    
    if selected_page == "🏠 Propietarios":
        from modules.marketplace import owners
        owners.main()
    elif selected_page == "👤 Panel de Cliente":
        if user_role == "buyer":
            from modules.marketplace import client_panel
            client_panel.main()
        elif user_role == "owner":
            from modules.marketplace import owners
            owners.main()
        elif user_role == "architect":
            from modules.marketplace import architects
            architects.main()
        else:
            st.error("Error: Rol de usuario no reconocido para el panel de cliente")


def show_selected_project_panel_v2(client_email: str, project_id: str):
    """Panel para mostrar proyecto seleccionado con detalles completos y opciones de compra - V2"""
    st.subheader("🏗️ Proyecto Arquitectónico Seleccionado V2")

    # Obtener datos completos del proyecto
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, m2_construidos, area_m2, price, estimated_cost,
               price_memoria, price_cad, property_type, foto_principal, galeria_fotos,
               memoria_pdf, planos_pdf, planos_dwg, modelo_3d_glb, vr_tour, energy_rating,
               architect_name, characteristics_json, habitaciones, banos, garaje, plantas,
               m2_parcela_minima, m2_parcela_maxima, certificacion_energetica, tipo_proyecto
        FROM projects
        WHERE id = ?
    """, (project_id,))
    row = cursor.fetchone()

    if not row:
        st.error("❌ Proyecto no encontrado")
        conn.close()
        return

    # Extraer datos del proyecto
    project_data = {
        'id': row[0],
        'title': row[1],
        'description': row[2],
        'm2_construidos': row[3],
        'area_m2': row[4],
        'price': row[5],
        'estimated_cost': row[6],
        'price_memoria': row[7] or 1800,
        'price_cad': row[8] or 2500,
        'property_type': row[9],
        'foto_principal': row[10],
        'galeria_fotos': row[11],
        'memoria_pdf': row[12],
        'planos_pdf': row[13],
        'planos_dwg': row[14],
        'modelo_3d_glb': row[15],
        'vr_tour': row[16],
        'energy_rating': row[17],
        'architect_name': row[18],
        'characteristics': json.loads(row[19]) if row[19] else {},
        'habitaciones': row[20],
        'banos': row[21],
        'garaje': row[22],
        'plantas': row[23],
        'm2_parcela_minima': row[24],
        'm2_parcela_maxima': row[25],
        'certificacion_energetica': row[26],
        'tipo_proyecto': row[27]
    }

    # Calcular superficie mínima requerida
    m2_proyecto = project_data['m2_construidos'] or project_data['area_m2'] or 0
    if project_data['m2_parcela_minima']:
        superficie_minima = project_data['m2_parcela_minima']
    else:
        superficie_minima = m2_proyecto / 0.33 if m2_proyecto > 0 else 0

    # Título principal
    st.title(f"🏗️ {project_data['title']}")
    st.markdown(f"**👨‍💼 Arquitecto:** {project_data['architect_name'] or 'No especificado'}")

    # Galería completa de fotos
    st.header("📸 Galería Completa del Proyecto")

    # Obtener imágenes válidas usando la función existente
    project_images = get_project_display_image(project_id, 'gallery')

    if project_images:
        # Mostrar imágenes en grid responsivo
        cols = st.columns(min(len(project_images), 3))
        for idx, img_path in enumerate(project_images):
            with cols[idx % 3]:
                try:
                    st.image(img_path, width='stretch', caption=f"Imagen {idx + 1}")
                except Exception as e:
                    st.warning(f"No se pudo cargar la imagen {idx + 1}")
    else:
        st.info("No hay imágenes disponibles para este proyecto")

    # Información técnica completa
    st.header("📋 Información Técnica Completa")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏠 Características Constructivas")
        st.write(f"**Superficie construida:** {m2_proyecto:.0f} m²")
        st.write(f"**Superficie mínima de terreno:** {superficie_minima:.0f} m²")
        if project_data['m2_parcela_maxima']:
            st.write(f"**Superficie máxima de terreno:** {project_data['m2_parcela_maxima']:.0f} m²")
        st.write(f"**Tipo:** {project_data['property_type'] or project_data['tipo_proyecto'] or 'Residencial'}")

        # Características específicas
        if project_data['habitaciones']:
            st.write(f"**Habitaciones:** {project_data['habitaciones']}")
        if project_data['banos']:
            st.write(f"**Baños:** {project_data['banos']}")
        if project_data['plantas']:
            st.write(f"**Plantas:** {project_data['plantas']}")
        if project_data['garaje']:
            st.write(f"**Garaje:** {'Sí' if project_data['garaje'] else 'No'}")

        # Certificación energética
        if project_data.get('certificacion_energetica') or project_data.get('energy_rating'):
            rating = project_data.get('certificacion_energetica') or project_data.get('energy_rating', 'A')
            st.write(f"**Certificación energética:** {rating}")

    with col2:
        st.subheader("💰 Información Económica")
        if project_data['estimated_cost']:
            st.write(f"**Coste de ejecución aproximado:** €{project_data['estimated_cost']:,.0f}")
        st.write("**Precio descarga prefiguración arquitectónica:**")
        st.write(f"• 📄 PDF (Memoria completa): €{project_data['price_memoria']}")
        st.write(f"• 🖥️ CAD (Planos editables): €{project_data['price_cad']}")
        total_price = project_data['price_memoria'] + project_data['price_cad']
        st.write(f"• 💰 **TOTAL:** €{total_price}")

    # Descripción completa
    if project_data['description']:
        st.header("📝 Descripción del Proyecto")
        st.write(project_data['description'])

    # Características adicionales
    if project_data['characteristics']:
        st.header("✨ Características Adicionales")
        chars = project_data['characteristics']
        if isinstance(chars, dict):
            for key, value in chars.items():
                st.write(f"• **{key}:** {value}")

    # SISTEMA DE COMPRA
    st.header("🛒 Adquirir Proyecto Completo")

    # Verificar si ya compró este proyecto
    cursor.execute("SELECT id FROM ventas_proyectos WHERE proyecto_id = ? AND cliente_email = ?", (project_id, client_email))
    ya_comprado = cursor.fetchone()
    conn.close()

    if ya_comprado:
        st.success("✅ **Ya has adquirido este proyecto**")
        st.info("Puedes descargar los archivos desde la sección 'Mis Proyectos'")

        # Mostrar botones de descarga
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 Descargar Memoria PDF", width='stretch', type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col2:
            if st.button("🖥️ Descargar Planos CAD", width='stretch', type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col3:
            if st.button("🏗️ Descargar Modelo 3D", width='stretch', type="primary"):
                st.info("Descarga iniciada... (simulado)")

    else:
        st.info("💳 Selecciona el producto que deseas adquirir:")

        col_pdf, col_cad = st.columns(2)

        with col_pdf:
            if st.button(f"📄 Comprar Memoria PDF - €{project_data['price_memoria']}", width='stretch', type="primary"):
                # Simular compra directa de PDF
                with st.spinner("Procesando compra de PDF..."):
                    import time
                    time.sleep(1)
                st.success("🎉 **PDF comprado con éxito!**")
                st.info("📧 Recibirás el enlace de descarga por email")

        with col_cad:
            if st.button(f"🖥️ Comprar Planos CAD - €{project_data['price_cad']}", width='stretch', type="primary"):
                # Simular compra directa de CAD
                with st.spinner("Procesando compra de CAD..."):
                    import time
                    time.sleep(1)
                st.success("🎉 **CAD comprado con éxito!**")
                st.info("📧 Recibirás el enlace de descarga por email")

    # FINCAS COMPATIBLES DEL USUARIO
    st.header("🏠 Fincas Compatibles")

    # Obtener fincas del usuario (compradas o propias)
    conn = db_conn()
    cursor = conn.cursor()

    # Fincas compradas
    cursor.execute("""
        SELECT p.id, p.title, p.surface_m2, p.buildable_m2
        FROM reservations r
        JOIN plots p ON r.plot_id = p.id
        WHERE r.buyer_email = ?
    """, (client_email,))

    fincas_compradas = cursor.fetchall()

    # Fincas propias (si es propietario)
    cursor.execute("""
        SELECT id, title, surface_m2, buildable_m2
        FROM plots
        WHERE owner_email = ?
    """, (client_email,))

    fincas_propias = cursor.fetchall()
    conn.close()

    fincas_usuario = fincas_compradas + fincas_propias

    if fincas_usuario:
        for finca in fincas_usuario:
            finca_id, finca_title, surface_m2, buildable_m2 = finca

            # Calcular superficie edificable
            superficie_edificable = buildable_m2 if buildable_m2 else surface_m2 * 0.33

            # Verificar compatibilidad
            compatible = False
            if m2_proyecto <= superficie_edificable:
                compatible = True

            with st.expander(f"🏠 {finca_title} - {'✅ Compatible' if compatible else '❌ No compatible'}", expanded=compatible):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Superficie total:** {surface_m2} m²")
                    st.write(f"**Superficie edificable:** {superficie_edificable:.0f} m²")
                    st.write(f"**Proyecto requiere:** {m2_proyecto:.0f} m²")

                with col2:
                    if compatible:
                        st.success("🎯 **¡Perfecto match!** Este proyecto cabe en tu finca")
                        if st.button(f"🚀 Diseñar en {finca_title}", key=f"design_v2_{finca_id}", width="stretch"):
                            st.info("🎨 Redirigiendo al diseñador... (próximamente)")
                    else:
                        deficit = m2_proyecto - superficie_edificable
                        st.warning(f"⚠️ Necesitas {deficit:.0f} m² más de superficie edificable")
    else:
        st.info("No tienes fincas registradas. Para usar este proyecto, primero compra una finca compatible.")

    # ACCIONES ADICIONALES
    st.header("🎯 ¿Qué deseas hacer ahora?")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📋 Ver Más Proyectos", width="stretch"):
            st.query_params.clear()
            st.query_params["page"] = "home"
            st.rerun()

    with col2:
        if st.button("🛒 Mi Historial de Compras", width='stretch'):
            # Limpiar proyecto seleccionado para mostrar panel normal
            if "selected_project_v2" in st.query_params:
                del st.query_params["selected_project_v2"]
            st.rerun()

    with col3:
        if st.button("📧 Contactar Arquitecto", width='stretch'):
            st.info(f"📧 Contacto: {project_data['architect_name'] or 'Equipo ARCHIRAPID'}")
            st.write("Email: proyectos@archirapid.com")
            st.write("Teléfono: +34 900 123 456")


def registro_v2():
    """Página de registro de usuario - Versión Profesional"""
    st.title("📝 Registro de Usuario - ARCHIRAPID")
    st.info("Regístrate para acceder a todos los proyectos y funcionalidades avanzadas")

    with st.form("registro_simple_v2"):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre", placeholder="Tu nombre")
            apellidos = st.text_input("Apellidos", placeholder="Tus apellidos")
            telefono = st.text_input("Teléfono", placeholder="+34 600 000 000")

        with col2:
            email = st.text_input("Email", placeholder="tu@email.com")
            confirmar_email = st.text_input("Confirmar Email", placeholder="tu@email.com")
            direccion = st.text_input("Dirección", placeholder="Calle, Ciudad, Provincia")

        submitted = st.form_submit_button("🚀 Registrarme", type="primary", width='stretch')

        if submitted:
            # Validaciones básicas
            if not nombre or not apellidos or not email:
                st.error("Por favor completa nombre, apellidos y email")
            elif email != confirmar_email:
                st.error("Los emails no coinciden")
            elif "@" not in email:
                st.error("Por favor introduce un email válido")
            else:
                # Registrar usuario en base de datos
                try:
                    from src import db
                    conn = db.get_conn()
                    cursor = conn.cursor()

                    # Verificar si el email ya existe
                    cursor.execute("SELECT id FROM clients WHERE email = ?", (email,))
                    existing = cursor.fetchone()

                    if existing:
                        st.info("Ya estabas registrado. Accediendo...")
                    else:
                        # Insertar nuevo cliente (combinar nombre y apellidos)
                        full_name = f"{nombre} {apellidos}".strip()
                        cursor.execute("""
                            INSERT INTO clients (name, email, phone, address, created_at)
                            VALUES (?, ?, ?, ?, datetime('now'))
                        """, (full_name, email, telefono, direccion))

                        st.info("Registro completado. Accediendo...")

                    conn.commit()
                    conn.close()

                    # Auto-login
                    st.session_state["client_logged_in"] = True
                    st.session_state["client_email"] = email
                    st.session_state["user_role"] = "buyer"
                    st.session_state["has_transactions"] = False
                    st.session_state["has_properties"] = False

                    # Si venía viendo un proyecto específico, guardarlo para mostrar los botones de compra
                    if "proyecto_seleccionado" in st.session_state and st.session_state["proyecto_seleccionado"]:
                        project_id = st.session_state["proyecto_seleccionado"].get("id")
                        if project_id:
                            st.session_state["selected_project_for_panel"] = project_id

                    # Redirigir de vuelta al Marketplace con sesión activa
                    st.query_params["page"] = "home"
                    st.rerun()

                except Exception as e:
                    st.error(f"Error en el registro: {e}")

    st.markdown("---")
    st.info("💡 **¿Ya tienes cuenta?** Si has realizado compras anteriores, accede directamente desde el panel de cliente.")


# === SCROLL TO TOP ON NAVIGATION ===
_nav_route = str(dict(st.query_params)) + "|" + st.session_state.get('selected_page', '')
if st.session_state.get('_nav_route') != _nav_route:
    st.session_state['_nav_route'] = _nav_route
    st.components.v1.html(
        "<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>",
        height=0
    )

# ═══════════════════════════════════════════════════════════════════════
# DEEP LINKS — tracking de origen y modo demo
# Soporta: ?seccion=arquitecto  ?from=linkedin  ?user=javier  ?demo=true
# ═══════════════════════════════════════════════════════════════════════
def _registrar_visita_demo(origen, nombre, accion):
    """Guarda una visita en visitas_demo. Silencioso si falla."""
    try:
        import uuid as _uuid
        from datetime import datetime as _dt
        from modules.marketplace.utils import db_conn as _dbc
        _conn = _dbc(); _c = _conn.cursor()
        _c.execute("""INSERT OR IGNORE INTO visitas_demo
                      (id,timestamp,origen,nombre_usuario,accion_realizada,session_id)
                      VALUES (?,?,?,?,?,?)""",
                   (_uuid.uuid4().hex, _dt.utcnow().isoformat(),
                    origen, nombre, accion,
                    st.session_state.get("_demo_session_id", "")))
        _conn.commit(); _conn.close()
    except Exception:
        pass

_qp_seccion = st.query_params.get("seccion", "")
_qp_from    = st.query_params.get("from", "")
_qp_ref     = st.query_params.get("ref", "")   # alias de ?from — para links de campaña
_qp_user    = st.query_params.get("user", "")
_qp_demo    = st.query_params.get("demo", "")
_qp_modo    = st.query_params.get("modo", "")

# ── Handlers retorno Stripe MLS y deep links MLS ─────────────────────────────
_qp_mls_pago    = st.query_params.get("mls_pago", "")
_qp_mls_reserva = st.query_params.get("mls_reserva_ok", "")
_qp_mls_ficha    = st.query_params.get("mls_ficha", "")
_qp_mls_goto       = st.query_params.get("mls_goto_finca", "")
_qp_mls_reset_tok  = st.query_params.get("mls_reset_token", "")
_qp_mls_reservar   = st.query_params.get("mls_reservar", "")
_qp_mls_contacto = st.query_params.get("mls_contacto", "")
if _qp_mls_pago == "ok":
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["_nav_radio"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_verificar_pago"] = True

if _qp_mls_reserva == "1":
    if st.query_params.get("tipo") == "cliente_directo":
        # Retorno Stripe cliente directo → página pública de confirmación
        st.session_state["selected_page"] = "_mls_retorno_cliente"
    else:
        # Retorno Stripe inmo colaboradora → portal MLS (lo gestiona internamente)
        st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
        st.session_state["_nav_radio"] = "🏢 Inmobiliarias MLS"

if _qp_mls_reset_tok:
    # Enlace de reset contraseña MLS — sin login requerido
    st.session_state["selected_page"] = "_mls_reset_password"
    st.session_state["mls_reset_token"] = _qp_mls_reset_tok

if _qp_mls_goto:
    # Solo procesar la primera vez — evita resetear navegación en cada rerun
    # mientras ?mls_goto_finca= sigue en la URL
    if st.session_state.get("_mls_goto_last") != _qp_mls_goto:
        st.session_state["_mls_goto_last"]   = _qp_mls_goto
        st.session_state["_mls_goto_active"] = True   # activa el bypass-tabs
        if st.session_state.get("mls_inmo"):
            st.session_state["mls_ficha_id"] = _qp_mls_goto
            st.session_state["mls_vista"]    = "ficha"
        else:
            st.session_state["mls_goto_finca_pending"] = _qp_mls_goto
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["_nav_radio"] = "🏢 Inmobiliarias MLS"

if _qp_mls_ficha:
    # Ficha pública — sin login requerido
    st.session_state["selected_page"] = "_mls_ficha_publica"
    st.session_state["mls_ficha_id"] = _qp_mls_ficha

if _qp_mls_reservar:
    # Reserva pública €200 — sin login requerido
    st.session_state["selected_page"] = "_mls_reservar_publica"
    st.session_state["mls_reservar_id"] = _qp_mls_reservar

if _qp_mls_contacto:
    # Contacto público — sin login requerido
    st.session_state["selected_page"] = "_mls_contacto_publica"
    st.session_state["mls_contacto_id"] = _qp_mls_contacto
# ─────────────────────────────────────────────────────────────────────────────

# ref y from son equivalentes; ref tiene prioridad si ambos presentes
_qp_origen = _qp_ref or _qp_from

# Generar session_id único para esta visita (solo una vez por sesión)
if "_demo_session_id" not in st.session_state:
    import uuid as _uuid_mod
    st.session_state["_demo_session_id"] = _uuid_mod.uuid4().hex

# Registrar origen una sola vez por sesión (demo=true o seccion=arquitecto/mls)
_es_visita_demo = _qp_demo == "true" or _qp_seccion in ("arquitecto", "mls")
if _es_visita_demo and not st.session_state.get("_origen_registrado"):
    _origen_final = _qp_origen or "directo"
    _registrar_visita_demo(_origen_final, _qp_user or "anonimo", f"visita:{_qp_seccion or 'home'}")
    st.session_state["_origen_registrado"] = True
    st.session_state["_visit_from"] = _origen_final

# Mensaje de bienvenida personalizado
if _qp_user and not st.session_state.get("_welcome_shown"):
    _nombre_display = _qp_user.capitalize()
    st.toast(f"Bienvenido, {_nombre_display}. Prueba ArchiRapid en directo.", icon="👋")
    st.session_state["_welcome_shown"] = True

# Activar sandbox si ?demo=true
if _qp_demo == "true" and not st.session_state.get("sandbox_mode"):
    st.session_state["sandbox_mode"] = True
    st.session_state["sandbox_user"] = _qp_user.capitalize() if _qp_user else "Visitante"

# Navegar directo al portal del arquitecto si ?seccion=arquitecto
if _qp_seccion == "arquitecto" and not st.session_state.get("_deep_link_routed"):
    st.session_state["selected_page"] = "Arquitectos (Marketplace)"
    st.session_state["_nav_radio"] = "Arquitectos (Marketplace)"
    st.session_state["_deep_link_routed"] = True
    # Si sandbox + modo estudio, marcar para abrir esa pestaña al entrar
    if _qp_modo == "estudio" or _qp_demo == "true":
        st.session_state["_open_estudio_tab"] = True

# Navegar directo al portal MLS si ?seccion=mls
if _qp_seccion == "mls" and not st.session_state.get("_deep_link_routed"):
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["_nav_radio"] = "🏢 Inmobiliarias MLS"
    st.session_state["_deep_link_routed"] = True
    if _qp_demo == "true":
        st.session_state["mls_demo_mode"] = True

# --- ÁRBITRO DE NAVEGACIÓN (Sincronización Botón Atrás) ---
# Mapeo slug → página (debe definirse antes de usarse)
_SLUG_TO_PAGE = {
    "home":          "🏠 Inicio / Marketplace",
    "admin":         "Intranet",
    "propietarios":  "🏠 Propietarios",
    "gemelo":        "Propietario (Gemelo Digital)",
    "lola":          "💬 Lola",
    "login":         "Iniciar Sesión",
    "registro":      "Registro de Usuario",
    "cliente":       "👤 Panel de Cliente",
    "disenador":     "Diseñador de Vivienda",
    "arquitectos":   "Arquitectos (Marketplace)",
    "proveedor":     "👤 Panel de Proveedor",
    "registro-pro":  "📝 Registro de Proveedor de Servicios",
    "mls":           "🏢 Inmobiliarias MLS",
    "estudiantes":   "🎓 Estudiantes",
    "prefabricadas": "🏠 Portal Prefabricadas",
}

_current_url_page = st.query_params.get("page", "home")
_last_sync_page = st.session_state.get("last_synced_page", "home")

# Actualizar last_synced_page sin rerun — el Sincronizador Maestro ya hizo
# el rerun necesario antes de llegar aquí. Solo actualizamos el guard.
if _current_url_page != _last_sync_page:
    st.session_state["last_synced_page"] = _current_url_page
    _target_title = _SLUG_TO_PAGE.get(_current_url_page, "🏠 Inicio / Marketplace")
    st.session_state["selected_page"] = _target_title
    st.session_state["_nav_radio"] = _target_title
    if _current_url_page == "login":
        st.session_state["viewing_login"] = True
    else:
        st.session_state["viewing_login"] = False
    # NO st.rerun() aquí — el Sincronizador Maestro ya resolvió la URL

_url_slug = st.query_params.get("page", "")
# ?page=login → mostrar formulario de login genérico en home
if _url_slug == "login":
    st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
    st.session_state["_nav_radio"] = "🏠 Inicio / Marketplace"
    st.session_state["viewing_login"] = True
    st.session_state["show_role_selector"] = False
    if st.session_state.get("login_role") is None:
        st.session_state["login_role"] = None
elif _url_slug in _SLUG_TO_PAGE:
    # Siempre sincronizar desde URL — permite que el botón atrás del navegador funcione
    _target_page = _SLUG_TO_PAGE[_url_slug]
    if st.session_state.get("selected_page") != _target_page:
        st.session_state["selected_page"] = _target_page
        st.session_state["show_role_selector"] = False
        st.session_state["viewing_login"] = False
    # Pre-configurar sidebar radio para que no sobreescriba con su estado previo
    st.session_state["_nav_radio"] = _target_page
elif _url_slug == "":
    # URL limpia (sin ?page=) y sin params especiales → volver a home
    _keep_params = {"selected_plot", "selected_project_v2", "selected_prefab",
                    "mls_ficha", "mls_reservar", "mls_contacto", "seccion",
                    "stripe_session", "payment", "sp_pago_ok", "sp_comision_ok",
                    "mls_pago", "mls_reserva_ok", "mls_goto_finca", "mls_reset_token",
                    "mls_reservar", "reset_token"}
    if not any(p in st.query_params for p in _keep_params):
        if st.session_state.get("selected_page") not in ("🏠 Inicio / Marketplace", None):
            st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
            st.session_state["_nav_radio"] = "🏠 Inicio / Marketplace"
            st.session_state["show_role_selector"] = False
            st.session_state["viewing_login"] = False

# === RUTA PÚBLICA: ?page=stats (sin login) ===
if st.query_params.get("page") == "stats":
    try:
        from modules.marketplace.stats_public import render as _render_stats
        _render_stats()
    except Exception as _se:
        st.error(f"Error cargando estadísticas: {_se}")
    st.stop()

# === RUTA PÚBLICA: ?page=privacidad ===
if st.query_params.get("page") == "privacidad":
    try:
        from modules.marketplace.privacidad import render as _render_priv
        _render_priv()
    except Exception as _pe:
        st.error(f"Error cargando política de privacidad: {_pe}")
    st.stop()

# === RUTA PÚBLICA: ?reset_token=XXX (recuperar contraseña) ===
if st.query_params.get("reset_token"):
    try:
        from modules.marketplace.password_reset import show_reset_password
        show_reset_password(st.query_params["reset_token"])
    except Exception as _re:
        st.error(f"Error en recuperación de contraseña: {_re}")
    st.stop()

# === RUTA PÚBLICA: ?page=recuperar_contrasena ===
if st.query_params.get("page") == "recuperar_contrasena":
    try:
        from modules.marketplace.password_reset import show_forgot_password
        show_forgot_password()
    except Exception as _fe:
        st.error(f"Error en recuperación de contraseña: {_fe}")
    st.stop()

# === STRIPE: verificar pago al volver de Checkout ===
if st.query_params.get("stripe_session") and st.query_params.get("payment") == "success":
    _ss_id = st.query_params["stripe_session"]
    if not st.session_state.get(f"stripe_verified_{_ss_id}"):
        try:
            from modules.stripe_utils import verify_session as _stripe_verify
            import sqlite3 as _sq3
            _sess = _stripe_verify(_ss_id)
            if _sess.payment_status == "paid":
                # StripeObject en SDK antiguo es dict-subclass; en SDK nuevo (Py3.14) usa _data
                _raw_meta = _sess.metadata
                if not _raw_meta:
                    _meta = {}
                elif isinstance(_raw_meta, dict):
                    _meta = dict(_raw_meta)
                else:
                    _meta = dict(getattr(_raw_meta, '_data', {}))
                _proj_id  = _meta.get("project_id", "")
                _cli_mail = _meta.get("client_email", "") or (_sess.customer_email or "")
                _prods    = _meta.get("products", "")
                _amount   = (_sess.amount_total or 0) / 100
                if _meta.get("type") == "plot_reservation":
                    # ── Reserva de finca: confirmar pago y auto-login ──
                    _plot_id_r  = _meta.get("plot_id", "")
                    _pending_id = _meta.get("pending_id", "")
                    _buyer_mail = _meta.get("buyer_email", "") or _cli_mail
                    _buyer_name = _meta.get("buyer_name", "")
                    if not st.session_state.get(f"stripe_verified_{_ss_id}"):
                        try:
                            from src.db import get_conn as _get_db_r
                            _conn_r = _get_db_r()
                            if _pending_id:
                                _conn_r.execute(
                                    "UPDATE reservations SET kind='reservation' WHERE id=? AND kind='pending'",
                                    (_pending_id,)
                                )
                                _conn_r.execute(
                                    "UPDATE plots SET status='reserved' WHERE id=?",
                                    (_plot_id_r,)
                                )
                                _conn_r.commit()
                            _conn_r.close()
                        except Exception as _re:
                            st.toast(f"Reserva anotada (aviso técnico: {_re})", icon="ℹ️")
                        st.session_state[f"stripe_verified_{_ss_id}"] = True
                        # Notificaciones admin: Telegram + email
                        try:
                            from modules.marketplace.email_notify import notify_new_reservation as _notify_res
                            _notify_res(_plot_id_r, _buyer_name, _buyer_mail, _amount, "reservation")
                        except Exception:
                            pass
                        st.session_state["logged_in"]         = True
                        st.session_state["user_email"]        = _buyer_mail
                        st.session_state["role"]              = "client"
                        st.session_state["user_name"]         = _buyer_name
                        st.session_state["auto_owner_email"]  = _buyer_mail
                        st.session_state["selected_page"]     = "👤 Panel de Cliente"
                        st.session_state["_nav_radio"]        = "👤 Panel de Cliente"
                        st.session_state["payment_confirmed"] = True
                        # client_panel.main() necesita estas keys para mostrar el dashboard
                        st.session_state["client_logged_in"]  = True
                        st.session_state["client_email"]      = _buyer_mail
                        st.session_state["user_role"]         = "buyer"
                        st.toast("🎉 ¡Reserva confirmada! Bienvenido a tu panel de cliente.", icon="✅")
                        try:
                            del st.query_params["stripe_session"]
                            del st.query_params["payment"]
                        except Exception:
                            pass
                        st.query_params["page"] = "cliente"
                        st.rerun()
                else:
                    _con3 = _sq3.connect("database.db", timeout=15)
                    _con3.execute("PRAGMA journal_mode=WAL")
                    _exists3 = _con3.execute(
                        "SELECT id FROM ventas_proyectos WHERE stripe_session_id = ?", (_ss_id,)
                    ).fetchone()
                    if not _exists3:
                        _con3.execute("""
                            INSERT INTO ventas_proyectos
                            (proyecto_id, cliente_email, nombre_cliente, productos_comprados,
                             total_pagado, metodo_pago, fecha_compra, stripe_session_id)
                            VALUES (?, ?, ?, ?, ?, 'Stripe', datetime('now'), ?)
                        """, (_proj_id, _cli_mail, _cli_mail, _prods, _amount, _ss_id))
                        _con3.commit()
                    _con3.close()
                    st.session_state[f"stripe_verified_{_ss_id}"] = True
                    st.toast("🎉 Pago completado. Ya puedes descargar tus archivos.", icon="✅")
                    if _cli_mail:
                        st.session_state["logged_in"]        = True
                        st.session_state["user_email"]       = _cli_mail
                        st.session_state["role"]             = "client"
                        st.session_state["client_logged_in"] = True
                        st.session_state["client_email"]     = _cli_mail
                        st.session_state["user_role"]        = "buyer"
                        st.session_state["selected_page"]    = "👤 Panel de Cliente"
                        st.session_state["_nav_radio"]       = "👤 Panel de Cliente"
        except Exception as _se:
            st.toast(f"Error verificando pago Stripe: {_se}", icon="⚠️")
    # Limpiar params de Stripe sin perder el proyecto
    try:
        del st.query_params["stripe_session"]
        del st.query_params["payment"]
    except Exception:
        pass

# === STRIPE: pago Plan Destacado constructor ===
if st.query_params.get("sp_pago_ok") == "1" and st.query_params.get("sp_sess"):
    _sp_sess = st.query_params["sp_sess"]
    _sp_pid  = st.query_params.get("sp_pid", "")
    if not st.session_state.get(f"sp_dest_verified_{_sp_sess}"):
        try:
            from modules.stripe_utils import verify_session as _sv2
            from datetime import datetime as _dt2, timedelta as _td2, timezone as _tz2
            _sess2 = _sv2(_sp_sess)
            if _sess2.payment_status == "paid":
                _meta2 = dict(_sess2.metadata or {})
                _pid2  = _meta2.get("provider_id") or _sp_pid
                if _pid2:
                    from modules.marketplace.utils import db_conn as _dc2
                    _cn2 = _dc2()
                    _until2 = (_dt2.now(_tz2.utc) + _td2(days=30)).strftime("%Y-%m-%d")
                    _cn2.execute(
                        "UPDATE service_providers SET is_featured=1, featured_until=?, featured_plan='destacado' WHERE id=?",
                        (_until2, _pid2)
                    )
                    _cn2.commit(); _cn2.close()
                    st.session_state[f"sp_dest_verified_{_sp_sess}"] = True
                    try:
                        from modules.marketplace.email_notify import _send as _s2
                        _s2(f"⭐ <b>Plan Destacado ACTIVADO (Stripe)</b>\nConstructor ID: {_pid2}\nVálido hasta: {_until2}")
                    except Exception:
                        pass
                    st.toast("⭐ ¡Plan Destacado activado! Ya apareces primero en las comparativas.", icon="⭐")
        except Exception:
            pass
    try:
        del st.query_params["sp_pago_ok"]
        del st.query_params["sp_sess"]
        del st.query_params["sp_pid"]
    except Exception:
        pass

# === STRIPE: pago comisión obra adjudicada ===
if st.query_params.get("sp_comision_ok") == "1" and st.query_params.get("sp_sess"):
    _sc_sess  = st.query_params["sp_sess"]
    _sc_offer = st.query_params.get("offer_id", "")
    if not st.session_state.get(f"sp_com_verified_{_sc_sess}"):
        try:
            from modules.stripe_utils import verify_session as _sv3
            _sess3 = _sv3(_sc_sess)
            if _sess3.payment_status == "paid" and _sc_offer:
                from modules.marketplace.utils import db_conn as _dc3
                _cn3 = _dc3()
                _cn3.execute(
                    "UPDATE construction_offers SET comision_pagada=1, comision_stripe_session=? WHERE id=?",
                    (_sc_sess, _sc_offer)
                )
                _cn3.commit(); _cn3.close()
                st.session_state[f"sp_com_verified_{_sc_sess}"] = True
                try:
                    from modules.marketplace.email_notify import _send as _s3
                    _s3(f"💰 <b>Comisión obra pagada (Stripe)</b>\nOferta ID: {_sc_offer}\nSesión: {_sc_sess}")
                except Exception:
                    pass
                st.toast("✅ Comisión pagada. Ya puedes ver el contacto del cliente.", icon="✅")
        except Exception:
            pass
    try:
        del st.query_params["sp_comision_ok"]
        del st.query_params["sp_sess"]
        del st.query_params["offer_id"]
    except Exception:
        pass

# FIX 2026-04-05 Bug #8a: retorno pago Diseñador de Vivienda → redirige a descarga (Step 6)
# success_url en flow.py usa /?pago=ok (sin page param) → capturar aquí
if st.query_params.get("pago") == "ok" and not st.query_params.get("page"):
    _s6_sid = st.session_state.get("stripe_session_id_s6")
    if _s6_sid and not st.session_state.get(f"s6_verified_{_s6_sid}"):
        try:
            from modules.stripe_utils import verify_session as _vs6a
            _sess6a = _vs6a(_s6_sid)
            if _sess6a.payment_status == "paid":
                _meta6a = dict(_sess6a.metadata or {})
                st.session_state["pago_completado"] = True
                st.session_state["total_pagado"] = float(_meta6a.get("total_eur", 0) or 0)
                st.session_state[f"s6_verified_{_s6_sid}"] = True
                st.session_state.pop("stripe_session_id_s6", None)
                st.session_state.pop("stripe_checkout_url_s6", None)
                st.toast("🎉 Pago confirmado. Descargando tu proyecto...", icon="✅")
        except Exception:
            # Stripe no disponible en local — simular pago confirmado
            st.session_state["pago_completado"] = True
    # Redirigir al diseñador (Step 6) donde están todos los descargables
    st.session_state["selected_page"]  = "Diseñador de Vivienda"
    st.session_state["_nav_radio"]     = "Diseñador de Vivienda"
    st.session_state["ai_house_step"]  = 6
    try:
        del st.query_params["pago"]
    except Exception:
        pass
    st.rerun()

# === STRIPE: retorno pago plan prefabricadas ===
if st.query_params.get("page") == "prefabricadas" and st.query_params.get("pago") == "ok":
    _pref_plan = st.query_params.get("plan", "normal")
    _pref_comp = st.session_state.get("prefab_company")
    if _pref_comp and not st.session_state.get(f"pref_plan_ok_{_pref_comp['id']}_{_pref_plan}"):
        try:
            from datetime import datetime as _dt_pref, timedelta as _td_pref
            from modules.marketplace.utils import db_conn as _dc_pref
            _until_pref = (_dt_pref.utcnow() + _td_pref(days=30)).strftime("%Y-%m-%d")
            _cp_conn = _dc_pref()
            _cp_conn.execute(
                "UPDATE prefab_companies SET plan=?, paid_until=? WHERE id=?",
                (_pref_plan, _until_pref, _pref_comp["id"])
            )
            _cp_conn.commit(); _cp_conn.close()
            # Actualizar sesión
            st.session_state["prefab_company"] = {**_pref_comp, "plan": _pref_plan, "paid_until": _until_pref}
            st.session_state[f"pref_plan_ok_{_pref_comp['id']}_{_pref_plan}"] = True
            st.toast(f"✅ Plan {_pref_plan} activado hasta {_until_pref}", icon="✅")
        except Exception:
            pass
    st.session_state["selected_page"] = "🏠 Portal Prefabricadas"
    st.session_state["_nav_radio"] = "🏠 Portal Prefabricadas"

# === NUEVAS RUTAS V2 (BORRÓN Y CUENTA NUEVA) ===
page_from_query = False  # Variable para controlar si la página viene de query params
if "selected_prefab" in st.query_params and not page_from_query:
    try:
        from modules.marketplace import prefab_detail
        prefab_detail.show(int(st.query_params["selected_prefab"]))
    except Exception as e:
        st.error(f"Error mostrando detalle de prefabricada: {e}")
    st.stop()

if "selected_project_v2" in st.query_params and not page_from_query:
    try:
        project_id = st.query_params["selected_project_v2"]
        detalles_proyecto_v2(project_id)
    except Exception as e:
        st.error(f"Error mostrando detalles del proyecto v2: {e}")
    st.stop()  # Detener la ejecución para no mostrar el resto de la app

if "selected_plot" in st.query_params and not page_from_query:
    try:
        plot_id = st.query_params["selected_plot"]
        from modules.marketplace.plot_detail import show_plot_detail_page
        show_plot_detail_page(plot_id)
    except Exception as e:
        st.error(f"Error mostrando finca: {e}")
    st.stop()

# ── Páginas públicas MLS — sin login (mismo patrón que selected_plot) ───────
if "mls_ficha" in st.query_params and not page_from_query:
    try:
        from modules.mls.mls_publico import show_ficha_publica
        show_ficha_publica(st.query_params["mls_ficha"])
    except Exception as e:
        st.error(f"Error mostrando ficha MLS: {e}")
    st.stop()

if "mls_reservar" in st.query_params and not page_from_query:
    try:
        from modules.mls.mls_publico import show_reservar_publico
        show_reservar_publico(st.query_params["mls_reservar"])
    except Exception as e:
        st.error(f"Error en formulario de reserva MLS: {e}")
    st.stop()

if "mls_contacto" in st.query_params and not page_from_query:
    try:
        from modules.mls.mls_publico import show_contacto_publico
        show_contacto_publico(st.query_params["mls_contacto"])
    except Exception as e:
        st.error(f"Error en formulario de contacto MLS: {e}")
    st.stop()

if st.query_params.get("mls_reserva_ok") == "1" and st.query_params.get("tipo") == "cliente_directo" and not page_from_query:
    try:
        from modules.mls.mls_publico import show_retorno_reserva_cliente
        show_retorno_reserva_cliente()
    except Exception as e:
        st.error(f"Error en confirmación de reserva: {e}")
    st.stop()
# ────────────────────────────────────────────────────────────────────────────

# Intercept directo: ?page=cliente → panel de cliente sin pasar por sidebar radio
# (Mismo patrón que commit a7e1fd9 que funcionaba: intercept + st.stop())
if st.query_params.get("page") == "cliente" and st.session_state.get('selected_page') != "🏠 Propietarios":
    try:
        from modules.marketplace import client_panel
        client_panel.main()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando panel cliente: {e}")


if st.query_params.get("page") in ("Diseñador de Vivienda", "disenador"):
    try:
        if st.session_state.get("mls_origin"):
            if st.button("← Volver al portal MLS", key="diseñador_back_mls"):
                st.session_state.pop("mls_origin", None)
                st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
                try:
                    del st.query_params["page"]
                except Exception:
                    pass
                st.rerun()
        with st.container():
            ai_house_flow.main()
            st.stop()
    except Exception as e:
        st.error(f"Error mostrando diseñador de vivienda: {e}")

if st.query_params.get("page") in ("Arquitectos (Marketplace)", "arquitectos"):
    try:
        from modules.marketplace import architects as _arch_mod
        _arch_mod.main()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando portal arquitectos: {e}")


# Page configuration and navigation - SIMPLIFIED VERSION
PAGES = {
    "🏠 Inicio / Marketplace": ("modules.marketplace.marketplace", "main"),
    "🏠 Propietarios": ("modules.marketplace.owners", "main"),
    "🏢 Inmobiliarias MLS": ("modules.mls.mls_portal", "main"),
    "🔍 Detalle de Finca": ("modules.marketplace.plot_detail", "show_plot_detail_page"),
    "Intranet": ("modules.marketplace.intranet", "main"),
    "👤 Panel de Proveedor": ("modules.marketplace.service_providers", "show_service_provider_panel"),
    "📝 Registro de Proveedor de Servicios": ("modules.marketplace.service_providers", "show_service_provider_registration"),
    "Arquitectos (Marketplace)": ("modules.marketplace.marketplace_upload", "main"),
    "👤 Panel de Cliente": ("modules.marketplace.client_panel", "main"),
    "Iniciar Sesión": ("modules.marketplace.auth", "show_login"),
    "Registro de Usuario": ("modules.marketplace.auth", "show_registration"),
    "💬 Lola": ("modules.marketplace.virtual_assistant", "main"),
    "🎓 Estudiantes": ("estudiantes", "mostrar_modulo_estudiantes"),
    "🏠 Portal Prefabricadas": ("modules.prefabricadas.portal", "main"),
}
PAGES = list(PAGES.keys())

# Helper: start a simple static server for local assets (with CORS)
def _start_static_server(root_dir: Path, port: int = 8765):
    # If already started, return existing port
    if st.session_state.get("static_server_started"):
        return st.session_state.get("static_server_port")
    try:
        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                super().end_headers()
            def do_OPTIONS(self):
                self.send_response(200, "OK")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.end_headers()

        Handler = functools.partial(CORSRequestHandler, directory=str(root_dir))
        httpd = socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler)
    except Exception:
        return None
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    st.session_state["static_server_started"] = True
    st.session_state["static_server_port"] = port
    st.session_state["static_server_obj"] = httpd
    return port


def render_portal_cliente_proyecto():
    from modules.marketplace.utils import db_conn
    st.header("📂 Portal de Cliente — Proyecto Seleccionado")

    proyecto = st.session_state.get("proyecto_seleccionado")
    interes_id = st.session_state.get("interes_proyecto_id")
    interes_titulo = st.session_state.get("interes_proyecto_titulo")
    email = st.session_state.get("email", "")
    rol = st.session_state.get("role", "cliente")  # futuro: cliente / propietario / arquitecto / admin

    if not proyecto and not interes_id:
        st.warning("No hay ningún proyecto seleccionado para mostrar en el portal de cliente.")
        return

    st.markdown("### 🏡 Información del Proyecto")

    if proyecto:
        st.write(f"**Título:** {proyecto.get('title', 'N/D')}")
        st.write(f"**💰 Precio:** {proyecto.get('price', 'N/D')} €")
        st.write(f"**📐 Superficie:** {proyecto.get('m2_construidos', 'N/D')} m²")
        st.write(f"**🛏️ Habitaciones:** {proyecto.get('habitaciones', 'N/D')}")
        st.write(f"**🛁 Baños:** {proyecto.get('banos', 'N/D')}")
        st.write(f"**🏠 Plantas:** {proyecto.get('plantas', 'N/D')}")
    else:
        st.warning("No hay proyecto seleccionado.")

    st.markdown("---")

    # VISUALIZACIONES (pestañas: 3D / VR / Fotos)
    st.markdown("### 🏗️ Visualizaciones del Proyecto")

    tab_3d, tab_vr, tab_fotos = st.tabs(["🎥 3D", "🥽 VR", "🖼️ Fotos / Planos"])

    # --- Pestaña 3D ---
    with tab_3d:
        st.markdown("#### 🎥 Visor 3D del Proyecto")

        if proyecto:
            # Usamos GLB siempre que exista
            glb_path = proyecto.get("modelo_3d_glb")

            if glb_path:
                rel_path = str(glb_path).replace("\\", "/").lstrip("/")
                # Obtener STATIC_URL si está definido, si no usar fallback
                STATIC_URL = globals().get('STATIC_URL', 'http://127.0.0.1:8765/')
                model_url = f"{STATIC_URL}{rel_path}".replace(" ", "%20")

                # three_html_for was removed — use Babylon viewer from flow instead
                st.info(f"Visor 3D disponible en el Diseñador. Modelo: `{rel_path}`")
                st.markdown(f"[Abrir en Diseñador 3D →](?page=Diseñador+de+Vivienda)")
            else:
                st.info("Este proyecto no tiene modelo GLB. Próximamente convertiremos OBJ a GLB automáticamente.")
        else:
            st.warning("No hay proyecto seleccionado en el portal.")

    # --- Pestaña VR ---
    with tab_vr:
        st.markdown("#### 🥽 Visor de Realidad Virtual")

        model_glb = None
        if proyecto and proyecto.get("modelo_3d_glb"):
            model_glb = proyecto.get("modelo_3d_glb")

        if model_glb:
            rel = str(model_glb).replace("\\", "/").lstrip("/")
            glb_url = f"http://localhost:8000/{rel}".replace(" ", "%20") + "?v=123"
            viewer_url = f"http://localhost:8000/static/vr_viewer.html?model={glb_url}"

            st.markdown(
                f'<iframe src="{viewer_url}" width="100%" height="600" allow="accelerometer; gyroscope; xr-spatial-tracking; vr" frameborder="0"></iframe>',
                unsafe_allow_html=True,
            )
            st.caption("Visor VR integrado. Si no funciona, verifica permisos del navegador.")
        else:
            st.info("Este proyecto todavía no tiene modelo VR asociado. Usaremos el modelo 3D como base en futuras versiones.")

    # --- Pestaña Fotos / Planos ---
    with tab_fotos:
        st.markdown("#### 🖼️ Galería de Fotos y Planos")

        # Foto principal
        foto = proyecto.get("foto_principal")
        if foto:
            rel = foto.replace("\\", "/").lstrip("/")
            url = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel}"
            st.image(url, width=400)

        # Imagen adicional dentro de characteristics_json
        try:
            import json
            chars = json.loads(proyecto.get("characteristics_json", "{}"))
            img2 = chars.get("imagenes")
            # Evitar duplicados
            if img2 and img2 == foto:
                img2 = None
            if img2:
                rel2 = img2.replace("\\", "/").lstrip("/")
                url2 = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel2}"
                st.image(url2, width=400)
        except:
            pass

        # Galería completa
        galeria_fotos = proyecto.get('files', {}).get('fotos', [])
        if galeria_fotos:
            st.subheader("Galería Completa")
            for foto in galeria_fotos:
                if foto and isinstance(foto, str) and not foto.isdigit() and foto.strip():
                    rel = foto.replace("\\", "/").lstrip("/")
                    url = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel}"
                    st.image(url, width=300)

    st.markdown("---")
    st.markdown("### 🛒 Acciones del Cliente")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛒 COMPRAR ESTE PROYECTO (simulado)", key="btn_comprar_proyecto_portal"):
            st.success("Simulando compra. Nuestro equipo comercial se pondrá en contacto contigo.")
    with col2:
        if st.button("📞 QUIERO QUE ME LLAMEN", key="btn_llamar_proyecto_portal"):
            st.success("Hemos registrado tu interés para que te llame el equipo comercial.")

    st.caption(f"Portal vinculado al email: {email or 'No registrado'}")

    st.markdown("---")
    st.markdown("### 🔧 Módulos Profesionales (Futuro)")
    st.info("Estos módulos estarán disponibles en futuras versiones para monetización:")
    st.write("- 🎨 Decoradores (packs de interiorismo)")
    st.write("- 🏗️ Constructores (presupuestos automáticos)")
    st.write("- 🧱 Prefabricadas (catálogo integrado)")
    st.write("- 🛡️ Aseguradoras (pólizas vinculadas)")
    st.write("- 🧰 Materiales de construcción (marketplace)")
    st.write("- 🧑‍💼 Arquitectos (gestión avanzada)")
    st.write("- 🧑‍💼 Propietarios (seguimiento de obra)")



# Lógica de navegación robusta

def sync_navigation():
    """Reset quirúrgico: si URL no tiene ?page= (o es home), fijar home sin borrar sesión.
    Evita que basura de sesiones previas (como _nav_radio='👤 Panel de Cliente')
    haga que el sidebar radio sobreescriba selected_page tras un botón 'Volver'.
    """
    page_param = st.query_params.get("page", "")
    if not page_param or page_param == "home":
        _portal_pages = {
            "👤 Panel de Cliente", "🏢 Inmobiliarias MLS",
            "🏠 Propietarios", "Diseñador de Vivienda",
            "👤 Panel de Proveedor", "🏠 Portal Prefabricadas",
            "🎓 Estudiantes", "📐 Portal de Arquitectos",
        }
        if st.session_state.get("_nav_radio") in _portal_pages:
            # Resetear solo navegación — NO tocar login ni datos Stripe
            st.session_state["_nav_radio"] = "🏠 Inicio / Marketplace"
            st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
            st.session_state["_nav_programmatic"] = True

sync_navigation()


def render_nav_header(titulo: str, back_slug: str = "home"):
    """Navbar universal: botón Volver + título de página.
    Úsala al inicio de cualquier portal para evitar callejones sin salida.

    Args:
        titulo:    Título visible del portal (ej: '👤 Panel de Cliente').
        back_slug: Slug de la URL destino al pulsar Volver (por defecto 'home').
    """
    _nc1, _nc2 = st.columns([1, 6])
    with _nc1:
        if st.button("⬅️ Volver", key=f"nav_back_{titulo[:12].replace(' ', '_')}",
                     use_container_width=True):
            st.session_state["_nav_programmatic"] = True   # evitar sobreescritura del radio oculto
            st.query_params.clear()
            st.query_params["page"] = back_slug
            st.session_state.pop("current_page_sync", None)  # forzar redetección
            st.rerun()
    with _nc2:
        st.subheader(titulo)
    st.divider()


# Pre-configurar la key del radio si no existe o si su valor no está en PAGES
_nav_val = st.session_state.get("_nav_radio")
if _nav_val is None or _nav_val not in PAGES:
    _init_page = st.session_state.get('selected_page', "🏠 Inicio / Marketplace")
    st.session_state["_nav_radio"] = _init_page if _init_page in PAGES else "🏠 Inicio / Marketplace"

# El sidebar DEBE leer de session_state vía key — así el URL sync puede forzar el valor
selected_page = st.sidebar.radio(
    "Navegación",
    options=PAGES,
    key="_nav_radio",
)

# Solo sincronizar si el usuario cambió el radio manualmente
# (el sidebar está oculto — no debe sobreescribir navegación programática)
if st.session_state.get("_nav_programmatic"):
    st.session_state.pop("_nav_programmatic", None)
else:
    st.session_state['selected_page'] = selected_page

# ── Panic Button de Hard Reset (último en sidebar) ─────────────────────
st.sidebar.divider()
if st.sidebar.button("♻️ Hard Reset Sesión", key="panic_reset_session", width='stretch', type="secondary"):
    st.session_state.clear()
    st.rerun()

# Lógica de Redirección — sincroniza selected_page → ?page=slug en la URL
_PAGE_TO_SLUG = {
    "Intranet":                              "admin",
    "🏠 Propietarios":                       "propietarios",
    "Propietario (Gemelo Digital)":          "gemelo",
    "💬 Lola":                               "lola",
    "Iniciar Sesión":                        "login",
    "Registro de Usuario":                   "registro",
    "👤 Panel de Cliente":                   "cliente",
    "Diseñador de Vivienda":                 "disenador",
    "Arquitectos (Marketplace)":             "arquitectos",
    "👤 Panel de Proveedor":                 "proveedor",
    "📝 Registro de Proveedor de Servicios": "registro-pro",
    "🏢 Inmobiliarias MLS":                  "mls",
    "🎓 Estudiantes":                        "estudiantes",
    "🏠 Portal Prefabricadas":               "prefabricadas",
}
_cur_page = st.session_state.get('selected_page', '')
_keep_nav_params = {"selected_plot", "selected_project_v2", "selected_prefab"}
if _cur_page == "🏠 Inicio / Marketplace":
    if not any(p in st.query_params for p in _keep_nav_params):
        # ?page=login si está abierto el formulario de login (para que back button funcione)
        if st.session_state.get("viewing_login"):
            if st.query_params.get("page") != "login":
                st.query_params.clear()
                st.query_params["page"] = "login"
        else:
            if st.query_params.get("page") != "home":
                st.query_params.clear()
                st.query_params["page"] = "home"
elif _cur_page in _PAGE_TO_SLUG:
    _target_slug = _PAGE_TO_SLUG[_cur_page]
    if st.query_params.get("page") != _target_slug:
        st.query_params["page"] = _target_slug

# Inicializar vista_actual si no existe (no altera comportamiento por defecto)
if "vista_actual" not in st.session_state:
    st.session_state["vista_actual"] = None

# Obtener rol del usuario actual para mostrar botones condicionalmente
current_user_role = None
client_logged_in = st.session_state.get("client_logged_in", False)
client_email = st.session_state.get("client_email", "")

if client_logged_in and client_email:
    try:
        from modules.marketplace.utils import get_user_by_email
        user_data = get_user_by_email(client_email)
        if user_data:
            current_user_role = user_data.get('role')
    except:
        current_user_role = None

# REMOVED: Conditional sidebar buttons for service providers - navigation is now simplified

# ── Blindaje del router — fusible por portal ──────────────────────────────────
# StopException y RerunException son señales internas de Streamlit, NO errores.
# Se re-lanzan siempre. Solo los errores reales muestran el fallback de escape.
_ST_INTERNAL = ("StopException", "RerunException")

def _portal_error(slug: str, err: Exception) -> None:
    """Fallback visual cuando un portal explota. El resto de la app sigue OK."""
    import traceback as _tb
    st.error(f"⚠️ Error cargando esta sección — `{type(err).__name__}: {err}`")
    with st.expander("Ver detalle técnico"):
        st.code(_tb.format_exc())
    if st.button("🏠 Volver al inicio", key=f"err_back_{slug}"):
        st.query_params["page"] = "home"
        st.session_state.pop("current_page_sync", None)
        st.rerun()


# Only handle special pages here; other pages delegate to modules
if st.session_state.get('selected_page') == "🔍 Detalle de Finca":
    if 'selected_plot' in st.session_state:
        from modules.marketplace.plot_detail import show_plot_detail_page
        show_plot_detail_page(st.session_state['selected_plot'])
        st.stop()
    else:
        st.error("No se ha seleccionado ninguna finca para mostrar detalles.")
        st.session_state['selected_page'] = "🏠 Inicio / Marketplace"
        st.rerun()

if st.session_state.get('selected_page') == "🏠 Inicio / Marketplace":
    # Redirigir propietarios a su panel
    if st.session_state.get('role') == 'owner':
        st.session_state['selected_page'] = "🏠 Propietarios"
        st.rerun()
    
    STATIC_ROOT = Path(r"C:/ARCHIRAPID_PROYECT25")
    STATIC_PORT = _start_static_server(STATIC_ROOT, port=8000)
    # URL base del servidor estático (definida temprano para usar en el header de diagnóstico)
    if STATIC_PORT:
        STATIC_URL = f"http://localhost:{STATIC_PORT}/"
    else:
        STATIC_URL = "http://localhost:8000/"

    # Header
    with st.container():
        try:
            from components.header import render_header
            cols = render_header()
            access_col = cols[2]
        except Exception:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                try:
                    st.image("assets/branding/logo.png", width=140)
                except Exception:
                    st.markdown("# 🏗️ ARCHIRAPID")
            with cols[1]:
                st.markdown("### IA Avanzada + Precios en Vivo + Exportación Profesional")
            access_col = cols[2]

        with access_col:
            if st.button("🔐 Admin", key="btn_admin", help="Acceso administrador"):
                st.session_state['selected_page'] = 'Intranet'
                st.query_params["page"] = "admin"
                st.rerun()

# ========== HOME: LANDING + MARKETPLACE + PROYECTOS ==========

    # Mostrar formulario de login si viewing_login es True
    if st.session_state.get('viewing_login', False):
        # PREFAB: login propio aislado — no usar login global
        if st.session_state.get('login_role') == 'prefab':
            st.session_state['viewing_login'] = False
            st.session_state['selected_page'] = "🏠 Portal Prefabricadas"
            st.session_state['_nav_radio'] = "🏠 Portal Prefabricadas"
            st.query_params["page"] = "prefabricadas"
            st.rerun()

        try:
            st.markdown("---")
            _login_role = st.session_state.get('login_role')
            _login_role_label = _login_role.title() if _login_role else ""
            _login_header = f"🔐 Iniciar Sesión — {_login_role_label}" if _login_role_label else "🔐 Iniciar Sesión"

            _hcol1, _hcol2 = st.columns([6, 1])
            with _hcol1:
                st.header(_login_header)
            with _hcol2:
                if st.button("✕ Cerrar", key="btn_close_login"):
                    st.session_state['viewing_login'] = False
                    st.session_state['login_role'] = None
                    st.session_state['_login_show_registro'] = False
                    st.rerun()

            _show_registro = st.session_state.get('_login_show_registro', False)
            if _login_role == 'services' and not _show_registro:
                if st.button("¿Primera vez? → Registrarme como Profesional", key="btn_toggle_registro"):
                    st.session_state['viewing_login'] = False
                    st.session_state['_login_show_registro'] = False
                    st.session_state['selected_page'] = "📝 Registro de Proveedor de Servicios"
                    st.query_params["page"] = "registro-pro"
                    st.rerun()
            else:
                _toggle_label = "← Ya tengo cuenta" if _show_registro else "¿Primera vez? → Crear cuenta nueva"
                if st.button(_toggle_label, key="btn_toggle_registro"):
                    st.session_state['_login_show_registro'] = not _show_registro
                    st.rerun()

            with st.form("login_form"):
                if st.session_state.get('_login_show_registro', False):
                    st.subheader("📝 Registro de Nuevo Usuario")
                    name = st.text_input("Nombre completo *", placeholder="Tu nombre completo")
                    email = st.text_input("Email *", placeholder="tu@email.com")
                    password = st.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
                    password_confirm = st.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")

                    submitted = st.form_submit_button("🚀 Registrarme y Acceder", type="primary", width='stretch')

                    if submitted:
                        if not name or not email or not password:
                            st.error("Por favor, completa los campos obligatorios marcados con *.")
                        elif password != password_confirm:
                            st.error("Las contraseñas no coinciden.")
                        elif len(password) < 6:
                            st.error("La contraseña debe tener al menos 6 caracteres.")
                        else:
                            try:
                                import uuid as _uuid
                                from werkzeug.security import generate_password_hash
                                hashed_password = generate_password_hash(password)
                                conn = db_conn()
                                c = conn.cursor()
                                new_role = 'client'
                                if st.session_state.get('login_role') == 'owner':
                                    new_role = 'owner'
                                new_id = str(_uuid.uuid4())
                                c.execute("""
                                    INSERT INTO users (id, email, full_name, role, is_professional, password_hash, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (new_id, email, name, new_role, 0, hashed_password))
                                conn.commit()
                                conn.close()
                                st.success("🎉 ¡Registro completado exitosamente!")
                                st.session_state.update({
                                    'user_id': new_id, 'user_email': email, 'role': new_role, 'user_name': name,
                                    'logged_in': True, 'viewing_login': False,
                                    'show_role_selector': False, '_login_show_registro': False,
                                })
                                _role_slug = {'client': 'cliente', 'owner': 'propietarios',
                                              'architect': 'arquitectos', 'services': 'proveedor',
                                              'admin': 'admin'}.get(new_role, 'home')
                                _role_page = _SLUG_TO_PAGE_MASTER.get(_role_slug, "🏠 Inicio / Marketplace")
                                st.session_state['selected_page'] = _role_page
                                st.query_params["page"] = _role_slug
                                st.rerun()
                            except Exception as _re:
                                if type(_re).__name__ in _ST_INTERNAL: raise
                                st.error(f"Error en el registro: {_re}")
                else:
                    email = st.text_input("📧 Email", key="login_email")
                    password = st.text_input("🔒 Contraseña", type="password", key="login_password")
                    submitted = st.form_submit_button("🚀 Entrar", type="primary", width='stretch')

                    if submitted:
                        if not email or not password:
                            st.error("Por favor, completa todos los campos.")
                        else:
                            from modules.marketplace.auth import authenticate_user
                            user_data = authenticate_user(email, password)
                            _expected_role = st.session_state.get('login_role')
                            _role_ok = (user_data and (_expected_role is None or user_data.get('role') == _expected_role))
                            if _role_ok:
                                st.session_state.update({
                                    'user_id': user_data['id'], 'user_email': user_data['email'],
                                    'role': user_data['role'],
                                    'user_name': user_data.get('full_name') or user_data.get('name') or user_data.get('email', 'Usuario'),
                                    'logged_in': True, 'viewing_login': False,
                                    'show_role_selector': False,
                                })
                                st.session_state.pop('login_role', None)
                                st.session_state.pop('_login_show_registro', None)
                                _role_slug = {'client': 'cliente', 'owner': 'propietarios',
                                              'architect': 'arquitectos', 'services': 'proveedor',
                                              'admin': 'admin'}.get(user_data['role'], 'home')
                                _role_page = _SLUG_TO_PAGE_MASTER.get(_role_slug, "🏠 Inicio / Marketplace")
                                st.session_state['selected_page'] = _role_page
                                st.query_params["page"] = _role_slug
                                st.rerun()
                            else:
                                st.error("Credenciales incorrectas.")

        except Exception as _login_err:
            if type(_login_err).__name__ in _ST_INTERNAL: raise
            st.error("⚠️ Error en el formulario de acceso.")
            if st.button("🔄 Reintentar", key="login_err_retry"):
                st.session_state['viewing_login'] = False
                st.rerun()

        st.stop()  # Detener el resto de la Home

    if st.session_state.get('show_role_selector', False):
        # Eliminado — el selector de rol ya no existe como página separada
        st.session_state['show_role_selector'] = False
        st.rerun()

    else:
        # ── MURO DE INVITACIÓN ──────────────────────────────────────────────────
        try:
            import sqlite3 as _sq3
            _wconn = _sq3.connect("database.db")
            _wc = _wconn.cursor()
            _wc.execute("SELECT COUNT(*) FROM waitlist")
            _taken = _wc.fetchone()[0]
            _wconn.close()
        except Exception:
            _taken = 0
        _MAX = 50
        _left = max(_MAX - _taken, 0)
        _pct = min(int(_taken / _MAX * 100), 100)

        # ── HERO COMPACTO: banner 75% + waitlist 25% ────────────────────────
        _hbanner, _hwaitlist = st.columns([3, 1], gap="small")

        with _hbanner:
            st.markdown(f"""
<div style="background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:12px;
            padding:12px 20px;border:1px solid rgba(245,158,11,0.3);
            display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;height:100%;">
  <!-- Sección izquierda: Beta Privada -->
  <div style="flex:1;min-width:220px;">
    <span style="font-size:10px;font-weight:700;color:#F59E0B;letter-spacing:2px;
                 text-transform:uppercase;">Beta Privada · Acceso Anticipado</span>
    <div style="font-size:1em;font-weight:800;color:#F8FAFC;line-height:1.2;">
      Acceso gratuito para los primeros {_MAX} usuarios
      <span style="font-size:0.75em;font-weight:400;color:#94A3B8;margin-left:10px;">
        ⚖️ Información orientativa basada en datos catastrales públicos. No sustituye el asesoramiento técnico, jurídico o urbanístico de un profesional colegiado.
      </span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:6px;">
      <div style="background:rgba(255,255,255,0.06);border-radius:8px;padding:6px 12px;white-space:nowrap;">
        <span style="color:#F59E0B;font-weight:700;">{_taken}</span>
        <span style="color:#94A3B8;font-size:0.85em;"> / {_MAX}</span>
        &nbsp;
        <span style="color:#10B981;font-weight:600;font-size:0.85em;">{_left} disponibles</span>
      </div>
      <div style="background:rgba(255,255,255,0.08);border-radius:6px;height:8px;width:80px;overflow:hidden;">
        <div style="background:linear-gradient(90deg,#F59E0B,#EF4444);
                    width:{_pct}%;height:100%;border-radius:6px;"></div>
      </div>
    </div>
  </div>
  <!-- Separador vertical -->
  <div style="width:1px;background:rgba(245,158,11,0.25);align-self:stretch;margin:0 8px;"></div>
  <!-- Sección derecha: MLS Inmobiliarias -->
  <div style="flex:0 0 auto;max-width:220px;">
    <span style="font-size:10px;font-weight:700;color:#F5A623;letter-spacing:2px;
                 text-transform:uppercase;">🏢 ¿Eres Inmobiliaria?</span>
    <div style="font-size:0.88em;font-weight:700;color:#F8FAFC;line-height:1.3;margin-top:2px;">
      Bolsa MLS colaborativa
    </div>
    <div style="font-size:0.78em;color:#94A3B8;margin-top:2px;">
      Comparte fincas, multiplica ventas.<br>
      Sin captación. Split automático.
    </div>
    <a href="/?seccion=mls"
       style="display:inline-block;margin-top:6px;padding:4px 12px;
              background:linear-gradient(90deg,#F5A623,#ef4444);color:white;
              border-radius:6px;font-size:0.78em;font-weight:700;text-decoration:none;">
      🎁 30 días Free Trial →
    </a>
  </div>
  <!-- Separador vertical -->
  <div style="width:1px;background:rgba(16,185,129,0.3);align-self:stretch;margin:0 8px;"></div>
  <!-- Sección: Estudiantes -->
  <div style="flex:0 0 auto;max-width:200px;">
    <span style="font-size:10px;font-weight:700;color:#10B981;letter-spacing:2px;
                 text-transform:uppercase;">🎓 ¿Eres Estudiante?</span>
    <div style="font-size:0.88em;font-weight:700;color:#F8FAFC;line-height:1.3;margin-top:2px;">
      Presenta tu TFG con IA
    </div>
    <div style="font-size:0.78em;color:#94A3B8;margin-top:2px;">
      Planos reales y presupuesto.<br>
      Acceso gratuito para arquitectura.
    </div>
    <a href="/?page=estudiantes"
       style="display:inline-block;margin-top:6px;padding:4px 12px;
              background:linear-gradient(90deg,#10B981,#3B82F6);color:white;
              border-radius:6px;font-size:0.78em;font-weight:700;text-decoration:none;">
      🎓 Acceso gratuito →
    </a>
  </div>
</div>""", unsafe_allow_html=True)

        _wl_key = "waitlist_submitted"
        with _hwaitlist:
            if not st.session_state.get(_wl_key):
                with st.expander("✋ Solicitar plaza gratuita", expanded=False):
                    with st.form("waitlist_form", clear_on_submit=True):
                        _wname  = st.text_input("Nombre", placeholder="Tu nombre")
                        _wemail = st.text_input("Email",  placeholder="tu@email.com")
                        _wprofile = st.selectbox("Soy...",
                            ["Comprador / Particular", "Propietario de terreno",
                             "Arquitecto / Profesional", "Inversor / Empresa"])
                        _wmsg = st.text_input("¿Qué buscas?", placeholder="Construir, invertir...")
                        _wsub = st.form_submit_button(
                            "Solicitar plaza" if _left > 0 else "Lista de espera",
                            type="primary", width='stretch')
                        if _wsub:
                            if not _wname or not _wemail or "@" not in _wemail:
                                st.error("Nombre y email requeridos.")
                            else:
                                try:
                                    import sqlite3 as _sq3b
                                    _wconn2 = _sq3b.connect("database.db")
                                    _wconn2.cursor().execute(
                                        "INSERT INTO waitlist (name, email, profile) VALUES (?,?,?)",
                                        (_wname.strip(), _wemail.strip().lower(), _wprofile))
                                    _wconn2.commit(); _wconn2.close()
                                    st.session_state[_wl_key] = True
                                    st.session_state["waitlist_name"] = _wname.strip()
                                    try:
                                        from modules.marketplace.email_notify import notify_waitlist
                                        notify_waitlist(_wname.strip(), _wemail.strip().lower(), _wprofile)
                                    except Exception:
                                        pass
                                    st.rerun()
                                except Exception as _we:
                                    if "UNIQUE" in str(_we):
                                        st.info("Ya estás en la lista.")
                                    else:
                                        st.error(f"Error: {_we}")
            else:
                _wname_saved = st.session_state.get("waitlist_name", "")
                st.success(f"✅ Plaza reservada{', ' + _wname_saved if _wname_saved else ''}.")

            # ── Acceso directo al portal MLS — 30 días free trial ────────────
            st.link_button("🎁 30 días Free Trial — Acceder al portal MLS →", "/?seccion=mls", width='stretch', type="primary")

        # ── NAVEGACIÓN PROFESIONAL CON ESPACIADO CORREGIDO ─────────────────────────
        st.markdown("""
<style>
    .access-grid {
        display: flex; gap: 10px; justify-content: space-between;
        margin-bottom: 15px;
        margin-top: 10px;
    }
    .access-card {
        flex: 1; background: white; padding: 12px; border-radius: 10px;
        border: 1px solid #e5e7eb; border-top: 4px solid #ccc; text-align: center;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    }
    .access-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); }
    .card-label { font-weight: 700; color: #111827; font-size: 0.85rem; margin-bottom: 8px; display: block; }

    .terreno { border-top-color: #10b981; } .comprador { border-top-color: #3b82f6; }
    .estudiante { border-top-color: #8b5cf6; } .arquitecto { border-top-color: #f59e0b; }
    .constructor { border-top-color: #d97706; } .prefab { border-top-color: #06b6d4; }
    .mls { border-top-color: #f43f5e; }

    div[data-testid="stButton"] > button {
        width: 100% !important; height: 30px !important; padding: 0 !important;
        font-size: 0.75rem !important; font-weight: 600 !important; border-radius: 6px !important;
        border: 1px solid #d1d5db !important;
    }

    hr { margin-top: 1.5rem !important; margin-bottom: 1.5rem !important; opacity: 0.2; }
</style>
""", unsafe_allow_html=True)

        cols = st.columns(7, gap="small")

        # --- CONFIGURACIÓN DE ROLES (Doble Identidad: Visual vs Técnico) ---
        roles = [
            ("📍 Terreno", "terreno", "🏠 Propietarios", "propietarios"),
            ("🏠 Comprador", "comprador", "👤 Panel de Cliente", "cliente"),
            ("🎓 Estudiante", "estudiante", "🎓 Estudiantes", "estudiantes"),
            ("📐 Arquitecto", "arquitecto", "Arquitectos (Marketplace)", "arquitectos"),
            ("🏗️ Profesionales", "constructor", "👤 Panel de Proveedor", "proveedor"),
            ("🏠 Prefab", "prefab", "🏠 Portal Prefabricadas", "prefabricadas"),
            ("🏢 Inmo/MLS", "mls", "🏢 Inmobiliarias MLS", "mls")
        ]

        for i, (label, style_class, page_name, page_slug) in enumerate(roles):
            with cols[i]:
                st.markdown(f'<div class="access-card {style_class}"><span class="card-label">{label}</span>', unsafe_allow_html=True)
                if st.button("Acceder", key=f"btn_nav_{page_slug}", use_container_width=True):
                    # ── Mapeo de role_slug → login_role (para BD) ──
                    _role_map = {
                        'propietarios': 'owner',
                        'cliente': 'client',
                        'estudiantes': 'student',
                        'arquitectos': 'architect',
                        'proveedor': 'services',
                        'prefabricadas': 'prefab',
                        'mls': 'inmo'
                    }
                    st.session_state['login_role'] = _role_map.get(page_slug, page_slug)
                    st.session_state['viewing_login'] = True
                    st.session_state['_login_show_registro'] = False  # Mostrar login por defecto
                    st.rerun()  # ← CRÍTICO: sin esto, tarda 1 ciclo extra (doble-clic lag)
                st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # PASO 1: Renderizar MARKETPLACE (mapa, fincas y proyectos)
        try:
            from modules.marketplace import marketplace
            marketplace.main()
        except Exception as e:
            if type(e).__name__ in _ST_INTERNAL: raise
            import traceback
            st.error(f"Error cargando marketplace: {e}")
            st.code(traceback.format_exc())


        # PASO 3: Renderizar PROYECTOS ARQUITECTÓNICOS
        st.divider()
        st.markdown("#### 🏗️ Proyectos Arquitectónicos Disponibles")

        try:
            from src import db
            from modules.marketplace.marketplace import get_project_display_image
            projects = db.get_featured_projects(limit=10)

            if projects:
                import base64, io
                N = 5
                cols = st.columns(N)
                for idx, p in enumerate(projects[:N*2]):
                    with cols[idx % N]:
                        # Imagen con altura fija via HTML para uniformidad
                        thumbnail = get_project_display_image(p['id'], image_type='main')
                        try:
                            if isinstance(thumbnail, bytes):
                                b64 = base64.b64encode(thumbnail).decode()
                            else:
                                buf = io.BytesIO()
                                thumbnail.save(buf, format='JPEG')
                                b64 = base64.b64encode(buf.getvalue()).decode()
                            st.markdown(
                                f'<img src="data:image/jpeg;base64,{b64}" '
                                f'style="width:100%;height:160px;object-fit:cover;'
                                f'border-radius:10px;display:block;">',
                                unsafe_allow_html=True
                            )
                        except Exception:
                            st.image(thumbnail, width='stretch')
                        title = p.get('title', 'Proyecto')
                        st.markdown(f"**{title[:28]}{'…' if len(title)>28 else ''}**")
                        st.caption(f"💰 €{p.get('price',0):,.0f}  ·  📐 {p.get('area_m2',0)} m²")
                        if st.button("Ver Detalles →", key=f"proj_home_{p['id']}", width='stretch'):
                            st.query_params["selected_project_v2"] = p['id']
                            st.rerun()
            else:
                st.info("No hay proyectos arquitectónicos disponibles aún.")
        except Exception as e:
            if type(e).__name__ in _ST_INTERNAL: raise
            st.error(f"Error cargando proyectos: {e}")

    # Sección casas prefabricadas
    st.markdown("---")
    st.markdown("#### 🏠 Adquiere tu Finca y Ponle una Casa Prefabricada")
    st.caption("Modelos entregables desde 45 m² · Madera · Acero modular · Hormigón prefab · Mixto")
    try:
        from src import db as _db
        _conn = _db.get_conn()
        _cur = _conn.cursor()
        _cur.execute("SELECT id, name, m2, rooms, bathrooms, floors, material, price, image_path, image_paths, price_label FROM prefab_catalog WHERE active=1 ORDER BY m2 LIMIT 10")
        prefabs = _cur.fetchall()
        _conn.close()
        if prefabs:
            import base64 as _b64, json as _pfjson
            _N = 5
            _cols = st.columns(_N)
            for _idx, _pf in enumerate(prefabs[:_N * 2]):
                _pf_id, _nm, _m2, _rms, _bths, _fls, _mat, _prc, _img, _imgs_j, _plbl = _pf
                # Primera foto válida
                _thumb = None
                try:
                    for _ip in (_pfjson.loads(_imgs_j) if _imgs_j else []):
                        if _ip:
                            _ip = _ip.replace("\\", "/")
                            if os.path.exists(_ip):
                                _thumb = _ip; break
                    if not _thumb and _img:
                        _img = _img.replace("\\", "/")
                        if os.path.exists(_img):
                            _thumb = _img
                except Exception:
                    pass
                # Precio
                _pdsp = (_plbl.strip() if _plbl and _plbl.strip() else
                         (f"€{float(_prc):,.0f}" if _prc and float(_prc) > 0 else "PRECIO A CONSULTAR"))
                with _cols[_idx % _N]:
                    if _thumb:
                        try:
                            with open(_thumb, "rb") as _tf:
                                _tb64 = _b64.b64encode(_tf.read()).decode()
                            _ext = _thumb.rsplit(".", 1)[-1].lower()
                            _mime = "image/png" if _ext == "png" else "image/jpeg"
                            st.markdown(f'<img src="data:{_mime};base64,{_tb64}" style="width:100%;height:140px;object-fit:cover;border-radius:10px;display:block;margin-bottom:6px;">', unsafe_allow_html=True)
                        except Exception:
                            st.markdown('<div style="height:140px;background:#F0F9FF;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2.5em;margin-bottom:6px;">🏠</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="height:140px;background:#F0F9FF;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2.5em;margin-bottom:6px;">🏠</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-weight:700;font-size:0.85em;color:#0D1B2A;">{_nm}</div><div style="font-size:0.76em;color:#64748B;">{_m2} m² · {_rms}hab · {_mat}</div><div style="font-weight:700;color:#2563EB;font-size:0.88em;margin-top:4px;">{_pdsp}</div>', unsafe_allow_html=True)
                    if st.button("Ver modelo →", key=f"prefab_home_{_pf_id}", width='stretch'):
                        st.query_params["selected_prefab"] = str(_pf_id)
                        st.rerun()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        st.info("Catálogo de prefabricadas próximamente disponible.")

    # Footer
    st.markdown("""
    <div style="margin-top:40px;padding:20px 24px 16px;background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:12px;font-family:'Segoe UI',sans-serif;">
        <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;padding:12px 16px;margin-bottom:16px;">
            <span style="color:#FCD34D;font-size:0.84em;">💼 <strong>Investors & Partners — Join the PropTech revolution in Spain.</strong>
            ARCHIRAPID is a <strong>PropTech · Real Estate Marketplace · SaaS</strong> platform built on AI:
            we connect landowners, architects and buyers in a single end-to-end ecosystem —
            from raw land discovery to architectural project delivery.
            Scalable, data-driven and ready to grow. <strong>Let's talk.</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:14px;">
            <div>
                <span style="color:#F8FAFC;font-size:0.8em;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">🏗️ ARCHIRAPID</span><br>
                <span style="color:#64748B;font-size:0.78em;">PropTech · Real Estate Marketplace · SaaS · AI · Madrid, Spain</span>
            </div>
            <div style="text-align:right;">
                <span style="color:#94A3B8;font-size:0.78em;">
                    📍 Avda. de Europa 15, 28224 Pozuelo de Alarcón (Madrid)<br>
                    ✉️ <a href="mailto:hola@archirapid.com" style="color:#94A3B8;text-decoration:none;">hola@archirapid.com</a>
                    &nbsp;·&nbsp; 📞 <a href="tel:+35623172704" style="color:#94A3B8;text-decoration:none;">+356 23 17 27 04</a>
                </span>
            </div>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:10px;margin-bottom:8px;">
            <span style="color:#64748B;font-size:0.72em;">⚖️ <em>ArchiRapid proporciona información orientativa basada en datos catastrales públicos. Esta información no sustituye el asesoramiento técnico, jurídico o urbanístico de un profesional colegiado.</em></span>
        </div>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;">
            <span style="color:#475569;font-size:0.74em;">© 2026 ARCHIRAPID — All rights reserved. Proyecto ARCHIRAPID S.L. (en constitución)</span>
            <span style="color:#475569;font-size:0.74em;">Built with AI · Madrid, Spain 🇪🇸</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.stop()  # Detener ejecución para Home

elif st.session_state.get('selected_page') == "🏠 Propietarios":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        render_nav_header("📍 Portal de Propietarios")
        with st.container():
            from modules.marketplace import owners
            owners.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("propietarios", _e)

elif st.session_state.get('selected_page') == "Propietario (Gemelo Digital)":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import gemelo_digital
            gemelo_digital.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("gemelo", _e)

elif st.session_state.get('selected_page') == "Diseñador de Vivienda":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import disenador_vivienda
            disenador_vivienda.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("disenador", _e)

# "Inmobiliaria (Mapa)" route removed — Home now uses `marketplace.main()` directly.

elif st.session_state.get('selected_page') == "Arquitectos (Marketplace)":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        render_nav_header("📐 Portal de Arquitectos")
        with st.container():
            from modules.marketplace import architects
            architects.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("arquitectos", _e)

elif st.session_state.get('selected_page') == "Intranet":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import intranet
            intranet.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("intranet", _e)

elif st.session_state.get('selected_page') == "👤 Panel de Cliente":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        render_nav_header("👤 Panel de Cliente")
        if st.session_state.get('role') == 'owner':
            from modules.marketplace import owners
            owners.main()
            st.stop()
        route_main_panel()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("cliente", _e)

elif st.session_state.get('selected_page') == "👤 Panel de Proveedor":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        render_nav_header("🏗️ Portal de Profesionales")
        with st.container():
            from modules.marketplace import service_providers
            service_providers.show_service_provider_panel()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("proveedor", _e)

elif st.session_state.get('selected_page') == "📝 Registro de Proveedor de Servicios":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import service_providers
            service_providers.show_service_provider_registration()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("registro_pro", _e)

elif st.session_state.get('selected_page') == "Iniciar Sesión":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import auth
            auth.show_login()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("login", _e)
    st.stop()

elif st.session_state.get('selected_page') == "Registro de Usuario":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import auth
            auth.show_registration()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("registro", _e)
    st.stop()

elif st.session_state.get('selected_page') == "💬 Lola":
    try:
        st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
        with st.container():
            from modules.marketplace import virtual_assistant
            virtual_assistant.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("lola", _e)
    st.stop()

elif st.session_state.get('selected_page') == "🏢 Inmobiliarias MLS":
    try:
        st.components.v1.html(
            "<script>window.parent.document"
            ".querySelector('section.main')"
            ".scrollTo(0,0);</script>",
            height=0
        )
        render_nav_header("🏢 Portal Inmobiliarias MLS")
        with st.container():
            from modules.mls import mls_portal
            mls_portal.main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls", _e)

elif st.session_state.get('selected_page') == "_mls_ficha_publica":
    try:
        st.components.v1.html(
            "<script>window.parent.document"
            ".querySelector('section.main')"
            ".scrollTo(0,0);</script>",
            height=0,
        )
        with st.container():
            from modules.mls.mls_publico import show_ficha_publica
            show_ficha_publica(st.session_state.get("mls_ficha_id", ""))
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_ficha", _e)

elif st.session_state.get('selected_page') == "_mls_reservar_publica":
    try:
        st.components.v1.html(
            "<script>window.parent.document"
            ".querySelector('section.main')"
            ".scrollTo(0,0);</script>",
            height=0,
        )
        with st.container():
            from modules.mls.mls_publico import show_reservar_publico
            show_reservar_publico(st.session_state.get("mls_reservar_id", ""))
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_reservar", _e)

elif st.session_state.get('selected_page') == "_mls_contacto_publica":
    try:
        st.components.v1.html(
            "<script>window.parent.document"
            ".querySelector('section.main')"
            ".scrollTo(0,0);</script>",
            height=0,
        )
        with st.container():
            from modules.mls.mls_publico import show_contacto_publico
            show_contacto_publico(st.session_state.get("mls_contacto_id", ""))
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_contacto", _e)

elif st.session_state.get('selected_page') == "_mls_retorno_cliente":
    try:
        st.components.v1.html(
            "<script>window.parent.document"
            ".querySelector('section.main')"
            ".scrollTo(0,0);</script>",
            height=0,
        )
        with st.container():
            from modules.mls.mls_publico import show_retorno_reserva_cliente
            show_retorno_reserva_cliente()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_retorno", _e)

elif st.session_state.get('selected_page') == "_mls_forgot_password":
    try:
        with st.container():
            from modules.mls.mls_portal import show_mls_forgot_password
            show_mls_forgot_password()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_forgot", _e)

elif st.session_state.get('selected_page') == "_mls_reset_password":
    try:
        with st.container():
            from modules.mls.mls_portal import show_mls_reset_password
            show_mls_reset_password(st.session_state.get("mls_reset_token", ""))
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("mls_reset", _e)

elif st.session_state.get('selected_page') == "🎓 Estudiantes":
    try:
        st.components.v1.html(
            "<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>",
            height=0,
        )
        render_nav_header("🎓 Portal de Estudiantes")
        with st.container():
            from estudiantes import mostrar_modulo_estudiantes
            mostrar_modulo_estudiantes()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("estudiantes", _e)

elif st.session_state.get('selected_page') == "🏠 Portal Prefabricadas":
    try:
        st.components.v1.html(
            "<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>",
            height=0,
        )
        render_nav_header("🏠 Portal Prefabricadas")
        with st.container():
            from modules.prefabricadas.portal import main
            main()
    except Exception as _e:
        if type(_e).__name__ in _ST_INTERNAL: raise
        _portal_error("prefabricadas", _e)
