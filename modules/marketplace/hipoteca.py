# modules/marketplace/hipoteca.py
"""
Calculadora de hipoteca ArchiRapid
Fórmula francesa de amortización (cuota constante).
Sin dependencias externas.
"""
import streamlit as st


def _cuota_mensual(principal: float, tasa_anual: float, anos: int) -> float:
    """Cuota mensual constante (sistema francés)."""
    if principal <= 0 or anos <= 0:
        return 0.0
    r = tasa_anual / 100 / 12          # tipo mensual
    n = anos * 12                       # número de cuotas
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def render_calculadora(
    precio_terreno: float = 0.0,
    coste_construccion: float = 0.0,
    key_prefix: str = "hip"
):
    """
    Renderiza la calculadora de hipoteca en línea.
    precio_terreno y coste_construccion son los valores pre-cargados del contexto.
    key_prefix evita colisiones si se usa en varias páginas.
    """
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0D1B2A,#1a2f4a);border-radius:14px;
                padding:20px 24px;border:1px solid rgba(245,158,11,0.25);margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
            <span style="font-size:1.6em;">🏦</span>
            <div>
                <div style="font-weight:800;color:#F8FAFC;font-size:1.05em;">
                    Calculadora de Financiación
                </div>
                <div style="color:#94A3B8;font-size:0.83em;">
                    Estimación orientativa · Datos del BCE · No vinculante
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        v_terreno = st.number_input(
            "💰 Precio del terreno (€)",
            min_value=0.0, max_value=5_000_000.0,
            value=float(precio_terreno),
            step=5_000.0, format="%.0f",
            key=f"{key_prefix}_terreno"
        )
        v_obra = st.number_input(
            "🏗️ Coste estimado de construcción (€)",
            min_value=0.0, max_value=5_000_000.0,
            value=float(coste_construccion) if coste_construccion > 0 else float(precio_terreno * 0.8),
            step=5_000.0, format="%.0f",
            key=f"{key_prefix}_obra",
            help="Orientativo: 900–2.000 €/m² según calidad y zona"
        )
        v_entrada_pct = st.slider(
            "📥 Aportación inicial (%)",
            min_value=5, max_value=50, value=20, step=5,
            key=f"{key_prefix}_entrada"
        )

    with c2:
        v_tipo = st.number_input(
            "📈 Tipo de interés anual (%)",
            min_value=0.5, max_value=15.0, value=3.5, step=0.1, format="%.2f",
            key=f"{key_prefix}_tipo",
            help="Euríbor + diferencial bancario. Referencia actual ~3,2%–3,8%"
        )
        v_anos = st.slider(
            "📅 Plazo (años)",
            min_value=5, max_value=35, value=25, step=5,
            key=f"{key_prefix}_anos"
        )

    # ── Cálculo ───────────────────────────────────────────────────────────────
    total_proyecto = v_terreno + v_obra
    entrada_eur    = total_proyecto * v_entrada_pct / 100
    principal      = total_proyecto - entrada_eur
    cuota          = _cuota_mensual(principal, v_tipo, v_anos)
    total_pagado   = cuota * v_anos * 12 + entrada_eur
    total_intereses= (cuota * v_anos * 12) - principal

    # ── KPIs resultado ────────────────────────────────────────────────────────
    st.markdown("")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("🏠 Coste total proyecto",  f"€{total_proyecto:,.0f}")
    r2.metric("📥 Entrada necesaria",      f"€{entrada_eur:,.0f}",
              delta=f"{v_entrada_pct}% del total")
    r3.metric("💳 Cuota mensual",          f"€{cuota:,.0f}",
              delta=f"{v_anos} años · {v_tipo}%")
    r4.metric("💸 Total intereses",        f"€{total_intereses:,.0f}",
              delta=f"Total pagado €{total_proyecto + total_intereses:,.0f}", delta_color="inverse")

    # ── Barra de desglose visual ──────────────────────────────────────────────
    if total_pagado > 0:
        pct_entrada  = entrada_eur    / total_pagado * 100
        pct_capital  = principal      / total_pagado * 100
        pct_intereses= total_intereses/ total_pagado * 100
        st.markdown(f"""
        <div style="margin:12px 0 4px;font-size:12px;color:#94A3B8;">Desglose del coste total</div>
        <div style="display:flex;height:22px;border-radius:8px;overflow:hidden;gap:2px;">
            <div style="width:{pct_entrada:.1f}%;background:#10B981;" title="Entrada"></div>
            <div style="width:{pct_capital:.1f}%;background:#2563EB;" title="Capital"></div>
            <div style="width:{pct_intereses:.1f}%;background:#F59E0B;" title="Intereses"></div>
        </div>
        <div style="display:flex;gap:20px;margin-top:6px;font-size:11px;color:#94A3B8;">
            <span><span style="color:#10B981;">■</span> Entrada {pct_entrada:.0f}%</span>
            <span><span style="color:#2563EB;">■</span> Capital {pct_capital:.0f}%</span>
            <span><span style="color:#F59E0B;">■</span> Intereses {pct_intereses:.0f}%</span>
        </div>
        """, unsafe_allow_html=True)

    st.caption(
        "⚠️ Cálculo orientativo. La cuota real depende de la entidad bancaria, "
        "tu perfil crediticio y las condiciones del mercado. "
        "Consulta con tu banco antes de tomar decisiones. "
        "Tipo Euríbor 12m referencia: BCE."
    )
