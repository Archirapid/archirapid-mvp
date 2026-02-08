import streamlit as st
from modules.marketplace.utils import get_user_by_email, db_conn
from werkzeug.security import check_password_hash

# Función de navegación unificada
def navigate_to(page_name):
    st.session_state["selected_page"] = page_name
    if page_name == "🏠 Propietarios":
        st.session_state['role'] = "owner"
        st.session_state['logged_in'] = True
    elif page_name in ["👤 Panel de Cliente", "Registro de Usuario", "Arquitectos (Marketplace)", "Intranet"]:
        st.query_params["page"] = page_name
    st.rerun()

def show_login():
    # 🛑 BLINDAJE: si ya hay rol, no volver a registrar
    if st.session_state.get("role"):
        return
    if st.session_state.get('login_role') == 'admin':
        # Login especial para admin
        st.title("🔐 Acceso Administrativo")
        admin_password = st.text_input("Contraseña de Acceso Administrativo", type="password", key="admin_pass")
        if st.button("🚀 Acceder como Admin", key="admin_login_btn"):
            if admin_password == "admin123":
                st.session_state['role'] = 'admin'
                st.session_state['logged_in'] = True
                st.session_state['selected_page'] = "Intranet"
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        return
    
    st.title("🔐 Iniciar Sesión")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña")

        submitted = st.form_submit_button("🚀 Iniciar Sesión", type="primary")

        if submitted:
            if not email or not password:
                st.error("Por favor, completa todos los campos.")
                return

            user = authenticate_user(email, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = email
                st.session_state["user_name"] = user['name']  # Guardar nombre del usuario
                st.session_state["role"] = user['role']

                user_role = user.get('role')
                if user_role == 'admin':
                    st.query_params["page"] = "Intranet"
                    st.session_state['selected_page'] = "Intranet"
                elif user_role == 'architect':
                    st.query_params["page"] = "Arquitectos (Marketplace)"
                    st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                elif user_role == 'owner':
                    st.query_params["page"] = "🏠 Propietarios"
                    st.session_state['selected_page'] = "🏠 Propietarios"
                elif user_role == 'services':
                    st.query_params["page"] = "👤 Panel de Proveedor"
                    st.session_state['selected_page'] = "👤 Panel de Proveedor"
                elif user_role == 'client':
                    st.query_params["page"] = "👤 Panel de Cliente"
                    st.session_state['selected_page'] = "👤 Panel de Cliente"
                else:
                    st.query_params["page"] = "👤 Panel de Cliente"
                    st.session_state['selected_page'] = "👤 Panel de Cliente"
                st.rerun()
            else:
                st.error("Credenciales incorrectas. Verifica tu email y contraseña.")

    st.markdown("---")
    st.markdown("### 💡 ¿Acabas de comprar una finca/proyecto?")
    st.info("**Ya estabas diseñando?** Usa el email y la contraseña que configuraste durante el pago y accede para avanzar con tu proyecto.")
    st.markdown("---")
    st.markdown("¿No tienes cuenta? [Regístrate aquí](?page=Registro%20de%20Usuario)")

def authenticate_user(email, password):
    try:
        conn = db_conn()
        c = conn.cursor()
        c.execute("SELECT id, email, name, role, password_hash FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()

        if row and check_password_hash(row[4], password):
            return {
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "role": row[3]
            }
    except Exception as e:
        st.error(f"Error de autenticación: {e}")

    return None

def show_registration():
    # 🛑 BLINDAJE: si ya hay rol, no volver a registrar
    if st.session_state.get("role"):
        return
    if st.session_state.get("authenticated"):
        return
    st.title("📝 Registro de Usuario")

    with st.form("registro_form"):
        st.subheader("📋 Información Personal")

        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre completo *", placeholder="Tu nombre completo")
        with col2:
            email = st.text_input("Email *", placeholder="tu@email.com")

        telefono = st.text_input("Teléfono", placeholder="+34 600 000 000")
        direccion = st.text_input("Dirección", placeholder="Calle, Ciudad, Provincia")

        st.subheader("🔐 Credenciales de Acceso")
        password = st.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
        password_confirm = st.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")

        st.subheader("👤 Tipo de Usuario")
        if st.session_state.get('login_role') == 'owner':
            st.info("Registrándote como Propietario")
            tipo_usuario = "Propietario (Subo fincas)"
            empresa = ""
            especialidad = ""
        else:
            role_to_index = {'client': 0, 'architect': 1, 'owner': 2}
            tipo_usuario = st.selectbox(
                "Selecciona tu perfil *",
                ["Cliente (Busco proyectos)", "Arquitecto (Vendo proyectos)", "Propietario (Subo fincas)"],
                index=role_to_index.get(st.session_state.get('login_role'), 0)
            )
            if tipo_usuario == "Arquitecto (Vendo proyectos)":
                empresa = st.text_input("Empresa/Estudio", placeholder="Nombre de tu empresa")
                especialidad = st.selectbox("Especialidad", ["Arquitectura Residencial", "Arquitectura Comercial", "Urbanismo", "Interiorismo", "Otros"])
            else:
                empresa = ""
                especialidad = ""

        submitted = st.form_submit_button("🚀 Registrarme y Acceder", type="primary")

        if submitted:
            if not nombre or not email or not password:
                st.error("Por favor, completa los campos obligatorios marcados con *.")
                return

            if password != password_confirm:
                st.error("Las contraseñas no coinciden.")
                return

            if len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
                return

            if st.session_state.get('login_role') == 'owner':
                role = "owner"
            else:
                if tipo_usuario == "Cliente (Busco proyectos)":
                    role = "client"
                elif tipo_usuario == "Arquitecto (Vendo proyectos)":
                    role = "architect"
                else:
                    role = "owner"

            try:
                from werkzeug.security import generate_password_hash
                hashed_password = generate_password_hash(password)

                conn = db_conn()
                c = conn.cursor()

                c.execute("""
                    INSERT INTO users (email, name, role, is_professional, password_hash, phone, address, company, specialty, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    email, nombre, role,
                    1 if role in ['architect', 'owner'] else 0,
                    hashed_password, telefono, direccion, empresa, especialidad
                ))

                conn.commit()
                conn.close()

                st.success("🎉 ¡Registro completado exitosamente!")

                # FORZADO BRUTO PARA EL JEFE
                st.session_state["logged_in"] = True
                st.session_state["email"] = email
                st.session_state["role"] = role
                if role == 'owner':
                    st.query_params["page"] = "🏠 Propietarios"
                    st.session_state["selected_page"] = "🏠 Propietarios"
                    # 🛡️ Marca sesión como autenticada
                    st.session_state["authenticated"] = True
                else:
                    st.query_params["page"] = "🏠 Inicio / Marketplace"
                    st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
                st.rerun()

            except Exception as e:
                st.error(f"Error en el registro: {e}")

    st.markdown("---")
    st.markdown("¿Ya tienes cuenta? [Inicia sesión aquí](?page=Iniciar%20Sesión)")