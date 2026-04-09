# modules/prefabricadas/admin.py
# Panel de administración de empresas prefabricadas — llamado desde intranet.py
import streamlit as st
from modules.marketplace.utils import db_conn

_PLANES = {
    "starter":     {"label": "Starter",     "precio": 59,  "emoji": "🏠"},
    "profesional": {"label": "Profesional", "precio": 129, "emoji": "⭐"},
    "premium":     {"label": "Premium",     "precio": 229, "emoji": "🏆"},
    "destacado":   {"label": "Destacado",   "precio": 49,  "emoji": "🌟"},
    "cortesia":    {"label": "Cortesía",    "precio": 0,   "emoji": "🎁"},
    # aliases
    "normal":      {"label": "Starter",     "precio": 59,  "emoji": "🏠"},
}

_PLAN_FORMAT = lambda x: {
    "starter":     "🏠 Starter — 59€/mes",
    "profesional": "⭐ Profesional — 129€/mes",
    "premium":     "🏆 Premium — 229€/mes",
    "destacado":   "🌟 Destacado — 49€/mes add-on",
    "cortesia":    "🎁 Cortesía (gratuito)",
    "normal":      "🏠 Starter — 59€/mes",
}.get(x, x)


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
                status TEXT DEFAULT 'pendiente',
                is_active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Migraciones seguras para nuevas columnas
        try:
            conn.execute("ALTER TABLE prefab_companies ADD COLUMN status TEXT DEFAULT 'pendiente'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE prefab_companies ADD COLUMN is_active INTEGER DEFAULT 0")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def render_admin_prefabricadas():
    _ensure_table()
    st.header("🏠 Gestión de Empresas Prefabricadas")

    conn = db_conn()
    try:
        companies = conn.execute("""
            SELECT id, nombre, cif, email, telefono, plan, paid_until, active, created_at,
                   comision_pct, hash_contrato_comision, pdf_contrato_url
            FROM prefab_companies ORDER BY active DESC, created_at DESC
        """).fetchall()
    finally:
        conn.close()

    cols_c = ["id","nombre","cif","email","telefono","plan","paid_until","active","created_at",
              "comision_pct","hash_contrato_comision","pdf_contrato_url"]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    _n_total    = len(companies)
    _n_activas  = sum(1 for c in companies if c[7])
    _n_premium  = sum(1 for c in companies if c[5] in ("premium", "profesional") and c[7])
    _n_dest     = sum(1 for c in companies if c[5] == "destacado" and c[7])
    _mrr        = (
        sum(59  for c in companies if c[5] in ("starter", "normal") and c[7]) +
        sum(129 for c in companies if c[5] == "profesional" and c[7]) +
        sum(229 for c in companies if c[5] == "premium" and c[7]) +
        sum(49  for c in companies if c[5] == "destacado" and c[7])
    )

    _k1, _k2, _k3, _k4 = st.columns(4)
    _k1.metric("🏭 Empresas registradas", _n_total)
    _k2.metric("✅ Activas", _n_activas)
    _k3.metric("🏆 Premium/Pro", _n_premium, delta=f"+{_n_dest} destacadas")
    _k4.metric("💶 MRR estimado", f"€{_mrr}/mes")

    st.markdown("---")

    if not companies:
        st.info("No hay empresas prefabricadas registradas aún. Cuando se registren desde el portal aparecerán aquí.")

    st.caption("Gestiona el acceso, plan y fechas de cada empresa prefabricada.")

    for row in companies:
        comp = dict(zip(cols_c, row))
        _icon = "🟢" if comp["active"] else "🔴"
        _plan_info = _PLANES.get(comp["plan"] or "starter", _PLANES["starter"])
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

                # Contrato de intermediación
                _hash_c = comp.get("hash_contrato_comision", "")
                _pdf_c = comp.get("pdf_contrato_url", "")
                _comision = comp.get("comision_pct") or 4.0
                st.markdown("---")
                st.markdown("**📄 Contrato de intermediación**")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.metric("Comisión acordada", f"{_comision}%")
                with col_c2:
                    if _hash_c:
                        st.caption(f"SHA-256: {_hash_c[:20]}...")
                    else:
                        st.caption("Sin contrato generado")
                if _pdf_c:
                    st.markdown(f"[📥 Descargar contrato firmado]({_pdf_c})")
                else:
                    st.info(
                        "El contrato se genera automáticamente "
                        "cuando la empresa completa el registro."
                    )

            with _ci2:
                st.markdown("**Plan y validez**")
                _plan_opts = ["starter", "profesional", "premium", "destacado", "cortesia"]
                _plan_actual = comp["plan"] or "starter"
                if _plan_actual not in _plan_opts:
                    _plan_actual = "starter"
                _new_plan = st.selectbox(
                    "Plan", _plan_opts,
                    index=_plan_opts.index(_plan_actual),
                    format_func=_PLAN_FORMAT,
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
                st.markdown("**Gestión de estado**")
                _sb1, _sb2, _sb3, _sb4 = st.columns(4)

                with _sb1:
                    if st.button("⏳ En trámite", key=f"pref_pending_{comp['id']}", use_container_width=True):
                        _sp = db_conn()
                        _sp.execute("UPDATE prefab_companies SET status=?, is_active=0 WHERE id=?", ("pendiente", comp["id"]))
                        _sp.commit(); _sp.close()
                        st.info("En trámite")
                        st.rerun()

                with _sb2:
                    if st.button("✅ Autorizar", key=f"pref_authorized_{comp['id']}", type="primary", use_container_width=True):
                        _sa = db_conn()
                        _sa.execute("UPDATE prefab_companies SET status=?, is_active=1, active=1 WHERE id=?", ("autorizado", comp["id"]))
                        _sa.commit(); _sa.close()
                        st.success("Autorizada ✅")
                        st.rerun()

                with _sb3:
                    if st.button("🔴 Suspender", key=f"pref_suspended_{comp['id']}", use_container_width=True):
                        _ssp = db_conn()
                        _ssp.execute("UPDATE prefab_companies SET status=?, is_active=0 WHERE id=?", ("suspendido", comp["id"]))
                        _ssp.commit(); _ssp.close()
                        st.warning("Suspendida")
                        st.rerun()

                with _sb4:
                    if st.button("❌ Anular", key=f"pref_cancelled_{comp['id']}", use_container_width=True):
                        _sc = db_conn()
                        _sc.execute("UPDATE prefab_companies SET status=?, is_active=0 WHERE id=?", ("anulado", comp["id"]))
                        _sc.commit(); _sc.close()
                        st.error("Anulada")
                        st.rerun()

                st.markdown("---")
                st.markdown("**🎁 Acceso de cortesía**")
                _comp_id = comp["id"]
                _meses_cortesia = st.selectbox(
                    "Meses de cortesía",
                    [1, 2, 3, 6, 12],
                    key=f"cortesia_meses_{_comp_id}"
                )
                if st.button(
                    f"🎁 Dar {_meses_cortesia} mes(es) cortesía",
                    key=f"btn_cortesia_{_comp_id}",
                    use_container_width=True
                ):
                    from datetime import datetime, timedelta
                    _until = (
                        datetime.utcnow() + timedelta(days=30 * _meses_cortesia)
                    ).strftime("%Y-%m-%d")
                    _cn = db_conn()
                    _cn.execute("""
                        UPDATE prefab_companies
                        SET active=1, status='autorizado', is_active=1,
                            plan='cortesia', paid_until=?,
                            destacado_activo=0
                        WHERE id=?
                    """, (_until, _comp_id))
                    _cn.commit()
                    _cn.close()
                    st.success(
                        f"✅ Cortesía activada hasta {_until}. "
                        "La empresa puede acceder y publicar modelos."
                    )
                    st.rerun()

                st.markdown("---")
                _ab1, _ab2, _ab3 = st.columns(3)
                with _ab1:
                    if comp["active"]:
                        if st.button("🚫 Desactivar", key=f"btn_pref_deact_{comp['id']}",
                                     use_container_width=True):
                            _ud = db_conn()
                            _ud.execute("UPDATE prefab_companies SET active=0 WHERE id=?", (comp["id"],))
                            _ud.commit(); _ud.close()
                            st.warning("Desactivada")
                            st.rerun()
                    else:
                        if st.button("✅ Activar", key=f"btn_pref_act_{comp['id']}",
                                     type="primary", use_container_width=True):
                            _ud = db_conn()
                            _ud.execute("UPDATE prefab_companies SET active=1 WHERE id=?", (comp["id"],))
                            _ud.commit(); _ud.close()
                            st.success("Activada ✅")
                            st.rerun()
                with _ab2:
                    if st.button("⏸ Pausar", key=f"btn_pref_pause_{comp['id']}",
                                 use_container_width=True):
                        _up = db_conn()
                        _up.execute("UPDATE prefab_companies SET status=?, is_active=0 WHERE id=?", ("pausado", comp["id"]))
                        _up.commit(); _up.close()
                        st.info("Pausada")
                        st.rerun()

                with _ab3:
                    # POPOVER para eliminar
                    with st.popover("🗑️ Eliminar", use_container_width=True):
                        st.error(f"⚠️ ¿Eliminar {comp['nombre']}?")
                        st.caption("Irreversible.")
                        if st.button("❌ Sí, eliminar", key=f"btn_pref_delete_{comp['id']}",
                                     type="primary", use_container_width=True):
                            _dd = db_conn()
                            _dd.execute("DELETE FROM prefab_companies WHERE id=?", (comp["id"],))
                            _dd.commit(); _dd.close()
                            st.success("Eliminada")
                            st.rerun()

    st.markdown("---")
    _render_catalog_items()


def _render_catalog_items():
    """Gestión de los modelos del catálogo de casas prefabricadas."""
    st.markdown("### 🏘️ Catálogo de modelos prefabricados")
    st.caption("Gestiona la disponibilidad de cada modelo en el marketplace.")

    # Filtro por empresa
    _cn_f = db_conn()
    try:
        _empresas = _cn_f.execute("""
            SELECT id, nombre, email
            FROM prefab_companies
            WHERE active = 1
            ORDER BY nombre
        """).fetchall()
    finally:
        _cn_f.close()

    _empresa_opts = {"Todas las empresas": None}
    for _emp in _empresas:
        _empresa_opts[f"{_emp[1]} ({_emp[2]})"] = _emp[0]

    _filtro_emp = st.selectbox(
        "Filtrar por empresa",
        options=list(_empresa_opts.keys()),
        key="admin_prefab_filtro_empresa"
    )
    _filtro_id = _empresa_opts[_filtro_emp]

    conn = db_conn()
    try:
        # Asegurar columna status en prefab_catalog (migración idempotente)
        try:
            conn.execute("ALTER TABLE prefab_catalog ADD COLUMN status TEXT DEFAULT 'disponible'")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE prefab_catalog ADD COLUMN prefab_company_id TEXT")
            conn.commit()
        except Exception:
            pass

        if _filtro_id:
            items = conn.execute("""
                SELECT id, name, m2, rooms, bathrooms, floors, material, price,
                       active, image_path, modulos, price_label,
                       COALESCE(status, CASE WHEN active=1 THEN 'disponible' ELSE 'suspendido' END) as status,
                       prefab_company_id
                FROM prefab_catalog
                WHERE prefab_company_id = ?
                ORDER BY name
            """, (_filtro_id,)).fetchall()
        else:
            items = conn.execute("""
                SELECT id, name, m2, rooms, bathrooms, floors, material, price,
                       active, image_path, modulos, price_label,
                       COALESCE(status, CASE WHEN active=1 THEN 'disponible' ELSE 'suspendido' END) as status,
                       prefab_company_id
                FROM prefab_catalog
                ORDER BY name
            """).fetchall()
    finally:
        conn.close()

    if not items:
        st.info("No hay modelos en el catálogo todavía.")
        return

    _ITEM_STATUS_ICON = {
        "disponible": "🟢", "aprobado": "🟢",
        "pendiente": "🟡",
        "suspendido": "🔴", "no_disponible": "🔴",
        "vendida": "🔵", "vendido": "🔵",
    }

    st.markdown(f"**{len(items)} modelos en catálogo:**")

    for itm in items:
        (iid, iname, im2, irooms, ibaths, ifloors, imaterial, iprice,
         iactive, iimg, imodulos, iprice_lbl, istatus, _item_company_id) = itm

        _sicon = _ITEM_STATUS_ICON.get(istatus or "disponible", "⚪")
        _price_disp = iprice_lbl if iprice_lbl else f"€{iprice:,.0f}"

        # Nombre de empresa para el header
        _empresa_nombre = ""
        if _item_company_id:
            try:
                _cn_en = db_conn()
                try:
                    _row_en = _cn_en.execute(
                        "SELECT nombre FROM prefab_companies WHERE id=?",
                        (_item_company_id,)
                    ).fetchone()
                finally:
                    _cn_en.close()
                _empresa_nombre = f" · {_row_en[0]}" if _row_en else ""
            except Exception:
                pass

        with st.expander(
            f"{_sicon} {iname}{_empresa_nombre} — {im2} m² · {imaterial} · {_price_disp} | Estado: {istatus or 'disponible'}"
        ):
            _ic1, _ic2 = st.columns([3, 2])
            with _ic1:
                st.markdown(f"""
| Campo | Valor |
|---|---|
| Habitaciones | {irooms} |
| Baños | {ibaths} |
| Plantas | {ifloors} |
| Material | {imaterial} |
| Módulos | {imodulos or '—'} |
| Precio | {_price_disp} |
| Estado | **{istatus or 'disponible'}** |
""")
                import os as _os_pf
                if iimg and _os_pf.path.exists(iimg):
                    st.image(iimg, width=160)
                elif iimg and iimg.startswith("http"):
                    st.image(iimg, width=160)

            with _ic2:
                st.markdown("**Cambiar estado**")
                _pc1, _pc2 = st.columns(2)
                with _pc1:
                    if st.button("✅ Aprobar 🟢", key=f"cat_apr_{iid}",
                                 type="primary" if istatus in ("disponible", "aprobado") else "secondary",
                                 use_container_width=True):
                        _cu = db_conn()
                        try:
                            _cu.execute("UPDATE prefab_catalog SET status='disponible', active=1 WHERE id=?", (iid,))
                            _cu.commit()
                        finally:
                            _cu.close()
                        st.rerun()
                with _pc2:
                    if st.button("⏳ Pendiente 🟡", key=f"cat_pend_{iid}",
                                 type="primary" if istatus == "pendiente" else "secondary",
                                 use_container_width=True):
                        _cu2 = db_conn()
                        try:
                            _cu2.execute("UPDATE prefab_catalog SET status='pendiente', active=0 WHERE id=?", (iid,))
                            _cu2.commit()
                        finally:
                            _cu2.close()
                        st.rerun()

                _pc3, _pc4 = st.columns(2)
                with _pc3:
                    if st.button("🔴 Suspender", key=f"cat_susp_{iid}",
                                 type="primary" if istatus == "suspendido" else "secondary",
                                 use_container_width=True):
                        _cu3 = db_conn()
                        try:
                            _cu3.execute("UPDATE prefab_catalog SET status='suspendido', active=0 WHERE id=?", (iid,))
                            _cu3.commit()
                        finally:
                            _cu3.close()
                        st.rerun()
                with _pc4:
                    if st.button("🔵 Vendida", key=f"cat_vend_{iid}",
                                 type="primary" if istatus in ("vendida", "vendido") else "secondary",
                                 use_container_width=True,
                                 help="Marca como vendida — no disponible en marketplace"):
                        _cu4 = db_conn()
                        try:
                            _cu4.execute("UPDATE prefab_catalog SET status='vendida', active=0 WHERE id=?", (iid,))
                            _cu4.commit()
                        finally:
                            _cu4.close()
                        st.rerun()

                st.markdown("---")
                with st.popover("🗑️ Eliminar modelo", use_container_width=True):
                    st.error(f"⚠️ ¿Eliminar '{iname}'?")
                    st.caption("Irreversible.")
                    if st.button("❌ Sí, eliminar", key=f"cat_del_{iid}",
                                 type="primary", use_container_width=True):
                        _cu5 = db_conn()
                        try:
                            _cu5.execute("DELETE FROM prefab_catalog WHERE id=?", (iid,))
                            _cu5.commit()
                        finally:
                            _cu5.close()
                        st.success(f"'{iname}' eliminado")
                        st.rerun()
