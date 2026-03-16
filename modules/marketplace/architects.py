# modules/marketplace/architects.py
import streamlit as st
from modules.marketplace.utils import save_upload, db_conn, insert_user, get_user_by_email
from src import db
import uuid, json
from datetime import datetime, timedelta
from time import sleep

def check_subscription(arch_id):
    """Verifica si el arquitecto tiene suscripción activa."""
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT plan_type, end_date, monthly_proposals_limit FROM subscriptions WHERE architect_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", (arch_id,))
        row = cur.fetchone()
        if row:
            return {"plan": row[0], "end_date": row[1], "limit": row[2], "active": True}
        return {"active": False}
    except Exception:
        return {"active": False}
    finally:
        conn.close()

def _get_base_url():
    """Devuelve la URL base de la app para construir success/cancel URLs de Stripe."""
    try:
        import streamlit as st
        # En Streamlit Cloud el host viene en headers; fallback a producción
        headers = st.context.headers if hasattr(st, "context") else {}
        host = headers.get("host", "archirapid.streamlit.app")
        proto = "https" if "streamlit.app" in host or "localhost" not in host else "http"
        return f"{proto}://{host}"
    except Exception:
        return "https://archirapid.streamlit.app"


def _activate_subscription_after_payment(arch_id, plan_key, session_id):
    """Activa suscripción en BD tras verificar pago Stripe. Idempotente."""
    _PLAN_META = {
        "sub_basic":     {"name": "BASIC",      "price": 29,  "limit": 1,   "fee": 10, "days": 30},
        "sub_pro":       {"name": "PRO",         "price": 99,  "limit": 5,   "fee": 8,  "days": 30},
        "sub_pro_anual": {"name": "PRO_ANUAL",   "price": 890, "limit": 999, "fee": 8,  "days": 365},
        "sub_enterprise":{"name": "ENTERPRISE",  "price": 299, "limit": 999, "fee": 5,  "days": 30},
    }
    meta = _PLAN_META.get(plan_key)
    if not meta:
        return False
    try:
        from modules.stripe_utils import verify_session
        sess = verify_session(session_id)
        if sess.payment_status != "paid":
            return False
    except Exception:
        return False  # Sin clave Stripe real, no activar
    try:
        conn = db_conn()
        c = conn.cursor()
        # Idempotente: no duplicar si ya existe
        c.execute("SELECT id FROM subscriptions WHERE architect_id=? AND status='active' AND plan_type=?",
                  (arch_id, meta["name"]))
        if c.fetchone():
            conn.close()
            return True
        sub_id = uuid.uuid4().hex
        start = datetime.now()
        end = start + timedelta(days=meta["days"])
        c.execute("""INSERT INTO subscriptions (id, architect_id, plan_type, price,
                     monthly_proposals_limit, commission_rate, status, start_date, end_date, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                  (sub_id, arch_id, meta["name"], meta["price"], meta["limit"],
                   meta["fee"], start.isoformat(), end.isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def main():
    st.header("🏗️ Portal para Arquitectos")

    # --- 0. RETORNO DESDE STRIPE (pago de suscripción) ---
    _qp = st.query_params
    _sub_session = _qp.get("sub_session", "")
    _sub_plan    = _qp.get("sub_plan", "")
    if _sub_session and _sub_plan and st.session_state.get("arch_id"):
        if not st.session_state.get(f"sub_activated_{_sub_session}"):
            ok = _activate_subscription_after_payment(
                st.session_state["arch_id"], _sub_plan, _sub_session)
            st.session_state[f"sub_activated_{_sub_session}"] = True
            if ok:
                st.success("¡Suscripción activada correctamente! Ya tienes acceso completo.")
            else:
                st.warning("El pago no pudo verificarse. Contacta a soporte si ya fue cobrado.")
        # Limpiar params de la URL
        try:
            del st.query_params["sub_session"]
            del st.query_params["sub_plan"]
        except Exception:
            pass

    # --- 1. LOGIN / IDENTIFICACIÓN ---
    if "arch_id" not in st.session_state:
        st.info("Accede a tu cuenta profesional.")
        with st.form("login_arch"):
            email = st.text_input("Email profesional")
            name = st.text_input("Nombre del Estudio / Arquitecto")
            submitted = st.form_submit_button("Entrar / Registrarse")
            
            if submitted:
                if not email or not name:
                    st.error("Campos requeridos.")
                else:
                    # Lookup real DB
                    user_data = get_user_by_email(email)
                    
                    if user_data:
                        st.session_state["arch_id"] = user_data["id"]
                        st.session_state["arch_name"] = user_data["name"]
                        st.session_state["arch_email"] = user_data["email"]
                        st.success(f"Bienvenido, {user_data['name']}")
                    else:
                        new_id = uuid.uuid4().hex
                        insert_user({"id": new_id, "name": name, "email": email, "role": "architect", "company": name})
                        st.session_state["arch_id"] = new_id
                        st.session_state["arch_name"] = name
                        st.session_state["arch_email"] = email
                        st.success("Cuenta creada. Bienvenido.")
                    sleep(1)
                    st.rerun()
        return

    # --- 2. DASHBOARD ---
    st.write(f"Conectado como: **{st.session_state.arch_name}**")
    
    sub_status = check_subscription(st.session_state["arch_id"])
    if sub_status["active"]:
        st.caption(f"✅ Suscripción Activa: **Plan {sub_status['plan']}** (Renueva: {sub_status['end_date']})")
    else:
        st.warning("⚠️ No tienes una suscripción activa. Tu visibilidad es limitada.")

    tab_planes, tab_subir, tab_proyectos, tab_matching, tab_ia, tab_estudio = st.tabs(["💎 Planes", "📤 Subir Proyecto", "📂 Mis Proyectos", "🎯 Oportunidades", "🤖 Asistente IA", "🏠 Modo Estudio"])

    with tab_ia:
        st.subheader("Boceto Generativo con IA (Groq)")
        st.info("Genera distribuciones preliminares para tus solares o proyectos.")
        from modules.marketplace import ai_engine as _ai_eng_tab

        c_ia_1, c_ia_2 = st.columns(2)
        with c_ia_1:
            ia_m2 = st.number_input("Superficie Finca (m²)", 200, 5000, 1000)
            ia_habs = st.slider("Habitaciones", 1, 6, 3)
            if st.button("✨ Generar Distribución", key="btn_gen_dist"):
                with st.spinner("Generando distribución con IA..."):
                    plan = _ai_eng_tab.plan_vivienda(ia_m2, ia_habs)
                    if "error" in plan:
                        st.error(plan["error"])
                    else:
                        st.session_state["ia_plan"] = plan
                        st.success("Distribución calculada.")

        with c_ia_2:
            if "ia_plan" in st.session_state:
                p = st.session_state["ia_plan"]
                st.write(p.get("descripcion", ""))
                st.dataframe(p.get("habitaciones", []))

                # SVG Generation
                if st.button("🎨 Renderizar Boceto", key="btn_render_boceto"):
                    total = p.get("total_m2", ia_m2*0.33)
                    svg = _ai_eng_tab.generate_sketch_svg(p.get("habitaciones", []), total)
                    
                    # Render SVG
                    import base64
                    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
                    html = f'<img src="data:image/svg+xml;base64,{b64}" width="100%"/>'
                    st.markdown("### Boceto Preliminar")
                    st.markdown(html, unsafe_allow_html=True)
                    with st.expander("Ver Código SVG"):
                        st.code(svg, language="xml")

    with tab_estudio:
        st.subheader("🏠 Modo Estudio — Diseño IA para Cualquier Solar")
        st.write("Genera proyectos completos con IA para cualquier parcela, sin necesidad de que esté en el marketplace.")

        # Pricing cards
        _ep1, _ep2, _ep3 = st.columns(3)
        with _ep1:
            with st.container(border=True):
                st.markdown("### Por Uso")
                st.markdown("**€19 / proyecto**")
                st.write("- 1 descarga ZIP")
                st.write("- Memoria PDF + Excel")
                st.write("- BIM/IFC incluido")
                st.caption("Pago único por descarga")
        with _ep2:
            with st.container(border=True):
                st.markdown("### PRO Mensual")
                st.markdown("**€99 / mes**")
                st.write("- Descargas ilimitadas")
                st.write("- Proyectos activos en marketplace")
                st.write("- Prioridad en matching")
                st.caption("Cancela cuando quieras")
        with _ep3:
            with st.container(border=True):
                st.markdown("### PRO Anual")
                st.markdown("**€890 / año**")
                st.write("- Todo lo de PRO Mensual")
                st.write("- **Ahorra 3 meses** vs mensual")
                st.write("- Soporte prioritario")
                st.caption("€99 × 12 = €1.188 → ahorras €298")

        st.markdown("---")

        if not st.session_state.get("estudio_mode"):
            st.subheader("Nuevo Diseño")
            with st.form("estudio_form"):
                _fc1, _fc2 = st.columns(2)
                with _fc1:
                    _e_ref     = st.text_input("Referencia Catastral (opcional)", "")
                    _e_address = st.text_input("Dirección del Solar", "")
                    _e_m2      = st.number_input("Superficie Finca (m²)", min_value=50, max_value=20000, value=500)
                    _e_rooms   = st.slider("Habitaciones deseadas", 1, 8, 3)
                with _fc2:
                    _e_style   = st.selectbox("Estilo Arquitectónico", ["Moderno", "Mediterráneo", "Industrial", "Minimalista", "Rústico", "Montaña"])
                    _e_budget  = st.number_input("Presupuesto estimado (€)", min_value=50000, max_value=5000000, value=200000, step=10000)
                    _e_client  = st.text_input("Nombre del cliente (para el PDF)", "")

                if st.form_submit_button("🚀 Iniciar Diseño con IA", type="primary"):
                    _arch_name = st.session_state.get("arch_name", "Arquitecto")
                    _max_build = round(_e_m2 * 0.33, 1)

                    # Synthetic plot data
                    st.session_state["design_plot_data"] = {
                        "id":              f"estudio_{uuid.uuid4().hex[:8]}",
                        "title":           _e_address or "Solar Modo Estudio",
                        "catastral_ref":   _e_ref,
                        "address":         _e_address,
                        "total_m2":        float(_e_m2),
                        "buildable_m2":    _max_build,
                        "m2":              float(_e_m2),
                        "surface_m2":      float(_e_m2),
                        "province":        "",
                        "lat":             None,
                        "lon":             None,
                        "owner_email":     st.session_state.get("arch_email", ""),
                        "description":     f"Solar diseñado en Modo Estudio por {_arch_name}",
                    }

                    # Pre-filled requirements
                    st.session_state["ai_house_requirements"] = {
                        "target_area_m2":       min(120.0, _max_build),
                        "max_buildable_m2":     _max_build,
                        "budget":               float(_e_budget),
                        "bedrooms":             _e_rooms,
                        "bathrooms":            max(1, _e_rooms - 1),
                        "wants_pool":           False,
                        "wants_porch":          True,
                        "wants_garage":         False,
                        "wants_outhouse":       False,
                        "max_floors":           1,
                        "style":                _e_style,
                        "materials":            ["hormigón"],
                        "notes":                "",
                        "orientation":          "Sur",
                        "roof_type":            "A dos aguas",
                        "energy_rating":        "B",
                        "accessibility":        False,
                        "sustainable_materials": [],
                        "nombre_proyecto":      _e_address or "Proyecto Modo Estudio",
                        "cliente":              _e_client,
                        "arquitecto":           _arch_name,
                    }

                    st.session_state["estudio_mode"]      = True
                    st.session_state["estudio_arch_name"] = _arch_name
                    st.session_state["estudio_client_name"] = _e_client

                    # Clear design_plot_id so flow.main() uses design_plot_data directly
                    st.session_state.pop("design_plot_id", None)

                    # Clear any stale flow keys
                    for _k in ["ai_house_step", "ai_house_rooms", "floor_plan_svg",
                               "floor_plan_signature", "ai_room_proposal", "babylon_html",
                               "babylon_editor_used", "babylon_modified_layout",
                               "current_floor_plan", "final_floor_plan", "selected_style_key",
                               "babylon_captures", "babylon_captures_thumb",
                               "pago_completado", "total_pagado", "estudio_pago_completado",
                               "stripe_session_id_estudio", "stripe_checkout_url_estudio",
                               "stripe_session_id_s6", "stripe_checkout_url_s6",
                               "doc_detail_s5", "svc_detail_s5", "coste_doc_s5", "coste_servicios_s5"]:
                        st.session_state.pop(_k, None)

                    st.rerun()
        else:
            _col_rst, _ = st.columns([1, 3])
            with _col_rst:
                if st.button("← Nuevo Diseño", key="estudio_reset"):
                    for _k in ["estudio_mode", "estudio_arch_name", "estudio_client_name",
                               "design_plot_data", "design_plot_id",
                               "ai_house_step", "ai_house_rooms", "floor_plan_svg",
                               "floor_plan_signature", "ai_room_proposal", "babylon_html",
                               "babylon_editor_used", "babylon_modified_layout",
                               "current_floor_plan", "final_floor_plan", "selected_style_key",
                               "babylon_captures", "babylon_captures_thumb",
                               "ai_house_requirements", "pago_completado", "total_pagado",
                               "estudio_pago_completado", "stripe_session_id_estudio",
                               "stripe_checkout_url_estudio", "stripe_session_id_s6",
                               "stripe_checkout_url_s6", "doc_detail_s5", "svc_detail_s5",
                               "coste_doc_s5", "coste_servicios_s5"]:
                        st.session_state.pop(_k, None)
                    st.rerun()

            from modules.ai_house_designer import flow as _estudio_flow
            _estudio_flow.main()

    with tab_planes:
        st.subheader("Elige tu nivel de visibilidad")

        # Modo Estudio pricing reminder
        with st.expander("💡 Modo Estudio — Descarga de proyectos", expanded=False):
            st.write("Descarga proyectos generados en Modo Estudio:")
            st.write("- **Por uso**: €19 por proyecto (plan Free)")
            st.write("- **PRO Mensual / Anual**: descargas ilimitadas (activar abajo)")

        col1, col2, col3 = st.columns(3)
        
        plans = [
            {"name": "BASIC",      "price": "29€/mes",  "limit": 1,   "fee": 10, "stripe_key": "sub_basic",     "label": "Contratar BASIC",      "days": 30},
            {"name": "PRO",        "price": "99€/mes",  "limit": 5,   "fee": 8,  "stripe_key": "sub_pro",        "label": "Contratar PRO",         "days": 30},
            {"name": "ENTERPRISE", "price": "299€/mes", "limit": 999, "fee": 5,  "stripe_key": "sub_enterprise", "label": "Contratar ENTERPRISE",  "days": 30},
        ]

        # Fila extra: PRO Anual (ahorro)
        st.markdown("---")
        with st.container(border=True):
            ca1, ca2 = st.columns([3, 1])
            with ca1:
                st.markdown("### PRO Anual — **890€/año** *(ahorra 3 meses)*")
                st.write("- Modo Estudio ilimitado · 999 proyectos activos · 8% comisión · Badge verificado")
            with ca2:
                if st.button("Contratar PRO Anual", key="plan_pro_anual", type="primary"):
                    try:
                        from modules.stripe_utils import create_checkout_session
                        base = _get_base_url()
                        success_url = f"{base}/?page=Arquitectos (Marketplace)&sub_session={{CHECKOUT_SESSION_ID}}&sub_plan=sub_pro_anual"
                        cancel_url  = f"{base}/?page=Arquitectos (Marketplace)"
                        url, sid = create_checkout_session(
                            ["sub_pro_anual"], "sub_pro_anual",
                            st.session_state.get("arch_email", ""),
                            success_url, cancel_url)
                        st.session_state["sub_stripe_url_pro_anual"] = url
                    except Exception as e:
                        st.error(f"Error al crear sesión de pago: {e}")
            if st.session_state.get("sub_stripe_url_pro_anual"):
                st.link_button("💳 Ir a pago PRO Anual", st.session_state["sub_stripe_url_pro_anual"], type="primary")
        st.markdown("---")

        for p in plans:
            with col1 if p['name']=="BASIC" else col2 if p['name']=="PRO" else col3:
                with st.container(border=True):
                    st.markdown(f"### {p['name']}")
                    st.markdown(f"**{p['price']}**")
                    st.write(f"- {p['limit']} Proyectos activos")
                    st.write(f"- {p['fee']}% Comisión plataforma")
                    _url_key = f"sub_stripe_url_{p['stripe_key']}"
                    if st.button(p['label'], key=f"plan_{p['name']}"):
                        try:
                            from modules.stripe_utils import create_checkout_session
                            base = _get_base_url()
                            success_url = f"{base}/?page=Arquitectos (Marketplace)&sub_session={{CHECKOUT_SESSION_ID}}&sub_plan={p['stripe_key']}"
                            cancel_url  = f"{base}/?page=Arquitectos (Marketplace)"
                            url, sid = create_checkout_session(
                                [p['stripe_key']], p['stripe_key'],
                                st.session_state.get("arch_email", ""),
                                success_url, cancel_url)
                            st.session_state[_url_key] = url
                        except Exception as e:
                            st.error(f"Error al crear sesión de pago: {e}")
                    if st.session_state.get(_url_key):
                        st.link_button(f"💳 Ir a pago {p['name']}", st.session_state[_url_key])

    with tab_subir:
        if not sub_status["active"]:
            st.error("Necesitas un plan activo para subir proyectos.")
        else:
            st.subheader("Nuevo Proyecto de Catálogo")
            st.info("Los proyectos se 'emparejan' automáticamente con fincas compatibles basándose en la edificabilidad.")
            
            with st.form("new_project"):
                c1, c2 = st.columns(2)
                with c1:
                    title = st.text_input("Título del Modelo")
                    style = st.selectbox("Estilo", ["Moderno", "Mediterráneo", "Industrial", "Minimalista"])
                    floors = st.number_input("Plantas", min_value=1, value=1)
                with c2:
                    price = st.number_input("Precio Estimado Construcción (€)", min_value=50000.0)
                    area = st.number_input("Superficie Construida (m²)", min_value=30.0)
                    footprint = st.number_input("Ocupación en Planta (m²)", min_value=30.0, help="Huella del edificio en el suelo. Importante para matching.")

                desc = st.text_area("Descripción y Acabados")
                
                # Calculation of requirements
                min_plot = footprint / 0.33  # Regla aproximada del 33% de ocupacion maxima
                st.caption(f"📏 **Requisito Automático:** Este proyecto requerirá una parcela de al menos **{min_plot:.0f} m²** (asumiendo coef. ocupación 33%)")

                uploaded_file = st.file_uploader("Render Principal (JPG/PNG)", type=['jpg','png','jpeg'])
                uploaded_pdf = st.file_uploader("Memoria / Planos (PDF)", type=['pdf'])
                
                if st.form_submit_button("Publicar Proyecto"):
                    if not title or area <= 0:
                        st.error("Datos incompletos.")
                    else:
                         # Save files
                        img_path = save_upload(uploaded_file, prefix="proj_img") if uploaded_file else None
                        pdf_path = save_upload(uploaded_pdf, prefix="proj_pdf") if uploaded_pdf else None
                        
                        proj_data = {
                            "id": uuid.uuid4().hex,
                            "architect_id": st.session_state["arch_id"],
                            "title": title,
                            "description": desc,
                            "area_m2": area,
                            "price": price,
                            "architect_name": st.session_state["arch_name"],
                            "m2_parcela_minima": min_plot,
                            "style": style,
                            "plantas": floors,
                            "planos_pdf": pdf_path,
                            "foto_principal": img_path
                        }
                        
                        try:
                            # Usamos la funcion flexible de db.py
                            db.insert_project(proj_data)
                            st.success("✅ Proyecto publicado en el marketplace.")
                            sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error guardando: {e}")

    with tab_proyectos:
        st.subheader("Tu Catálogo")
        # Query simple manual
        conn = db.get_conn()
        import pandas as pd
        try:
            df = pd.read_sql_query("SELECT id, title, area_m2, price, m2_parcela_minima FROM projects WHERE architect_id=?", conn, params=(st.session_state["arch_id"],))
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("No hay proyectos.")
        except Exception as e:
            st.error(e)
        finally:
            conn.close()

    with tab_matching:
        st.subheader("🎯 Oportunidades (Solares Compatibles)")
        if not sub_status["active"]:
             st.warning("Suscríbete para ver oportunidades y contactar clientes.")
        else:
            from modules.marketplace import ai_engine as _ai_eng_match
            # 1. Traer mis proyectos
            try:
                conn = db.get_conn()
                my_projects = pd.read_sql_query("SELECT id, title, m2_parcela_minima FROM projects WHERE architect_id=?", conn, params=(st.session_state["arch_id"],))
                
                # 2. Traer todos los solares
                # Nota: En prod, hacer esto con SQL join espacial o filtros más inteligentes
                all_plots = pd.read_sql_query("SELECT id, title, m2, province, price, description FROM plots", conn)
                
                if my_projects.empty:
                    st.info("Sube proyectos primero para encontrar solares compatibles.")
                elif all_plots.empty:
                    st.info("No hay solares registrados en la plataforma aún.")
                else:
                    st.write(f"Analizando compatibilidad de tus **{len(my_projects)} proyectos** con **{len(all_plots)} solares** disponibles...")
                    
                    found_matches = False
                    
                    for idx, plot in all_plots.iterrows():
                        # Lógica simple de matching: El solar debe ser mayor que el requerimiento mínimo del proyecto
                        # Convertimos a numérico por si acaso
                        plot_m2 = float(plot['m2']) if plot['m2'] else 0
                        
                        compatible_projects = my_projects[my_projects['m2_parcela_minima'] <= plot_m2]
                        
                        if not compatible_projects.empty:
                            found_matches = True
                            with st.expander(f"📍 Solar en {plot['province']} - {plot['title']} ({plot_m2} m²)", expanded=True):
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    st.write(f"**Precio:** {plot['price']}€")
                                    st.write(f"_{plot['description']}_")
                                    st.write("---")
                                    st.write(f"✅ **{len(compatible_projects)} Proyectos Compatibles:**")
                                    for idx_p, proj in compatible_projects.iterrows():
                                        st.write(f"- 🏠 **{proj['title']}** (Req: {proj['m2_parcela_minima']:.0f} m²)")
                                    
                                    # AI Analysis
                                    with st.expander("🤖 Análisis de Viabilidad IA"):
                                        if st.button("Analizar Compatibilidad", key=f"ai_{plot['id']}"):
                                            with st.spinner("IA analizando normativa y encaje..."):
                                                prompt = f"Analiza la viabilidad preliminar de construir un proyecto residencial en un solar de {plot['m2']} m2 en {plot['province']}. Descripción del terreno: {plot['description']}. Precio suelo: {plot['price']}€. Dame 3 pros y 1 contra."
                                                analysis = _ai_eng_match.generate_text(prompt)
                                                st.write(analysis)
                                
                                with c2:
                                    # Formulario de propuesta rápida
                                    st.markdown(f"**Proponer para: {plot['title']}**")
                                    proj_selected = st.selectbox("Elige Proyecto", compatible_projects['title'], key=f"sel_{plot['id']}")
                                    msg = st.text_area("Mensaje al Propietario", "Hola, me interesa este solar para mi proyecto...", key=f"msg_{plot['id']}")
                                    bid_price = st.number_input("Oferta / Precio Proyecto (€)", value=0.0, key=f"prc_{plot['id']}")
                                    
                                    if st.button("Enviar 🚀", key=f"btn_{plot['id']}"):
                                        # Encontrar ID del proyecto seleccionado
                                        proj_id = compatible_projects[compatible_projects['title'] == proj_selected].iloc[0]['id']
                                        
                                        prop_data = {
                                            "id": uuid.uuid4().hex,
                                            "architect_id": st.session_state["arch_id"],
                                            "plot_id": plot['id'],
                                            "project_id": proj_id,
                                            "message": msg,
                                            "price": bid_price,
                                            "status": "pending",
                                            "created_at": datetime.now().isoformat()
                                        }
                                        try:
                                            db.insert_proposal(prop_data)
                                            st.success("Propuesta enviada correctamente.")
                                        except Exception as e:
                                            st.error(f"Error al enviar: {e}")

                    if not found_matches:
                        st.info("No se encontraron solares compatibles con tus proyectos actuales (por requisitos de superficie).")
            
            except Exception as e:
                st.error(f"Error cargando oportunidades: {e}")
            finally:
                if 'conn' in locals(): conn.close()

