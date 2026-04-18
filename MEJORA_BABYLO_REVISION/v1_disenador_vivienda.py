
# disenador_vivienda.py - Wizard Avanzado con Arquitecto Virtual IA
import streamlit as st
import json
from modules.marketplace import ai_engine
from .catastro_api import fetch_by_ref_catastral
from .data_access import list_fincas, save_proyecto
from .gemelo_digital_vis import create_gemelo_3d

def main():
    st.title("🧙‍♂️ Arquitecto Virtual - Diseño Asistido")
    st.markdown("Tu experto IA te guiará paso a paso para diseñar la casa de tus sueños.")
    
    # State Machine
    if "wizard_step" not in st.session_state:
        st.session_state["wizard_step"] = 1
    
    # Verificar si viene desde plot_detail con una parcela específica
    selected_plot_id = st.session_state.get("selected_plot_for_design")
    preselected_finca = None
    
    if selected_plot_id:
        # Buscar la finca específica por ID
        from src import db
        plot_data = db.get_plot_by_id(selected_plot_id)
        if plot_data:
            preselected_finca = {
                'id': plot_data['id'],
                'direccion': plot_data.get('address', plot_data.get('locality', 'Sin dirección')),
                'ref_catastral': plot_data.get('catastral_ref', ''),
                'superficie': plot_data.get('m2', 0),
                'coordenadas': f"{plot_data.get('lat', 0)}, {plot_data.get('lon', 0)}"
            }
            st.info(f"🎯 Diseñando para la parcela: **{plot_data.get('title', 'Sin título')}**")
    
    # === PASO 1: FINCA Y CONTEXTO ===
    if st.session_state["wizard_step"] == 1:
        st.header("Paso 1: Tu Terreno")
        
        fincas = list_fincas()
        if not fincas:
             st.warning("Primero debes tener una finca registrada.")
             return
             
        finca_opts = {f"{f['direccion']} (Ref: {f['ref_catastral']})": f for f in fincas}
        
        # Si hay una finca preseleccionada, mostrarla primero
        if preselected_finca:
            default_finca_name = None
            for finca_name, finca_data in finca_opts.items():
                if finca_data.get('ref_catastral') == preselected_finca['ref_catastral']:
                    default_finca_name = finca_name
                    break
            
            if default_finca_name:
                finca_opts_list = list(finca_opts.keys())
                default_index = finca_opts_list.index(default_finca_name) if default_finca_name in finca_opts_list else 0
            else:
                default_index = 0
        else:
            default_index = 0
        
        sel = st.selectbox("Selecciona la finca donde construir:", 
                          list(finca_opts.keys()),
                          index=default_index)
        
        if sel:
            finca = finca_opts[sel]
            st.info(f"📍 Analizando {finca['direccion']}...")
            
            # Validación Catastral Real
            if st.button("Validar Geometría en Catastro"):
                with st.spinner("Conectando con Sede Electrónica..."):
                    cat_data = fetch_by_ref_catastral(finca['ref_catastral'])
                    if cat_data.get("estado") == "validado_oficial":
                        st.success(f"✅ Coordenadas Oficales: {cat_data['ubicacion_geo']['lat']}, {cat_data['ubicacion_geo']['lng']}")
                        st.session_state["design_finca"] = finca
                        st.session_state["design_finca"].update({"geo_real": cat_data['ubicacion_geo']})
                    else:
                        st.warning("No se pudo validar en Catastro oficial. Usando datos locales.")
                        st.session_state["design_finca"] = finca

            if "design_finca" in st.session_state:
                 if st.button("Siguiente: Entrevista de Diseño ->"):
                     st.session_state["wizard_step"] = 2
                     st.rerun()

    # === PASO 2: ENTREVISTA IA ===
    elif st.session_state["wizard_step"] == 2:
        st.header("Paso 2: Entrevista de Diseño")
        st.markdown("El Arquitecto Virtual necesita entender tus preferencias.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Estructura y Estilo")
            estilo = st.selectbox("Estilo Arquitectónico", ["Moderno", "Rústico / Piedra", "Mediterráneo", "Industrial", "Minimalista"])
            material = st.selectbox("Material Principal", ["Hormigón", "Ladrillo Visto", "Piedra Natural", "Madera Tecnológica"])
            cubierta = st.selectbox("Tipo de Cubierta", ["Plana (Moderna)", "Inclinada Teja", "Pizarra Negra (Montaña)", "A dos aguas"])
            
        with c2:
            st.subheader("Programa de Necesidades")
            habs = st.slider("Habitaciones", 1, 8, 3)
            extras = st.multiselect("Elementos Extra", ["Piscina", "Chimenea", "Porche", "Garaje Subterráneo", "Huerto Solar"])
            presupuesto = st.select_slider("Nivel de Acabados / Presupuesto", options=["Low Cost", "Estándar", "Premium", "Lujo"])

        desc_adicional = st.text_area("Cuéntale más detalles al arquitecto (vistas, orientación, sueños...):")
        
        if st.button("🧠 Generar Propuesta Arquitectónica"):
            with st.spinner("La IA está diseñando tu proyecto... (Calculando estructuras y distribución)"):
                finca = st.session_state["design_finca"]
        
                prompt = f"""
Actúa como Arquitecto Senior especializado en vivienda unifamiliar eficiente en España.

Diseña una vivienda en:
- Finca: {finca['surface_m2']} m2 en {finca['municipio']}.
- Estilo arquitectónico: {estilo} con cubierta {cubierta}.
- Material principal: {material}.
- Programa: {habs} habitaciones.
- Extras deseados: {', '.join(extras) if extras else 'ninguno'}.
- Detalles adicionales del usuario: {desc_adicional}.

Responde EXCLUSIVAMENTE en formato JSON válido, sin texto fuera del JSON.
Estructura EXACTAMENTE así:

{{
  "concepto": "Descripción poética y técnica del diseño, máximo 4-5 frases.",
  "distribucion": [
    {{
      "nombre": "Dormitorio principal",
      "m2": 14
    }},
    {{
      "nombre": "Salón-comedor",
      "m2": 26
    }}
  ],
  "materialidad": "Explicación de por qué se han elegido estos materiales y cómo se adaptan al entorno.",
  "habitaciones": [
    {{
      "id": "dormitorio_1",
      "tipo": "dormitorio",
      "m2": 12,
      "planta": 1
    }},
    {{
      "id": "salon",
      "tipo": "salon",
      "m2": 25,
      "planta": 1
    }}
  ]
}}

IMPORTANTE:
- No incluyas comentarios.
- No uses comillas simples.
- No envuelvas el JSON en ```json ni ```.
- No añadas texto antes ni después del JSON.
                """.strip()
        
                res = ai_engine.generate_text(prompt)
        
                # Manejo de errores de la IA (cuota, clave, red, etc.)
                if isinstance(res, str) and res.startswith("Error:"):
                    st.error(res)
                else:
                    try:
                        clean = res.replace("```json", "").replace("```", "").strip()
                        plan = json.loads(clean)
                        st.session_state["design_plan"] = plan
                        st.session_state["wizard_step"] = 3
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al interpretar la respuesta de la IA: {e}")
                        st.code(res)

    # === PASO 3: VISUALIZACIÓN Y REFINAMIENTO ===
    elif st.session_state["wizard_step"] == 3:
        plan = st.session_state["design_plan"]
        st.header("Paso 3: Tu Propuesta de Diseño")
        
        st.success("✅ Diseño Generado por IA")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("### 📝 Concepto")
            st.info(plan.get("concepto", ""))
            st.markdown("### 🧱 Materialidad")
            st.write(plan.get("materialidad", ""))
            
            if st.button("<- Volver a diseñar"):
                st.session_state["wizard_step"] = 2
                st.rerun()
                
        with c2:
            st.subheader("🏗️ Modelo Volumétrico Preliminar")
            # Adaptar JSON de IA para el visualizador 3D existente
            # Asegurar formato compatible
            plot_dummy = {"surface_m2": st.session_state["design_finca"]["surface_m2"]}
            
            # Intentar reutilizar create_gemelo_3d
            try:
                fig = create_gemelo_3d(plan)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.warning(f"No se pudo renderizar 3D: {e}")
                st.json(plan) # Fallback

if __name__ == "__main__":
    main()