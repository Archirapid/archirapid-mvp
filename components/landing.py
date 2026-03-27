import streamlit as st

st.markdown("""
<style>
/* ===== ARCHIRAPID DESIGN SYSTEM ===== */

.ar-hero-brand {
    font-size: 2.4em;
    font-weight: 900;
    color: #0D1B2A;
    letter-spacing: -1px;
    line-height: 1.1;
    margin: 0;
}
.ar-hero-sub {
    font-size: 1.05em;
    color: #64748B;
    margin-top: 6px;
    font-weight: 400;
}
.ar-hero-badge {
    display: inline-block;
    background: rgba(37,99,235,0.1);
    color: #2563EB;
    border: 1px solid rgba(37,99,235,0.2);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75em;
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* Cards */
.ar-card {
    background: white;
    border-radius: 18px;
    padding: 30px 22px 16px;
    text-align: center;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    border-top: 4px solid;
    height: 100%;
}
.ar-card-owner  { border-top-color: #F5A623; }
.ar-card-arch   { border-top-color: #2563EB; }
.ar-card-client { border-top-color: #10B981; }

.ar-icon {
    width: 60px; height: 60px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 26px;
    margin: 0 auto 16px;
}
.ar-icon-owner  { background: #FFF5E0; }
.ar-icon-arch   { background: #EEF4FF; }
.ar-icon-client { background: #ECFDF5; }

.ar-card-title {
    font-size: 1.25em;
    font-weight: 800;
    color: #0D1B2A;
    margin-bottom: 8px;
}
.ar-card-text {
    font-size: 0.92em;
    color: #64748B;
    line-height: 1.5;
    margin-bottom: 20px;
}

/* Button styling */
.ar-btn-owner  > button { background: #F5A623 !important; color: white !important; border: none !important; border-radius: 10px !important; font-weight: 700 !important; }
.ar-btn-arch   > button { background: #2563EB !important; color: white !important; border: none !important; border-radius: 10px !important; font-weight: 700 !important; }
.ar-btn-client > button { background: #10B981 !important; color: white !important; border: none !important; border-radius: 10px !important; font-weight: 700 !important; }
.ar-btn-pro    > button { background: #F5A623 !important; color: #0D1B2A !important; border: none !important; border-radius: 10px !important; font-weight: 700 !important; }
.ar-btn-search > button { background: transparent !important; color: white !important; border: 1px solid rgba(255,255,255,0.4) !important; border-radius: 10px !important; font-weight: 600 !important; }
.ar-btn-admin  > button { background: transparent !important; color: #94A3B8 !important; border: none !important; font-size: 0.8em !important; padding: 4px 8px !important; }
</style>
""", unsafe_allow_html=True)


def render_landing():
    # ===== HEADER =====
    col_logo, col_title, col_acc = st.columns([1, 4, 1])
    with col_logo:
        try:
            st.image("assets/branding/logo.png", width=110)
        except:
            st.markdown("**🏗️**")
    with col_title:
        st.markdown("""
        <div style="padding-top:8px">
            <div class="ar-hero-badge">IA · CATASTRO · ARQUITECTURA</div>
            <div class="ar-hero-brand">Del terreno a tu casa</div>
            <div class="ar-hero-sub">Conectamos propietarios, arquitectos y clientes con tecnología e inteligencia artificial</div>
        </div>
        """, unsafe_allow_html=True)
    with col_acc:
        st.markdown('<div style="padding-top:20px">', unsafe_allow_html=True)
        if st.button("🔑 Acceder", key="btn_acceder_header"):
            st.session_state['show_role_selector'] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr style='margin:20px 0 24px;border:none;border-top:1px solid #E2E8F0'>", unsafe_allow_html=True)

    # ===== 3 ACCESS CARDS =====
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
        if st.button("Subir Mi Finca →", key="btn_prop", use_container_width=True):
            st.session_state['login_role'] = 'owner'
            st.session_state['viewing_login'] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="ar-card ar-card-arch">
            <div class="ar-icon ar-icon-arch">📐</div>
            <div class="ar-card-title">Soy Arquitecto</div>
            <div class="ar-card-text">Comparte proyectos ejecutables y conecta con clientes reales de forma profesional.</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="ar-btn-arch">', unsafe_allow_html=True)
        if st.button("Acceso Arquitectos →", key="btn_arq", use_container_width=True):
            st.query_params["page"] = "Arquitectos (Marketplace)"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="ar-card ar-card-client">
            <div class="ar-icon ar-icon-client">🏡</div>
            <div class="ar-card-title">Busco Casa</div>
            <div class="ar-card-text">Explora fincas, proyectos compatibles o diseña tu casa con IA en minutos.</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="ar-btn-client">', unsafe_allow_html=True)
        if st.button("Ver Proyectos →", key="btn_cli", use_container_width=True):
            st.query_params["page"] = "👤 Panel de Cliente"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ===== PROFESSIONAL BANNER (formerly at bottom of app.py) =====
    st.markdown("<br>", unsafe_allow_html=True)
    col_pro1, col_pro2, col_pro3 = st.columns([3, 1, 1], gap="medium")
    with col_pro1:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0D1B2A 0%,#1B3558 100%);border-radius:14px;padding:22px 28px;">
            <div style="font-size:1.15em;font-weight:800;color:white;margin-bottom:5px;">🛠️ ¿Eres profesional de la construcción o reformas?</div>
            <div style="color:#94B8D4;font-size:0.92em;">Únete a nuestra red de proveedores y conecta con clientes que necesitan tus servicios.</div>
        </div>
        """, unsafe_allow_html=True)
    with col_pro2:
        st.markdown('<div class="ar-btn-pro" style="padding-top:8px">', unsafe_allow_html=True)
        if st.button("Registrarme como Profesional", key="register_professional", use_container_width=True):
            st.session_state['selected_page'] = "📝 Registro de Proveedor de Servicios"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col_pro3:
        st.markdown('<div class="ar-btn-search" style="padding-top:8px">', unsafe_allow_html=True)
        if st.button("🛠️ Buscar Profesionales", key="search_professionals", use_container_width=True):
            from modules.marketplace import service_providers
            service_providers.show_services_marketplace()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr style='margin:24px 0 16px;border:none;border-top:1px solid #E2E8F0'>", unsafe_allow_html=True)

    # ===== MAPA Y BUSCADOR (lógica intacta) =====
    st.subheader("🗺️ Explora Fincas Disponibles en España y Portugal")

    col_search1, col_search2, col_search3 = st.columns([2, 1, 1])
    with col_search1:
        search_query = st.text_input("🔍 Buscar por dirección, provincia o referencia catastral",
                                     placeholder="Ej: Madrid, Barcelona, Camilo Jose Cela...",
                                     key="home_search")
    with col_search2:
        provincia_filter = st.selectbox("Provincia",
                                       ["Todas", "Madrid", "Barcelona", "Valencia", "Sevilla", "Málaga", "Lisboa", "Porto"],
                                       key="home_province")
    with col_search3:
        min_price = st.number_input("Precio min (€)", min_value=0, value=0, step=10000, key="home_min_price")
        max_price = st.number_input("Precio max (€)", min_value=0, value=500000, step=10000, key="home_max_price")

    try:
        from modules.marketplace.utils import list_published_plots
        import folium
        import streamlit.components.v1 as components

        plots = list_published_plots()

        if provincia_filter and provincia_filter != "Todas":
            selected_province = provincia_filter.lower()
            plots = [p for p in plots
                    if selected_province in (p.get('province') or '').lower()]

        if search_query:
            plots = [p for p in plots
                    if search_query.lower() in (p.get('title', '') + ' ' +
                                               p.get('address', '') + ' ' +
                                               str(p.get('catastral_ref', ''))).lower()]

        if min_price > 0 or max_price > 0:
            filtered_plots = []
            for p in plots:
                price = p.get('price') or 0
                if min_price > 0 and price < min_price:
                    continue
                if max_price > 0 and price > max_price:
                    continue
                filtered_plots.append(p)
            plots = filtered_plots

        plots_with_coords = [p for p in plots if p.get('lat') is not None and p.get('lon') is not None]

        if plots_with_coords:
            center_lat = 40.0
            center_lon = -4.0
            zoom_level = 5

            if len(plots_with_coords) > 0:
                lats = [float(p['lat']) for p in plots_with_coords]
                lons = [float(p['lon']) for p in plots_with_coords]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)
                zoom_level = 6 if len(plots_with_coords) > 1 else 10

            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')

            from src.models.finca import FincaMVP
            from src.solar_virtual_svg import mostrar_solar_virtual_svg
            for p in plots_with_coords:
                finca = FincaMVP.desde_dict(p)
                m_finca = folium.Map(location=[finca.lat, finca.lon], zoom_start=15, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')

                from src import db as db_check
                conn_check = db_check.get_conn()
                cursor_check = conn_check.cursor()
                cursor_check.execute("SELECT 1 FROM reservations WHERE plot_id = ?", (p.get('id'),))
                is_sold = cursor_check.fetchone() is not None
                conn_check.close()

                if is_sold:
                    icon = folium.Icon(color='red', icon='ban', prefix='fa', icon_color='white')
                else:
                    icon = folium.Icon(color='blue', icon='home', prefix='fa', icon_color='white')

                folium.Marker([finca.lat, finca.lon], icon=icon).add_to(m_finca)
                st.markdown(f"### {finca.titulo if hasattr(finca, 'titulo') else p.get('title', 'Finca')}")
                components.html(m_finca._repr_html_(), height=300)
                st.write(f"**Superficie edificable:** {finca.superficie_edificable:.2f} m²")
                st.write(f"**Solar virtual:** {finca.solar_virtual}")
                mostrar_solar_virtual_svg(finca)
                st.markdown("---")
        else:
            m = folium.Map(location=[40.0, -4.0], zoom_start=5, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            components.html(m._repr_html_(), height=700)
            st.info("📍 No se encontraron fincas con los filtros seleccionados. Intenta cambiar los criterios de búsqueda.")
    except Exception as e:
        try:
            import traceback
            from pathlib import Path
            Path('tmp').mkdir(exist_ok=True)
            with open('tmp/map_error.txt', 'w', encoding='utf-8') as f:
                f.write('Exception in components/landing.py map render:\n')
                traceback.print_exc(file=f)
        except Exception:
            pass
        import folium
        import streamlit.components.v1 as components
        m = folium.Map(location=[40.0, -4.0], zoom_start=5, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
        components.html(m._repr_html_(), height=700)
        st.warning("⚠️ Error cargando el mapa. Por favor, recarga la página.")

    st.markdown("<hr style='margin:24px 0 16px;border:none;border-top:1px solid #E2E8F0'>", unsafe_allow_html=True)

    # Footer con acceso admin sutil
    col_foot1, col_foot2, col_foot3 = st.columns([3, 1, 1])
    with col_foot3:
        st.markdown('<div class="ar-btn-admin">', unsafe_allow_html=True)
        if st.button("🔐 Admin", type="secondary"):
            st.session_state['selected_page'] = "Intranet"
            st.session_state['show_role_selector'] = False
            st.session_state['viewing_login'] = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
