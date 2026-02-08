import streamlit as st

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
            "notes": ""
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
    
    # Actualizar session state con los valores introducidos
    st.session_state["ai_house_requirements"] = req
    
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
    
    if st.button("Continuar a Paso 2"):
        st.session_state["ai_house_step"] = 2
        st.rerun()

def render_step2():
    st.header("Paso 2 – Propuesta de distribución")
    
    # Obtener requisitos del paso 1
    req = st.session_state.get("ai_house_requirements", {})
    
    # Crear plot ficticio
    plot = Plot(
        id="proposal_plot_001",
        area_m2=500.0,
        buildable_ratio=0.33,
        shape="rectangular",
        orientation="sur"
    )
    
    # Crear tipos de habitación fijos
    salon_cocina_type = RoomType(
        code="salon_cocina",
        name="Salón-Cocina",
        min_m2=25.0,
        max_m2=50.0,
        base_cost_per_m2=700.0,
        extra_cost_factors={"kitchen_equipment": 300.0}
    )
    
    dormitorio_principal_type = RoomType(
        code="dormitorio_principal",
        name="Dormitorio Principal",
        min_m2=12.0,
        max_m2=25.0,
        base_cost_per_m2=800.0,
        extra_cost_factors={"premium_finish": 200.0}
    )
    
    dormitorio_secundario_type = RoomType(
        code="dormitorio_secundario",
        name="Dormitorio",
        min_m2=8.0,
        max_m2=15.0,
        base_cost_per_m2=600.0
    )
    
    # Crear lista de habitaciones
    rooms = []
    
    # Siempre 1 salón-cocina
    rooms.append(RoomInstance(
        room_type=salon_cocina_type,
        area_m2=35.0,
        floor=0
    ))
    
    # Siempre 1 dormitorio principal
    rooms.append(RoomInstance(
        room_type=dormitorio_principal_type,
        area_m2=18.0,
        floor=0
    ))
    
    # Dormitorios secundarios según requisitos (mínimo 1)
    num_bedrooms = max(1, int(req.get("bedrooms", 3)) - 1)
    for i in range(num_bedrooms):
        rooms.append(RoomInstance(
            room_type=dormitorio_secundario_type,
            area_m2=12.0,
            floor=0
        ))
    
    # Crear diseño
    design = HouseDesign(
        plot=plot,
        rooms=rooms,
        style=req.get("style", "moderna"),
        materials=req.get("materials", ["hormigón"]),
        budget_limit=req.get("budget_limit")
    )
    
    # Mostrar tabla de estancias
    st.subheader("📋 Estancias propuestas")
    
    room_data = []
    for room in design.rooms:
        room_data.append({
            "Estancia": room.room_type.name,
            "m² sugeridos": f"{room.area_m2:.0f}",
            "m² mínimo": f"{room.room_type.min_m2:.0f}",
            "m² máximo": f"{room.room_type.max_m2:.0f}"
        })
    
    st.table(room_data)
    
    # Métricos del diseño
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Superficie máxima edificable",
            value=f"{design.plot.max_buildable_m2:.0f} m²"
        )
    with col2:
        st.metric(
            label="Superficie total diseñada",
            value=f"{design.total_area():.0f} m²"
        )
    with col3:
        st.metric(
            label="Coste estimado",
            value=f"€{design.estimated_cost():,.0f}"
        )
    
    # Advertencia si excede el máximo edificable
    if design.total_area() > design.plot.max_buildable_m2:
        st.warning(f"⚠️ La superficie diseñada ({design.total_area():.0f} m²) excede el máximo edificable ({design.plot.max_buildable_m2:.0f} m²)")
    
    # Botones de navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Volver al Paso 1"):
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