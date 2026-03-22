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
    col1, col2 = st.columns(2)
    if precio:
        col1.metric("Precio", f"€{precio:,.0f}")
    if superficie:
        col2.metric("Superficie", f"{superficie:,.0f} m²")
    if catastro_ref and catastro_ref != "—":
        st.markdown(f"**Referencia catastral:** `{catastro_ref}`")

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

    # ── Badge validación catastral ─────────────────────────────────────────────
    if finca.get("catastro_validada"):
        geo_txt = ""
        if lat and lon:
            geo_txt = f" · lat {float(lat):.5f}, lon {float(lon):.5f}"
        st.success(f"✅ Referencia catastral validada por Sede Electrónica del Catastro{geo_txt}")

    # ── Calculadora de financiación ───────────────────────────────────────────
    st.markdown("---")
    try:
        from modules.marketplace.hipoteca import render_calculadora
        coste_obra = float(superficie or 0) * 0.33 * 1300
        with st.expander(
            "🏦 Calculadora de Financiación — ¿Cuánto pagaría al mes?",
            expanded=False,
        ):
            render_calculadora(
                precio_terreno=precio,
                coste_construccion=coste_obra,
                key_prefix=f"mls_{finca_id}",
            )
    except Exception:
        pass

    # ── Proyectos compatibles ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🏠 Proyectos Compatibles para esta Parcela")
    try:
        from modules.marketplace.compatibilidad import get_proyectos_compatibles
        proyectos = get_proyectos_compatibles(
            client_parcel_size=float(superficie or 0),
        )
        if proyectos:
            p_cols = st.columns(min(len(proyectos), 3))
            for i, p in enumerate(proyectos[:3]):
                with p_cols[i % 3]:
                    m2_p = p.get("m2_construidos") or p.get("area_m2") or 0
                    price_p = float(p.get("price") or 0)
                    st.markdown(f"**{p.get('title', 'Proyecto')}**")
                    st.caption(f"{m2_p:,.0f} m² construidos · €{price_p:,.0f}")
                    if st.button(
                        "Ver proyecto →",
                        key=f"mls_proj_{finca_id}_{p['id']}",
                        use_container_width=True,
                    ):
                        st.query_params["selected_project_v2"] = str(p["id"])
                        st.rerun()
        else:
            st.info("Aún no hay proyectos de vivienda en el catálogo. Próximamente.")
    except Exception:
        pass

    # ── Reservar / Comprar (mismo flujo que pin azul) ─────────────────────────
    st.markdown("---")
    st.subheader("📝 ¿Interesado en esta finca?")

    if reservada:
        st.warning("🔒 Esta finca está actualmente reservada.")
        st.info("Déjanos tu contacto por si quedara disponible.")
        _form_contacto(finca)
    else:
        show_form = st.session_state.get(f"_mls_form_{finca_id}", False)

        if st.button("📝 Reservar o Comprar Finca", type="primary", key="fp_btn_reservar"):
            st.session_state[f"_mls_form_{finca_id}"] = not show_form
            st.rerun()

        if st.session_state.get(f"_mls_form_{finca_id}", False):
            st.markdown("### 📋 Formulario de Contacto")
            col1, col2 = st.columns(2)
            with col1:
                buyer_name     = st.text_input("Nombre completo *", key=f"mls_name_{finca_id}")
                buyer_email    = st.text_input("Email *",            key=f"mls_email_{finca_id}")
                buyer_password = st.text_input(
                    "Contraseña de acceso *", type="password",
                    key=f"mls_pwd_{finca_id}",
                    help="Será tu contraseña para el panel de cliente",
                )
            with col2:
                buyer_phone = st.text_input("Teléfono", key=f"mls_phone_{finca_id}")
                reservation_type = st.selectbox(
                    "Tipo de interés",
                    ["Reserva (10%)", "Compra completa (100%)"],
                    key=f"mls_type_{finca_id}",
                )

            if reservation_type == "Reserva (10%)":
                amount = precio * 0.1
                amount_text = f"€{amount:,.0f} (10% del precio total)"
            else:
                amount = precio
                amount_text = f"€{amount:,.0f} (precio completo)"
            st.markdown(f"**Importe a pagar:** {amount_text}")

            if st.button("✅ Confirmar y Proceder", type="primary", key=f"mls_confirm_{finca_id}"):
                if not buyer_name or not buyer_email or not buyer_password:
                    st.error("Completa nombre, email y contraseña (*obligatorios).")
                elif len(buyer_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    try:
                        from modules.marketplace.utils import create_or_update_client_user
                        create_or_update_client_user(buyer_email, buyer_name, buyer_password)

                        # Sesión y redirección — idéntico al flujo azul
                        st.session_state["logged_in"]       = True
                        st.session_state["user_email"]      = buyer_email
                        st.session_state["role"]            = "client"
                        st.session_state["user_name"]       = buyer_name
                        st.session_state["selected_page"]   = "👤 Panel de Cliente"
                        st.session_state["mls_reserva_finca_id"] = finca_id
                        st.query_params.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar: {e}")

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
