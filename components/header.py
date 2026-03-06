import streamlit as st


def render_header(logo_path: str = "assets/branding/logo.png", tagline: str = "Del terreno a tu casa — tecnología e inteligencia artificial"):
    """Render header con logo a la izquierda y tagline profesional."""
    cols = st.columns([1, 4, 1])
    with cols[0]:
        try:
            st.image(logo_path, width=140)
        except Exception:
            st.markdown("**🏗️ ARCHIRAPID**")
    with cols[1]:
        st.markdown(f"""
        <div style="padding-top:10px">
            <span style="font-size:0.72em;font-weight:700;color:#2563EB;letter-spacing:1.5px;text-transform:uppercase;">IA · CATASTRO · ARQUITECTURA</span><br>
            <span style="font-size:1.6em;font-weight:900;color:#0D1B2A;letter-spacing:-0.5px;">{tagline}</span>
        </div>
        """, unsafe_allow_html=True)
    return cols
