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