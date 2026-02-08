import streamlit as st
import json
import os
from dotenv import load_dotenv
from groq import Groq

from .data_model import create_example_design, HouseDesign, Plot, RoomType, RoomInstance

def main():
    # Inicializar el paso si no existe
    if "ai_house_step" not in st.session_state:
        st.session_state["ai_house_step"] = 1
    
    ai_house_step = st.session_state["ai_house_step"]
    
    # Título principal
    st.title("🏠 Diseñador de Vivienda con IA (MVP)")
    
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
    st.header("Paso 1 – Necesidades y preferencias del cliente")
    
    # Inicializar requisitos si no existen
    if "ai_house_requirements" not in st.session_state:
        st.session_state["ai_house_requirements"] = {
            "target_area_m2": 120.0,
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
    
    req = st.session_state["ai_house_requirements"]
    
    # Formulario en dos columnas
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📐 Dimensiones y habitaciones")
        
        req["target_area_m2"] = st.number_input(
            "Superficie objetivo (m²)",
            min_value=40.0,
            max_value=400.0,
            value=float(req["target_area_m2"]),
            step=5.0
        )
        
        req["budget_limit"] = st.number_input(
            "Presupuesto máximo (€)",
            min_value=0.0,
            value=float(req["budget_limit"] or 0.0),
            step=10000.0,
            help="0 = sin límite"
        )
        
        req["bedrooms"] = st.number_input(
            "Dormitorios",
            min_value=1.0,
            max_value=6.0,
            value=float(req["bedrooms"])
        )
        
        req["bathrooms"] = st.number_input(
            "Baños",
            min_value=1.0,
            max_value=4.0,
            value=float(req["bathrooms"])
        )
        
        req["max_floors"] = st.selectbox(
            "Número máximo de plantas",
            options=[1, 2, 3],
            index=req["max_floors"] - 1
        )
        
        req["orientation"] = st.selectbox(
            "Orientación solar principal",
            options=["Norte", "Sur", "Este", "Oeste", "Sudeste", "Suroeste"],
            index=["Norte", "Sur", "Este", "Oeste", "Sudeste", "Suroeste"].index(req.get("orientation", "Sur"))
        )
        
        req["roof_type"] = st.selectbox(
            "Tipo de cubierta",
            options=["Plana", "A dos aguas", "A cuatro aguas", "Inclinada"],
            index=["Plana", "A dos aguas", "A cuatro aguas", "Inclinada"].index(req.get("roof_type", "A dos aguas"))
        )
    
    with col_right:
        st.subheader("🎨 Estilo y extras")
        
        req["style"] = st.selectbox(
            "Estilo preferido",
            options=["moderna", "rústica", "minimalista", "mediterránea"],
            index=["moderna", "rústica", "minimalista", "mediterránea"].index(req["style"])
        )
        
        req["materials"] = st.multiselect(
            "Materiales principales",
            options=["hormigón", "madera", "piedra", "ladrillo"],
            default=req["materials"]
        )
        
        st.markdown("**Extras deseados:**")
        req["wants_pool"] = st.checkbox("Piscina", value=req["wants_pool"])
        req["wants_porch"] = st.checkbox("Porche", value=req["wants_porch"])
        req["wants_garage"] = st.checkbox("Garaje", value=req["wants_garage"])
        req["wants_outhouse"] = st.checkbox("Casa de aperos separada", value=req["wants_outhouse"])
        
        req["notes"] = st.text_area(
            "Cuéntanos qué te gustaría (texto libre)",
            value=req["notes"],
            height=100
        )
        
        req["energy_rating"] = st.selectbox(
            "Eficiencia energética objetivo",
            options=["A", "B", "C", "D"],
            index=["A", "B", "C", "D"].index(req.get("energy_rating", "B"))
        )
        
        req["accessibility"] = st.checkbox(
            "Vivienda adaptada (accesibilidad)",
            value=req.get("accessibility", False)
        )
        
        req["sustainable_materials"] = st.multiselect(
            "Materiales sostenibles",
            options=["Paneles solares", "Bomba de calor", "Aislamiento natural", "Recuperación de agua"],
            default=req.get("sustainable_materials", [])
        )
    
    # Actualizar session state con los valores introducidos
    st.session_state["ai_house_requirements"] = req
    
    # Separador visual
    st.markdown("---")
    st.info("🔗 **Gemelos Digitales UE** - Preparado para Testear fondos")
    
    # Separador visual
    st.markdown("---")
    
    # Crear un diseño de ejemplo
    design = create_example_design()
    
    st.caption("Vista previa con datos de ejemplo (temporal)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Superficie máxima edificable",
            value=f"{design.plot.max_buildable_m2:.0f} m²"
        )
    with col2:
        st.metric(
            label="Superficie diseñada (ejemplo)",
            value=f"{design.total_area():.0f} m²"
        )
    
    st.write(f"**Coste estimado:** €{design.estimated_cost():,.0f}")
    
    col_btn, col_cont = st.columns([1, 3])
    with col_btn:
        if st.button("🤖 Analizar preferencias con IA", type="secondary"):
            try:
                from dotenv import load_dotenv
                import os
                import json
                from groq import Groq
                
                load_dotenv()
                groq_api_key = os.getenv("GROQ_API_KEY")
                
                if not groq_api_key:
                    st.error("❌ GROQ_API_KEY no encontrada en .env")
                    st.stop()
                
                client = Groq(api_key=groq_api_key)
                
                prompt = f"""FONTANERO ESPAÑOL necesita CASA COMPLETA. 

DATOS: {req['notes']} | Dorm: {req['bedrooms']} | Baños: {req['bathrooms']}

**SIEMPRE INCLUIR estas 8+ habitaciones:**
1. "salon_cocina": 35.0
2. "dormitorio_principal": 16.0  
3. "dormitorio": 12.0 x {int(req['bedrooms'])-1}
4. "bano": 6.0 x {int(req['bathrooms'])}
5. SI "bodega"/"sótano" → "bodega": 10.0
6. SI "piscina" → "piscina": 25.0
7. SI "paneles"/"solares" → "paneles_solares": 5.0
8. SI "garaje"/"parking" → "garaje": 18.0
9. SI "apero"/"caseta" → "casa_apero": 20.0

**EJEMPLO "bodega 8 pax + piscina":**
{{"salon_cocina":35,"dormitorio_principal":16,"dormitorio":12,"bano":6,"bodega":10,"piscina":25}}

**SOLO JSON válido sin texto extra:**"""
                
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                
                # Extraer y limpiar JSON de respuesta de Groq
                response_text = response.choices[0].message.content.strip()
                
                st.write("🔍 Respuesta cruda de IA:", response_text[:200] + "..." if len(response_text) > 200 else response_text)
                
                # Buscar JSON entre ```json ... ```
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                else:
                    json_str = response_text
                
                # Intentar parsear (con fallback)
                try:
                    ai_proposal = json.loads(json_str)
                except json.JSONDecodeError:
                    # Fallback: devolver propuesta básica
                    ai_proposal = {
                        "salon_cocina": 35.0,
                        "dormitorio_principal": 18.0,
                        "dormitorio": 12.0 * (req.get("bedrooms", 3) - 1),
                        "bano": 6.0 * req.get("bathrooms", 2),
                        "extras": []
                    }
                
                # Actualizar requirements
                req["ai_room_proposal"] = ai_proposal
                st.session_state["ai_house_requirements"] = req
                st.success("✅ IA ha analizado tus preferencias")
                st.rerun()
                st.stop()
            
            except json.JSONDecodeError as e:
                st.error(f"❌ Error parseando respuesta de IA: {e}")
            except Exception as e:
                st.error(f"❌ Error con IA: {e}")
    
    with col_cont:
        st.success("🤖 **La IA propone esta casa para ti:**")
        if req.get("ai_room_proposal"):
            proposal_text = []
            for code, area in req["ai_room_proposal"].items():
                if isinstance(area, (int, float)):
                    name = code.replace("_", " ").replace("salon", "Salón").replace("bano", "Baño").title()
                    proposal_text.append(f"• **{name}** ({area} m²)")
                else:
                    proposal_text.append(f"• **{code.title()}**")
            for line in proposal_text:
                st.markdown(line)
    
    if st.button("Continuar a Paso 2"):
        st.session_state["ai_house_step"] = 2
        st.rerun()

def render_step2():
    st.header("Paso 2 – Ajusta tu distribución")
    
    req = st.session_state.get("ai_house_requirements", {})
    
    # Si no hay propuesta IA, volver al Paso 1
    if not req.get("ai_room_proposal"):
        st.warning("⚠️ Primero analiza tus preferencias con IA en Paso 1")
        if st.button("← Volver al Paso 1"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # Crear plot ficticio
    plot = Plot(id="design_plot", area_m2=500.0, buildable_ratio=0.33)
    
    # Tipos de habitación CON PRECIOS REALES
    room_types = {
        "salon_cocina": RoomType("salon_cocina", "Salón-Cocina", 25,50,1200),
        "dormitorio_principal": RoomType("dormitorio_principal", "Dormitorio Principal", 12,25,1400),
        "dormitorio": RoomType("dormitorio", "Dormitorio", 8,15,1100),
        "bano": RoomType("bano", "Baño", 4,8,900),
        "bodega": RoomType("bodega", "Bodega", 6,12,600),
        "piscina": RoomType("piscina", "Piscina", 20,40,2500),
        "paneles_solares": RoomType("paneles_solares", "Paneles Solares", 3,10,3000),
        "garaje": RoomType("garaje", "Garaje", 12,25,900),
        "casa_apero": RoomType("casa_apero", "Casa de Aperos", 15,30,800),
        "huerto": RoomType("huerto", "Huerto", 10,50,150),
        "porche": RoomType("porche", "Porche", 10,25,700),
        "bomba_agua": RoomType("bomba_agua", "Bomba de Agua", 2,5,5000),
        "cubierta": RoomType("cubierta", "Cubierta Tejado", 80,150,400),
        "accesibilidad": RoomType("accesibilidad", "Accesibilidad", 0,10,2000)
    }
    
    # Inicializar diseño editable
    if "house_design" not in st.session_state:
        rooms = []
        for room_code, area in req["ai_room_proposal"].items():
            room_type = room_types.get(room_code)
            if not room_type:
                room_type = RoomType(room_code, room_code.replace("_", " ").title(), 10, 50, 1000)
            if isinstance(area, (int, float)):
                rooms.append(RoomInstance(room_type, float(area)))
            elif isinstance(area, list):
                for sub_area in area:
                    rooms.append(RoomInstance(room_type, float(sub_area)))
        st.session_state["house_design"] = HouseDesign(plot=plot, rooms=rooms)
    
    design = st.session_state["house_design"]
    
    # Tabla FONTANERO SIMPLE (sin bugs Streamlit)
    room_data = []
    room_names = {
        "salon_cocina": "🏠 Salón-Cocina",
        "dormitorio_principal": "🛏️ Dorm. Principal", 
        "dormitorio": "🛏️ Dormitorio",
        "bano": "🚿 Baño",
        "bodega": "🍷 Bodega",
        "piscina": "🏊 Piscina",
        "paneles_solares": "☀️ Paneles Solares",
        "garaje": "🚗 Garaje"
    }
    
    for room in design.rooms:
        name = room_names.get(room.room_type.code, f"📦 {room.room_type.code.title()}")
        total_cost = room.area_m2 * getattr(room.room_type, 'base_cost_per_m2', 1000)
        
        room_data.append({
            "Habitación": name,
            "m²": f"{room.area_m2:.0f}",
            "€/m²": f"€{getattr(room.room_type, 'base_cost_per_m2', 1000):,.0f}",
            "Total": f"€{total_cost:,.0f}"
        })
    
    st.subheader("📊 Tu propuesta actual")
    
    for room in design.rooms:
        code = room.room_type.code
        
        # HARDCODE precios por código
        if code == "salon_cocina":
            icon, name, price_m2 = "🏠", "Salón Cocina", 1200
        elif code == "dormitorio_principal":
            icon, name, price_m2 = "🛏️", "Dormitorio Principal", 1400
        elif code == "dormitorio":
            icon, name, price_m2 = "🛏️", "Dormitorio", 1100
        elif code == "bano":
            icon, name, price_m2 = "🚿", "Baño", 900
        elif code == "bodega":
            icon, name, price_m2 = "🍷", "Bodega", 600
        elif code == "piscina":
            icon, name, price_m2 = "🏊", "Piscina", 2500
        elif code == "paneles_solares":
            icon, name, price_m2 = "☀️", "Paneles Solares", 3000
        elif code == "garaje":
            icon, name, price_m2 = "🚗", "Garaje", 900
        elif code == "casa_apero":
            icon, name, price_m2 = "🔧", "Casa Aperos", 800
        else:
            icon, name, price_m2 = "📦", code.title(), 1000
        
        total = room.area_m2 * price_m2
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**{icon} {name}**")
        with col2:
            st.markdown(f"**{room.area_m2:.0f} m²**")
        with col3:
            st.markdown(f"**€{price_m2:,.0f}**")
        with col4:
            st.markdown(f"**€{total:,.0f}**")
        st.markdown("---")
    
    # SLIDERS ABAJO
    st.subheader("🔧 Ajusta medidas")
    for i, room in enumerate(design.rooms):
        with st.container():
            col1, col2 = st.columns([3,1])
            with col1: st.write(f"**{room.room_type.name}**")
            with col2: st.write(f"{room.area_m2:.0f} m²")
            new_area = st.slider(
                f"m² {room.room_type.name}",
                min_value=float(room.room_type.min_m2),
                max_value=float(room.room_type.max_m2),
                value=float(room.area_m2),
                step=0.5,
                key=f"slider_{i}"
            )
            design.rooms[i].area_m2 = new_area
    
    # MÉTRICOS EN TIEMPO REAL
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Máx. edificable", f"{design.plot.max_buildable_m2:.0f} m²")
    with col2:
        total_area = design.total_area()
        color = "normal" if total_area <= design.plot.max_buildable_m2 else "inverse"
        st.metric("Total diseñado", f"{total_area:.0f} m²", delta=None, delta_color=color)
    with col3:
        st.metric("Coste total", f"€{design.estimated_cost():,.0f}")
    
    # Botones
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Volver al Paso 1"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
    with col2:
        if st.button("Continuar a Paso 3"):
            st.session_state["ai_house_step"] = 3
            st.rerun()

def render_step3():
    st.header("Paso 3 – Diseño volumétrico y 3D")
    st.info("Esta funcionalidad todavía está en construcción.")
    
    if st.button("Volver al Paso 2"):
        st.session_state["ai_house_step"] = 2
        st.rerun()