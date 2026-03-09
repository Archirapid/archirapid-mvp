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
        if password != "admin123":  # Contraseña de admin
            st.warning("🔒 Acceso restringido. Solo personal autorizado de ARCHIRAPID.")
            st.info("Si eres cliente o profesional, utiliza los botones de la página principal.")
            return
        st.success("✅ Acceso autorizado a Intranet")

    # PANEL DE GESTIÓN INTERNA
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📋 Gestión de Fincas", "🏗️ Gestión de Proyectos", "💰 Ventas y Transacciones", "📞 Consultas", "🛠️ Profesionales", "⚙️ Admin", "🎯 Waitlist", "📬 Actividad", "📊 Analytics"])

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
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Aprobar {p['id']}", key=f"approve_plot_{p['id']}"):
                                st.success("Finca aprobada (Admin)")
                        with col2:
                            if st.button(f"Rechazar {p['id']}", key=f"reject_plot_{p['id']}"):
                                st.info("Funcionalidad próximamente")
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
        try:
            st.header("Ventas y Transacciones")
            st.info("📊 Módulo de analítica en preparación. Próximamente verás aquí el flujo de caja.")
            conn = db_conn(); c = conn.cursor()
            c.execute("SELECT * FROM reservations ORDER BY created_at DESC")
            reservations = c.fetchall()
            conn.close()
            if reservations:
                for r in reservations:
                    st.write(f"**Reserva ID:** {r[0]} | **Finca:** {r[1]} | **Comprador:** {r[2]} | **Monto:** €{r[4]} | **Tipo:** {r[5]}")
                    if st.button(f"Confirmar {r[0]}", key=f"confirm_{r[0]}"):
                        st.success("Reserva confirmada (Admin)")
            else:
                st.info("Próximamente. No hay reservas.")
        except Exception as e:
            st.error(f"Error en Ventas y Transacciones: {e}")

    with tab4:
        try:
            st.header("Consultas y Soporte")
            st.info("📊 Módulo de analítica en preparación. Próximamente verás aquí el flujo de caja.")
            st.info("Próximamente. Panel de consultas y soporte.")
        except Exception as e:
            st.error(f"Error en Consultas y Soporte: {e}")

    with tab5:
        try:
            st.header("🛠️ Gestión de Profesionales Registrados")
            
            # Función para obtener profesionales
            def get_service_providers():
                conn = db_conn()
                c = conn.cursor()
                c.execute("""
                    SELECT name, company, specialty, experience_years, service_area, certifications
                    FROM service_providers
                    ORDER BY name
                """)
                providers = c.fetchall()
                conn.close()
                return providers
            
            providers = get_service_providers()
            
            if providers:
                # Filtro por especialidad
                specialties = list(set([p[2] for p in providers if p[2]]))  # Especialidades únicas
                selected_specialty = st.selectbox("Filtrar por Especialidad", ["Todas"] + sorted(specialties), key="filter_specialty")
                
                # Filtrar datos
                if selected_specialty != "Todas":
                    filtered_providers = [p for p in providers if p[2] == selected_specialty]
                else:
                    filtered_providers = providers
                
                # Preparar datos para tabla
                table_data = []
                for p in filtered_providers:
                    table_data.append({
                        "Nombre": p[0],
                        "Empresa": p[1] or "Independiente",
                        "Especialidad": p[2],
                        "Años Exp.": p[3],
                        "Ciudad": p[4] or "No especificada",
                        "Certificaciones": p[5] or "Ninguna"
                    })
                
                st.dataframe(table_data, use_container_width=True)
                st.success(f"Mostrando {len(filtered_providers)} profesionales")
            else:
                st.info("No hay profesionales registrados aún.")
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
                cur.execute("UPDATE plots SET status = 'disponible', buyer_email = NULL, reserved_by = NULL")
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
            _cw = _sq3w.connect("database.db")
            _dfw = _pdw.read_sql_query(
                "SELECT name, email, profile, created_at, approved FROM waitlist ORDER BY created_at DESC",
                _cw
            )
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
            st.error(f"Error cargando waitlist: {_ew}")
            st.code(traceback.format_exc())

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
TELEGRAM_BOT_TOKEN = "8611167436:AAGohKZ9nKIhv_YbDNMqzcgkHZeIvr1V6j0"
TELEGRAM_CHAT_ID   = "5712417665"
```
""")
        except Exception:
            pass

        st.markdown("---")
        import sqlite3 as _sq3a
        import pandas as _pda

        _ca = _sq3a.connect("database.db", timeout=10)

        # Últimos registros
        st.subheader("👤 Últimos registros de usuarios")
        try:
            _df_users = _pda.read_sql_query(
                "SELECT name, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 20",
                _ca
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
            _df_res = _pda.read_sql_query(
                """SELECT r.buyer_name, r.buyer_email, p.title as finca, r.amount, r.kind, r.created_at
                   FROM reservations r LEFT JOIN plots p ON r.plot_id=p.id
                   ORDER BY r.created_at DESC LIMIT 20""",
                _ca
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
            _df_wl = _pda.read_sql_query(
                "SELECT name, email, profile, created_at FROM waitlist ORDER BY created_at DESC LIMIT 10",
                _ca
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

        try:
            _db9 = _sq9.connect("database.db", timeout=10)

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

            k5, k6, k7, k8 = st.columns(4)
            k5.metric("🛒 Reservas totales", _n_res)
            k6.metric("✅ Compras efectivas", _n_purchase)
            k7.metric("🎯 Waitlist total", _n_waitlist, delta=f"{_n_approved} aprobados")
            k8.metric("📐 Conversión reserva→compra",
                      f"{(_n_purchase/_n_res*100):.1f}%" if _n_res else "—")

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
                    _df_roles = _pd9.read_sql_query(
                        "SELECT role as Rol, COUNT(*) as Total FROM users GROUP BY role ORDER BY Total DESC",
                        _db9
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
                    _df_prov = _pd9.read_sql_query(
                        "SELECT province as Provincia, COUNT(*) as Fincas FROM plots GROUP BY province ORDER BY Fincas DESC",
                        _db9
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
                _df_kind = _pd9.read_sql_query(
                    "SELECT kind as Tipo, COUNT(*) as Operaciones, COALESCE(SUM(amount),0) as Importe FROM reservations GROUP BY kind",
                    _db9
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
                _df_daily = _pd9.read_sql_query(
                    """SELECT DATE(created_at) as Fecha, COUNT(*) as Registros
                       FROM users
                       WHERE created_at >= DATE('now', '-30 days')
                       GROUP BY DATE(created_at)
                       ORDER BY Fecha""",
                    _db9
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
                _df_top = _pd9.read_sql_query(
                    "SELECT title as Finca, province as Provincia, m2 as 'm²', price as 'Precio (€)', status as Estado FROM plots ORDER BY price DESC LIMIT 10",
                    _db9
                )
                if not _df_top.empty:
                    st.dataframe(_df_top, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin fincas en el catálogo.")
            except Exception as _et:
                st.warning(f"Top fincas: {_et}")

            _db9.close()

        except Exception as _e9:
            st.error(f"Error en Analytics: {_e9}")