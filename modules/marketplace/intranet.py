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
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Gestión de Fincas", "🏗️ Gestión de Proyectos", "💰 Ventas y Transacciones", "📞 Consultas", "🛠️ Profesionales", "⚙️ Admin"])

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
            import os as _os

            # Listar modelos actuales
            _conn = _db_conn()
            _cur = _conn.cursor()
            _cur.execute("SELECT id, name, m2, rooms, bathrooms, floors, material, price, active, image_path FROM prefab_catalog ORDER BY m2")
            prefabs = _cur.fetchall()
            _conn.close()

            st.markdown(f"**{len(prefabs)} modelos en catálogo:**")

            for pf in prefabs:
                pf_id, name, m2, rooms, bathrooms, floors, material, price, active, image_path = pf
                with st.expander(f"{'✅' if active else '🔴'} [{pf_id}] {name} — {m2} m² · {material} · €{price:,.0f}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        new_name     = st.text_input("Nombre",      value=name,      key=f"pf_name_{pf_id}")
                        new_m2       = st.number_input("m²",        value=float(m2), key=f"pf_m2_{pf_id}", min_value=10.0, step=5.0)
                        new_price    = st.number_input("Precio (€)", value=float(price), key=f"pf_price_{pf_id}", min_value=0.0, step=1000.0)
                        new_rooms    = st.number_input("Habitaciones", value=int(rooms), key=f"pf_rooms_{pf_id}", min_value=1, max_value=10)
                        new_baths    = st.number_input("Baños",      value=int(bathrooms), key=f"pf_baths_{pf_id}", min_value=1, max_value=6)
                        new_floors   = st.number_input("Plantas",    value=int(floors), key=f"pf_floors_{pf_id}", min_value=1, max_value=4)
                        new_material = st.selectbox("Material", ["Madera","Modular acero","Contenedor","Hormigón prefab","Mixto"],
                                                    index=["Madera","Modular acero","Contenedor","Hormigón prefab","Mixto"].index(material) if material in ["Madera","Modular acero","Contenedor","Hormigón prefab","Mixto"] else 0,
                                                    key=f"pf_mat_{pf_id}")
                        new_active   = st.checkbox("Activo (visible en catálogo)", value=bool(active), key=f"pf_active_{pf_id}")
                    with c2:
                        # Foto actual
                        if image_path and _os.path.exists(image_path):
                            st.image(image_path, width=160, caption="Foto actual")
                        else:
                            st.info("Sin foto")
                        # Subir foto nueva
                        new_img = st.file_uploader("Subir foto", type=["jpg","jpeg","png","webp"], key=f"pf_img_{pf_id}")
                        if new_img:
                            import pathlib as _pl
                            _dest_dir = _pl.Path("uploads/prefab")
                            _dest_dir.mkdir(parents=True, exist_ok=True)
                            _dest = _dest_dir / f"prefab_{pf_id}_{new_img.name}"
                            with open(_dest, "wb") as _f:
                                _f.write(new_img.read())
                            st.success(f"Foto guardada: {_dest}")
                            image_path = str(_dest)

                    if st.button(f"💾 Guardar cambios — {name}", key=f"pf_save_{pf_id}"):
                        _conn2 = _db_conn()
                        _cur2 = _conn2.cursor()
                        _cur2.execute("""
                            UPDATE prefab_catalog
                            SET name=?, m2=?, rooms=?, bathrooms=?, floors=?, material=?, price=?, active=?, image_path=?
                            WHERE id=?
                        """, (new_name, new_m2, new_rooms, new_baths, new_floors, new_material, new_price, int(new_active), image_path, pf_id))
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
                    nf_price    = st.number_input("Precio (€)", min_value=0.0, value=80000.0, step=1000.0)
                    nf_desc     = st.text_area("Descripción corta")
                with nf_c2:
                    nf_rooms    = st.number_input("Habitaciones", min_value=1, max_value=10, value=3)
                    nf_baths    = st.number_input("Baños", min_value=1, max_value=6, value=1)
                    nf_floors   = st.number_input("Plantas", min_value=1, max_value=4, value=1)
                    nf_material = st.selectbox("Material", ["Madera","Modular acero","Contenedor","Hormigón prefab","Mixto"])
                    nf_img      = st.file_uploader("Foto del modelo", type=["jpg","jpeg","png","webp"])
                if st.form_submit_button("➕ Añadir al catálogo", type="primary"):
                    if nf_name:
                        nf_img_path = "assets/branding/logo.png"
                        if nf_img:
                            import pathlib as _pl2
                            _d = _pl2.Path("uploads/prefab")
                            _d.mkdir(parents=True, exist_ok=True)
                            _p = _d / f"prefab_new_{nf_img.name}"
                            with open(_p, "wb") as _f2:
                                _f2.write(nf_img.read())
                            nf_img_path = str(_p)
                        _conn4 = _db_conn()
                        _cur4 = _conn4.cursor()
                        _cur4.execute("""
                            INSERT INTO prefab_catalog (name, m2, rooms, bathrooms, floors, material, price, description, image_path)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (nf_name, nf_m2, nf_rooms, nf_baths, nf_floors, nf_material, nf_price, nf_desc, nf_img_path))
                        _conn4.commit()
                        _conn4.close()
                        st.success(f"✅ Modelo '{nf_name}' añadido al catálogo.")
                        st.rerun()
                    else:
                        st.error("El nombre es obligatorio.")

        except Exception as e:
            st.error(f"Error gestionando catálogo de prefabricadas: {e}")