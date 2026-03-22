"""
modules/mls/mls_publico.py
Páginas públicas MLS — sin login requerido.

Cuatro funciones de UI para los botones del popup naranja:
  show_ficha_publica(finca_id)       — ficha pública (cualquier usuario, sin login)
  show_reservar_publico(finca_id)    — formulario reserva €200 Stripe
  show_contacto_publico(finca_id)    — formulario contacto sin pago
  show_retorno_reserva_cliente()     — handler retorno Stripe tipo=cliente_directo

Seguridad:
  - Solo usa get_finca_sin_identidad_listante() — inmo_id NUNCA expuesto
  - No muestra REF MLS, comisiones ni datos identificativos de la listante
  - Zero imports de mls_portal (no arrastra login gate)
"""
import json
import os

import streamlit as st

from modules.mls import mls_db


# =============================================================================
# SHOW FICHA PÚBLICA
# =============================================================================

def show_ficha_publica(finca_id: str) -> None:
    """Ficha pública de una finca MLS. Sin login. Sin identidad listante."""
    if not finca_id:
        st.error("Referencia de finca no encontrada.")
        return

    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        st.error("Esta finca no está disponible o no existe.")
        return

    estado    = finca.get("estado", "publicada")
    reservada = estado in ("reservada", "reserva_pendiente_confirmacion")
    titulo    = finca.get("titulo") or "Finca MLS"
    precio    = float(finca.get("precio") or 0)
    superficie = finca.get("superficie_m2")
    catastro_ref = finca.get("catastro_ref") or "—"
    descripcion  = finca.get("descripcion_publica") or ""
    lat = finca.get("catastro_lat")
    lon = finca.get("catastro_lon")

    # ── Cabecera ──────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='color:#F5A623;font-weight:700;font-size:13px;"
        "margin-bottom:4px;'>🟠 ArchiRapid MLS</div>",
        unsafe_allow_html=True,
    )
    st.title(titulo)

    if reservada:
        st.warning("🔒 Esta finca tiene una reserva activa en este momento.")

    # ── Métricas principales ──────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    if precio:
        col1.metric("Precio", f"€{precio:,.0f}")
    if superficie:
        col2.metric("Superficie", f"{superficie:,.0f} m²")
    col3.markdown(f"**Ref. catastral**  \n`{catastro_ref}`")

    # ── Descripción ───────────────────────────────────────────────────────────
    if descripcion:
        st.markdown("---")
        st.markdown("### Descripción")
        st.markdown(descripcion)

    # ── Imágenes ──────────────────────────────────────────────────────────────
    raw_paths = finca.get("image_paths") or "[]"
    try:
        paths = json.loads(raw_paths) if isinstance(raw_paths, str) else raw_paths
        if not isinstance(paths, list):
            paths = []
    except Exception:
        paths = []

    if paths:
        st.markdown("---")
        st.markdown("### Imágenes")
        img_cols = st.columns(min(len(paths), 3))
        for i, rel_path in enumerate(paths[:6]):
            try:
                norm = rel_path.replace("\\", "/")
                if os.path.exists(norm):
                    with open(norm, "rb") as f:
                        import base64
                        b64 = base64.b64encode(f.read()).decode()
                    ext  = os.path.splitext(norm)[1].lower().lstrip(".")
                    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
                    img_cols[i % 3].markdown(
                        f'<img src="data:image/{mime};base64,{b64}" '
                        f'style="width:100%;border-radius:6px;margin-bottom:6px;">',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

    # ── Mini mapa ─────────────────────────────────────────────────────────────
    if lat and lon:
        try:
            import folium
            import streamlit.components.v1 as _stc
            m = folium.Map(location=[float(lat), float(lon)], zoom_start=15)
            folium.Marker(
                location=[float(lat), float(lon)],
                icon=folium.Icon(color="orange", icon="building", prefix="fa"),
                tooltip=titulo,
            ).add_to(m)
            st.markdown("---")
            st.markdown("### Ubicación")
            st.caption("Ubicación aproximada — dirección exacta disponible tras reserva")
            _stc.html(m._repr_html_(), height=300)
        except Exception:
            pass

    # ── CTAs ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    if reservada:
        st.info(
            "Esta finca está actualmente reservada.  \n"
            "Puedes dejarnos tu contacto por si quedara libre."
        )
        _form_contacto(finca)
    else:
        cta1, cta2 = st.columns(2)
        with cta1:
            if st.button(
                "💳 Reservar esta finca (€200)",
                type="primary",
                key="fp_btn_reservar",
            ):
                st.session_state["selected_page"] = "_mls_reservar_publica"
                st.session_state["mls_reservar_id"] = finca_id
                st.rerun()
        with cta2:
            if st.button("✉️ Solicitar más información", key="fp_btn_contactar"):
                st.session_state["_fp_show_contacto"] = True
                st.rerun()

        if st.session_state.get("_fp_show_contacto"):
            st.markdown("---")
            _form_contacto(finca)

    st.markdown("---")
    st.markdown("[← Volver al mapa](/)")


# =============================================================================
# SHOW RESERVAR PÚBLICO
# =============================================================================

def show_reservar_publico(finca_id: str) -> None:
    """Formulario de reserva €200 para cliente directo desde pin naranja."""
    if not finca_id:
        st.error("Referencia de finca no encontrada.")
        return

    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        st.error("Esta finca no está disponible.")
        return

    estado = finca.get("estado", "publicada")
    if estado not in ("publicada",):
        st.warning("🔒 Esta finca no está disponible para reserva en este momento.")
        st.markdown("[← Volver al mapa](/)")
        return

    st.markdown(
        "<div style='color:#F5A623;font-weight:700;font-size:13px;"
        "margin-bottom:4px;'>🟠 ArchiRapid MLS</div>",
        unsafe_allow_html=True,
    )

    from modules.mls.mls_reservas import ui_formulario_reserva_cliente_directo
    ui_formulario_reserva_cliente_directo(finca)

    st.markdown("---")
    st.markdown("[← Volver al mapa](/)")


# =============================================================================
# SHOW CONTACTO PÚBLICO
# =============================================================================

def show_contacto_publico(finca_id: str) -> None:
    """Formulario de contacto sin pago para una finca MLS."""
    if not finca_id:
        st.error("Referencia de finca no encontrada.")
        return

    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        st.error("Esta finca no está disponible.")
        return

    titulo = finca.get("titulo") or "Finca MLS"
    precio = float(finca.get("precio") or 0)

    st.markdown(
        "<div style='color:#F5A623;font-weight:700;font-size:13px;"
        "margin-bottom:4px;'>🟠 ArchiRapid MLS</div>",
        unsafe_allow_html=True,
    )
    st.subheader("✉️ Solicitar información")
    st.markdown(f"**{titulo}** · €{precio:,.0f}")
    st.markdown("---")

    _form_contacto(finca)

    st.markdown("---")
    st.markdown("[← Volver al mapa](/)")


# =============================================================================
# SHOW RETORNO RESERVA CLIENTE (handler Stripe tipo=cliente_directo)
# =============================================================================

def show_retorno_reserva_cliente() -> None:
    """Handler de retorno Stripe para tipo=cliente_directo."""
    st.markdown(
        "<div style='color:#F5A623;font-weight:700;font-size:13px;"
        "margin-bottom:4px;'>🟠 ArchiRapid MLS</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Confirmación de reserva")

    from modules.mls.mls_reservas import ui_handler_retorno_stripe
    ui_handler_retorno_stripe(dict(st.query_params))

    st.markdown("---")
    st.markdown("[← Volver al mapa](/)")


# =============================================================================
# HELPER INTERNO — formulario de contacto reutilizable
# =============================================================================

def _form_contacto(finca: dict) -> None:
    """Formulario de contacto inline. Reutilizado en ficha y contacto directo."""
    finca_id = finca.get("id", "")

    with st.form(f"mls_contacto_pub_{finca_id}", clear_on_submit=True):
        nombre  = st.text_input("Nombre *", placeholder="Tu nombre y apellidos")
        email   = st.text_input("Email *", placeholder="tu@email.com")
        mensaje = st.text_area(
            "Mensaje",
            placeholder="¿En qué podemos ayudarte?",
            max_chars=300,
        )
        enviado = st.form_submit_button("Enviar consulta →", type="primary")

    if enviado:
        if not nombre.strip() or not email.strip() or "@" not in email:
            st.error("Introduce nombre y email válidos.")
            return
        ok = mls_db.registrar_contacto_cliente(
            finca_id=finca_id,
            nombre=nombre.strip(),
            email=email.strip().lower(),
            mensaje=mensaje.strip(),
        )
        if ok:
            st.success(
                "✅ Consulta enviada. ArchiRapid se pondrá en contacto contigo en breve."
            )
        else:
            st.error("Error al enviar la consulta. Inténtalo de nuevo.")
