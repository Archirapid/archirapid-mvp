# modules/prefabricadas/portal.py
# Portal de empresa prefabricada: registro, login, dashboard, pago de planes
import streamlit as st
import hashlib
import uuid
from modules.marketplace.utils import db_conn

PLANES_PREFAB = {
    "starter": {
        "label": "🏠 Starter",
        "precio": 59,
        "modelos": 3,
        "features": [
            "Hasta 3 modelos en catálogo",
            "Ficha con fotos y descripción",
            "Recepción de leads directos",
        ],
        "price_id": "price_starter_prefab",
    },
    "profesional": {
        "label": "⭐ Profesional",
        "precio": 129,
        "modelos": 6,
        "features": [
            "Hasta 6 modelos en catálogo",
            "Badge empresa verificada",
            "Apareces en panel del comprador al elegir finca",
            "Todo lo del plan Starter",
        ],
        "price_id": "price_profesional_prefab",
    },
    "premium": {
        "label": "🏆 Premium",
        "precio": 229,
        "modelos": 12,
        "features": [
            "Hasta 12 modelos en catálogo",
            "Posición prioritaria en home",
            "Notificación a compradores activos",
            "Métricas de visitas y leads",
            "Todo lo del plan Profesional",
        ],
        "price_id": "price_premium_prefab",
    },
}

# Alias para compatibilidad con lógica existente
_PLANES = {
    "starter":     {"label": "Starter",     "precio": 59,  "emoji": "🏠"},
    "profesional": {"label": "Profesional", "precio": 129, "emoji": "⭐"},
    "premium":     {"label": "Premium",     "precio": 229, "emoji": "🏆"},
    "destacado":   {"label": "Destacado",   "precio": 49,  "emoji": "🌟"},
    "normal":      {"label": "Starter",     "precio": 59,  "emoji": "🏠"},
}


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _ensure_table():
    conn = db_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prefab_companies (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                cif TEXT,
                email TEXT UNIQUE NOT NULL,
                telefono TEXT,
                password_hash TEXT,
                plan TEXT DEFAULT 'starter',
                paid_until TEXT,
                active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        # Columnas nuevas — idempotentes
        for _col, _def in [
            ("comision_pct", "REAL DEFAULT 4.0"),
            ("destacado_activo", "INTEGER DEFAULT 0"),
            ("destacado_hasta", "TEXT"),
            ("hash_contrato_comision", "TEXT"),
            ("pdf_contrato_url", "TEXT"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE prefab_companies ADD COLUMN {_col} {_def}"
                )
                conn.commit()
            except Exception:
                pass  # columna ya existe
    finally:
        conn.close()


def _get_company(email: str):
    conn = db_conn()
    try:
        row = conn.execute(
            """SELECT id, nombre, cif, email, telefono, plan, paid_until, active,
                      comision_pct, destacado_activo, destacado_hasta,
                      hash_contrato_comision, pdf_contrato_url
               FROM prefab_companies WHERE email=?""",
            (email,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return dict(zip([
        "id", "nombre", "cif", "email", "telefono", "plan", "paid_until", "active",
        "comision_pct", "destacado_activo", "destacado_hasta",
        "hash_contrato_comision", "pdf_contrato_url"
    ], row))


def main():
    _ensure_table()

    # Recuperar sesión si viene de retorno Stripe con ?email=
    if (
        not st.session_state.get("prefab_company")
        and st.query_params.get("pago") == "ok"
    ):
        _email_ret = st.query_params.get("email", "")
        if _email_ret:
            _comp_ret = _get_company(_email_ret)
            if _comp_ret:
                st.session_state["prefab_company"] = _comp_ret

    _company = st.session_state.get("prefab_company")

    if _company:
        _render_dashboard(_company)
    else:
        _render_login_register()


def _render_login_register():
    st.title("🏠 Portal de Empresas Prefabricadas")
    st.caption("Gestiona tu presencia en ArchiRapid y llega a clientes que ya han elegido su terreno.")

    tab_login, tab_register = st.tabs(["🔐 Acceder", "📝 Registrarse"])

    with tab_login:
        st.subheader("Acceso empresa")
        _email = st.text_input("Email corporativo", key="pref_login_email")
        _pw = st.text_input("Contraseña", type="password", key="pref_login_pw")
        if st.button("🔐 Acceder", type="primary", use_container_width=True, key="pref_login_btn"):
            if _email and _pw:
                _comp = _get_company(_email)
                if _comp and _comp.get("password_hash") == _hash_pw(_pw):
                    if not _comp["active"]:
                        st.warning("Tu cuenta está pendiente de aprobación por ArchiRapid. Te avisaremos por email.")
                    else:
                        st.session_state["prefab_company"] = _comp
                        st.rerun()
                else:
                    st.error("Email o contraseña incorrectos.")
            else:
                st.warning("Introduce email y contraseña.")

    with tab_register:
        st.subheader("Registro de empresa")
        st.info("Una vez registrada, el equipo de ArchiRapid revisará tu solicitud en menos de 24h.")

        # Detectar si viene con token de invitación
        _invite_activo = st.session_state.get("_invite_activo", False)
        _invite_plan   = st.session_state.get("_invite_plan", "starter")
        _invite_meses  = st.session_state.get("_invite_meses", 3)
        _invite_token  = st.session_state.get("_invite_token", "")

        if _invite_activo:
            st.success(
                f"🎟️ Invitación válida — Acceso gratuito "
                f"{_invite_meses} mes(es) · Plan {_invite_plan}"
            )

        with st.form("pref_register_form"):
            _rc1, _rc2 = st.columns(2)
            with _rc1:
                _rn   = st.text_input("Nombre empresa *")
                _re   = st.text_input("Email corporativo *")
                _rcif = st.text_input("CIF")
            with _rc2:
                _rt   = st.text_input("Teléfono")
                _rpw  = st.text_input("Contraseña *", type="password")
                _rpw2 = st.text_input("Repetir contraseña *", type="password")

            # Planes
            if not _invite_activo:
                st.markdown("#### Elige tu plan de publicación:")
                _cols_planes = st.columns(3)
                for i, (plan_key, plan_info) in enumerate(PLANES_PREFAB.items()):
                    with _cols_planes[i]:
                        st.markdown(
                            f"**{plan_info['label']}**\n\n"
                            f"### {plan_info['precio']}€/mes\n\n"
                            f"*Hasta {plan_info['modelos']} modelos*"
                        )
                        for feat in plan_info["features"]:
                            st.markdown(f"✅ {feat}")
                        st.markdown("")

                _rplan = st.radio(
                    "Plan seleccionado",
                    options=list(PLANES_PREFAB.keys()),
                    format_func=lambda k: f"{PLANES_PREFAB[k]['label']} — {PLANES_PREFAB[k]['precio']}€/mes",
                    horizontal=True,
                    key="prefab_plan_radio"
                )
            else:
                st.info(
                    f"✅ Plan **{_invite_plan}** activado automáticamente "
                    f"por tu invitación — {_invite_meses} mes(es) gratuitos. "
                    "No es necesario seleccionar ningún plan."
                )
                # Forzar el plan del invite en session_state
                # para que el INSERT lo use
                _rplan = _invite_plan

            st.markdown("---")
            st.markdown("**📊 Comisión de venta aplicable**")
            _comision_reg = st.slider(
                "Porcentaje de comisión sobre precio de venta final (obligatorio)",
                min_value=2.5,
                max_value=8.0,
                value=4.0,
                step=0.5,
                format="%.1f%%",
                key="prefab_comision_slider",
                help="ArchiRapid aplicará este porcentaje sobre cada venta "
                     "intermediada a través de la plataforma."
            )
            st.caption(
                f"⚖️ Comisión acordada: **{_comision_reg}%** sobre precio de venta. "
                "Quedará reflejada en el contrato de intermediación firmado "
                "digitalmente con SHA-256."
            )

            if st.form_submit_button("📝 Solicitar registro", type="primary"):
                if not (_rn and _re and _rpw):
                    st.error("Nombre, email y contraseña son obligatorios.")
                elif _rpw != _rpw2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    _existing = _get_company(_re)
                    if _existing:
                        st.warning("Ya existe una cuenta con ese email. Usa el login.")
                    else:
                        _new_id = uuid.uuid4().hex
                        _conn_reg = db_conn()
                        try:
                            _conn_reg.execute(
                                """INSERT INTO prefab_companies
                                   (id, nombre, cif, email, telefono, password_hash,
                                    plan, comision_pct, active, status)
                                   VALUES (?,?,?,?,?,?,?,?,1,'autorizado')""",
                                (_new_id, _rn, _rcif or None, _re, _rt or None,
                                 _hash_pw(_rpw), _rplan, _comision_reg)
                            )
                            _conn_reg.commit()
                            # Generar contrato SHA-256
                            try:
                                from disclaimer_legal import generar_contrato_comision
                                _hash_c, _pdf_c = generar_contrato_comision(
                                    email=_re,
                                    nombre=_rn,
                                    titulo_finca=f"Empresa prefabricada: {_rn}",
                                    precio=0,
                                    comision_pct=int(_comision_reg * 10),
                                    plot_id="prefab"
                                )
                                if _hash_c:
                                    _conn_reg.execute(
                                        "UPDATE prefab_companies "
                                        "SET hash_contrato_comision=?, pdf_contrato_url=? "
                                        "WHERE email=?",
                                        (_hash_c, _pdf_c, _re)
                                    )
                                    _conn_reg.commit()
                            except Exception:
                                pass
                            try:
                                from modules.marketplace.email_notify import _send
                                _send(f"🏠 Nueva empresa prefabricada registrada:\n{_rn} ({_re})\nPlan: {_rplan} · Comisión: {_comision_reg}%")
                            except Exception:
                                pass
                            # Acceso inmediato + redirigir según si hay token de invitación
                            _nueva_empresa = _get_company(_re)
                            if _invite_activo and _invite_token and _nueva_empresa:
                                # Actualizar plan con cortesía
                                import datetime as _dt_inv
                                _until_inv = (
                                    _dt_inv.datetime.utcnow()
                                    + _dt_inv.timedelta(days=30 * int(_invite_meses))
                                ).strftime("%Y-%m-%d")
                                try:
                                    _cn_upd = db_conn()
                                    _cn_upd.execute("""
                                        UPDATE prefab_companies
                                        SET plan=?, paid_until=?,
                                            active=1, status='autorizado'
                                        WHERE email=?
                                    """, (_invite_plan, _until_inv, _re))
                                    _cn_upd.execute("""
                                        UPDATE invitaciones
                                        SET estado='usado',
                                            usado_at=?,
                                            usado_por_email=?
                                        WHERE token=?
                                    """, (
                                        _dt_inv.datetime.utcnow().isoformat() + "Z",
                                        _re, _invite_token
                                    ))
                                    _cn_upd.commit()
                                    _cn_upd.close()
                                except Exception as _eu:
                                    st.error(f"Error activando cortesía: {_eu}")

                                # Recargar empresa con datos actualizados
                                _empresa_final = _get_company(_re)
                                if _empresa_final:
                                    # Limpiar flags invite
                                    st.session_state["_invite_completado"] = True
                                    st.session_state.pop("_invite_activo", None)
                                    st.session_state.pop("_invite_token", None)
                                    st.session_state.pop("_invite_plan", None)
                                    st.session_state.pop("_invite_meses", None)
                                    # Setear sesión empresa
                                    st.session_state["prefab_company"] = _empresa_final
                                    # NO hacer st.rerun() aquí — dejar que el flujo
                                    # continúe naturalmente al dashboard
                                    st.success(
                                        f"✅ Bienvenido/a. Tu acceso gratuito de "
                                        f"{_invite_meses} mes(es) está activo. "
                                        "Accediendo a tu panel..."
                                    )
                                    st.rerun()
                                else:
                                    st.error(
                                        "Registro completado pero no se pudo "
                                        "cargar el panel. Accede con tus credenciales."
                                    )
                            else:
                                st.success("✅ Empresa registrada. Redirigiendo al pago del plan...")
                                import time
                                time.sleep(1)
                                if _nueva_empresa:
                                    st.session_state["prefab_company"] = _nueva_empresa
                                    _checkout_plan(_rplan, _nueva_empresa)
                                else:
                                    st.info(
                                        "Registro completado. Accede con tus credenciales "
                                        "para activar tu plan."
                                    )
                            st.stop()
                        except Exception as _ex:
                            st.error(f"Error en registro: {_ex}")
                        finally:
                            _conn_reg.close()


def _render_dashboard(company: dict):
    """Dashboard para empresa prefabricada autenticada."""
    st.title(f"🏠 {company['nombre']}")

    _co1, _co2 = st.columns([5, 1])
    with _co1:
        _plan_key = company.get("plan") or "starter"
        _plan_info = _PLANES.get(_plan_key, _PLANES["starter"])
        st.caption(f"Plan: {_plan_info['emoji']} **{_plan_info['label']}** | Email: {company['email']}")
    with _co2:
        if st.button("🚪 Salir", key="pref_logout"):
            st.session_state.pop("prefab_company", None)
            st.rerun()

    # Banner estado plan
    _plan = company.get("plan") or "starter"
    _paid_until = company.get("paid_until")
    _plan_label = _PLANES.get(_plan, _PLANES["starter"])["label"]
    if _plan in ("profesional", "premium", "destacado"):
        st.success(f"⭐ Plan {_plan_label} activo — válido hasta: {_paid_until or 'indefinido'}")
    else:
        st.info(f"📋 Plan {_plan_label} activo — válido hasta: {_paid_until or 'indefinido'}")

    # Comisión acordada y contrato
    _comision_display = company.get("comision_pct") or 4.0
    st.caption(f"📊 Comisión de intermediación acordada: **{_comision_display}%**")
    if company.get("pdf_contrato_url"):
        st.markdown(f"[📄 Ver contrato de intermediación]({company['pdf_contrato_url']})")

    tab_catalogo, tab_plan, tab_datos = st.tabs(["🏭 Mis modelos", "💳 Mi plan", "📋 Mis datos"])

    with tab_catalogo:
        st.subheader("Modelos en el catálogo")
        _company_id = st.session_state.get("prefab_company", {}).get("id", "")
        _conn_cat = db_conn()
        try:
            _models = _conn_cat.execute("""
                SELECT id, name, m2, price, price_label,
                       active, material, status, image_paths,
                       prefab_company_id
                FROM prefab_catalog
                WHERE prefab_company_id = ?
                ORDER BY m2
            """, (_company_id,)).fetchall()
        finally:
            _conn_cat.close()

        if not _models:
            st.info("No hay modelos en el catálogo aún. Usa el formulario de abajo para añadir el primero.")
        else:
            for _m in _models:
                _mid, _mname, _mm2, _mprice, _mplabel, _mactive, _mmat, _mst, _mimgs, _mcid = _m
                _mstatus = "✅ Visible" if _mactive else "🔴 Oculto"
                _mst_label = f" · pendiente revisión" if _mst == "pendiente" else ""
                st.markdown(f"- **{_mname}** — {_mm2} m² · {_mmat} · {_mplabel or f'€{_mprice:,.0f}'} · {_mstatus}{_mst_label}")

        st.markdown("---")
        st.markdown("### ➕ Añadir nuevo modelo")
        with st.form("form_nuevo_modelo"):
            _nm_nombre = st.text_input("Nombre del modelo *")
            _col1, _col2 = st.columns(2)
            with _col1:
                _nm_m2 = st.number_input("Superficie (m²) *", min_value=20.0, step=5.0)
                _nm_hab = st.number_input("Habitaciones", min_value=1, step=1)
                _nm_ban = st.number_input("Baños", min_value=1, step=1)
            with _col2:
                _nm_mat = st.selectbox(
                    "Material",
                    ["Madera", "Hormigón", "Acero modular", "Modular acero",
                     "Mixto", "Contenedor", "PVC", "Otro"]
                )
                _nm_precio = st.number_input("Precio (€, 0 = Consultar)", min_value=0.0, step=1000.0)
                _nm_plantas = st.number_input("Plantas", min_value=1, step=1)
            _nm_desc = st.text_area("Descripción", max_chars=500)
            _nm_img = st.file_uploader("Imagen principal", type=["jpg", "jpeg", "png"])
            _nm_submit = st.form_submit_button("📤 Enviar modelo para revisión")

            if _nm_submit:
                if not _nm_nombre:
                    st.error("El nombre es obligatorio.")
                else:
                    _cid_new = st.session_state.get("prefab_company", {}).get("id", "")
                    _img_url = ""
                    if _nm_img:
                        try:
                            from modules.marketplace.utils import save_upload
                            _img_url = save_upload(_nm_img, prefix="prefab_modelo")
                        except Exception:
                            pass
                    _precio_label = (
                        f"{_nm_precio:,.0f}€" if _nm_precio > 0 else "Consultar"
                    )
                    try:
                        _cn_ins = db_conn()
                        try:
                            _cn_ins.execute("""
                                INSERT INTO prefab_catalog
                                (id, name, m2, rooms, bathrooms,
                                 floors, material, price,
                                 description, image_path,
                                 price_label, active, status,
                                 prefab_company_id)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,0,'pendiente',?)
                            """, (
                                __import__('uuid').uuid4().hex,
                                _nm_nombre, _nm_m2, int(_nm_hab),
                                int(_nm_ban), int(_nm_plantas),
                                _nm_mat, _nm_precio, _nm_desc,
                                _img_url, _precio_label, _cid_new
                            ))
                            _cn_ins.commit()
                        finally:
                            _cn_ins.close()
                        st.success(
                            "✅ Modelo enviado para revisión. "
                            "El equipo de ArchiRapid lo revisará en 24-48h."
                        )
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Error guardando modelo: {_e}")

    with tab_plan:
        st.subheader("Cambiar o renovar plan")
        _cp1, _cp2, _cp3 = st.columns(3)

        for col, plan_key in zip([_cp1, _cp2, _cp3], ["starter", "profesional", "premium"]):
            pinfo = PLANES_PREFAB[plan_key]
            with col:
                _border = "2px solid #F59E0B" if _plan == plan_key else "1px solid #334155"
                _bg = "background:rgba(245,158,11,0.05);" if _plan == plan_key else ""
                _feats = "".join(f"✅ {f}<br>" for f in pinfo["features"])
                st.markdown(f"""
<div style="border:{_border};border-radius:8px;padding:16px;margin-bottom:8px;{_bg}">
  <div style="font-size:1.1em;font-weight:700;">{pinfo['label']} — €{pinfo['precio']}/mes</div>
  <div style="color:#94A3B8;font-size:0.85em;margin-top:6px;">{_feats}</div>
</div>""", unsafe_allow_html=True)
                if _plan != plan_key and st.button(
                    f"Cambiar a {pinfo['label']}", key=f"pref_to_{plan_key}",
                    use_container_width=True,
                    type="primary" if plan_key == "premium" else "secondary"
                ):
                    _checkout_plan(plan_key, company)

        st.markdown("---")
        st.markdown("### 🌟 Destacado Premium")
        st.caption(
            "Aparece el primero en la home de ArchiRapid durante 30 días. "
            "Badge dorado visible. Notificación a compradores activos."
        )

        _dest_activo = company.get("destacado_activo", 0)
        _dest_hasta = company.get("destacado_hasta", "")

        if _dest_activo and _dest_hasta:
            st.success(f"✅ Destacado activo hasta {_dest_hasta}")
        else:
            st.info("No tienes destacado activo actualmente.")
            if st.button("⭐ Activar Destacado — 49€/mes", key="btn_destacado_prefab", type="primary"):
                _checkout_plan("destacado", company)

    with tab_datos:
        st.subheader("Datos de empresa")
        st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {company['nombre']} |
| CIF | {company.get('cif') or '—'} |
| Email | {company['email']} |
| Teléfono | {company.get('telefono') or '—'} |
| Comisión acordada | {company.get('comision_pct') or 4.0}% |
""")
        st.info("Para modificar tus datos contacta con soporte@archirapid.com")


def _checkout_plan(plan: str, company: dict):
    """Redirige a Stripe Checkout para pagar un plan."""
    PRICE_IDS = {
        "starter":     "price_starter_prefab",
        "profesional": "price_profesional_prefab",
        "premium":     "price_premium_prefab",
        "destacado":   "price_destacado_prefab_49",
        "normal":      "price_starter_prefab",
    }
    try:
        from modules.stripe_utils import _get_base_url
        import stripe, os
        _sk = os.getenv("STRIPE_SECRET_KEY") or ""
        try:
            import streamlit as _st
            _sk = _st.secrets.get("STRIPE_SECRET_KEY", _sk)
        except Exception:
            pass
        if not _sk:
            st.error("Stripe no configurado. Contacta con soporte@archirapid.com")
            return
        stripe.api_key = _sk
        _plan_info = _PLANES.get(plan, _PLANES["starter"])
        _base = _get_base_url()
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=company["email"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"ArchiRapid Prefabricadas — Plan {_plan_info['label']}"},
                    "unit_amount": _plan_info["precio"] * 100,
                },
                "quantity": 1,
            }],
            metadata={"prefab_company_id": company["id"], "plan": plan},
            success_url=f"{_base}/?page=prefabricadas&pago=ok&plan={plan}&email={company['email']}",
            cancel_url=f"{_base}/?page=prefabricadas",
        )
        st.markdown(f'<meta http-equiv="refresh" content="0; url={session.url}">', unsafe_allow_html=True)
        st.link_button(f"💳 Ir a pago — {_plan_info['label']} €{_plan_info['precio']}/mes →",
                       session.url, type="primary", use_container_width=True)
    except Exception as _ex:
        st.error(f"Error generando pago: {_ex}")
