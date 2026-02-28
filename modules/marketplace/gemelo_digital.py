# modules/marketplace/gemelo_digital.py
"""
Gemelo Digital Inteligente para ARCHIRAPID
Módulo que crea réplicas virtuales de proyectos con análisis IA en tiempo real.
Integración quirúrgica: no rompe código existente, reutiliza componentes.
"""

import streamlit as st
import plotly.graph_objects as go
import json
import random
from modules.marketplace.utils import list_published_plots
from modules.marketplace.ai_engine import get_ai_response, plan_vivienda
from .validacion import validar_plan_local
from .pago_simulado import init_pago_state, render_paso_pago, verificar_pago, reset_pago
from .documentacion import generar_memoria_constructiva, generar_presupuesto_estimado, generar_plano_cad
from .data_access import list_fincas, get_finca, save_proyecto
from .catastro_api import fetch_by_ref_catastral

def generar_plan_vivienda(plot_data, num_habitaciones, num_banos, con_garage, presupuesto_max):
    """
    Genera un plan de vivienda estructurado usando IA.
    Devuelve JSON con distribución de habitaciones y cálculos automáticos.

    Args:
        plot_data: Datos de la parcela del marketplace
        num_habitaciones: Número de habitaciones deseadas
        num_banos: Número de baños deseados
        con_garage: Si incluye garage
        presupuesto_max: Presupuesto máximo en euros

    Returns:
        dict: Plan estructurado en formato JSON compatible con visualización 3D
    """
    superficie_parcela = plot_data['surface_m2']

    # Usar la nueva función plan_vivienda del ai_engine
    plan_simple = plan_vivienda(superficie_parcela, num_habitaciones, con_garage)

    # Si hay error en la respuesta de IA, usar fallback
    if "error" in plan_simple:
        return crear_plan_fallback(num_habitaciones, num_banos, con_garage, int(superficie_parcela * 0.33))

    # Convertir el formato simple al formato complejo esperado
    distribucion = []

    # Convertir habitaciones
    tipos_habitacion = ["dormitorio", "salon", "cocina", "bano", "terraza"]
    for i, hab in enumerate(plan_simple.get("habitaciones", [])):
        tipo = tipos_habitacion[min(i, len(tipos_habitacion)-1)]
        distribucion.append({
            "tipo": tipo,
            "nombre": hab["nombre"],
            "m2": hab["m2"],
            "descripcion": f"Habitación tipo {tipo}"
        })

    # Agregar baños si se especificaron
    for i in range(num_banos):
        distribucion.append({
            "tipo": "bano",
            "nombre": f"Baño {i+1}",
            "m2": 6,
            "descripcion": "Baño completo"
        })

    # Agregar garage si se solicitó
    if con_garage and "garage" in plan_simple:
        distribucion.append({
            "tipo": "garage",
            "nombre": "Garage",
            "m2": plan_simple["garage"]["m2"],
            "descripcion": "Estacionamiento para vehículos"
        })

    # Calcular métricas
    total_m2 = plan_simple.get("total_m2", sum(h["m2"] for h in distribucion))
    eficiencia_parcela = (total_m2 / superficie_parcela) * 100
    presupuesto_estimado = total_m2 * 1000  # €1000/m² aproximado

    # Crear respuesta en formato esperado
    plan_completo = {
        "distribucion": distribucion,
        "metricas": {
            "total_m2_construidos": total_m2,
            "m2_parcela_usados": total_m2,
            "eficiencia_parcela": round(eficiencia_parcela, 1),
            "presupuesto_estimado": presupuesto_estimado,
            "tiempo_construccion_meses": 8
        },
        "validaciones": {
            "cumple_normativa": total_m2 <= int(superficie_parcela * 0.33),
            "edificabilidad_ok": eficiencia_parcela <= 33,
            "presupuesto_ok": presupuesto_estimado <= presupuesto_max,
            "observaciones": f"Plan generado por IA para {num_habitaciones} habitaciones"
        }
    }

    return plan_completo

def crear_plan_fallback(num_habitaciones, num_banos, con_garage, m2_max):
    """Plan básico de fallback cuando la IA falla"""
    distribucion = []

    # Salón básico
    distribucion.append({
        "tipo": "salon",
        "nombre": "Salón-Comedor",
        "m2": min(25, m2_max // 4),
        "descripcion": "Espacio principal"
    })

    # Cocina
    distribucion.append({
        "tipo": "cocina",
        "nombre": "Cocina",
        "m2": 10,
        "descripcion": "Cocina funcional"
    })

    # Dormitorios
    for i in range(num_habitaciones):
        distribucion.append({
            "tipo": "dormitorio",
            "nombre": f"Dormitorio {i+1}",
            "m2": 12 if i == 0 else 10,
            "descripcion": "Habitación cómoda" if i == 0 else "Habitación secundaria"
        })

    # Baños
    for i in range(num_banos):
        distribucion.append({
            "tipo": "bano",
            "nombre": f"Baño {i+1}",
            "m2": 6 if i == 0 else 4,
            "descripcion": "Baño completo" if i == 0 else "Baño secundario"
        })

    # Garage si aplica
    if con_garage:
        distribucion.append({
            "tipo": "garage",
            "nombre": "Garage",
            "m2": 20,
            "descripcion": "Para 2 vehículos"
        })

    total_m2 = sum(item['m2'] for item in distribucion)

    return {
        "distribucion": distribucion,
        "metricas": {
            "total_m2_construidos": total_m2,
            "m2_parcela_usados": total_m2,
            "eficiencia_parcela": round((total_m2 / 100) * 100, 1),  # Asumiendo parcela de 100m² para cálculo
            "presupuesto_estimado": total_m2 * 1000,
            "tiempo_construccion_meses": 6
        },
        "validaciones": {
            "cumple_normativa": total_m2 <= m2_max,
            "edificabilidad_ok": total_m2 <= m2_max,
            "presupuesto_ok": True,
            "observaciones": "Plan básico generado automáticamente"
        }
    }


def editor_tabiques(plan_json, superficie_finca):
    """
    Componente de edición de tabiques que permite ajustar m² por estancia.
    Usa st.data_editor para edición interactiva manteniendo nombres fijos.

    Args:
        plan_json: Plan actual con habitaciones
        superficie_finca: Superficie total de la finca

    Returns:
        tuple: (plan_json_actualizado, resultado_validacion)
    """
    st.subheader("✏️ Editar tabiques (m² por estancia)")

    # Construir dataframe simple para edición
    filas = []
    for h in plan_json.get("habitaciones", []):
        filas.append({
            "nombre": h.get("nombre", "Estancia"),
            "m2": float(h.get("m2", 0))
        })

    # Editor de datos con nombres deshabilitados
    edited = st.data_editor(
        filas,
        num_rows="dynamic",
        column_config={
            "nombre": st.column_config.TextColumn("Estancia", disabled=True),
            "m2": st.column_config.NumberColumn("m²", min_value=1.0, step=0.5)
        },
        use_container_width=True
    )

    # Aplicar cambios al JSON (solo m2)
    for i, h in enumerate(plan_json.get("habitaciones", [])):
        if i < len(edited):
            h["m2"] = float(edited[i]["m2"])

    # Recalcular total_m2
    total = 0
    for h in plan_json.get("habitaciones", []):
        total += float(h.get("m2", 0))
    if "garage" in plan_json:
        total += float(plan_json["garage"].get("m2", 0))
    plan_json["total_m2"] = total

    # Validación local
    resultado = validar_plan_local(plan_json, superficie_finca)

    # Mostrar validaciones
    st.markdown("### 📏 Validación con reglas genéricas")
    if resultado["ok"]:
        st.success(".1f"".1f")
    else:
        for e in resultado["errores"]:
            st.error(e)

    for r in resultado["recomendaciones"]:
        st.info(r)

    return plan_json, resultado


def evaluar_con_ia(plan_json, superficie_finca):
    """
    Evalúa el plan con IA y propone ajustes según normas genéricas.

    Args:
        plan_json: Plan actual
        superficie_finca: Superficie de la finca

    Returns:
        str: Análisis y propuestas de la IA
    """
    total = plan_json.get("total_m2", 0)
    if total == 0:
        total = sum(float(h.get("m2", 0)) for h in plan_json.get("habitaciones", [])) + \
                (float(plan_json["garage"].get("m2", 0)) if "garage" in plan_json else 0)

    prompt = f"""
Eres un asistente de arquitectura para un MVP. Normas genéricas:
- Dormitorios ≥ 8 m² (recomendado ≥ 10 m²).
- Salón/Comedor ≥ 12 m² (recomendado ≥ 18 m²).
- Cocina ≥ 6 m².
- Baño ≥ 3 m².
- Superficie construida ≤ 33% de la finca.

Finca: {superficie_finca:.1f} m². Máximo construible: {superficie_finca*0.33:.1f} m².
Plan actual (JSON): {json.dumps(plan_json, ensure_ascii=False)}

Tarea:
1) Indica qué estancias NO cumplen y por qué.
2) Propón ajustes concretos de m² por estancia para cumplir (sin superar el 33%).
3) Si algún dormitorio queda en 6 m², explica que solo sería válido como despensa/trastero en este MVP.
4) Devuelve un JSON de propuesta ajustada con habitaciones (nombre, m2), garage y total_m2.
"""

    try:
        analisis = get_ai_response(prompt)
        return analisis
    except Exception as e:
        return f"Error al consultar IA: {str(e)}. Verifica configuración de API."


def analizar_impacto_ambiental(m2_construidos: float, estilo: str) -> dict:
    """Simula un análisis de eficiencia y emisiones para un proyecto.

    - Si el estilo es 'Moderno' o 'Sostenible' (variante insensible a mayúsculas),
      la eficiencia se considera alta ('A').
    - Si el estilo es 'Rústica Tradicional' o similares, se considera 'C'.
    - En otros casos se asigna 'B'.

    Retorna un dict con claves: 'eficiencia_energetica' y 'emisiones_co2_kg'.
    """
    estilo_norm = (estilo or '').strip().lower()
    if estilo_norm in ('moderno', 'moderna', 'sostenible', 'eco', 'sustainable'):
        eficiencia = 'A'
    elif estilo_norm in ('rustica tradicional', 'rústica tradicional', 'rustico', 'rústico'):
        eficiencia = 'C'
    else:
        eficiencia = 'B'

    try:
        emisiones = 500 + float(m2_construidos)
    except Exception:
        emisiones = 500.0

    return {
        'eficiencia_energetica': eficiencia,
        'emisiones_co2_kg': emisiones
    }


def main():
    """Interfaz principal del Gemelo Digital"""
    st.title("🏠 Gemelo Digital Inteligente")
    st.markdown("""
    **Simula y optimiza tu proyecto arquitectónico con IA en tiempo real**

    Este gemelo digital analiza tu parcela y genera recomendaciones inteligentes
    para eficiencia energética, distribución óptima y sostenibilidad.
    """)
    st.markdown("---")

    # === CONEXIÓN CON FINCAS: Seleccionar finca del cliente ===
    st.subheader("📍 Selecciona tu Finca")
    
    # Verificar si viene desde plot_detail con una parcela específica
    selected_plot_id = st.session_state.get("selected_plot_for_gemelo")
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
            st.info(f"🎯 Analizando la parcela: **{plot_data.get('title', 'Sin título')}**")
    
    fincas = list_fincas()

    if not fincas:
        st.warning("No hay fincas disponibles. Ve a la sección de Propietario para subir una finca.")
        return

    finca_options = {f"{f['direccion']} (Ref: {f['ref_catastral']}) - {f.get('superficie', 'N/A')} m²": f
                    for f in fincas}
    
    # Si hay una finca preseleccionada, mostrarla primero
    if preselected_finca:
        default_index = 0
        finca_options_list = list(finca_options.keys())
        # Buscar si la finca preseleccionada está en la lista
        for i, finca_name in enumerate(finca_options_list):
            if preselected_finca['ref_catastral'] in finca_name:
                default_index = i
                break
    else:
        default_index = 0
    
    selected_finca_name = st.selectbox(
        "Selecciona una finca:",
        list(finca_options.keys()),
        index=default_index,
        key="gemelo_finca_select_mvp"
    )

    selected_finca = finca_options[selected_finca_name] if selected_finca_name else None

    if not selected_finca:
        st.info("👆 Selecciona una finca para continuar con el análisis.")
        return

    # === MAPEO DE CAMPOS REALES DE LA BD ===
    direccion = selected_finca.get("direccion", "Sin dirección")
    municipio = selected_finca.get("provincia", "Sin municipio")
    superficie = selected_finca.get("superficie_parcela", 0)
    ref_cat = selected_finca.get("referencia_catastral", "No disponible")
    pdf_cat = selected_finca.get("plano_catastral_path", "No disponible")
    lat = selected_finca.get("lat", None)
    lon = selected_finca.get("lon", None)

    coordenadas_str = f"{lat}, {lon}" if lat and lon else "No disponibles"

    # === BOTÓN ACTUALIZAR CATASTRO ===
    if st.button("🔄 Actualizar datos catastrales", key="update_catastro_gemelo"):
        with st.spinner("Consultando Catastro..."):
            from modules.marketplace.catastro_api import fetch_by_ref_catastral
            catastro_data = fetch_by_ref_catastral(ref_cat)
            if catastro_data:
                st.success("✅ Datos catastrales actualizados")
            else:
                st.warning("No se pudieron actualizar los datos catastrales")

    # === MOSTRAR INFORMACIÓN DE LA FINCA ===
    st.success(f"✅ Finca seleccionada: **{direccion}**")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Superficie", f"{superficie} m²")
        st.write(f"**Municipio:** {municipio}")

    with col2:
        st.write(f"**Ref. Catastral:** {ref_cat}")
        st.write(f"**PDF Catastral:** {pdf_cat}")

    with col3:
        st.write(f"**Latitud:** {lat}")
        st.write(f"**Longitud:** {lon}")

    # Información adicional
    with st.expander("📋 Detalles completos de la finca", expanded=False):
        st.json({
            "direccion": direccion,
            "municipio": municipio,
            "superficie_parcela": superficie,
            "referencia_catastral": ref_cat,
            "plano_catastral_path": pdf_cat,
            "lat": lat,
            "lon": lon,
            "estado": selected_finca.get("estado", {})
        })

    st.markdown("---")

    # === NUEVA SECCIÓN MVP: Generación Rápida de Plan con IA ===
    st.subheader("🚀 MVP - Generación Rápida de Plan con IA")
    st.markdown("**Genera un plan de vivienda completo con IA en segundos**")

    # Información sobre configuración necesaria
    with st.expander("ℹ️ Configuración requerida", expanded=False):
        st.markdown("""
        **Para usar esta funcionalidad necesitas:**
        - ✅ API Key de OpenRouter configurada
        - ✅ Conexión a internet
        - ✅ Modelo Mistral-7B disponible

        **Variables de entorno requeridas:**
        ```
        OPENROUTER_API_KEY=tu_api_key_aqui
        ```

        La IA generará automáticamente la distribución óptima basada en la normativa española.
        """)

    # --- Inputs del cliente (usando datos de la finca seleccionada) ---
    superficie_finca = selected_finca.get('superficie_parcela', 500)  # Usar superficie de la finca seleccionada

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Superficie de finca", f"{superficie_finca} m²")
        st.info("📏 Superficie tomada de la finca seleccionada")
    with col2:
        habitaciones = st.slider("Número de habitaciones", min_value=1, max_value=10, value=3,
                               help="Número total de habitaciones (salón, dormitorios, cocina, baños)")
    with col3:
        garage = st.checkbox("Incluir garage", value=True,
                           help="¿Quieres incluir un garage en el diseño?")

    # Mostrar información adicional de la finca
    with st.expander("📋 Detalles de la finca seleccionada", expanded=False):
        st.json({
            "direccion": selected_finca.get('direccion'),
            "superficie": selected_finca.get('superficie'),
            "ref_catastral": selected_finca.get('ref_catastral'),
            "coordenadas": selected_finca.get('coordenadas'),
            "descripcion": selected_finca.get('descripcion')
        })

    # --- Generar plan con IA ---
    if st.button("🚀 Generar Plan con IA", type="primary", use_container_width=True):
        with st.spinner("🤖 IA analizando finca y generando distribución óptima..."):
            try:
                # Importar la función plan_vivienda
                from .ai_engine import plan_vivienda

                # Llamar a la IA para generar el plan usando datos de la finca
                plan_json = plan_vivienda(superficie_finca, habitaciones, garage)

                # Verificar si hay error en la respuesta
                if 'error' in plan_json:
                    st.error(f"❌ Error en la generación IA: {plan_json['error']}")
                    with st.expander("Detalles del error", expanded=False):
                        if 'raw' in plan_json:
                            st.code(plan_json['raw'], language='text')
                        st.markdown("""
                        **Posibles soluciones:**
                        1. Verifica que la API key de OpenRouter esté configurada:
                           ```powershell
                           $env:OPENROUTER_API_KEY = "tu_api_key_aqui"
                           ```
                        2. Reinicia la terminal/IDE después de configurar
                        3. Verifica tu conexión a internet
                        """)
                    return

                # Guardar en session_state para persistencia
                st.session_state['plan_ia_mvp'] = plan_json
                st.session_state['parametros_mvp'] = {
                    'superficie_finca': superficie_finca,
                    'habitaciones': habitaciones,
                    'garage': garage,
                    'finca_id': selected_finca.get('id'),
                    'finca_direccion': selected_finca.get('direccion'),
                    'referencia_catastral': selected_finca.get('ref_catastral'),
                    'coordenadas': selected_finca.get('coordenadas')
                }

                st.success("✅ Plan generado exitosamente con IA!")
                st.info(f"📊 Plan optimizado para parcela de {superficie_finca} m² con {habitaciones} habitaciones{' + garage' if garage else ''}")

            except Exception as e:
                st.error(f"❌ Error inesperado: {str(e)}")
                st.info("Verifica la configuración de la aplicación y la conexión a internet.")

    # --- Mostrar resultados si existen ---
    if 'plan_ia_mvp' in st.session_state:
        plan_json = st.session_state['plan_ia_mvp']

        # Mostrar el JSON generado por IA
        st.subheader("📊 Plan Generado por IA")
        with st.expander("Ver JSON completo del plan", expanded=False):
            st.json(plan_json)

        # Resumen del plan
        if 'habitaciones' in plan_json:
            habitaciones_lista = plan_json['habitaciones']

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                habitaciones_count = len(habitaciones_lista)
                st.metric("Habitaciones", habitaciones_count)
            with col_b:
                garage_incluido = 'garage' in plan_json and plan_json['garage']
                st.metric("Garage", "Sí" if garage_incluido else "No")
            with col_c:
                total_m2 = plan_json.get('total_m2', sum(h.get('m2', 0) for h in habitaciones_lista) + (plan_json['garage'].get('m2', 0) if garage_incluido else 0))
                st.metric("Superficie Total", f"{total_m2} m²")

            # Lista de habitaciones
            st.markdown("**🏠 Distribución Generada:**")
            for hab in habitaciones_lista:
                st.markdown(f"🏠 **{hab.get('nombre', 'Habitación')}** - {hab.get('m2', 0)} m²")

            if garage_incluido:
                garage_m2 = plan_json['garage'].get('m2', 0)
                st.markdown(f"🚗 **Garage** - {garage_m2} m²")

        # --- Visualización 3D ---
        st.subheader("🏗️ Visualización 3D del Plan Generado")
        try:
            fig = create_gemelo_3d(plan_json, selected_finca)
            st.plotly_chart(fig, use_container_width=True)

            st.info("💡 **Visualización IA**: Los cubos representan habitaciones proporcionales centradas en la parcela. "
                   "Puedes rotar, hacer zoom y explorar el diseño generado.")

        except Exception as e:
            st.error(f"❌ Error en la visualización 3D: {str(e)}")

        # --- Edición de tabiques ---
        st.markdown("---")
        plan_json_editado, resultado_validacion = editor_tabiques(plan_json, superficie_finca)

        # Actualizar session_state si cambió
        if plan_json_editado != plan_json:
            st.session_state['plan_ia_mvp'] = plan_json_editado
            plan_json = plan_json_editado
            st.success("✅ Cambios aplicados al plan")

        # --- Evaluación con IA ---
        if st.button("🧠 Validar con IA y proponer ajustes", type="secondary", use_container_width=True):
            with st.spinner("🤖 IA analizando y proponiendo ajustes..."):
                try:
                    informe_ia = evaluar_con_ia(plan_json, superficie_finca)
                    st.markdown("### 📊 Informe y Propuestas de IA")
                    st.write(informe_ia)

                    # Intentar parsear JSON de propuesta si existe
                    try:
                        # Buscar JSON en la respuesta (entre ```json y ```)
                        import re
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', informe_ia, re.DOTALL)
                        if json_match:
                            propuesta_json = json.loads(json_match.group(1))
                            st.markdown("### ✅ Propuesta ajustada por IA")
                            with st.expander("Ver propuesta JSON", expanded=False):
                                st.json(propuesta_json)

                            # Opción para aplicar la propuesta
                            if st.button("📝 Aplicar propuesta de IA", type="primary"):
                                st.session_state['plan_ia_mvp'] = propuesta_json
                                st.success("✅ Propuesta aplicada. Recarga la página para ver los cambios.")
                                st.rerun()
                        else:
                            st.info("La IA proporcionó análisis textual. Si incluye una propuesta JSON, se mostrará arriba.")

                    except json.JSONDecodeError:
                        st.info("La IA devolvió análisis textual sin propuesta JSON estructurada.")

                except Exception as e:
                    st.error(f"❌ Error al consultar IA: {str(e)}")

        # --- Memoria constructiva y presupuesto ---
        st.markdown("---")
        st.subheader("🧾 Memoria Constructiva y Presupuesto")

        # Importar funciones de documentación
        from .documentacion import generar_memoria_constructiva, generar_presupuesto_estimado

        # Generar y mostrar memoria
        memoria = generar_memoria_constructiva(plan_json, superficie_finca)
        with st.expander("📄 Ver Memoria Constructiva Completa", expanded=False):
            st.code(memoria, language="text")

        # Generar y mostrar presupuesto
        presupuesto = generar_presupuesto_estimado(plan_json)
        col_pres1, col_pres2 = st.columns(2)

        with col_pres1:
            st.metric("Superficie Total", f"{presupuesto['superficie_total']:.1f} m²")
            st.metric("Coste por m²", f"€{presupuesto['coste_m2']:.0f}")
            st.metric("Subtotal Obra", f"€{presupuesto['subtotal_obra']:,.0f}")

        with col_pres2:
            st.metric("Honorarios", f"€{presupuesto['honorarios_profesionales']:,.0f}")
            st.metric("Impuestos", f"€{presupuesto['impuestos']:,.0f}")
            st.metric("Total Estimado", f"€{presupuesto['total_estimado']:,.0f}")

        st.info(f"💡 {presupuesto['nota']}")

        # --- Pago y exportación ---
        st.markdown("---")
        st.subheader("💳 Pago y Exportación")

        # Inicializar estado de pago
        init_pago_state()

        # Renderizar interfaz de pago
        render_paso_pago()

        # Verificar si el pago está completado
        if verificar_pago():
            st.success("✅ Pago verificado. Puedes descargar la documentación.")

            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                # Descargar memoria como PDF (placeholder)
                st.download_button(
                    label="📄 Descargar Memoria Constructiva (PDF)",
                    data=memoria.encode("utf-8"),
                    file_name="memoria_constructiva.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            with col_exp2:
                # Descargar plan como DXF generado por IA
                if st.button("🖼️ Generar y Descargar Plan DXF (CAD)", use_container_width=True):
                    with st.spinner("Generando plano CAD con IA..."):
                        dxf_content = generar_plano_cad(plan_json)
                        st.download_button(
                            label="💾 Descargar DXF generado",
                            data=dxf_content.encode("utf-8"),
                            file_name="planta_mvp.dxf",
                            mime="application/octet-stream",
                            use_container_width=True,
                            help="Plano CAD generado por IA en formato DXF"
                        )
                        st.success("✅ Plano DXF generado y listo para descargar!")

            st.info("📋 Próximas integraciones: Exportación real a PDF con formato profesional. DXF generado por IA listo para AutoCAD/LibreCAD.")

        else:
            st.warning("💳 Completa el pago para habilitar las descargas de documentación.")

        # --- Exportación (mantener funcionalidad existente) ---
        st.markdown("---")
        st.subheader("📄 Exportar Plan")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if st.button("📄 Exportar a PDF", use_container_width=True):
                st.info("Funcionalidad de exportación PDF próximamente...")
        with col_exp2:
            if st.button("🖼️ Exportar a CAD/DWG", use_container_width=True):
                st.info("Funcionalidad de exportación CAD próximamente...")

    st.markdown("---")
    # === FIN SECCIÓN MVP ===

    # Puente inteligente con marketplace existente (funcionalidad original)
    st.subheader("📍 Análisis Avanzado de Parcela Existente")
    plots = list_published_plots()

    if not plots:
        st.warning("No hay parcelas disponibles en el marketplace. Primero registra algunas parcelas.")
        return

    plot_options = {f"{p['title']} ({p['surface_m2']} m² - {p.get('location', 'Ubicación no especificada')})": p
                   for p in plots}
    selected_plot_name = st.selectbox("Selecciona una parcela del marketplace:",
                                     list(plot_options.keys()),
                                     key="gemelo_parcela_select_avanzado")
    selected_plot = plot_options[selected_plot_name] if selected_plot_name else None

    if selected_plot:
        # Mostrar información de la parcela
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Superficie", f"{selected_plot['surface_m2']} m²")
            st.metric("Precio", f"€{selected_plot['price']}")
            st.write(f"**Urbana:** {'Sí' if selected_plot.get('is_urban') else 'No'}")
            if selected_plot.get('cadastral_ref'):
                st.write(f"**Referencia:** {selected_plot['cadastral_ref']}")

        with col2:
            # Placeholder para ubicación (podría integrar mapa real)
            st.info("📍 Ubicación de la parcela seleccionada")

        st.markdown("---")

        # 🎯 NUEVO: Generador Interactivo de Plan de Vivienda
        st.subheader("🏠 Diseña Tu Vivienda - Guía Paso a Paso")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("**📋 Especificaciones de tu hogar**")

            # Sliders interactivos para el diseño
            num_habitaciones = st.slider("Número de habitaciones", 1, 6, 3, key="num_hab")
            num_banos = st.slider("Número de baños", 1, 4, 2, key="num_banos")
            con_garage = st.checkbox("Incluir garage", value=True, key="con_garage")
            presupuesto_max = st.slider("Presupuesto máximo (€)", 50000, 500000, 150000, key="presupuesto")

            # Botón para generar plan
            if st.button("🚀 Generar Plan de Vivienda con IA", type="primary", key="generar_plan"):
                with st.spinner("🎨 Creando distribución óptima con IA..."):
                    plan_generado = generar_plan_vivienda(
                        selected_plot, num_habitaciones, num_banos,
                        con_garage, presupuesto_max
                    )
                    st.session_state['plan_vivienda'] = plan_generado
                    st.success("✅ Plan generado exitosamente!")

        with col2:
            # Mostrar plan generado si existe
            if 'plan_vivienda' in st.session_state:
                plan = st.session_state['plan_vivienda']

                if 'distribucion' in plan:
                    st.markdown("**📐 Distribución Generada**")

                    # Mostrar resumen
                    metricas = plan.get('metricas', {})
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Superficie Construida", f"{metricas.get('total_m2_construidos', 0)} m²")
                    with col_b:
                        st.metric("Presupuesto Estimado", f"€{metricas.get('presupuesto_estimado', 0):,}")
                    with col_c:
                        st.metric("Tiempo Construcción", f"{metricas.get('tiempo_construccion_meses', 0)} meses")

                    # Mostrar habitaciones en una tabla bonita
                    st.markdown("**🏠 Habitaciones del Plan**")
                    for hab in plan['distribucion']:
                        tipo_icon = {
                            'salon': '🛋️', 'dormitorio': '🛏️', 'cocina': '🍳',
                            'bano': '🚿', 'garage': '🚗'
                        }.get(hab['tipo'], '🏠')

                        st.markdown(f"{tipo_icon} **{hab['nombre']}** - {hab['m2']} m²")
                        if 'descripcion' in hab:
                            st.caption(hab['descripcion'])

                    # Validaciones
                    validaciones = plan.get('validaciones', {})
                    if validaciones.get('cumple_normativa'):
                        st.success("✅ Diseño cumple normativa urbanística")
                    else:
                        st.warning("⚠️ Revisar cumplimiento normativo")

                else:
                    st.error("Error en el formato del plan generado")
            else:
                st.info("👆 Configura tus preferencias y genera un plan personalizado")

        st.markdown("---")

        # Análisis del gemelo digital (existente)
        st.subheader("🎛️ Parámetros del Gemelo Digital")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🌡️ Condiciones Ambientales**")
            temperatura = st.slider("Temperatura exterior (°C)", -10, 45, 20, key="temp_gemelo")
            humedad = st.slider("Humedad relativa (%)", 0, 100, 60, key="hum_gemelo")
            orientacion = st.selectbox("Orientación principal", ["Norte", "Sur", "Este", "Oeste"], key="ori_gemelo")

        with col2:
            st.markdown("**👥 Uso y Ocupación**")
            ocupacion = st.slider("Nº ocupantes", 1, 12, 4, key="ocup_gemelo")
            uso_principal = st.selectbox("Uso principal", ["Vivienda", "Oficina", "Comercial", "Mixto"], key="uso_gemelo")
            horario_uso = st.selectbox("Horario de uso", ["Diurno", "Nocturno", "24h", "Esporádico"], key="hora_gemelo")

        with col3:
            st.markdown("**🏗️ Características Constructivas**")
            eficiencia_objetivo = st.selectbox("Eficiencia energética objetivo",
                                             ["A+", "A", "B", "C", "D"], key="efic_gemelo")
            material_muros = st.selectbox("Material principal muros",
                                        ["Madera", "Ladrillo", "Hormigón", "Bloque"], key="mat_gemelo")
            sistema_clima = st.checkbox("Sistema climatización", key="clima_gemelo")
            paneles_solares = st.checkbox("Paneles solares", key="solar_gemelo")
            aerotermia = st.checkbox("Aerotermia", key="aero_gemelo")
            geotermia = st.checkbox("Geotermia", key="geo_gemelo")
            lluvia = st.checkbox("Recuperación agua lluvia", key="rain_gemelo")
            aislamiento = st.checkbox("Aislamiento natural", key="ins_gemelo")
            domotica = st.checkbox("Domótica", key="domo_gemelo")

        # Botón de análisis IA
        if st.button("🚀 Analizar Gemelo Digital con IA", type="primary", key="analizar_gemelo"):
            analizar_gemelo_digital(selected_plot, temperatura, humedad, orientacion,
                                  ocupacion, uso_principal, horario_uso, eficiencia_objetivo,
                                  material_muros, sistema_clima, paneles_solares)

        # Visualización 3D del gemelo
        st.markdown("---")
        st.subheader("🏗️ Visualización 3D del Gemelo Digital")

        # Si hay un plan de vivienda generado por IA, usar la nueva visualización 3D
        if 'plan_vivienda' in st.session_state and st.session_state['plan_vivienda']:
            plan_actual = st.session_state['plan_vivienda']
            if 'distribucion' in plan_actual:
                # Convertir el formato del plan a JSON compatible con create_gemelo_3d
                plan_json = {
                    "habitaciones": [
                        {
                            "nombre": hab["nombre"],
                            "m2": hab["m2"]
                        } for hab in plan_actual["distribucion"]
                        if hab["tipo"] != "garage"
                    ]
                }
                # añadir garage
                # (se añade más abajo)
                
                # incluir datos energéticos seleccionados
                energy_list = []
                if paneles_solares: energy_list.append("solar")
                if 'aerotermia' in locals() and aerotermia: energy_list.append("aerotermia")
                if 'geotermia' in locals() and geotermia: energy_list.append("geotermia")
                if 'lluvia' in locals() and lluvia: energy_list.append("rainwater")
                if 'aislamiento' in locals() and aislamiento: energy_list.append("insulation")
                if 'domotica' in locals() and domotica: energy_list.append("domotic")
                if energy_list:
                    plan_json["energy_systems"] = energy_list
                    # calcular coste usando misma dict si disponible
                    try:
                        from modules.ai_house_designer.flow import ENERGY_COSTS
                        cost = sum(ENERGY_COSTS.get(e,0) for e in energy_list if e != 'solar')
                        # panel solar no lo añadimos aquí; coste ya en plan_vivienda?
                        plan_json["energy_extras_cost"] = cost
                    except Exception:
                        pass

                # Añadir garage si existe
                garage_hab = next((h for h in plan_actual["distribucion"] if h["tipo"] == "garage"), None)
                if garage_hab:
                    plan_json["garage"] = {"m2": garage_hab["m2"]}

                # Crear visualización 3D del plan generado por IA
                fig = create_gemelo_3d(plan_json, selected_plot)
                st.plotly_chart(fig, use_container_width=True)

                st.info("💡 **Visualización IA**: Este modelo 3D muestra el plan generado automáticamente basado en tus preferencias.")
            else:
                # Fallback a la visualización tradicional si no hay distribución detallada
                fig = crear_visualizacion_gemelo(selected_plot, temperatura, ocupacion,
                                               material_muros, sistema_clima, paneles_solares, plan_actual)
                st.plotly_chart(fig, use_container_width=True)
        else:
            # Visualización tradicional del gemelo sin plan específico
            fig = crear_visualizacion_gemelo(selected_plot, temperatura, ocupacion,
                                           material_muros, sistema_clima, paneles_solares, None)
            st.plotly_chart(fig, use_container_width=True)

        # Información adicional
        with st.expander("ℹ️ Acerca del Gemelo Digital"):
            st.markdown("""
            **¿Qué es un Gemelo Digital?**
            - Réplica virtual inteligente de tu proyecto
            - Se alimenta de datos reales y simulados
            - Permite análisis predictivo y optimización

            **Beneficios:**
            - ✅ Optimización energética antes de construir
            - ✅ Análisis de eficiencia y sostenibilidad
            - ✅ Simulación de diferentes escenarios
            - ✅ Recomendaciones basadas en IA

            **Próximas ampliaciones:**
            - Integración con sensores IoT reales
            - Análisis de ciclo de vida del edificio
            - Simulaciones climáticas avanzadas
            - Certificaciones energéticas automáticas
            """)

def analizar_gemelo_digital(plot, temp, hum, ori, ocup, uso, horario, efic, mat, clima, solar):
    """Análisis inteligente del gemelo digital usando IA"""

    # Crear prompt detallado para IA
    prompt = f"""
    ERES UN ARQUITECTO Y ENGENIERO ESPECIALISTA EN EFICIENCIA ENERGÉTICA.

    Analiza este GEMENO DIGITAL de proyecto arquitectónico:

    **DATOS DE LA PARCELA:**
    - Superficie: {plot['surface_m2']} m²
    - Ubicación: {plot.get('location', 'No especificada')}
    - Tipo: {'Urbana' if plot.get('is_urban') else 'Rústica'}
    - Precio: €{plot['price']}

    **CONDICIONES AMBIENTALES:**
    - Temperatura exterior: {temp}°C
    - Humedad relativa: {hum}%
    - Orientación principal: {ori}

    **USO Y OCUPACIÓN:**
    - Número de ocupantes: {ocup}
    - Uso principal: {uso}
    - Horario de uso: {horario}

    **CARACTERÍSTICAS CONSTRUCTIVAS:**
    - Eficiencia energética objetivo: {efic}
    - Material principal muros: {mat}
    - Sistema climatización: {'Sí' if clima else 'No'}
    - Paneles solares: {'Sí' if solar else 'No'}

    **ANÁLISIS REQUERIDO:**
    1. **EFICIENCIA ENERGÉTICA ESTIMADA**: Califica (A+, A, B, C, D) y justifica
    2. **CONSUMO ENERGÉTICO ANUAL**: Estima kWh/año y €/año aproximado
    3. **RECOMENDACIONES DE MEJORA**: 3-5 sugerencias concretas y prioritarias
    4. **IMPACTO AMBIENTAL**: Emisiones CO2 estimadas y comparación con estándar
    5. **OPTIMIZACIONES ARQUITECTÓNICAS**: Mejoras en distribución, orientación, materiales

    **FORMATO DE RESPUESTA:**
    - Usa viñetas y encabezados claros
    - Sé específico y cuantitativo cuando sea posible
    - Incluye cálculos aproximados basados en normativa española
    - Prioriza soluciones realistas y económicamente viables
    """

    with st.spinner("🤖 IA analizando el gemelo digital... Esto puede tomar unos segundos"):
        try:
            analisis = get_ai_response(prompt)

            # Mostrar resultados
            st.success("✅ Análisis completado exitosamente!")

            # Tabs para organizar resultados
            tab1, tab2, tab3 = st.tabs(["📊 Eficiencia Energética", "💡 Recomendaciones", "🌱 Impacto Ambiental"])

            with tab1:
                st.subheader("📊 Evaluación Energética")
                # Aquí podríamos extraer métricas específicas del análisis
                st.write(analisis)

            with tab2:
                st.subheader("💡 Recomendaciones de Optimización")
                st.info("Las recomendaciones específicas se incluyen en el análisis completo arriba.")

            with tab3:
                st.subheader("🌱 Impacto Ambiental")
                st.info("El análisis ambiental detallado está incluido arriba.")

            # Guardar análisis en session_state para posibles exportaciones
            st.session_state['gemelo_analisis'] = {
                'plot': plot,
                'parametros': {
                    'temperatura': temp, 'humedad': hum, 'orientacion': ori,
                    'ocupacion': ocup, 'uso': uso, 'horario': horario,
                    'eficiencia': efic, 'material': mat, 'clima': clima, 'solar': solar
                },
                'analisis_ia': analisis,
                'timestamp': str(st.session_state.get('timestamp', 'now'))
            }

        except Exception as e:
            st.error(f"❌ Error en el análisis IA: {str(e)}")
            st.info("Verifica que la API key de OpenRouter esté configurada correctamente.")

def crear_visualizacion_gemelo(plot, temp, ocup, mat, clima, solar, plan_vivienda=None):
    """Crea visualización 3D dinámica del gemelo digital con habitaciones individuales"""

    # Inicialización segura de variables base
    altura_base = 3  # Altura por planta por defecto (3 metros)
    # Nota: En futuras versiones, altura_base podría calcularse dinámicamente
    # basado en material, ocupación o normativa local (ej: altura_base = 2.8 si mat == 'Madera')

    fig = go.Figure()

    # Dimensiones base adaptadas a la parcela
    superficie = plot['surface_m2']
    lado = (superficie ** 0.5) * 0.8  # Aproximación cuadrada con factor de edificabilidad

    # Base de la parcela
    fig.add_trace(go.Mesh3d(
        x=[0, lado, lado, 0],
        y=[0, 0, lado, lado],
        z=[0, 0, 0, 0],
        i=[0, 0], j=[1, 2], k=[2, 3],
        color='lightgreen',
        name='Parcela',
        opacity=0.3
    ))

    if plan_vivienda and 'distribucion' in plan_vivienda:
        # Visualización avanzada con habitaciones del plan
        habitaciones = plan_vivienda['distribucion']

        # Colores por tipo de habitación
        colores_por_tipo = {
            'salon': 'lightblue',
            'dormitorio': 'lightcoral',
            'cocina': 'orange',
            'bano': 'lightcyan',
            'garage': 'gray',
            'terraza': 'green',
            'pasillo': 'beige'
        }

        # Calcular posiciones y tamaños
        total_m2 = sum(h['m2'] for h in habitaciones if h['tipo'] != 'garage')
        lado_edificio = min(lado * 0.8, (total_m2 ** 0.5) * 1.2)

        # Posicionar habitaciones en una distribución lógica
        habitaciones_posicionadas = posicionar_habitaciones(habitaciones, lado_edificio)

        for hab in habitaciones_posicionadas:
            tipo = hab['tipo']
            color = colores_por_tipo.get(tipo, 'lightgray')

            # Crear cubo para cada habitación
            x0, y0 = hab['pos_x'], hab['pos_y']
            ancho, largo = hab['ancho'], hab['largo']
            altura = 3  # Altura estándar

            # Vertices del cubo
            x = [x0, x0+ancho, x0+ancho, x0, x0, x0+ancho, x0+ancho, x0]
            y = [y0, y0, y0+largo, y0+largo, y0, y0, y0+largo, y0+largo]
            z = [0, 0, 0, 0, altura, altura, altura, altura]

            fig.add_trace(go.Mesh3d(
                x=x, y=y, z=z,
                i=[0, 0, 0, 1, 4, 4, 2, 6, 4, 0, 3, 7],
                j=[1, 2, 3, 2, 5, 6, 6, 5, 1, 5, 2, 6],
                k=[2, 3, 0, 3, 6, 7, 3, 2, 6, 1, 6, 2],
                color=color,
                name=f"{hab['nombre']} ({hab['m2']}m²)",
                opacity=0.8,
                hovertext=f"{hab['nombre']}<br>{hab['m2']} m²<br>{hab.get('descripcion', '')}"
            ))

            # Añadir etiqueta de texto
            fig.add_trace(go.Scatter3d(
                x=[x0 + ancho/2],
                y=[y0 + largo/2],
                z=[altura + 0.5],
                mode='text',
                text=[hab['nombre']],
                textposition="middle center",
                showlegend=False
            ))

    else:
        # Visualización básica anterior (cuando no hay plan detallado)
        # altura_base ya está inicializada al principio de la función
        pass

    plantas = max(1, min(3, ocup // 2))  # Estimación de plantas basada en ocupación
    altura_total = plantas * altura_base

    # Color adaptado al material
    colores_material = {
        'Madera': 'saddlebrown',
        'Ladrillo': 'firebrick',
        'Hormigón': 'gray',
        'Bloque': 'lightgray'
    }
    color_edificio = colores_material.get(mat, 'lightblue')

    # Estructura del edificio
    ancho_edificio = lado * 0.6
    largo_edificio = lado * 0.7

    fig.add_trace(go.Mesh3d(
        x=[lado*0.2, lado*0.2+ancho_edificio, lado*0.2+ancho_edificio, lado*0.2,
           lado*0.2, lado*0.2+ancho_edificio, lado*0.2+ancho_edificio, lado*0.2],
        y=[lado*0.15, lado*0.15, lado*0.15+largo_edificio, lado*0.15+largo_edificio,
           lado*0.15, lado*0.15, lado*0.15+largo_edificio, lado*0.15+largo_edificio],
        z=[0, 0, 0, 0, altura_total, altura_total, altura_total, altura_total],
        i=[0, 0, 0, 1, 4, 4, 2, 6, 4, 0, 3, 7],
        j=[1, 2, 3, 2, 5, 6, 6, 5, 1, 5, 2, 6],
        k=[2, 3, 0, 3, 6, 7, 3, 2, 5, 1, 6, 2],
        color=color_edificio,
        name=f'Edificio ({plantas} plantas)',
        opacity=0.8
    ))

    # Indicadores dinámicos
    indicadores = []

    # Temperatura
    color_temp = 'blue' if temp < 15 else 'red' if temp > 25 else 'orange'
    indicadores.append({
        'x': [lado*0.5], 'y': [lado*0.5], 'z': [altura_total + 1],
        'text': [f'🌡️ {temp}°C'],
        'color': color_temp
    })

    # Sistema climatización
    if clima:
        indicadores.append({
            'x': [lado*0.3], 'y': [lado*0.8], 'z': [altura_total + 0.5],
            'text': ['❄️ Climatización'],
            'color': 'lightblue'
        })

    # Paneles solares
    if solar:
        # Representar paneles en el techo
        fig.add_trace(go.Mesh3d(
            x=[lado*0.25, lado*0.75, lado*0.75, lado*0.25],
            y=[lado*0.2, lado*0.2, lado*0.3, lado*0.3],
            z=[altura_total, altura_total, altura_total, altura_total],
            i=[0, 0], j=[1, 2], k=[2, 3],
            color='darkblue',
            name='Paneles Solares',
            opacity=0.9
        ))

    # Añadir indicadores
    for ind in indicadores:
        fig.add_trace(go.Scatter3d(
            x=ind['x'], y=ind['y'], z=ind['z'],
            mode='markers+text',
            text=ind['text'],
            textposition="top center",
            marker=dict(size=8, color=ind['color'])
        ))

    # Configuración de la escena
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (m)', autorange=True),
            yaxis=dict(title='Largo (m)', autorange=True),
            zaxis=dict(title='Altura (m)', autorange=True),
            aspectmode='data'
        ),
        title=f"Gemelo Digital - {plot['title']} ({superficie} m²)",
        height=600,
        showlegend=True
    )

    # Añadir controles de ayuda
    fig.update_layout(
        scene=dict(
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        )
    )

    return fig

def posicionar_habitaciones(habitaciones, lado_edificio):
    """Posiciona habitaciones en el plano de forma lógica"""
    habitaciones_posicionadas = []
    x_actual = 0
    y_actual = 0
    fila_altura = 0

    for hab in habitaciones:
        m2 = hab['m2']
        lado_cuadrado = m2 ** 0.5  # Aproximación cuadrada

        # Si no cabe en la fila actual, pasar a nueva fila
        if x_actual + lado_cuadrado > lado_edificio:
            x_actual = 0
            y_actual += fila_altura
            fila_altura = lado_cuadrado

        hab_pos = hab.copy()
        hab_pos.update({
            'pos_x': x_actual,
            'pos_y': y_actual,
            'ancho': lado_cuadrado,
            'largo': lado_cuadrado
        })

        habitaciones_posicionadas.append(hab_pos)
        x_actual += lado_cuadrado
        fila_altura = max(fila_altura, lado_cuadrado)

    return habitaciones_posicionadas


def create_gemelo_3d(plan_json: dict, selected_finca: dict = None):
    """
    Renderiza un modelo 3D básico de la vivienda a partir del JSON de la IA.
    - Centra los cubos en la parcela.
    - Escala visualmente los cubos para que se vean proporcionados.
    - Superpone los cubos sobre el plano base de la parcela.
    """

    fig = go.Figure()

    # ✅ Dimensiones de la parcela desde selected_finca o valores por defecto
    if selected_finca and "solar_virtual" in selected_finca:
        ancho_parcela = selected_finca["solar_virtual"].get("ancho", 100)
        largo_parcela = selected_finca["solar_virtual"].get("largo", 100)
    else:
        ancho_parcela = 100
        largo_parcela = 100

    # ✅ Coordenadas base de la parcela usando dimensiones reales
    parcela_x = [0, ancho_parcela, ancho_parcela, 0, 0]
    parcela_y = [0, 0, largo_parcela, largo_parcela, 0]
    parcela_z = [0] * len(parcela_x)

    fig.add_trace(go.Scatter3d(
        x=parcela_x,
        y=parcela_y,
        z=parcela_z,
        mode="lines",
        line=dict(color="brown", width=4),
        name="Parcela"
    ))

    # ✅ Centro de la parcela
    centro_x = ancho_parcela / 2
    centro_y = largo_parcela / 2

    # ✅ Escala visual para que los cubos se vean bien
    escala_visual = 2.5

    # ✅ Posición inicial relativa al centro
    offset_x = -20
    offset_y = -20

    colores = ["lightblue", "lightgreen", "lightpink", "lightyellow", "lavender", "beige", "lightgray"]

    # ✅ Dibujar habitaciones
    if "habitaciones" in plan_json:
        for idx, hab in enumerate(plan_json["habitaciones"]):
            nombre = hab.get("nombre", f"Habitación {idx+1}")
            m2 = hab.get("m2", 10)

            lado = int((m2) ** 0.5) * escala_visual
            altura = 3

            x0 = centro_x + offset_x
            x1 = x0 + lado
            y0 = centro_y + offset_y
            y1 = y0 + lado
            z0, z1 = 0, altura

            fig.add_trace(go.Mesh3d(
                x=[x0, x1, x1, x0, x0, x1, x1, x0],
                y=[y0, y0, y1, y1, y0, y0, y1, y1],
                z=[z0, z0, z0, z0, z1, z1, z1, z1],
                i=[0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 4, 5],
                j=[1, 2, 3, 5, 6, 7, 5, 6, 7, 6, 0, 1],
                k=[2, 3, 0, 6, 7, 4, 6, 7, 4, 7, 5, 2],
                opacity=0.5,
                color=random.choice(colores),
                name=nombre
            ))

            fig.add_trace(go.Scatter3d(
                x=[(x0+x1)/2], y=[(y0+y1)/2], z=[altura+0.5],
                mode="text",
                text=[f"{nombre} ({m2} m²)"],
                textposition="top center"
            ))

            offset_x += lado + 5  # Separación entre cubos

    # ✅ Dibujar garage si existe
    if "garage" in plan_json:
        m2 = plan_json["garage"].get("m2", 20)
        lado = int((m2) ** 0.5) * escala_visual
        altura = 3

        x0 = centro_x + offset_x
        x1 = x0 + lado
        y0 = centro_y + offset_y
        y1 = y0 + lado
        z0, z1 = 0, altura

        fig.add_trace(go.Mesh3d(
            x=[x0, x1, x1, x0, x0, x1, x1, x0],
            y=[y0, y0, y1, y1, y0, y0, y1, y1],
            z=[z0, z0, z0, z0, z1, z1, z1, z1],
            i=[0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 4, 5],
            j=[1, 2, 3, 5, 6, 7, 5, 6, 7, 6, 0, 1],
            k=[2, 3, 0, 6, 7, 4, 6, 7, 4, 7, 5, 2],
            opacity=0.5,
            color="gray",
            name="Garage"
        ))

        fig.add_trace(go.Scatter3d(
            x=[(x0+x1)/2], y=[(y0+y1)/2], z=[altura+0.5],
            mode="text",
            text=[f"Garage ({m2} m²)"],
            textposition="top center"
        ))

    fig.update_layout(scene=dict(
        xaxis_title="Ancho (m)",
        yaxis_title="Largo (m)",
        zaxis_title="Altura (m)"
    ))

    return fig