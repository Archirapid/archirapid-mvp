import streamlit as st
import os
import json
from modules.marketplace.utils import db_conn


def _load_photos(image_paths_json, image_path_single):
    """Devuelve lista de rutas de fotos válidas."""
    paths = []
    try:
        if image_paths_json:
            parsed = json.loads(image_paths_json)
            paths = [p.replace("\\", "/") for p in parsed if p and os.path.exists(p.replace("\\", "/"))]
    except Exception:
        pass
    if not paths and image_path_single:
        image_path_single = image_path_single.replace("\\", "/")
        if os.path.exists(image_path_single):
            paths = [image_path_single]
    return paths


def _price_display(price, price_label):
    """Texto de precio para mostrar al cliente."""
    if price_label and price_label.strip():
        return price_label.strip()
    if price and float(price) > 0:
        return f"€{float(price):,.0f}"
    return "PRECIO A CONSULTAR"


def show(prefab_id):
    """Página de detalle de casa prefabricada — accesible sin login."""

    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, m2, rooms, bathrooms, floors, material, price, description, "
        "image_path, image_paths, modulos, price_label "
        "FROM prefab_catalog WHERE id=? AND active=1",
        (prefab_id,)
    )
    pf = cur.fetchone()
    conn.close()

    if not pf:
        st.error("Modelo no encontrado o no disponible.")
        if st.button("⬅️ Volver al inicio"):
            st.query_params.clear()
            st.rerun()
        return

    pf_id, name, m2, rooms, bathrooms, floors, material, price, description, \
        image_path, image_paths_json, modulos, price_label = pf

    photos = _load_photos(image_paths_json, image_path)
    price_text = _price_display(price, price_label)
    price_numeric = float(price) if price and float(price) > 0 else 0

    # Botón volver
    if st.button("⬅️ Volver al catálogo", key="prefab_back"):
        st.query_params.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(f"## 🏠 {name}")

    # --- GALERÍA ---
    if photos:
        # Foto principal grande
        # Selector de foto activa via session_state
        photo_key = f"prefab_photo_{pf_id}"
        if photo_key not in st.session_state or st.session_state[photo_key] >= len(photos):
            st.session_state[photo_key] = 0

        active_idx = st.session_state[photo_key]
        col_img, col_data = st.columns([1, 1])

        with col_img:
            st.image(photos[active_idx], use_container_width=True)
            # Miniaturas si hay más de 1 foto
            if len(photos) > 1:
                thumb_cols = st.columns(len(photos))
                for i, ph in enumerate(photos):
                    with thumb_cols[i]:
                        border = "3px solid #2563EB" if i == active_idx else "2px solid #E2E8F0"
                        st.markdown(
                            f'<img src="data:image/jpeg;base64,PLACEHOLDER" '
                            f'style="display:none">',
                            unsafe_allow_html=True
                        )
                        if st.button(f"{'●' if i == active_idx else '○'} Foto {i+1}",
                                     key=f"prefab_thumb_{pf_id}_{i}",
                                     use_container_width=True):
                            st.session_state[photo_key] = i
                            st.rerun()
    else:
        col_img, col_data = st.columns([1, 1])
        with col_img:
            st.markdown(
                '<div style="background:#F0F9FF;border:2px solid #BAE6FD;border-radius:12px;'
                'height:280px;display:flex;align-items:center;justify-content:center;font-size:5em;">🏠</div>',
                unsafe_allow_html=True
            )
            st.caption("Fotos del modelo disponibles próximamente")

    with col_data:
        # Precio
        st.markdown(f"### 💰 {price_text}")
        st.caption("INSTALACIÓN NO INCLUIDA")

        st.markdown("---")
        st.markdown("#### Especificaciones")

        specs = [
            ("📐 Superficie", f"{m2} m²"),
            ("🛏️ Habitaciones", str(rooms)),
            ("🚿 Baños", str(bathrooms)),
            ("🏢 Plantas", str(floors)),
            ("🪵 Material", material),
        ]
        if modulos:
            specs.append(("🔲 Módulos", modulos))

        for label, value in specs:
            col_l, col_v = st.columns([1, 1])
            with col_l:
                st.markdown(f"**{label}**")
            with col_v:
                st.markdown(value)

        # Estimación solo si hay precio numérico
        if price_numeric > 0:
            st.markdown("---")
            install_est = round(m2 * 180, -2)
            st.markdown(
                f'<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:12px;">'
                f'<span style="font-size:0.85em;color:#1E40AF;">'
                f'💡 <strong>Instalación estimada:</strong> €{install_est:,.0f} &nbsp;·&nbsp; '
                f'<strong>Total orientativo:</strong> €{price_numeric + install_est:,.0f}'
                f'</span></div>',
                unsafe_allow_html=True
            )

    # Descripción
    if description:
        st.markdown("---")
        st.markdown("#### Descripción")
        st.markdown(description)

    # Bloque de acción
    st.markdown("---")
    st.markdown("#### ¿Qué quieres hacer?")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown(
            '<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;padding:16px;text-align:center;">'
            '<div style="font-size:2em;">🏡</div>'
            '<div style="font-weight:700;font-size:0.9em;margin:8px 0;">Ya tengo una finca</div>'
            '<div style="font-size:0.78em;color:#64748B;">Configura esta casa sobre tu parcela en el portal de cliente</div>'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("Ir a mi portal →", key="prefab_to_portal", use_container_width=True):
            st.session_state['prefab_highlight_id'] = pf_id
            st.session_state['show_prefab_config'] = True
            st.session_state['selected_page'] = "👤 Panel de Cliente"
            st.query_params.clear()
            st.rerun()

    with col_b:
        st.markdown(
            '<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:16px;text-align:center;">'
            '<div style="font-size:2em;">🔍</div>'
            '<div style="font-weight:700;font-size:0.9em;margin:8px 0;">Quiero una finca primero</div>'
            '<div style="font-size:0.78em;color:#64748B;">Explora parcelas disponibles y elige la tuya</div>'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("Ver fincas disponibles →", key="prefab_to_fincas", use_container_width=True):
            st.query_params.clear()
            st.rerun()

    with col_c:
        st.markdown(
            '<div style="background:#FFF1F2;border:1px solid #FECDD3;border-radius:10px;padding:16px;text-align:center;">'
            '<div style="font-size:2em;">📨</div>'
            '<div style="font-weight:700;font-size:0.9em;margin:8px 0;">Solo quiero esta casa</div>'
            '<div style="font-size:0.78em;color:#64748B;">Solicita presupuesto y te contactamos en 24-48h</div>'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("Solicitar presupuesto →", key="prefab_request", use_container_width=True, type="primary"):
            st.session_state[f'prefab_request_sent_{pf_id}'] = True
            st.rerun()

    if st.session_state.get(f'prefab_request_sent_{pf_id}'):
        with st.form("prefab_contact_form"):
            st.markdown("##### Solicitud de presupuesto — **" + name + "**")
            req_name  = st.text_input("Tu nombre")
            req_email = st.text_input("Tu email")
            req_phone = st.text_input("Teléfono (opcional)")
            req_notes = st.text_area("¿Tienes ya una parcela? ¿Alguna preferencia o pregunta?")
            if st.form_submit_button("Enviar solicitud", type="primary"):
                if req_name and req_email:
                    try:
                        conn2 = db_conn()
                        cur2 = conn2.cursor()
                        cur2.execute("""
                            CREATE TABLE IF NOT EXISTS prefab_requests (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                prefab_id INTEGER, name TEXT, email TEXT,
                                phone TEXT, notes TEXT, created_at TEXT
                            )
                        """)
                        from datetime import datetime
                        cur2.execute(
                            "INSERT INTO prefab_requests (prefab_id, name, email, phone, notes, created_at) VALUES (?,?,?,?,?,?)",
                            (pf_id, req_name, req_email, req_phone, req_notes, datetime.now().isoformat())
                        )
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass
                    st.success(f"✅ Solicitud enviada. Te contactaremos en {req_email} en 24-48h.")
                    st.balloons()
                    st.session_state[f'prefab_request_sent_{pf_id}'] = False
                else:
                    st.error("Nombre y email son obligatorios.")
