"""
modules/mls/mls_proyectos.py
Tab "Proyectos" del Portal MLS — ArchiRapid.

Muestra proyectos arquitectónicos del catálogo que encajan con las fincas
de la inmo (o con un solar que indique manualmente).

Lógica de edificabilidad: superficie_parcela × 0.33 (CTE España/Portugal).
Comisión inmo MLS: 7 % de la comisión de ArchiRapid (10 % del precio de venta)
  → 0,7 % del precio total del proyecto.
"""
from __future__ import annotations

import json
import streamlit as st

from src import db as _db
from modules.mls import mls_db

# ── Constantes ────────────────────────────────────────────────────────────────
_EDIFICABILIDAD = 0.33          # CTE España/Portugal
_ARCH_COMISION  = 0.10          # ArchiRapid cobra 10 % al arquitecto
_INMO_SHARE     = 0.07          # Inmo MLS recibe 7 % de esa comisión
_INMO_PCT       = _ARCH_COMISION * _INMO_SHARE   # 0.007 del precio de venta


# ── Query de proyectos compatibles ────────────────────────────────────────────

def _get_projects(superficie_parcela: float, budget_max: float = None) -> list:
    """
    Devuelve proyectos del catálogo que encajan en la parcela dada.

    Filtros:
      - m2_construidos (o area_m2) <= superficie_parcela × 0.33
      - m2_parcela_minima IS NULL OR m2_parcela_minima <= superficie_parcela
      - is_active = 1
      - price <= budget_max  (solo si budget_max > 0)
    Orden: price ASC. Límite 30.
    """
    edificable = superficie_parcela * _EDIFICABILIDAD
    params: list = [edificable, edificable, superficie_parcela]

    budget_clause = ""
    if budget_max and budget_max > 0:
        budget_clause = "AND COALESCE(price, 0) <= ?"
        params.append(float(budget_max))

    query = f"""
        SELECT id, title,
               COALESCE(m2_construidos, area_m2, 0) AS m2,
               COALESCE(price, 0)                   AS price,
               COALESCE(price_memoria, 1800)         AS price_memoria,
               COALESCE(price_cad, 2500)             AS price_cad,
               foto_principal, architect_name,
               COALESCE(m2_parcela_minima, 0)        AS parcela_min
        FROM projects
        WHERE is_active = 1
          AND COALESCE(m2_construidos, area_m2, 0) > 0
          AND COALESCE(m2_construidos, area_m2, 0) <= ?
          AND (
               COALESCE(m2_construidos, area_m2, 0) <= ?
          )
          AND (m2_parcela_minima IS NULL OR m2_parcela_minima <= ?)
          {budget_clause}
        ORDER BY price ASC
        LIMIT 30
    """
    try:
        conn = _db.get_conn()
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def _comision_inmo(price_memoria: float, price_cad: float) -> float:
    """Comisión estimada para la inmo MLS = 7% de (10% del precio total)."""
    total = (price_memoria or 1800) + (price_cad or 2500)
    return round(total * _INMO_PCT, 2)


# ── UI principal ──────────────────────────────────────────────────────────────

def ui_tab_proyectos(inmo: dict) -> None:
    """Tab Proyectos del portal MLS."""

    st.markdown("### 🏗️ Catálogo de Proyectos")
    st.caption(
        "Encuentra proyectos arquitectónicos que encajan en las fincas de tus clientes. "
        "Si la venta se cierra, recibes una comisión sobre la descarga."
    )

    with st.expander("ℹ️ ¿Cómo funciona la comisión?", expanded=False):
        st.markdown(
            f"""
**Cuando un cliente compra un proyecto a través de tu gestión:**
- ArchiRapid cobra al arquitecto el **10 %** del precio de venta.
- Tú recibes el **7 %** de esa comisión = **0,7 %** del precio total del proyecto.

**Ejemplo:** Proyecto con Memoria PDF (€1.800) + Planos CAD (€2.500) = **€4.300**
→ ArchiRapid comisión: **€430**
→ **Tu parte: €{4300 * _INMO_PCT:,.0f}** por ese proyecto vendido.

Para formalizar la venta contacta con ArchiRapid indicando la REF del proyecto y los datos del cliente.
"""
        )

    st.divider()

    # ── Obtener fincas de esta inmo ──────────────────────────────────────────
    fincas = mls_db.get_fincas_by_inmo(inmo["id"])
    fincas_activas = [
        f for f in fincas
        if f.get("estado") not in ("cerrada", "eliminada", "expirada")
        and f.get("superficie_m2")
    ]

    # ── Inputs ───────────────────────────────────────────────────────────────
    col_input, col_budget = st.columns([2, 1])

    with col_input:
        if fincas_activas:
            opciones = {
                f["id"]: f"{f.get('titulo') or f['id'][:8]}  ·  {f.get('superficie_m2', 0):,.0f} m²"
                for f in fincas_activas
            }
            finca_sel_id = st.selectbox(
                "Selecciona una de tus fincas",
                options=list(opciones.keys()),
                format_func=lambda k: opciones[k],
                key="mls_proy_finca_sel",
            )
            finca_sel = next((f for f in fincas_activas if f["id"] == finca_sel_id), None)
            superficie = float(finca_sel["superficie_m2"]) if finca_sel else 0.0
            edificable = superficie * _EDIFICABILIDAD
            st.caption(
                f"📐 Parcela: **{superficie:,.0f} m²** · "
                f"Edificable CTE 0,33: **{edificable:,.0f} m²**"
            )
        else:
            st.info("Aún no tienes fincas activas. Introduce los datos del solar del cliente manualmente.")
            superficie = st.number_input(
                "Superficie del solar del cliente (m²)",
                min_value=50.0,
                max_value=50_000.0,
                value=500.0,
                step=50.0,
                key="mls_proy_m2_manual",
            )
            edificable = superficie * _EDIFICABILIDAD
            st.caption(f"📐 Edificable CTE 0,33: **{edificable:,.0f} m²**")

    with col_budget:
        budget_max = st.number_input(
            "Presupuesto máx. cliente (€)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=0.0,
            step=10_000.0,
            format="%.0f",
            help="0 = sin límite de presupuesto",
            key="mls_proy_budget",
        )

    btn_buscar = st.button(
        "🔍 Ver proyectos compatibles",
        type="primary",
        key="mls_proy_buscar_btn",
    )

    if not btn_buscar and "mls_proy_results" not in st.session_state:
        return

    if btn_buscar:
        if superficie <= 0:
            st.warning("Introduce una superficie válida.")
            return
        with st.spinner("Buscando proyectos compatibles…"):
            proyectos = _get_projects(superficie, budget_max if budget_max > 0 else None)
        st.session_state["mls_proy_results"] = proyectos
        st.session_state["mls_proy_edificable"] = edificable

    proyectos = st.session_state.get("mls_proy_results", [])
    edificable_cached = st.session_state.get("mls_proy_edificable", edificable)

    st.divider()

    if not proyectos:
        st.warning(
            f"No se encontraron proyectos que encajen en **{edificable_cached:,.0f} m²** construibles"
            + (f" con presupuesto ≤ **€{budget_max:,.0f}**" if budget_max > 0 else "")
            + ". Prueba a ampliar el presupuesto o revisar la superficie."
        )
        return

    st.success(
        f"✅ **{len(proyectos)} proyectos** encajan en {edificable_cached:,.0f} m² edificables"
        + (f" · presupuesto ≤ €{budget_max:,.0f}" if budget_max > 0 else "")
    )

    # ── Grid de resultados ───────────────────────────────────────────────────
    cols = st.columns(3)
    for idx, p in enumerate(proyectos):
        with cols[idx % 3]:
            with st.container(border=True):
                # Foto
                foto = p.get("foto_principal")
                if foto:
                    try:
                        st.image(foto, use_container_width=True)
                    except Exception:
                        pass

                titulo   = p.get("title") or "Proyecto"
                m2       = float(p.get("m2") or 0)
                price    = float(p.get("price") or 0)
                p_mem    = float(p.get("price_memoria") or 1800)
                p_cad    = float(p.get("price_cad") or 2500)
                arq      = p.get("architect_name") or "ArchiRapid"
                comision = _comision_inmo(p_mem, p_cad)

                st.markdown(f"**{titulo}**")
                st.caption(f"👤 {arq}")
                st.markdown(
                    f"📐 **{m2:,.0f} m²** construidos  \n"
                    f"💰 Precio: **€{price:,.0f}**  \n"
                    f"📄 Memoria: €{p_mem:,.0f}  ·  🖥️ CAD: €{p_cad:,.0f}"
                )
                st.markdown(
                    f"<div style='background:#f0f7ff;border-radius:4px;padding:6px 8px;"
                    f"font-size:12px;margin-top:4px;'>"
                    f"💼 <b>Tu comisión estimada: €{comision:,.2f}</b></div>",
                    unsafe_allow_html=True,
                )
                st.link_button(
                    "Ver proyecto completo →",
                    f"/?selected_project_v2={p['id']}",
                    use_container_width=True,
                )
