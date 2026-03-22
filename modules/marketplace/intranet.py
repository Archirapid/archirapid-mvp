# modules/marketplace/intranet.py - GESTIÓN INTERNA DE LA EMPRESA
import streamlit as st
from modules.marketplace.utils import db_conn, list_published_plots, list_projects
import json

def main():
    st.title("🔐 Intranet — Gestión Interna de ARCHIRAPID")

    # Verificar si ya está logueado como admin
    if st.session_state.get("rol") == "admin":
        st.success("✅ Acceso autorizado a Intranet (sesión activa)")
    else:
        # SOLO ACCESO CON CONTRASEÑA DE ADMIN
        password = st.text_input("Contraseña de Acceso Administrativo", type="password")
        _admin_pw = None
        try:
            _admin_pw = st.secrets.get("ADMIN_PASSWORD", "admin123")
        except Exception:
            _admin_pw = "admin123"
        if password != _admin_pw:
            if password:  # solo mostrar warning si ya escribió algo
                st.warning("🔒 Contraseña incorrecta.")
            else:
                st.info("🔒 Acceso restringido. Solo personal autorizado de ARCHIRAPID.")
            return
        st.session_state["rol"] = "admin"
        st.rerun()

    # PANEL DE GESTIÓN INTERNA
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(["📋 Gestión de Fincas", "🏗️ Gestión de Proyectos", "💰 Ventas y Transacciones", "📞 Consultas", "🛠️ Profesionales", "⚙️ Admin", "🎯 Waitlist", "📬 Actividad", "📊 Analytics", "🏢 MLS — Inmobiliarias"])

    with tab1:
        try:
            st.header("Gestión de Fincas Publicadas")
            plots = list_published_plots()
            if plots:
                for p in plots:
                    with st.expander(f"Finca: {p['title']}"):
                        st.write(f"**ID:** {p['id']}")
                        st.write(f"**Superficie:** {p['surface_m2']} m²")
                        st.write(f"**Precio:** €{p['price']}")
                        st.write(f"**Status:** {p.get('status', 'Pendiente')}")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button(f"Aprobar {p['id']}", key=f"approve_plot_{p['id']}"):
                                st.success("Finca aprobada (Admin)")
                        with col2:
                            if st.button(f"Rechazar {p['id']}", key=f"reject_plot_{p['id']}"):
                                st.info("Funcionalidad próximamente")
                        with col3:
                            if st.button(f"📢 Alertar suscriptores", key=f"alert_plot_{p['id']}"):
                                try:
                                    from modules.marketplace.alertas import notify_new_plot
                                    n = notify_new_plot(dict(p))
                                    if n > 0:
                                        st.success(f"✅ {n} email(s) enviados.")
                                    else:
                                        st.info("Sin suscriptores coincidentes o RESEND_API_KEY no configurada.")
                                except Exception as _ae:
                                    st.error(f"Error alertas: {_ae}")

                        # ── Tour 360° ──────────────────────────────────────────
                        st.markdown("---")
                        _has_360 = bool(p.get("tour_360_b64", ""))
                        st.markdown(
                            f"**🔭 Tour Virtual 360°:** {'✅ Activo' if _has_360 else '⬜ Sin tour'}"
                        )
                        _up360 = st.file_uploader(
                            "Subir foto equirectangular (JPG/PNG — cualquier móvil en modo 360°)",
                            type=["jpg", "jpeg", "png"],
                            key=f"tour360_{p['id']}"
                        )
                        if _up360:
                            try:
                                import io as _io360
                                import base64 as _b64mod
                                from PIL import Image as _PIL360
                                _img = _PIL360.open(_up360).convert("RGB")
                                if _img.width > 2048:
                                    _ratio = 2048 / _img.width
                                    _img = _img.resize(
                                        (2048, int(_img.height * _ratio)),
                                        _PIL360.Resampling.LANCZOS
                                    )
                                _buf360 = _io360.BytesIO()
                                _img.save(_buf360, format="JPEG", quality=82)
                                _b64_val = _b64mod.b64encode(_buf360.getvalue()).decode()
                                _conn360 = db_conn()
                                try:
                                    _conn360.execute("ALTER TABLE plots ADD COLUMN tour_360_b64 TEXT")
                                    _conn360.commit()
                                except Exception:
                                    pass  # columna ya existe
                                _conn360.execute(
                                    "UPDATE plots SET tour_360_b64=? WHERE id=?",
                                    (_b64_val, p["id"])
                                )
                                _conn360.commit()
                                _conn360.close()
                                st.success("✅ Tour 360° guardado. Recarga la página para verlo activo.")
                            except Exception as _e360:
                                st.error(f"Error guardando tour 360°: {_e360}")
            else:
                st.info("No hay fincas publicadas")
        except Exception as e:
            st.error(f"Error en Gestión de Fincas: {e}")

    with tab2:
        try:
            st.header("Gestión de Proyectos Arquitectónicos")
            projects = list_projects()
            if projects:
                for proj in projects:
                    with st.expander(f"Proyecto: {proj['title']}"):
                        # Imagen principal o fallback
                        img_path = proj['foto_principal'] if proj['foto_principal'] else "assets/fincas/image1.jpg"
                        st.image(img_path, width=120, caption="Imagen principal")
                        st.write(f"**Arquitecto:** {proj['architect_name']}")
                        st.write(f"**Precio:** €{proj['price']}")
                        st.write(f"**Área:** {proj['area_m2']} m²")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Aprobar Proyecto {proj['id']}", key=f"approve_proj_{proj['id']}"):
                                st.success("Proyecto aprobado (Admin)")
                        with col2:
                            if st.button(f"Rechazar Proyecto {proj['id']}", key=f"reject_proj_{proj['id']}"):
                                st.info("Funcionalidad próximamente")
            else:
                st.info("Próximamente. No hay proyectos.")
        except Exception as e:
            st.error(f"Error en Gestión de Proyectos: {e}")

    with tab3:
        st.header("💰 Ventas y Transacciones — Todos los flujos")
        import sqlite3 as _sq3, pandas as _pd3

        def _read3(conn, sql):
            cur = conn.execute(sql)
            rows = cur.fetchall()
            if not rows:
                return _pd3.DataFrame()
            cols = [d[0] for d in (cur.description or [])]
            data = []
            for r in rows:
                try:
                    data.append([r[i] for i in range(len(cols))])
                except Exception:
                    data.append([r[c] for c in cols])
            return _pd3.DataFrame(data, columns=cols)

        # ── KPIs de ingresos ──────────────────────────────────────────────────
        try:
            _db3 = db_conn()

            _rev_fincas = float(_db3.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()[0])
            _n_res3     = _db3.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]

            _n_subs, _mrr = 0, 0.0
            try:
                _subs_row = _db3.execute(
                    "SELECT COUNT(*), COALESCE(SUM(price),0) FROM subscriptions WHERE status='active'"
                ).fetchone()
                _n_subs, _mrr = int(_subs_row[0]), float(_subs_row[1])
            except Exception:
                pass

            _n_ai_proj = 0
            try:
                _n_ai_proj = _db3.execute("SELECT COUNT(*) FROM ai_projects").fetchone()[0]
            except Exception:
                pass

            _n_estudio = 0
            try:
                _n_estudio = _db3.execute("SELECT COUNT(*) FROM estudio_projects").fetchone()[0]
            except Exception:
                pass

            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("🏡 Ingresos fincas", f"€{_rev_fincas:,.0f}", delta=f"{_n_res3} operaciones")
            _k2.metric("💎 Suscripciones activas", _n_subs, delta=f"MRR €{_mrr:,.0f}")
            _k3.metric("🏠 Proyectos AI pagados", _n_ai_proj)
            _k4.metric("🎨 Proyectos Modo Estudio", _n_estudio)
            _db3.close()
        except Exception as _ek3:
            st.warning(f"Error KPIs: {_ek3}")

        st.markdown("---")

        # ── 1. Reservas y compras de fincas ──────────────────────────────────
        st.subheader("🏡 Reservas y Compras de Fincas")
        try:
            _db3b = db_conn()
            _df_res3 = _read3(
                _db3b,
                """SELECT r.id, r.buyer_name, r.buyer_email, p.title as finca,
                          r.amount, r.kind, r.created_at
                   FROM reservations r LEFT JOIN plots p ON r.plot_id=p.id
                   ORDER BY r.created_at DESC"""
            )
            _db3b.close()
            if not _df_res3.empty:
                _df_res3["kind"] = _df_res3["kind"].map(
                    {"purchase": "Compra", "reservation": "Reserva"}
                ).fillna(_df_res3["kind"])
                st.dataframe(
                    _df_res3.rename(columns={
                        "id": "ID", "buyer_name": "Comprador", "buyer_email": "Email",
                        "finca": "Finca", "amount": "Importe (€)", "kind": "Tipo", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin reservas ni compras todavía.")
        except Exception as _er3:
            st.error(f"Error reservas: {_er3}")

        st.markdown("---")

        # ── 2. Suscripciones de Arquitectos ──────────────────────────────────
        st.subheader("💎 Suscripciones de Arquitectos (Planes BASIC / PRO / ENTERPRISE)")
        try:
            _db3c = db_conn()
            _df_subs = _read3(
                _db3c,
                """SELECT s.id, COALESCE(a.name, u.name) as arquitecto,
                          COALESCE(a.email, u.email) as email,
                          s.plan_type as plan, s.price as precio_mes,
                          s.monthly_proposals_limit as limite,
                          s.commission_rate as comision,
                          s.status, s.start_date, s.end_date
                   FROM subscriptions s
                   LEFT JOIN architects a ON s.architect_id = a.id
                   LEFT JOIN users u ON s.architect_id = u.id
                   ORDER BY s.created_at DESC"""
            )
            _db3c.close()
            if not _df_subs.empty:
                _df_subs["precio_mes"] = _df_subs["precio_mes"].apply(lambda x: f"€{x:,.0f}/mes")
                _df_subs["comision"]   = _df_subs["comision"].apply(lambda x: f"{x}%")
                st.dataframe(
                    _df_subs.rename(columns={
                        "id": "Sub ID", "arquitecto": "Arquitecto", "email": "Email",
                        "plan": "Plan", "precio_mes": "Precio", "limite": "Proyectos",
                        "comision": "Comisión", "status": "Estado",
                        "start_date": "Inicio", "end_date": "Vencimiento"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin suscripciones activas todavía.")
        except Exception as _es3:
            st.error(f"Error suscripciones: {_es3}")

        st.markdown("---")

        # ── 3. Proyectos AI Designer pagados ─────────────────────────────────
        st.subheader("🏠 Proyectos AI Designer — Pagos Realizados")
        try:
            _db3d = db_conn()
            _df_ai = _read3(
                _db3d,
                """SELECT client_email, project_name, total_area, total_cost,
                          style, energy_label, status, created_at
                   FROM ai_projects ORDER BY created_at DESC"""
            )
            _db3d.close()
            if not _df_ai.empty:
                _df_ai["total_cost"] = _df_ai["total_cost"].apply(lambda x: f"€{x:,.0f}")
                _df_ai["total_area"] = _df_ai["total_area"].apply(lambda x: f"{x:.0f} m²")
                st.dataframe(
                    _df_ai.rename(columns={
                        "client_email": "Email cliente", "project_name": "Proyecto",
                        "total_area": "Superficie", "total_cost": "Coste total",
                        "style": "Estilo", "energy_label": "Energía",
                        "status": "Estado", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin proyectos AI Designer pagados todavía.")
        except Exception as _eai3:
            st.error(f"Error proyectos AI: {_eai3}")

        st.markdown("---")

        # ── 4. Proyectos Modo Estudio ─────────────────────────────────────────
        st.subheader("🎨 Proyectos Modo Estudio — Arquitectos")
        try:
            _db3e = db_conn()
            _df_est = _read3(
                _db3e,
                """SELECT ep.architect_id,
                          COALESCE(a.name, u.name) as arquitecto,
                          COALESCE(a.email, u.email) as email,
                          ep.address, ep.surface_m2, ep.style, ep.budget,
                          ep.total_cost, ep.paid, ep.created_at
                   FROM estudio_projects ep
                   LEFT JOIN architects a ON ep.architect_id = a.id
                   LEFT JOIN users u ON ep.architect_id = u.id
                   ORDER BY ep.created_at DESC"""
            )
            _db3e.close()
            if not _df_est.empty:
                _df_est["paid"]       = _df_est["paid"].map({1: "✅ Pagado", 0: "⏳ Pendiente"})
                _df_est["budget"]     = _df_est["budget"].apply(lambda x: f"€{x:,.0f}" if x else "—")
                _df_est["total_cost"] = _df_est["total_cost"].apply(lambda x: f"€{x:,.0f}" if x else "—")
                _df_est["surface_m2"] = _df_est["surface_m2"].apply(lambda x: f"{x:.0f} m²" if x else "—")
                st.dataframe(
                    _df_est.rename(columns={
                        "arquitecto": "Arquitecto", "email": "Email",
                        "address": "Dirección", "surface_m2": "Superficie",
                        "style": "Estilo", "budget": "Presupuesto",
                        "total_cost": "Coste generado", "paid": "Pago", "created_at": "Fecha"
                    }).drop(columns=["architect_id"], errors="ignore"),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin proyectos Modo Estudio todavía.")
        except Exception as _ee3:
            st.error(f"Error proyectos estudio: {_ee3}")

        st.markdown("---")

        # ── 5. Stripe — Todos los pagos ───────────────────────────────────────
        st.subheader("💳 Stripe — Todos los pagos (tiempo real)")
        try:
            from modules.stripe_utils import list_recent_sessions as _lrs3
            _stripe_all = _lrs3(limit=100)
            _rows3 = []
            for _ss3 in _stripe_all.data:
                _meta3 = _ss3.metadata or {}
                _rows3.append({
                    "Fecha":      _pd3.to_datetime(_ss3.created, unit="s").strftime("%d/%m/%Y %H:%M"),
                    "Email":      _ss3.customer_email or _meta3.get("client_email", "—"),
                    "Concepto":   _meta3.get("products", _meta3.get("mode", _meta3.get("project", "—"))),
                    "Importe (€)": (_ss3.amount_total or 0) / 100,
                    "Estado":     "✅ Pagado" if _ss3.payment_status == "paid" else "⏳ Pendiente",
                    "Session ID": _ss3.id[-20:],
                })
            if _rows3:
                _df_st3 = _pd3.DataFrame(_rows3)
                _paid3  = _df_st3[_df_st3["Estado"] == "✅ Pagado"]["Importe (€)"].sum()
                _sc1, _sc2 = st.columns(2)
                _sc1.metric("💶 Total cobrado (Stripe)", f"€{_paid3:,.2f}")
                _sc2.metric("🧾 Sesiones totales", len(_rows3))
                st.dataframe(_df_st3, use_container_width=True, hide_index=True)
            else:
                st.info("Sin sesiones Stripe todavía. Usa tarjeta 4242 4242 4242 4242 para test.")
        except Exception as _est3:
            st.warning(f"Stripe no disponible: {_est3}")

    with tab4:
        try:
            st.header("Consultas y Soporte")
            st.info("📊 Módulo de analítica en preparación. Próximamente verás aquí el flujo de caja.")
            st.info("Próximamente. Panel de consultas y soporte.")
        except Exception as e:
            st.error(f"Error en Consultas y Soporte: {e}")

    with tab5:
        try:
            st.header("🛠️ Gestión de Profesionales / Constructores")

            _conn5 = db_conn()
            # Añadir columnas si no existen
            for _col, _def in [("is_featured","INTEGER DEFAULT 0"),
                                ("featured_until","TEXT"),
                                ("featured_plan","TEXT DEFAULT 'free'")]:
                try:
                    _conn5.execute(f"ALTER TABLE service_providers ADD COLUMN {_col} {_def}")
                    _conn5.commit()
                except Exception:
                    try:
                        _conn5.rollback()
                    except Exception:
                        pass

            _providers5 = _conn5.execute("""
                SELECT id, name, email, company, specialty, experience_years,
                       service_area, is_featured, featured_until, featured_plan,
                       created_at
                FROM service_providers ORDER BY is_featured DESC, name
            """).fetchall()
            _conn5.close()

            if not _providers5:
                st.info("No hay profesionales registrados aún.")
            else:
                # KPIs
                _n_feat = sum(1 for p in _providers5 if p[7])
                _n_free = len(_providers5) - _n_feat
                _k1, _k2, _k3 = st.columns(3)
                _k1.metric("👷 Total constructores", len(_providers5))
                _k2.metric("⭐ Destacados (€99/mes)", _n_feat,
                           delta=f"€{_n_feat*99}/mes MRR")
                _k3.metric("🆓 Plan gratuito", _n_free)

                st.markdown("---")
                st.markdown("**Gestionar planes Destacado:**")

                for _p5 in _providers5:
                    (_pid5, _name5, _email5, _comp5, _spec5, _exp5,
                     _area5, _feat5, _funtil5, _fplan5, _cat5) = _p5
                    _badge = "⭐ DESTACADO" if _feat5 else "🆓 Gratuito"
                    with st.expander(f"{_badge} · {_name5} ({_email5}) — {_area5}"):
                        _ci1, _ci2 = st.columns(2)
                        with _ci1:
                            st.markdown(f"""
<div style="font-size:12px;color:#CBD5E1;line-height:1.9;">
  <b>Empresa:</b> {_comp5 or '—'}<br>
  <b>Especialidad:</b> {_spec5 or '—'}<br>
  <b>Experiencia:</b> {_exp5} años<br>
  <b>Zona:</b> {_area5 or '—'}<br>
  <b>Plan solicitado:</b> {_fplan5 or 'free'}<br>
  <b>Registrado:</b> {(_cat5 or '')[:10]}
</div>""", unsafe_allow_html=True)
                        with _ci2:
                            _new_feat = st.checkbox(
                                "⭐ Activar/desactivar Destacado",
                                value=bool(_feat5),
                                key=f"feat_{_pid5}"
                            )
                            _new_until = st.text_input(
                                "Válido hasta (YYYY-MM-DD)",
                                value=_funtil5 or "",
                                key=f"until_{_pid5}",
                                placeholder="2026-04-09"
                            )
                            if st.button(f"💾 Guardar plan", key=f"savefeat_{_pid5}",
                                         type="primary", use_container_width=True):
                                _conn_upd = db_conn()
                                _conn_upd.execute(
                                    "UPDATE service_providers SET is_featured=?, featured_until=? WHERE id=?",
                                    (int(_new_feat), _new_until or None, _pid5)
                                )
                                _conn_upd.commit(); _conn_upd.close()
                                # Notificar al constructor
                                try:
                                    from modules.marketplace.email_notify import _send
                                    _status = "ACTIVADO ⭐" if _new_feat else "desactivado"
                                    _send(f"⭐ <b>Plan Destacado {_status}</b>\n{_name5} ({_email5})\nVálido hasta: {_new_until or 'indefinido'}")
                                except Exception:
                                    pass
                                st.success(f"✅ Plan de {_name5} actualizado.")
                                st.rerun()

        except Exception as e:
            st.error(f"Error en Gestión de Profesionales: {e}")

    with tab6:
        st.header("⚙️ Herramientas de Administración")
        st.warning("Estas acciones afectan a datos reales. Úsalas solo si sabes lo que haces.")

        st.subheader("🔄 Resincronización Total")
        st.write("Elimina todas las reservas bloqueadas, resetea fincas a 'disponible' y limpia la caché de Streamlit.")
        if st.button("🚨 FORZAR RESINCRONIZACIÓN TOTAL", type="primary"):
            try:
                import sqlite3
                from modules.marketplace.utils import DB_PATH
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()
                cur.execute("DELETE FROM reservations")
                cur.execute("UPDATE plots SET status = 'disponible'")
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("✅ Resincronización completada. Todas las fincas disponibles y caché limpia.")
                st.rerun()
            except Exception as e:
                st.error(f"Error en resincronización: {e}")

        st.markdown("---")
        st.subheader("🏠 Gestión Catálogo de Prefabricadas")

        try:
            from modules.marketplace.utils import db_conn as _db_conn
            import os as _os, json as _json, pathlib as _pl

            _MATERIALS = ["Madera","Modular acero","Contenedor","Hormigón prefab","Mixto"]

            def _save_prefab_photos(pf_id, uploaded_files, existing_paths):
                """Guarda hasta 3 fotos y devuelve lista de rutas."""
                paths = list(existing_paths)
                _dest_dir = _pl.Path("uploads/prefab")
                _dest_dir.mkdir(parents=True, exist_ok=True)
                for i, uf in enumerate(uploaded_files):
                    if uf is not None:
                        _dest = _dest_dir / f"prefab_{pf_id}_img{i+1}_{uf.name}"
                        with open(_dest, "wb") as _fh:
                            _fh.write(uf.read())
                        slot = i
                        if slot < len(paths):
                            paths[slot] = str(_dest)
                        else:
                            paths.append(str(_dest))
                return paths[:3]

            # Listar modelos actuales
            _conn = _db_conn()
            _cur = _conn.cursor()
            _cur.execute("""
                SELECT id, name, m2, rooms, bathrooms, floors, material, price, active,
                       image_path, image_paths, modulos, price_label
                FROM prefab_catalog ORDER BY m2
            """)
            prefabs = _cur.fetchall()
            _conn.close()

            st.markdown(f"**{len(prefabs)} modelos en catálogo:**")

            for pf in prefabs:
                pf_id, name, m2, rooms, bathrooms, floors, material, price, active, \
                    image_path, image_paths_json, modulos, price_label = pf

                # Parsear fotos existentes
                try:
                    existing_photos = _json.loads(image_paths_json) if image_paths_json else []
                except Exception:
                    existing_photos = [image_path] if image_path else []

                price_display = price_label if price_label else f"€{price:,.0f}"
                with st.expander(f"{'✅' if active else '🔴'} [{pf_id}] {name} — {m2} m² · {material} · {price_display}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        new_name     = st.text_input("Nombre",        value=name,       key=f"pf_name_{pf_id}")
                        new_m2       = st.number_input("m²",          value=float(m2),  key=f"pf_m2_{pf_id}", min_value=10.0, step=5.0)
                        new_price    = st.number_input("Precio numérico (€)", value=float(price or 0), key=f"pf_price_{pf_id}", min_value=0.0, step=1000.0)
                        new_price_lbl= st.text_input("Precio texto (ej: Consultar)", value=price_label or "", key=f"pf_plabel_{pf_id}", help="Si rellenas esto, se muestra en lugar del precio numérico")
                        new_rooms    = st.number_input("Habitaciones", value=int(rooms), key=f"pf_rooms_{pf_id}", min_value=1, max_value=10)
                        new_baths    = st.number_input("Baños",        value=int(bathrooms), key=f"pf_baths_{pf_id}", min_value=1, max_value=6)
                        new_floors   = st.number_input("Plantas",      value=int(floors), key=f"pf_floors_{pf_id}", min_value=1, max_value=4)
                        new_modulos  = st.text_input("Módulos",        value=modulos or "", key=f"pf_mod_{pf_id}", help="Nº o descripción de módulos (ej: 2 módulos 6x3m)")
                        new_material = st.selectbox("Material", _MATERIALS,
                                                    index=_MATERIALS.index(material) if material in _MATERIALS else 0,
                                                    key=f"pf_mat_{pf_id}")
                        new_active   = st.checkbox("Activo (visible en catálogo)", value=bool(active), key=f"pf_active_{pf_id}")
                    with c2:
                        st.markdown("**Fotos actuales:**")
                        for _pi, _pp in enumerate(existing_photos):
                            if _pp and _os.path.exists(_pp):
                                st.image(_pp, width=130, caption=f"Foto {_pi+1}")
                            else:
                                st.caption(f"Foto {_pi+1}: no encontrada")
                        st.markdown("**Subir fotos (máx. 3):**")
                        new_imgs_raw = st.file_uploader(
                            "Selecciona hasta 3 fotos",
                            type=["jpg","jpeg","png","webp"],
                            accept_multiple_files=True,
                            key=f"pf_imgs_{pf_id}"
                        )
                        new_imgs = list(new_imgs_raw)[:3] if new_imgs_raw else []
                        # Rellena con None hasta tener 3 slots
                        new_imgs += [None] * (3 - len(new_imgs))

                    if st.button(f"💾 Guardar cambios — {name}", key=f"pf_save_{pf_id}"):
                        new_photos = _save_prefab_photos(pf_id, new_imgs, existing_photos)
                        new_img_path = new_photos[0] if new_photos else (image_path or "")
                        _conn2 = _db_conn()
                        _cur2 = _conn2.cursor()
                        _cur2.execute("""
                            UPDATE prefab_catalog
                            SET name=?, m2=?, rooms=?, bathrooms=?, floors=?, material=?,
                                price=?, active=?, image_path=?, image_paths=?, modulos=?, price_label=?
                            WHERE id=?
                        """, (new_name, new_m2, new_rooms, new_baths, new_floors, new_material,
                              new_price, int(new_active), new_img_path,
                              _json.dumps(new_photos), new_modulos or None,
                              new_price_lbl or None, pf_id))
                        _conn2.commit()
                        _conn2.close()
                        st.success(f"✅ Modelo '{new_name}' actualizado.")
                        st.rerun()

                    if st.button(f"🗑️ Eliminar modelo [{pf_id}]", key=f"pf_del_{pf_id}", type="secondary"):
                        _conn3 = _db_conn()
                        _cur3 = _conn3.cursor()
                        _cur3.execute("DELETE FROM prefab_catalog WHERE id=?", (pf_id,))
                        _conn3.commit()
                        _conn3.close()
                        st.warning(f"Modelo {name} eliminado.")
                        st.rerun()

            st.markdown("---")
            st.markdown("**➕ Añadir nuevo modelo**")
            with st.form("new_prefab_form"):
                nf_c1, nf_c2 = st.columns(2)
                with nf_c1:
                    nf_name     = st.text_input("Nombre del modelo")
                    nf_m2       = st.number_input("Superficie (m²)", min_value=20.0, value=80.0, step=5.0)
                    nf_price    = st.number_input("Precio numérico (€)", min_value=0.0, value=80000.0, step=1000.0)
                    nf_price_lbl= st.text_input("Precio texto (ej: Consultar)", help="Si rellenas esto, se muestra en lugar del precio numérico")
                    nf_modulos  = st.text_input("Módulos", help="Ej: 2 módulos 6x3m")
                    nf_desc     = st.text_area("Descripción corta")
                with nf_c2:
                    nf_rooms    = st.number_input("Habitaciones", min_value=1, max_value=10, value=3)
                    nf_baths    = st.number_input("Baños", min_value=1, max_value=6, value=1)
                    nf_floors   = st.number_input("Plantas", min_value=1, max_value=4, value=1)
                    nf_material = st.selectbox("Material", _MATERIALS)
                    nf_imgs_raw = st.file_uploader("Fotos del modelo (máx. 3)", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
                if st.form_submit_button("➕ Añadir al catálogo", type="primary"):
                    if nf_name:
                        # Guardar fotos
                        _dest_dir2 = _pl.Path("uploads/prefab")
                        _dest_dir2.mkdir(parents=True, exist_ok=True)
                        nf_photos = []
                        for _i, _uf in enumerate((nf_imgs_raw or [])[:3]):
                            if _uf:
                                _dp = _dest_dir2 / f"prefab_new_img{_i+1}_{_uf.name}"
                                with open(_dp, "wb") as _fh2:
                                    _fh2.write(_uf.read())
                                nf_photos.append(str(_dp))
                        nf_img_path = nf_photos[0] if nf_photos else "assets/branding/logo.png"
                        _conn4 = _db_conn()
                        _cur4 = _conn4.cursor()
                        _cur4.execute("""
                            INSERT INTO prefab_catalog
                                (name, m2, rooms, bathrooms, floors, material, price, description,
                                 image_path, image_paths, modulos, price_label)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (nf_name, nf_m2, nf_rooms, nf_baths, nf_floors, nf_material,
                              nf_price, nf_desc, nf_img_path,
                              _json.dumps(nf_photos) if nf_photos else None,
                              nf_modulos or None, nf_price_lbl or None))
                        _conn4.commit()
                        _conn4.close()
                        st.success(f"✅ Modelo '{nf_name}' añadido al catálogo.")
                        st.rerun()
                    else:
                        st.error("El nombre es obligatorio.")

        except Exception as e:
            import traceback
            st.error(f"Error gestionando catálogo de prefabricadas: {e}")

    with tab7:
        st.header("Lista de Espera (Waitlist)")
        try:
            import sqlite3 as _sq3w, pandas as _pdw
            _cw = db_conn()
            _cur_wl = _cw.execute("SELECT name, email, profile, created_at, approved FROM waitlist ORDER BY created_at DESC")
            _rows_wl = _cur_wl.fetchall()
            _cols_wl = [d[0] for d in (_cur_wl.description or [])]
            _data_wl = []
            for _r_wl in _rows_wl:
                try:
                    _data_wl.append([_r_wl[i] for i in range(len(_cols_wl))])
                except Exception:
                    _data_wl.append([_r_wl[c] for c in _cols_wl])
            _dfw = _pdw.DataFrame(_data_wl, columns=_cols_wl)
            _cw.close()
            _total = len(_dfw)
            _approved = int(_dfw['approved'].sum()) if _total > 0 else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Total solicitudes", _total)
            c2.metric("Aprobados", _approved)
            c3.metric("Pendientes", _total - _approved)
            st.markdown("---")
            if _total > 0:
                st.dataframe(_dfw.rename(columns={
                    'name': 'Nombre', 'email': 'Email', 'profile': 'Perfil',
                    'created_at': 'Fecha', 'approved': 'Aprobado'
                }), use_container_width=True, hide_index=True)
                # Exportar CSV
                _csv = _dfw.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Descargar CSV",
                    data=_csv,
                    file_name="waitlist_archirapid.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Aun no hay solicitudes en la lista de espera.")
        except Exception as _ew:
            import traceback as _tb7
            st.error(f"Error cargando waitlist: {_ew}")
            st.code(_tb7.format_exc())

    with tab8:
        st.header("📬 Actividad Reciente")

        # Estado configuración Telegram
        try:
            from modules.marketplace.email_notify import _get_telegram_creds
            _tok, _cid = _get_telegram_creds()
            if _tok and _cid:
                st.success("✅ Telegram configurado — notificaciones activas (@archirapid_mvp_bot)")
            else:
                st.warning("⚠️ **Notificaciones Telegram inactivas** — añade las credenciales en Streamlit Cloud Secrets.")
                with st.expander("¿Cómo configurar?"):
                    st.markdown("""
En Streamlit Cloud → Settings → Secrets, añade:
```
TELEGRAM_BOT_TOKEN = "tu_token_del_bot"
TELEGRAM_CHAT_ID   = "tu_chat_id"
```
Obtén el token creando un bot con @BotFather en Telegram.
""")
        except Exception:
            pass

        st.markdown("---")
        import sqlite3 as _sq3a
        import pandas as _pda

        _ca = db_conn()

        def _read_tab8(conn, sql):
            cur = conn.execute(sql)
            rows = cur.fetchall()
            if not rows:
                return _pda.DataFrame()
            cols = [d[0] for d in (cur.description or [])]
            data = []
            for r in rows:
                try:
                    data.append([r[i] for i in range(len(cols))])
                except Exception:
                    data.append([r[c] for c in cols])
            return _pda.DataFrame(data, columns=cols)

        # Últimos registros
        st.subheader("👤 Últimos registros de usuarios")
        try:
            _df_users = _read_tab8(
                _ca,
                "SELECT name, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 20"
            )
            if not _df_users.empty:
                _df_users["✉️"] = _df_users["email"].apply(
                    lambda e: f"[Escribir](mailto:{e})"
                )
                st.dataframe(
                    _df_users.rename(columns={"name": "Nombre", "email": "Email", "role": "Rol", "created_at": "Fecha"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin registros todavía.")
        except Exception as _eu:
            st.error(f"Error: {_eu}")

        st.markdown("---")

        # Últimas reservas/compras
        st.subheader("💰 Últimas reservas y compras de fincas")
        try:
            _df_res = _read_tab8(
                _ca,
                """SELECT r.buyer_name, r.buyer_email, p.title as finca, r.amount, r.kind, r.created_at
                   FROM reservations r LEFT JOIN plots p ON r.plot_id=p.id
                   ORDER BY r.created_at DESC LIMIT 20"""
            )
            if not _df_res.empty:
                _df_res["kind"] = _df_res["kind"].map({"purchase": "Compra", "reservation": "Reserva"}).fillna(_df_res["kind"])
                st.dataframe(
                    _df_res.rename(columns={
                        "buyer_name": "Comprador", "buyer_email": "Email",
                        "finca": "Finca", "amount": "Importe (€)",
                        "kind": "Tipo", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin transacciones todavía.")
        except Exception as _er:
            st.error(f"Error: {_er}")

        st.markdown("---")

        # Waitlist reciente
        st.subheader("🎯 Waitlist reciente")
        try:
            _df_wl = _read_tab8(
                _ca,
                "SELECT name, email, profile, created_at FROM waitlist ORDER BY created_at DESC LIMIT 10"
            )
            if not _df_wl.empty:
                st.dataframe(
                    _df_wl.rename(columns={"name": "Nombre", "email": "Email", "profile": "Perfil", "created_at": "Fecha"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin solicitudes todavía.")
        except Exception as _ew2:
            st.error(f"Error: {_ew2}")

        _ca.close()

    # ── TAB 9: ANALYTICS ──────────────────────────────────────────────────────
    with tab9:
        st.header("📊 Dashboard de Analytics — ArchiRapid")
        import sqlite3 as _sq9
        import pandas as _pd9
        import datetime as _dt9

        def _read_sql9(conn, sql):
            """pd.read_sql_query compatible con SQLite y psycopg2 wrapper."""
            try:
                cur = conn.execute(sql)
                rows = cur.fetchall()
                if not rows:
                    return _pd9.DataFrame()
                cols = [d[0].title() if d[0].islower() else d[0] for d in (cur.description or [])]
                data = []
                for r in rows:
                    try:
                        data.append([r[i] for i in range(len(cols))])
                    except Exception:
                        data.append([r[c] for c in cols])
                return _pd9.DataFrame(data, columns=cols)
            except Exception as _re:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise _re

        try:
            _db9 = db_conn()

            # ══ 🚨 ALERTAS Y PENDIENTES ══════════════════════════════════════
            st.subheader("🚨 Alertas y pendientes — Acción requerida")
            _alerts_list = []
            try:
                _n_inmo_pend = _db9.execute(
                    "SELECT COUNT(*) FROM inmobiliarias WHERE activa=0"
                ).fetchone()[0]
                if _n_inmo_pend > 0:
                    _alerts_list.append(f"🏢 **{_n_inmo_pend} inmobiliaria(s)** pendiente(s) de aprobación → pestaña MLS")
            except Exception:
                pass
            try:
                _n_finca_pend = _db9.execute(
                    "SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'"
                ).fetchone()[0]
                if _n_finca_pend > 0:
                    _alerts_list.append(f"🏠 **{_n_finca_pend} finca(s) MLS** pendiente(s) de publicación → pestaña MLS")
            except Exception:
                pass
            try:
                _n_colab_pend = _db9.execute(
                    "SELECT COUNT(*) FROM notificaciones_mls WHERE tipo_evento='solicitud_colaboracion_72h' AND destinatario_id='admin' AND leida=0"
                ).fetchone()[0]
                if _n_colab_pend > 0:
                    _alerts_list.append(f"🤝 **{_n_colab_pend} solicitud(es) de colaboración 72h** sin gestionar → pestaña MLS")
            except Exception:
                pass
            try:
                _n_res_48h = _db9.execute(
                    "SELECT COUNT(*) FROM reservas_mls WHERE estado='pendiente_confirmacion_48h'"
                ).fetchone()[0]
                if _n_res_48h > 0:
                    _alerts_list.append(f"⏰ **{_n_res_48h} reserva(s)** cliente pendientes confirmación 48h → pestaña MLS")
            except Exception:
                pass
            try:
                _n_waitlist_pend = _db9.execute(
                    "SELECT COUNT(*) FROM waitlist WHERE approved=0"
                ).fetchone()[0]
                if _n_waitlist_pend > 0:
                    _alerts_list.append(f"🎯 **{_n_waitlist_pend} persona(s)** en waitlist sin aprobar → pestaña Waitlist")
            except Exception:
                pass

            if _alerts_list:
                for _al in _alerts_list:
                    st.warning(_al)
            else:
                st.success("✅ Sin alertas activas. Todo al día.")

            st.markdown("---")

            # ── KPIs principales ──────────────────────────────────────────────
            st.subheader("Métricas globales")

            _n_users    = _db9.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            _n_plots    = _db9.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
            _n_avail    = _db9.execute("SELECT COUNT(*) FROM plots WHERE status='disponible'").fetchone()[0]
            _n_projects = _db9.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            _n_res      = _db9.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            _n_purchase = _db9.execute("SELECT COUNT(*) FROM reservations WHERE kind='purchase'").fetchone()[0]
            _rev_row    = _db9.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()
            _revenue    = float(_rev_row[0]) if _rev_row else 0.0
            _n_waitlist = _db9.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0]
            _n_approved = _db9.execute("SELECT COUNT(*) FROM waitlist WHERE approved=1").fetchone()[0]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("👤 Usuarios registrados", _n_users)
            k2.metric("🗺️ Fincas publicadas", _n_plots, delta=f"{_n_avail} disponibles")
            k3.metric("🏗️ Proyectos activos", _n_projects)
            k4.metric("💶 Ingresos acumulados", f"€{_revenue:,.0f}", delta=f"{_n_res} transacciones")

            _n_alerts = 0
            try:
                _n_alerts = _db9.execute("SELECT COUNT(*) FROM plot_alerts WHERE active=1").fetchone()[0]
            except Exception:
                pass

            k5, k6, k7, k8 = st.columns(4)
            k5.metric("🛒 Reservas totales", _n_res)
            k6.metric("✅ Compras efectivas", _n_purchase)
            k7.metric("🎯 Waitlist total", _n_waitlist, delta=f"{_n_approved} aprobados")
            k8.metric("📐 Conversión reserva→compra",
                      f"{(_n_purchase/_n_res*100):.1f}%" if _n_res else "—")

            _n_subs9, _mrr9, _n_estudio9 = 0, 0.0, 0
            try:
                _sr9 = _db9.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM subscriptions WHERE status='active'").fetchone()
                _n_subs9, _mrr9 = int(_sr9[0]), float(_sr9[1])
            except Exception:
                pass
            try:
                _n_estudio9 = _db9.execute("SELECT COUNT(*) FROM estudio_projects").fetchone()[0]
            except Exception:
                pass

            k9, k10, k11, k12 = st.columns(4)
            k9.metric("🔔 Alertas activas", _n_alerts)
            k10.metric("💎 Suscripciones activas", _n_subs9, delta=f"MRR €{_mrr9:,.0f}")
            k11.metric("🎨 Proyectos Modo Estudio", _n_estudio9)
            _n_ai9 = 0
            try:
                _n_ai9 = _db9.execute("SELECT COUNT(*) FROM ai_projects").fetchone()[0]
            except Exception:
                pass
            k12.metric("🏠 Proyectos AI pagados", _n_ai9)

            st.markdown("---")

            # ── 💳 Stripe Revenue Dashboard ───────────────────────────────────
            st.subheader("💳 Stripe — Revenue en tiempo real (modo test)")
            try:
                from modules.stripe_utils import list_recent_sessions as _lrs
                import pandas as _pd_stripe
                _stripe_sessions = _lrs(limit=50)
                _stripe_rows = []
                for _ss in _stripe_sessions.data:
                    if _ss.payment_status == "paid":
                        _meta = _ss.metadata or {}
                        _stripe_rows.append({
                            "Fecha": _pd_stripe.to_datetime(_ss.created, unit="s").strftime("%d/%m/%Y %H:%M"),
                            "Email": _ss.customer_email or _meta.get("client_email", "—"),
                            "Productos": _meta.get("products", "—"),
                            "Proyecto ID": _meta.get("project_id", "—"),
                            "Importe (€)": (_ss.amount_total or 0) / 100,
                            "Estado": "✅ Pagado",
                        })
                if _stripe_rows:
                    _df_stripe = _pd_stripe.DataFrame(_stripe_rows)
                    _total_stripe = _df_stripe["Importe (€)"].sum()
                    _sc1, _sc2, _sc3 = st.columns(3)
                    _sc1.metric("💶 Revenue Stripe (test)", f"€{_total_stripe:,.0f}")
                    _sc2.metric("🧾 Pagos completados", len(_stripe_rows))
                    _sc3.metric("📊 Ticket medio", f"€{_total_stripe/len(_stripe_rows):,.0f}" if _stripe_rows else "—")
                    st.dataframe(_df_stripe, use_container_width=True, hide_index=True)
                else:
                    st.info("Aún no hay pagos completados en Stripe (modo test). Realiza una compra de prueba con la tarjeta 4242 4242 4242 4242.")
            except Exception as _stripe_err:
                st.warning(f"Stripe no disponible: {_stripe_err}")

            st.markdown("---")

            # ── Funnel de conversión ──────────────────────────────────────────
            st.subheader("🔽 Funnel de conversión")
            _funnel_data = {
                "Etapa": ["Fincas publicadas", "Usuarios registrados", "Reservas realizadas", "Compras efectivas", "Waitlist aprobados"],
                "Total": [_n_plots, _n_users, _n_res, _n_purchase, _n_approved]
            }
            _df_funnel = _pd9.DataFrame(_funnel_data).set_index("Etapa")
            st.bar_chart(_df_funnel)

            st.markdown("---")

            # ── Usuarios por rol ──────────────────────────────────────────────
            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("👥 Usuarios por rol")
                try:
                    _df_roles = _read_sql9(
                        _db9,
                        "SELECT role as Rol, COUNT(*) as Total FROM users GROUP BY role ORDER BY Total DESC"
                    )
                    if not _df_roles.empty:
                        st.dataframe(_df_roles, use_container_width=True, hide_index=True)
                        st.bar_chart(_df_roles.set_index("Rol"))
                    else:
                        st.info("Sin datos de roles todavía.")
                except Exception as _er:
                    st.warning(f"Roles: {_er}")

            with col_b:
                st.subheader("🗺️ Fincas por provincia")
                try:
                    _df_prov = _read_sql9(
                        _db9,
                        "SELECT province as Provincia, COUNT(*) as Fincas FROM plots GROUP BY province ORDER BY Fincas DESC"
                    )
                    if not _df_prov.empty:
                        st.dataframe(_df_prov, use_container_width=True, hide_index=True)
                        st.bar_chart(_df_prov.set_index("Provincia"))
                    else:
                        st.info("Sin datos de provincias todavía.")
                except Exception as _ep:
                    st.warning(f"Provincias: {_ep}")

            st.markdown("---")

            # ── Ingresos por tipo de operación ────────────────────────────────
            st.subheader("💰 Ingresos por tipo de operación")
            try:
                _df_kind = _read_sql9(
                    _db9,
                    "SELECT kind as Tipo, COUNT(*) as Operaciones, COALESCE(SUM(amount),0) as Importe FROM reservations GROUP BY kind"
                )
                if not _df_kind.empty:
                    _df_kind["Tipo"] = _df_kind["Tipo"].map(
                        {"purchase": "Compra", "reservation": "Reserva", "pdf": "Docs PDF",
                         "cad": "Docs CAD", "full": "Paquete completo"}
                    ).fillna(_df_kind["Tipo"])
                    st.dataframe(_df_kind, use_container_width=True, hide_index=True)
                    st.bar_chart(_df_kind.set_index("Tipo")["Importe"])
                else:
                    st.info("Sin transacciones todavía.")
            except Exception as _ek:
                st.warning(f"Tipos: {_ek}")

            st.markdown("---")

            # ── Actividad diaria (últimos 30 días) ────────────────────────────
            st.subheader("📅 Registros de usuarios — últimos 30 días")
            try:
                _df_daily = _read_sql9(
                    _db9,
                    """SELECT DATE(created_at) as Fecha, COUNT(*) as Registros
                       FROM users
                       WHERE DATE(created_at) >= DATE('now', '-30 days')
                       GROUP BY DATE(created_at)
                       ORDER BY Fecha"""
                )
                if not _df_daily.empty:
                    st.line_chart(_df_daily.set_index("Fecha"))
                else:
                    st.info("Sin registros en los últimos 30 días.")
            except Exception as _ed:
                st.warning(f"Actividad diaria: {_ed}")

            st.markdown("---")

            # ── Top fincas por precio ─────────────────────────────────────────
            st.subheader("🏆 Top 10 fincas por precio")
            try:
                _df_top = _read_sql9(
                    _db9,
                    "SELECT title as Finca, province as Provincia, m2 as Superficie_m2, price as Precio_EUR, status as Estado FROM plots ORDER BY price DESC LIMIT 10"
                )
                if not _df_top.empty:
                    st.dataframe(_df_top, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin fincas en el catálogo.")
            except Exception as _et:
                st.warning(f"Top fincas: {_et}")

            # ── TRACKING DEEP LINKS Y DEMOS ────────────────────────────────
            st.markdown("---")
            st.subheader("🔗 Tracking de Deep Links y Demos")
            try:
                _df_vis = _read_sql9(
                    _db9,
                    """SELECT origen as Origen,
                              COUNT(*) as Visitas,
                              SUM(convirtio_a_registro) as Registros,
                              ROUND(SUM(convirtio_a_registro)*100.0/COUNT(*),1) as ConvPct
                       FROM visitas_demo
                       GROUP BY origen ORDER BY Visitas DESC"""
                )
                if not _df_vis.empty:
                    _kv1, _kv2, _kv3 = st.columns(3)
                    _kv1.metric("Total visitas demo", int(_df_vis["Visitas"].sum()))
                    _kv2.metric("Registros generados", int(_df_vis["Registros"].sum()))
                    _total_vis = int(_df_vis["Visitas"].sum())
                    _total_reg = int(_df_vis["Registros"].sum())
                    _conv_global = round(_total_reg * 100.0 / _total_vis, 1) if _total_vis > 0 else 0
                    _kv3.metric("Conversion global", f"{_conv_global}%")
                    st.dataframe(_df_vis, use_container_width=True, hide_index=True)

                    # Detalle de visitas recientes
                    _df_det = _read_sql9(
                        _db9,
                        """SELECT timestamp as Fecha, origen as Origen, nombre_usuario as Usuario,
                                  accion_realizada as Accion,
                                  CASE convirtio_a_registro WHEN 1 THEN 'Si' ELSE 'No' END as Registro
                           FROM visitas_demo ORDER BY timestamp DESC LIMIT 50"""
                    )
                    st.caption("Ultimas 50 visitas:")
                    st.dataframe(_df_det, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin visitas registradas todavia. Comparte el enlace demo para empezar a trackear.")
                    st.code("https://archirapid.streamlit.app/?seccion=arquitecto&demo=true&from=linkedin&user=nombre")
            except Exception as _ev:
                st.error(f"Error tracking: {_ev}")

            # ── MLS Analytics ─────────────────────────────────────────────────
            st.markdown("---")
            st.subheader("🏢 MLS — Estadísticas consolidadas")
            try:
                _mls_a_conn = db_conn()

                # KPIs MLS en una fila
                _mls_total_inmos   = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias").fetchone()[0]
                _mls_act_inmos     = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=1").fetchone()[0]
                _mls_pend_inmos    = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=0").fetchone()[0]
                _mls_fincas_pub    = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='publicada'").fetchone()[0]
                _mls_fincas_res    = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='reservada'").fetchone()[0]
                _mls_fincas_pend   = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'").fetchone()[0]
                _mls_reservas_act  = _mls_a_conn.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='activa'").fetchone()[0]

                _ma1, _ma2, _ma3, _ma4 = st.columns(4)
                _ma1.metric("🏢 Inmos totales", _mls_total_inmos,
                            delta=f"{_mls_act_inmos} activas / {_mls_pend_inmos} pend.")
                _ma2.metric("🏠 Fincas publicadas", _mls_fincas_pub)
                _ma3.metric("🔒 Fincas reservadas", _mls_fincas_res)
                _ma4.metric("📋 Reservas activas", _mls_reservas_act)

                _col_mls1, _col_mls2 = st.columns(2)

                with _col_mls1:
                    # Fincas MLS por estado
                    try:
                        _df_mls_estado = _read_sql9(
                            _mls_a_conn,
                            "SELECT estado as Estado, COUNT(*) as Total FROM fincas_mls GROUP BY estado ORDER BY Total DESC"
                        )
                        if not _df_mls_estado.empty:
                            st.caption("Fincas MLS por estado")
                            st.bar_chart(_df_mls_estado.set_index("Estado"))
                    except Exception as _em1:
                        st.warning(f"Fincas MLS estado: {_em1}")

                with _col_mls2:
                    # Inmos por provincia
                    try:
                        _df_mls_prov = _read_sql9(
                            _mls_a_conn,
                            "SELECT provincia as Provincia, COUNT(*) as Inmos FROM inmobiliarias GROUP BY provincia ORDER BY Inmos DESC LIMIT 10"
                        )
                        if not _df_mls_prov.empty:
                            st.caption("Inmos MLS por provincia (top 10)")
                            st.bar_chart(_df_mls_prov.set_index("Provincia"))
                    except Exception as _em2:
                        st.warning(f"Inmos provincia: {_em2}")

                # Actividad MLS últimos 30 días (registros de inmos + fincas subidas)
                try:
                    _df_mls_act = _read_sql9(
                        _mls_a_conn,
                        """
                        SELECT DATE(created_at) as Fecha, 'Inmobiliarias' as Tipo, COUNT(*) as N
                        FROM inmobiliarias
                        WHERE created_at >= DATE('now', '-30 days')
                        GROUP BY DATE(created_at)
                        UNION ALL
                        SELECT DATE(created_at) as Fecha, 'Fincas MLS' as Tipo, COUNT(*) as N
                        FROM fincas_mls
                        WHERE created_at >= DATE('now', '-30 days')
                        GROUP BY DATE(created_at)
                        ORDER BY Fecha
                        """
                    )
                    if not _df_mls_act.empty:
                        _df_mls_pivot = _df_mls_act.pivot_table(
                            index="Fecha", columns="Tipo", values="N", aggfunc="sum"
                        ).fillna(0)
                        st.caption("Actividad MLS — últimos 30 días")
                        st.bar_chart(_df_mls_pivot)
                except Exception as _em3:
                    pass  # tabla puede estar vacía — no mostrar error

                # Notificaciones MLS pendientes por tipo
                try:
                    _df_notifs = _read_sql9(
                        _mls_a_conn,
                        """SELECT tipo_evento as Tipo, COUNT(*) as Total
                           FROM notificaciones_mls
                           WHERE leida=0
                           GROUP BY tipo_evento ORDER BY Total DESC"""
                    )
                    if not _df_notifs.empty:
                        st.caption("Notificaciones MLS sin leer por tipo")
                        st.dataframe(_df_notifs, use_container_width=True, hide_index=True)
                except Exception:
                    pass

                _mls_a_conn.close()
            except Exception as _emls:
                st.warning(f"Error estadísticas MLS: {_emls}")

            _db9.close()

        except Exception as _e9:
            st.error(f"Error en Analytics: {_e9}")

    # ── TAB 10: MLS — INMOBILIARIAS ───────────────────────────────────────────
    with tab10:
        st.header("🏢 ArchiRapid MLS — Panel de Administración")

        # Imports locales — sin afectar el resto de la Intranet
        try:
            from modules.mls import mls_db as _mls
            from modules.mls import mls_notificaciones as _mls_notif
        except Exception as _imp_err:
            st.error(f"No se pudo cargar el módulo MLS: {_imp_err}")
            st.stop()

        def _mask_iban(iban: str) -> str:
            """Muestra solo los últimos 4 dígitos del IBAN en listados."""
            if not iban or len(iban) < 4:
                return iban or "—"
            return "****…****" + iban[-4:]

        # ══ SECCIÓN F: KPIs MLS ══════════════════════════════════════════════
        st.subheader("📊 KPIs MLS")
        try:
            _mls_conn = db_conn()
            _n_inmo_total  = _mls_conn.execute("SELECT COUNT(*) FROM inmobiliarias").fetchone()[0]
            _n_inmo_act    = _mls_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=1").fetchone()[0]
            _n_fincas_pub  = _mls_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='publicada'").fetchone()[0]
            _n_reservas_a  = _mls_conn.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='activa'").fetchone()[0]
            _mls_conn.close()

            _mls_conn2 = db_conn()
            _n_pend_inmo   = _mls_conn2.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=0").fetchone()[0]
            _n_pend_finca  = _mls_conn2.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'").fetchone()[0]
            _n_res_cli     = _mls_conn2.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='pendiente_confirmacion_48h'").fetchone()[0]
            # Ingresos estimados: sum de pagos Stripe con mls en productos
            _ingresos_mls  = 0.0
            try:
                from modules.stripe_utils import list_recent_sessions as _lrs_mls
                _sess_mls = _lrs_mls(limit=100)
                import datetime as _dt_mls
                _this_month = _dt_mls.datetime.now().replace(day=1, hour=0, minute=0, second=0)
                for _sm in _sess_mls.data:
                    if _sm.payment_status == "paid":
                        _meta_m = _sm.metadata or {}
                        _prods  = _meta_m.get("products", "")
                        if "mls" in _prods.lower():
                            _ts = _dt_mls.datetime.fromtimestamp(_sm.created)
                            if _ts >= _this_month:
                                _ingresos_mls += (_sm.amount_total or 0) / 100
            except Exception:
                pass
            _mls_conn2.close()

            _fk1, _fk2, _fk3, _fk4 = st.columns(4)
            _fk1.metric("🏢 Inmos registradas", _n_inmo_total)
            _fk2.metric("✅ Inmos activas", _n_inmo_act)
            _fk3.metric("🏠 Fincas publicadas", _n_fincas_pub)
            _fk4.metric("🔒 Reservas activas", _n_reservas_a)

            _fk5, _fk6, _fk7, _fk8 = st.columns(4)
            _fk5.metric("⏳ Pendientes aprobación", _n_pend_inmo,
                        delta="⚠️ Acción requerida" if _n_pend_inmo > 0 else None,
                        delta_color="inverse")
            _fk6.metric("📋 Fincas pend. aprobación", _n_pend_finca,
                        delta="⚠️ Acción requerida" if _n_pend_finca > 0 else None,
                        delta_color="inverse")
            _fk7.metric("⏰ Reservas cliente 48h", _n_res_cli)
            _fk8.metric("💶 Ingresos MLS (este mes)", f"€{_ingresos_mls:,.0f}")
        except Exception as _ef:
            st.warning(f"Error KPIs MLS: {_ef}")

        st.markdown("---")

        # ══ SECCIÓN A: Inmobiliarias pendientes de aprobación ════════════════
        st.subheader("⏳ A. Inmobiliarias pendientes de aprobación")
        try:
            _pendientes = _mls.get_inmos_pendientes()
            if not _pendientes:
                st.success("✅ Sin registros pendientes de aprobación.")
            else:
                st.warning(f"**{len(_pendientes)} inmobiliaria(s) esperando aprobación.**")
                for _p in _pendientes:
                    _pnombre = _p.get("nombre_comercial") or _p.get("nombre", "Sin nombre")
                    with st.expander(f"📋 {_pnombre} — {_p.get('cif','?')} | {_p.get('email','?')} | {(_p.get('created_at',''))[:10]}"):
                        _ca, _cb = st.columns([3, 1])
                        with _ca:
                            st.markdown("**📊 Datos de empresa**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre legal | {_p.get('nombre_sociedad') or '—'} |
| Nombre comercial | {_p.get('nombre_comercial') or '—'} |
| CIF | `{_p.get('cif','—')}` |
| Email corporativo | {_p.get('email','—')} |
| Email login | {_p.get('email_login') or '—'} |
| Teléfono principal | {_p.get('telefono') or '—'} |
| Teléfono secundario | {_p.get('telefono_secundario') or '—'} |
| Telegram | {_p.get('telegram_contacto') or '—'} |
| Web | {_p.get('web') or '—'} |
| IP registro | `{_p.get('ip_registro','—')}` |
| Fecha registro | {(_p.get('created_at',''))[:19]} |
""")
                            st.markdown("**📍 Dirección**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Dirección | {_p.get('direccion') or '—'} |
| Localidad | {_p.get('localidad') or '—'} |
| Provincia | {_p.get('provincia') or '—'} |
| CP | {_p.get('codigo_postal') or '—'} |
| País | {_p.get('pais') or '—'} |
""")
                            st.markdown("**👤 Persona de contacto**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {_p.get('contacto_nombre') or '—'} |
| Cargo | {_p.get('contacto_cargo') or '—'} |
| Email directo | {_p.get('contacto_email') or '—'} |
| Teléfono | {_p.get('contacto_telefono') or '—'} |
| Telegram | {_p.get('contacto_telegram') or '—'} |
""")
                            st.markdown("**🧾 Facturación**")
                            _iban_m = _mask_iban(_p.get('iban') or '')
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Razón social | {_p.get('factura_razon_social') or '—'} |
| CIF factura | {_p.get('factura_cif') or '—'} |
| Dirección fiscal | {_p.get('factura_direccion') or '—'} |
| Email facturas | {_p.get('factura_email') or '—'} |
| IBAN | `{_iban_m}` |
| Banco | {_p.get('banco_nombre') or '—'} |
| Titular | {_p.get('banco_titular') or '—'} |
""")
                        with _cb:
                            st.markdown("**Acciones**")
                            if st.button("✅ Aprobar", key=f"mls_apro_{_p['id']}", type="primary",
                                         use_container_width=True):
                                _mls.update_inmo_activa(_p["id"], 1)
                                try:
                                    _mls_notif.notif_aprobacion(
                                        nombre=_pnombre,
                                        email=_p.get("email", ""),
                                        aprobada=True,
                                    )
                                except Exception:
                                    pass
                                st.success(f"✅ {_pnombre} aprobada.")
                                st.rerun()

                            st.markdown("")
                            _confirm_key = f"mls_confirm_del_{_p['id']}"
                            if st.session_state.get(_confirm_key):
                                st.warning("⚠️ ¿Confirmar eliminación? Esta acción no se puede deshacer.")
                                _cc1, _cc2 = st.columns(2)
                                with _cc1:
                                    if st.button("Sí, eliminar", key=f"mls_del_yes_{_p['id']}",
                                                 type="primary", use_container_width=True):
                                        try:
                                            _dc = db_conn()
                                            _dc.execute("DELETE FROM inmobiliarias WHERE id=?", (_p["id"],))
                                            _dc.commit()
                                            _dc.close()
                                            _mls_notif.notif_aprobacion(
                                                nombre=_pnombre,
                                                email=_p.get("email", ""),
                                                aprobada=False,
                                            )
                                        except Exception:
                                            pass
                                        st.session_state.pop(_confirm_key, None)
                                        st.rerun()
                                with _cc2:
                                    if st.button("Cancelar", key=f"mls_del_no_{_p['id']}",
                                                 use_container_width=True):
                                        st.session_state.pop(_confirm_key, None)
                                        st.rerun()
                            else:
                                if st.button("❌ Rechazar y eliminar", key=f"mls_del_{_p['id']}",
                                             use_container_width=True):
                                    st.session_state[_confirm_key] = True
                                    st.rerun()
        except Exception as _ea:
            st.warning(f"Error sección A: {_ea}")

        st.markdown("---")

        # ══ SECCIÓN B: Inmobiliarias activas ═════════════════════════════════
        st.subheader("✅ B. Inmobiliarias activas")
        try:
            _activas = _mls.get_inmos_activas()
            if not _activas:
                st.info("No hay inmobiliarias activas todavía.")
            else:
                for _a in _activas:
                    if _a is None:
                        continue
                    _anombre = _a.get("nombre_comercial") or _a.get("nombre", "?")
                    _plan_a  = (_a.get("plan") or "ninguno").upper()
                    _firma_a = "✅" if _a.get("firma_hash") else "⚠️ Pendiente"
                    # Contar fincas activas
                    _n_fincas_a = 0
                    try:
                        _fc = db_conn()
                        _n_fincas_a = _fc.execute(
                            "SELECT COUNT(*) FROM fincas_mls WHERE inmo_id=? AND estado NOT IN ('eliminada','cerrada')",
                            (_a["id"],)
                        ).fetchone()[0]
                        _fc.close()
                    except Exception:
                        pass

                    with st.expander(
                        f"🏢 {_anombre} — Plan {_plan_a} | Firma: {_firma_a} | "
                        f"Fincas: {_n_fincas_a} | {_a.get('email','')}"
                    ):
                        _ba, _bb = st.columns([3, 1])
                        with _ba:
                            # Tabla resumida
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre comercial | {_anombre} |
| CIF | `{_a.get('cif','—')}` |
| Email | {_a.get('email','—')} |
| Plan | **{_plan_a}** |
| Plan activo | {'✅' if _a.get('plan_activo') else '❌'} |
| Firma acuerdo | {_firma_a} |
| Fecha firma | {((_a.get('firma_timestamp') or ''))[:10] or '—'} |
| Fincas activas | {_n_fincas_a} |
""")
                            # Detalle completo en sub-expander
                            with st.expander("📋 Ver detalle completo"):
                                _iban_full = _a.get("iban") or "—"
                                st.markdown(f"""
**Empresa**
- Nombre legal: {_a.get('nombre_sociedad') or '—'}
- Teléfono: {_a.get('telefono') or '—'} / {_a.get('telefono_secundario') or '—'}
- Web: {_a.get('web') or '—'}
- Dirección: {_a.get('direccion') or '—'}, {_a.get('localidad') or '—'}, {_a.get('provincia') or '—'} {_a.get('codigo_postal') or ''}, {_a.get('pais') or '—'}

**Contacto responsable**
- {_a.get('contacto_nombre') or '—'} ({_a.get('contacto_cargo') or 'sin cargo'})
- Email: {_a.get('contacto_email') or '—'}
- Tel: {_a.get('contacto_telefono') or '—'}

**Facturación**
- Razón social: {_a.get('factura_razon_social') or '—'}
- CIF: {_a.get('factura_cif') or '—'}
- Dirección fiscal: {_a.get('factura_direccion') or '—'}
- Email facturas: {_a.get('factura_email') or '—'}
- IBAN completo: `{_iban_full}`
- Banco: {_a.get('banco_nombre') or '—'} — Titular: {_a.get('banco_titular') or '—'}
""")
                        with _bb:
                            st.markdown("**Acciones**")
                            if st.button("⏸ Suspender", key=f"mls_susp_{_a['id']}",
                                         use_container_width=True):
                                _mls.update_inmo_activa(_a["id"], 0)
                                st.warning(f"⏸ {_anombre} suspendida.")
                                st.rerun()
        except Exception as _eb:
            st.warning(f"Error sección B: {_eb}")

        st.markdown("---")

        # ══ SECCIÓN C: Fincas MLS ════════════════════════════════════════════
        st.subheader("🏠 C. Fincas MLS en el sistema")
        try:
            # Filtro por estado
            _estados_filtro = ["Todos", "pendiente_validacion", "validada_pendiente_aprobacion",
                               "publicada", "reservada", "reserva_pendiente_confirmacion",
                               "cerrada", "pausada", "eliminada"]
            _filtro_estado = st.selectbox(
                "Filtrar por estado", _estados_filtro,
                key="mls_filtro_estado_fincas"
            )

            _fq = db_conn()
            _sql_fincas = """
                SELECT f.id, f.ref_codigo, f.titulo, f.precio, f.superficie_m2,
                       f.estado, f.created_at, f.catastro_validada,
                       f.dias_en_mercado_inicio,
                       COALESCE(i.nombre_comercial, i.nombre, '—') as listante,
                       i.email as listante_email
                FROM fincas_mls f
                LEFT JOIN inmobiliarias i ON f.inmo_id = i.id
            """
            if _filtro_estado != "Todos":
                _sql_fincas += " WHERE f.estado = ?"
                _fincas_list = _fq.execute(_sql_fincas, (_filtro_estado,)).fetchall()
            else:
                _fincas_list = _fq.execute(_sql_fincas).fetchall()
            _fq.close()

            if not _fincas_list:
                st.info("No hay fincas que coincidan con el filtro.")
            else:
                import pandas as _pd_mls
                _cols_f = ["id","ref_codigo","titulo","precio","superficie_m2","estado",
                           "created_at","catastro_validada","dias_en_mercado_inicio",
                           "listante","listante_email"]
                _df_fincas = _pd_mls.DataFrame([dict(zip(_cols_f, r)) for r in _fincas_list])

                # Calcular días en mercado
                import datetime as _dt_mls2
                def _dias(ts):
                    try:
                        d = _dt_mls2.datetime.fromisoformat(ts)
                        return (_dt_mls2.datetime.now(_dt_mls2.timezone.utc) - d).days
                    except Exception:
                        return "—"
                _df_fincas["días"] = _df_fincas["dias_en_mercado_inicio"].apply(_dias)
                _df_fincas["catastro"] = _df_fincas["catastro_validada"].map({1: "✅", 0: "⚠️"}).fillna("⚠️")

                st.dataframe(
                    _df_fincas[["ref_codigo","titulo","precio","estado","días","listante","catastro"]].rename(columns={
                        "ref_codigo": "REF", "titulo": "Título",
                        "precio": "Precio (€)", "estado": "Estado",
                        "días": "Días", "listante": "Listante", "catastro": "Catastro"
                    }),
                    use_container_width=True, hide_index=True
                )

                st.markdown("**Acciones por finca:**")
                for _, _frow in _df_fincas.iterrows():
                    _fid    = _frow["id"]
                    _fref   = _frow["ref_codigo"] or "sin ref"
                    _ftit   = _frow["titulo"] or "Sin título"
                    _festado = _frow["estado"]
                    _femail = _frow["listante_email"]
                    _flis   = _frow["listante"]

                    with st.expander(f"[{_fref}] {_ftit} — {_festado}"):
                        _fc1, _fc2 = st.columns([2, 1])
                        with _fc1:
                            st.markdown(f"**Listante:** {_flis} | **Estado:** `{_festado}` | "
                                        f"**Precio:** €{_frow['precio']:,.0f} | "
                                        f"**Superficie:** {_frow['superficie_m2']} m²")
                        with _fc2:
                            # Aprobar publicación — solo si está validada_pendiente_aprobacion
                            if _festado == "validada_pendiente_aprobacion":
                                if st.button("✅ Aprobar publicación", key=f"mls_apro_f_{_fid}",
                                             type="primary", use_container_width=True):
                                    try:
                                        _mls.update_finca_estado(_fid, "publicada")
                                        _mls_notif.notif_finca_publicada(
                                            ref_codigo=_fref,
                                            titulo=_ftit,
                                            precio=_frow["precio"],
                                            inmo_email=_femail or "",
                                        )
                                    except Exception:
                                        pass
                                    st.rerun()

                            # Confirmación reserva cliente directo
                            if _festado == "reserva_pendiente_confirmacion":
                                # Buscar datos del cliente en reservas
                                try:
                                    _rc = db_conn()
                                    _res_cli_row = _rc.execute(
                                        """SELECT notas FROM reservas_mls
                                           WHERE finca_id=? AND inmo_colaboradora_id='CLIENTE_DIRECTO'
                                           ORDER BY timestamp_reserva DESC LIMIT 1""",
                                        (_fid,)
                                    ).fetchone()
                                    _rc.close()
                                    _notas_cli = (_res_cli_row[0] or "") if _res_cli_row else ""
                                    # notas = "Cliente: {nombre} | {email}"
                                    _nom_cli, _email_cli = "—", "—"
                                    if "Cliente:" in _notas_cli and "|" in _notas_cli:
                                        _parts = _notas_cli.split("|")
                                        _nom_cli  = _parts[0].replace("Cliente:", "").strip()
                                        _email_cli = _parts[1].strip() if len(_parts) > 1 else "—"
                                except Exception:
                                    _nom_cli, _email_cli = "—", "—"

                                st.caption(f"Cliente: {_nom_cli} | {_email_cli}")
                                _rc1, _rc2 = st.columns(2)
                                with _rc1:
                                    if st.button("✅ Confirmar disponible", key=f"mls_conf_{_fid}",
                                                 type="primary", use_container_width=True):
                                        _mls.update_finca_estado(_fid, "reservada")
                                        try:
                                            _mls_notif.notif_confirmacion_reserva_cliente(
                                                email_cliente=_email_cli,
                                                nombre_cliente=_nom_cli,
                                                ref_codigo=_fref,
                                                confirmada=True,
                                            )
                                        except Exception:
                                            pass
                                        st.rerun()
                                with _rc2:
                                    if st.button("❌ No disponible", key=f"mls_nodisp_{_fid}",
                                                 use_container_width=True):
                                        _mls.update_finca_estado(_fid, "publicada")
                                        try:
                                            _mls_notif.notif_confirmacion_reserva_cliente(
                                                email_cliente=_email_cli,
                                                nombre_cliente=_nom_cli,
                                                ref_codigo=_fref,
                                                confirmada=False,
                                            )
                                        except Exception:
                                            pass
                                        st.rerun()

                            # Botones de gestión general
                            _gb1, _gb2 = st.columns(2)
                            with _gb1:
                                if _festado not in ("pausada", "cerrada", "eliminada"):
                                    if st.button("⏸ Pausar", key=f"mls_pau_{_fid}",
                                                 use_container_width=True):
                                        _mls.update_finca_estado(_fid, "pausada")
                                        st.rerun()
                                elif _festado == "pausada":
                                    if st.button("▶️ Reactivar", key=f"mls_react_{_fid}",
                                                 type="primary", use_container_width=True):
                                        _mls.update_finca_estado(_fid, "publicada")
                                        st.rerun()
                            with _gb2:
                                if _festado != "eliminada":
                                    _elim_key = f"mls_elim_confirm_{_fid}"
                                    if st.session_state.get(_elim_key):
                                        if st.button("⚠️ Confirmar borrado lógico",
                                                     key=f"mls_elim_yes_{_fid}",
                                                     use_container_width=True):
                                            _mls.update_finca_estado(_fid, "eliminada")
                                            st.session_state.pop(_elim_key, None)
                                            st.rerun()
                                    else:
                                        if st.button("🗑️ Eliminar", key=f"mls_elim_{_fid}",
                                                     use_container_width=True):
                                            st.session_state[_elim_key] = True
                                            st.rerun()
        except Exception as _ec:
            st.warning(f"Error sección C: {_ec}")

        st.markdown("---")

        # ══ SECCIÓN D: Reservas activas ══════════════════════════════════════
        st.subheader("🔒 D. Reservas activas")
        try:
            import datetime as _dt_res
            _rq = db_conn()
            _reservas_admin = _rq.execute("""
                SELECT r.id, r.finca_id, r.inmo_colaboradora_id, r.estado,
                       r.importe_reserva, r.timestamp_reserva, r.timestamp_expira_72h, r.notas,
                       f.ref_codigo, f.titulo,
                       COALESCE(il.nombre_comercial, il.nombre, '—') as listante,
                       COALESCE(ic.nombre_comercial, ic.nombre, r.inmo_colaboradora_id) as colaboradora
                FROM reservas_mls r
                LEFT JOIN fincas_mls f ON r.finca_id = f.id
                LEFT JOIN inmobiliarias il ON f.inmo_id = il.id
                LEFT JOIN inmobiliarias ic ON r.inmo_colaboradora_id = ic.id
                WHERE r.estado IN ('activa','pendiente_confirmacion_48h')
                ORDER BY r.timestamp_reserva DESC
            """).fetchall()
            _rq.close()

            if not _reservas_admin:
                st.info("No hay reservas activas en este momento.")
            else:
                _cols_r = ["id","finca_id","inmo_colaboradora_id","estado","importe_reserva",
                           "timestamp_reserva","timestamp_expira_72h","notas",
                           "ref_codigo","titulo","listante","colaboradora"]
                for _rv in _reservas_admin:
                    _rd = dict(zip(_cols_r, _rv))
                    # Calcular horas restantes
                    _hrs_rest = "—"
                    try:
                        _exp_dt = _dt_res.datetime.fromisoformat(_rd["timestamp_expira_72h"])
                        _now_dt = _dt_res.datetime.now(_dt_res.timezone.utc)
                        if _exp_dt.tzinfo is None:
                            _exp_dt = _exp_dt.replace(tzinfo=_dt_res.timezone.utc)
                        _diff   = _exp_dt - _now_dt
                        _hrs_rest = f"{max(0, int(_diff.total_seconds() // 3600))}h"
                    except Exception:
                        pass

                    _tipo_r = "👤 Cliente directo" if _rd["inmo_colaboradora_id"] == "CLIENTE_DIRECTO" \
                              else "🤝 Colaboradora"
                    with st.expander(
                        f"[{_rd['ref_codigo'] or '?'}] {_rd['titulo'] or '?'} — "
                        f"{_tipo_r} | {_hrs_rest} restantes | €{_rd['importe_reserva']:,.0f}"
                    ):
                        _ra, _rb = st.columns([3, 1])
                        with _ra:
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| REF finca | `{_rd['ref_codigo'] or '—'}` |
| Tipo | {_tipo_r} |
| Colaboradora/Cliente | {_rd['colaboradora']} |
| Listante | {_rd['listante']} |
| Importe reserva | €{_rd['importe_reserva']:,.0f} |
| Reservado el | {(_rd['timestamp_reserva'] or '')[:16]} |
| Expira | {(_rd['timestamp_expira_72h'] or '')[:16]} |
| Horas restantes | **{_hrs_rest}** |
| Notas | {_rd['notas'] or '—'} |
""")
                        with _rb:
                            if st.button("⏰ Forzar expiración", key=f"mls_fexp_{_rd['id']}",
                                         use_container_width=True):
                                try:
                                    _ec2 = db_conn()
                                    _ec2.execute(
                                        "UPDATE reservas_mls SET estado='expirada' WHERE id=?",
                                        (_rd["id"],)
                                    )
                                    _ec2.execute(
                                        "UPDATE fincas_mls SET estado='publicada', updated_at=? WHERE id=?",
                                        (_dt_res.datetime.now(_dt_res.timezone.utc).isoformat(timespec="seconds"),
                                         _rd["finca_id"])
                                    )
                                    _ec2.commit()
                                    _ec2.close()
                                    st.success("Reserva expirada. Finca liberada.")
                                    st.rerun()
                                except Exception as _ef2:
                                    st.error(f"Error: {_ef2}")
        except Exception as _ed:
            st.warning(f"Error sección D: {_ed}")

        st.markdown("---")

        # ══ SECCIÓN E: Firmas del acuerdo ════════════════════════════════════
        st.subheader("✍️ E. Firmas del Acuerdo de Colaboración MLS")
        try:
            _fq2 = db_conn()
            _firmas_admin = _fq2.execute("""
                SELECT fc.id, COALESCE(i.nombre_comercial, i.nombre, '—') as inmo,
                       fc.cif, fc.timestamp, fc.ip,
                       fc.documento_hash, fc.firma_hash, fc.documento_version
                FROM firmas_colaboracion fc
                LEFT JOIN inmobiliarias i ON fc.inmo_id = i.id
                ORDER BY fc.timestamp DESC
            """).fetchall()
            _fq2.close()

            if not _firmas_admin:
                st.info("No hay firmas registradas todavía.")
            else:
                import pandas as _pd_f
                _cols_fi = ["id","inmo","cif","timestamp","ip","doc_hash","firma_hash","version"]
                _df_fi   = _pd_f.DataFrame([dict(zip(_cols_fi, r)) for r in _firmas_admin])
                # Truncar hashes para listado
                _df_fi["doc_hash_s"]   = _df_fi["doc_hash"].str[:16]  + "…"
                _df_fi["firma_hash_s"] = _df_fi["firma_hash"].str[:16] + "…"
                st.dataframe(
                    _df_fi[["inmo","cif","timestamp","ip","doc_hash_s","firma_hash_s","version"]].rename(columns={
                        "inmo": "Inmobiliaria", "cif": "CIF",
                        "timestamp": "Fecha firma", "ip": "IP",
                        "doc_hash_s": "Doc hash (16)", "firma_hash_s": "Firma hash (16)",
                        "version": "Versión"
                    }),
                    use_container_width=True, hide_index=True
                )
                st.caption("Firmas digitales eIDAS art.25 — SHA-256 sobre TEXTO_ACUERDO + timestamp + CIF + IP")

                for _, _fir in _df_fi.iterrows():
                    with st.expander(f"📄 Certificado completo — {_fir['inmo']} ({_fir['timestamp'][:10]})"):
                        st.markdown(f"""
**Inmobiliaria:** {_fir['inmo']}
**CIF:** `{_fir['cif']}`
**Timestamp:** `{_fir['timestamp']}`
**IP firmante:** `{_fir['ip']}`
**Versión documento:** `{_fir['version']}`

**Documento hash (SHA-256 completo):**
```
{_fir['doc_hash']}
```
**Firma hash (SHA-256 completo):**
```
{_fir['firma_hash']}
```
*Referencia legal: eIDAS art.25 — Firma electrónica avanzada.*
*SHA-256(TEXTO_ACUERDO_MLS + timestamp + CIF + IP)*
""")
        except Exception as _ee2:
            st.warning(f"Error sección E: {_ee2}")

        st.markdown("---")

        # ══ SECCIÓN F: Solicitudes de Colaboración 72h ═══════════════════════
        st.subheader("🤝 F. Solicitudes de Colaboración 72h")
        try:
            import json as _json_f
            _sq_f = db_conn()
            _sols_admin = _sq_f.execute("""
                SELECT id, payload, timestamp, leida
                FROM notificaciones_mls
                WHERE tipo_evento = 'solicitud_colaboracion_72h'
                  AND destinatario_id = 'admin'
                ORDER BY timestamp DESC
                LIMIT 50
            """).fetchall()
            _sq_f.close()

            _sols_pend = [s for s in _sols_admin if not s[3]]
            if _sols_pend:
                st.warning(f"**{len(_sols_pend)} solicitud(es) pendiente(s) de gestión.**")
            elif not _sols_admin:
                st.info("No hay solicitudes de colaboración todavía.")

            for _s in _sols_admin:
                _sid   = _s[0]
                _ts    = (_s[2] or "")[:16].replace("T", " ")
                _leida = bool(_s[3])
                try:
                    _pl = _json_f.loads(_s[1] or "{}")
                except Exception:
                    _pl = {}

                _ref_s    = _pl.get("ref_codigo") or "—"
                _inm_nom  = _pl.get("inmo_nombre") or "—"
                _inm_em   = _pl.get("inmo_email")  or ""
                _finca_id = _pl.get("finca_id")    or ""
                _inmo_id  = _pl.get("inmo_id")     or ""
                _notas_s  = _pl.get("notas")       or ""

                _label = f"{'✅' if _leida else '🆕'} [{_ref_s}] {_inm_nom} — {_ts}"
                with st.expander(_label, expanded=not _leida):
                    st.markdown(
                        f"**Inmo:** {_inm_nom}  \n"
                        f"**Email:** {_inm_em}  \n"
                        f"**REF finca:** `{_ref_s}`  \n"
                        f"**Notas:** {_notas_s or '—'}"
                    )
                    if not _leida and _finca_id and _inmo_id:
                        _bf1, _bf2 = st.columns(2)
                        with _bf1:
                            if st.button(
                                "✅ Confirmar reserva 72h",
                                key=f"mls_sol_ok_{_sid}",
                                type="primary",
                                use_container_width=True,
                            ):
                                try:
                                    _mls.update_finca_estado(_finca_id, "reservada")
                                    _mls.create_reserva(
                                        finca_id=_finca_id,
                                        inmo_colaboradora_id=_inmo_id,
                                        stripe_session_id=None,
                                        importe=0.0,
                                    )
                                    _mls.create_notificacion(
                                        destinatario_tipo="inmo",
                                        destinatario_id=_inmo_id,
                                        tipo_evento="solicitud_colaboracion_confirmada",
                                        payload=_json_f.dumps({
                                            "finca_id": _finca_id,
                                            "ref_codigo": _ref_s,
                                            "mensaje": "Tu solicitud de colaboración ha sido confirmada. "
                                                       "ArchiRapid se pondrá en contacto para coordinar el pago.",
                                        }),
                                    )
                                    _mls.marcar_leida(_sid)
                                    st.rerun()
                                except Exception as _ef2:
                                    st.error(f"Error al confirmar: {_ef2}")
                        with _bf2:
                            if st.button(
                                "❌ Rechazar",
                                key=f"mls_sol_no_{_sid}",
                                use_container_width=True,
                            ):
                                try:
                                    _mls.create_notificacion(
                                        destinatario_tipo="inmo",
                                        destinatario_id=_inmo_id,
                                        tipo_evento="solicitud_colaboracion_rechazada",
                                        payload=_json_f.dumps({
                                            "finca_id": _finca_id,
                                            "ref_codigo": _ref_s,
                                            "mensaje": "Tu solicitud de colaboración no pudo ser confirmada "
                                                       "en este momento. Contacta con ArchiRapid para más información.",
                                        }),
                                    )
                                    _mls.marcar_leida(_sid)
                                    st.rerun()
                                except Exception as _ef3:
                                    st.error(f"Error al rechazar: {_ef3}")
                    elif _leida:
                        st.caption("✅ Gestionada")
        except Exception as _ef_sec:
            st.warning(f"Error sección F: {_ef_sec}")