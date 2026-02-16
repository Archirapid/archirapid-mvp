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
    st.header("Paso 1 – Necesidades y preferencias del cliente")
    
    # Mostrar elementos añadidos automáticamente en la sesión anterior
    if 'validation_missing_items' in st.session_state:
        missing = st.session_state['validation_missing_items']
        st.success(f"✅ **Elementos añadidos automáticamente:** {', '.join(missing)}")
        # Limpiar para no mostrarlo de nuevo
        del st.session_state['validation_missing_items']
    
    # Mostrar información de la parcela si está disponible
    plot_data = st.session_state.get("design_plot_data")
    if plot_data:
        st.info(f"📍 **Diseñando para:** {plot_data['title']} | "
                f"Parcela: {plot_data['total_m2']:.0f} m² | "
                f"**Máximo edificable:** {plot_data['buildable_m2']:.0f} m² (33% de la parcela)")
    
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
        
        # Límite de edificabilidad según parcela
        plot_data = st.session_state.get("design_plot_data")
        max_allowed = plot_data['buildable_m2'] if plot_data else 400.0
        
        req["target_area_m2"] = st.number_input(
            "Superficie objetivo (m²)",
            min_value=40.0,
            max_value=float(max_allowed),
            value=min(float(req.get("target_area_m2", 120.0)), float(max_allowed)),
            step=5.0,
            help=f"Máximo edificable en esta parcela: {max_allowed:.0f} m²" if plot_data else None
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
        
        st.markdown("**🌿 Materiales sostenibles:**")
        
        # Lista temporal para guardar selecciones
        selected_sustainable = []
        
        col_sust1, col_sust2 = st.columns(2)
        with col_sust1:
            if st.checkbox("☀️ Paneles solares", 
                          value='Paneles solares' in req.get("sustainable_materials", []),
                          key="check_paneles"):
                selected_sustainable.append("Paneles solares")
            
            if st.checkbox("🔥 Bomba de calor", 
                          value='Bomba de calor' in req.get("sustainable_materials", []),
                          key="check_bomba"):
                selected_sustainable.append("Bomba de calor")
        
        with col_sust2:
            if st.checkbox("🌿 Aislamiento natural", 
                          value='Aislamiento natural' in req.get("sustainable_materials", []),
                          key="check_aislamiento"):
                selected_sustainable.append("Aislamiento natural")
            
            if st.checkbox("💧 Recuperación de agua", 
                          value='Recuperación de agua' in req.get("sustainable_materials", []),
                          key="check_agua"):
                selected_sustainable.append("Recuperación de agua")
        
        # Guardar en req
        req["sustainable_materials"] = selected_sustainable
    
    # Actualizar session state con los valores introducidos
    st.session_state["ai_house_requirements"] = req
    
    # Separador visual
    st.markdown("---")
    st.info("🔗 **Gemelos Digitales UE** - Preparado para Testear fondos")
    
    st.markdown("---")
    
    col_btn, col_cont = st.columns([1, 3])
    with col_btn:
        if st.button("🤖 Analizar preferencias con IA", type="secondary"):
            try:
                from dotenv import load_dotenv
                import os
                import json
                from groq import Groq
                from pathlib import Path
                
                # Ruta absoluta a la raíz del proyecto
                import sys
                project_root = Path(__file__).parent.parent.parent
                env_path = project_root / '.env'
                
                # DEBUG: Mostrar ruta calculada
                print(f"DEBUG: Buscando .env en: {env_path}")
                print(f"DEBUG: ¿Existe el archivo? {env_path.exists()}")
                
                load_dotenv(dotenv_path=env_path)
                
                # Verificar todas las variables de entorno que empiecen con GROQ
                import os
                print(f"DEBUG: Variables GROQ encontradas: {[k for k in os.environ.keys() if 'GROQ' in k]}")
                
                groq_api_key = os.getenv("GROQ_API_KEY")
                
                # DEBUG: Verificar que se cargó
                if not groq_api_key:
                    # Intentar cargar desde ruta actual
                    load_dotenv()
                    groq_api_key = os.getenv("GROQ_API_KEY")
                
                if not groq_api_key:
                    st.error("❌ GROQ_API_KEY no encontrada. Verifica tu archivo .env")
                    st.info(f"Buscando .env en: {env_path}")
                    st.stop()
                
                client = Groq(api_key=groq_api_key)
                
                prompt = f"""Eres un arquitecto español experto. Diseña una vivienda COMPLETA basándote EXACTAMENTE en estas preferencias:

**DATOS DEL CLIENTE:**
- Superficie objetivo: {req['target_area_m2']} m² (DEBE aproximarse a esta cifra)
- Presupuesto: €{req.get('budget_limit', 0):,.0f}
- Dormitorios: {req['bedrooms']} (incluir 1 principal + {req['bedrooms']-1} secundarios)
- Baños: {req['bathrooms']}
- Plantas: {req['max_floors']}
- Estilo: {req['style']}
- Orientación: {req.get('orientation', 'Sur')}
- Cubierta: {req.get('roof_type', 'A dos aguas')}

**EXTRAS SOLICITADOS (OBLIGATORIO incluir):**
{f"- PISCINA: 25-30 m² (obligatorio)" if req['wants_pool'] else ""}
{f"- PORCHE: 15-20 m² (obligatorio)" if req['wants_porch'] else ""}
{f"- GARAJE: 20-25 m² (obligatorio)" if req['wants_garage'] else ""}
{f"- CASA DE APEROS: 20 m² (obligatorio)" if req['wants_outhouse'] else ""}

**MATERIALES Y EXTRAS OBLIGATORIOS (el cliente los marcó - INCLUIR SÍ O SÍ):**
{f'''- ✅ PANELES SOLARES: 5-8 m² (OBLIGATORIO)
  Código en JSON: "paneles_solares": 6''' if 'Paneles solares' in req.get('sustainable_materials', []) else ""}
{f'''- ✅ BOMBA DE CALOR: incluir como instalación
  Código en JSON: "bomba_calor": 3''' if 'Bomba de calor' in req.get('sustainable_materials', []) else ""}
{f'''- ✅ AISLAMIENTO NATURAL: muros con aislamiento ecológico
  Código en JSON: "aislamiento_natural": 2''' if 'Aislamiento natural' in req.get('sustainable_materials', []) else ""}
{f'''- ✅ RECUPERACIÓN DE AGUA: sistema de reciclaje
  Código en JSON: "recuperacion_agua": 2''' if 'Recuperación de agua' in req.get('sustainable_materials', []) else ""}
{f'''- ✅ ACCESIBILIDAD: rampas, puertas anchas (90cm), baño adaptado
  Añadir 5-8 m² extra para pasillos amplios
  Código en JSON: "accesibilidad": 6''' if req.get('accessibility') else ""}

**MATERIALES DE CONSTRUCCIÓN PREFERIDOS:**
- Material principal: {', '.join(req.get('materials', ['hormigón']))}
- Estos materiales deben mencionarse en la descripción técnica
- Si incluye "ladrillo" → muros de carga de ladrillo cara vista
- Si incluye "hormigón" → estructura de hormigón armado
- Si incluye "madera" → estructura de madera laminada

**NOTAS ESPECIALES DEL CLIENTE:**
"{req['notes']}"

**INSTRUCCIONES CRÍTICAS:**
1. Si pide "bodega para X pax" → bodega de mínimo 12-15 m²
2. Dormitorio principal: 14-18 m²
3. Dormitorios secundarios: 10-12 m² cada uno
4. Baño completo: 5-6 m² cada uno
5. Salón-cocina integrado: 30-40 m² (núcleo social)
6. SIEMPRE incluir pasillo/distribuidor: 8-10 m²
7. La suma total debe aproximarse a {req['target_area_m2']} m²

**VALIDACIÓN OBLIGATORIA:**
- Si el cliente marcó "Paneles solares" → JSON DEBE incluir "paneles_solares": 6
- Si el cliente marcó "Accesibilidad" → JSON DEBE incluir "accesibilidad": 6
- Si el cliente pidió "bodega para X pax" → bodega mínimo 12-15 m²
- La suma total debe aproximarse a {req['target_area_m2']} m² (±10%)

**EJEMPLO DE RESPUESTA (para bodega 8 pax + piscina + porche + paneles):**
{{
  "salon_cocina": 38,
  "dormitorio_principal": 16,
  "dormitorio": 11,
  "dormitorio_2": 11,
  "bano": 6,
  "bano_2": 5,
  "bodega": 14,
  "piscina": 28,
  "porche": 18,
  "paneles_solares": 6,
  "pasillo": 9
}}

**RESPONDE SOLO JSON válido, sin markdown ni texto adicional.**
"""
                
                # ============================================
                # 🔍 DEBUG DE INPUTS
                # ============================================
                st.write("🔍 DEBUG - Materiales sostenibles marcados:", req.get('sustainable_materials', []))
                st.write("🔍 DEBUG - Accesibilidad marcada:", req.get('accessibility', False))
                st.write("🔍 DEBUG - Materiales construcción:", req.get('materials', []))
                
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
                
                # ============================================
                # 🔧 VALIDACIÓN PROTEGIDA (línea ~430)
                # ============================================
                try:
                    # SIEMPRE verificar y añadir elementos obligatorios
                    missing_items = []
                    
                    # Convertir propuesta a string para búsqueda
                    proposal_str = json.dumps(ai_proposal).lower()
                    
                    # Paneles solares
                    if 'Paneles solares' in req.get('sustainable_materials', []):
                        has_paneles = any([
                            'paneles_solares' in ai_proposal,
                            'paneles solares' in proposal_str,
                            'paneles' in proposal_str
                        ])
                        if not has_paneles:
                            ai_proposal['paneles_solares'] = 6
                            missing_items.append("☀️ Paneles solares (6 m²)")
                    
                    # Bomba de calor
                    if 'Bomba de calor' in req.get('sustainable_materials', []):
                        has_bomba = any([
                            'bomba_calor' in ai_proposal,
                            'bomba de calor' in proposal_str,
                            'bomba' in proposal_str
                        ])
                        if not has_bomba:
                            ai_proposal['bomba_calor'] = 3
                            missing_items.append("🔥 Bomba de calor (3 m²)")
                    
                    # Aislamiento natural
                    if 'Aislamiento natural' in req.get('sustainable_materials', []):
                        has_aislamiento = any([
                            'aislamiento_natural' in ai_proposal,
                            'aislamiento natural' in proposal_str,
                            'aislamiento' in proposal_str
                        ])
                        if not has_aislamiento:
                            ai_proposal['aislamiento_natural'] = 2
                            missing_items.append("🌿 Aislamiento natural (2 m²)")
                    
                    # Recuperación de agua
                    if 'Recuperación de agua' in req.get('sustainable_materials', []):
                        has_agua = any([
                            'recuperacion_agua' in ai_proposal,
                            'recuperacion de agua' in proposal_str,
                            'recuperacion' in proposal_str
                        ])
                        if not has_agua:
                            ai_proposal['recuperacion_agua'] = 2
                            missing_items.append("💧 Recuperación de agua (2 m²)")
                    
                    # Accesibilidad
                    if req.get('accessibility'):
                        has_accesibilidad = any([
                            'accesibilidad' in ai_proposal,
                            'accesible' in proposal_str,
                            'adaptada' in proposal_str
                        ])
                        if not has_accesibilidad:
                            ai_proposal['accesibilidad'] = 6
                            missing_items.append("♿ Accesibilidad (6 m²)")
                
                except Exception as val_error:
                    st.error(f"❌ ERROR CRÍTICO EN VALIDACIÓN: {val_error}")
                    import traceback
                    error_trace = traceback.format_exc()
                    st.code(error_trace)
                    st.warning("⚠️ La validación falló. Continuando sin añadir elementos.")
                    missing_items = []
                    
                    # DEBUG: Mostrar estado
                    st.write("🔍 Estado en el momento del error:")
                    st.write("- ai_proposal:", ai_proposal)
                    st.write("- req:", req)
                
                # Guardar missing_items y MOSTRAR ANTES DE RERUN
                if missing_items:
                    st.session_state['validation_missing_items'] = missing_items
                    st.warning(f"⚠️ **ELEMENTOS AÑADIDOS:** {', '.join(missing_items)}")
                    st.write("👉 La IA omitió estos elementos. Los hemos añadido automáticamente.")
                
                # DEBUG: Mostrar propuesta final
                st.write("🔍 DEBUG - Propuesta final completa:", ai_proposal)
                st.write("🔍 DEBUG - Total elementos:", len(ai_proposal))
                
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
        # ============================================
        # 🎨 PROPUESTA DE IA - DISEÑO PROFESIONAL
        # ============================================
        
        if req.get("ai_room_proposal"):
            # Calcular totales
            proposal = req["ai_room_proposal"]
            total_area = sum([v for v in proposal.values() if isinstance(v, (int, float))])
            target_area = req.get('target_area_m2', 120)
            budget = req.get('budget_limit', 0)
            
            # Estimación de coste (1200€/m² promedio construcción España)
            estimated_cost = total_area * 1200
            budget_status = "suficiente" if budget >= estimated_cost else "insuficiente"
            budget_diff = abs(budget - estimated_cost)
            
            # RESUMEN EJECUTIVO
            st.success("🏗️ **PROPUESTA ARQUITECTÓNICA GENERADA**")
            
            # Métricas principales
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Superficie Total", f"{total_area:.0f} m²", 
                         f"{((total_area/target_area - 1) * 100):+.0f}% vs objetivo")
            with col_m2:
                cost_color = "🟢" if budget >= estimated_cost else "🔴"
                st.metric("Coste Estimado", f"€{estimated_cost:,.0f}", 
                         f"{cost_color} {budget_status.title()}")
            with col_m3:
                if budget > 0:
                    if budget >= estimated_cost:
                        st.metric("Margen Disponible", f"€{budget_diff:,.0f}", 
                                 "Para acabados premium")
                    else:
                        st.metric("Déficit", f"€{budget_diff:,.0f}", 
                                 "⚠️ Revisar presupuesto")
            
            st.markdown("---")
            
            # ANÁLISIS DE IA
            st.markdown("### 🤖 Análisis del Arquitecto IA")
            
            analysis_parts = []
            
            # Analizar notas del cliente
            client_notes = req.get('notes', '').lower()
            if 'bodega' in client_notes:
                bodega_area = proposal.get('bodega', 0)
                if bodega_area >= 12:
                    analysis_parts.append(f"✅ **Bodega dimensionada correctamente** ({bodega_area} m²) - apropiada para eventos sociales y almacenaje de vino.")
                else:
                    analysis_parts.append(f"⚠️ **Bodega pequeña** ({bodega_area} m²) - podría ser insuficiente para 8 personas.")
            
            # Analizar presupuesto
            if budget > 0:
                if budget >= estimated_cost:
                    surplus = budget - estimated_cost
                    analysis_parts.append(f"💰 **Presupuesto holgado**: Dispone de €{surplus:,.0f} adicionales para acabados de lujo, domótica, o ampliar zonas exteriores.")
                elif budget >= estimated_cost * 0.9:
                    analysis_parts.append(f"⚠️ **Presupuesto ajustado**: El coste estimado se aproxima al límite. Recomendamos reservar 10% adicional para imprevistos.")
                else:
                    deficit = estimated_cost - budget
                    analysis_parts.append(f"🔴 **Presupuesto insuficiente**: Faltan €{deficit:,.0f}. Considere reducir superficie o usar materiales más económicos.")
            
            # Analizar distribución
            bedrooms_count = sum([1 for k in proposal.keys() if 'dormitorio' in k.lower()])
            bathrooms_count = sum([1 for k in proposal.keys() if 'bano' in k.lower()])
            
            if bedrooms_count == req.get('bedrooms', 3):
                analysis_parts.append(f"✅ **Dormitorios**: {bedrooms_count} habitaciones según lo solicitado - distribución óptima para familia.")
            
            if bathrooms_count == req.get('bathrooms', 2):
                analysis_parts.append(f"✅ **Baños**: {bathrooms_count} baños - cumple con la demanda funcional.")
            
            # Mostrar análisis
            for part in analysis_parts:
                st.markdown(part)
            
            st.markdown("---")
            
            # DISTRIBUCIÓN DE ESPACIOS - VISUAL
            st.markdown("### 📐 Distribución de Espacios")
            
            # Iconos por tipo de habitación
            room_icons = {
                'salon': '🏠', 'cocina': '🍳',
                'dormitorio': '🛏️', 'bano': '🚿',
                'bodega': '🍷', 'piscina': '🏊',
                'garaje': '🚗', 'porche': '🌿',
                'pasillo': '🚪', 'paneles': '☀️',
                'casa_apero': '🔧', 'huerto': '🌱',
                'bomba': '🔥', 'aislamiento': '🌿',
                'recuperacion': '💧', 'accesibilidad': '♿'
            }
            
            # Agrupar por categorías
            living_spaces = []
            private_spaces = []
            service_spaces = []
            outdoor_spaces = []
            sustainable_spaces = []
            
            for code, area in proposal.items():
                if not isinstance(area, (int, float)):
                    continue
                
                # Determinar icono
                icon = '📦'
                for key, emoji in room_icons.items():
                    if key in code.lower():
                        icon = emoji
                        break
                
                # Formatear nombre
                name = code.replace("_", " ").replace("salon", "Salón").replace("bano", "Baño").title()
                
                # Categorizar
                if any(x in code.lower() for x in ['salon', 'cocina']):
                    living_spaces.append((icon, name, area))
                elif any(x in code.lower() for x in ['dormitorio', 'bano']):
                    private_spaces.append((icon, name, area))
                elif any(x in code.lower() for x in ['garaje', 'bodega', 'pasillo']):
                    service_spaces.append((icon, name, area))
                elif any(x in code.lower() for x in ['piscina', 'porche', 'paneles', 'huerto']):
                    outdoor_spaces.append((icon, name, area))
                elif any(x in code.lower() for x in ['bomba', 'aislamiento', 'recuperacion', 'accesibilidad']):
                    sustainable_spaces.append((icon, name, area))
            
            # Mostrar por categorías
            if living_spaces:
                st.markdown("**🏠 Espacios Comunes**")
                cols = st.columns(len(living_spaces))
                for idx, (icon, name, area) in enumerate(living_spaces):
                    with cols[idx]:
                        st.markdown(f"<div style='background: #E3F2FD; padding: 15px; border-radius: 10px; text-align: center;'>"
                                   f"<div style='font-size: 2em;'>{icon}</div>"
                                   f"<div style='font-weight: bold;'>{name}</div>"
                                   f"<div style='color: #1976D2; font-size: 1.2em;'>{area} m²</div>"
                                   f"</div>", unsafe_allow_html=True)
            
            if private_spaces:
                st.markdown("**🛏️ Espacios Privados**")
                cols = st.columns(min(len(private_spaces), 4))
                for idx, (icon, name, area) in enumerate(private_spaces):
                    with cols[idx % 4]:
                        st.markdown(f"<div style='background: #F3E5F5; padding: 15px; border-radius: 10px; text-align: center;'>"
                                   f"<div style='font-size: 2em;'>{icon}</div>"
                                   f"<div style='font-weight: bold;'>{name}</div>"
                                   f"<div style='color: #7B1FA2; font-size: 1.2em;'>{area} m²</div>"
                                   f"</div>", unsafe_allow_html=True)
            
            if service_spaces:
                st.markdown("**🔧 Espacios de Servicio**")
                cols = st.columns(len(service_spaces))
                for idx, (icon, name, area) in enumerate(service_spaces):
                    with cols[idx]:
                        st.markdown(f"<div style='background: #FFF3E0; padding: 15px; border-radius: 10px; text-align: center;'>"
                                   f"<div style='font-size: 2em;'>{icon}</div>"
                                   f"<div style='font-weight: bold;'>{name}</div>"
                                   f"<div style='color: #F57C00; font-size: 1.2em;'>{area} m²</div>"
                                   f"</div>", unsafe_allow_html=True)
            
            if outdoor_spaces:
                st.markdown("**🌿 Espacios Exteriores**")
                cols = st.columns(len(outdoor_spaces))
                for idx, (icon, name, area) in enumerate(outdoor_spaces):
                    with cols[idx]:
                        st.markdown(f"<div style='background: #E8F5E9; padding: 15px; border-radius: 10px; text-align: center;'>"
                                   f"<div style='font-size: 2em;'>{icon}</div>"
                                   f"<div style='font-weight: bold;'>{name}</div>"
                                   f"<div style='color: #388E3C; font-size: 1.2em;'>{area} m²</div>"
                                   f"</div>", unsafe_allow_html=True)            
            if sustainable_spaces:
                st.markdown("**🌱 Sostenibilidad y Accesibilidad**")
                cols = st.columns(len(sustainable_spaces))
                for idx, (icon, name, area) in enumerate(sustainable_spaces):
                    with cols[idx]:
                        st.markdown(f"<div style='background: #E8F5E9; padding: 15px; border-radius: 10px; text-align: center;'>" 
                                   f"<div style='font-size: 2em;'>{icon}</div>"
                                   f"<div style='font-weight: bold;'>{name}</div>"
                                   f"<div style='color: #4CAF50; font-size: 1.2em;'>{area} m²</div>"
                                   f"</div>", unsafe_allow_html=True)    
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
    
    # Tipos de habitación CON PRECIOS REALES (formato explícito)
    room_types = {
        "salon_cocina": RoomType(
            code="salon_cocina",
            name="Salón-Cocina",
            min_m2=25,
            max_m2=50,
            base_cost_per_m2=1200
        ),
        "dormitorio_principal": RoomType(
            code="dormitorio_principal",
            name="Dormitorio Principal",
            min_m2=12,
            max_m2=25,
            base_cost_per_m2=1400
        ),
        "dormitorio": RoomType(
            code="dormitorio",
            name="Dormitorio",
            min_m2=8,
            max_m2=15,
            base_cost_per_m2=1100
        ),
        "bano": RoomType(
            code="bano",
            name="Baño",
            min_m2=4,
            max_m2=8,
            base_cost_per_m2=900
        ),
        "bodega": RoomType(
            code="bodega",
            name="Bodega",
            min_m2=6,
            max_m2=12,
            base_cost_per_m2=600
        ),
        "piscina": RoomType(
            code="piscina",
            name="Piscina",
            min_m2=20,
            max_m2=40,
            base_cost_per_m2=2500
        ),
        "paneles_solares": RoomType(
            code="paneles_solares",
            name="Paneles Solares",
            min_m2=3,
            max_m2=10,
            base_cost_per_m2=3000
        ),
        "garaje": RoomType(
            code="garaje",
            name="Garaje",
            min_m2=12,
            max_m2=25,
            base_cost_per_m2=900
        ),
        "casa_apero": RoomType(
            code="casa_apero",
            name="Casa de Aperos",
            min_m2=15,
            max_m2=30,
            base_cost_per_m2=800
        ),
        "huerto": RoomType(
            code="huerto",
            name="Huerto",
            min_m2=10,
            max_m2=50,
            base_cost_per_m2=150
        ),
        "porche": RoomType(
            code="porche",
            name="Porche",
            min_m2=10,
            max_m2=25,
            base_cost_per_m2=700
        ),
        "bomba_agua": RoomType(
            code="bomba_agua",
            name="Bomba de Agua",
            min_m2=2,
            max_m2=5,
            base_cost_per_m2=5000
        ),
        "cubierta": RoomType(
            code="cubierta",
            name="Cubierta Tejado",
            min_m2=80,
            max_m2=150,
            base_cost_per_m2=400
        ),
        "accesibilidad": RoomType(
            code="accesibilidad",
            name="Accesibilidad",
            min_m2=0,
            max_m2=10,
            base_cost_per_m2=2000
        )
    }
    
    # Inicializar diseño editable
    if "house_design" not in st.session_state:
        rooms = []
        for room_code, area in req["ai_room_proposal"].items():
            if not isinstance(area, (int, float)):
                continue
            
            # Buscar tipo coincidente (con similitud)
            room_type = None
            
            # 1. Busca coincidencia exacta
            if room_code in room_types:
                room_type = room_types[room_code]
            
            # 2. Busca por palabras clave
            else:
                code_lower = room_code.lower()
                
                # Mapeo de códigos similares
                if 'salon' in code_lower or 'cocina' in code_lower:
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
                elif 'aislamiento' in code_lower:
                    room_type = RoomType(room_code, room_code.replace("_", " ").title(), 1, 5, 1500)
                elif 'recuperacion' in code_lower or 'recuperación' in code_lower:
                    room_type = RoomType(room_code, room_code.replace("_", " ").title(), 1, 5, 1000)
                elif 'accesibilidad' in code_lower:
                    room_type = room_types['accesibilidad']
                elif 'pasillo' in code_lower:
                    room_type = RoomType(room_code, "Pasillo", 5, 15, 800)
                elif 'huerto' in code_lower:
                    room_type = room_types['huerto']
                elif 'apero' in code_lower or 'aperos' in code_lower:
                    room_type = room_types['casa_apero']
                else:
                    # Tipo genérico
                    room_type = RoomType(room_code, room_code.replace("_", " ").title(), 5, 50, 1000)
            
            # Crear instancia de habitación
            rooms.append(RoomInstance(room_type=room_type, area_m2=float(area)))
        
        st.session_state["house_design"] = HouseDesign(plot=plot, rooms=rooms)
    
    design = st.session_state["house_design"]
    
    # ============================================
    # 📊 RESUMEN DE DISTRIBUCIÓN (COMPACTO)
    # ============================================
    st.subheader("📊 Tu propuesta actual")
    
    # Crear DataFrame para tabla compacta
    import pandas as pd
    
    table_data = []
    for room in design.rooms:
        price_per_m2 = float(room.room_type.base_cost_per_m2) if hasattr(room.room_type, 'base_cost_per_m2') else 0
        cost = room.area_m2 * price_per_m2
        table_data.append({
            "Espacio": room.room_type.code.replace("_", " ").title(),
            "m²": f"{room.area_m2:.0f}",
            "€/m²": f"€{price_per_m2:,.0f}",
            "Total": f"€{cost:,.0f}"
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # ============================================
    # 🔧 AJUSTA MEDIDAS (2 COLUMNAS)
    # ============================================
    st.markdown("---")
    st.subheader("🔧 Ajusta medidas")
    
    # Dividir en 2 columnas
    for i in range(0, len(design.rooms), 2):
        col1, col2 = st.columns(2)
        
        # Slider izquierdo
        with col1:
            if i < len(design.rooms):
                room = design.rooms[i]
                new_area = st.slider(
                    f"{room.room_type.code.replace('_', ' ').title()}",
                    min_value=float(room.room_type.min_m2),
                    max_value=float(room.room_type.max_m2),
                    value=float(room.area_m2),
                    step=0.5,
                    key=f"slider_{i}",
                    help=f"Rango: {room.room_type.min_m2}-{room.room_type.max_m2} m²"
                )
                design.rooms[i].area_m2 = new_area
        
        # Slider derecho
        with col2:
            if i + 1 < len(design.rooms):
                room = design.rooms[i + 1]
                new_area = st.slider(
                    f"{room.room_type.code.replace('_', ' ').title()}",
                    min_value=float(room.room_type.min_m2),
                    max_value=float(room.room_type.max_m2),
                    value=float(room.area_m2),
                    step=0.5,
                    key=f"slider_{i+1}",
                    help=f"Rango: {room.room_type.min_m2}-{room.room_type.max_m2} m²"
                )
                design.rooms[i + 1].area_m2 = new_area
    
    # ============================================
    # 📊 MÉTRICAS EN TIEMPO REAL
    # ============================================
    st.markdown("---")
    
    # Calcular totales MANUALMENTE
    total_area = sum([r.area_m2 for r in design.rooms])
    total_cost = sum([r.area_m2 * r.room_type.base_cost_per_m2 for r in design.rooms])
    
    plot_data = st.session_state.get("design_plot_data")
    
    max_allowed = plot_data['buildable_m2'] if plot_data else 400.0
    
    col1, col2, col3 = st.columns(3)
    
    # Máximo edificable
    col1.metric("Máx. edificable", f"{max_allowed:.0f} m²")
    
    # Total diseñado (con color)
    delta_color = "normal" if total_area <= max_allowed else "inverse"
    col2.metric(
        "Total diseñado", 
        f"{total_area:.0f} m²",
        delta=f"{total_area - max_allowed:+.0f} m²",
        delta_color=delta_color
    )
    
    # Coste total
    col3.metric("Coste total", f"€{total_cost:,.0f}")
    
    # Validación de exceso
    if total_area > max_allowed:
        excess = total_area - max_allowed
        st.error(f"⚠️ **EXCESO:** Te has pasado {excess:.0f} m². Reduce habitaciones o elimina elementos.")
    elif total_area > max_allowed * 0.95:
        st.warning(f"⚠️ Estás cerca del límite ({total_area:.0f}/{max_allowed:.0f} m²)")
    else:
        st.success(f"✅ Dentro del límite ({total_area:.0f}/{max_allowed:.0f} m²)")
    
    st.markdown("---")
    
    # ============================================
    # ✂️ ELIMINAR ELEMENTOS OPCIONALES
    # ============================================
    st.subheader("✂️ Elementos opcionales")
    st.caption("Desmarca para eliminar del diseño y ahorrar presupuesto")
    
    # Identificar elementos opcionales (no esenciales)
    optional_elements = []
    for i, room in enumerate(design.rooms):
        code = room.room_type.code.lower()
        # Solo piscina, garaje, porche, casa aperos, paneles son opcionales
        if any(x in code for x in ['piscina', 'garaje', 'porche', 'casa', 'apero', 'paneles', 'bomba', 'aislamiento', 'recuperacion']):
            optional_elements.append((i, room))
    
    if optional_elements:
        # Mostrar en grid 2 columnas
        cols = st.columns(2)
        rooms_to_remove = []
        
        for idx, (room_idx, room) in enumerate(optional_elements):
            with cols[idx % 2]:
                # Nombre formateado
                room_name = room.room_type.code.replace("_", " ").title()
                
                # Icono
                icon = '📦'
                if 'piscina' in room.room_type.code.lower():
                    icon = '🏊'
                elif 'garaje' in room.room_type.code.lower():
                    icon = '🚗'
                elif 'porche' in room.room_type.code.lower():
                    icon = '🌿'
                elif 'paneles' in room.room_type.code.lower():
                    icon = '☀️'
                elif 'bomba' in room.room_type.code.lower():
                    icon = '🔥'
                elif 'aislamiento' in room.room_type.code.lower():
                    icon = '🌿'
                elif 'recuperacion' in room.room_type.code.lower():
                    icon = '💧'
                
                # Cálculo del ahorro
                cost_savings = room.area_m2 * room.room_type.base_cost_per_m2
                
                # Checkbox
                keep = st.checkbox(
                    f"{icon} **{room_name}** ({room.area_m2:.0f} m² = €{cost_savings:,.0f})",
                    value=True,
                    key=f"keep_{room_idx}",
                    help=f"Desmarcar para eliminar y ahorrar €{cost_savings:,.0f}"
                )
                
                if not keep:
                    rooms_to_remove.append(room_idx)
        
        # Eliminar habitaciones desmarcadas
        if rooms_to_remove:
            # Eliminar en orden inverso para no desajustar índices
            for idx in sorted(rooms_to_remove, reverse=True):
                design.rooms.pop(idx)
            
            st.success(f"✅ Eliminados {len(rooms_to_remove)} elemento(s). Presupuesto actualizado.")
    
    # ============================================
    # 📐 VISUALIZACIÓN DEL PLANO 2D
    # ============================================
    st.markdown("---")
    st.subheader("📐 Visualización del Plano")
    
    if st.button("🎨 Generar Plano 2D", type="primary"):
        try:
            from .step2_planner import ProfessionalFloorPlan
            
            # Generar plano
            planner = ProfessionalFloorPlan(design)
            img_bytes = planner.generate()
            
            # Guardar en session state
            st.session_state['current_floor_plan'] = img_bytes
            
            st.success("✅ Plano generado correctamente")
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error generando plano: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Mostrar plano si existe
    if 'current_floor_plan' in st.session_state:
        st.image(
            st.session_state['current_floor_plan'],
            caption="Plano de distribución profesional",
            use_container_width=True
        )
        
        # Botón para descargar
        st.download_button(
            label="📥 Descargar Plano PNG",
            data=st.session_state['current_floor_plan'],
            file_name="plano_distribucion.png",
            mime="image/png"
        )

    # ============================================
    # 🤖 SUGERENCIAS INTELIGENTES DE IA
    # ============================================
    if 'current_floor_plan' in st.session_state:
        st.markdown("---")
        st.subheader("🤖 Análisis del Arquitecto IA")
        
        # Analizar distribución con IA
        with st.spinner("Analizando distribución..."):
            try:
                from groq import Groq
                import os
                from dotenv import load_dotenv
                from pathlib import Path
                
                # Cargar API key
                project_root = Path(__file__).parent.parent.parent
                load_dotenv(dotenv_path=project_root / '.env')
                groq_api_key = os.getenv("GROQ_API_KEY")
                
                if not groq_api_key:
                    st.warning("⚠️ API key de Groq no encontrada")
                else:
                    client = Groq(api_key=groq_api_key)
                    
                    # Crear resumen de distribución
                    rooms_summary = []
                    for room in design.rooms:
                        rooms_summary.append(f"- {room.room_type.name}: {room.area_m2:.0f} m²")
                    
                    prompt = f"""Eres un arquitecto experto. Analiza esta distribución de vivienda:

HABITACIONES:
{chr(10).join(rooms_summary)}

TOTAL: {sum([r.area_m2 for r in design.rooms]):.0f} m²

Proporciona:
1. Evaluación general (1-2 líneas)
2. 2-3 sugerencias concretas de mejora
3. Alertas si algo es problemático (cocina muy pequeña, baño sin ventilación, etc.)

Sé conciso y práctico. Formato:

✅/⚠️/❌ [Aspecto]: [Comentario breve]
💡 Sugerencia: [Acción específica]
"""
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3
                    )
                    
                    analysis = response.choices[0].message.content.strip()
                    
                    # Mostrar en expander
                    with st.expander("📋 Ver análisis detallado", expanded=True):
                        st.markdown(analysis)
            
            except Exception as e:
                st.error(f"❌ Error en análisis IA: {e}")

    st.markdown("---")
    
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