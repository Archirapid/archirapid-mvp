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
        st.title("🔐 Acceso Administrativo")
        with st.form("admin_login_form"):
            admin_email = st.text_input("Email", placeholder="admin@archirapid.com")
            admin_password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("🚀 Acceder como Admin", type="primary")
            if submitted:
                user = authenticate_user(admin_email, admin_password)
                if user and user.get('role') == 'admin':
                    st.session_state['role'] = 'admin'
                    st.session_state['logged_in'] = True
                    st.session_state['user_email'] = admin_email
                    st.session_state['user_name'] = user.get('name', 'Admin')
                    st.session_state['selected_page'] = "Intranet"
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas o sin permisos de administrador.")
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
    st.markdown("¿No tienes cuenta? [Regístrate aquí](?page=Registro%20de%20Usuario)  ·  [¿Olvidaste tu contraseña?](?page=recuperar_contrasena)")

def authenticate_user(email, password):
    try:
        conn = db_conn()
        c = conn.cursor()
        c.execute("SELECT id, email, name, role, password_hash FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()

        # Soportar sqlite3.Row, tuple y dict (modo Postgres)
        def _get(r, key, idx):
            try:
                return r[key]
            except (KeyError, TypeError, IndexError):
                return r[idx]

        if row and check_password_hash(_get(row, 'password_hash', 4), password):
            return {
                "id": _get(row, 'id', 0),
                "email": _get(row, 'email', 1),
                "name": _get(row, 'name', 2),
                "role": _get(row, 'role', 3),
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

    # precargar valores si vienen de un formulario anterior
    pre_nombre = st.session_state.pop('auth_prefill_name', '')
    pre_email = st.session_state.pop('auth_prefill_email', '')
    pre_telefono = st.session_state.pop('auth_prefill_phone', '')

    with st.form("registro_form"):
        st.subheader("📋 Información Personal")

        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre completo *", placeholder="Tu nombre completo", value=pre_nombre)
        with col2:
            email = st.text_input("Email *", placeholder="tu@email.com", value=pre_email)

        telefono = st.text_input("Teléfono", placeholder="+34 600 000 000", value=pre_telefono)
        direccion = st.text_input("Dirección", placeholder="Calle, Ciudad, Provincia")

        st.subheader("🔐 Credenciales de Acceso")
        password = st.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
        password_confirm = st.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")

        st.subheader("👤 Tipo de Usuario")
        # si venimos del formulario de arquitectos forzamos ese perfil
        if st.session_state.get('login_role') == 'owner':
            st.info("Registrándote como Propietario")
            tipo_usuario = "Propietario (Subo fincas)"
            empresa = ""
            especialidad = ""
        elif st.session_state.get('login_role') == 'architect':
            # ocultar selector, ya sabemos que es arquitecto
            tipo_usuario = "Arquitecto (Vendo proyectos)"
            st.info("Registrándote como Arquitecto")
            empresa = st.text_input("Empresa/Estudio", placeholder="Nombre de tu empresa")
            especialidad = st.selectbox("Especialidad", ["Arquitectura Residencial", "Arquitectura Comercial", "Urbanismo", "Interiorismo", "Otros"])
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

        st.markdown("---")
        gdpr_ok = st.checkbox(
            "He leído y acepto la [Política de Privacidad](?page=privacidad) y el tratamiento de mis datos personales "
            "conforme al RGPD (UE) 2016/679. Puedo solicitar su eliminación en hola@archirapid.com. *",
            key="gdpr_consent"
        )

        submitted = st.form_submit_button("🚀 Registrarme y Acceder", type="primary")

        if submitted:
            if not gdpr_ok:
                st.error("Debes aceptar la Política de Privacidad para continuar.")
                return

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

                try:
                    from modules.marketplace.email_notify import notify_new_registration
                    notify_new_registration(nombre, email, role)
                except Exception:
                    pass

                st.success("🎉 ¡Registro completado exitosamente!")

                # ANCLAJE PERMANENTE: siempre forzamos valores de owner
                st.session_state['logged_in'] = True
                st.session_state['role'] = 'owner'  # Forzado manual
                st.session_state['selected_page'] = "🏠 Propietarios"
                st.query_params["page"] = "🏠 Propietarios"

                # preservamos también la lógica anterior por compatibilidad
                st.session_state["email"] = email
                if role == 'owner':
                    # 🛡️ Marca sesión como autenticada
                    st.session_state["authenticated"] = True
                elif role == 'architect':
                    st.session_state['arquitecto_id'] = email
                    st.session_state["authenticated"] = True
                else:
                    st.session_state["authenticated"] = True
                st.rerun()

            except Exception as e:
                st.error(f"Error en el registro: {e}")

    st.markdown("---")
    st.markdown("¿Ya tienes cuenta? [Inicia sesión aquí](?page=Iniciar%20Sesión)")