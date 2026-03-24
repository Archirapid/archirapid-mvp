"""
modules/mls/mls_prefabricadas.py
Tab "Prefabricadas" del Portal MLS — ArchiRapid.

Muestra casas prefabricadas del catálogo que físicamente caben en la parcela
del cliente (m² prefab <= edificable = parcela × 0.33).

Comisión inmo MLS: 7 % de la comisión del 10 % de ArchiRapid = 0,7 % del precio.
"""
from __future__ import annotations

import streamlit as st

from src import db as _db
from modules.mls import mls_db

# ── Constantes ────────────────────────────────────────────────────────────────
_EDIFICABILIDAD   = 0.33
_INSTALL_POR_M2   = 180.0    # €/m² estimación de instalación/cimentación
_ARCH_COMISION    = 0.10
_INMO_SHARE       = 0.07
_INMO_PCT         = _ARCH_COMISION * _INMO_SHARE   # 0.007


# ── Query ─────────────────────────────────────────────────────────────────────

def _get_prefabs(superficie_parcela: float, budget_max: float = None) -> list:
    """
    Prefabricadas cuya superficie construida cabe en la parcela dada.
    Filtro: m2 <= superficie_parcela × 0.33
    """
    edificable = superficie_parcela * _EDIFICABILIDAD
    params: list = [edificable]

    budget_clause = ""
    if budget_max and budget_max > 0:
        budget_clause = "AND COALESCE(price, 0) <= ?"
        params.append(float(budget_max))

    query = f"""
        SELECT id, name, m2, rooms, bathrooms, floors, material,
               COALESCE(price, 0)  AS price,
               price_label, image_path, image_paths, description
        FROM prefab_catalog
        WHERE active = 1
          AND m2 > 0
          AND m2 <= ?
          {budget_clause}
        ORDER BY m2 ASC
        LIMIT 30
    """
    try:
        conn = _db.get_conn()
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def _comision_inmo(price: float) -> float:
    return round(price * _INMO_PCT, 2)


# ── UI ────────────────────────────────────────────────────────────────────────

def ui_tab_prefabricadas(inmo: dict) -> None:
    """Tab Prefabricadas del portal MLS."""

    st.markdown("### 🏡 Casas Prefabricadas")
    st.caption(
        "Explora el catálogo de casas prefabricadas que encajan en los solares de tus clientes. "
        "Precio prefabricada + instalación estimada en cada tarjeta."
    )

    with st.expander("ℹ️ ¿Cómo funciona la comisión?", expanded=False):
        st.markdown(
            f"""
**Cuando un cliente adquiere una prefabricada a través de tu gestión:**
- ArchiRapid cobra al proveedor el **10 %** del precio de venta.
- Tú recibes el **7 %** de esa comisión = **0,7 %** del precio de la prefabricada.

**Ejemplo:** Prefabricada €144.000
→ Comisión ArchiRapid: **€14.400**
→ **Tu parte: €{144000 * _INMO_PCT:,.0f}**

Para gestionar la venta contacta con ArchiRapid indicando el modelo y datos del cliente.
"""
        )

    st.divider()

    # ── Inputs ───────────────────────────────────────────────────────────────
    fincas = mls_db.get_fincas_by_inmo(inmo["id"])
    fincas_activas = [
        f for f in fincas
        if f.get("estado") not in ("cerrada", "eliminada", "expirada")
        and f.get("superficie_m2")
    ]

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
                key="mls_pref_finca_sel",
            )
            finca_sel = next((f for f in fincas_activas if f["id"] == finca_sel_id), None)
            superficie = float(finca_sel["superficie_m2"]) if finca_sel else 0.0
        else:
            st.info("Sin fincas activas. Introduce los datos del solar del cliente manualmente.")
            superficie = st.number_input(
                "Superficie del solar del cliente (m²)",
                min_value=50.0,
                max_value=50_000.0,
                value=500.0,
                step=50.0,
                key="mls_pref_m2_manual",
            )

        edificable = superficie * _EDIFICABILIDAD
        st.caption(f"📐 Edificable CTE 0,33: **{edificable:,.0f} m²**")

    with col_budget:
        budget_max = st.number_input(
            "Presupuesto máx. cliente (€)",
            min_value=0.0,
            max_value=5_000_000.0,
            value=0.0,
            step=10_000.0,
            format="%.0f",
            help="0 = sin límite",
            key="mls_pref_budget",
        )

    btn_buscar = st.button(
        "🔍 Ver prefabricadas compatibles",
        type="primary",
        key="mls_pref_buscar_btn",
    )

    if not btn_buscar and "mls_pref_results" not in st.session_state:
        return

    if btn_buscar:
        if superficie <= 0:
            st.warning("Introduce una superficie válida.")
            return
        with st.spinner("Buscando prefabricadas compatibles…"):
            prefabs = _get_prefabs(superficie, budget_max if budget_max > 0 else None)
        st.session_state["mls_pref_results"] = prefabs
        st.session_state["mls_pref_edificable"] = edificable

    prefabs = st.session_state.get("mls_pref_results", [])
    edificable_cached = st.session_state.get("mls_pref_edificable", edificable)

    st.divider()

    if not prefabs:
        st.warning(
            f"No se encontraron prefabricadas que encajen en **{edificable_cached:,.0f} m²** construibles"
            + (f" con presupuesto ≤ **€{budget_max:,.0f}**" if budget_max > 0 else "")
            + "."
        )
        return

    st.success(f"✅ **{len(prefabs)} modelos** compatibles con {edificable_cached:,.0f} m² edificables")

    # ── Grid ─────────────────────────────────────────────────────────────────
    cols = st.columns(3)
    for idx, p in enumerate(prefabs):
        with cols[idx % 3]:
            with st.container(border=True):
                # Foto
                import json as _json
                foto = None
                try:
                    imgs = _json.loads(p.get("image_paths") or "[]")
                    foto = imgs[0] if imgs else p.get("image_path")
                except Exception:
                    foto = p.get("image_path")
                if foto:
                    try:
                        st.image(foto, use_container_width=True)
                    except Exception:
                        pass

                name      = p.get("name") or "Prefabricada"
                m2        = float(p.get("m2") or 0)
                price     = float(p.get("price") or 0)
                p_label   = p.get("price_label")
                rooms     = p.get("rooms", "—")
                baths     = p.get("bathrooms", "—")
                floors    = p.get("floors", 1)
                material  = p.get("material") or "—"
                install   = round(m2 * _INSTALL_POR_M2, -2)
                comision  = _comision_inmo(price)

                precio_str = p_label if p_label else f"€{price:,.0f}"
                total_str  = f"€{(price + install):,.0f}" if not p_label else "A consultar"

                st.markdown(f"**{name}**")
                st.caption(f"🧱 {material}  ·  {floors} planta{'s' if floors > 1 else ''}")
                st.markdown(
                    f"📐 **{m2:,.0f} m²**  ·  🛏 {rooms} hab.  ·  🚿 {baths} baños  \n"
                    f"🏷️ Prefab: **{precio_str}**  \n"
                    f"🔧 Instalación estimada: **€{install:,.0f}** ({_INSTALL_POR_M2:.0f}€/m²)  \n"
                    f"📦 Total estimado: **{total_str}**"
                )
                if price > 0:
                    st.markdown(
                        f"<div style='background:#f0f7ff;border-radius:4px;padding:6px 8px;"
                        f"font-size:12px;margin-top:4px;'>"
                        f"💼 <b>Tu comisión estimada: €{comision:,.2f}</b></div>",
                        unsafe_allow_html=True,
                    )
                st.link_button(
                    "Ver modelo completo →",
                    f"/?selected_prefab={p['id']}",
                    use_container_width=True,
                )
