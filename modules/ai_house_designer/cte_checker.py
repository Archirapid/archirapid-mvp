"""
cte_checker.py — Chequeo CTE DB-HS y DB-SUA en tiempo real
Sprint 4: Módulo de Cumplimiento CTE

Normas implementadas:
  DB-HS 3 (Calidad del aire interior): ventilación mínima por superficie.
  DB-HS 3 (Iluminación natural): hueco mínimo = 12% de la superficie de la estancia.
  DB-SUA 1 (Seguridad de utilización): anchura libre de paso ≥ 0.80m en habitaciones,
            ≥ 0.90m en cocinas, ≥ 1.00m en pasillos.

Uso:
    from modules.ai_house_designer.cte_checker import check_cte, render_cte_panel
    issues = check_cte(rooms)
    render_cte_panel(rooms)
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple


# ─── Tablas CTE ──────────────────────────────────────────────────────────────

# DB-HS 3: caudal mínimo de ventilación (l/s por m²) por tipo de estancia
_HS3_VENTILACION: Dict[str, float] = {
    "dormitorio":            1.5,
    "dormitorio_principal":  1.5,
    "salon":                 1.0,
    "cocina":                2.0,   # cocina requiere extracción mecánica
    "salon_cocina":          1.5,
    "bano":                  2.0,
    "aseo":                  2.0,
    "default":               1.0,
}

# DB-HS 3: superficie mínima de hueco iluminante (% de la superficie útil)
_HS3_ILUMINACION_PCT = 0.12   # 12% de la superficie de la estancia

# DB-HS 3: superficie mínima de la estancia para cumplir ventilación natural
_HS3_VENTILACION_NATURAL_MIN_M2 = 4.0  # < 4m² → obligatorio ventilación mecánica

# DB-SUA 1: anchura libre mínima de paso (m) por tipo
_SUA1_ANCHO_PASO: Dict[str, float] = {
    "pasillo":               1.00,
    "cocina":                0.90,
    "bano":                  0.80,
    "aseo":                  0.80,
    "dormitorio":            0.80,
    "dormitorio_principal":  0.80,
    "salon":                 0.90,
    "default":               0.80,
}

# DB-SUA 1: superficie mínima de estancia para paso funcional (heurística)
# Si la estancia es muy pequeña, puede no cumplir el paso libre
_SUA1_MIN_M2_POR_TIPO: Dict[str, float] = {
    "bano":                  3.0,
    "aseo":                  1.5,
    "cocina":                6.0,
    "dormitorio":            6.0,
    "dormitorio_principal":  10.0,
    "salon":                 12.0,
    "pasillo":               2.0,
    "default":               4.0,
}


# ─── Clases de resultado ─────────────────────────────────────────────────────

class CTEIssue:
    def __init__(self, room_name: str, doc: str, rule: str, message: str, severity: str = "warning"):
        self.room_name = room_name
        self.doc = doc          # "DB-HS" | "DB-SUA"
        self.rule = rule        # e.g. "HS3-ventilacion"
        self.message = message
        self.severity = severity  # "error" | "warning"

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.doc}/{self.rule} {self.room_name}: {self.message}"


# ─── Motor de chequeo ─────────────────────────────────────────────────────────

def check_cte(rooms: List[Dict[str, Any]], budget_m2: float | None = None) -> List[CTEIssue]:
    """
    Ejecuta todos los checks CTE sobre la lista de habitaciones.

    Args:
        rooms: lista de dicts con "code", "name", "area_m2"
        budget_m2: m² máximos contratados (si se supera → error)

    Returns:
        Lista de CTEIssue (puede estar vacía si todo cumple).
    """
    issues: List[CTEIssue] = []

    total_interior = 0.0
    for r in rooms:
        code = (r.get("code") or r.get("name") or "").lower().strip()
        area = float(r.get("area_m2") or r.get("area") or 0.0)
        name = r.get("name") or code

        # Saltar exteriores — no aplica CTE habitabilidad
        if _is_exterior(code):
            continue

        total_interior += area

        issues += _check_hs3_ventilacion(name, code, area)
        issues += _check_hs3_iluminacion(name, code, area)
        issues += _check_sua1_dimensiones(name, code, area)

    # Chequeo presupuesto m²
    if budget_m2 and budget_m2 > 0 and total_interior > budget_m2 * 1.05:
        issues.append(CTEIssue(
            room_name="Vivienda completa",
            doc="Presupuesto",
            rule="m2-contratados",
            message=(
                f"Superficie interior total ({total_interior:.1f} m²) supera los m² "
                f"contratados ({budget_m2:.1f} m²). Reduce habitaciones o amplía el presupuesto."
            ),
            severity="error",
        ))

    return issues


def _check_hs3_ventilacion(name: str, code: str, area: float) -> List[CTEIssue]:
    issues = []
    caudal_min = _HS3_VENTILACION.get(code, _HS3_VENTILACION["default"])
    caudal_total = area * caudal_min  # l/s mínimo para la estancia

    if area < _HS3_VENTILACION_NATURAL_MIN_M2:
        issues.append(CTEIssue(
            room_name=name,
            doc="DB-HS3",
            rule="ventilacion-mecanica",
            message=f"{area:.1f} m² — estancia muy pequeña, requiere ventilación mecánica forzada.",
            severity="warning",
        ))
    elif code in ("cocina",) and area < 8.0:
        issues.append(CTEIssue(
            room_name=name,
            doc="DB-HS3",
            rule="ventilacion-cocina",
            message=f"Cocina de {area:.1f} m² requiere campana extractora + ventilación mecánica (CTE HS3).",
            severity="warning",
        ))
    return issues


def _check_hs3_iluminacion(name: str, code: str, area: float) -> List[CTEIssue]:
    issues = []
    hueco_min = area * _HS3_ILUMINACION_PCT
    if area < 4.0:
        return issues  # muy pequeño, se valida en ventilación
    # Heurística: si el área es muy grande y el tipo es dormitorio/salón,
    # estimamos que necesitaría un hueco grande
    if hueco_min > 3.0 and code in ("salon", "dormitorio_principal", "salon_cocina"):
        issues.append(CTEIssue(
            room_name=name,
            doc="DB-HS3",
            rule="iluminacion-natural",
            message=(
                f"Estancia de {area:.1f} m² requiere hueco iluminante ≥ {hueco_min:.2f} m² "
                f"(12% superficie). Verifica ventana en editor 3D."
            ),
            severity="warning",
        ))
    return issues


def _check_sua1_dimensiones(name: str, code: str, area: float) -> List[CTEIssue]:
    issues = []
    min_area = _SUA1_MIN_M2_POR_TIPO.get(code, _SUA1_MIN_M2_POR_TIPO["default"])
    min_paso = _SUA1_ANCHO_PASO.get(code, _SUA1_ANCHO_PASO["default"])

    if area < min_area:
        issues.append(CTEIssue(
            room_name=name,
            doc="DB-SUA1",
            rule="dimensiones-minimas",
            message=(
                f"{area:.1f} m² < mínimo recomendado {min_area:.1f} m² "
                f"para paso libre de {min_paso:.2f} m (CTE DB-SUA 1)."
            ),
            severity="warning" if area >= min_area * 0.8 else "error",
        ))
    return issues


def _is_exterior(code: str) -> bool:
    EXTERIOR = {"porche", "terraza", "piscina", "huerto", "caseta",
                "garaje", "paneles_solares", "bomba_agua", "aperos"}
    return any(e in code for e in EXTERIOR)


# ─── Render Streamlit ─────────────────────────────────────────────────────────

def render_cte_panel(rooms: List[Dict[str, Any]], budget_m2: float | None = None):
    """
    Muestra panel CTE compacto en Streamlit con semáforo de cumplimiento.
    Llamar desde render_step2() después de los sliders.
    """
    import streamlit as st

    issues = check_cte(rooms, budget_m2)

    errors   = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if not issues:
        st.markdown("""
<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.4);
            border-radius:8px;padding:8px 14px;margin-top:8px;">
  <span style="color:#10B981;font-weight:700;">✅ CTE — Sin incidencias detectadas</span>
  <span style="color:#64748B;font-size:11px;margin-left:8px;">
    DB-HS3 Ventilación · DB-HS3 Iluminación · DB-SUA1 Dimensiones
  </span>
</div>""", unsafe_allow_html=True)
        return

    # Semáforo
    color = "#EF4444" if errors else "#F59E0B"
    label = f"{'🔴' if errors else '🟡'} CTE — {len(errors)} error(es), {len(warnings)} aviso(s)"

    with st.expander(label, expanded=bool(errors)):
        if errors:
            st.markdown("**🔴 Errores — el diseño no cumple normativa:**")
            for e in errors:
                st.error(f"**{e.doc}/{e.rule}** · {e.room_name}: {e.message}")
        if warnings:
            st.markdown("**🟡 Avisos — revisar antes de la ejecución:**")
            for w in warnings:
                st.warning(f"**{w.doc}/{w.rule}** · {w.room_name}: {w.message}")
        st.caption("Chequeo automático orientativo. Requiere validación de arquitecto colegiado.")
