# modules/marketplace/gemelo_editor.py

import json
import streamlit as st
from modules.marketplace.validacion import validar_plan_local
from modules.marketplace.ai_engine import get_ai_response

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
    st.markdown("### 📏 Validación local (reglas genéricas)")
    if resultado["ok"]:
        st.success(f"✅ Plan válido: {plan_json.get('total_m2', 0):.1f} m² construidos dentro de normativa")
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


def aplicar_propuesta_ia(informe_ia_texto: str, plan_json_actual: dict):
    """
    Intenta aplicar una propuesta de IA parseando JSON del informe.

    Args:
        informe_ia_texto: Texto del informe IA
        plan_json_actual: Plan actual como fallback

    Returns:
        dict: Plan actualizado o el actual si no se pudo parsear
    """
    try:
        # Buscar JSON en el texto (puede estar entre ```json y ```)
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', informe_ia_texto, re.DOTALL)
        if json_match:
            propuesta = json.loads(json_match.group(1))
            return propuesta
        else:
            # Intentar parsear todo el texto como JSON
            propuesta = json.loads(informe_ia_texto)
            return propuesta
    except json.JSONDecodeError:
        st.warning("La IA devolvió texto no JSON. Revisa el informe manualmente.")
        return plan_json_actual