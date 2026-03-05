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
    else:
        st.info("📋 Recomendado: Verifica que los datos de la finca coincidan con la nota catastral antes de comprar")

        if st.button("🔍 Verificar con Nota Catastral", key=f"verify_ia_{plot_id}", type="secondary"):
            with st.spinner("Analizando datos catastrales completos con IA..."):
                try:
                    from modules.marketplace.ai_engine import extraer_datos_catastral_completo

                    # Buscar archivos PDF catastrales
                    import os
                    from pathlib import Path

                    pdf_paths = [
                        Path("archirapid_extract/catastro_output/nota_catastral.pdf"),
                        Path("uploads/nota_catastral.pdf"),
                        Path("catastro_output/nota_catastral.pdf")
                    ]

                    pdf_encontrado = None
                    for pdf_path in pdf_paths:
                        if pdf_path.exists():
                            pdf_encontrado = pdf_path
                            break

                    if pdf_encontrado:
                        datos_extraidos = extraer_datos_catastral_completo(str(pdf_encontrado))

                        if datos_extraidos and "error" not in datos_extraidos:
                            # Comparar datos extraídos con datos de la finca
                            superficie_pdf = datos_extraidos.get("superficie_m2", 0)
                            ref_catastral_pdf = datos_extraidos.get("referencia_catastral", "")

                            superficie_finca = plot.get('surface_m2') or plot.get('m2') or 0
                            ref_catastral_finca = plot.get('catastral_ref', '')

                            # Verificar coincidencias
                            superficie_ok = abs(superficie_pdf - superficie_finca) < 10  # Tolerancia de 10m²
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

                                # Mostrar plano vectorizado si existe
                                archivos = datos_extraidos.get('archivos_generados', {})
                                plano_visualizado = archivos.get('plano_vectorizado')
                                plano_limpio = archivos.get('plano_limpio')

                                if plano_visualizado and Path(plano_visualizado).exists():
                                    st.markdown("### 📐 Plano Catastral Vectorizado")
                                    st.image(str(plano_visualizado), caption="Plano con contornos detectados", use_container_width=True)

                                    # Opción de descarga del plano técnico
                                    if plano_limpio and Path(plano_limpio).exists():
                                        with open(plano_limpio, "rb") as file:
                                            st.download_button(
                                                label="📄 Descargar Plano Técnico (PNG)",
                                                data=file,
                                                file_name="plano_catastral_limpio.png",
                                                mime="image/png",
                                                help="Plano limpio con medidas para uso arquitectónico"
                                            )

                                st.markdown("### 🔍 Comparación con Datos Publicados")
                                st.write(f"**Superficie Finca:** {superficie_finca} m²")
                                st.write(f"**Referencia Catastral Finca:** {ref_catastral_finca}")

                                if superficie_ok and ref_ok:
                                    st.success("✅ VERIFICACIÓN EXITOSA: Los datos coinciden perfectamente")
                                    st.session_state[f'ia_verified_{plot_id}'] = True
                                    st.balloons()
                                elif superficie_ok:
                                    st.warning("⚠️ Superficie correcta, pero referencia catastral diferente")
                                    st.info("Los datos de superficie coinciden, pero verifica la referencia catastral")
                                else:
                                    st.error("❌ DISCREPANCIA: Los datos de superficie no coinciden")
                                    st.warning("Revisa la información antes de proceder con la compra")
                        else:
                            error_msg = datos_extraidos.get("error", "Error desconocido")
                            st.error(f"❌ Error en extracción completa: {error_msg}")
                    else:
                        st.warning("⚠️ No se encontró archivo PDF de nota catastral")
                        st.info("Sube un archivo 'nota_catastral.pdf' a la carpeta uploads/ o archirapid_extract/catastro_output/")

                except Exception as e:
                    st.error(f"Error en verificación IA completa: {str(e)}")

    st.markdown("---")

    # Botón de acción principal: Reservar o Comprar
    st.subheader("📝 ¿Interesado en esta finca?")

    # Estado de expansión del formulario
    show_form = st.session_state.get(f'form_expanded_{plot_id}', False)

    if st.button("📝 Reservar o Comprar Finca", type="primary"):
        st.session_state[f'form_expanded_{plot_id}'] = not show_form
        st.rerun()

    # Formulario de contacto (expandible)
    if st.session_state.get(f'form_expanded_{plot_id}', False):
        st.markdown("### 📋 Formulario de Contacto")

        col_form1, col_form2 = st.columns(2)

        with col_form1:
            buyer_name = st.text_input("Nombre completo *", key=f"name_{plot_id}")
            buyer_email = st.text_input("Email *", key=f"email_{plot_id}")
            buyer_password = st.text_input("Contraseña de acceso *", type="password", key=f"password_{plot_id}",
                                         help="Esta será tu contraseña para acceder a tu panel de cliente")

        with col_form2:
            buyer_phone = st.text_input("Teléfono", key=f"phone_{plot_id}")
            reservation_type = st.selectbox(
                "Tipo de interés",
                ["Reserva (10%)", "Compra completa (100%)"],
                key=f"type_{plot_id}"
            )

        # Calcular importe según tipo
        if reservation_type == "Reserva (10%)":
            amount = precio * 0.1
            amount_text = f"€{amount:,.0f} (10% del precio total)"
        else:
            amount = precio
            amount_text = f"€{amount:,.0f} (precio completo)"

        st.markdown(f"**Importe a pagar:** {amount_text}")

        if st.button("✅ Confirmar y Proceder", type="primary", key=f"confirm_{plot_id}"):
            if not buyer_name or not buyer_email or not buyer_password:
                st.error("Por favor completa nombre, email y contraseña (todos los campos marcados con * son obligatorios)")
            elif len(buyer_password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres")
            else:
                try:
                    kind = "reservation" if "Reserva" in reservation_type else "purchase"
                    rid = reserve_plot(
                        plot_id,
                        buyer_name,
                        buyer_email,
                        amount,
                        kind=kind
                    )

                    # Crear/actualizar usuario cliente con contraseña
                    create_or_update_client_user(buyer_email, buyer_name, buyer_password)

                    # SESIÓN REFORZADA - Asegurar acceso inmediato al panel
                    st.session_state['payment_confirmed'] = True
                    st.session_state['active_purchase_id'] = rid

                    # FLUJO DE ENTRADA OBLIGATORIO - CERO FRICCIÓN
                    st.session_state['logged_in'] = True
                    st.session_state['user_email'] = buyer_email
                    st.session_state['role'] = 'client'
                    st.session_state['auto_owner_email'] = buyer_email  # ESTA ES LA LLAVE QUE FALTA
                    st.session_state['user_name'] = buyer_name  # Guardar nombre del usuario
                    st.session_state['selected_page'] = '👤 Panel de Cliente'
                    st.rerun()

                except Exception as e:
                    st.error(f"Error al procesar la operación: {str(e)}")

    st.markdown("---")