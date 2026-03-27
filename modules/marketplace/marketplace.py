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
    # MLS fincas store resolved path directly in image_path
    if plot.get("_is_mls") and plot.get("image_path"):
        p = plot["image_path"].replace("\\", "/")
        if os.path.exists(p):
            return p

    if plot.get('photo_paths'):
        try:
            paths = json.loads(plot['photo_paths'])
            if paths and isinstance(paths, list):
                # Supabase Storage URL — devolver directamente
                if isinstance(paths[0], str) and paths[0].startswith("http"):
                    return paths[0]
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

def get_popup_image_b64(plot):
    """
    Devuelve un data URI base64 de la imagen de la finca para incrustar
    directamente en el HTML del popup de Folium (los file:// URLs son bloqueados
    por los navegadores en iframes).
    """
    import base64 as _b64
    rel_path = get_plot_image_path(plot)
    rel_path = rel_path.lstrip('/').replace('\\', '/')
    abs_path = Path(rel_path).resolve()

    if not abs_path.exists():
        abs_path = Path("assets/branding/logo.png").resolve()

    try:
        with open(abs_path, 'rb') as f:
            data = _b64.b64encode(f.read()).decode()
        ext = abs_path.suffix.lower().lstrip('.')
        mime = 'image/png' if ext == 'png' else ('image/gif' if ext == 'gif' else 'image/jpeg')
        return f"data:{mime};base64,{data}"
    except Exception:
        return ""

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

def _render_plot_card(plot, key_prefix, show_premium_badge=False):
    """Renderiza una tarjeta de finca uniforme (plots propios y MLS)."""
    import base64 as _b64
    is_mls = plot.get("_is_mls", False)
    img_path = get_plot_image_path(plot)
    st.markdown('<style>.finca-badge{display:inline-block;background:#FFF5E0;color:#F5A623;border:1px solid #F5A623;border-radius:8px;font-size:0.68em;font-weight:700;padding:1px 7px;margin-bottom:4px;}.mls-badge{display:inline-block;background:#F59E0B;color:#fff;border-radius:6px;font-size:0.65em;font-weight:800;padding:2px 7px;letter-spacing:1px;margin-bottom:4px;}</style>', unsafe_allow_html=True)
    # Imagen con altura fija; para MLS superponemos badge naranja
    img_html = ""
    try:
        with open(img_path, 'rb') as f:
            b64 = _b64.b64encode(f.read()).decode()
        ext = str(img_path).rsplit('.', 1)[-1].lower()
        mime = 'image/png' if ext == 'png' else ('image/gif' if ext == 'gif' else 'image/jpeg')
        mls_overlay = (
            '<div style="position:absolute;top:7px;left:7px;background:#F59E0B;color:#fff;'
            'border-radius:5px;font-size:0.62em;font-weight:900;padding:2px 7px;'
            'letter-spacing:1.5px;pointer-events:none;">MLS</div>'
            if is_mls else ""
        )
        img_html = (
            f'<div style="position:relative;width:100%;">'
            f'<img src="data:{mime};base64,{b64}" '
            f'style="width:100%;height:160px;object-fit:cover;border-radius:10px;display:block;">'
            f'{mls_overlay}'
            f'</div>'
        )
    except Exception:
        img_html = ""
    if img_html:
        st.markdown(img_html, unsafe_allow_html=True)
    else:
        st.image(img_path, use_container_width=True)

    if show_premium_badge:
        st.markdown('<span class="finca-badge">⭐ DESTACADA</span>', unsafe_allow_html=True)

    title = plot.get('title') or "Sin título"
    st.markdown(f"**{title[:28]}{'…' if len(title)>28 else ''}**")
    st.caption(f"📏 {plot.get('m2','N/A')} m²  ·  💰 €{float(plot.get('price',0) or 0):,.0f}")

    if is_mls:
        mls_id = plot.get("_mls_id") or plot.get("id")
        if st.button("Ver Detalles", key=f"{key_prefix}_mls_{mls_id}", use_container_width=True):
            set_query_param("mls_ficha", str(mls_id))
            st.rerun()
        # MLS fincas no participan en el comparador nativo (distintos campos)
        return

    if st.button("Ver Detalles", key=f"{key_prefix}_{plot['id']}", use_container_width=True):
        set_query_param("selected_plot", plot["id"])
        st.rerun()
    # ── Botón comparar ────────────────────────────────────────────────────────
    if "compare_plots" not in st.session_state:
        st.session_state.compare_plots = []
    pid = plot["id"]
    in_compare = pid in st.session_state.compare_plots
    btn_label = "✓ En comparativa" if in_compare else "＋ Comparar"
    btn_type  = "secondary"
    if st.button(btn_label, key=f"cmp_{key_prefix}_{pid}", use_container_width=True, type=btn_type):
        if in_compare:
            st.session_state.compare_plots.remove(pid)
        elif len(st.session_state.compare_plots) < 3:
            st.session_state.compare_plots.append(pid)
        else:
            st.toast("Máximo 3 fincas en la comparativa. Quita una primero.", icon="⚠️")
        st.rerun()


def render_comparador(plots_all: list):
    """Muestra la tabla comparativa de las fincas seleccionadas (2-3)."""
    ids = st.session_state.get("compare_plots", [])
    if len(ids) < 2:
        return
    selected = [p for p in plots_all if p["id"] in ids]
    if len(selected) < 2:
        return

    import base64 as _b64

    st.markdown("---")
    st.markdown("### ⚖️ Comparativa de fincas seleccionadas")

    # Cabecera: imagen + título
    header_cols = st.columns(len(selected))
    for i, plot in enumerate(selected):
        with header_cols[i]:
            img_path = get_plot_image_path(plot)
            try:
                with open(img_path, "rb") as f:
                    b64 = _b64.b64encode(f.read()).decode()
                ext = str(img_path).rsplit(".", 1)[-1].lower()
                mime = "image/png" if ext == "png" else "image/jpeg"
                st.markdown(
                    f'<img src="data:{mime};base64,{b64}" '
                    f'style="width:100%;height:140px;object-fit:cover;border-radius:10px;">',
                    unsafe_allow_html=True
                )
            except Exception:
                st.image(img_path, use_container_width=True)
            st.markdown(f"**{plot.get('title', '—')}**")

    # Filas de datos
    def _row(label, fn):
        row_cols = st.columns(len(selected))
        for i, plot in enumerate(selected):
            with row_cols[i]:
                try:
                    val = fn(plot)
                except Exception:
                    val = "—"
                st.markdown(
                    f'<div style="background:rgba(30,58,95,0.3);border-radius:6px;'
                    f'padding:7px 10px;margin-bottom:4px;">'
                    f'<div style="color:#94A3B8;font-size:11px;">{label}</div>'
                    f'<div style="color:#F8FAFC;font-weight:600;font-size:14px;">{val}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    _row("💰 Precio",         lambda p: f"€{float(p.get('price',0)):,.0f}")
    _row("📏 Superficie",     lambda p: f"{p.get('m2','—')} m²")
    _row("€ / m²",            lambda p: f"€{float(p.get('price',0))/max(float(p.get('m2',1) or 1),1):,.0f}/m²")
    _row("📐 Edificable",     lambda p: f"{p.get('superficie_edificable','—')} m²")
    _row("📍 Provincia",      lambda p: p.get('province') or p.get('locality') or "—")
    _row("✅ Estado",         lambda p: (p.get('status') or "—").capitalize())
    _row("🏗️ Referencia cat.",lambda p: p.get('catastral_ref') or "—")

    # CTAs
    cta_cols = st.columns(len(selected))
    for i, plot in enumerate(selected):
        with cta_cols[i]:
            if st.button("Ver Detalles →", key=f"cmp_detail_{plot['id']}", use_container_width=True, type="primary"):
                set_query_param("selected_plot", plot["id"])
                st.rerun()

    # Limpiar comparativa
    st.markdown("")
    if st.button("🗑️ Limpiar comparativa", key="clear_compare"):
        st.session_state.compare_plots = []
        st.rerun()


def _get_mls_fincas_for_grid():
    """Fetch MLS fincas (publicadas) and normalize to plots-dict shape."""
    import sqlite3 as _sq3
    from modules.marketplace.utils import DB_PATH
    try:
        conn = _sq3.connect(DB_PATH, timeout=15)
        conn.row_factory = _sq3.Row
        cur = conn.cursor()
        # Minimal columns — no 'featured' to avoid OperationalError if missing
        cur.execute("""
            SELECT id, titulo, descripcion_publica, precio, superficie_m2,
                   catastro_lat, catastro_lon, created_at, image_paths
            FROM fincas_mls
            WHERE estado IN ('publicada','reservada')
            ORDER BY created_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception:
        return []

    result = []
    for r in rows:
        img_path = None
        try:
            imgs = json.loads(r.get("image_paths") or "[]")
            for _p in imgs:
                if _p:
                    _p = str(_p).replace("\\", "/")
                    if not _p.startswith("uploads/"):
                        _p = "uploads/" + _p
                    if os.path.exists(_p):
                        img_path = _p
                        break
        except Exception:
            pass
        result.append({
            "id":          f"mls_{r['id']}",
            "_mls_id":     r["id"],
            "_is_mls":     True,
            "title":       r.get("titulo") or "Finca MLS",
            "description": r.get("descripcion_publica") or "",
            "m2":          r.get("superficie_m2"),
            "price":       r.get("precio") or 0,
            "lat":         r.get("catastro_lat"),
            "lon":         r.get("catastro_lon"),
            "featured":    0,          # MLS no usa destacadas por ahora
            "created_at":  r.get("created_at") or "",
            "image_path":  img_path,
        })
    return result


def render_featured_plots(plots):
    """Grid 5 columnas: fila destacadas (premium) + fila recientes — incluye MLS."""
    # Merge regular plots + MLS fincas
    mls_fincas = _get_mls_fincas_for_grid()
    all_plots = list(plots) + mls_fincas

    if not all_plots:
        st.info("No hay fincas disponibles con los filtros actuales.")
        return

    # Separar premium y normales (ambas fuentes)
    premium = sorted([p for p in all_plots if p.get("featured") == 1],
                     key=lambda p: str(p.get("created_at") or ""), reverse=True)
    normal  = sorted([p for p in all_plots if p.get("featured") != 1],
                     key=lambda p: str(p.get("created_at") or ""), reverse=True)

    N = 5  # columnas

    # Fila 1: Destacadas (solo si hay al menos una)
    if premium:
        st.markdown("#### ⭐ Fincas Destacadas")
        cols = st.columns(N)
        for i, plot in enumerate(premium[:N]):
            with cols[i]:
                _render_plot_card(plot, "prem", show_premium_badge=True)

    # Fila 2 (y fila 3 si hay): Recientes — máximo 2 filas × 5 = 10 tarjetas
    st.markdown("#### 🏠 Fincas Disponibles")
    to_show = normal[:N * 2]
    if not to_show:
        st.info("Sube fincas para verlas aquí.")
        return
    # Renderizar en filas reales de 5 columnas
    for row_start in range(0, len(to_show), N):
        row_plots = to_show[row_start:row_start + N]
        cols = st.columns(N)
        for i, plot in enumerate(row_plots):
            with cols[i]:
                _render_plot_card(plot, f"norm_r{row_start}", show_premium_badge=False)

    # ── Comparador (aparece solo cuando hay 2-3 seleccionadas) ───────────────
    _n_cmp = len(st.session_state.get("compare_plots", []))
    if _n_cmp >= 2:
        render_comparador(plots)
    elif _n_cmp == 1:
        st.caption("＋ Selecciona al menos una finca más para comparar.")

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

    for plot in plots_processed:
        lat = float(plot['lat'])
        lon = float(plot['lon'])
        _pid = plot['id']

        icon = folium.Icon(color='blue', icon='home', prefix='fa', icon_color='white')
        img_src = get_popup_image_b64(plot)
        location_note = "<small style='color:orange;'>Ubicación aproximada</small><br>" if plot.get('approximate_location') else ""
        img_tag = f'<img src="{img_src}" style="width:100%;height:100px;object-fit:cover;border-radius:5px;display:block;margin-bottom:6px;" alt="">' if img_src else ''
        popup_html = f'''
        <div style="width:180px;font-family:sans-serif;font-size:13px;">
            {img_tag}
            <b style="font-size:13px;">{plot['title']}</b><br>
            {location_note}
            <span style="color:#64748B;">{plot.get('m2', 'N/A')} m²</span><br>
            <a href="/?selected_plot={_pid}" target="_blank"
               style="margin-top:6px;padding:5px 10px;background:#ff4b4b;color:white;
                      text-decoration:none;border-radius:3px;display:inline-block;font-weight:600;">
                Ver más detalles
            </a>
        </div>
        '''
        marker = folium.Marker([lat, lon], icon=icon,
                               popup=folium.Popup(popup_html, max_width=250),
                               tooltip=plot['title'])
        marker.add_to(m)

    # ── ArchiRapid MLS: pins naranjas ─────────────────────────────────────────
    try:
        from modules.mls.mls_mapa import (
            get_fincas_mls_para_mapa,
            add_mls_markers_to_map,
        )
        add_mls_markers_to_map(m, get_fincas_mls_para_mapa())
    except Exception:
        pass  # MLS nunca interrumpe el mapa azul
    # ──────────────────────────────────────────────────────────────────────────

    # Renderizar mapa (srcdoc iframe: URLs relativas resuelven contra el dominio padre)
    try:
        st.components.v1.html(m._repr_html_(), height=600)
    except Exception as e:
        st.error(f"No fue posible renderizar el mapa interactivo: {str(e)}")

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

    # CSS/JS de estilos — al final para no generar espacio fantasma antes del mapa
    # MutationObserver + setTimeout garantizan que pinta los botones aunque se inyecte tarde
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

    # Limpiar caché para asegurar sincronización
    st.cache_data.clear()