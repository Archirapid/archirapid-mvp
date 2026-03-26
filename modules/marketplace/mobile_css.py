# modules/marketplace/mobile_css.py
"""
CSS responsivo para móvil — ArchiRapid
Inyectado una vez al inicio de app.py.
Solo activa en pantallas <= 768px (media query).
Desktop completamente intacto.
"""
import streamlit as st

_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════
   ARCHIRAPID — Mobile CSS  |  Solo aplica en <= 768px
   ═══════════════════════════════════════════════════════════ */

@media (max-width: 768px) {

  /* ── Contenedor principal: menos padding lateral ── */
  section.main .block-container {
    padding-left: 12px  !important;
    padding-right: 12px !important;
    padding-top: 12px   !important;
    max-width: 100%     !important;
  }

  /* ── Botones: área táctil mínima 44px (Apple HIG) ── */
  .stButton > button {
    min-height: 44px    !important;
    font-size: 15px     !important;
    padding: 10px 16px  !important;
    width: 100%         !important;
    border-radius: 8px  !important;
  }

  /* ── Inputs de texto: 16px evita zoom automático en iOS ── */
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input,
  .stTextArea > div > textarea,
  .stSelectbox > div > div > div,
  .stMultiSelect > div > div > div {
    font-size: 16px     !important;
    min-height: 44px    !important;
    padding: 10px 12px  !important;
  }

  /* ── Selectbox altura táctil ── */
  .stSelectbox > div > div {
    min-height: 44px !important;
  }

  /* ── Checkboxes y radio: área táctil ampliada ── */
  .stCheckbox > label,
  .stRadio > div > label {
    padding: 8px 4px    !important;
    font-size: 15px     !important;
    line-height: 1.5    !important;
  }

  /* ── Tabs: fuente y padding para dedos ── */
  .stTabs [role="tab"] {
    font-size: 13px     !important;
    padding: 10px 10px  !important;
    min-height: 44px    !important;
  }

  /* ── Expanders: área de click más generosa (Streamlit 1.42+) ── */
  details[data-testid="stExpander"] summary {
    font-size: 14px     !important;
    padding: 12px 8px   !important;
    min-height: 44px    !important;
  }

  /* ── Texto general: legible sin lupa ── */
  .stMarkdown p,
  .stMarkdown li,
  .stMarkdown td,
  .stMarkdown th {
    font-size: 14px     !important;
    line-height: 1.65   !important;
  }

  /* ── Títulos: escala móvil ── */
  .stMarkdown h1 { font-size: 1.5rem  !important; }
  .stMarkdown h2 { font-size: 1.3rem  !important; }
  .stMarkdown h3 { font-size: 1.1rem  !important; }

  /* ── Métricas (st.metric): más compactas ── */
  [data-testid="metric-container"] {
    padding: 10px 8px   !important;
  }
  [data-testid="metric-container"] label {
    font-size: 12px     !important;
  }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.2rem   !important;
  }

  /* ── Tarjetas HTML personalizadas: no desbordan ── */
  .stMarkdown div[style],
  .element-container div[style] {
    max-width: 100%     !important;
    box-sizing: border-box !important;
  }

  /* ── Tablas y dataframes: scroll horizontal suave ── */
  .stDataFrame,
  [data-testid="stTable"] {
    overflow-x: auto    !important;
    -webkit-overflow-scrolling: touch !important;
    max-width: 100%     !important;
  }

  /* ── Columnas Streamlit: scroll suave si no caben ── */
  [data-testid="column"] {
    min-width: 0        !important;
    overflow: hidden    !important;
  }

  /* ── Sidebar: pantalla completa en móvil (Streamlit ya lo hace,
        esto refuerza el botón de apertura) ── */
  [data-testid="collapsedControl"] {
    top: 8px            !important;
  }

  /* ── Imágenes: nunca desbordan ── */
  .stImage img {
    max-width: 100%     !important;
    height: auto        !important;
    border-radius: 8px  !important;
  }

  /* ── Alertas/info: padding compacto ── */
  .stAlert {
    padding: 10px 12px  !important;
    font-size: 13px     !important;
  }

  /* ── Captions ── */
  .stCaption {
    font-size: 12px     !important;
    line-height: 1.5    !important;
  }

  /* ── Form submit buttons: prominentes ── */
  [data-testid="stFormSubmitButton"] > button {
    min-height: 48px    !important;
    font-size: 16px     !important;
    font-weight: 700    !important;
  }

  /* ── Scrollbar horizontal invisible pero funcional ── */
  ::-webkit-scrollbar {
    height: 4px         !important;
    width: 4px          !important;
  }
  ::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.2) !important;
    border-radius: 4px  !important;
  }
}

/* ── Fuera del media query: mejoras universales leves ── */

/* Evitar que inputs hagan zoom en iOS (aplica siempre, inofensivo en desktop) */
input[type="text"],
input[type="email"],
input[type="password"],
input[type="number"],
textarea,
select {
  font-size: 16px !important;
}

/* Imágenes nunca desbordan su contenedor (inofensivo en desktop) */
img {
  max-width: 100%;
  height: auto;
}

/* ── Eliminar espacio muerto en cabecera (todas las pantallas) ─────────────
   Streamlit añade ~80-100px vacíos arriba por defecto.
   Reducimos al mínimo sin ocultar la toolbar de Streamlit Cloud. */
header[data-testid="stHeader"] {
  height: 3rem            !important;
  min-height: 0           !important;
  background: transparent !important;
}
.block-container {
  padding-top: 0.75rem    !important;
}
</style>
"""


def inject():
    """Llama esta función una sola vez al inicio de app.py."""
    st.markdown(_CSS, unsafe_allow_html=True)
