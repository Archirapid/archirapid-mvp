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
    
    # Guardar selecciones
    if 'request' not in st.session_state:
        st.session_state['request'] = {}
    
    st.session_state['request']['house_shape'] = house_shape
    st.session_state['request']['roof_type'] = roof_type
    
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

PETICIONES ESPECIALES DEL CLIENTE (OBLIGATORIO INCLUIR):
{req.get('special_notes', 'ninguna')}

IMPORTANTE - Si el cliente menciona:
- "chimenea" → añadir coste €3,000-5,000 en descripción
- "suelo radiante" → añadir €80/m² extra al presupuesto
- "domótica" → añadir €5,000-15,000 en sistemas inteligentes
- Cualquier extra especial → incluirlo en el análisis y presupuesto
NUNCA ignorar las peticiones especiales del cliente.

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
        
        # Diccionario de costes por m² según tipo
        ROOM_COSTS = {
            'salon': 1200, 'cocina': 1200, 'dormitorio': 1100,
            'bano': 900, 'garaje': 900, 'porche': 700,
            'bodega': 600, 'pasillo': 800, 'paneles': 3000,
            'piscina': 2500, 'huerto': 150, 'despacho': 1100,
            'caseta': 800, 'office': 1100, 'lavadero': 700,
        }
        
        def get_cost_per_m2(room_code: str) -> int:
            code_lower = room_code.lower()
            for key, cost in ROOM_COSTS.items():
                if key in code_lower:
                    return cost
            return 1000  # coste por defecto
        
        # Mostrar sliders SOLO para rooms que NO se van a eliminar
        for i, room in enumerate(design.rooms):
            if room.area_m2 < 2:
                continue
            if i in preview_remove:
                continue  # No mostrar slider si va a ser eliminado
            
            cost_per_m2 = get_cost_per_m2(room.room_type.code)
            current_cost = room.area_m2 * cost_per_m2
            
            # Mostrar nombre y precio actual
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{room.room_type.name}**")
            with col2:
                st.markdown(f"<span style='color:#2ECC71; font-weight:bold;'>€{current_cost:,.0f}</span>", 
                           unsafe_allow_html=True)
            
            new_area = st.slider(
                f"{room.area_m2:.1f} m²",
                min_value=float(room.room_type.min_m2),
                max_value=float(room.room_type.max_m2),
                value=float(room.area_m2),
                step=0.5,
                key=f"step2_slider_{i}",
                label_visibility="collapsed"
            )
            
            # Actualizar área y mostrar cambio si hubo
            if abs(new_area - room.area_m2) > 0.1:
                old_cost = room.area_m2 * cost_per_m2
                new_cost = new_area * cost_per_m2
                diff = new_cost - old_cost
                
                if diff > 0:
                    st.caption(f"💰 +€{diff:,.0f}")
                elif diff < 0:
                    st.caption(f"💰 {diff:,.0f}")
            
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
        
        # TABS: 2D y 3D
        tab_2d, tab_3d = st.tabs(["📐 Plano 2D", "🏠 Vista 3D"])
        
        with tab_2d:
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
        
        with tab_3d:
            if st.button("Generar Vista 3D", type="primary", use_container_width=True):
                try:
                    from .viewer3d import Viewer3D
                    roof_type = st.session_state.get('request', {}).get('roof_type', 'Dos aguas (clásico, eficiente)')
                    viewer = Viewer3D(design, roof_type=roof_type)
                    html_3d = viewer.generate_html()
                    st.session_state['current_3d_html'] = html_3d
                    st.success("Vista 3D generada")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generando 3D: {e}")
                    import traceback
                    st.code(traceback.format_exc())
            
            if 'current_3d_html' in st.session_state:
                import streamlit.components.v1 as components
                components.html(
                    st.session_state['current_3d_html'],
                    height=570,
                    scrolling=False
                )
                st.caption("Arrastra para rotar · Scroll para zoom · Botones para cambiar vista")
            else:
                st.info("Pulsa 'Generar Vista 3D' para ver tu casa en 3D interactivo")
        
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
    """Paso 3: Documentación completa y monetización"""
    
    st.header("Paso 3 – Tu Proyecto Completo")
    st.caption("Documentación técnica, eficiencia energética y siguiente paso.")
    
    # Validar datos
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if not proposal:
        st.warning("Primero completa el Paso 1 y 2")
        if st.button("← Volver al inicio"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # Calcular datos del diseño
    budget = req.get('budget', 150000)
    style = req.get('style', 'No especificado')
    energy = req.get('energy', {})
    water_systems = req.get('water_systems', [])
    sewage_systems = req.get('sewage_systems', [])
    
    total_area = sum(v for v in proposal.values() if isinstance(v, (int, float)))
    
    # Costes por partidas
    construction_cost = int(total_area * 1100)
    foundation_cost = int(total_area * 180)
    installation_cost = int(total_area * 150)
    architecture_cost = int((construction_cost + foundation_cost) * 0.08)
    total_cost = construction_cost + foundation_cost + installation_cost + architecture_cost
    
    # Calcular subvenciones
    subsidy = 0
    if energy.get('solar'): subsidy += 3000
    if energy.get('aerotermia'): subsidy += 5000
    if energy.get('geotermia'): subsidy += 8000
    if energy.get('insulation'): subsidy += 2000
    if energy.get('rainwater'): subsidy += 1000
    if energy.get('domotic'): subsidy += 500
    subsidy_total = min(subsidy, int(total_cost * 0.40))
    
    # ============================================
    # RESUMEN EJECUTIVO - ARRIBA
    # ============================================
    st.markdown("### Tu Proyecto en Números")
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Coste Total Estimado",
        f"€{total_cost:,}",
        delta=f"vs €{int(total_area * 3500):,} piso ciudad",
        delta_color="normal"
    )
    col2.metric(
        "Subvenciones Estimadas",
        f"€{subsidy_total:,}",
        delta=f"Coste neto: €{total_cost - subsidy_total:,}",
        delta_color="normal"
    )
    col3.metric(
        "Superficie Total",
        f"{total_area:.0f} m²",
        delta=f"Estilo: {style.split(' ')[-1]}"
    )
    col4.metric(
        "Ahorro vs Piso Ciudad",
        f"€{int(total_area * 3500) - (total_cost - subsidy_total):,}",
        delta="Ahorro real con subvenciones"
    )
    
    st.markdown("---")
    
    # ============================================
    # DOS COLUMNAS: ENERGÍA + PRESUPUESTO
    # ============================================
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        
        # EFICIENCIA ENERGÉTICA
        st.markdown("### Eficiencia Energética")
        
        # Calcular calificación
        energy_score = 0
        if energy.get('solar'): energy_score += 25
        if energy.get('aerotermia'): energy_score += 20
        if energy.get('geotermia'): energy_score += 20
        if energy.get('insulation'): energy_score += 15
        if energy.get('rainwater'): energy_score += 10
        if energy.get('domotic'): energy_score += 10
        
        if energy_score >= 60:
            rating = "A"
            rating_color = "#2ECC71"
            rating_text = "Máxima eficiencia energética"
        elif energy_score >= 40:
            rating = "B"
            rating_color = "#27AE60"
            rating_text = "Alta eficiencia energética"
        elif energy_score >= 20:
            rating = "C"
            rating_color = "#F39C12"
            rating_text = "Eficiencia media"
        else:
            rating = "D"
            rating_color = "#E74C3C"
            rating_text = "Eficiencia básica"
        
        # Badge de calificación
        st.markdown(f"""
        <div style='background: {rating_color}; padding: 20px; border-radius: 10px; 
                    text-align: center; color: white; margin-bottom: 15px;'>
            <h1 style='margin:0; font-size: 60px;'>{rating}</h1>
            <p style='margin:0; font-size: 16px;'>{rating_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Detalles energéticos
        consumo_base = total_area * 120  # kWh/año casa normal
        ahorro_pct = energy_score * 0.9
        consumo_real = int(consumo_base * (1 - ahorro_pct/100))
        ahorro_euros = int((consumo_base - consumo_real) * 0.18)
        co2_evitado = int((consumo_base - consumo_real) * 0.25 / 1000 * 10) / 10
        
        e1, e2 = st.columns(2)
        e1.metric("Consumo estimado", f"{consumo_real:,} kWh/año",
                 delta=f"-{ahorro_pct:.0f}% vs media")
        e2.metric("Ahorro energético", f"€{ahorro_euros:,}/año",
                 delta="vs casa convencional")
        
        st.metric("CO₂ evitado", f"{co2_evitado} ton/año",
                 delta="Contribución al medioambiente")
        
        # Sistemas instalados
        st.markdown("**Sistemas sostenibles incluidos:**")
        systems = []
        if energy.get('solar'): systems.append("☀️ Paneles solares fotovoltaicos")
        if energy.get('aerotermia'): systems.append("🌡️ Aerotermia (calefacción/frío)")
        if energy.get('geotermia'): systems.append("🌍 Geotermia")
        if energy.get('insulation'): systems.append("🌿 Aislamiento natural")
        if energy.get('rainwater'): systems.append("💧 Recuperación agua lluvia")
        if energy.get('domotic'): systems.append("🏠 Domótica inteligente")
        if water_systems: systems.append(f"💧 Agua: {' + '.join(water_systems)}")
        if sewage_systems: systems.append(f"♻️ Saneamiento: {' + '.join(sewage_systems)}")
        
        for s in systems:
            st.markdown(f"- {s}")
        
        st.markdown("---")
        
        # SUBVENCIONES
        st.markdown("### Subvenciones Disponibles")
        
        subsidy_data = []
        if energy.get('solar'):
            subsidy_data.append(("☀️ Paneles solares (IDAE)", "€3,000"))
        if energy.get('aerotermia'):
            subsidy_data.append(("🌡️ Aerotermia (NextGen EU)", "€5,000"))
        if energy.get('geotermia'):
            subsidy_data.append(("🌍 Geotermia (NextGen EU)", "€8,000"))
        if energy.get('insulation'):
            subsidy_data.append(("🌿 Aislamiento (IDAE)", "€2,000"))
        if energy.get('rainwater'):
            subsidy_data.append(("💧 Agua lluvia (CC.AA.)", "€1,000"))
        
        if subsidy_data:
            for name, amount in subsidy_data:
                col_s1, col_s2 = st.columns([3, 1])
                col_s1.markdown(f"- {name}")
                col_s2.markdown(f"**{amount}**")
            
            st.success(f"Total estimado: **€{subsidy_total:,}** (hasta 40% del coste)")
            st.caption("Sujeto a convocatorias vigentes. Consulta con nuestro equipo.")
        else:
            st.info("Activa sistemas sostenibles en el Paso 1 para acceder a subvenciones")
    
    with col_right:
        
        # PRESUPUESTO DETALLADO
        st.markdown("### Presupuesto por Partidas")
        
        import pandas as pd
        
        partidas = [
            ("1. Cimentación", f"€{foundation_cost:,}", 
             f"{int(foundation_cost/total_cost*100)}%",
             "Zapatas/losa según estudio geotécnico"),
            ("2. Estructura y cubierta", f"€{int(construction_cost*0.35):,}",
             "32%", "Estructura + tejado + cerramientos ext."),
            ("3. Cerramientos y tabiquería", f"€{int(construction_cost*0.20):,}",
             "18%", "Fachada, ventanas, puertas, tabiques int."),
            ("4. Instalaciones", f"€{installation_cost:,}",
             f"{int(installation_cost/total_cost*100)}%",
             "Elec., fontanería, climatización, domótica"),
            ("5. Acabados", f"€{int(construction_cost*0.25):,}",
             "23%", "Pavimentos, pintura, cocina, baños"),
            ("6. Sistemas sostenibles", f"€{int(construction_cost*0.10):,}",
             "9%", "Paneles, aerotermia, depósito lluvia"),
            ("7. Honorarios técnicos", f"€{architecture_cost:,}",
             "8%", "Arquitecto, aparejador, licencias"),
        ]
        
        df = pd.DataFrame(partidas, 
                         columns=["Partida", "Coste", "%", "Descripción"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Total
        st.markdown(f"""
        <div style='background: #2C3E50; padding: 15px; border-radius: 8px; 
                    color: white; text-align: center;'>
            <h3 style='margin:0;'>TOTAL: €{total_cost:,}</h3>
            <p style='margin:5px 0 0 0; font-size:14px;'>
                Neto con subvenciones: €{total_cost - subsidy_total:,}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # PLANO ACTUAL
        st.markdown("### Tu Plano")
        
        if 'current_floor_plan' in st.session_state:
            st.image(
                st.session_state['current_floor_plan'],
                caption="Plano de distribución",
                use_container_width=True
            )
        else:
            st.info("Genera el plano en el Paso 2")
        
        st.markdown("---")
        
        # DESCARGAS
        st.markdown("### Descargas")
        
        dl1, dl2 = st.columns(2)
        
        with dl1:
            if 'current_floor_plan' in st.session_state:
                st.download_button(
                    label="Descargar Plano PNG",
                    data=st.session_state['current_floor_plan'],
                    file_name="plano_archirapid.png",
                    mime="image/png",
                    use_container_width=True
                )
        
        with dl2:
            # Excel presupuesto
            try:
                import io
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
                
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Presupuesto"
                
                # Cabecera
                ws['A1'] = "PRESUPUESTO ARCHIRAPID"
                ws['A1'].font = Font(bold=True, size=14)
                ws['A2'] = f"Superficie: {total_area:.0f} m² | Estilo: {style}"
                
                # Headers
                headers = ["Partida", "Coste (€)", "% Total", "Descripción"]
                for col, h in enumerate(headers, 1):
                    cell = ws.cell(row=4, column=col, value=h)
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="2C3E50")
                
                # Datos
                for row, (partida, coste, pct, desc) in enumerate(partidas, 5):
                    ws.cell(row=row, column=1, value=partida)
                    ws.cell(row=row, column=2, value=coste)
                    ws.cell(row=row, column=3, value=pct)
                    ws.cell(row=row, column=4, value=desc)
                
                # Total
                ws.cell(row=len(partidas)+6, column=1, value="TOTAL").font = Font(bold=True)
                ws.cell(row=len(partidas)+6, column=2, value=f"€{total_cost:,}").font = Font(bold=True)
                ws.cell(row=len(partidas)+7, column=1, value="Con subvenciones").font = Font(bold=True)
                ws.cell(row=len(partidas)+7, column=2, value=f"€{total_cost-subsidy_total:,}").font = Font(bold=True, color="2ECC71")
                
                # Ajustar columnas
                ws.column_dimensions['A'].width = 30
                ws.column_dimensions['B'].width = 15
                ws.column_dimensions['C'].width = 10
                ws.column_dimensions['D'].width = 45
                
                excel_buffer = io.BytesIO()
                wb.save(excel_buffer)
                excel_buffer.seek(0)
                
                st.download_button(
                    label="Descargar Excel",
                    data=excel_buffer.getvalue(),
                    file_name="presupuesto_archirapid.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.warning(f"Excel no disponible: {e}")
    
    st.markdown("---")
    
    # ============================================
    # CONSTRUCTORES ASOCIADOS - MONETIZACIÓN
    # ============================================
    st.markdown("### Constructores Asociados")
    st.caption("Solicita presupuesto real a constructores verificados de tu zona")
    
    constructors = [
        {
            "name": "Construcciones EcoVerde",
            "specialty": "Vivienda sostenible y bioconstrucción",
            "rating": "⭐⭐⭐⭐⭐",
            "projects": "127 proyectos",
            "zone": "Andalucía, Extremadura"
        },
        {
            "name": "BuildGreen España",
            "specialty": "Casas pasivas y certificación energética",
            "rating": "⭐⭐⭐⭐⭐",
            "projects": "89 proyectos",
            "zone": "Nacional"
        },
        {
            "name": "Construye Rural",
            "specialty": "Vivienda rural, piedra natural y madera",
            "rating": "⭐⭐⭐⭐",
            "projects": "203 proyectos",
            "zone": "Todo el territorio"
        }
    ]
    
    cols = st.columns(3)
    for col, constructor in zip(cols, constructors):
        with col:
            st.markdown(f"""
            <div style='border: 1px solid #ddd; border-radius: 10px; 
                        padding: 15px; height: 200px;'>
                <h4 style='color: #2C3E50; margin-top:0;'>{constructor["name"]}</h4>
                <p style='font-size:12px; color:#666;'>{constructor["specialty"]}</p>
                <p>{constructor["rating"]}</p>
                <p style='font-size:11px;'>📁 {constructor["projects"]}</p>
                <p style='font-size:11px;'>📍 {constructor["zone"]}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.button(
                f"Solicitar Presupuesto",
                key=f"constructor_{constructor['name']}",
                use_container_width=True,
                type="primary"
            )
    
    st.info("ArchiRapid cobra una comisión del 3% al constructor cuando se formaliza el contrato. Sin coste para el cliente.")
    
    st.markdown("---")
    
    # NAVEGACIÓN
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Volver al Paso 2", use_container_width=True):
            st.session_state["ai_house_step"] = 2
            st.rerun()
    with col2:
        if st.button("Finalizar y Contactar", type="primary", use_container_width=True):
            st.balloons()
            st.success("Proyecto completado. Nos pondremos en contacto contigo en 24h.")