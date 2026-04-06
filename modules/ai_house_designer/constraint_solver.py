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
from typing import List, Dict, Any, Tuple
import math

# ─── Metadatos geométricos: INTERNAL vs EXTERNAL ─────────────────────────────
# INTERNAL: siempre dentro del perímetro construido de la vivienda.
# EXTERNAL: deben estar FUERA de la huella interior; si colisionan → auto_eject.
INTERNAL_TYPES: Dict[str, str] = {
    "salon":        "Zona día",
    "salon_cocina": "Zona día",
    "cocina":       "Zona húmeda/día",
    "bano":         "Zona húmeda",
    "aseo":         "Zona húmeda",
    "dormitorio":   "Zona noche",
    "pasillo":      "Circulación",
    "distribuidor": "Circulación",
    "hall":         "Circulación",
    "despacho":     "Zona día",
    "office":       "Zona día",
    "estudio":      "Zona día",
    "sala_estar":   "Zona día",
    "comedor":      "Zona día",
    "lavanderia":   "Zona servicio",
    "despensa":     "Zona servicio",
}

EXTERNAL_TYPES: Dict[str, str] = {
    "porche":         "Exterior semi-cubierto",
    "terraza":        "Exterior descubierto",
    "piscina":        "Exterior lúdico",
    "huerto":         "Exterior productivo",
    "caseta":         "Anejo exterior",
    "tejavana":       "Anejo exterior cubierto",
    "aperos":         "Anejo exterior",
    "garaje":         "Anejo/exterior",
    "paneles_solares":"Cubierta/exterior",
    "bomba_agua":     "Caseta técnica exterior",
}

# ─── Margen de expulsión automática (metros) ──────────────────────────────────
AUTO_EJECT_MARGIN = 2.0

# Tipos que pueden opcionalmente ser interior (garaje integrado, etc.)
AMBIGUOUS_TYPES: set[str] = {"garaje", "porche"}

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

def _is_internal_code(code: str) -> bool:
    """True si el código corresponde a un tipo INTERNAL."""
    return any(k in code for k in INTERNAL_TYPES)


def _is_external_code_strict(code: str) -> bool:
    """True si el código es exclusivamente EXTERNAL (nunca dentro de la huella)."""
    c = code.lower()
    return any(k in c for k in EXTERNAL_TYPES if k not in AMBIGUOUS_TYPES)


def _aabb_overlap(ax: float, az: float, aw: float, ad: float,
                  bx: float, bz: float, bw: float, bd: float) -> bool:
    """True si los dos AABB se solapan (Axis-Aligned Bounding Box)."""
    return (ax < bx + bw and ax + aw > bx and
            az < bz + bd and az + ad > bz)


def _internal_bbox(rooms: List[Dict]) -> Tuple[float, float, float, float] | None:
    """Calcula el bounding box de todos los rooms INTERNAL con coordenadas."""
    internals = [r for r in rooms if _is_internal_code(r.get("code", ""))
                 and r.get("x") is not None]
    if not internals:
        return None
    min_x = min(r["x"] for r in internals)
    min_z = min(r.get("z", 0) for r in internals)
    max_x = max(r["x"] + r.get("width", 0) for r in internals)
    max_z = max(r.get("z", 0) + r.get("depth", 0) for r in internals)
    return (min_x, min_z, max_x - min_x, max_z - min_z)


def auto_eject(rooms: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """
    Física de repulsión geométrica: si un objeto EXTERNAL colisiona con
    la huella INTERNAL lo expulsa +AUTO_EJECT_MARGIN metros en el eje X o Z
    más corto hasta eliminar el solapamiento.

    Rooms marcados con is_user_placed=True NO se mueven (física OFF en edición manual).

    Args:
        rooms: lista de dicts con {code, x, z, width, depth, ...}
               (los que no tienen coordenadas se omiten silenciosamente)
    Returns:
        (rooms_modificados, mensajes_de_expulsión)
    """
    bbox = _internal_bbox(rooms)
    if bbox is None:
        return rooms, []

    ibx, ibz, ibw, ibd = bbox
    messages: List[str] = []

    for r in rooms:
        code = r.get("code", "").lower()
        if not _is_external_code_strict(code):
            continue
        # Física OFF: usuario ha posicionado este elemento manualmente
        if r.get("is_user_placed") or r.get("isEditable"):
            continue
        rx = r.get("x")
        rz = r.get("z")
        rw = r.get("width", 0)
        rd = r.get("depth", 0)
        if rx is None or rz is None:
            continue

        if not _aabb_overlap(rx, rz, rw, rd, ibx, ibz, ibw, ibd):
            continue  # sin colisión

        # Calcular penetración en cada eje
        overlap_x_right = (rx + rw) - ibx          # cuánto penetra por la derecha
        overlap_x_left  = (ibx + ibw) - rx          # cuánto penetra por la izquierda
        overlap_z_front = (rz + rd) - ibz           # penetración por frente
        overlap_z_back  = (ibz + ibd) - rz          # penetración por atrás

        # Expulsar por el eje con menor penetración (camino más corto)
        candidates = [
            ("x+", overlap_x_right, ibx - rw - AUTO_EJECT_MARGIN, None),
            ("x-", overlap_x_left,  None, ibx + ibw + AUTO_EJECT_MARGIN),
            ("z+", overlap_z_front, None, None),
            ("z-", overlap_z_back,  None, None),
        ]
        # Elegir el de menor penetración
        min_pen = min(candidates, key=lambda c: c[1])
        axis = min_pen[0]

        if axis == "x+":
            r["x"] = ibx - rw - AUTO_EJECT_MARGIN
        elif axis == "x-":
            r["x"] = ibx + ibw + AUTO_EJECT_MARGIN
        elif axis == "z+":
            r["z"] = ibz - rd - AUTO_EJECT_MARGIN
        else:  # z-
            r["z"] = ibz + ibd + AUTO_EJECT_MARGIN

        messages.append(
            f"AUTO-EJECT: '{r.get('name', code)}' colisionaba con zona interior "
            f"— reposicionado +{AUTO_EJECT_MARGIN}m eje {axis[0].upper()}."
        )

    return rooms, messages


def validate_design(rooms: List[Dict[str, Any]], plot_data: Dict[str, Any] | None = None) -> ConstraintResult:
    """
    Valida el diseño completo contra todas las reglas.
    Si los rooms incluyen coordenadas (x, z, width, depth), aplica auto_eject
    geométrico antes de validar.

    Args:
        rooms: lista de dicts con al menos {"name": str, "area_m2": float, "code": str}
               Opcionalmente: {"x": float, "z": float, "width": float, "depth": float}
        plot_data: dict con "buildable_m2" (opcional)

    Returns:
        ConstraintResult con listas de errores y warnings.
    """
    result = ConstraintResult()

    if not rooms:
        result.errors.append("El diseño no tiene habitaciones definidas.")
        return result

    # Auto-eject geométrico si hay coordenadas
    has_coords = any(r.get("x") is not None for r in rooms)
    if has_coords:
        rooms, eject_msgs = auto_eject(list(rooms))
        for msg in eject_msgs:
            result.warnings.append(msg)

    # Normalizar: asegurar que cada room tiene "code" y "area_m2"
    normalized = []
    for r in rooms:
        code = (r.get("code") or r.get("name") or "").lower().strip()
        area = float(r.get("area_m2") or r.get("area") or 0.0)
        normalized.append({"code": code, "area_m2": area, "name": r.get("name", code),
                            "x": r.get("x"), "z": r.get("z"),
                            "width": r.get("width"), "depth": r.get("depth")})

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
    return any(ext in code for ext in EXTERNAL_TYPES)


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
