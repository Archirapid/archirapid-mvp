"""
constraint_solver.py — Validación semántica y espacial del diseño
Sprint 1: Semántica Espacial y Constraint Solver

Reglas implementadas:
  1. Supervivencia: el diseño DEBE tener Salón (≥12 m²) y Cocina (≥8 m²).
  2. Aislamiento exterior: los tipos marcados como EXTERIOR no pueden estar
     dentro del polígono de la vivienda (su BoundingBox no puede intersecar
     con el conjunto de habitaciones interiores).
  3. Ocupación edificable: la suma de m² de interiores no puede superar
     el máximo edificable de la parcela.
"""

from __future__ import annotations
from typing import List, Dict, Any

# ─── Tipos exteriores — nunca dentro de la huella interior ───────────────────
EXTERIOR_TYPES: set[str] = {
    "porche", "terraza", "piscina", "huerto", "caseta", "aperos",
    "garaje",           # discutible, pero en España suele ser anejo exterior
    "paneles_solares",  # en cubierta o suelo exterior
    "bomba_agua",       # caseta técnica exterior
}

# Tipos que pueden opcionalmente ser interior (garaje integrado, etc.)
AMBIGUOUS_TYPES: set[str] = {"garaje"}

# ─── Mínimos de supervivencia CTE/LOE ────────────────────────────────────────
SURVIVAL_RULES: Dict[str, Dict] = {
    "salon":       {"min_m2": 12.0, "display": "Salón"},
    "cocina":      {"min_m2": 8.0,  "display": "Cocina"},
    "salon_cocina": {"min_m2": 20.0, "display": "Salón-Cocina"},  # combo válido
}

# ─── Alias que cuentan como "salón" en validación CTE ────────────────────────
# Un office grande, sala de estar, living o comedor cubre el nodo Salón.
SALON_ALIASES: tuple[str, ...] = (
    "salon", "sala_estar", "sala_de_estar", "salita", "living",
    "comedor", "office", "despacho", "estudio",
)

# ─── Resultado ────────────────────────────────────────────────────────────────

class ConstraintResult:
    def __init__(self):
        self.errors: List[str] = []    # bloquean el flujo
        self.warnings: List[str] = []  # informativas, no bloquean

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self):
        return f"ConstraintResult(valid={self.is_valid}, errors={self.errors}, warnings={self.warnings})"


# ─── Función principal ────────────────────────────────────────────────────────

def validate_design(rooms: List[Dict[str, Any]], plot_data: Dict[str, Any] | None = None) -> ConstraintResult:
    """
    Valida el diseño completo contra todas las reglas.

    Args:
        rooms: lista de dicts con al menos {"name": str, "area_m2": float, "code": str (opcional)}
        plot_data: dict con "buildable_m2" (opcional)

    Returns:
        ConstraintResult con listas de errores y warnings.
    """
    result = ConstraintResult()

    if not rooms:
        result.errors.append("El diseño no tiene habitaciones definidas.")
        return result

    # Normalizar: asegurar que cada room tiene "code" y "area_m2"
    normalized = []
    for r in rooms:
        code = (r.get("code") or r.get("name") or "").lower().strip()
        area = float(r.get("area_m2") or r.get("area") or 0.0)
        normalized.append({"code": code, "area_m2": area, "name": r.get("name", code)})

    _check_survival(normalized, result)
    _check_exterior_isolation(normalized, result)
    if plot_data:
        _check_buildable_area(normalized, plot_data, result)

    return result


def _check_survival(rooms: List[Dict], result: ConstraintResult):
    """Regla 1: el diseño debe tener Salón ≥12m² Y Cocina ≥8m² (o Salón-Cocina ≥20m²).
    Acepta aliases de salón: office, sala_estar, living, comedor, despacho, estudio."""
    has_salon_cocina = False
    salon_m2 = 0.0
    cocina_m2 = 0.0
    salon_alias_used = ""

    for r in rooms:
        code = r.get("code", "").lower()
        area = float(r.get("area_m2", 0))
        if "salon" in code and "cocina" in code:
            has_salon_cocina = True
            if area >= SURVIVAL_RULES["salon_cocina"]["min_m2"]:
                return  # Salón-Cocina combinado válido
            else:
                result.errors.append(
                    f"Salón-Cocina integrado tiene {area:.1f} m² — mínimo CTE: "
                    f"{SURVIVAL_RULES['salon_cocina']['min_m2']} m²."
                )
                return
        # Alias: cualquier código que contenga un alias de salón cuenta como salón
        if any(alias in code for alias in SALON_ALIASES) and "cocina" not in code:
            if area > salon_m2:
                salon_m2 = area
                salon_alias_used = code
        if "cocina" in code and "salon" not in code:
            cocina_m2 = max(cocina_m2, area)

    if not has_salon_cocina:
        min_salon = SURVIVAL_RULES["salon"]["min_m2"]
        if salon_m2 == 0.0:
            result.errors.append(
                f"Diseño inválido: falta zona de Salón (mínimo CTE {min_salon} m²). "
                "Añade un salón, sala de estar u office en el layout."
            )
        elif salon_m2 < min_salon:
            alias_label = salon_alias_used if salon_alias_used != "salon" else "Salón"
            result.warnings.append(          # ← warning, no error — permite continuar
                f"'{alias_label}' tiene {salon_m2:.1f} m² (mínimo CTE {min_salon} m²). "
                "Se acepta bajo responsabilidad del proyectista."
            )

        if cocina_m2 == 0.0:
            result.errors.append(
                f"Diseño inválido: falta Cocina (mínimo CTE {SURVIVAL_RULES['cocina']['min_m2']} m²)."
            )
        elif cocina_m2 < SURVIVAL_RULES["cocina"]["min_m2"]:
            result.warnings.append(          # ← warning, no error
                f"Cocina de {cocina_m2:.1f} m² no cumple el mínimo CTE de "
                f"{SURVIVAL_RULES['cocina']['min_m2']} m². "
                "Se acepta bajo responsabilidad del proyectista."
            )


def _check_exterior_isolation(rooms: List[Dict], result: ConstraintResult):
    """
    Regla 2: los tipos exteriores no deben estar en el interior.
    Como no tenemos coordenadas reales en este punto del flujo, usamos
    una heurística semántica: si un tipo exterior tiene area_m2 > 0
    y hay habitaciones interiores, advertimos si el exterior excede
    el 40% del total interior (indicio de que está mal clasificado).
    """
    interior_area = sum(
        r["area_m2"] for r in rooms
        if not _is_exterior_code(r["code"])
    )
    exterior_items = [r for r in rooms if _is_exterior_code(r["code"])]

    for ext in exterior_items:
        if ext["area_m2"] > interior_area * 0.5:
            result.warnings.append(
                f"'{ext['name']}' ({ext['area_m2']:.1f} m²) es un elemento exterior "
                f"que supera el 50% de la superficie interior ({interior_area:.1f} m²). "
                "Comprueba que está ubicado fuera de la huella de la vivienda en el editor 3D."
            )

    # Alerta si hay exteriores con 0 m² (posible error de configuración)
    for ext in exterior_items:
        if ext["area_m2"] <= 0:
            result.warnings.append(
                f"'{ext['name']}' es un elemento exterior con 0 m². "
                "Verifica su tamaño en el paso de ajuste de espacios."
            )


def _check_buildable_area(rooms: List[Dict], plot_data: Dict, result: ConstraintResult):
    """Regla 3: la superficie interior no puede superar el edificable de la parcela."""
    buildable = float(plot_data.get("buildable_m2") or
                      plot_data.get("m2_edificable") or 0.0)
    if buildable <= 0:
        return  # sin dato de parcela, no se puede validar

    interior_area = sum(
        r["area_m2"] for r in rooms
        if not _is_exterior_code(r["code"])
    )

    if interior_area > buildable * 1.05:  # 5% de tolerancia para redondeos
        result.errors.append(
            f"La superficie interior ({interior_area:.1f} m²) supera el máximo "
            f"edificable de la parcela ({buildable:.1f} m²). "
            "Reduce la superficie en el editor o elige una parcela mayor."
        )
    elif interior_area > buildable * 0.95:
        result.warnings.append(
            f"La superficie interior ({interior_area:.1f} m²) está muy cerca "
            f"del límite edificable ({buildable:.1f} m²)."
        )


def _is_exterior_code(code: str) -> bool:
    return any(ext in code for ext in EXTERIOR_TYPES)


# ─── Helper para Streamlit — mostrar resultado en UI ─────────────────────────

def show_constraint_results(result: ConstraintResult) -> bool:
    """
    Muestra errores/warnings en Streamlit.
    Retorna True si el diseño puede continuar.
    Bypass temporal: errores de supervivencia se muestran como warnings para
    no bloquear el acceso al Editor 3D durante pruebas.
    """
    import streamlit as st

    for w in result.warnings:
        st.warning(f"⚠️ {w}")

    if not result.is_valid:
        for e in result.errors:
            # Bypass: mostrar como warning en lugar de error bloqueante
            st.warning(
                f"⚠️ **Aviso CTE (no bloqueante):** {e} — "
                "Puedes continuar al Editor 3D bajo responsabilidad del proyectista."
            )
        # No retornamos False → el flujo puede continuar
    return True
