import streamlit as st
import json
import os
from dotenv import load_dotenv
from groq import Groq

from .data_model import create_example_design, HouseDesign, Plot, RoomType, RoomInstance

def main():
    # ============================================
    # 🔗 CONEXIÓN CON DATOS DE LA FINCA COMPRADA
    # ============================================
    
    # Obtener ID de la finca si viene del panel de cliente
    design_plot_id = st.session_state.get("design_plot_id")
    
    if design_plot_id:
        # Consultar datos de la finca en la BD
        try:
            from modules.marketplace.utils import db_conn
            conn = db_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, catastral_ref, m2, superficie_edificable, 
                       lat, lon, owner_email
                FROM plots 
                WHERE id = ?
            """, (design_plot_id,))
            
            plot_row = cursor.fetchone()
            conn.close()
            
            if plot_row:
                # Guardar datos de la parcela en session_state
                st.session_state["design_plot_data"] = {
                    'id': plot_row[0],
                    'title': plot_row[1],
                    'catastral_ref': plot_row[2],
                    'total_m2': plot_row[3] or 0,
                    'buildable_m2': (plot_row[3] * 0.33) if plot_row[3] else 0,
                    'lat': plot_row[5],
                    'lon': plot_row[6],
                    'owner_email': plot_row[7]
                }
                
                # Pre-configurar superficie objetivo según edificabilidad
                if "ai_house_requirements" not in st.session_state:
                    max_buildable = st.session_state["design_plot_data"]['buildable_m2']
                    st.session_state["ai_house_requirements"] = {
                        "target_area_m2": min(120.0, max_buildable),  # 120m² o el máximo edificable
                        "max_buildable_m2": max_buildable,  # NUEVO: límite máximo
                        "budget_limit": None,
                        "bedrooms": 3,
                        "bathrooms": 2,
                        "wants_pool": False,
                        "wants_porch": True,
                        "wants_garage": False,
                        "wants_outhouse": False,
                        "max_floors": 1,
                        "style": "moderna",
                        "materials": ["hormigón"],
                        "notes": "",
                        "orientation": "Sur",
                        "roof_type": "A dos aguas",
                        "energy_rating": "B",
                        "accessibility": False,
                        "sustainable_materials": []
                    }
            else:
                st.warning("⚠️ No se encontraron datos de la finca. Usando valores por defecto.")
        
        except Exception as e:
            st.error(f"❌ Error cargando datos de la finca: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # ============================================
    
    # Inicializar el paso si no existe
    if "ai_house_step" not in st.session_state:
        st.session_state["ai_house_step"] = 1
    
    ai_house_step = st.session_state["ai_house_step"]
    
    # Título principal
    st.title("🏠 Diseñador de Vivienda con IA (MVP) v2.1 🔧")
    
    # Mostrar paso actual
    st.subheader(f"Paso {ai_house_step} de 3")
    
    # Llamar a la función correspondiente según el paso
    if ai_house_step == 1:
        render_step1()
    elif ai_house_step == 2:
        render_step2()
    elif ai_house_step == 3:
        render_step3()

def render_step1():
    """Paso 1: Configurador de vivienda - Estilo Mercedes Benz"""
    
    st.header("🏡 Diseña Tu Vivienda Sostenible")
    st.caption("Configura tu casa ideal. La IA diseñará la distribución perfecta para ti.")
    
    # Obtener datos de la finca
    plot_data = st.session_state.get("design_plot_data", {})
    max_buildable = plot_data.get('buildable_m2', 0)
    
    # ============================================
    # BANNER FINCA
    # ============================================
    if plot_data:
        col1, col2, col3 = st.columns(3)
        col1.metric("📍 Tu Finca", plot_data.get('title', 'Tu parcela'))
        col2.metric("📏 Superficie total", f"{plot_data.get('total_m2', 0):.0f} m²")
        col3.metric("🏗️ Máx. edificable (33%)", f"{max_buildable:.0f} m²")
        st.markdown("---")
    
    # ============================================
    # PASO A: PRESUPUESTO
    # ============================================
    st.subheader("💰 ¿Cuál es tu presupuesto?")
    
    budget = st.select_slider(
        "Selecciona tu rango de inversión",
        options=[50000, 75000, 100000, 125000, 150000, 175000, 200000, 
                 250000, 300000, 400000, 500000],
        value=150000,
        format_func=lambda x: f"€{x:,.0f}"
    )
    
    # Mensaje orientativo según presupuesto
    if budget < 100000:
        st.info("🏠 Casa básica sostenible: 60-80 m² · 2 dormitorios · Eficiente")
    elif budget < 150000:
        st.info("🏡 Casa confortable: 80-120 m² · 3 dormitorios · Muy eficiente")
    elif budget < 250000:
        st.success("🏘️ Casa amplia premium: 120-180 m² · 4 dormitorios · Alta eficiencia")
    else:
        st.success("🏰 Casa de lujo sostenible: 180m²+ · 5+ dormitorios · Máxima eficiencia")
    
    st.markdown("---")
    
    # ============================================
    # PASO B: ESTILO DE VIVIENDA
    # ============================================
    st.subheader("🎨 ¿Qué estilo te gusta?")
    
    col1, col2, col3 = st.columns(3)
    
    styles = {
        "🌿 Ecológico": "Materiales naturales, mínimo impacto ambiental",
        "🏡 Rural": "Piedra, madera, integrado en el paisaje",
        "🏠 Moderno": "Líneas limpias, grandes ventanales, minimalista",
        "⛰️ Montaña": "Refugio alpino, tejados inclinados, madera y piedra",
        "🌊 Playa": "Abierto, ventilado, colores claros, terrazas",
        "🏛️ Clásico": "Elegante, simétrico, materiales nobles",
        "💃 Andaluz": "Patio central, cerámica, cal, frescor natural",
        "🌆 Contemporáneo": "Vanguardista, tecnológico, sostenible"
    }
    
    style_options = list(styles.keys())
    selected_style = st.radio(
        "Elige el estilo de tu vivienda",
        style_options,
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # Mostrar descripción del estilo
    st.caption(f"✨ {styles[selected_style]}")
    
    st.markdown("---")
    
    # ============================================
    # PASO C: HABITACIONES Y BAÑOS
    # ============================================
    st.subheader("🛏️ Habitaciones y Baños")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        bedrooms = st.number_input(
            "🛏️ Dormitorios",
            min_value=1, max_value=6,
            value=3, step=1
        )
    
    with col2:
        bathrooms = st.number_input(
            "🚿 Baños",
            min_value=1, max_value=4,
            value=2, step=1
        )
    
    with col3:
        floors = st.selectbox(
            "Plantas",
            ["1 Planta", "2 Plantas", "Planta Baja + Semisótano", "2 Plantas + Semisótano"],
            index=0,
            help="Cada planta genera su propio plano de distribución"
        )
        
        # Avisos según selección
        if floors == "2 Plantas":
            st.caption("⚠️ Se diseñarán 2 planos: Planta Baja y Planta Alta")
        elif "Semisótano" in floors:
            st.caption("⚠️ Incluye plano de semisótano (garage/bodega/zona técnica)")
    
    st.markdown("---")
    
    # ============================================
    # PASO C2: FORMA Y TEJADO
    # ============================================
    st.subheader("🏗️ Forma y Tejado")
    
    col1, col2 = st.columns(2)
    
    with col1:
        house_shape = st.selectbox(
            "Forma de la planta",
            [
                "Cuadrada (más económica)",
                "Rectangular (más común)",
                "En L (para parcelas irregulares)",
                "Irregular / Personalizada"
            ],
            index=1,
            help="La forma afecta al coste de cimentación y construcción"
        )
        
        # Info de coste según forma
        shape_costs = {
            "Cuadrada (más económica)": ("Mínimo perímetro = mínimo coste", "✅"),
            "Rectangular (más común)": ("Equilibrio perfecto coste/funcionalidad", "✅"),
            "En L (para parcelas irregulares)": ("15-20% más cara que rectangular", "⚠️"),
            "Irregular / Personalizada": ("20-30% más cara, requiere arquitecto", "⚠️")
        }
        
        msg, icon = shape_costs[house_shape]
        st.caption(f"{icon} {msg}")
    
    with col2:
        roof_type = st.selectbox(
            "Tipo de tejado",
            [
                "Dos aguas (clásico, eficiente)",
                "Cuatro aguas (para zonas con mucha lluvia)",
                "Plana/Transitable (zona seca, terraza)",
                "A un agua (moderno, minimalista)",
                "Invertida (colecta agua lluvia)"
            ],
            index=0,
            help="El tejado afecta al coste, aislamiento y recogida de agua"
        )
    
    st.markdown("---")
    
    # ============================================
    # PASO D: EXTRAS
    # ============================================
    st.subheader("🌟 Extras")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        has_garage = st.checkbox("🚗 Garaje", value=True)
        has_pool = st.checkbox("🏊 Piscina")
    
    with col2:
        has_porch = st.checkbox("🌿 Porche/Terraza", value=True)
        has_bodega = st.checkbox("🍷 Bodega")
    
    with col3:
        has_huerto = st.checkbox("🌱 Huerto")
        has_caseta = st.checkbox("🔧 Casa de Aperos")
    
    with col4:
        has_accessible = st.checkbox("♿ Accesible")
        has_office = st.checkbox("💼 Despacho")
    
    st.markdown("---")
    
    # ============================================
    # PASO E: ENERGÍA Y SOSTENIBILIDAD
    # ============================================
    st.subheader("⚡ Energía y Sostenibilidad")
    st.caption("Reduce tu factura energética hasta un 90%")
    
    col1, col2 = st.columns(2)
    
    with col1:
        solar = st.checkbox("☀️ Paneles Solares", value=True,
            help="Autoconsumo eléctrico. Ahorro: €1,200/año")
        aerotermia = st.checkbox("🌡️ Aerotermia",
            help="Calefacción/frío eficiente. Ahorro: €800/año")
        geotermia = st.checkbox("🌍 Geotermia",
            help="Temperatura constante del suelo")
    
    with col2:
        rainwater = st.checkbox("💧 Recuperación Agua Lluvia", value=True,
            help="Ahorro hasta 40% en agua")
        insulation = st.checkbox("🌿 Aislamiento Natural",
            help="Lana de roca, corcho, cáñamo")
        domotic = st.checkbox("🏠 Domótica",
            help="Control inteligente del hogar")
    
    # Calcular ahorro estimado
    ahorro_anual = 0
    if solar: ahorro_anual += 1200
    if aerotermia: ahorro_anual += 800
    if rainwater: ahorro_anual += 300
    if insulation: ahorro_anual += 400
    if geotermia: ahorro_anual += 1000
    
    if ahorro_anual > 0:
        st.success(f"💰 Ahorro energético estimado: **€{ahorro_anual:,}/año** · Retorno inversión: {int(15000/ahorro_anual)} años")
    
    st.markdown("---")
    
    # ============================================
    # PASO F: NOTAS ESPECIALES
    # ============================================
    st.subheader("📝 Algo más que quieras añadir")
    
    special_notes = st.text_area(
        "Cuéntanos más detalles",
        placeholder="Ej: Quiero una bodega grande para eventos, necesito espacio para animales, me gusta mucho la luz natural...",
        height=80,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # ============================================
    # PASO G: CIMIENTOS E INSTALACIONES
    # ============================================
    st.subheader("🏗️ Cimientos e Instalaciones Básicas")
    st.caption("Calculamos automáticamente lo mínimo necesario para abaratar costes")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        foundation_type = st.selectbox(
            "Tipo de cimentación",
            [
                "Zapatas aisladas (mínimo, más barato)",
                "Losa de hormigón (suelos blandos)",
                "Pilotes (terrenos difíciles)",
                "Recomendación automática IA"
            ],
            index=3
        )
    
    with col2:
        st.markdown("**Suministro de agua**")
        water_municipal = st.checkbox("🏘️ Red municipal (si disponible)", value=False)
        water_rain = st.checkbox("🌧️ Depósito agua lluvia", value=True, 
            help="Depósito 5,000-10,000L. Ahorro 40% en agua")
        water_well = st.checkbox("⛏️ Pozo propio", value=False)
        water_solar = st.checkbox("☀️ Calentador solar ACS", value=True,
            help="Agua caliente sanitaria solar. Ahorro €400/año")
        
        # Calcular combinación
        water_systems = []
        if water_municipal: water_systems.append("red municipal")
        if water_rain: water_systems.append("depósito lluvia")
        if water_well: water_systems.append("pozo")
        if water_solar: water_systems.append("solar ACS")
        
        if not water_systems:
            st.warning("⚠️ Selecciona al menos un sistema de agua")
        else:
            st.caption(f"✅ Combinación: {' + '.join(water_systems)}")
    
    with col3:
        st.markdown("**Saneamiento**")
        sew_municipal = st.checkbox("🏘️ Red municipal (si disponible)", value=False,
            key="sew_municipal")
        sew_septic = st.checkbox("♻️ Fosa séptica ecológica", value=True,
            help="Autónomo, sin conexión a red")
        sew_phyto = st.checkbox("🌿 Fitodepuración", value=False,
            help="Máxima sostenibilidad. Filtra con plantas naturales")
        sew_biodigestor = st.checkbox("⚗️ Biodigestor", value=False,
            help="Genera biogás aprovechable para cocina")
        
        sewage_systems = []
        if sew_municipal: sewage_systems.append("red municipal")
        if sew_septic: sewage_systems.append("fosa séptica")
        if sew_phyto: sewage_systems.append("fitodepuración")
        if sew_biodigestor: sewage_systems.append("biodigestor")
        
        if not sewage_systems:
            st.warning("⚠️ Selecciona al menos un sistema de saneamiento")
        else:
            st.caption(f"✅ Combinación: {' + '.join(sewage_systems)}")
    
    st.markdown("---")
    
    # ============================================
    # BOTÓN DISEÑAR
    # ============================================
    
    # Calcular m² recomendados según presupuesto
    cost_per_m2 = 1100  # €/m² promedio sostenible
    max_m2_budget = int(budget * 0.85 / cost_per_m2)  # 85% para construcción
    
    if max_buildable > 0:
        recommended_m2 = min(max_m2_budget, int(max_buildable * 0.9))
    else:
        recommended_m2 = max_m2_budget
    
    # Calcular presupuesto cimentación automáticamente
    foundation_cost = int(recommended_m2 * 180)  # €180/m² cimentación
    
    st.info(f"💰 Presupuesto estimado de cimentación: **€{foundation_cost:,}** ({int(foundation_cost/budget*100)}% del presupuesto total) · Incluido en el presupuesto global")
    
    # Resumen antes del botón
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 15px; color: white; text-align: center;'>
        <h3>📋 Tu configuración</h3>
        <p>💰 Presupuesto: <b>€{budget:,}</b> · 
           🎨 Estilo: <b>{selected_style}</b> · 
           🛏️ Dormitorios: <b>{bedrooms}</b> · 
           🚿 Baños: <b>{bathrooms}</b></p>
        <p>📐 Superficie recomendada: <b>{recommended_m2} m²</b> 
           (dentro de tu presupuesto y parcela)</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        design_button = st.button(
            "🤖 DISEÑAR MI CASA CON IA",
            type="primary",
            use_container_width=True
        )
    
    if design_button:
        # Recopilar todos los datos
        req = {
            "budget": budget,
            "style": selected_style,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "floors": floors,
            "target_area_m2": recommended_m2,
            "max_buildable_m2": max_buildable,
            "house_shape": house_shape,
            "roof_type": roof_type,
            "foundation_type": foundation_type,
            "water_systems": water_systems,
            "sewage_systems": sewage_systems,
            "water_details": {
                "municipal": water_municipal,
                "rain_tank": water_rain,
                "well": water_well,
                "solar_acs": water_solar
            },
            "sewage_details": {
                "municipal": sew_municipal,
                "septic": sew_septic,
                "phyto": sew_phyto,
                "biodigestor": sew_biodigestor
            },
            "extras": {
                "garage": has_garage,
                "pool": has_pool,
                "porch": has_porch,
                "bodega": has_bodega,
                "huerto": has_huerto,
                "caseta": has_caseta,
                "accessible": has_accessible,
                "office": has_office
            },
            "energy": {
                "solar": solar,
                "aerotermia": aerotermia,
                "geotermia": geotermia,
                "rainwater": rainwater,
                "insulation": insulation,
                "domotic": domotic
            },
            "special_notes": special_notes,
            "estimated_savings": ahorro_anual
        }
        
        st.session_state["ai_house_requirements"] = req
        
        # Llamar a IA
        _generate_ai_proposal(req)

def _generate_ai_proposal(req):
    """Genera propuesta de distribución con IA"""
    with st.spinner("🤖 La IA está diseñando tu casa..."):
        try:
            from dotenv import load_dotenv
            from groq import Groq
            from pathlib import Path
            import os
            import json
            
            # Cargar API key
            project_root = Path(__file__).parent.parent.parent
            load_dotenv(dotenv_path=project_root / '.env')
            groq_api_key = os.getenv("GROQ_API_KEY")
            
            if not groq_api_key:
                st.error("❌ GROQ_API_KEY no encontrada")
                return
            
            client = Groq(api_key=groq_api_key)
            
            # Construir prompt simplificado
            extras_list = [k for k, v in req['extras'].items() if v]
            energy_list = [k for k, v in req['energy'].items() if v]
            
            prompt = f"""Diseña una vivienda '{req['style']}'de {req['target_area_m2']}m² con:
- {req['bedrooms']} dormitorios (1 principal + {req['bedrooms']-1} secundarios)
- {req['bathrooms']} baños
- Extras: {', '.join(extras_list) if extras_list else 'ninguno'}
- Energía/Sostenibilidad: {', '.join(energy_list) if energy_list else 'ninguno'}

Notas especiales: {req['special_notes'] or 'ninguna'}

Responde SOLO con un JSON válido (sin markdown) con habitaciones y m². Ejemplo:
{{
  "salon_cocina": 35,
  "dormitorio_principal": 16,
  "dormitorio": 11,
  "bano": 6,
  "bano_2": 5,
  "porche": 18,
  "garaje": 20
}}
"""
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # Parsear respuesta
            response_text = response.choices[0].message.content.strip()
            
            # Limpiar markdown si existe
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            ai_proposal = json.loads(response_text)
            
            # Guardar propuesta
            req["ai_room_proposal"] = ai_proposal
            st.session_state["ai_house_requirements"] = req
            
            st.success("✅ ¡Casa diseñada! Pasando al Paso 2...")
            st.session_state["ai_house_step"] = 2
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error generando diseño: {e}")
            import traceback
            st.code(traceback.format_exc())

def render_step2():
    """Paso 2: Editor visual unificado - Layout 2 columnas profesional"""
    
    st.header("Paso 2 – Tu Casa en Tiempo Real")
    st.caption("Ajusta tu diseño. El plano se actualiza automáticamente.")
    
    # ============================================
    # VALIDAR DATOS
    # ============================================
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if not proposal:
        st.warning("Primero completa el Paso 1")
        if st.button("← Volver al Paso 1"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # Datos de parcela
    plot_data = st.session_state.get("design_plot_data", {})
    max_buildable = plot_data.get('buildable_m2', 400.0)
    
    # ============================================
    # TIPOS DE HABITACIÓN CON PRECIOS REALES
    # ============================================
    from .data_model import HouseDesign, Plot, RoomType, RoomInstance
    
    room_types = {
        "salon_cocina": RoomType(code="salon_cocina", name="Salón-Cocina", min_m2=20, max_m2=50, base_cost_per_m2=1200),
        "dormitorio_principal": RoomType(code="dormitorio_principal", name="Dormitorio Principal", min_m2=12, max_m2=25, base_cost_per_m2=1400),
        "dormitorio": RoomType(code="dormitorio", name="Dormitorio", min_m2=8, max_m2=15, base_cost_per_m2=1100),
        "bano": RoomType(code="bano", name="Baño", min_m2=4, max_m2=8, base_cost_per_m2=900),
        "bodega": RoomType(code="bodega", name="Bodega", min_m2=6, max_m2=20, base_cost_per_m2=600),
        "piscina": RoomType(code="piscina", name="Piscina", min_m2=20, max_m2=60, base_cost_per_m2=2500),
        "paneles_solares": RoomType(code="paneles_solares", name="Paneles Solares", min_m2=3, max_m2=15, base_cost_per_m2=3000),
        "garaje": RoomType(code="garaje", name="Garaje", min_m2=15, max_m2=40, base_cost_per_m2=900),
        "porche": RoomType(code="porche", name="Porche/Terraza", min_m2=8, max_m2=40, base_cost_per_m2=700),
        "bomba_agua": RoomType(code="bomba_agua", name="Instalaciones", min_m2=2, max_m2=8, base_cost_per_m2=2000),
        "accesibilidad": RoomType(code="accesibilidad", name="Zona Accesible", min_m2=0, max_m2=10, base_cost_per_m2=2000),
        "pasillo": RoomType(code="pasillo", name="Pasillo/Distribuidor", min_m2=5, max_m2=20, base_cost_per_m2=800),
        "huerto": RoomType(code="huerto", name="Huerto", min_m2=10, max_m2=100, base_cost_per_m2=150),
        "despacho": RoomType(code="despacho", name="Despacho", min_m2=8, max_m2=20, base_cost_per_m2=1100),
    }
    
    # ============================================
    # CREAR DISEÑO CON MAPEO INTELIGENTE
    # ============================================
    plot = Plot(
        id=plot_data.get('id', 'temp'),
        area_m2=plot_data.get('total_m2', 400.0),
        buildable_ratio=0.33
    )
    design = HouseDesign(plot)
    
    for code, area in proposal.items():
        if not isinstance(area, (int, float)):
            continue
        
        room_type = None
        code_lower = code.lower()
        
        if code in room_types:
            room_type = room_types[code]
        elif 'salon' in code_lower or 'cocina' in code_lower:
            room_type = room_types['salon_cocina']
        elif 'dormitorio' in code_lower and 'principal' in code_lower:
            room_type = room_types['dormitorio_principal']
        elif 'dormitorio' in code_lower:
            room_type = room_types['dormitorio']
        elif 'bano' in code_lower or 'baño' in code_lower:
            room_type = room_types['bano']
        elif 'bodega' in code_lower:
            room_type = room_types['bodega']
        elif 'piscina' in code_lower:
            room_type = room_types['piscina']
        elif 'paneles' in code_lower or 'solar' in code_lower:
            room_type = room_types['paneles_solares']
        elif 'garaje' in code_lower or 'garage' in code_lower:
            room_type = room_types['garaje']
        elif 'porche' in code_lower or 'terraza' in code_lower:
            room_type = room_types['porche']
        elif 'bomba' in code_lower or 'instalac' in code_lower:
            room_type = room_types['bomba_agua']
        elif 'accesib' in code_lower:
            room_type = room_types['accesibilidad']
        elif 'pasillo' in code_lower or 'distrib' in code_lower:
            room_type = room_types['pasillo']
        elif 'huerto' in code_lower:
            room_type = room_types['huerto']
        elif 'despacho' in code_lower or 'oficina' in code_lower:
            room_type = room_types['despacho']
        else:
            room_type = RoomType(
                code=code,
                name=code.replace("_", " ").title(),
                min_m2=5, max_m2=50,
                base_cost_per_m2=1000
            )
        
        design.rooms.append(RoomInstance(
            room_type=room_type,
            area_m2=float(area)
        ))
    
    # ============================================
    # LAYOUT 2 COLUMNAS PRINCIPALES
    # ============================================
    col_left, col_right = st.columns([4, 6])
    
    # ============================================
    # COLUMNA IZQUIERDA: CONTROLES
    # ============================================
    with col_left:
        
        budget = req.get('budget', 150000)
        
        # Placeholder para métricas (se calculan después de sliders y checkboxes)
        metrics_placeholder = st.empty()
        
        st.markdown("---")
        
        # AJUSTAR HABITACIONES
        st.markdown("#### Ajustar Habitaciones")
        
        # Primero identificar qué extras están marcados para eliminar
        optional_codes = ['piscina', 'garaje', 'porche', 'bodega', 
                         'huerto', 'paneles', 'bomba', 'accesib']
        
        # Pre-calcular qué rooms se van a eliminar
        preview_remove = []
        for i, room in enumerate(design.rooms):
            code = room.room_type.code.lower()
            if any(x in code for x in optional_codes):
                keep = st.session_state.get(f"keep_{i}", True)
                if not keep:
                    preview_remove.append(i)
        
        # Mostrar sliders SOLO para rooms que NO se van a eliminar
        for i, room in enumerate(design.rooms):
            if room.area_m2 < 2:
                continue
            if i in preview_remove:
                continue  # No mostrar slider si va a ser eliminado
                
            new_area = st.slider(
                f"{room.room_type.name}",
                min_value=float(room.room_type.min_m2),
                max_value=float(room.room_type.max_m2),
                value=float(room.area_m2),
                step=0.5,
                key=f"step2_slider_{i}",
                help=f"€{room.room_type.base_cost_per_m2:,}/m²"
            )
            design.rooms[i].area_m2 = new_area
        
        st.markdown("---")
        
        # ELIMINAR EXTRAS
        st.markdown("#### Eliminar Extras (Ahorrar)")
        
        optional_codes = ['piscina', 'garaje', 'porche', 'bodega', 
                         'huerto', 'paneles', 'bomba', 'accesib']
        
        rooms_to_remove = []
        for i, room in enumerate(design.rooms):
            code = room.room_type.code.lower()
            if any(x in code for x in optional_codes):
                cost = room.area_m2 * room.room_type.base_cost_per_m2
                keep = st.checkbox(
                    f"{room.room_type.name} · €{cost:,.0f}",
                    value=True,
                    key=f"keep_{i}"
                )
                if not keep:
                    rooms_to_remove.append(i)
        
        # Eliminar desmarcados
        for idx in sorted(rooms_to_remove, reverse=True):
            design.rooms.pop(idx)
        
        # RECALCULAR MÉTRICAS FINALES (después de sliders y checkboxes)
        total_area_final = sum([r.area_m2 for r in design.rooms])
        total_cost_final = sum([r.area_m2 * r.room_type.base_cost_per_m2 for r in design.rooms])
        foundation_cost = int(total_area_final * 180)
        installation_cost = int(total_area_final * 150)
        total_with_extras = total_cost_final + foundation_cost + installation_cost
        budget_pct = total_with_extras / budget * 100
        
        if budget_pct <= 90:
            b_icon = "✅"
            b_color = "normal"
        elif budget_pct <= 100:
            b_icon = "⚠️"
            b_color = "normal"
        else:
            b_icon = "❌"
            b_color = "inverse"
        
        # Rellenar placeholder con métricas actualizadas
        with metrics_placeholder.container():
            m1, m2 = st.columns(2)
            m1.metric(
                "Presupuesto",
                f"€{total_with_extras:,.0f}",
                delta=f"{b_icon} {budget_pct:.0f}% de €{budget:,.0f}",
                delta_color=b_color
            )
            m2.metric(
                "Superficie",
                f"{total_area_final:.0f} m²",
                delta=f"Máx: {max_buildable:.0f} m²"
            )
            savings = req.get('estimated_savings', 0)
            if savings > 0:
                st.success(f"Ahorro energético: €{savings:,}/año")
        
        st.markdown("---")
        
        if 'current_floor_plan' in st.session_state:
            st.download_button(
                label="Descargar Plano PNG",
                data=st.session_state['current_floor_plan'],
                file_name="plano_distribucion.png",
                mime="image/png",
                use_container_width=True
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Paso 1", use_container_width=True):
                st.session_state["ai_house_step"] = 1
                st.rerun()
        with col2:
            if st.button("Paso 3 →", type="primary", use_container_width=True):
                st.session_state["ai_house_step"] = 3
                st.rerun()
    
    # ============================================
    # COLUMNA DERECHA: PLANO + IA
    # ============================================
    with col_right:
        
        # TABLA RESUMEN
        st.markdown("#### Tu Distribución")
        
        import pandas as pd
        table_data = []
        for room in design.rooms:
            price = room.room_type.base_cost_per_m2
            cost = room.area_m2 * price
            table_data.append({
                "Espacio": room.room_type.name,
                "m²": f"{room.area_m2:.0f}",
                "€/m²": f"€{price:,}",
                "Total": f"€{cost:,.0f}"
            })
        
        # Añadir cimentación e instalaciones
        table_data.append({
            "Espacio": "Cimentación",
            "m²": f"{total_area_final:.0f}",
            "€/m²": "€180",
            "Total": f"€{foundation_cost:,}"
        })
        table_data.append({
            "Espacio": "Instalaciones",
            "m²": f"{total_area_final:.0f}",
            "€/m²": "€150",
            "Total": f"€{installation_cost:,}"
        })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # PLANO 2D
        st.markdown("#### Plano de Distribución")
        
        if st.button("Generar Plano 2D", type="primary", use_container_width=True):
            try:
                from .floor_plan_svg import FloorPlanSVG
                planner = FloorPlanSVG(design)
                img_bytes = planner.generate()
                st.session_state['current_floor_plan'] = img_bytes
                st.session_state['current_design'] = design
                st.success("Plano generado correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"Error generando plano: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        if 'current_floor_plan' in st.session_state:
            st.image(
                st.session_state['current_floor_plan'],
                caption="Plano profesional con medidas reales",
                use_container_width=True
            )
        else:
            st.info("Pulsa 'Generar Plano 2D' para ver tu distribución")
        
        st.markdown("---")
        
        # ANÁLISIS IA
        if 'current_floor_plan' in st.session_state:
            st.markdown("#### Análisis del Arquitecto IA")
            
            with st.spinner("Analizando..."):
                try:
                    from groq import Groq
                    import os
                    from dotenv import load_dotenv
                    from pathlib import Path
                    
                    project_root = Path(__file__).parent.parent.parent
                    load_dotenv(dotenv_path=project_root / '.env')
                    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                    
                    rooms_summary = "\n".join([
                        f"- {r.room_type.name}: {r.area_m2:.0f} m² ({r.area_m2:.1f}m × {r.area_m2/max(r.area_m2**0.5,1):.1f}m aprox)"
                        for r in design.rooms
                    ])
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": f"""Eres arquitecto experto en vivienda sostenible española.

Analiza esta distribución:
{rooms_summary}
TOTAL: {total_area_final:.0f} m²
PRESUPUESTO: €{budget:,}
ESTILO: {req.get('style', 'No especificado')}

Evalúa brevemente:
1. ¿Las medidas son correctas para una vivienda real? (mínimos CTE)
2. ¿Algún espacio demasiado grande o pequeño?
3. ¿El presupuesto es realista?
4. Una sugerencia de mejora concreta

Máximo 150 palabras. Usa: ✅ para correcto, ⚠️ para mejorable, ❌ para problema."""}],
                        temperature=0.3,
                        max_tokens=300
                    )
                    
                    st.markdown(response.choices[0].message.content)
                
                except Exception as e:
                    st.warning(f"Análisis IA no disponible: {e}")

def render_step3():
    """Paso 3: Vista 3D y exportación"""
    
    st.header("Paso 3 – Vista 3D y Documentación")
    
    # Verificar que existe propuesta
    req = st.session_state.get("ai_house_requirements")
    if not req or "ai_room_proposal" not in req:
        st.warning("⚠️ Primero completa el Paso 1")
        if st.button("← Volver al Paso 1"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # Obtener diseño
    proposal = req["ai_room_proposal"]
    
    # Recrear HouseDesign (igual que en Paso 2)
    from .data_model import HouseDesign, Plot, RoomType, RoomInstance
    
    # Tipos de habitación
    room_types = {
        "salon_cocina": RoomType(code="salon_cocina", name="Salón-Cocina", min_m2=25, max_m2=50, base_cost_per_m2=1200),
        "dormitorio_principal": RoomType(code="dormitorio_principal", name="Dormitorio Principal", min_m2=12, max_m2=25, base_cost_per_m2=1400),
        "dormitorio": RoomType(code="dormitorio", name="Dormitorio", min_m2=8, max_m2=15, base_cost_per_m2=1100),
        "bano": RoomType(code="bano", name="Baño", min_m2=4, max_m2=8, base_cost_per_m2=900),
        "bodega": RoomType(code="bodega", name="Bodega", min_m2=6, max_m2=12, base_cost_per_m2=600),
        "piscina": RoomType(code="piscina", name="Piscina", min_m2=20, max_m2=40, base_cost_per_m2=2500),
        "paneles_solares": RoomType(code="paneles_solares", name="Paneles Solares", min_m2=3, max_m2=10, base_cost_per_m2=3000),
        "garaje": RoomType(code="garaje", name="Garaje", min_m2=12, max_m2=25, base_cost_per_m2=900),
        "porche": RoomType(code="porche", name="Porche", min_m2=10, max_m2=25, base_cost_per_m2=700),
        "bomba_agua": RoomType(code="bomba_agua", name="Bomba de Agua", min_m2=2, max_m2=5, base_cost_per_m2=5000),
        "accesibilidad": RoomType(code="accesibilidad", name="Accesibilidad", min_m2=0, max_m2=10, base_cost_per_m2=2000)
    }
    
    # Obtener datos de la parcela si existen
    plot_data = st.session_state.get("design_plot_data")
    
    if plot_data:
        plot = Plot(
            id=plot_data.get('id', 'unknown'),
            area_m2=plot_data.get('total_m2', 400.0),
            buildable_ratio=0.33
        )
    else:
        # Fallback si no hay datos de parcela
        plot = Plot(
            id='temp',
            area_m2=400.0,
            buildable_ratio=0.33
        )
    
    design = HouseDesign(plot)
    
    for code, area in proposal.items():
        if not isinstance(area, (int, float)):
            continue
        
        # Buscar tipo
        room_type = None
        code_lower = code.lower()
        
        if code in room_types:
            room_type = room_types[code]
        elif 'salon' in code_lower or 'cocina' in code_lower:
            room_type = room_types['salon_cocina']
        elif 'dormitorio' in code_lower and 'principal' in code_lower:
            room_type = room_types['dormitorio_principal']
        elif 'dormitorio' in code_lower:
            room_type = room_types['dormitorio']
        elif 'bano' in code_lower or 'baño' in code_lower:
            room_type = room_types['bano']
        elif 'bodega' in code_lower:
            room_type = room_types['bodega']
        elif 'piscina' in code_lower:
            room_type = room_types['piscina']
        elif 'paneles' in code_lower:
            room_type = room_types['paneles_solares']
        elif 'garaje' in code_lower:
            room_type = room_types['garaje']
        elif 'porche' in code_lower:
            room_type = room_types['porche']
        elif 'bomba' in code_lower:
            room_type = room_types['bomba_agua']
        elif 'accesibilidad' in code_lower:
            room_type = room_types['accesibilidad']
        else:
            room_type = RoomType(code=code, name=code.replace("_", " ").title(), min_m2=5, max_m2=50, base_cost_per_m2=1000)
        
        design.rooms.append(RoomInstance(room_type=room_type, area_m2=float(area)))
    
    # ============================================
    # ✏️ EDITOR INTERACTIVO
    # ============================================
    
    try:
        from .interactive_editor import InteractiveFloorEditor
        
        editor = InteractiveFloorEditor(design, ai_validator=None)
        editor.render()
        
    except Exception as e:
        st.error(f"❌ Error en editor: {e}")
        import traceback
        st.code(traceback.format_exc())
    
    st.markdown("---")
    
    # ============================================
    # 📐 VISUALIZACIÓN DEL PLANO ACTUAL
    # ============================================
    st.subheader("📐 Tu Plano Actual")
    
    # Mostrar plano 2D si existe
    if 'current_floor_plan' in st.session_state:
        st.image(
            st.session_state['current_floor_plan'],
            caption="Plano de distribución - Genera de nuevo si hiciste cambios",
            use_container_width=True
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Descargar Plano Actual",
                data=st.session_state['current_floor_plan'],
                file_name="plano_distribucion.png",
                mime="image/png"
            )
        with col2:
            if st.button("🔄 Regenerar Plano con Cambios"):
                st.info("💡 Vuelve al Paso 2 y pulsa 'Generar Plano 2D' de nuevo")
    else:
        st.warning("⚠️ Aún no has generado el plano. Vuelve al Paso 2.")
    
    st.markdown("---")
    
    # ============================================
    # 📄 DOCUMENTACIÓN
    # ============================================
    st.subheader("📄 Generar Documentación")
    st.info("🚧 Próximamente: Memoria técnica PDF, Presupuesto Excel, Planos DWG")
    
    st.markdown("---")
    
    # Botones de navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Volver al Paso 2"):
            st.session_state["ai_house_step"] = 2
            st.rerun()
    with col2:
        st.button("🎉 Finalizar Diseño", type="primary", disabled=True)