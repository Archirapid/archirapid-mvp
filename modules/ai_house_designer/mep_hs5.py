"""
Motor CTE HS-5 — Cálculo de saneamiento según normativa española
DB-HS Documento Básico Salubridad, Sección HS 5: Evacuación de aguas
Python puro — sin dependencias externas
"""
from typing import List, Dict, Any


# ─── Tablas CTE HS-5 ─────────────────────────────────────────────────────────

# UDs por aparato sanitario — Tabla 4.1 CTE HS-5
UD_APARATOS: Dict[str, Dict] = {
    "wc_cisterna":   {"nombre": "WC cisterna",    "ud": 4},
    "wc_fluxor":     {"nombre": "WC fluxor",       "ud": 8},
    "lavabo":        {"nombre": "Lavabo",           "ud": 2},
    "ducha":         {"nombre": "Ducha",            "ud": 2},
    "banera":        {"nombre": "Bañera",           "ud": 3},
    "banera_grande": {"nombre": "Bañera grande",    "ud": 4},
    "fregadero":     {"nombre": "Fregadero cocina", "ud": 3},
    "lavavajillas":  {"nombre": "Lavavajillas",     "ud": 3},
    "lavadora":      {"nombre": "Lavadora",         "ud": 3},
    "vertedero":     {"nombre": "Vertedero",        "ud": 8},
    "sumidero":      {"nombre": "Sumidero",         "ud": 1},
}

# Diámetro ramal individual (mm) — Tabla 4.3 CTE HS-5, pendiente 2%
_TABLA_RAMAL = [(4, 50), (8, 63), (12, 75), (20, 90), (32, 110), (96, 125), (float("inf"), 160)]

# Diámetro colector (mm) — Tabla 4.5 CTE HS-5, pendiente 2%
_TABLA_COLECTOR = [(12, 63), (24, 75), (48, 90), (96, 110), (192, 125), (float("inf"), 160)]


def _d_ramal(ud: float) -> int:
    for ud_max, d in _TABLA_RAMAL:
        if ud <= ud_max:
            return d
    return 160


def _d_colector(ud: float) -> int:
    for ud_max, d in _TABLA_COLECTOR:
        if ud <= ud_max:
            return d
    return 160


# ─── Normativa CCAA ──────────────────────────────────────────────────────────

def _get_ccaa_normativa(provincia_o_ccaa: str) -> Dict:
    """
    Devuelve la fila de normativa_fosas_ccaa para la provincia/CCAA indicada.
    Búsqueda fuzzy: coincidencia parcial case-insensitive.
    Retorna {} si no encuentra o si falla la consulta DB.
    """
    if not provincia_o_ccaa:
        return {}
    try:
        import sqlite3 as _sq
        from modules.marketplace.utils import DB_PATH as _DBP
        conn = _sq.connect(_DBP, timeout=10)
        conn.row_factory = _sq.Row
        q = provincia_o_ccaa.strip().lower()
        cur = conn.execute(
            "SELECT * FROM normativa_fosas_ccaa WHERE LOWER(ccaa) LIKE ? OR LOWER(codigo) = ?",
            (f"%{q}%", q[:3])
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception:
        return {}


# ─── Motor principal ──────────────────────────────────────────────────────────

def calcular_saneamiento(rooms_layout: List[Dict], req: Dict = None) -> Dict[str, Any]:
    """
    Calcula la instalación de saneamiento según CTE HS-5.

    Args:
        rooms_layout : lista de rooms Babylon {code, name, zone, area_m2, x, z, width, depth}
        req          : ai_house_requirements {bedrooms, bathrooms, ...} (opcional)

    Returns:
        dict con: aparatos, ud_total, ramales, colector, fosa,
                  presupuesto, resumen_texto, meta
    """
    if not rooms_layout:
        return _resultado_vacio()
    if req is None:
        req = {}

    # ── 1. Clasificar habitaciones ────────────────────────────────────────────
    def _code(r):
        return (r.get("code", "") + " " + r.get("name", "")).lower()

    banos      = [r for r in rooms_layout if "bano"    in _code(r) and "aseo" not in _code(r)]
    aseos      = [r for r in rooms_layout if "aseo"    in _code(r)]
    cocinas    = [r for r in rooms_layout if "cocina"  in _code(r)]
    dormits    = [r for r in rooms_layout if "dormitorio" in _code(r)]
    lavaderias = [r for r in rooms_layout
                  if any(x in _code(r) for x in ["lavader", "plancha", "util"])]

    # ── 2. Estimar habitantes ─────────────────────────────────────────────────
    n_dorm_p = sum(1 for r in dormits if "principal" in _code(r))
    n_dorm_s = len(dormits) - n_dorm_p
    habitantes = max(2, n_dorm_p * 2 + n_dorm_s * 1)
    if req.get("bedrooms"):
        habitantes = max(2, int(req["bedrooms"]) + 1)
    habitantes = int(round(habitantes))

    # ── 3. Aparatos y ramales por estancia ────────────────────────────────────
    aparatos: Dict[str, Dict] = {}
    ramales: List[Dict] = []

    def _add(key: str, n: int = 1):
        cfg = UD_APARATOS[key]
        if key not in aparatos:
            aparatos[key] = {"nombre": cfg["nombre"], "ud_unidad": cfg["ud"], "count": 0}
        aparatos[key]["count"] += n

    # Baños
    for i, r in enumerate(banos):
        area = r.get("area_m2") or 5.0
        _add("wc_cisterna")
        _add("lavabo")
        if area >= 7.0:
            _add("banera")
            ud_r = 4 + 2 + 3   # 9
        else:
            _add("ducha")
            ud_r = 4 + 2 + 2   # 8
        ramales.append({
            "id":           f"ramal_bano_{i+1}",
            "descripcion":  f"Baño {i+1}",
            "ud":           ud_r,
            "diametro_mm":  _d_ramal(ud_r),
            "longitud_m":   round(max(3.0, area * 0.5), 1),
        })

    # Aseos
    for i, r in enumerate(aseos):
        _add("wc_cisterna")
        _add("lavabo")
        ud_r = 6  # WC4 + lavabo2
        ramales.append({
            "id":           f"ramal_aseo_{i+1}",
            "descripcion":  f"Aseo {i+1}",
            "ud":           ud_r,
            "diametro_mm":  _d_ramal(ud_r),
            "longitud_m":   3.0,
        })

    # Cocinas
    for i, r in enumerate(cocinas):
        _add("fregadero")
        _add("lavavajillas")
        ud_r = 6  # fregadero3 + lavavajillas3
        area = r.get("area_m2") or 9.0
        ramales.append({
            "id":           f"ramal_cocina_{i+1}",
            "descripcion":  f"Cocina {i+1}",
            "ud":           ud_r,
            "diametro_mm":  _d_ramal(ud_r),
            "longitud_m":   round(max(2.0, area * 0.4), 1),
        })

    # Lavadora (en lavadería, o en baño principal si no existe)
    if lavaderias:
        for _ in lavaderias:
            _add("lavadora")
    elif banos:
        _add("lavadora")   # lavadora en baño principal
    else:
        _add("lavadora")   # siempre hay lavadora

    # ── 4. UDs totales ────────────────────────────────────────────────────────
    ud_total = sum(v["ud_unidad"] * v["count"] for v in aparatos.values())

    # ── 5. Colector principal ─────────────────────────────────────────────────
    # Longitud estimada = anchura casa + distancia a fosa (~4m extra)
    try:
        tw = max(r.get("x", 0) + r.get("width", 0) for r in rooms_layout)
    except Exception:
        tw = 10.0
    col_long = round(tw + 4.5, 1)

    colector = {
        "ud_total":      ud_total,
        "diametro_mm":   _d_colector(ud_total),
        "pendiente_pct": 2.0,
        "longitud_m":    col_long,
        "material":      "PVC sanitario serie B",
    }

    # ── 6. Fosa séptica ───────────────────────────────────────────────────────
    # Volumen mínimo: 200 L/hab/día × 3 días de retención = 600 L/hab
    vol_calc = habitantes * 600

    # Leer normativa CCAA si está disponible
    ccaa_norm = _get_ccaa_normativa(req.get("provincia") or req.get("ccaa") or "")
    vol_minimo_ccaa = ccaa_norm.get("vol_minimo_l", 2000) if ccaa_norm else 2000
    vol_base = max(vol_calc, vol_minimo_ccaa)

    for tam_comercial in [2000, 3000, 4000, 6000, 8000, 10000]:
        if vol_base <= tam_comercial:
            vol_com = tam_comercial
            break
    else:
        vol_com = vol_base

    fosa = {
        "habitantes":             habitantes,
        "vol_calc_litros":        vol_calc,
        "vol_comercial_litros":   vol_com,
        "vol_minimo_ccaa_litros": vol_minimo_ccaa,
        "tipo":                   "Fosa séptica prefabricada PE/fibra vidrio",
        "diametro_est_m":         round(0.8 + vol_com / 10000, 1),
        "longitud_est_m":         round(0.8 + vol_com / 6000, 1),
        "ccaa_norm":              ccaa_norm,
    }

    # ── 7. Presupuesto orientativo ────────────────────────────────────────────
    m_col  = colector["longitud_m"]
    m_ram  = round(sum(r["longitud_m"] for r in ramales), 1)
    n_arq  = max(2, len(ramales) + 1)
    h_obra = round(8 + len(ramales) * 4 + 6, 0)
    m3_exc = round(m_col * 0.4 * 0.6 + 3.5, 1)

    partidas = {
        "tuberia_colector": {
            "descripcion": f"Tubería PVC Ø{colector['diametro_mm']}mm colector ({m_col}m)",
            "ud": "m.l.", "cantidad": m_col,   "precio_ud": 18.50,
            "total": round(m_col * 18.50, 2),
        },
        "tuberia_ramales": {
            "descripcion": f"Tuberías PVC ramales interiores ({m_ram}m total)",
            "ud": "m.l.", "cantidad": m_ram,   "precio_ud": 12.80,
            "total": round(m_ram * 12.80, 2),
        },
        "arquetas": {
            "descripcion": f"Arquetas de registro ({n_arq} ud)",
            "ud": "ud",   "cantidad": n_arq,   "precio_ud": 95.0,
            "total": round(n_arq * 95.0, 2),
        },
        "fosa_septica": {
            "descripcion": f"Fosa séptica prefabricada {vol_com}L",
            "ud": "ud",   "cantidad": 1,        "precio_ud": round(vol_com * 0.42, 2),
            "total": round(vol_com * 0.42, 2),
        },
        "excavacion": {
            "descripcion": f"Excavación zanjas + pozo fosa ({m3_exc}m³)",
            "ud": "m³",   "cantidad": m3_exc,  "precio_ud": 22.0,
            "total": round(m3_exc * 22.0, 2),
        },
        "mano_obra": {
            "descripcion": f"Mano de obra instalación completa ({int(h_obra)}h)",
            "ud": "h",    "cantidad": h_obra,  "precio_ud": 28.0,
            "total": round(h_obra * 28.0, 2),
        },
    }
    total_pres = round(sum(v["total"] for v in partidas.values()), 2)

    # ── 8. Resumen texto ──────────────────────────────────────────────────────
    lines = [
        "📊 CÁLCULO CTE HS-5 — SANEAMIENTO",
        f"Vivienda: {len(dormits)} dorm · {len(banos)} baños · {len(aseos)} aseos · {len(cocinas)} cocinas",
        f"Habitantes estimados: {habitantes}",
        "",
        f"APARATOS SANITARIOS  ({ud_total} UD totales):",
    ]
    for v in aparatos.values():
        lines.append(f"  · {v['nombre']}: {v['count']} ud × {v['ud_unidad']} UD = {v['count']*v['ud_unidad']} UD")
    lines += ["", "RAMALES INDIVIDUALES:"]
    for r in ramales:
        lines.append(f"  · {r['descripcion']}: {r['ud']} UD → Ø{r['diametro_mm']}mm PVC, {r['longitud_m']}m")
    lines += [
        "",
        "COLECTOR PRINCIPAL:",
        f"  · {ud_total} UD → Ø{colector['diametro_mm']}mm PVC serie B",
        f"  · Pendiente {colector['pendiente_pct']}%  ·  Longitud estimada {colector['longitud_m']}m",
        "",
        "FOSA SÉPTICA:",
        f"  · {habitantes} hab × 600 L = {vol_calc} L calculados → {vol_com} L comercial",
        f"  · {fosa['tipo']}",
        f"  · Dimensiones aprox. Ø{fosa['diametro_est_m']}m × {fosa['longitud_est_m']}m",
        "",
        f"PRESUPUESTO ORIENTATIVO (IVA incluido): €{total_pres:,.2f}",
    ]

    return {
        "aparatos":       aparatos,
        "ud_total":       ud_total,
        "ramales":        ramales,
        "colector":       colector,
        "fosa":           fosa,
        "presupuesto":    partidas,
        "total_presupuesto": total_pres,
        "resumen_texto":  "\n".join(lines),
        "meta": {
            "habitantes":  habitantes,
            "n_banos":     len(banos),
            "n_aseos":     len(aseos),
            "n_cocinas":   len(cocinas),
            "n_dormits":   len(dormits),
        },
    }


def _resultado_vacio() -> Dict:
    return {
        "aparatos": {}, "ud_total": 0, "ramales": [], "colector": {},
        "fosa": {}, "presupuesto": {}, "total_presupuesto": 0,
        "resumen_texto": "Sin datos de distribución disponibles.", "meta": {},
    }


# ─── UI Streamlit ─────────────────────────────────────────────────────────────

def render_mep_hs5_panel(rooms_layout: List[Dict], req: Dict = None) -> None:
    """
    Renderiza el panel CTE HS-5 en Streamlit.
    Llamar dentro de un st.expander o directamente.
    """
    import streamlit as st
    import json

    if isinstance(rooms_layout, str):
        try:
            rooms_layout = json.loads(rooms_layout)
        except Exception:
            rooms_layout = []

    if not rooms_layout:
        st.info("Genera primero el editor 3D para calcular las instalaciones.")
        return

    calc = calcular_saneamiento(rooms_layout, req or {})
    meta = calc["meta"]

    # KPIs superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚽 UDs totales",      calc["ud_total"])
    c2.metric("📏 Colector Ø",       f"{calc['colector'].get('diametro_mm', '—')} mm")
    c3.metric("🪣 Fosa séptica",     f"{calc['fosa'].get('vol_comercial_litros', '—')} L")
    c4.metric("💶 Presupuesto est.", f"€{calc['total_presupuesto']:,.0f}")

    st.markdown("---")
    col_a, col_b = st.columns([1, 1])

    # Aparatos sanitarios
    with col_a:
        st.markdown("**🚿 Aparatos sanitarios**")
        if calc["aparatos"]:
            rows = []
            for v in calc["aparatos"].values():
                rows.append({
                    "Aparato":  v["nombre"],
                    "Uds":      v["count"],
                    "UD/ud":    v["ud_unidad"],
                    "UD total": v["count"] * v["ud_unidad"],
                })
            import pandas as pd
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(f"Total: **{calc['ud_total']} UD** · {meta.get('habitantes',0)} habitantes estimados")

    # Ramales
    with col_b:
        st.markdown("**🔧 Ramales individuales**")
        if calc["ramales"]:
            rows2 = [
                {
                    "Ramal":       r["descripcion"],
                    "UD":          r["ud"],
                    "Ø (mm)":      r["diametro_mm"],
                    "Long. (m)":   r["longitud_m"],
                }
                for r in calc["ramales"]
            ]
            import pandas as pd
            st.dataframe(pd.DataFrame(rows2), hide_index=True, use_container_width=True)

    # Colector + fosa
    st.markdown("---")
    col_c, col_d = st.columns([1, 1])

    with col_c:
        st.markdown("**🔩 Colector principal**")
        col = calc["colector"]
        if col:
            st.markdown(f"""
| Parámetro | Valor |
|-----------|-------|
| UDs totales | {col.get('ud_total')} UD |
| Diámetro | Ø{col.get('diametro_mm')} mm |
| Material | {col.get('material')} |
| Pendiente | {col.get('pendiente_pct')}% |
| Longitud est. | {col.get('longitud_m')} m |
""")

    with col_d:
        st.markdown("**🪣 Fosa séptica**")
        fosa = calc["fosa"]
        if fosa:
            _ccaa = fosa.get("ccaa_norm") or {}
            _ccaa_row = f"| Mín. CCAA ({_ccaa.get('ccaa','—')}) | {_ccaa.get('vol_minimo_l','—')} L |\n" if _ccaa else ""
            _decreto_row = f"| Decreto | {_ccaa.get('decreto','—')} |\n" if _ccaa else ""
            _bio_row = f"| Biodigestor requerido | {'Sí ⚠️' if _ccaa.get('requiere_biodigestor') else 'No'} |\n" if _ccaa else ""
            st.markdown(f"""
| Parámetro | Valor |
|-----------|-------|
| Habitantes | {fosa.get('habitantes')} |
| Volumen calc. (CTE) | {fosa.get('vol_calc_litros')} L |
{_ccaa_row}| **Volumen comercial** | **{fosa.get('vol_comercial_litros')} L** |
{_decreto_row}{_bio_row}| Tipo | {fosa.get('tipo')} |
| Dimensiones aprox. | Ø{fosa.get('diametro_est_m')}m × {fosa.get('longitud_est_m')}m |
""")
            if _ccaa.get("nota"):
                st.caption(f"📋 {_ccaa['nota']}")

    # Presupuesto
    st.markdown("---")
    st.markdown("**💶 Presupuesto orientativo (IVA incluido)**")
    pres = calc["presupuesto"]
    if pres:
        rows3 = [
            {
                "Partida":     v["descripcion"],
                "Ud":          v["ud"],
                "Cantidad":    v["cantidad"],
                "€/ud":        f"€{v['precio_ud']:.2f}",
                "Total":       f"€{v['total']:,.2f}",
            }
            for v in pres.values()
        ]
        import pandas as pd
        st.dataframe(pd.DataFrame(rows3), hide_index=True, use_container_width=True)
        st.success(f"**TOTAL SANEAMIENTO: €{calc['total_presupuesto']:,.2f}** *(orientativo, sin proyecto de ejecución)*")

    # Descarga resumen
    st.download_button(
        "⬇️ Descargar resumen CTE HS-5 (.txt)",
        data=calc["resumen_texto"].encode("utf-8"),
        file_name="calculo_saneamiento_hs5.txt",
        mime="text/plain",
        key=f"dl_hs5_resumen_{id(calc)}",
    )
    st.caption("⚠️ Cálculo orientativo. Requiere validación por técnico competente antes de ejecución.")
