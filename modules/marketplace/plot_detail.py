"""
Página de detalles completa de una finca
Muestra toda la información necesaria para que el cliente decida comprar
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import os
import json
import base64
import re
from modules.marketplace.utils import calculate_edificability, reserve_plot, create_or_update_client_user
from modules.marketplace.catastro_api import fetch_by_ref_catastral
from modules.marketplace.marketplace import get_plot_image_path
from modules.marketplace.compatibilidad import get_proyectos_compatibles
from src import db

def generar_svg_solar_validado(superficie_parcela, max_construible, es_urbano=True):
    # Dimensiones del lienzo SVG
    width, height = 300, 250
    margin = 30

    # Color según tipo de suelo
    color_solar = "#e8f4f8" if es_urbano else "#fdf2e9" # Azul suave vs Naranja rústico
    color_borde = "#2980b9" if es_urbano else "#d35400"

    # 1. Dibujamos el Solar (La Parcela)
    solar_w = width - (margin * 2)
    solar_h = height - (margin * 2)

    # 2. Calculamos el área de construcción proporcional
    # Si la edificabilidad es el 33%, el cuadro interno ocupará esa proporción de área
    ratio = max_construible / superficie_parcela if superficie_parcela > 0 else 0
    factor_escala = ratio ** 0.5  # Raíz cuadrada para escala lineal

    const_w = solar_w * factor_escala
    const_h = solar_h * factor_escala

    # Centramos la construcción dentro del solar
    const_x = margin + (solar_w - const_w) / 2
    const_y = margin + (solar_h - const_h) / 2

    svg = f"""
    <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="{margin}" y="{margin}" width="{solar_w}" height="{solar_h}"
              fill="{color_solar}" stroke="{color_borde}" stroke-width="2" />

        <rect x="{const_x}" y="{const_y}" width="{const_w}" height="{const_h}"
              fill="#2ecc71" fill-opacity="0.6" stroke="#27ae60" stroke-width="2" stroke-dasharray="4" />

        <text x="{width/2}" y="{margin-10}" text-anchor="middle" font-size="12" font-family="sans-serif" fill="#34495e">
            Parcela Real: {superficie_parcela} m²
        </text>
        <text x="{width/2}" y="{height-margin+20}" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#27ae60">
            Máx. Edificable: {max_construible} m² ({int(ratio*100)}%)
        </text>
    </svg>
    """
    return svg

def get_all_plot_images(plot):
    """Obtener todas las imágenes de la finca"""
    images = []
    if plot.get('photo_paths'):
        try:
            paths = json.loads(plot['photo_paths']) if isinstance(plot.get('photo_paths'), str) else plot.get('photo_paths')
            if paths and isinstance(paths, list):
                for path in paths:
                    if isinstance(path, str) and path.startswith("http"):
                        images.append(path)
                    else:
                        img_path = f"uploads/{path}"
                        if os.path.exists(img_path):
                            images.append(img_path)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback a imagen única
    if not images:
        single_img = get_plot_image_path(plot)
        if single_img and os.path.exists(single_img):
            images.append(single_img)

    return images if images else ['assets/fincas/image1.jpg']

def get_project_images(proyecto):
    """Obtener todas las imágenes válidas de un proyecto"""
    images = []

    # Procesar foto principal
    foto_principal = proyecto.get('foto_principal')
    if foto_principal and os.path.exists(foto_principal):
        images.append(foto_principal)

    # Procesar galería de fotos
    galeria = proyecto.get('galeria_fotos', [])

    # Validar que galeria sea una lista y no un número
    if galeria and isinstance(galeria, list) and not any(isinstance(item, (int, float)) for item in galeria):
        for img_path in galeria:
            if img_path and isinstance(img_path, str) and img_path.strip() and img_path not in images and os.path.exists(img_path):
                images.append(img_path)

def show_plot_detail_page(plot_id: str):
    """Muestra la página completa de detalles de una finca"""

    # Limpiar sidebar para vista dedicada
    st.sidebar.empty()

    # Obtener datos de la finca
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plots WHERE id = ?", (plot_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        st.error("❌ Finca no encontrada")
        if st.button("← Volver al mapa"):
            if 'selected_plot' in st.session_state:
                del st.session_state['selected_plot']
            st.rerun()
        return

    # Convertir row a dict
    plot = dict(row)

    import json

    # Normalizar solar_virtual: si viene como string JSON, convertirlo a dict
    solar_virtual = plot.get("solar_virtual")
    if isinstance(solar_virtual, str):
        try:
            solar_virtual = json.loads(solar_virtual)
        except Exception:
            solar_virtual = {}

    # Guardar de nuevo en plot para que el resto del código lo use correctamente
    plot["solar_virtual"] = solar_virtual

    # Título principal
    st.title(f"🏡 {plot.get('title', 'Finca sin título')}")

    # Botón volver
    if st.button("← Volver al mapa", key="back_to_map"):
        if 'selected_plot' in st.session_state:
            del st.session_state['selected_plot']
        st.rerun()

    st.markdown("---")

    # ========================================================================
    # SECCIÓN 1: FICHA TÉCNICA DEL TERRENO (Visible para todos)
    # ========================================================================

    st.header("📋 Ficha Técnica del Terreno")

    # Galería de imágenes
    st.subheader("📸 Galería de Imágenes")
    images = get_all_plot_images(plot)

    if len(images) > 0:
        # Mostrar primera imagen grande
        col_img_main, col_img_thumb = st.columns([2, 1])
        with col_img_main:
            st.image(images[0], width=600, caption=plot.get('title', ''))

        with col_img_thumb:
            if len(images) > 1:
                st.caption("Más imágenes:")
                for i, img_path in enumerate(images[1:4]):  # Máximo 3 thumbnails
                    st.image(img_path, width=150)

    st.markdown("---")

    # Información principal en columnas
    col_info1, col_info2 = st.columns(2)

    with col_info1:
        st.subheader("📊 Datos del Terreno")

        superficie = plot.get('surface_m2') or plot.get('m2') or 0
        precio = plot.get('price') or 0
        provincia = plot.get('province', 'N/A')
        localidad = plot.get('locality', plot.get('address', 'N/A'))

        st.metric("💰 Precio", f"€{precio:,.0f}")
        st.metric("📏 Superficie Total", f"{superficie} m²")

        # Cálculo de edificabilidad (33%)
        max_edificable = calculate_edificability(superficie, 0.33)
        st.metric("🏗️ Máximo Construible (33%)", f"{max_edificable:.0f} m²")

        st.markdown(f"**📍 Ubicación:** {localidad}, {provincia}")
        st.markdown(f"**🏷️ Tipo:** {plot.get('type', 'Urbano')}")

        if plot.get('catastral_ref'):
            st.markdown(f"**📋 Referencia Catastral:** `{plot['catastral_ref']}`")

    with col_info2:
        st.subheader("📍 Ubicación en Mapa")
        try:
            import folium
            import streamlit.components.v1 as components
            lat = float(plot.get('lat', 40.4168))
            lon = float(plot.get('lon', -3.7038))
            m = folium.Map(location=[lat, lon], zoom_start=15, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            
            # Verificar si la finca está vendida/reservada
            conn_check = db.get_conn()
            cursor_check = conn_check.cursor()
            cursor_check.execute("SELECT 1 FROM reservations WHERE plot_id = ?", (plot_id,))
            is_sold = cursor_check.fetchone() is not None
            conn_check.close()
            
            # Definir icono según disponibilidad
            if is_sold:
                # FINCA VENDIDA/RESERVADA: Color ROJO con icono de prohibido
                icon = folium.Icon(color='red', icon='ban', prefix='fa', icon_color='white')
            else:
                # FINCA DISPONIBLE: Color AZUL con icono de casa
                icon = folium.Icon(color='blue', icon='home', prefix='fa', icon_color='white')
            
            folium.Marker(
                [lat, lon],
                popup=plot.get('title', 'Finca'),
                icon=icon
            ).add_to(m)
            components.html(m._repr_html_(), height=300)
        except Exception as e:
            st.error(f"Error mostrando mapa: {e}")

    st.markdown("---")

    # ========================================================================
    # VERIFICACIÓN CON IA (antes de comprar)
    # ========================================================================

    st.subheader("🔍 Verificación Técnica con IA")

    # Estado de verificación IA
    ia_verified = st.session_state.get(f'ia_verified_{plot_id}', False)

    if ia_verified:
        st.success("✅ Datos verificados con IA - La información catastral coincide con los datos publicados")
        # Mostrar detalles guardados si existen
        _saved = st.session_state.get(f'ia_verified_data_{plot_id}')
        if _saved:
            with st.expander("📊 Ver datos verificados", expanded=False):
                import json as _j
                _d = _saved if isinstance(_saved, dict) else _j.loads(_saved)
                st.write(f"**Superficie:** {_d.get('superficie_m2', 0)} m²")
                st.write(f"**Referencia Catastral:** {_d.get('referencia_catastral', '')}")
                st.write(f"**Municipio:** {_d.get('municipio', '')}")
    else:
        st.info("📋 Recomendado: Verifica que los datos de la finca coincidan con la nota catastral antes de comprar")

        if st.button("🔍 Verificar con Nota Catastral", key=f"verify_ia_{plot_id}", type="secondary"):
            with st.spinner("Analizando datos catastrales completos con IA..."):
                try:
                    from modules.marketplace.ai_engine import extraer_datos_catastral_completo
                    import json as _json
                    from pathlib import Path
                    from modules.marketplace.utils import db_conn as _db_conn

                    datos_extraidos = None
                    metodo_usado = None

                    # 1. Comprobar caché en DB
                    _conn_cache = _db_conn()
                    _cached = _conn_cache.execute(
                        "SELECT ai_verification_cache FROM plots WHERE id=?", (plot_id,)
                    ).fetchone()
                    _conn_cache.close()
                    _cached_val = None
                    if _cached:
                        try:
                            _cached_val = _cached['ai_verification_cache']
                        except (KeyError, TypeError):
                            _cached_val = _cached[0] if _cached else None
                    if _cached_val:
                        try:
                            datos_extraidos = _json.loads(_cached_val)
                            metodo_usado = "cache"
                        except Exception:
                            datos_extraidos = None

                    # 2. Si no hay caché, buscar PDF y llamar a la API
                    if not datos_extraidos:
                        pdf_paths = []
                        for field in ('registry_note_path', 'plano_catastral_path'):
                            finca_path = plot.get(field)
                            if finca_path:
                                pdf_paths.append(Path(finca_path))
                        pdf_paths += [
                            Path("archirapid_extract/catastro_output/nota_catastral.pdf"),
                            Path("uploads/nota_catastral.pdf"),
                            Path("catastro_output/nota_catastral.pdf"),
                        ]
                        pdf_encontrado = next((p for p in pdf_paths if p.exists()), None)

                        if not pdf_encontrado:
                            st.warning("⚠️ No se encontró archivo PDF de nota catastral")
                            st.info("Sube un archivo 'nota_catastral.pdf' a la carpeta uploads/ o archirapid_extract/catastro_output/")
                        else:
                            datos_extraidos = extraer_datos_catastral_completo(str(pdf_encontrado))
                            metodo_usado = "ocr"

                            # Fallback a Gemini Vision si PDF es imagen escaneada
                            if datos_extraidos and "error" in datos_extraidos and "imagen escaneada" in datos_extraidos["error"]:
                                st.info("📷 PDF escaneado detectado — usando Gemini Vision para extraer datos...")
                                from modules.marketplace.ai_engine import extraer_datos_nota_catastral
                                gemini_result = extraer_datos_nota_catastral(str(pdf_encontrado))
                                if gemini_result and "error" not in gemini_result:
                                    datos_extraidos = {
                                        "superficie_m2": gemini_result.get("superficie_grafica_m2", 0),
                                        "referencia_catastral": gemini_result.get("referencia_catastral", ""),
                                        "municipio": gemini_result.get("municipio", ""),
                                    }
                                    metodo_usado = "gemini"
                                    # Guardar en caché para evitar llamadas futuras a la API
                                    try:
                                        _cc = _db_conn()
                                        _cc.execute(
                                            "UPDATE plots SET ai_verification_cache=? WHERE id=?",
                                            (_json.dumps(datos_extraidos), plot_id)
                                        )
                                        _cc.commit()
                                        _cc.close()
                                    except Exception:
                                        pass
                                else:
                                    datos_extraidos = gemini_result

                    # 3. Mostrar resultados (fuera del bloque cache/pdf)
                    if datos_extraidos:
                        if metodo_usado == "cache":
                            st.caption("⚡ Resultado en caché — sin llamada a API")
                        if "error" in datos_extraidos:
                            st.error(f"❌ Error en extracción completa: {datos_extraidos['error']}")
                        else:
                            superficie_pdf = datos_extraidos.get("superficie_m2", 0)
                            ref_catastral_pdf = datos_extraidos.get("referencia_catastral", "")
                            superficie_finca = plot.get('surface_m2') or plot.get('m2') or 0
                            ref_catastral_finca = plot.get('catastral_ref', '')
                            superficie_ok = superficie_pdf > 0 and abs(superficie_pdf - superficie_finca) < 10
                            ref_ok = ref_catastral_pdf.strip() == ref_catastral_finca.strip()

                            with st.expander("📊 Resultados de Verificación IA Completa", expanded=True):
                                st.markdown("### 📋 Datos Extraídos de la Nota Catastral")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Superficie:** {superficie_pdf} m²")
                                    st.write(f"**Referencia Catastral:** {ref_catastral_pdf}")
                                    st.write(f"**Municipio:** {datos_extraidos.get('municipio', 'No detectado')}")
                                with col2:
                                    st.write(f"**Forma Geométrica:** {datos_extraidos.get('forma_geometrica', 'No detectada')}")
                                    st.write(f"**Vértices:** {datos_extraidos.get('vertices', 0)}")
                                    dims = datos_extraidos.get('dimensiones', {})
                                    st.write(f"**Dimensiones:** {dims.get('ancho_m', 0):.1f}m × {dims.get('largo_m', 0):.1f}m")

                                st.markdown("### 🏗️ Información de Edificabilidad")
                                ed = datos_extraidos.get('edificabilidad', {})
                                st.write(f"**Máx. Edificable:** {ed.get('max_edificable_m2', 0):.1f} m²")
                                st.write(f"**Porcentaje:** {ed.get('porcentaje_edificable', 0):.1f}%")

                                st.markdown("### 🧭 Orientación y Plano")
                                st.write(f"**Orientación Norte:** {datos_extraidos.get('orientacion_norte', 'No detectada')}")

                                archivos = datos_extraidos.get('archivos_generados', {})
                                plano_visualizado = archivos.get('plano_vectorizado')
                                plano_limpio = archivos.get('plano_limpio')
                                if plano_visualizado and Path(plano_visualizado).exists():
                                    st.markdown("### 📐 Plano Catastral Vectorizado")
                                    st.image(str(plano_visualizado), caption="Plano con contornos detectados", use_container_width=True)
                                    if plano_limpio and Path(plano_limpio).exists():
                                        with open(plano_limpio, "rb") as file:
                                            st.download_button(
                                                label="📄 Descargar Plano Técnico (PNG)",
                                                data=file,
                                                file_name="plano_catastral_limpio.png",
                                                mime="image/png",
                                            )

                                st.markdown("### 🔍 Comparación con Datos Publicados")
                                st.write(f"**Superficie Finca:** {superficie_finca} m²")
                                st.write(f"**Referencia Catastral Finca:** {ref_catastral_finca}")
                                if superficie_ok and ref_ok:
                                    st.success("✅ VERIFICACIÓN EXITOSA: Los datos coinciden perfectamente")
                                    st.session_state[f'ia_verified_{plot_id}'] = True
                                    st.session_state[f'ia_verified_data_{plot_id}'] = datos_extraidos
                                    st.balloons()
                                elif superficie_ok:
                                    st.warning("⚠️ Superficie correcta, pero referencia catastral diferente")
                                    st.info("Los datos de superficie coinciden, pero verifica la referencia catastral")
                                else:
                                    st.error("❌ DISCREPANCIA: Los datos de superficie no coinciden")
                                    st.warning("Revisa la información antes de proceder con la compra")

                except Exception as e:
                    st.error(f"Error en verificación IA completa: {str(e)}")

    st.markdown("---")

    # ── Sección de reserva de finca ──────────────────────────────────────────
    st.subheader("🏡 Reservar esta Finca")

    # Calcular importe reserva 1%
    _precio_reserva = precio * 0.01
    _precio_str = f"{precio:,.0f}".replace(",", ".")
    _reserva_str = f"{_precio_reserva:,.0f}".replace(",", ".")

    # Si ya hay URL de Stripe pendiente, mostrar botón de pago
    _stripe_url_key = f"stripe_reserva_url_{plot_id}"
    if st.session_state.get(_stripe_url_key):
        _s_url = st.session_state[_stripe_url_key]
        st.success("✅ Formulario recibido. Completa el pago para confirmar tu reserva.")
        st.markdown(
            f'<a href="{_s_url}" target="_blank" style="display:inline-block;'
            'background:#1E3A5F;color:#fff;padding:14px 28px;border-radius:8px;'
            'font-weight:700;font-size:16px;text-decoration:none;margin-top:8px;">'
            f'💳 Pagar €{_reserva_str} con Tarjeta — Reserva 7 días</a>',
            unsafe_allow_html=True,
        )
        if st.button("✏️ Cambiar datos del formulario", key=f"reset_reserva_{plot_id}"):
            del st.session_state[_stripe_url_key]
            st.rerun()
    else:
        st.markdown(
            f"Precio de la finca: **€{_precio_str}** · "
            f"Importe de reserva (1%): **€{_reserva_str}**"
        )
        st.info(
            "⚠️ **Reserva temporal de 7 días** — Al completar el pago, la finca quedará reservada "
            "exclusivamente a tu nombre durante 7 días naturales (art. 1454 CC). "
            "Pasado ese plazo sin escritura, la reserva caduca y el importe queda a favor del vendedor "
            "como señal de arras.",
        )

        with st.form(key=f"form_reservar_{plot_id}"):
            st.markdown("### 📋 Formulario de Registro")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                buyer_name  = st.text_input("Nombre completo *")
                buyer_email = st.text_input("Email *")
                buyer_pass  = st.text_input("Contraseña de acceso *", type="password",
                                            help="Con esta contraseña accederás a tu panel de cliente")
            with col_f2:
                buyer_phone = st.text_input("Teléfono")
                buyer_dni   = st.text_input("DNI / NIF *")
                buyer_dom   = st.text_input("Domicilio")
                buyer_prov  = st.text_input("Provincia")
            _submitted = st.form_submit_button("🏡 Reservar esta Finca", type="primary", use_container_width=True)

        if _submitted:
            if not buyer_name or not buyer_email or not buyer_pass or not buyer_dni:
                st.error("Nombre, email, contraseña y DNI/NIF son obligatorios (*)")
            elif len(buyer_pass) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres")
            elif "@" not in buyer_email:
                st.error("Introduce un email válido")
            else:
                try:
                    import uuid as _uuid_mod
                    from datetime import datetime as _dt
                    from src.db import get_conn as _get_db

                    # 1. Crear/actualizar usuario cliente
                    create_or_update_client_user(buyer_email, buyer_name, buyer_pass)

                    # 2. Insertar reserva pendiente (se confirmará tras el pago Stripe)
                    _pending_id = _uuid_mod.uuid4().hex
                    _conn_r = _get_db()
                    try:
                        _conn_r.execute(
                            "INSERT INTO reservations "
                            "(id,plot_id,buyer_name,buyer_email,amount,kind,created_at,"
                            "buyer_dni,buyer_domicilio,buyer_province) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (_pending_id, str(plot_id), buyer_name, buyer_email,
                             _precio_reserva, "pending", _dt.utcnow().isoformat(),
                             buyer_dni, buyer_dom, buyer_prov)
                        )
                        _conn_r.commit()
                    except Exception:
                        # PostgreSQL: rollback obligatorio antes de cualquier nueva query
                        try:
                            _conn_r.rollback()
                        except Exception:
                            pass
                        # Fallback sin columnas nuevas (pre-migración)
                        _conn_r.execute(
                            "INSERT INTO reservations (id,plot_id,buyer_name,buyer_email,amount,kind,created_at) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (_pending_id, str(plot_id), buyer_name, buyer_email,
                             _precio_reserva, "pending", _dt.utcnow().isoformat())
                        )
                        _conn_r.commit()
                    finally:
                        _conn_r.close()

                    # 3. Crear sesión Stripe y mostrar botón de pago
                    from modules.stripe_utils import create_reservation_checkout as _crc
                    _plot_ref = plot.get("catastral_ref") or plot.get("ref_catastral") or str(plot_id)
                    _s_url, _s_id = _crc(
                        plot_id=str(plot_id),
                        pending_id=_pending_id,
                        buyer_name=buyer_name,
                        buyer_email=buyer_email,
                        amount_cents=max(int(_precio_reserva * 100), 50),
                        plot_ref=_plot_ref,
                        success_url=(
                            "https://archirapid.streamlit.app/"
                            "?stripe_session={CHECKOUT_SESSION_ID}&payment=success"
                        ),
                        cancel_url=f"https://archirapid.streamlit.app/?selected_plot={plot_id}",
                    )
                    st.session_state[_stripe_url_key] = _s_url
                    st.rerun()
                except Exception as _e:
                    st.error(f"Error al preparar la reserva: {_e}")

    # ── Tour Virtual 360° ─────────────────────────────────────────────────────
    _b64_360 = plot.get("tour_360_b64", "") or ""
    if _b64_360:
        with st.expander("🔭 Tour Virtual 360° — Explora la finca", expanded=True):
            st.components.v1.html(f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.css">
  <script src="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.js"></script>
  <style>
    body {{ margin:0; padding:0; background:#0D1B2A; }}
    #pano {{ width:100%; height:420px; border-radius:10px; overflow:hidden; }}
  </style>
</head>
<body>
  <div id="pano"></div>
  <script>
    pannellum.viewer('pano', {{
      type: 'equirectangular',
      panorama: 'data:image/jpeg;base64,{_b64_360}',
      autoLoad: true,
      autoRotate: -1.5,
      showFullscreenCtrl: true,
      showZoomCtrl: true,
      mouseZoom: true,
      hfov: 100,
      pitch: 0,
      yaw: 0,
      strings: {{
        loadButtonLabel: "Cargar Tour 360°",
        loadingLabel: "Cargando...",
        bylineLabel: "ArchiRapid"
      }}
    }});
  </script>
</body>
</html>
""", height=440, scrolling=False)

    # ── Alertas de nuevas fincas (inline, sin imports externos) ──────────────
    _pid_al = str(plot.get('id', 'x'))
    with st.expander("🔔 Avisarme cuando haya fincas similares", expanded=False):
        st.markdown("""
        <div style="background:rgba(37,99,235,0.08);border:1px solid rgba(37,99,235,0.3);
                    border-radius:10px;padding:12px 16px;margin-bottom:10px;">
            <div style="font-weight:700;color:#F8FAFC;font-size:14px;">
                🔔 Alertas de nuevas fincas
            </div>
            <div style="color:#94A3B8;font-size:12px;margin-top:2px;">
                Te avisamos por email cuando publiquemos fincas que encajen contigo
            </div>
        </div>
        """, unsafe_allow_html=True)
        import sqlite3 as _sq_al
        import datetime as _dt_al
        _al_c1, _al_c2 = st.columns(2)
        with _al_c1:
            _al_name  = st.text_input("Tu nombre",    placeholder="Nombre",         key=f"aln_{_pid_al}")
            _al_email = st.text_input("Email *",       placeholder="tu@email.com",   key=f"ale_{_pid_al}")
        with _al_c2:
            _al_price = st.number_input(
                "Presupuesto máximo (€)", min_value=0.0, max_value=5_000_000.0,
                value=float(plot.get("price") or 0) * 2,
                step=10_000.0, format="%.0f", key=f"alp_{_pid_al}",
                help="0 = sin límite"
            )
            _al_prov_default = plot.get("province") or ""
            _al_prov = st.text_input("Provincia de interés", value=_al_prov_default, key=f"alv_{_pid_al}")
        if st.button("🔔 Activar alerta", key=f"albtn_{_pid_al}", type="primary", use_container_width=True):
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
                        "SELECT id FROM plot_alerts WHERE email=? AND province=?",
                        (_al_email.lower().strip(), _al_prov)
                    ).fetchone()
                    _now_al = _dt_al.datetime.utcnow().isoformat(timespec="seconds") + "Z"
                    if _exists:
                        _c_al.execute(
                            "UPDATE plot_alerts SET name=?, max_price=?, active=1, created_at=? WHERE id=?",
                            (_al_name, _al_price, _now_al, _exists[0])
                        )
                    else:
                        _c_al.execute(
                            "INSERT INTO plot_alerts (email,name,province,max_price,created_at) VALUES (?,?,?,?,?)",
                            (_al_email.lower().strip(), _al_name, _al_prov, _al_price, _now_al)
                        )
                    _c_al.commit(); _c_al.close()
                    st.success(f"✅ Alerta activada para fincas en {_al_prov or 'España'}.")
                    try:
                        from modules.marketplace.email_notify import _send
                        _send(f"🔔 <b>Nueva alerta</b>\nEmail: {_al_email}\nProvincia: {_al_prov or 'Todas'}\nPresupuesto: €{_al_price:,.0f}")
                    except Exception:
                        pass
                except Exception:
                    st.info("✅ Petición recibida. Te contactaremos en hola@archirapid.com")

    # ── Calculadora de financiación ───────────────────────────────────────────
    try:
        from modules.marketplace.hipoteca import render_calculadora
        precio_p   = float(plot.get("price") or 0)
        sup_p      = float(plot.get("surface_m2") or plot.get("m2") or 0)
        coste_obra = sup_p * 0.33 * 1300  # edificable × €1.300/m² orientativo
        with st.expander("🏦 Calculadora de Financiación — ¿Cuánto pagaría al mes?", expanded=False):
            render_calculadora(
                precio_terreno=precio_p,
                coste_construccion=coste_obra,
                key_prefix=f"pd_{plot.get('id','x')}"
            )
    except Exception:
        pass

    # ── Proyectos compatibles ─────────────────────────────────────────────────
    try:
        sup_plot = float(plot.get("m2") or plot.get("surface_m2") or 0)
        proyectos = get_proyectos_compatibles(
            plot_id=str(plot.get("id", "")),
            client_parcel_size=sup_plot,
        )
        if proyectos:
            st.markdown("---")
            st.subheader("🏠 Proyectos Compatibles con tu Parcela")
            p_cols = st.columns(min(len(proyectos), 3))
            for i, p in enumerate(proyectos[:3]):
                with p_cols[i % 3]:
                    m2_p = p.get("m2_construidos") or p.get("area_m2") or 0
                    price_p = float(p.get("price") or 0)
                    st.markdown(f"**{p.get('title', 'Proyecto')}**")
                    st.caption(f"{m2_p:,.0f} m² construidos · €{price_p:,.0f}")
                    if st.button(
                        "Ver proyecto →",
                        key=f"pd_proj_{plot.get('id','x')}_{p['id']}",
                        use_container_width=True,
                    ):
                        st.query_params["selected_project_v2"] = str(p["id"])
                        st.rerun()
    except Exception:
        pass

    st.markdown("---")