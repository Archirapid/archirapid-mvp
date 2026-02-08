import streamlit as st

from .data_model import create_example_design, HouseDesign, Plot

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
    st.header("Paso 2 – Metros, normativa y costes")
    st.info("Esta funcionalidad todavía está en construcción.")
    
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