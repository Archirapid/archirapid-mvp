"""
modules/mls/mls_mapa.py
Pins naranjas (MLS inmobiliarias) para el mapa Folium existente.

Sin imports de Streamlit.
Todas las funciones son seguras: nunca propagan excepciones al llamador.
"""

import folium


# =============================================================================
# CONSULTA DE DATOS
# =============================================================================

def get_fincas_mls_para_mapa() -> list:
    """
    Devuelve fincas MLS aptas para el pin naranja en el mapa.

    Filtros:
      - catastro_validada = 1
      - estado IN ('publicada', 'reservada', 'reserva_pendiente_confirmacion')
      - catastro_lat IS NOT NULL
      - catastro_lon IS NOT NULL

    Columnas devueltas: id, ref_codigo, titulo, precio,
      catastro_lat, catastro_lon, superficie_m2, estado
    inmo_id NUNCA incluido (guardia defensiva con assert).

    Devuelve [] ante cualquier error — nunca propaga excepciones.
    """
    try:
        from src import db as _db
        conn = _db.get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, ref_codigo, titulo, precio,
                      catastro_lat, catastro_lon, superficie_m2, estado
               FROM fincas_mls
               WHERE catastro_validada = 1
                 AND estado IN (
                     'publicada',
                     'reservada',
                     'reserva_pendiente_confirmacion'
                 )
                 AND catastro_lat  IS NOT NULL
                 AND catastro_lon  IS NOT NULL
               ORDER BY created_at DESC"""
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        # Guardia defensiva: inmo_id nunca debe aparecer en los datos del mapa
        for row in rows:
            assert "inmo_id" not in row, (
                "SEGURIDAD: inmo_id presente en datos del mapa MLS"
            )
        return rows
    except Exception:
        return []


# =============================================================================
# POPUP HTML
# =============================================================================

# Estilo de botón idéntico al popup azul existente (misma fuente, mismo padding)
_BTN_BASE = (
    "margin-top:4px;padding:5px 10px;color:white;"
    "text-decoration:none;border-radius:3px;"
    "display:inline-block;font-weight:600;font-size:12px;"
)


def _popup_html_naranja(finca: dict) -> str:
    """
    Genera el HTML del popup para un pin naranja MLS.

    Estilo replicado exactamente del popup azul existente:
      width:180px · font-family:sans-serif · font-size:13px
      max_width=250 · mismo padding de botones (5px 10px)
      misma fuente y tamaños

    Sin comisiones, sin identidad de listante.
    """
    finca_id  = finca.get("id", "")
    titulo    = finca.get("titulo") or "Finca MLS"
    ref       = finca.get("ref_codigo") or "—"
    m2        = finca.get("superficie_m2")
    precio    = float(finca.get("precio") or 0)
    estado    = finca.get("estado", "publicada")

    m2_str    = f"{m2:,.0f}" if m2 else "N/A"

    # Badge de reserva si corresponde (visible, no revela colaboradora)
    reserva_badge = ""
    if estado in ("reservada", "reserva_pendiente_confirmacion"):
        reserva_badge = (
            "<small style='color:orange;'>🔒 Reserva activa</small><br>"
        )

    return f"""<div style="width:180px;font-family:sans-serif;font-size:13px;">
  <div style="color:#F5A623;font-weight:700;font-size:12px;margin-bottom:4px;">
    🟠 ArchiRapid MLS
  </div>
  <b style="font-size:13px;">{titulo}</b><br>
  {reserva_badge}
  <span style="color:#64748B;">REF: {ref}</span><br>
  <span style="color:#64748B;">{m2_str} m²</span>&nbsp;·&nbsp;
  <b style="color:#1B2A6B;">€{precio:,.0f}</b><br>
  <a href="/?mls_ficha={finca_id}"
     style="{_BTN_BASE}background:#1B2A6B;">
    Ver ficha →
  </a>
  <a href="/?mls_reservar={finca_id}"
     style="{_BTN_BASE}background:#F5A623;color:#1B2A6B;">
    Reservar €200
  </a>
  <a href="/?mls_contacto={finca_id}"
     style="{_BTN_BASE}background:#64748B;">
    Solicitar info
  </a>
</div>"""


# =============================================================================
# INYECCIÓN DE MARKERS
# =============================================================================

def add_mls_markers_to_map(m, fincas: list) -> None:
    """
    Añade pins naranjas al mapa Folium m para cada finca MLS.

    Pin:     folium.Icon(color='orange', icon='building', prefix='fa')
    Popup:   HTML idéntico en estilo al popup azul (width:180px, sans-serif, 13px)
    Tooltip: "{titulo} | €{precio:,.0f}"

    Comportamiento de fallos:
      - Finca sin lat/lon: skip silencioso (continue)
      - Finca individual con error: skip silencioso, continúa con las demás
      - El mapa azul existente NUNCA se ve afectado
    """
    for finca in fincas:
        try:
            lat = finca.get("catastro_lat")
            lon = finca.get("catastro_lon")
            if lat is None or lon is None:
                continue  # skip silencioso

            titulo = finca.get("titulo") or "Finca MLS"
            precio = float(finca.get("precio") or 0)

            icon = folium.Icon(
                color="orange",
                icon="building",
                prefix="fa",
            )
            marker = folium.Marker(
                location=[float(lat), float(lon)],
                icon=icon,
                popup=folium.Popup(_popup_html_naranja(finca), max_width=250),
                tooltip=f"{titulo} | €{precio:,.0f}",
            )
            marker.add_to(m)

        except Exception:
            continue  # finca individual falla → siguiente finca
