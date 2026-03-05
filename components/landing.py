import streamlit as st

st.markdown("""
<style>
.role-container {
    background: linear-gradient(135deg, #d4e4ff 0%, #e8f1ff 100%);
    padding: 60px 30px;
    border-radius: 20px;
    margin-top: 20px;
}

.role-card {
    background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
    border: 1px solid #d0ddff;
    border-radius: 16px;
    padding: 35px 25px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.role-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 28px rgba(0,0,0,0.12);
}

.card-icon {
    font-size: 56px;
    margin-bottom: 18px;
}

.card-title {
    font-size: 1.6em;
    font-weight: 800;
    color: #003366;
    margin-bottom: 12px;
}

.card-text {
    font-size: 1.05em;
    color: #333;
    line-height: 1.4;
    margin-bottom: 25px;
}

.role-btn > button {
    background-color: #0b5cff !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 12px 18px !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0 2px 6px rgba(11, 92, 255, 0.3) !important;
}

.role-btn > button:hover {
    background-color: #0846c3 !important;
}
</style>
""", unsafe_allow_html=True)

def render_landing():
    # Logo pequeño en lugar del header grande
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        try:
            st.image("assets/branding/logo.png", width=200)
        except:
            st.markdown("### 🏗️ ARCHIRAPID")
    
    st.markdown("---")
    
    st.markdown('<div class="role-container">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="role-card">
            <div class="card-icon">🏗️</div>
            <div class="card-title">Tengo un Terreno</div>
            <div class="card-text">
                Publica tu finca y recibe propuestas reales de arquitectos especializados.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="role-btn">', unsafe_allow_html=True)
        if st.button("Subir Mi Finca", key="btn_prop"):
            st.session_state['login_role'] = 'owner'
            st.session_state['viewing_login'] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="role-card">
            <div class="card-icon">📐</div>
            <div class="card-title">Soy Arquitecto</div>
            <div class="card-text">
                Comparte tus proyectos ejecutables y conecta con clientes reales de forma profesional.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="role-btn">', unsafe_allow_html=True)
        if st.button("Acceso Arquitectos", key="btn_arq"):
            st.query_params["page"] = "Arquitectos (Marketplace)"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="role-card">
            <div class="card-icon">🏡</div>
            <div class="card-title">Busco Casa</div>
            <div class="card-text">
                Explora fincas, proyectos compatibles o diseña tu casa con IA en minutos.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="role-btn">', unsafe_allow_html=True)
        if st.button("Acceso Clientes", key="btn_cli"):
            st.query_params["page"] = "👤 Panel de Cliente"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    
    # Sección principal: Mapa y Buscador
    st.subheader("🗺️ Explora Fincas Disponibles en España y Portugal")
    
    # Buscador integrado
    from src import db
    
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
        
        # Obtener todas las fincas
        db.ensure_tables()
        plots = list_published_plots()
        
        # Aplicar filtros sobre todas las fincas
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
        
        # Ahora filtrar por coordenadas para el mapa
        plots_with_coords = [p for p in plots if p.get('lat') is not None and p.get('lon') is not None]
        
        if plots_with_coords:
            # Centrar mapa en España/Portugal
            # Centro aproximado entre España y Portugal
            center_lat = 40.0  # Centro de la Península Ibérica
            center_lon = -4.0
            zoom_level = 5  # Vista que cubre España y Portugal
            
            # Si hay fincas, calcular centro basado en ellas
            if len(plots_with_coords) > 0:
                lats = [float(p['lat']) for p in plots_with_coords]
                lons = [float(p['lon']) for p in plots_with_coords]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)
                zoom_level = 6 if len(plots_with_coords) > 1 else 10
            
            # Crear mapa (MÁS ALTO)
            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            
            # Mostrar detalles de cada finca usando FincaMVP y visualización avanzada
            from src.models.finca import FincaMVP
            from src.solar_virtual_svg import mostrar_solar_virtual_svg
            import folium
            import streamlit.components.v1 as components
            for p in plots_with_coords:
                # 1. Convertir dict a FincaMVP
                finca = FincaMVP.desde_dict(p)
                # 2. Mostrar mapa de la finca
                m_finca = folium.Map(location=[finca.lat, finca.lon], zoom_start=15, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
                
                # Verificar si la finca está vendida/reservada para definir el color del marcador
                from src import db
                conn_check = db.get_conn()
                cursor_check = conn_check.cursor()
                cursor_check.execute("SELECT 1 FROM reservations WHERE plot_id = ?", (p.get('id'),))
                is_sold = cursor_check.fetchone() is not None
                conn_check.close()
                
                # Definir icono según disponibilidad
                if is_sold:
                    # FINCA VENDIDA/RESERVADA: Color ROJO con icono de prohibido
                    icon = folium.Icon(color='red', icon='ban', prefix='fa', icon_color='white')
                else:
                    # FINCA DISPONIBLE: Color AZUL con icono de casa
                    icon = folium.Icon(color='blue', icon='home', prefix='fa', icon_color='white')
                
                folium.Marker([finca.lat, finca.lon], icon=icon).add_to(m_finca)
                st.markdown(f"### {finca.titulo if hasattr(finca, 'titulo') else p.get('title', 'Finca')}")
                components.html(m_finca._repr_html_(), height=300)
                # 3. Mostrar superficie edificable y solar_virtual
                st.write(f"**Superficie edificable:** {finca.superficie_edificable:.2f} m²")
                st.write(f"**Solar virtual:** {finca.solar_virtual}")
                mostrar_solar_virtual_svg(finca)
                st.markdown("---")
        else:
            # Mapa sin marcadores centrado en España/Portugal
            m = folium.Map(location=[40.0, -4.0], zoom_start=5, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            components.html(m._repr_html_(), height=700)
            st.info("📍 No se encontraron fincas con los filtros seleccionados. Intenta cambiar los criterios de búsqueda.")
    except Exception as e:
        # Log exception details for debugging to a file and show fallback map
        try:
            import traceback
            Path('tmp').mkdir(exist_ok=True)
            with open('tmp/map_error.txt', 'w', encoding='utf-8') as f:
                f.write('Exception in components/landing.py map render:\n')
                traceback.print_exc(file=f)
        except Exception:
            pass
        # Fallback simple map
        import folium
        import streamlit.components.v1 as components
        m = folium.Map(location=[40.0, -4.0], zoom_start=5, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
        components.html(m._repr_html_(), height=700)
        st.warning("⚠️ Error cargando el mapa. Por favor, recarga la página.")

    st.markdown("---")
    
    # Footer con acceso corporativo sutil
    col_foot1, col_foot2, col_foot3 = st.columns([3, 1, 1])
    with col_foot3:
        if st.button("🔐 Admin", type="secondary"):
            st.session_state['role'] = 'admin'
            st.rerun()

