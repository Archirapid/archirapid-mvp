import streamlit as st
import sqlite3
from modules.marketplace.utils import list_published_plots, save_upload, reserve_plot, list_projects, calculate_edificability
from src import db
import folium
import uuid
import base64
import os
import json
from pathlib import Path

# Función de navegación unificada
def navigate_to(page_name):
    """Navegación unificada usando query params y session state"""
    st.query_params["page"] = page_name
    st.session_state["selected_page"] = page_name
    st.rerun()

# Helper to read query params (compatible con varias versiones de Streamlit)
def get_query_params():
    """
    Obtiene los query params actuales.
    """
    return st.query_params

# Helper to set query params (compatible con varias versiones de Streamlit)
def set_query_param(key, value):
    """
    Establece un query param.
    """
    st.query_params[key] = str(value)

# Map plot ids to images - ELIMINADO: Usar lógica unificada con BD
# PLOT_IMAGES = {
#     'finca_es_malaga': 'assets/fincas/image1.jpg',
#     'finca_es_madrid': 'assets/fincas/image2.jpg',
#     'finca_pt_lisboa': 'assets/fincas/image3.jpg',
# }

def get_plot_image_path(plot):
    """Get the image path for a plot, preferring uploaded photos from BD."""
    if plot.get('photo_paths'):
        try:
            paths = json.loads(plot['photo_paths'])
            if paths and isinstance(paths, list):
                # Añadir el prefijo uploads/ al nombre del archivo
                upload_path = f"uploads/{paths[0]}"
                # Verificar si el archivo existe
                if os.path.exists(upload_path):
                    return upload_path
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Si no hay imagen subida, usar placeholder genérico de ARCHIRAPID
    return 'assets/branding/logo.png'

def get_project_display_image(project_id, image_type='main'):
    """Función unificada para obtener imagen de proyecto.

    Args:
        project_id: ID del proyecto
        image_type: 'main' para imagen principal, 'gallery' para todas las imágenes

    Returns:
        str: Ruta a la imagen principal (si image_type='main')
        list: Lista de rutas de imágenes (si image_type='gallery')
    """
    import glob

    try:
        # PRIMERO: Intentar usar rutas de la base de datos
        try:
            project = db.get_project_by_id(project_id)
            if project and 'files' in project and 'fotos' in project['files']:
                fotos_from_db = project['files']['fotos']
                if fotos_from_db:
                    if image_type == 'main':
                        # Usar la primera imagen como principal
                        main_image = fotos_from_db[0]
                        if os.path.exists(main_image):
                            return main_image
                    elif image_type == 'gallery':
                        # Filtrar solo imágenes que existen
                        existing_images = [img for img in fotos_from_db if os.path.exists(img)]
                        if existing_images:
                            return existing_images
        except Exception as db_error:
            # Si falla la consulta a BD, continuar con escaneo físico
            pass

        # SEGUNDO: Si BD falla o no tiene imágenes, escanear físicamente
        base_path = "uploads"

        if image_type == 'main':
            # Buscar imagen principal: project_main_*
            patterns = [
                f"{base_path}/project_main_{project_id}.*",
                f"{base_path}/project_{project_id}_main.*",
                f"{base_path}/*{project_id}*main*.*",
                f"{base_path}/*{project_id}*.jpg",
                f"{base_path}/*{project_id}*.png",
                f"{base_path}/*{project_id}*.jpeg"
            ]

            for pattern in patterns:
                matches = glob.glob(pattern)
                if matches:
                    return matches[0]

            # Placeholder si no se encuentra
            return 'assets/branding/logo.png'

        elif image_type == 'gallery':
            # Buscar todas las imágenes del proyecto
            patterns = [
                f"{base_path}/project_*_{project_id}.*",
                f"{base_path}/project_{project_id}_*.*",
                f"{base_path}/*{project_id}*.*"
            ]

            all_images = []
            for pattern in patterns:
                matches = glob.glob(pattern)
                # Filtrar solo imágenes
                for match in matches:
                    if match.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                        all_images.append(match)

            # Remover duplicados y ordenar
            all_images = list(set(all_images))
            all_images.sort()

            return all_images if all_images else []

        else:
            return 'assets/branding/logo.png'

    except Exception as e:
        # En caso de error, usar placeholder
        return 'assets/branding/logo.png' if image_type == 'main' else []

def get_popup_image_url(plot):
    """
    Devuelve una URL absoluta file:// hacia la imagen de la finca,
    para que Folium pueda mostrarla en el popup aunque se ejecute en local.
    Si la imagen no existe, usa un placeholder en assets.
    """
    rel_path = get_plot_image_path(plot)  # 'uploads/...' o 'assets/...'
    rel_path = rel_path.lstrip('/').replace('\\', '/')

    # Construir ruta absoluta basada en el directorio actual del proyecto
    abs_path = Path(rel_path).resolve()

    if not abs_path.exists():
        # Fallback a placeholder
        abs_path = Path("assets/branding/logo.png").resolve()

    # Construir URL file:// (ej. file:///C:/ARCHIRAPID_PROYECT25/uploads/imagen.jpg)
    return abs_path.as_uri()

def get_plot_detail_url(plot_id):
    """
    Construye la URL completa para ver detalles de la finca.
    Apunta a la app Streamlit principal para abrir página completa.
    """
    # Base URL de Streamlit (ajusta si es diferente)
    base_url = "http://localhost:8501"
    return f"{base_url}/?selected_plot={plot_id}"

def extract_cadastral_data(plot):
    """Extrae datos catastrales de la nota si existe."""
    cadastral_data = {}

    if plot.get('registry_note_path'):
        try:
            # Usar módulos de extracción existentes - simplificado por ahora
            # TODO: Integrar con extract_pdf.py y parse_project_memoria.py cuando estén disponibles
            cadastral_data.update({
                'surface': plot.get('m2'),
                'cadastral_ref': plot.get('cadastral_ref', 'Extraído de nota'),
                'shape': 'Rectangular',
                'dimensions': 'N/A',
                'buildable_m2': int(plot.get('m2', 0) * 0.33)
            })
        except Exception as e:
            st.warning(f"No se pudieron extraer datos catastrales: {e}")

    # Fallback a datos básicos
    if not cadastral_data:
        cadastral_data = {
            'surface': plot.get('m2'),
            'cadastral_ref': plot.get('cadastral_ref', 'No disponible'),
            'shape': 'Rectangular (estimado)',
            'dimensions': 'N/A',
            'buildable_m2': int(plot.get('m2', 0) * 0.33)
        }

    return cadastral_data

def setup_filters():
    """Configura y retorna los filtros encima del mapa."""
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        min_m = st.number_input("Min m²", value=0)
    with col_f2:
        max_m = st.number_input("Max m²", value=100000)
    with col_f3:
        q = st.text_input("Buscar (provincia, título)")
    return min_m, max_m, q

def get_available_plots():
    """Lógica unificada: TODAS las fincas de la DB (sin filtros para forzar visibilidad)"""
    from modules.marketplace.utils import db_conn
    
    with db_conn() as conn:
        # Forzamos que la conexión devuelva diccionarios (el cable que falta)
        conn.row_factory = sqlite3.Row 
        cur = conn.cursor()
        
        # Obtener TODAS las fincas de la base de datos
        cur.execute("SELECT * FROM plots")
        plots = [dict(row) for row in cur.fetchall()]
        
        return plots

def get_filtered_plots(min_surface=0, max_surface=1000000, query=""):
    """Filtra las fincas unificadas con protección contra valores Nulos (None)"""
    all_available = get_available_plots()
    
    # Aseguramos que la query no sea None
    query_str = (query or "").lower()
    
    filtered = []
    for p in all_available:
        try:
            # 1. Protección para superficie
            sup = float(p.get('m2') if p.get('m2') is not None else 0)
            
            # 2. Protección para Título y Descripción
            titulo = (p.get('title') or "").lower()
            descripcion = (p.get('description') or "").lower()
            
            cumple_sup = min_surface <= sup <= max_surface
            cumple_query = query_str in titulo or query_str in descripcion
            
            if cumple_sup and cumple_query:
                filtered.append(p)
        except Exception as e:
            # Si una finca específica da error, la saltamos pero no rompemos toda la App
            continue
            
    return filtered

def render_featured_plots(plots):
    """Renderiza la sección de fincas destacadas en grid de 3 columnas (2 filas = 6 fincas)."""
    st.header("🏠 Fincas Destacadas")

    if not plots:
        st.info("No hay fincas disponibles con los filtros actuales.")
        return

    # Separar fincas premium
    premium = [p for p in plots if p.get("featured") == 1]
    normal = [p for p in plots if p.get("featured") != 1]

    # Ordenar premium por fecha (más recientes primero)
    premium_sorted = sorted(
        premium,
        key=lambda p: str(p.get("created_at") or ""),
        reverse=True
    )

    # Ordenar normales por fecha
    normal_sorted = sorted(
        normal,
        key=lambda p: str(p.get("created_at") or ""),
        reverse=True
    )

    # Construir lista final: primero premium, luego normales (6 fincas total)
    featured = premium_sorted[:6]

    if len(featured) < 6:
        needed = 6 - len(featured)
        featured += normal_sorted[:needed]

    # Tomar solo las primeras 6 fincas
    featured = featured[:6]

    # Renderizar en grid 3 columnas (2 filas)
    cols = st.columns(3)
    for i, plot in enumerate(featured):
        with cols[i % 3]:
            # Contenedor para la tarjeta de finca
            with st.container():
                # Imagen de la finca
                img_path = get_plot_image_path(plot)
                st.image(img_path, width="stretch", caption=f"{plot['title'][:20]}...")

                # Indicador especial para las 2 primeras fincas (destacadas)
                if i < 2:
                    st.caption("⭐ DESTACADA PREMIUM")

                # Información básica
                st.markdown(f"**📏 {plot.get('m2', 'N/A')} m²**")
                st.markdown(f"**💰 €{plot.get('price', 0):,.0f}**")

                # Botón para ver detalles (mantiene la misma lógica)
                if st.button("Ver Detalles", key=f"featured_{plot['id']}", width="stretch"):
                    set_query_param("selected_plot", plot["id"])
                    st.rerun()

def render_map(plots):
    """Renderiza el mapa interactivo con las fincas."""
    st.header("🗺️ Mapa de Fincas")

    # Limpiar caché para evitar fantasmas
    st.cache_data.clear()

    # Procesar todas las plots, asignando coordenadas por defecto si faltan
    plots_processed = []
    for p in plots:
        plot = p.copy()  # Copia para no modificar el original
        if plot.get('lat') is None or plot.get('lon') is None:
            plot['lat'] = 40.4168  # Madrid por defecto
            plot['lon'] = -3.7038
            plot['approximate_location'] = True
        else:
            plot['approximate_location'] = False
        plots_processed.append(plot)

    if not plots_processed:
        st.info("📍 No hay fincas disponibles para mostrar en el mapa.")
        return

    # Calcular centro del mapa
    lats = [float(p['lat']) for p in plots_processed]
    lons = [float(p['lon']) for p in plots_processed]
    center_lat = sum(lats) / len(lats) if lats else 40.1
    center_lon = sum(lons) / len(lons) if lons else -4.0
    zoom_level = 6 if len(plots_processed) > 1 else 12

    # Crear mapa con Folium
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')

    # Todas las plots en esta lista son disponibles (ya filtradas por get_available_plots)
    for plot in plots_processed:
        lat = float(plot['lat'])
        lon = float(plot['lon'])
        plot_id = plot['id']
        img_path = get_plot_image_path(plot)

        # Todas las fincas en esta lista son disponibles (filtradas previamente)
        icon = folium.Icon(color='blue', icon='home', prefix='fa', icon_color='white')

        # Crear popup HTML con imagen y enlace a detalles
        img_src = get_popup_image_url(plot)  # URL completa o relativa para la imagen
        detail_url = get_plot_detail_url(plot['id'])

        # Botón normal para fincas disponibles
        button_html = f'''
        <a href="{detail_url}" target="_blank"
           style="margin-top:5px; padding:5px 10px; background:#ff4b4b; color:white; text-decoration:none; border-radius:3px; display:inline-block;">
            Ver más detalles
        </a>
        '''

        # Nota de ubicación aproximada si aplica
        location_note = "<small style='color:orange;'>Ubicación aproximada</small><br>" if plot.get('approximate_location') else ""

        popup_html = f'''
        <div style="width:160px; text-align:center;">
            <img src="{img_src}" style="width:100%; border-radius:5px;" alt="Imagen de {plot['title']}">
            <br><b>{plot['title']}</b><br>
            {location_note}
            <small>{plot.get('m2', 'N/A')} m²</small><br>
            {button_html}
        </div>
        '''

        marker = folium.Marker([lat, lon], icon=icon, popup=folium.Popup(popup_html, max_width=250))
        marker.add_to(m)

    # Renderizar mapa
    try:
        st.components.v1.html(m._repr_html_(), height=600)
    except Exception as e:
        st.error(f"No fue posible renderizar el mapa interactivo: {str(e)}")
        # Fallback: mostrar coordenadas como texto
        st.write("**Fincas encontradas:**")
        for plot in plots_processed:
            st.write(f"- {plot.get('title', 'Sin título')}: {plot.get('lat')}, {plot.get('lon')}")

    # Control nativo para navegación
    render_map_navigation(plots)

def render_map_navigation(plots):
    """Renderiza el control de navegación del mapa."""
    st.markdown("---")
    
    # Procesar todas las plots igual que en render_map
    plots_processed = []
    for p in plots:
        plot = p.copy()
        if plot.get('lat') is None or plot.get('lon') is None:
            plot['lat'] = 40.4168
            plot['lon'] = -3.7038
            plot['approximate_location'] = True
        else:
            plot['approximate_location'] = False
        plots_processed.append(plot)
    
    if not plots_processed:
        return

    # Crear opciones para el selectbox
    plot_options = {f"{p['title']} ({p.get('m2', 'N/A')} m²)": p['id'] for p in plots_processed}
    selected_option = st.selectbox(
        "Selecciona una finca del mapa para ver detalles:",
        options=[""] + list(plot_options.keys()),
        key="map_plot_selector_v3"
    )

    if st.button("🔍 IR A LA FICHA DETALLADA DE LA FINCA SELECCIONADA",
               use_container_width=True,
               disabled=not selected_option):
        if selected_option and selected_option in plot_options:
            selected_id = plot_options[selected_option]
            set_query_param("selected_plot", selected_id)

def render_client_panel():
    """Renderiza el panel de cliente cuando hay una transacción completada."""
    if not st.session_state.get("transaction_completed", False):
        return

    st.success("🎉 ¡Transacción completada exitosamente!")
    st.balloons()

    st.markdown("---")

    # Panel de cliente mejorado
    st.subheader("🏠 Panel de Cliente - ARCHIRAPID")
    st.info(f"**✅ Transacción completada:** {st.session_state.get('transaction_type', 'N/A').title()} - ID: {st.session_state.get('transaction_id', 'N/A')}")

    st.markdown("### 🎯 ¿Qué desea hacer ahora?")

    # Opciones principales en cards
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Cree su casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key="go_designer", type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda...")
            st.info("Aquí se abriría el módulo de diseño de vivienda")

    with col2:
        st.markdown("#### 📐 GESTIONAR PROYECTOS")
        st.write("Vea proyectos compatibles con su finca")
        if st.button("📋 Ver Mis Proyectos", key="go_projects", type="primary"):
            st.success("📐 Redirigiendo a Gestión de Proyectos...")
            st.info("Aquí se mostrarían los proyectos disponibles para su finca")

    st.markdown("---")

    # Opciones adicionales
    st.markdown("### 🔧 Opciones Adicionales")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("📊 Ver Transacción", key="view_transaction", use_container_width=True):
            st.info(f"📋 **Detalles de la transacción:**\n"
                   f"- Tipo: {st.session_state.get('transaction_type', 'N/A')}\n"
                   f"- ID: {st.session_state.get('transaction_id', 'N/A')}\n"
                   f"- Cliente: {st.session_state.get('client_name', 'N/A')}\n"
                   f"- Email: {st.session_state.get('client_email', 'N/A')}")

    with col_b:
        if st.button("🏠 Volver al Marketplace", key="back_marketplace"):
            st.success("🏠 Volviendo al marketplace...")
            # Limpiar estado
            keys_to_clear = ["show_client_form", "transaction_completed", "transaction_type",
                           "transaction_id", "client_name", "client_email"]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    with col_c:
        if st.button("📧 Contactar Soporte", key="contact_support"):
            st.info("📧 Contactando con soporte técnico...")
            st.info("Un agente se pondrá en contacto con usted pronto")

def render_projects_section():
    """Renderiza la sección de proyectos arquitectónicos (actualmente desactivada)."""
    st.markdown("---")
    # Temporarily disabled: list_projects() currently raises DB error (no such column: p.characteristics_json)
    # Wrapping the entire projects block in `if False` until DB schema is fixed.
    if False:
        st.header("🏗️ Proyectos Arquitectónicos Disponibles")
        projects = list_projects()
        if projects:
            for proj in projects:
                # Botón visual con thumbnail
                col1, col2 = st.columns([1, 3])
                with col1:
                    fotos = proj['files'].get('fotos', [])
                    thumbnail = f"uploads/{os.path.basename(fotos[0])}" if fotos else "assets/fincas/image1.jpg"
                    st.image(thumbnail, width=100, caption="")
                    if st.button("Ver Proyecto", key=f"view_{proj['id']}"):
                        st.session_state.selected_proj = proj['id']
                with col2:
                    st.subheader(f"{proj['title']}")
                    st.write(f"**Arquitecto:** {proj['architect_name']} ({proj['company'] or 'Independiente'})")
                    st.write(f"**Precio:** €{proj['price']} | **Área:** {proj['area_m2']} m²")
                    st.write(f"**Descripción:** {proj['description'][:100]}...")

        else:
            st.info("No hay proyectos arquitectónicos disponibles aún. ¡Sé el primero en subir uno!")

    # Mostrar detalles del proyecto seleccionado (código desactivado)
    selected_proj_id = st.session_state.get('selected_proj')
    if selected_proj_id:
        # Código de detalles del proyecto aquí (desactivado)
        pass

def main():
    # 1. Verificar si hay una finca seleccionada en la URL
    params = get_query_params() or {}
    selected_plot_local = None
    if params.get("selected_plot"):
        selected_plot_local = params["selected_plot"][0] if isinstance(params["selected_plot"], list) else params["selected_plot"]

    # Si hay una finca seleccionada, mostrar página de detalles y salir
    if selected_plot_local:
        from modules.marketplace.plot_detail import show_plot_detail_page
        show_plot_detail_page(selected_plot_local)
        return

    # Mensaje de bienvenida si está logueado
    if st.session_state.get('logged_in'):
        user_name = st.session_state.get('user_name', st.session_state.get('email', 'Usuario'))
        role = st.session_state.get('role', '')
        if role == 'services':
            panel_name = "Panel de Proveedor"
        elif role == 'architect':
            panel_name = "Panel de Arquitecto"
        elif role == 'admin':
            panel_name = "Intranet"
        else:
            panel_name = "Panel de Cliente"
        
        st.success(f"👋 ¡Hola, {user_name}! | [Ir a Mi {panel_name}](?page={panel_name.replace(' ', '%20')})")

    # CSS del sistema de diseño
    st.markdown("""
    <style>
    .ar-card {
        background: white;
        border-radius: 14px;
        padding: 18px 18px 10px;
        text-align: center;
        box-shadow: 0 3px 16px rgba(0,0,0,0.07);
        border-top: 4px solid;
    }
    .ar-card-owner  { border-top-color: #F5A623; }
    .ar-card-arch   { border-top-color: #2563EB; }
    .ar-card-client { border-top-color: #10B981; }
    .ar-icon { width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;margin:0 auto 10px; }
    .ar-icon-owner  { background:#FFF5E0; }
    .ar-icon-arch   { background:#EEF4FF; }
    .ar-icon-client { background:#ECFDF5; }
    .ar-card-title { font-size:1.05em;font-weight:800;color:#0D1B2A;margin-bottom:5px; }
    .ar-card-text  { font-size:0.85em;color:#64748B;line-height:1.4;margin-bottom:12px; }
    </style>
    <script>
    (function applyButtonColors() {
        var rules = [
            { text: 'Subir mi Finca',              bg: '#F5A623', fg: 'white' },
            { text: 'Mis Proyectos',               bg: '#2563EB', fg: 'white' },
            { text: 'Ver Proyectos',               bg: '#10B981', fg: 'white' },
            { text: 'Mis Favoritos',               bg: '#10B981', fg: 'white' },
            { text: 'Registrarme como Profesional',bg: '#F5A623', fg: '#0D1B2A' },
        ];
        function paint() {
            document.querySelectorAll('button').forEach(function(btn) {
                var t = btn.innerText.trim();
                rules.forEach(function(r) {
                    if (t.startsWith(r.text)) {
                        btn.style.setProperty('background', r.bg, 'important');
                        btn.style.setProperty('color',      r.fg, 'important');
                        btn.style.setProperty('border',     'none', 'important');
                        btn.style.setProperty('border-radius', '10px', 'important');
                        btn.style.setProperty('font-weight', '700', 'important');
                    }
                });
            });
        }
        paint();
        [300, 800, 1500].forEach(function(d){ setTimeout(paint, d); });
        new MutationObserver(paint).observe(document.body, {childList:true, subtree:true});
    })();
    </script>
    """, unsafe_allow_html=True)

    # 3. Tres tarjetas de acceso directo
    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        st.markdown("""
        <div class="ar-card ar-card-owner">
            <div class="ar-icon ar-icon-owner">🏗️</div>
            <div class="ar-card-title">Tengo un Terreno</div>
            <div class="ar-card-text">Publica tu finca y recibe propuestas reales de arquitectos especializados.</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="ar-btn-owner">', unsafe_allow_html=True)
        if st.button("Subir mi Finca →", key="upload_plot", use_container_width=True):
            if st.session_state.get("logged_in") and st.session_state.get("role") == "owner":
                navigate_to("🏠 Propietarios")
            else:
                st.session_state['login_role'] = 'owner'
                st.session_state['viewing_login'] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="ar-card ar-card-arch">
            <div class="ar-icon ar-icon-arch">📐</div>
            <div class="ar-card-title">Soy Arquitecto</div>
            <div class="ar-card-text">Comparte proyectos ejecutables y conecta con clientes de forma profesional.</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="ar-btn-arch">', unsafe_allow_html=True)
        if st.button("Mis Proyectos →", key="architect_portal", use_container_width=True):
            navigate_to("Arquitectos (Marketplace)")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="ar-card ar-card-client">
            <div class="ar-icon ar-icon-client">🏡</div>
            <div class="ar-card-title">Busco Casa</div>
            <div class="ar-card-text">Explora proyectos disponibles o diseña tu casa con IA en minutos.</div>
        </div>
        """, unsafe_allow_html=True)
        logged_in = st.session_state.get("logged_in", False)
        email = st.session_state.get("email", "")
        st.markdown('<div class="ar-btn-client">', unsafe_allow_html=True)
        if logged_in and email:
            if st.button("Mis Favoritos →", key="browse_projects", use_container_width=True):
                navigate_to("👤 Panel de Cliente")
        else:
            if st.button("Ver Proyectos →", key="browse_projects", use_container_width=True):
                st.info("¡Bienvenido! Explora todos los proyectos abajo. Para guardar favoritos o contactar arquitectos, regístrate.")
                if st.button("📝 Registrarme", key="register_from_marketplace"):
                    navigate_to("Registro de Usuario")
        st.markdown('</div>', unsafe_allow_html=True)

    # Banner de profesionales (antes al fondo de app.py)
    st.markdown("<br>", unsafe_allow_html=True)
    col_pro1, col_pro2, col_pro3 = st.columns([3, 1, 1], gap="medium")
    with col_pro1:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0D1B2A 0%,#1B3558 100%);border-radius:14px;padding:20px 26px;">
            <div style="font-size:1.1em;font-weight:800;color:white;margin-bottom:5px;">🛠️ ¿Eres profesional de la construcción o reformas?</div>
            <div style="color:#94B8D4;font-size:0.9em;">Únete a nuestra red de proveedores y conecta con clientes que necesitan tus servicios.</div>
        </div>
        """, unsafe_allow_html=True)
    with col_pro2:
        st.markdown('<div class="ar-btn-pro" style="padding-top:6px">', unsafe_allow_html=True)
        if st.button("Registrarme como Profesional", key="register_professional", use_container_width=True):
            st.session_state['selected_page'] = "📝 Registro de Proveedor de Servicios"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col_pro3:
        st.markdown('<div class="ar-btn-search" style="padding-top:6px">', unsafe_allow_html=True)
        if st.button("🛠️ Buscar Profesionales", key="search_professionals", use_container_width=True):
            from modules.marketplace import service_providers
            service_providers.show_services_marketplace()
        st.markdown('</div>', unsafe_allow_html=True)

    # 4. Marketplace de proyectos (siempre visible debajo)
    st.markdown("---")

    # Configurar filtros del sidebar
    min_surface, max_surface, search_query = setup_filters()

    # Obtener fincas filtradas
    plots = get_filtered_plots(min_surface, max_surface, search_query)

    # Layout principal: mapa ocupa todo el ancho
    render_map(plots)

    # Sección de fincas destacadas debajo del mapa
    render_featured_plots(plots)

    # Sección de proyectos adicionales
    render_projects_section()

    # Limpiar caché para asegurar sincronización
    st.cache_data.clear()