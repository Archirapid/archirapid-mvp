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
  - La capa profesional (_show_capa_profesional_inmo) solo se activa cuando
    st.session_state["mls_inmo"] tiene activa=1 Y firma_hash válido
  - REF MLS y comisiones solo visibles para inmos colaboradoras con acuerdo firmado
"""
import json
import os

import streamlit as st

from modules.mls import mls_db


# =============================================================================
# HELPERS
# =============================================================================

def _get_mls_images(finca: dict) -> list:
    """Resuelve rutas de imágenes de una finca MLS (con o sin prefijo uploads/)."""
    raw = finca.get("image_paths") or "[]"
    try:
        paths = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(paths, list):
            paths = []
    except Exception:
        paths = []
    result = []
    for p in paths:
        norm = p.replace("\\", "/")
        if os.path.exists(norm):
            result.append(norm)
        elif os.path.exists(f"uploads/{norm}"):
            result.append(f"uploads/{norm}")
    if not result and os.path.exists("assets/fincas/image1.jpg"):
        result = ["assets/fincas/image1.jpg"]
    return result


def _show_capa_profesional_inmo(finca: dict, finca_id: str) -> None:
    """Sección profesional — visible SOLO para inmos con plan activo y firma válida.

    Muestra: REF MLS, comisión, importe estimado, notas privadas.
    La ACCIÓN (reserva) se centraliza en el Portal MLS para evitar duplicidad de flujos.
    """
    inmo = st.session_state.get("mls_inmo")
    if not inmo:
        return
    if not inmo.get("activa"):
        return
    if not inmo.get("firma_hash"):
        return

    ref_codigo     = finca.get("ref_codigo") or "Pendiente asignación"
    comision_colab = finca.get("comision_colaboradora_pct")
    notas          = finca.get("notas_privadas") or ""
    precio         = float(finca.get("precio") or 0)
    estado         = finca.get("estado", "")
    reservada      = estado in ("reservada", "reserva_pendiente_confirmacion")

    st.markdown("---")
    st.markdown(
        """<div style="background:linear-gradient(135deg,#0a1f0a,#0d2b0d);
                      border:1.5px solid #22c55e;border-radius:10px;
                      padding:14px 18px;margin-bottom:12px;">
            <div style="color:#22c55e;font-weight:800;font-size:13px;letter-spacing:1px;">
                🏢 INFORMACIÓN PROFESIONAL MLS — COLABORADORA
            </div>
            <div style="color:#94a3b8;font-size:11px;margin-top:3px;">
                Visible solo para inmobiliarias colaboradoras con acuerdo MLS firmado
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        st.metric("🔑 REF MLS", ref_codigo)
    with col_p2:
        colab_str = f"{comision_colab:.1f}%" if comision_colab is not None else "—"
        st.metric("💶 Tu comisión", colab_str)
    with col_p3:
        if comision_colab and precio:
            importe_colab = precio * comision_colab / 100
            st.metric("💰 Importe estimado", f"€{importe_colab:,.0f}")

    if notas:
        with st.expander("📝 Notas del listante (privadas)", expanded=False):
            st.markdown(notas)

    st.markdown("---")

    if reservada:
        st.warning("🔒 Esta finca tiene una reserva activa en este momento.")
    else:
        st.info(
            "**Para reservar esta finca para tu cliente**, utiliza tu **Portal MLS** "
            "donde gestionas todo el flujo: reserva, visita y comisiones."
        )

    # Botón único: lleva directamente a la ficha profesional dentro del portal
    if st.button(
        "🏢 Gestionar en mi Portal MLS →",
        key=f"mls_ir_portal_{finca_id}",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["mls_ficha_id"] = finca_id
        st.session_state["mls_vista"]    = "ficha"
        st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
        st.query_params.clear()
        st.rerun()


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

    estado       = finca.get("estado", "publicada")
    reservada    = estado in ("reservada", "reserva_pendiente_confirmacion")
    titulo       = finca.get("titulo") or "Finca MLS"
    precio       = float(finca.get("precio") or 0)
    sup          = float(finca.get("superficie_m2") or 0)
    catastro_ref = finca.get("catastro_ref") or ""
    descripcion  = finca.get("descripcion_publica") or ""
    lat          = finca.get("catastro_lat")
    lon          = finca.get("catastro_lon")
    tipo_suelo   = finca.get("tipo_suelo") or "Urbana"
    servicios_raw = finca.get("servicios")

    # ── Cabecera ──────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='color:#F5A623;font-weight:700;font-size:13px;"
        "margin-bottom:4px;'>🟠 ArchiRapid MLS</div>",
        unsafe_allow_html=True,
    )
    st.title(titulo)
    if reservada:
        st.warning("🔒 Esta finca tiene una reserva activa en este momento.")
    if st.button("← Volver al mapa", key="mls_back_btn"):
        st.query_params.clear()
        st.rerun()

    st.markdown("---")

    # ── Sección 1: Ficha Técnica ──────────────────────────────────────────────
    st.header("📋 Ficha Técnica del Terreno")

    # Galería de imágenes — igual que pin azul (1 grande + miniaturas)
    img_files = _get_mls_images(finca)
    if img_files:
        st.subheader("📸 Galería de Imágenes")
        col_main, col_thumb = st.columns([2, 1])
        with col_main:
            st.image(img_files[0], use_container_width=True, caption=titulo)
        with col_thumb:
            if len(img_files) > 1:
                st.caption("Más imágenes:")
                for img in img_files[1:4]:
                    st.image(img, width=150)

    st.markdown("---")

    # Datos del terreno + mapa — 2 columnas igual que pin azul
    col_datos, col_mapa = st.columns(2)

    with col_datos:
        st.subheader("📊 Datos del Terreno")
        try:
            from modules.marketplace.utils import calculate_edificability
            max_edificable = calculate_edificability(sup, 0.33)
        except Exception:
            max_edificable = sup * 0.33

        st.metric("💰 Precio", f"€{precio:,.0f}")
        st.metric("📏 Superficie Total", f"{sup:,.0f} m²")
        st.metric("🏗️ Máximo Construible (33%)", f"{max_edificable:.0f} m²")
        st.markdown(f"**🏷️ Tipo:** {tipo_suelo}")
        if catastro_ref:
            st.markdown(f"**📋 Referencia Catastral:** `{catastro_ref}`")
        if servicios_raw:
            try:
                servicios = json.loads(servicios_raw) if isinstance(servicios_raw, str) else servicios_raw
                if servicios:
                    st.markdown(f"**🔌 Servicios:** {', '.join(servicios)}")
            except Exception:
                pass

    with col_mapa:
        st.subheader("📍 Ubicación en Mapa")
        if lat and lon:
            try:
                import folium
                import streamlit.components.v1 as _stc
                _m = folium.Map(
                    location=[float(lat), float(lon)],
                    zoom_start=15,
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri",
                )
                folium.Marker(
                    [float(lat), float(lon)],
                    popup=titulo,
                    icon=folium.Icon(color="orange", icon="home", prefix="fa", icon_color="white"),
                    tooltip=titulo,
                ).add_to(_m)
                _stc.html(_m._repr_html_(), height=300)
                st.caption("Ubicación aproximada — dirección exacta disponible tras reserva")
            except Exception:
                st.info("Mapa no disponible.")
        else:
            st.info("Coordenadas pendientes de validación catastral.")

    st.markdown("---")

    # Solar virtual — igual que pin azul
    if sup > 0:
        try:
            from modules.marketplace.plot_detail import generar_svg_solar_validado
            es_urbano = tipo_suelo.lower() != "industrial"
            svg = generar_svg_solar_validado(sup, max_edificable, es_urbano=es_urbano)
            col_sv1, col_sv2 = st.columns([1, 2])
            with col_sv1:
                st.markdown("**🗺️ Esquema del Solar**")
                import streamlit.components.v1 as _stc_svg
                _stc_svg.html(f"<html><body style='margin:0;padding:0;background:transparent'>{svg}</body></html>", height=270)
            with col_sv2:
                st.markdown("**📐 Edificabilidad**")
                st.markdown(
                    f"- **Parcela total:** {sup:,.0f} m²\n"
                    f"- **Máx. construible (33%):** {max_edificable:.0f} m²\n"
                    f"- **Tipo de suelo:** {tipo_suelo}"
                )
        except Exception:
            pass

    # Descripción
    if descripcion:
        st.markdown("---")
        st.markdown("### Descripción")
        st.markdown(descripcion)

    st.markdown("---")

    # ── Verificación catastral — versión MLS (sin PDF, usa datos de API) ──────
    st.subheader("🔍 Verificación Técnica")
    if finca.get("catastro_validada"):
        st.success("✅ Datos verificados con Catastro — La referencia catastral está validada oficialmente")
        with st.expander("📊 Ver datos de validación", expanded=False):
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.write(f"**Superficie:** {sup:,.0f} m²")
                st.write(f"**Referencia Catastral:** {catastro_ref or '—'}")
                st.write(f"**Tipo suelo:** {tipo_suelo}")
            with col_v2:
                if lat and lon:
                    st.write(f"**Latitud:** {float(lat):.6f}")
                    st.write(f"**Longitud:** {float(lon):.6f}")
    else:
        st.info("📋 Validación catastral en proceso. Contacta con ArchiRapid para más información.")

    st.markdown("---")

    # ── Alertas de fincas similares — igual que pin azul ─────────────────────
    import sqlite3 as _sq_al
    import datetime as _dt_al
    with st.expander("🔔 Avisarme cuando haya fincas similares", expanded=False):
        st.markdown("""
        <div style="background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.3);
                    border-radius:10px;padding:12px 16px;margin-bottom:10px;">
            <div style="font-weight:700;color:#F8FAFC;font-size:14px;">
                🔔 Alertas de nuevas fincas
            </div>
            <div style="color:#94A3B8;font-size:12px;margin-top:2px;">
                Te avisamos por email cuando publiquemos fincas similares
            </div>
        </div>
        """, unsafe_allow_html=True)
        _al_c1, _al_c2 = st.columns(2)
        with _al_c1:
            _al_name  = st.text_input("Tu nombre",  placeholder="Nombre",       key=f"mls_aln_{finca_id}")
            _al_email = st.text_input("Email *",     placeholder="tu@email.com", key=f"mls_ale_{finca_id}")
        with _al_c2:
            _al_price = st.number_input(
                "Presupuesto máximo (€)", min_value=0.0, max_value=5_000_000.0,
                value=precio * 2, step=10_000.0, format="%.0f",
                key=f"mls_alp_{finca_id}", help="0 = sin límite",
            )
            _al_tipo = st.text_input("Tipo de suelo de interés", value=tipo_suelo, key=f"mls_alv_{finca_id}")
        if st.button("🔔 Activar alerta", key=f"mls_albtn_{finca_id}", type="primary", use_container_width=True):
            if not _al_email or "@" not in _al_email:
                st.error("Introduce un email válido.")
            else:
                try:
                    _c_al = _sq_al.connect("database.db", timeout=10)
                    _c_al.execute("PRAGMA journal_mode=WAL")
                    _c_al.execute("""CREATE TABLE IF NOT EXISTS plot_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT, name TEXT, province TEXT,
                        max_price REAL DEFAULT 0, created_at TEXT, active INTEGER DEFAULT 1)""")
                    _exists = _c_al.execute(
                        "SELECT id FROM plot_alerts WHERE email=?",
                        (_al_email.lower().strip(),)
                    ).fetchone()
                    _now_al = _dt_al.datetime.utcnow().isoformat(timespec="seconds") + "Z"
                    if _exists:
                        _c_al.execute(
                            "UPDATE plot_alerts SET name=?, max_price=?, active=1, created_at=? WHERE id=?",
                            (_al_name, _al_price, _now_al, _exists[0]),
                        )
                    else:
                        _c_al.execute(
                            "INSERT INTO plot_alerts (email,name,province,max_price,created_at) VALUES (?,?,?,?,?)",
                            (_al_email.lower().strip(), _al_name, _al_tipo, _al_price, _now_al),
                        )
                    _c_al.commit()
                    _c_al.close()
                    st.success(f"✅ Alerta activada para fincas {_al_tipo or 'similares'}.")
                except Exception:
                    st.info("✅ Petición recibida. Te contactaremos en hola@archirapid.com")

    # ── Calculadora de financiación — igual que pin azul ─────────────────────
    st.markdown("---")
    try:
        from modules.marketplace.hipoteca import render_calculadora
        with st.expander("🏦 Calculadora de Financiación — ¿Cuánto pagaría al mes?", expanded=False):
            render_calculadora(
                precio_terreno=precio,
                coste_construccion=sup * 0.33 * 1300,
                key_prefix=f"mls_{finca_id}",
            )
    except Exception:
        pass

    # ── Proyectos compatibles — igual que pin azul ────────────────────────────
    st.markdown("---")
    st.subheader("🏠 Proyectos Compatibles para esta Parcela")
    try:
        from modules.marketplace.compatibilidad import get_proyectos_compatibles
        proyectos = get_proyectos_compatibles(client_parcel_size=sup)
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

    # ── Capa profesional: visible solo para inmos colaboradoras ──────────────
    _show_capa_profesional_inmo(finca, finca_id)

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
