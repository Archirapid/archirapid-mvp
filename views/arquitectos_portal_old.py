import streamlit as st
from src import db
import uuid

st.set_page_config(page_title='Portal Arquitectos')

st.title('Portal de Arquitectos')

# Cargar planes
planes = []
try:
    planes = db.obtener_todos_los_planes()
except Exception as e:
    st.error('No se pudieron cargar los planes: ' + str(e))

plan_options = {p['id']: f"{p['nombre_plan']} — ${p['precio_mensual']} / mes" for p in planes}

with st.form('registro_arquitecto'):
    nombre = st.text_input('Nombre completo')
    email = st.text_input('Email')
    telefono = st.text_input('Teléfono')
    especialidad = st.text_input('Especialidad')
    plan_id = st.selectbox('Selecciona un plan', options=list(plan_options.keys()), format_func=lambda x: plan_options.get(x, 'Sin plan')) if planes else None
    submitted = st.form_submit_button('Registrarme')

if submitted:
    if not nombre or not email:
        st.warning('Nombre y email son obligatorios')
    else:
        ok = db.guardar_nuevo_arquitecto(nombre, email, telefono, especialidad, plan_id)
        if ok:
                # auto-login after registration
                datos_reg = db.obtener_datos_arquitecto(email)
                if datos_reg:
                    st.session_state['logged_in_architect'] = True
                    st.session_state['architect_id'] = datos_reg.get('id')
                    st.session_state['architect_name'] = nombre
                st.success('Registro realizado correctamente')
                st.experimental_rerun()
    with st.form("login_arquitecto_form"):
        email_login = st.text_input("Email", value="", placeholder="tu@estudio.com")
        submitted_login = st.form_submit_button("Acceder")

        if submitted_login:
            if not email_login or "@" not in email_login:
                st.error("Introduce un email válido.")
            else:
                datos = db.obtener_datos_arquitecto(email_login)
                if datos:
                    st.session_state['logged_in_architect'] = True
                    st.session_state['architect_id'] = datos['id']
                    st.session_state['architect_name'] = datos['nombre']
                    st.success(f"¡Bienvenido de nuevo, {datos['nombre']}! Ahora puedes subir proyectos.")
                    st.experimental_rerun()
                else:
                    st.error("No se encontró ningún arquitecto con ese email. Por favor regístrate.")


# Dashboard / panel del arquitecto (migrado desde pages/subir_proyecto.py)
def render_architect_dashboard():
    import streamlit as st
    import os
    import time
    import re
    from src import db

    # Protección de acceso
    if not st.session_state.get('logged_in_architect'):
        st.error('❌ Acceso denegado. Por favor, inicia sesión como Arquitecto para subir proyectos.')
        st.stop()

    # Identidad del arquitecto desde sesión
    architect_id = st.session_state.get('architect_id')
    nombre_arquitecto = st.session_state.get('architect_name', 'Arquitecto')
    st.header(f"Panel de Proyectos de {nombre_arquitecto}")

    # Comprobar límite de proyectos (usa architect_id de sesión)
    can_upload = db.verificar_limite_proyectos(architect_id)

    # Obtener plan_id, límite y contador actual para mostrar información
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT plan_id FROM arquitectos WHERE id = ?", (architect_id,))
    row = cur.fetchone()
    plan_id = None
    if row:
        try:
            plan_id = row['plan_id']
        except Exception:
            plan_id = row[0]

    limite = None
    if plan_id is not None:
        cur.execute("SELECT limite_proyectos FROM planes WHERE id = ?", (plan_id,))
        p = cur.fetchone()
        if p:
            try:
                limite = p['limite_proyectos']
            except Exception:
                limite = p[0]

    cur.execute("SELECT COUNT(1) as cnt FROM proyectos WHERE arquitecto_id = ?", (architect_id,))
    cnt_row = cur.fetchone()
    current_count = 0
    if cnt_row:
        try:
            current_count = cnt_row['cnt']
        except Exception:
            current_count = cnt_row[0]
    conn.close()

    if not can_upload:
        st.error(f"Has alcanzado el límite de {limite if limite is not None else 'X'} proyectos para tu plan. Actualiza tu plan para subir más.")
        st.stop()

    # Formulario de subida de proyecto (PDF)
    with st.form('subir_proyecto_form'):
        titulo = st.text_input('Título', value='')
        estilo = st.text_input('Estilo', value='')
        m2_construidos = st.number_input('M² construidos', min_value=0.0, step=1.0, format='%.2f')
        presupuesto_ejecucion = st.number_input('Presupuesto de ejecución (€)', min_value=0.0, step=100.0, format='%.2f')
        m2_parcela_minima = st.number_input('M² parcela mínima', min_value=0.0, step=1.0, format='%.2f')
        alturas = st.number_input('Alturas', min_value=1, step=1)
        pdf_file = st.file_uploader('PDF del proyecto', type=['pdf'])
        submitted = st.form_submit_button('Subir proyecto')

    if submitted:
        if not titulo:
            st.warning('El título es obligatorio')
        elif not pdf_file:
            st.warning('Adjunta el PDF del proyecto')
        else:
            uploads_dir = os.path.join('uploads', 'projects')
            os.makedirs(uploads_dir, exist_ok=True)
            safe_title = re.sub(r'[^A-Za-z0-9_-]', '_', titulo)[:50]
            ts = int(time.time())
            filename = f"{architect_id}_{safe_title}_{ts}.pdf"
            filepath = os.path.join(uploads_dir, filename)
            try:
                with open(filepath, 'wb') as f:
                    f.write(pdf_file.getbuffer())
            except Exception as e:
                st.error(f"Error guardando el PDF: {e}")
                filepath = None

            if filepath:
                ok = db.guardar_nuevo_proyecto(architect_id, titulo, estilo, m2_construidos,
                                               presupuesto_ejecucion, m2_parcela_minima, alturas, filepath)
                if ok:
                    # Recalcular contador y límite usando architect_id de sesión
                    conn = db.get_conn(); cur = conn.cursor()
                    cur.execute("SELECT COUNT(1) as cnt FROM proyectos WHERE arquitecto_id = ?", (architect_id,))
                    row_cnt = cur.fetchone()
                    try:
                        cnt_val = row_cnt['cnt']
                    except Exception:
                        cnt_val = row_cnt[0]

                    cur.execute("SELECT plan_id FROM arquitectos WHERE id = ?", (architect_id,))
                    r = cur.fetchone()
                    p_id = None
                    if r:
                        try:
                            p_id = r['plan_id']
                        except Exception:
                            p_id = r[0]

                    limite_val = None
                    if p_id is not None:
                        cur.execute("SELECT limite_proyectos FROM planes WHERE id = ?", (p_id,))
                        p2 = cur.fetchone()
                        if p2:
                            try:
                                limite_val = p2['limite_proyectos']
                            except Exception:
                                limite_val = p2[0]
                    conn.close()
                    remaining = (int(limite_val) - int(cnt_val)) if limite_val is not None else 'N/A'
                    st.success(f"¡Proyecto {titulo} subido con éxito! (Quedan {remaining} proyectos disponibles en tu plan)")
                else:
                    st.error('Error al guardar el proyecto en la base de datos. Revisa la consola del servidor.')


# Si ya está logueado, mostrar el dashboard automáticamente
if st.session_state.get('logged_in_architect'):
    try:
        render_architect_dashboard()
    except Exception:
        # Evitar que errores del panel rompan la página de registro
        st.warning('No se pudo renderizar el panel del arquitecto.')