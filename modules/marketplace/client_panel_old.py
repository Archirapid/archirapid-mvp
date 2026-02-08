# modules/marketplace/client_panel.py
import streamlit as st
from modules.marketplace.utils import db_conn
import json
import os

def main():
    st.title("👤 Panel de Cliente - ARCHIRAPID")
    
    # Auto-login si viene de query params con owner_email
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
            # st.session_state["user_role"] = "buyer" if transactions else "owner"  # DESACTIVADO: Asignación ilegal
            st.session_state["has_transactions"] = len(transactions) > 0
            st.session_state["has_properties"] = len(owner_plots) > 0
            
            role_text = "comprador" if transactions else "propietario"
            st.info(f"🔄 Auto-acceso concedido como {role_text} para {auto_email}")
            
            # Limpiar el estado de auto-login
            del st.session_state["auto_owner_email"]
    
    # Login simple por email
    if "client_logged_in" not in st.session_state:
        st.session_state["client_logged_in"] = False
    
    if not st.session_state["client_logged_in"]:
        st.subheader("🔐 Acceso al Panel de Cliente")
        st.info("Introduce el email que usaste al realizar tu compra/reserva")
        
        email = st.text_input("Email de cliente", placeholder="tu@email.com")
        
        if st.button("Acceder", type="primary"):
            if email:
                # Verificar si el email tiene transacciones O es propietario con fincas
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
                
                conn.close()
                
                # Permitir acceso si tiene transacciones O fincas como propietario
                if transactions or owner_plots:
                    st.session_state["client_logged_in"] = True
                    st.session_state["client_email"] = email
                    # st.session_state["user_role"] = "buyer" if transactions else "owner"  # DESACTIVADO: Asignación ilegal
                    st.session_state["has_transactions"] = len(transactions) > 0
                    st.session_state["has_properties"] = len(owner_plots) > 0
                    
                    role_text = "comprador" if transactions else "propietario"
                    st.success(f"✅ Acceso concedido como {role_text} para {email}")
                    st.rerun()
                else:
                    st.error("No se encontraron transacciones ni propiedades para este email")
            else:
                st.error("Por favor introduce tu email")
        
        st.markdown("---")
        st.info("💡 **Nota:** Si acabas de realizar una compra, usa el email que proporcionaste en el formulario de datos personales.")
        st.stop()
    
    # Panel de cliente logueado
    client_email = st.session_state.get("client_email")
    user_role = st.session_state.get("user_role", "buyer")
    has_transactions = st.session_state.get("has_transactions", False)
    has_properties = st.session_state.get("has_properties", False)
    
    # Botón de cerrar sesión en sidebar
    with st.sidebar:
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state["client_logged_in"] = False
            if "client_email" in st.session_state:
                del st.session_state["client_email"]
            if "user_role" in st.session_state:
                del st.session_state["user_role"]
            if "has_transactions" in st.session_state:
                del st.session_state["has_transactions"]
            if "has_properties" in st.session_state:
                del st.session_state["has_properties"]
            st.rerun()
    
    # Mostrar rol del usuario
    role_emoji = "🛒" if user_role == "buyer" else "🏠"
    role_text = "Comprador" if user_role == "buyer" else "Propietario"
    st.success(f"{role_emoji} **Bienvenido/a {role_text}** - {client_email}")
    
    # Contenido diferente según el rol
    if user_role == "buyer" and has_transactions:
        # Panel para compradores con transacciones
        show_buyer_panel(client_email)
    elif user_role == "owner" and has_properties:
        # Panel para propietarios con fincas
        show_owner_panel_v2(client_email)
    else:
        st.error("Error: No se pudo determinar el tipo de panel apropiado")
        st.stop()

def show_buyer_panel(client_email):
    """Panel para compradores con transacciones"""
    st.subheader("📋 Mis Transacciones")
    
    # Obtener transacciones del cliente
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.plot_id, r.buyer_name, r.amount, r.kind, r.created_at, 
               p.title, p.surface_m2, p.price, p.photo_paths
        FROM reservations r
        LEFT JOIN plots p ON r.plot_id = p.id
        WHERE r.buyer_email = ?
        ORDER BY r.created_at DESC
    """, (client_email,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    if not transactions:
        st.warning("No tienes transacciones registradas")
        return
    
    # Mostrar resumen de transacciones
    for trans in transactions:
        trans_id, plot_id, buyer_name, amount, kind, created_at, plot_title, surface_m2, price, photo_paths = trans
        
        with st.expander(f"🏠 {plot_title} - {kind.upper()}", expanded=True):
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
                st.markdown(f"**📋 ID Transacción:** `{trans_id}`")
                st.markdown(f"**🏠 Finca:** {plot_title}")
                st.markdown(f"**📏 Superficie:** {surface_m2} m²")
                st.markdown(f"**💰 Precio Total:** €{price}")
                st.markdown(f"**💵 Cantidad Pagada:** €{amount}")
                st.markdown(f"**📅 Fecha:** {created_at}")
                st.markdown(f"**✅ Tipo:** {kind.upper()}")
    
    show_common_actions()  # Acciones comunes para compradores

def show_owner_panel_v2(client_email):
    """Panel para propietarios con fincas"""
    st.subheader("🏠 Mis Propiedades Publicadas")
    
    # Obtener fincas del propietario
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, owner_id, title, cadastral_ref, surface_m2, buildable_m2, is_urban, vector_geojson, registry_note_path, price, lat, lon, status, created_at, photo_paths, owner_name, owner_email, owner_phone, sanitation_type, plot_type, propietario_direccion FROM plots WHERE owner_email = ? ORDER BY created_at DESC", (client_email,))
    
    properties = cursor.fetchall()
    conn.close()
    
    if not properties:
        st.warning("No tienes propiedades publicadas")
        return
    
    # Mostrar propiedades
    for prop in properties:
        prop_id = prop[0]
        title = prop[2]
        surface_m2 = prop[4]
        price = prop[9]
        status = prop[12]
        created_at = prop[13]
        photo_paths = prop[14]
        owner_name = prop[15]
        owner_phone = prop[17]
        
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
    st.subheader("🎯 Gestión de Propiedades")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 VER PROPUESTAS")
        st.write("Revisa las propuestas de arquitectos para tus fincas")
        if st.button("📨 Ver Todas las Propuestas", key="view_proposals_owner", use_container_width=True, type="primary"):
            st.success("📨 Mostrando todas las propuestas...")
            st.info("Aquí podrás gestionar todas las propuestas recibidas para tus propiedades")
    
    with col2:
        st.markdown("#### ➕ PUBLICAR MÁS FINCAS")
        st.write("Añade más propiedades a tu portafolio")
        if st.button("🏠 Subir Nueva Finca", key="upload_new_property", use_container_width=True, type="primary"):
            st.success("🏠 Redirigiendo a subida de fincas...")
            st.info("Accede desde el menú lateral 'Propietarios (Subir Fincas)'")
    
    show_common_actions()  # Acciones comunes para todos

def show_buyer_actions():
    """Acciones comunes para compradores"""
    st.markdown("---")
    
    # Opciones de acción para compradores
    st.subheader("🎯 ¿Qué deseas hacer?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key="go_designer_panel", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda...")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")
    
    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key="go_projects_panel", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles...")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")
    
    st.markdown("---")
    
    # Opciones adicionales
    st.subheader("🔧 Opciones Adicionales")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        if st.button("🗺️ Volver al Marketplace", key="back_to_marketplace", use_container_width=True):
            st.success("🏠 Volviendo al marketplace...")
            st.info("Puedes seguir explorando más fincas y proyectos")
    
    with col_b:
        if st.button("📧 Contactar Soporte", key="contact_support_panel", use_container_width=True):
            st.info("📧 Contacto con soporte:")
            st.write("**Email:** soporte@archirapid.com")
            st.write("**Teléfono:** +34 900 123 456")
    
    with col_c:
        if st.button("📄 Descargar Documentación", key="download_docs", use_container_width=True):
            st.info("📄 Descarga disponible próximamente")
            st.write("Pronto podrás descargar todos los documentos de tu transacción")

# Añadir import necesario
import os
def show_common_actions():
    """Acciones comunes para compradores y propietarios"""
    st.markdown("---")
    
    # Opciones de acción
    st.subheader("🎯 ¿Qué deseas hacer?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key="go_designer_panel", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda...")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")
    
    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key="go_projects_panel", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles...")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")
    
    st.markdown("---")
    
    # Opciones adicionales
    st.subheader("🔧 Opciones Adicionales")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        if st.button("🗺️ Volver al Marketplace", key="back_to_marketplace", use_container_width=True):
            st.success("🏠 Volviendo al marketplace...")
            st.info("Puedes seguir explorando más fincas y proyectos")
    
    with col_b:
        if st.button("📧 Contactar Soporte", key="contact_support_panel", use_container_width=True):
            st.info("📧 Contacto con soporte:")
            st.write("**Email:** soporte@archirapid.com")
            st.write("**Teléfono:** +34 900 123 456")
    
    with col_c:
        if st.button("📄 Descargar Documentación", key="download_docs", use_container_width=True):
            st.info("📄 Descarga disponible próximamente")
            st.write("Pronto podrás descargar todos los documentos de tu transacción")

# Añadir import necesario
import os
