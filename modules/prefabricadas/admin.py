# modules/prefabricadas/admin.py
# Panel de administración de empresas prefabricadas — llamado desde intranet.py
import streamlit as st
from modules.marketplace.utils import db_conn

_PLANES = {
    "normal":    {"label": "Normal",    "precio": 49,  "emoji": "📋"},
    "destacado": {"label": "Destacado", "precio": 149, "emoji": "⭐"},
}


def _ensure_table():
    """Crea la tabla prefab_companies si no existe (idempotente)."""
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


def render_admin_prefabricadas():
    _ensure_table()
    st.header("🏠 Gestión de Empresas Prefabricadas")

    conn = db_conn()
    try:
        companies = conn.execute("""
            SELECT id, nombre, cif, email, telefono, plan, paid_until, active, created_at
            FROM prefab_companies ORDER BY active DESC, created_at DESC
        """).fetchall()
    finally:
        conn.close()

    cols_c = ["id","nombre","cif","email","telefono","plan","paid_until","active","created_at"]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    _n_total    = len(companies)
    _n_activas  = sum(1 for c in companies if c[7])
    _n_dest     = sum(1 for c in companies if c[5] == "destacado" and c[7])
    _n_normal   = sum(1 for c in companies if c[5] == "normal" and c[7])
    _mrr        = _n_dest * 149 + _n_normal * 49

    _k1, _k2, _k3, _k4 = st.columns(4)
    _k1.metric("🏭 Empresas registradas", _n_total)
    _k2.metric("✅ Activas", _n_activas)
    _k3.metric("⭐ Plan Destacado", _n_dest, delta=f"€{_n_dest*149}/mes")
    _k4.metric("💶 MRR estimado", f"€{_mrr}/mes")

    st.markdown("---")

    if not companies:
        st.info("No hay empresas prefabricadas registradas aún. Cuando se registren desde el portal aparecerán aquí.")
        _render_add_form()
        return

    st.caption("Gestiona el acceso, plan y fechas de cada empresa prefabricada.")

    for row in companies:
        comp = dict(zip(cols_c, row))
        _icon = "🟢" if comp["active"] else "🔴"
        _plan_info = _PLANES.get(comp["plan"] or "normal", _PLANES["normal"])
        with st.expander(
            f"{_icon} {_plan_info['emoji']} {comp['nombre']} — {comp['email']} | {_plan_info['label']} €{_plan_info['precio']}/mes"
        ):
            _ci1, _ci2 = st.columns([3, 2])
            with _ci1:
                st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {comp['nombre']} |
| CIF | `{comp['cif'] or '—'}` |
| Email | {comp['email']} |
| Teléfono | {comp['telefono'] or '—'} |
| Plan | **{_plan_info['label']}** — €{_plan_info['precio']}/mes |
| Pagado hasta | {comp['paid_until'] or '—'} |
| Estado | {'✅ Activa' if comp['active'] else '🔴 Inactiva'} |
| Registro | {(comp['created_at'] or '')[:10]} |
""")
                st.markdown(f"[✉️ Contactar](mailto:{comp['email']})")

            with _ci2:
                st.markdown("**Plan y validez**")
                _new_plan = st.selectbox(
                    "Plan", list(_PLANES.keys()),
                    index=list(_PLANES.keys()).index(comp["plan"] or "normal"),
                    format_func=lambda p: f"{_PLANES[p]['emoji']} {_PLANES[p]['label']} — €{_PLANES[p]['precio']}/mes",
                    key=f"pref_plan_{comp['id']}"
                )
                _new_until = st.text_input(
                    "Pagado hasta (YYYY-MM-DD)",
                    value=comp["paid_until"] or "",
                    key=f"pref_until_{comp['id']}",
                    placeholder="2026-12-31"
                )
                if st.button("💾 Guardar plan", key=f"pref_save_{comp['id']}",
                             type="primary", use_container_width=True):
                    _upd = db_conn()
                    _upd.execute(
                        "UPDATE prefab_companies SET plan=?, paid_until=? WHERE id=?",
                        (_new_plan, _new_until or None, comp["id"])
                    )
                    _upd.commit(); _upd.close()
                    st.success("Plan actualizado ✅"); st.rerun()

                st.markdown("---")
                _ab1, _ab2 = st.columns(2)
                with _ab1:
                    if comp["active"]:
                        if st.button("🚫 Desactivar", key=f"pref_deact_{comp['id']}",
                                     use_container_width=True):
                            _ud = db_conn()
                            _ud.execute("UPDATE prefab_companies SET active=0 WHERE id=?", (comp["id"],))
                            _ud.commit(); _ud.close()
                            st.warning("Desactivada"); st.rerun()
                    else:
                        if st.button("✅ Activar", key=f"pref_act_{comp['id']}",
                                     type="primary", use_container_width=True):
                            _ud = db_conn()
                            _ud.execute("UPDATE prefab_companies SET active=1 WHERE id=?", (comp["id"],))
                            _ud.commit(); _ud.close()
                            st.success("Activada ✅"); st.rerun()
                with _ab2:
                    if st.button("🗑️ Eliminar", key=f"pref_del_{comp['id']}",
                                 use_container_width=True, type="secondary"):
                        st.session_state[f"pref_del_confirm_{comp['id']}"] = True

                if st.session_state.get(f"pref_del_confirm_{comp['id']}"):
                    st.error(f"¿Eliminar {comp['nombre']}? Irreversible.")
                    _dc1, _dc2 = st.columns(2)
                    with _dc1:
                        if st.button("❌ Sí", key=f"pref_del_yes_{comp['id']}",
                                     type="primary", use_container_width=True):
                            _dd = db_conn()
                            _dd.execute("DELETE FROM prefab_companies WHERE id=?", (comp["id"],))
                            _dd.commit(); _dd.close()
                            st.session_state.pop(f"pref_del_confirm_{comp['id']}", None)
                            st.success("Eliminada"); st.rerun()
                    with _dc2:
                        if st.button("↩️ Cancelar", key=f"pref_del_no_{comp['id']}",
                                     use_container_width=True):
                            st.session_state.pop(f"pref_del_confirm_{comp['id']}", None)
                            st.rerun()

    st.markdown("---")
    _render_add_form()


def _render_add_form():
    """Formulario para añadir empresa manualmente desde admin."""
    st.markdown("### ➕ Añadir empresa prefabricada manualmente")
    with st.form("add_prefab_company"):
        _fc1, _fc2 = st.columns(2)
        with _fc1:
            _fn = st.text_input("Nombre empresa *")
            _fe = st.text_input("Email *")
            _fcif = st.text_input("CIF")
        with _fc2:
            _ft = st.text_input("Teléfono")
            _fp = st.selectbox("Plan inicial", list(_PLANES.keys()),
                               format_func=lambda p: f"{_PLANES[p]['emoji']} {_PLANES[p]['label']}")
            _fu = st.text_input("Pagado hasta (YYYY-MM-DD)", placeholder="2026-12-31")
        _fa = st.checkbox("Activar inmediatamente", value=True)
        if st.form_submit_button("➕ Añadir empresa", type="primary"):
            if _fn and _fe:
                import uuid
                _nid = uuid.uuid4().hex
                _ac = db_conn()
                try:
                    _ac.execute(
                        """INSERT INTO prefab_companies
                           (id, nombre, cif, email, telefono, plan, paid_until, active)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (_nid, _fn, _fcif or None, _fe, _ft or None, _fp, _fu or None, int(_fa))
                    )
                    _ac.commit()
                    st.success(f"✅ Empresa '{_fn}' añadida.")
                    st.rerun()
                except Exception as _ex:
                    st.error(f"Error: {_ex}")
                finally:
                    _ac.close()
            else:
                st.error("Nombre y email son obligatorios.")
