from dotenv import load_dotenv
load_dotenv()

import sqlite3
import pandas as pd
import os
import threading
import http.server
import socketserver
import functools
import time
from pathlib import Path
from src import db as _db
from modules.marketplace.utils import init_db, db_conn
from modules.marketplace.marketplace import get_project_display_image

# Inicializar base de datos
init_db()

# Configurar página con layout amplio
import streamlit as st
st.set_page_config(layout='wide')

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
    """Panel de cliente - VERSIÓN V2 (copia exacta del contenido original)"""
    # modules/marketplace/client_panel.py
    from modules.marketplace.utils import db_conn
    import json
    import os
    from modules.marketplace.compatibilidad import get_proyectos_compatibles

    # Iniciar servidor estático para VR y archivos
    from pathlib import Path
    STATIC_ROOT = Path(r"C:/ARCHIRAPID_PROYECT25")
    STATIC_PORT = _start_static_server(STATIC_ROOT, port=8000)
    if STATIC_PORT:
        STATIC_URL = f"http://localhost:{STATIC_PORT}/"
    else:
        STATIC_URL = "http://localhost:8000/"

    st.title("👤 Panel de Cliente - ARCHIRAPID V2")

    # PRIMERO: Verificar si ya está logueado con credenciales (sistema de passwords)
    if st.session_state.get('logged_in') and st.session_state.get('role') == 'client':
        user_email = st.session_state.get('user_email')
        user_name = st.session_state.get('user_name', 'Cliente')

        # Mostrar directamente el panel profesional
        show_client_dashboard(user_email, user_name)
        return

    # BYPASS PARA PAGO CONFIRMADO - Acceso inmediato sin consultas DB
    if st.session_state.get('payment_confirmed'):
        user_email = st.session_state.get('user_email')
        user_name = st.session_state.get('user_name', 'Cliente')

        # Limpiar el flag para evitar loops
        del st.session_state['payment_confirmed']

        # Mostrar directamente el panel profesional
        show_client_dashboard(user_email, user_name)
        return

    # SEGUNDO: Auto-login si viene de query params con owner_email (sistema legacy)
    # SOLO SI NO TIENE CREDENCIALES VÁLIDAS
    if not (st.session_state.get('logged_in') and st.session_state.get('role') == 'client'):
        if "auto_owner_email" in st.session_state and not st.session_state.get("client_logged_in", False):
            auto_email = st.session_state["auto_owner_email"]
            # Verificar si el email tiene transacciones O es propietario con fincas
            conn = db_conn()
            cursor = conn.cursor()

            # Buscar transacciones (compras/reservas)
            cursor.execute("SELECT * FROM reservations WHERE buyer_email=?", (auto_email,))
            transactions = cursor.fetchall()

            # Si no tiene transacciones, buscar si es propietario con fincas publicadas
            if not transactions:
                cursor.execute("SELECT * FROM plots WHERE owner_email=?", (auto_email,))
                owner_plots = cursor.fetchall()
            else:
                owner_plots = []

            conn.close()

            # Auto-login si tiene transacciones O fincas como propietario
            if transactions or owner_plots:
                st.session_state["client_logged_in"] = True
                st.session_state["client_email"] = auto_email
                st.session_state["user_role"] = "buyer" if transactions else "owner"
                st.session_state["has_transactions"] = len(transactions) > 0
                st.session_state["has_properties"] = len(owner_plots) > 0

                role_text = "comprador" if transactions else "propietario"
                st.info(f"🔄 Auto-acceso concedido como {role_text} para {auto_email}")

                # Limpiar el estado de auto-login
                del st.session_state["auto_owner_email"]

    # Verificar si viene de vista previa de proyecto
    selected_project = st.query_params.get("selected_project_v2")
    if selected_project and not st.session_state.get("client_logged_in", False):
        st.info("🔍 Proyecto seleccionado detectado. Por favor inicia sesión para continuar.")

    # Login simple por email
    # SOLO SI NO TIENE CREDENCIALES VÁLIDAS
    if not (st.session_state.get('logged_in') and st.session_state.get('role') == 'client'):
        if "client_logged_in" not in st.session_state:
            st.session_state["client_logged_in"] = False

        if not st.session_state["client_logged_in"]:
            st.subheader("🔐 Acceso al Panel de Cliente V2")
            st.info("Introduce el email que usaste al realizar tu compra/reserva")

            email = st.text_input("Email de cliente", placeholder="tu@email.com")

            if st.button("Acceder", type="primary"):
                if email:
                    # Verificar si el email tiene transacciones, propiedades O está registrado como cliente
                    conn = db_conn()
                    cursor = conn.cursor()

                    # Buscar transacciones (compras/reservas)
                    cursor.execute("SELECT * FROM reservations WHERE buyer_email=?", (email,))
                    transactions = cursor.fetchall()

                    # Si no tiene transacciones, buscar si es propietario con fincas publicadas
                    if not transactions:
                        cursor.execute("SELECT * FROM plots WHERE owner_email=?", (email,))
                        owner_plots = cursor.fetchall()
                    else:
                        owner_plots = []

                    # Si no tiene transacciones ni propiedades, verificar si está registrado como cliente
                    is_registered_client = False
                    if not transactions and not owner_plots:
                        cursor.execute("SELECT id, name FROM clients WHERE email = ?", (email,))
                        client_record = cursor.fetchone()
                        is_registered_client = client_record is not None

                    conn.close()

                    # Permitir acceso si tiene transacciones, fincas como propietario O está registrado como cliente
                    if transactions or owner_plots or is_registered_client:
                        st.session_state["client_logged_in"] = True
                        st.session_state["client_email"] = email

                        # Determinar el rol basado en la prioridad: transacciones > propiedades > cliente registrado
                        if transactions:
                            user_role = "buyer"
                            role_text = "comprador"
                        elif owner_plots:
                            user_role = "owner"
                            role_text = "propietario"
                        else:
                            # Cliente registrado sin transacciones ni propiedades
                            user_role = "buyer"  # Por defecto buyer para poder comprar proyectos
                            role_text = "cliente registrado"

                        st.session_state["user_role"] = user_role
                        st.session_state["has_transactions"] = len(transactions) > 0
                        st.session_state["has_properties"] = len(owner_plots) > 0

                        st.success(f"✅ Acceso concedido como {role_text} para {email}")
                        st.rerun()
                    else:
                        st.error("No se encontraron transacciones, propiedades ni registro para este email")
                else:
                    st.error("Por favor introduce tu email")

            st.markdown("---")
            st.info("💡 **Nota:** Si acabas de realizar una compra, usa el email que proporcionaste en el formulario de datos personales.")
            st.info("Por favor inicia sesión para acceder al panel.")
            # st.stop()  # Comentado para permitir que la página se cargue

    if st.session_state["client_logged_in"]:
        # Panel de cliente logueado
        client_email = st.session_state.get("client_email")
        user_role = st.session_state.get("user_role", "buyer")
        has_transactions = st.session_state.get("has_transactions", False)
        has_properties = st.session_state.get("has_properties", False)

        # Botón de cerrar sesión en sidebar
        with st.sidebar:
            if st.button("🚪 Cerrar Sesión", key="logout_button_v2"):
                st.session_state["client_logged_in"] = False
                for key in ["client_email", "user_role", "has_transactions", "has_properties", "selected_project_for_panel"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        # Mostrar rol del usuario
        role_emoji = "🛒" if user_role == "buyer" else "🏠"
        role_text = "Comprador" if user_role == "buyer" else "Propietario"
        # st.success(f"{role_emoji} **Bienvenido/a {role_text}** - {client_email}")

        # 🔍 MODO 3: Usuario interesado en un proyecto (sin transacciones)
        selected_project_for_panel = st.session_state.get("selected_project_for_panel")
        if user_role == "buyer" and not has_transactions and selected_project_for_panel:
            show_selected_project_panel_v2(client_email, selected_project_for_panel)
            return

        # Contenido diferente según el rol
        if user_role == "buyer":
            show_buyer_panel_v2(client_email)
        elif user_role == "owner":
            show_owner_panel_v2(client_email)
        else:
            st.error("Error: No se pudo determinar el tipo de panel apropiado")
            st.stop()


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
        st.write("**Precio descarga proyecto completo:**")
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
            if st.button("📄 Descargar Memoria PDF", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col2:
            if st.button("🖥️ Descargar Planos CAD", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col3:
            if st.button("🏗️ Descargar Modelo 3D", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")

    else:
        st.info("💳 Selecciona el producto que deseas adquirir:")

        col_pdf, col_cad = st.columns(2)

        with col_pdf:
            if st.button(f"📄 Comprar Memoria PDF - €{project_data['price_memoria']}", use_container_width=True, type="primary"):
                # Simular compra directa de PDF
                with st.spinner("Procesando compra de PDF..."):
                    import time
                    time.sleep(1)
                st.success("🎉 **PDF comprado con éxito!**")
                st.info("📧 Recibirás el enlace de descarga por email")

        with col_cad:
            if st.button(f"🖥️ Comprar Planos CAD - €{project_data['price_cad']}", use_container_width=True, type="primary"):
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
                        if st.button(f"🚀 Diseñar en {finca_title}", key=f"design_v2_{finca_id}", use_container_width=True):
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
        if st.button("📋 Ver Más Proyectos", use_container_width=True):
            st.query_params.clear()
            st.query_params["page"] = "🏠 HOME"
            st.rerun()

    with col2:
        if st.button("🛒 Mi Historial de Compras", use_container_width=True):
            # Limpiar proyecto seleccionado para mostrar panel normal
            if "selected_project_v2" in st.query_params:
                del st.query_params["selected_project_v2"]
            st.rerun()

    with col3:
        if st.button("📧 Contactar Arquitecto", use_container_width=True):
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
                    st.query_params["page"] = "🏠 Inicio / Marketplace"
                    st.rerun()

                except Exception as e:
                    st.error(f"Error en el registro: {e}")

    st.markdown("---")
    st.info("💡 **¿Ya tienes cuenta?** Si has realizado compras anteriores, accede directamente desde el panel de cliente.")


# === FUNCIONES AUXILIARES V2 ===

def show_buyer_panel_v2(client_email):
    """Panel principal para compradores - V2"""
    st.header("🛒 Panel de Comprador V2")

    # Tabs para diferentes secciones
    tab1, tab2, tab3 = st.tabs(["🔍 Buscar Proyectos", "📋 Mis Intereses", "📊 Mis Transacciones"])

    with tab1:
        # Búsqueda avanzada de proyectos
        show_advanced_project_search_v2(client_email)

    with tab2:
        # Mostrar proyectos guardados/interesantes
        show_client_interests_v2(client_email)

    with tab3:
        # Mostrar transacciones realizadas
        show_client_transactions_v2(client_email)


def show_owner_panel_v2(client_email):
    """Panel para propietarios con fincas - V2"""
    st.subheader("🏠 Mis Propiedades Publicadas V2")

    # Obtener fincas del propietario
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, cadastral_ref, surface_m2, buildable_m2, is_urban, vector_geojson, registry_note_path, price, lat, lon, status, created_at, photo_paths, owner_name, owner_email, owner_phone, sanitation_type, plot_type, propietario_direccion FROM plots WHERE owner_email = ? ORDER BY created_at DESC", (client_email,))

    properties = cursor.fetchall()
    conn.close()

    if not properties:
        st.warning("No tienes propiedades publicadas")
        return

    # Mostrar propiedades
    for prop in properties:
        prop_id = prop[0]
        title = prop[1]
        surface_m2 = prop[3]
        price = prop[8]
        status = prop[11]
        created_at = prop[12]
        photo_paths = prop[13]
        owner_name = prop[14]
        owner_phone = prop[16]

        status_emoji = "✅" if status == "published" else "⏳" if status == "pending" else "❌"

        with st.expander(f"{status_emoji} {title} - {surface_m2} m²", expanded=True):
            col1, col2 = st.columns([1, 2])

            with col1:
                # Mostrar imagen de la finca
                if photo_paths:
                    try:
                        paths = json.loads(photo_paths)
                        if paths and isinstance(paths, list):
                            img_path = f"uploads/{paths[0]}"
                            if os.path.exists(img_path):
                                st.image(img_path, width=200)
                    except:
                        st.image("assets/fincas/image1.jpg", width=200)
                else:
                    st.image("assets/fincas/image1.jpg", width=200)

            with col2:
                st.markdown(f"**🏠 Propiedad:** {title}")
                st.markdown(f"**📏 Superficie:** {surface_m2} m²")
                st.markdown(f"**💰 Precio:** €{price}")
                st.markdown(f"**📊 Estado:** {status.capitalize()}")
                st.markdown(f"**📅 Publicada:** {created_at}")
                st.markdown(f"**📞 Contacto:** {owner_phone}")

                # Estadísticas de la propiedad
                st.markdown("---")
                st.markdown("**📈 Estadísticas:**")

                # Contar propuestas para esta finca
                conn = db_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM proposals WHERE plot_id = ?", (prop_id,))
                proposals_count = cursor.fetchone()[0]
                conn.close()

                col_stats1, col_stats2 = st.columns(2)
                with col_stats1:
                    st.metric("📨 Propuestas Recibidas", proposals_count)
                with col_stats2:
                    st.metric("👁️ Visitas Estimadas", "N/A")  # TODO: implementar contador de visitas

    # Opciones específicas para propietarios
    st.markdown("---")
    st.subheader("🎯 Gestión de Propiedades V2")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 VER PROPUESTAS")
        st.write("Revisa las propuestas de arquitectos para tus fincas")
        if st.button("📨 Ver Todas las Propuestas", key="view_proposals_owner_v2", use_container_width=True, type="primary"):
            st.success("📨 Mostrando todas las propuestas... (V2)")
            st.info("Aquí podrás gestionar todas las propuestas recibidas para tus propiedades")

    with col2:
        st.markdown("#### ➕ PUBLICAR MÁS FINCAS")
        st.write("Añade más propiedades a tu portafolio")
        if st.button("🏠 Subir Nueva Finca", key="upload_new_property_v2", use_container_width=True, type="primary"):
            st.success("🏠 Redirigiendo a subida de fincas... (V2)")
            st.info("Accede desde el menú lateral 'Propietarios (Subir Fincas)'")

    show_common_actions_v2(context="owner")


def show_client_interests_v2(client_email):
    """Mostrar proyectos de interés del cliente - V2"""
    st.subheader("⭐ Mis Proyectos de Interés V2")

    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ci.project_id, ci.created_at, p.title, p.m2_construidos, p.price, p.foto_principal
        FROM client_interests ci
        JOIN projects p ON ci.project_id = p.id
        WHERE ci.email = ?
        ORDER BY ci.created_at DESC
    """, (client_email,))

    interests = cursor.fetchall()
    conn.close()

    if not interests:
        st.info("No tienes proyectos guardados como de interés. Explora el marketplace para encontrar proyectos que te gusten.")
        return

    # Mostrar proyectos de interés
    for interest in interests:
        project_id, saved_at, title, m2, price, foto = interest

        with st.expander(f"🏗️ {title}", expanded=True):
            col1, col2 = st.columns([1, 2])

            with col1:
                if foto:
                    try:
                        st.image(foto, width=200)
                    except:
                        st.image("assets/fincas/image1.jpg", width=200)
                else:
                    st.image("assets/fincas/image1.jpg", width=200)

            with col2:
                st.markdown(f"**🏗️ Proyecto:** {title}")
                st.markdown(f"**📏 Superficie:** {m2} m²" if m2 else "**📏 Superficie:** N/D")
                st.markdown(f"**💰 Precio:** €{price:,.0f}" if price else "**💰 Precio:** N/D")
                st.markdown(f"**📅 Guardado:** {saved_at}")

                if st.button("Ver Detalles", key=f"view_interest_v2_{project_id}"):
                    st.query_params["selected_project_v2"] = project_id
                    st.rerun()


def show_client_transactions_v2(client_email):
    """Mostrar transacciones del cliente (fincas compradas) - V2"""
    st.subheader("📋 Mis Transacciones V2")

    # Obtener transacciones del cliente
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.id, r.plot_id, r.buyer_name, r.amount, r.kind, r.created_at,
           p.title, p.m2, p.price, p.photo_paths
    FROM reservations r
    JOIN plots p ON r.plot_id = p.id
    WHERE r.buyer_email = ?
    ORDER BY r.created_at DESC
""", (client_email,))

    transactions = cursor.fetchall()
    conn.close()

    if not transactions:
        st.info("No se encontraron transacciones para este cliente.")
        return

    # Mostrar tabla general
    st.dataframe(transactions)

    # Mostrar resumen de transacciones
    for trans in transactions:
        trans_id, plot_id, buyer_name, amount, kind, created_at, plot_title, m2, price, photo_paths = trans

        with st.expander(f"🏠 {plot_title} - {kind.upper()}", expanded=True):
            col1, col2 = st.columns([1, 2])

            # 📸 Columna izquierda: imagen
            with col1:
                if photo_paths:
                    try:
                        paths = json.loads(photo_paths)
                        if paths and isinstance(paths, list):
                            image_paths = [f"uploads/{path}" for path in paths]
                            st.image(image_paths, caption=["Foto " + str(i+1) for i in range(len(image_paths))], use_container_width=True)
                    except Exception as e:
                        st.warning(f"No se pudo cargar la imagen: {e}")

            # 📋 Columna derecha: detalles
            with col2:
                st.markdown(f"**📋 ID Transacción:** `{trans_id}`")
                st.markdown(f"**🏠 Finca:** {plot_title}")
                st.markdown(f"**📏 Superficie:** {m2} m²")
                st.markdown(f"**💰 Precio Total:** €{price}")
                st.markdown(f"**💵 Cantidad Pagada:** €{amount}")
                st.markdown(f"**📅 Fecha:** {created_at}")
                st.markdown(f"**✅ Tipo:** {kind.upper()}")

        # 🔍 PROYECTOS COMPATIBLES
        st.markdown("### 📐 Proyectos Compatibles")

        proyectos = get_proyectos_compatibles(plot_id)

        if not proyectos:
            st.info("No hay proyectos compatibles para esta finca.")
        else:
            for p in proyectos:
                st.markdown(f"**🏗️ {p.get('nombre', 'Proyecto sin nombre')}** — {p.get('total_m2', '?')} m²")

                img = p.get("imagen_principal")
                if img:
                    st.image(f"assets/projects/{img}", use_container_width=True)

                st.markdown("---")

        show_common_actions_v2(context=f"buyer_{trans_id}")  # Acciones comunes para compradores


def show_common_actions_v2(context="common"):
    """Acciones comunes para compradores y propietarios - V2"""
    st.markdown("---")

    # Opciones de acción
    st.subheader("🎯 ¿Qué deseas hacer? V2")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key=f"go_designer_panel_2_{context}", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda... (V2)")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")

    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key=f"go_projects_panel_{context}", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles... (V2)")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")

    st.markdown("---")

    # Opciones adicionales
    st.subheader("🔧 Opciones Adicionales V2")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("🗺️ Volver al Marketplace", key=f"back_to_marketplace_{context}", use_container_width=True):
            st.success("🏠 Volviendo al marketplace... (V2)")
            st.info("Puedes seguir explorar más fincas y proyectos")

    with col_b:
        if st.button("📧 Contactar Soporte", key=f"contact_support_{context}", use_container_width=True):
            st.info("📧 Contacto con soporte:")
            st.write("**Email:** soporte@archirapid.com")
            st.write("**Teléfono:** +34 900 123 456")

    with col_c:
        if st.button("📄 Descargar Documentación", key=f"download_docs_{context}", use_container_width=True):
            st.info("📄 Descarga disponible próximamente")
            st.write("Pronto podrás descargar todos los documentos de tu transacción")


def show_advanced_project_search_v2(client_email):
    """Búsqueda avanzada de proyectos por criterios - V2"""
    st.subheader("🔍 Buscar Proyectos Arquitectónicos V2")
    st.write("Encuentra proyectos compatibles con tus necesidades específicas")

    # Formulario de búsqueda
    with st.form("advanced_search_form_v2"):
        st.markdown("### 🎯 Especifica tus criterios")

        col1, col2 = st.columns(2)

        with col1:
            presupuesto_max = st.number_input(
                "💰 Presupuesto máximo (€)",
                min_value=0,
                value=0,
                step=10000,
                help="Precio máximo que estás dispuesto a pagar por el proyecto completo"
            )

            area_deseada = st.number_input(
                "📐 Área de construcción deseada (m²)",
                min_value=0,
                value=0,
                step=10,
                help="Superficie aproximada que quieres construir (±20% tolerancia)"
            )

        with col2:
            parcela_disponible = st.number_input(
                "🏞️ Parcela disponible (m²)",
                min_value=0,
                value=0,
                step=50,
                help="Tamaño de terreno que tienes disponible"
            )

            # Checkbox para buscar solo proyectos que quepan
            solo_compatibles = st.checkbox(
                "Solo proyectos que quepan en mi parcela",
                value=True,
                help="Filtrar proyectos cuya parcela mínima sea ≤ a tu terreno disponible"
            )

        # Botón de búsqueda
        submitted = st.form_submit_button("🔍 Buscar Proyectos", type="primary", width='stretch')

    # Mostrar proyectos disponibles (todos al inicio, filtrados si se buscó)
    search_params = {'client_email': client_email}  # Parámetros por defecto

    # Si se hizo una búsqueda, usar esos parámetros
    if 'last_search_params_v2' in st.session_state:
        search_params = st.session_state['last_search_params_v2']

    # Buscar proyectos
    with st.spinner("Cargando proyectos..."):
        proyectos = get_proyectos_compatibles(**search_params)

    # Mostrar contador
    st.markdown(f"### 🏗️ Proyectos Disponibles: {len(proyectos)}")

    if not proyectos:
        st.info("No hay proyectos disponibles en este momento.")
        return

    # Formulario de búsqueda (siempre visible)
    with st.expander("🔍 Filtrar Proyectos", expanded=False):
        with st.form("advanced_search_form_v2"):
            st.markdown("### 🎯 Especifica tus criterios")

            col1, col2 = st.columns(2)

            with col1:
                presupuesto_max = st.number_input(
                    "💰 Presupuesto máximo (€)",
                    min_value=0,
                    value=0,
                    step=10000,
                    help="Precio máximo que estás dispuesto a pagar por el proyecto completo"
                )

                area_deseada = st.number_input(
                    "📐 Área de construcción deseada (m²)",
                    min_value=0,
                    value=0,
                    step=10,
                    help="Superficie aproximada que quieres construir (±20% tolerancia)"
                )

            with col2:
                parcela_disponible = st.number_input(
                    "🏞️ Parcela disponible (m²)",
                    min_value=0,
                    value=0,
                    step=50,
                    help="Tamaño de terreno que tienes disponible"
                )

                # Checkbox para buscar solo proyectos que quepan
                solo_compatibles = st.checkbox(
                    "Solo proyectos que quepan en mi parcela",
                    value=True,
                    help="Filtrar proyectos cuya parcela mínima sea ≤ a tu terreno disponible"
                )

            # Botón de búsqueda
            submitted = st.form_submit_button("🔍 Aplicar Filtros", type="primary", width='stretch')

        if submitted:
            # Preparar parámetros de búsqueda
            search_params = {
                'client_budget': presupuesto_max if presupuesto_max > 0 else None,
                'client_desired_area': area_deseada if area_deseada > 0 else None,
                'client_parcel_size': parcela_disponible if parcela_disponible > 0 and solo_compatibles else None,
                'client_email': client_email
            }
            st.session_state['last_search_params_v2'] = search_params

            # Mostrar criterios aplicados
            st.markdown("### 📋 Filtros aplicados:")
            criterios = []
            if search_params['client_budget']:
                criterios.append(f"💰 Presupuesto ≤ €{search_params['client_budget']:,}")
            if search_params['client_desired_area']:
                criterios.append(f"📐 Área ≈ {search_params['client_desired_area']} m² (±20%)")
            if search_params['client_parcel_size']:
                criterios.append(f"🏞️ Parcela ≥ {search_params['client_parcel_size']} m²")

            if criterios:
                for criterio in criterios:
                    st.write(f"• {criterio}")
            else:
                st.info("Mostrando todos los proyectos")

            # Re-buscar con filtros
            with st.spinner("Aplicando filtros..."):
                proyectos = get_proyectos_compatibles(**search_params)
            st.markdown(f"### 🏗️ Resultados filtrados: {len(proyectos)} proyectos")

    # Mostrar proyectos en grid
    cols = st.columns(2)
    for idx, proyecto in enumerate(proyectos):
        with cols[idx % 2]:
            # Tarjeta de proyecto
            with st.container():
                # Imagen
                foto = proyecto.get('foto_principal')
                if foto:
                    try:
                        st.image(foto, width=250, caption=proyecto['title'])
                    except:
                        st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])
                else:
                    st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])

                # Información básica
                st.markdown(f"**🏗️ {proyecto['title']}**")
                st.write(f"📐 **Área:** {proyecto.get('m2_construidos', proyecto.get('area_m2', 'N/D'))} m²")
                st.write(f"💰 **Precio:** €{proyecto.get('price', 0):,.0f}" if proyecto.get('price') else "💰 **Precio:** Consultar")

                # Arquitecto
                if proyecto.get('architect_name'):
                    st.write(f"👨‍💼 **Arquitecto:** {proyecto['architect_name']}")

                # Compatibilidad (si hay filtros aplicados)
                if 'last_search_params_v2' in st.session_state and st.session_state['last_search_params_v2'].get('client_parcel_size'):
                    parcel_size = st.session_state['last_search_params_v2']['client_parcel_size']
                    if proyecto.get('m2_parcela_minima'):
                        if proyecto['m2_parcela_minima'] <= parcel_size:
                            st.success("✅ Compatible con tu parcela")
                        else:
                            st.warning(f"⚠️ Necesita parcela ≥ {proyecto['m2_parcela_minima']} m²")

                # Botón de detalles
                if st.button("Ver Detalles", key=f"search_detail_v2_{proyecto['id']}", use_container_width=True):
                    st.query_params["selected_project_v2"] = proyecto['id']
                    st.rerun()

                # Botones de compra directa (si está logueado)
                if st.session_state.get("client_logged_in", False):
                    # Verificar si ya compró este proyecto
                    conn_check = db_conn()
                    cursor_check = conn_check.cursor()
                    cursor_check.execute("SELECT id FROM ventas_proyectos WHERE proyecto_id = ? AND cliente_email = ?", (proyecto['id'], client_email))
                    ya_compro = cursor_check.fetchone()
                    conn_check.close()

                    if ya_compro:
                        st.success("✅ Ya adquirido")
                    else:
                        # Botones de compra
                        col_buy_pdf, col_buy_cad = st.columns(2)
                        with col_buy_pdf:
                            if st.button(f"📄 PDF €{proyecto.get('price_memoria', 1800)}", key=f"buy_pdf_{proyecto['id']}", use_container_width=True):
                                # Simular compra de PDF
                                with st.spinner("Procesando compra..."):
                                    import time
                                    time.sleep(1)
                                # Registrar compra
                                conn_buy = db_conn()
                                cursor_buy = conn_buy.cursor()
                                cursor_buy.execute("""
                                    INSERT INTO ventas_proyectos
                                    (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (proyecto['id'], client_email, "Compra directa", "PDF", proyecto.get('price_memoria', 1800), "Simulado"))
                                conn_buy.commit()
                                conn_buy.close()
                                st.success("🎉 PDF comprado!")
                                st.rerun()

                        with col_buy_cad:
                            if st.button(f"🖥️ CAD €{proyecto.get('price_cad', 2500)}", key=f"buy_cad_{proyecto['id']}", use_container_width=True):
                                # Simular compra de CAD
                                with st.spinner("Procesando compra..."):
                                    import time
                                    time.sleep(1)
                                # Registrar compra
                                conn_buy = db_conn()
                                cursor_buy = conn_buy.cursor()
                                cursor_buy.execute("""
                                    INSERT INTO ventas_proyectos
                                    (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (proyecto['id'], client_email, "Compra directa", "CAD", proyecto.get('price_cad', 2500), "Simulado"))
                                conn_buy.commit()
                                conn_buy.close()
                                st.success("🎉 CAD comprado!")
                                st.rerun()

                st.markdown("---")


# === NUEVAS RUTAS V2 (BORRÓN Y CUENTA NUEVA) ===
page_from_query = False  # Variable para controlar si la página viene de query params
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
        st.session_state['selected_page'] = "🔍 Detalle de Finca"
        st.session_state['selected_plot'] = plot_id
        del st.query_params["selected_plot"]
        st.rerun()
    except Exception as e:
        st.error(f"Error procesando finca seleccionada: {e}")
    st.stop()  # Detener la ejecución para no mostrar el resto de la app

if st.query_params.get("page") == "👤 Panel de Cliente":
    try:
        panel_cliente_v2()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando panel cliente v2: {e}")

if st.query_params.get("page") == "Registro de Usuario":
    try:
        registro_v2()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando registro v2: {e}")


# Page configuration and navigation - SIMPLIFIED VERSION
PAGES = {
    "🏠 Inicio / Marketplace": ("modules.marketplace.marketplace", "main"),
    "🔍 Detalle de Finca": ("modules.marketplace.plot_detail", "show_plot_detail_page"),
    "Intranet": ("modules.marketplace.intranet", "main"),
    "👤 Panel de Proveedor": ("modules.marketplace.service_providers", "show_service_provider_panel"),
    "📝 Registro de Proveedor de Servicios": ("modules.marketplace.service_providers", "show_service_provider_registration"),
    "Arquitectos (Marketplace)": ("modules.marketplace.marketplace_upload", "main"),
    "👤 Panel de Cliente": ("modules.marketplace.client_panel", "main"),
    "🏠 Propietarios": ("modules.marketplace.owners", "main"),
    "Iniciar Sesión": ("modules.marketplace.auth", "show_login"),
    "Registro de Usuario": ("modules.marketplace.auth", "show_registration"),
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

                try:
                    html_final = three_html_for(model_url, str(proyecto.get("id")))
                    st.components.v1.html(html_final, height=700, scrolling=False)
                except Exception as e:
                    st.error(f"Error cargando visor 3D: {e}")
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

# El sidebar DEBE leer de session_state obligatoriamente
selected_page = st.sidebar.radio(
    "Navegación",
    options=PAGES,
    index=PAGES.index(st.session_state.get('selected_page', "🏠 Inicio / Marketplace")) if st.session_state.get('selected_page', "🏠 Inicio / Marketplace") in PAGES else 0
)

# Sincronizamos por si el usuario cambia el radio manualmente
st.session_state['selected_page'] = selected_page

# Lógica de Redirección
if st.session_state.get('selected_page') == "🏠 Inicio / Marketplace":
    st.query_params.clear()
elif st.session_state.get('selected_page') in ["👤 Panel de Proveedor", "📝 Registro de Proveedor de Servicios"]:
    st.query_params["page"] = st.session_state.get('selected_page')

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
            if st.button("🔑 Acceder", key="btn_acceder"):
                if st.session_state.get('rol') == 'admin':
                    st.session_state['selected_page'] = 'Intranet'
                    st.rerun()
                else:
                    st.session_state['show_role_selector'] = True
                    st.rerun()

# ========== HOME: LANDING + MARKETPLACE + PROYECTOS ==========

    # Mostrar formulario de login si viewing_login es True
    if st.session_state.get('viewing_login', False):
        st.markdown("---")
        st.header(f"🔐 Iniciar Sesión - {st.session_state.get('login_role', '').title()}")
        
        modo_registro = st.checkbox("¿Es tu primera vez? Activa el modo registro", key="modo_registro")
        
        with st.form("login_form"):
            if modo_registro:
                st.subheader("📝 Registro de Nuevo Usuario")
                name = st.text_input("Nombre completo *", placeholder="Tu nombre completo")
                email = st.text_input("Email *", placeholder="tu@email.com")
                password = st.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
                password_confirm = st.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("🚀 Registrarme y Acceder", type="primary")
                with col2:
                    if st.form_submit_button("⬅️ Volver al login"):
                        st.session_state['modo_registro'] = False
                        st.rerun()
                
                if submitted:
                    if not name or not email or not password:
                        st.error("Por favor, completa los campos obligatorios marcados con *.")
                    elif password != password_confirm:
                        st.error("Las contraseñas no coinciden.")
                    elif len(password) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                    else:
                        try:
                            from werkzeug.security import generate_password_hash
                            hashed_password = generate_password_hash(password)
                            
                            conn = db_conn()
                            c = conn.cursor()
                            
                            c.execute("""
                                INSERT INTO users (email, full_name, role, is_professional, password_hash, created_at)
                                VALUES (?, ?, ?, ?, ?, datetime('now'))
                            """, (
                                email, name, 'client',
                                0,  # is_professional
                                hashed_password
                            ))
                            
                            user_id = c.lastrowid
                            conn.commit()
                            conn.close()
                            
                            st.success("🎉 ¡Registro completado exitosamente!")
                            
                            # Login automático
                            st.session_state['user_id'] = user_id
                            st.session_state['user_email'] = email
                            st.session_state['role'] = 'client'
                            st.session_state['user_name'] = name
                            st.session_state['logged_in'] = True
                            st.session_state['viewing_login'] = False
                            st.session_state['show_role_selector'] = False
                            
                            # Redirigir según el rol
                            if st.session_state['role'] == 'client':
                                st.session_state['selected_page'] = "👤 Panel de Cliente"
                            elif st.session_state['role'] == 'architect':
                                st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                            elif st.session_state['role'] == 'services':
                                st.session_state['selected_page'] = "👤 Panel de Proveedor"
                            elif st.session_state['role'] == 'admin':
                                st.session_state['selected_page'] = "Intranet"
                            
                            st.success(f"¡Bienvenido {name}!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error en el registro: {e}")
            else:
                email = st.text_input("📧 Email", key="login_email")
                password = st.text_input("🔒 Contraseña", type="password", key="login_password")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("🚀 Entrar", type="primary")
                with col2:
                    if st.form_submit_button("⬅️ Volver al selector"):
                        st.session_state['viewing_login'] = False
                        st.session_state['show_role_selector'] = True
                        st.rerun()
                
                if submitted:
                    if not email or not password:
                        st.error("Por favor, completa todos los campos.")
                    else:
                        # Usar la función de autenticación existente
                        from modules.marketplace.auth import authenticate_user
                        user_data = authenticate_user(email, password)
                        
                        if user_data and user_data.get('role') == st.session_state.get('login_role'):
                            # Login exitoso
                            st.session_state['user_id'] = user_data['id']
                            st.session_state['user_email'] = user_data['email']
                            st.session_state['role'] = user_data['role']
                            st.session_state['user_name'] = user_data.get('full_name') or user_data.get('name') or user_data.get('email', 'Usuario')
                            st.session_state['logged_in'] = True
                            st.session_state['viewing_login'] = False
                            st.session_state['show_role_selector'] = False
                            
                            # Redirigir según el rol
                            if st.session_state['role'] == 'client':
                                st.session_state['selected_page'] = "👤 Panel de Cliente"
                            elif st.session_state['role'] == 'architect':
                                st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                            elif st.session_state['role'] == 'services':
                                st.session_state['selected_page'] = "👤 Panel de Proveedor"
                            elif st.session_state['role'] == 'admin':
                                st.session_state['selected_page'] = "Intranet"
                            
                            st.success(f"¡Bienvenido {st.session_state['user_name']}!")
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas o rol no coincide.")
        
        st.stop()  # Detener el resto de la Home

    if st.session_state.get('show_role_selector', False):
        # Pantalla de Selector de Rol
        st.markdown("---")
        st.header("🔐 Selecciona tu Perfil de Acceso")
        st.markdown("Elige el tipo de usuario que eres para acceder a las funcionalidades correspondientes.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("### 🏠 Cliente")
            st.markdown("Accede a tus proyectos y compras.")
            if st.button("🔑 Acceso Cliente", key="select_client", use_container_width=True):
                st.session_state['login_role'] = 'client'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col2:
            st.markdown("### 🏗️ Arquitecto")
            st.markdown("Gestiona tus diseños y fincas.")
            if st.button("🔑 Acceso Arquitecto", key="select_architect", use_container_width=True):
                st.session_state['login_role'] = 'architect'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col3:
            st.markdown("### 🏡 Propietario")
            st.markdown("Administra tus propiedades.")
            if st.button("🔑 Acceso Propietario", key="select_owner", use_container_width=True):
                st.session_state['login_role'] = 'owner'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col4:
            st.markdown("### 🛠️ Servicios")
            st.markdown("Gestiona tus servicios profesionales.")
            if st.button("🔑 Acceso Servicios", key="select_services", use_container_width=True):
                st.session_state['login_role'] = 'services'
                st.session_state['viewing_login'] = True
                st.rerun()

        # Botón discreto para admin
        st.markdown("---")
        col_admin = st.columns([10, 1])[1]
        with col_admin:
            if st.button("🔐 Admin", key="admin_access"):
                st.session_state['login_role'] = 'admin'
                st.session_state['viewing_login'] = True
                st.rerun()

        # Botón para volver
        st.markdown("---")
        if st.button("⬅️ Volver", key="back_to_home"):
            st.session_state['show_role_selector'] = False
            st.rerun()
        st.stop()  # Detenemos el resto de la Home

    else:
        # PASO 1: Renderizar MARKETPLACE (contiene las tarjetas de acceso)
        try:
            from modules.marketplace import marketplace
            marketplace.main()
        except Exception as e:
            import traceback
            st.error(f"❌ Error cargando marketplace:  {e}")
            st.code(traceback.format_exc())

        # PASO 3: Renderizar PROYECTOS ARQUITECTÓNICOS
        st.markdown("---")
        st.header("🏗️ Proyectos Arquitectónicos Disponibles")

        try:
            from src import db
            from modules.marketplace.marketplace import get_project_display_image
            projects = db.get_featured_projects(limit=6)
            
            if projects: 
                cols = st.columns(3)
                for idx, p in enumerate(projects):
                    with cols[idx % 3]:
                        # Usar función unificada para obtener imagen del proyecto
                        thumbnail = get_project_display_image(p['id'], image_type='main')
                        
                        st.image(thumbnail, width=250)
                        st.subheader(p.get('title', 'Proyecto'))
                        st.write(f"**€{p.get('price', 0):,.0f}** | {p.get('area_m2', 0)} m²")
                        if st.button("DETALLES (v2)", key=f"proj_home_{p['id']}"):
                            # Abrir en "nueva ventana" usando query params V2
                            st.query_params["selected_project_v2"] = p['id']
                            st.rerun()
            else:
                st.info("No hay proyectos arquitectónicos disponibles aún.")
        except Exception as e:
            st.error(f"Error cargando proyectos: {e}")

    # Banner de captación para profesionales
    st.markdown("---")
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("""
            <div style="background-color: #f0f8ff; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff;">
                <h3 style="color: #007bff; margin-top: 0;">¿Eres profesional de la construcción o reformas?</h3>
                <p style="margin-bottom: 0;">Únete a nuestra red de proveedores y conecta con clientes que necesitan tus servicios.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("Registrarme como Profesional", key="register_professional"):
                st.session_state['selected_page'] = "📝 Registro de Proveedor de Servicios"
                st.rerun()

    # Botón para buscar profesionales
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🛠️ Buscar Profesionales", key="search_professionals"):
            from modules.marketplace import service_providers
            service_providers.show_services_marketplace()

    st.stop()  # Detener ejecución para Home

if st.session_state.get('selected_page') == "Propietario (Gemelo Digital)":
    with st.container():
        # Flujo principal: Propietario sube finca → IA genera plan
        from modules.marketplace import gemelo_digital
        gemelo_digital.main()

elif st.session_state.get('selected_page') == "🏠 Propietarios":
    with st.container():
        # Propietarios suben fincas al marketplace inmobiliario
        from modules.marketplace import owners
        owners.main()

elif st.session_state.get('selected_page') == "Diseñador de Vivienda":
    with st.container():
        # Flujo secundario: Cliente diseña vivienda personalizada
        from modules.marketplace import disenador_vivienda
        disenador_vivienda.main()

# "Inmobiliaria (Mapa)" route removed — Home now uses `marketplace.main()` directly.

elif st.session_state.get('selected_page') == "👤 Panel de Cliente":
    with st.container():
        # Importar y ejecutar el panel de cliente
        from modules.marketplace import client_panel
        client_panel.main()

elif st.session_state.get('selected_page') == "Arquitectos (Marketplace)":
    with st.container():
        # Use the new main() entrypoint which handles auth, plans and upload flow
        from modules.marketplace import marketplace_upload
        marketplace_upload.main()

elif st.session_state.get('selected_page') == "Intranet":
    st.write("Cargando Panel de Control...")
    with st.container():
        from modules.marketplace import intranet
        intranet.main()

elif st.session_state.get('selected_page') == "👤 Panel de Proveedor":
    with st.container():
        from modules.marketplace import service_providers
        service_providers.show_service_provider_panel()

elif st.session_state.get('selected_page') == "📝 Registro de Proveedor de Servicios":
    with st.container():
        from modules.marketplace import service_providers
        service_providers.show_service_provider_registration()

elif st.session_state.get('selected_page') == "Iniciar Sesión":
    with st.container():
        from modules.marketplace import auth
        auth.show_login()
        st.stop()

elif st.session_state.get('selected_page') == "Registro de Usuario":
    with st.container():
        from modules.marketplace import auth
        auth.show_registration()
        st.stop()
