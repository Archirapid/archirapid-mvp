# modules/prefabricadas/portal.py
# Portal de empresa prefabricada: registro, login, dashboard, pago de planes
import streamlit as st
import hashlib
import uuid
from modules.marketplace.utils import db_conn

_PLANES = {
    "normal":    {"label": "Normal",    "precio": 49,  "emoji": "📋",
                  "descripcion": "Listado en catálogo + ficha propia"},
    "destacado": {"label": "Destacado", "precio": 149, "emoji": "⭐",
                  "descripcion": "Badge destacado + primero en home + aparece en panel del comprador"},
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
                plan TEXT DEFAULT 'normal',
                paid_until TEXT,
                active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _get_company(email: str):
    conn = db_conn()
    try:
        row = conn.execute(
            "SELECT id,nombre,cif,email,telefono,plan,paid_until,active FROM prefab_companies WHERE email=?",
            (email,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return dict(zip(["id","nombre","cif","email","telefono","plan","paid_until","active"], row))


def main():
    _ensure_table()

    # Estado de sesión
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

        with st.form("pref_register_form"):
            _rc1, _rc2 = st.columns(2)
            with _rc1:
                _rn  = st.text_input("Nombre empresa *")
                _re  = st.text_input("Email corporativo *")
                _rcif = st.text_input("CIF")
            with _rc2:
                _rt  = st.text_input("Teléfono")
                _rpw = st.text_input("Contraseña *", type="password")
                _rpw2 = st.text_input("Repetir contraseña *", type="password")

            # Planes
            st.markdown("**Elige tu plan:**")
            _pc1, _pc2 = st.columns(2)
            with _pc1:
                st.markdown(f"""
<div style="border:1px solid #334155;border-radius:8px;padding:12px;">
  <div style="font-size:1.1em;font-weight:700;">📋 Plan Normal — €49/mes</div>
  <div style="color:#94A3B8;font-size:0.85em;margin-top:4px;">
    ✅ Listado en catálogo<br>
    ✅ Ficha propia con fotos<br>
    ✅ Apareces en resultados de búsqueda
  </div>
</div>""", unsafe_allow_html=True)
            with _pc2:
                st.markdown(f"""
<div style="border:2px solid #F59E0B;border-radius:8px;padding:12px;background:rgba(245,158,11,0.05);">
  <div style="font-size:1.1em;font-weight:700;">⭐ Plan Destacado — €149/mes</div>
  <div style="color:#94A3B8;font-size:0.85em;margin-top:4px;">
    ✅ Todo lo del plan Normal<br>
    ✅ Badge destacado visible<br>
    ✅ Primero en home y marketplace<br>
    ✅ Apareces en panel del comprador al elegir finca
  </div>
</div>""", unsafe_allow_html=True)

            _rplan = st.radio("Plan seleccionado", list(_PLANES.keys()),
                              format_func=lambda p: f"{_PLANES[p]['emoji']} {_PLANES[p]['label']} — €{_PLANES[p]['precio']}/mes",
                              horizontal=True, key="pref_reg_plan")

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
                                   (id,nombre,cif,email,telefono,password_hash,plan,active)
                                   VALUES (?,?,?,?,?,?,?,0)""",
                                (_new_id, _rn, _rcif or None, _re, _rt or None, _hash_pw(_rpw), _rplan)
                            )
                            _conn_reg.commit()
                            st.success(
                                "✅ Solicitud enviada. El equipo de ArchiRapid revisará tu cuenta "
                                "y te avisará por email en menos de 24h."
                            )
                            # Notificar admin via Telegram si está configurado
                            try:
                                from modules.marketplace.email_notify import _send
                                _send(f"🏠 Nueva empresa prefabricada solicita acceso:\n{_rn} ({_re})\nPlan: {_rplan}")
                            except Exception:
                                pass
                        except Exception as _ex:
                            st.error(f"Error en registro: {_ex}")
                        finally:
                            _conn_reg.close()


def _render_dashboard(company: dict):
    """Dashboard para empresa prefabricada autenticada."""
    st.title(f"🏠 {company['nombre']}")

    _co1, _co2 = st.columns([5, 1])
    with _co1:
        _plan_info = _PLANES.get(company.get("plan") or "normal", _PLANES["normal"])
        st.caption(f"Plan: {_plan_info['emoji']} **{_plan_info['label']}** | Email: {company['email']}")
    with _co2:
        if st.button("🚪 Salir", key="pref_logout"):
            st.session_state.pop("prefab_company", None)
            st.rerun()

    # Banner estado plan
    _plan = company.get("plan") or "normal"
    _paid_until = company.get("paid_until")
    if _plan == "destacado":
        st.success(f"⭐ Plan Destacado activo — válido hasta: {_paid_until or 'indefinido'}")
    else:
        st.info(f"📋 Plan Normal activo — válido hasta: {_paid_until or 'indefinido'}")

    tab_catalogo, tab_plan, tab_datos = st.tabs(["🏭 Mis modelos", "💳 Mi plan", "📋 Mis datos"])

    with tab_catalogo:
        st.subheader("Modelos en el catálogo")
        _conn_cat = db_conn()
        try:
            _models = _conn_cat.execute(
                "SELECT id, name, m2, price, price_label, active, material FROM prefab_catalog ORDER BY m2"
            ).fetchall()
        finally:
            _conn_cat.close()

        if not _models:
            st.info("No hay modelos en el catálogo aún. El equipo de ArchiRapid los añadirá por ti.")
        else:
            for _m in _models:
                _mid, _mname, _mm2, _mprice, _mplabel, _mactive, _mmat = _m
                _mstatus = "✅ Visible" if _mactive else "🔴 Oculto"
                st.markdown(f"- **{_mname}** — {_mm2} m² · {_mmat} · {_mplabel or f'€{_mprice:,.0f}'} · {_mstatus}")

        st.info("Para modificar modelos, añadir fotos o cambiar precios contacta con soporte@archirapid.com")

    with tab_plan:
        st.subheader("Cambiar o renovar plan")
        _cp1, _cp2 = st.columns(2)
        with _cp1:
            _border_n = "2px solid #F59E0B" if _plan == "normal" else "1px solid #334155"
            st.markdown(f"""
<div style="border:{_border_n};border-radius:8px;padding:16px;margin-bottom:8px;">
  <div style="font-size:1.1em;font-weight:700;">📋 Plan Normal — €49/mes</div>
  <div style="color:#94A3B8;font-size:0.85em;margin-top:6px;">
    ✅ Listado en catálogo · ✅ Ficha propia
  </div>
</div>""", unsafe_allow_html=True)
            if _plan != "normal" and st.button("Cambiar a Normal", key="pref_to_normal",
                                                use_container_width=True):
                _checkout_plan("normal", company)

        with _cp2:
            _border_d = "2px solid #F59E0B" if _plan == "destacado" else "1px solid #334155"
            st.markdown(f"""
<div style="border:{_border_d};border-radius:8px;padding:16px;background:rgba(245,158,11,0.05);">
  <div style="font-size:1.1em;font-weight:700;">⭐ Plan Destacado — €149/mes</div>
  <div style="color:#94A3B8;font-size:0.85em;margin-top:6px;">
    ✅ Todo Normal · ✅ Badge · ✅ Primero en home · ✅ Panel comprador
  </div>
</div>""", unsafe_allow_html=True)
            if _plan != "destacado" and st.button("⭐ Upgrade a Destacado", key="pref_to_dest",
                                                   type="primary", use_container_width=True):
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
""")
        st.info("Para modificar tus datos contacta con soporte@archirapid.com")


def _checkout_plan(plan: str, company: dict):
    """Redirige a Stripe Checkout para pagar un plan."""
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
        _plan_info = _PLANES[plan]
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
            success_url=f"{_base}/?page=prefabricadas&pago=ok&plan={plan}",
            cancel_url=f"{_base}/?page=prefabricadas",
        )
        st.markdown(f'<meta http-equiv="refresh" content="0; url={session.url}">', unsafe_allow_html=True)
        st.link_button(f"💳 Ir a pago — {_plan_info['label']} €{_plan_info['precio']}/mes →",
                       session.url, type="primary", use_container_width=True)
    except Exception as _ex:
        st.error(f"Error generando pago: {_ex}")
