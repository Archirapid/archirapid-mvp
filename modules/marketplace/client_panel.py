# modules/marketplace/client_panel.py
import streamlit as st
try:
    from modules.marketplace.utils import db_conn
except ImportError:
    # Fallback si falla el import
    import sys
    sys.path.append(r"C:/ARCHIRAPID_PROYECT25")
    from src import db as db_module
    def db_conn():
        return db_module.get_conn()
import json
import os
from pathlib import Path
from modules.marketplace.compatibilidad import get_proyectos_compatibles

def generate_3d_viewer_html(model_url):
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; background-color: #f0f0f0; }}
            canvas {{ display: block; }}
            #info {{ position: absolute; top: 10px; width: 100%; text-align: center; font-family: sans-serif; pointer-events: none; }}
        </style>
    </head>
    <body>
        <div id="info">Cargando Proyecto 3D...</div>
        <script type="module">
            import * as THREE from 'https://cdn.skypack.dev/three@0.128.0';
            import {{ GLTFLoader }} from 'https://cdn.skypack.dev/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';
            import {{ OrbitControls }} from 'https://cdn.skypack.dev/three@0.128.0/examples/jsm/controls/OrbitControls.js';                                                                                                                  
            const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xeeeeee);
        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 10000);
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.outputEncoding = THREE.sRGBEncoding;
        document.body.appendChild(renderer.domElement);                                        
        // LUCES (Una ambiental y dos direccionales para evitar sombras negras)
        scene.add(new THREE.AmbientLight(0xffffff, 1.0));
        const light1 = new THREE.DirectionalLight(0xffffff, 0.8);
        light1.position.set(100, 100, 100);
        scene.add(light1);                                                                                            
        const controls = new OrbitControls(camera, renderer.domElement);
        
        const loader = new GLTFLoader();
        console.log("Intentando cargar:", "{model_url}");                                                                                                    
        loader.load("{model_url}", (gltf) => {{
            const model = gltf.scene;
            scene.add(model);                                                                                      
            // --- EL TRUCO DEL CENTRADO ---
            const box = new THREE.Box3().setFromObject(model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            
            // Ajustamos la cámara según el tamaño real del modelo
            const cameraZ = maxDim * 2; 
            camera.position.set(center.x + maxDim, center.y + maxDim, center.z + cameraZ);
            camera.lookAt(center);
            
            controls.target.copy(center);
            controls.update();
            
            document.getElementById('info').innerText = "Modelo Cargado Correctamente";
            console.log("Modelo centrado en:", center, "Tamaño:", size);
        }}, undefined, (error) => {{
            console.error("Error cargando GLB:", error);
            document.getElementById('info').innerText = "Error al visualizar el modelo";
        }});                                                                                                                   
        function animate() {{
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }}
        animate();                                                                                                       
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>
'''

def show_full_client_dashboard(client_email):
    """Muestra el panel completo del cliente para usuarios ya logueados"""
    # Panel de cliente logueado
    user_role = st.session_state.get("user_role", "buyer")
    has_transactions = st.session_state.get("has_transactions", False)
    has_properties = st.session_state.get("has_properties", False)
    
    # Botón de cerrar sesión en sidebar
    with st.sidebar:
        if st.button("🚪 Cerrar Sesión", width='stretch', key="logout_button"):
            st.session_state["client_logged_in"] = False
            for key in ["client_email", "user_role", "has_transactions", "has_properties", "selected_project_for_panel"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Mostrar rol del usuario
    role_emoji = "🛒" if user_role == "buyer" else "🏠"
    role_text = "Comprador" if user_role == "buyer" else "Propietario"
    st.success(f"{role_emoji} **Bienvenido/a {role_text}** - {client_email}")
    
    # � QUIRÚRGICO: Manejar proyecto seleccionado desde query params para usuarios logueados
    selected_project = st.query_params.get("selected_project")
    if selected_project and not st.session_state.get("selected_project_for_panel"):
        st.session_state["selected_project_for_panel"] = selected_project
        # Limpiar query param para evitar conflictos futuros
        if "selected_project" in st.query_params:
            del st.query_params["selected_project"]
    
    # �🔍 MODO 3: Usuario interesado en un proyecto (sin transacciones)
    selected_project_for_panel = st.session_state.get("selected_project_for_panel")
    if user_role == "buyer" and not has_transactions and selected_project_for_panel:
        show_selected_project_panel(client_email, selected_project_for_panel)
        return
    
    # Contenido diferente según el rol
    if user_role == "buyer":
        show_buyer_panel(client_email)
    elif user_role == "owner":
        show_owner_panel_v2(client_email)
    else:
        st.error("Error: No se pudo determinar el tipo de panel apropiado")
        st.stop()

def main():
    st.title("👤 Panel de Cliente - ARCHIRAPID")

    # BYPASS TOTAL: Si venimos de un pago o estamos logueados, entramos directo
    email_final = st.session_state.get('user_email') or st.session_state.get('auto_owner_email')

    if st.session_state.get('logged_in') and st.session_state.get('role') == 'client' and email_final:
        show_full_client_dashboard(email_final)
        return

    # Auto-login si viene de query params con owner_email
    if "auto_owner_email" in st.session_state and not st.session_state.get("client_logged_in", False):
        auto_email = st.session_state["auto_owner_email"]
        # Verificar si el email tiene transacciones O es propietario con fincas
        conn = db_conn()
        cursor = conn.cursor()

        # Buscar transacciones de COMPRA O RESERVA (este panel es para compradores y reservadores)
        cursor.execute("SELECT * FROM reservations WHERE buyer_email=?", (auto_email,))
        transactions = cursor.fetchall()

        # NO auto-login para propietarios - ellos tienen panel separado
        owner_plots = []

        conn.close()

        # Auto-login SOLO si tiene transacciones de COMPRA verificadas
        if transactions:
            st.session_state["client_logged_in"] = True
            st.session_state["client_email"] = auto_email
            st.session_state["user_role"] = "buyer"
            st.session_state["has_transactions"] = len(transactions) > 0
            st.session_state["has_properties"] = False

            st.info(f"🔄 Auto-acceso concedido como comprador para {auto_email}")

            # Limpiar el estado de auto-login
            del st.session_state["auto_owner_email"]

    # Verificar si viene de vista previa de proyecto
    selected_project = st.query_params.get("selected_project")
    if selected_project and not st.session_state.get("client_logged_in", False):
        st.info("🔍 Proyecto seleccionado detectado. Por favor inicia sesión para continuar.")
    
    # Login simple por email
    if "client_logged_in" not in st.session_state:
        st.session_state["client_logged_in"] = False
    
    if not st.session_state["client_logged_in"]:
        st.subheader("🔐 Acceso al Panel de Cliente")
        st.info("Introduce el email que usaste al realizar tu compra/reserva")
        
        email = st.text_input("Email de cliente", placeholder="tu@email.com")
        
        if st.button("Acceder", type="primary"):
            if email:
                # Verificar si el email tiene transacciones, propiedades O está registrado como cliente
                conn = db_conn()
                cursor = conn.cursor()
                
                # Verificar si el email tiene transacciones de COMPRA O RESERVA (clientes que han comprado o reservado)
                cursor.execute("SELECT * FROM reservations WHERE buyer_email=?", (email,))
                transactions = cursor.fetchall()
                
                # NO permitir acceso a propietarios aquí - ellos tienen su propio panel
                owner_plots = []  # No buscar propiedades de propietario
                
                # NO verificar registro como cliente genérico - solo compras reales
                is_registered_client = False
                
                conn.close()
                
                # Permitir acceso SOLO si tiene transacciones de COMPRA verificadas
                if transactions:
                    st.session_state["client_logged_in"] = True
                    st.session_state["client_email"] = email
                    st.session_state["user_role"] = "buyer"
                    st.session_state["has_transactions"] = len(transactions) > 0
                    st.session_state["has_properties"] = False  # No es propietario en este panel
                    
                    st.success(f"✅ Acceso concedido como cliente para {email}")
                    st.rerun()
                else:
                    st.error("❌ Acceso denegado. Este panel es exclusivo para clientes que han realizado compras o reservas.")
                    st.info("Si eres propietario, accede desde la página principal. Si has comprado o reservado un proyecto, verifica tu email.")
            else:
                st.error("Por favor introduce tu email")
        
        st.markdown("---")
        st.info("💡 **Nota:** Si acabas de realizar una compra, usa el email que proporcionaste en el formulario de datos personales.")
        st.info("Por favor inicia sesión para acceder al panel.")
        # st.stop()  # Comentado para permitir que la página se cargue

def show_selected_project_panel(client_email, project_id):
    """Panel completo para mostrar proyecto seleccionado con todos los detalles"""
    from modules.marketplace.project_detail import get_project_by_id
    from modules.marketplace import ai_engine_groq as ai
    from modules.marketplace.plot_detail import get_project_images

    # BOTÓN PARA VOLVER A LA BÚSQUEDA
    col_back, col_empty = st.columns([1, 4])
    with col_back:
        if st.button("⬅️ Volver a Proyectos", key="back_to_search"):
            st.session_state['selected_project_for_panel'] = None
            st.session_state['show_project_search'] = True
            st.rerun()

    # Obtener datos completos del proyecto incluyendo modelo 3D
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, architect_id, title, description, area_m2, price, 
               foto_principal, galeria_fotos, memoria_pdf, planos_pdf, 
               planos_dwg, modelo_3d_glb, vr_tour, ocr_text, created_at
        FROM projects
        WHERE id = ?
    """, (project_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        st.error("Proyecto no encontrado")
        return

    # Parsear galeria_fotos si es JSON
    import json
    galeria_fotos = []
    if row[7]:  # galeria_fotos
        try:
            if isinstance(row[7], str):
                galeria_fotos = json.loads(row[7])
            elif isinstance(row[7], list):
                galeria_fotos = row[7]
        except:
            galeria_fotos = []

    # Convertir a dict con todos los campos (mapeando a los nombres esperados)
    project = {
        'id': row[0],
        'architect_id': row[1],
        'title': row[2],
        'description': row[3],
        'area_m2': row[4],
        'price': row[5],
        'files': {
            'fotos': galeria_fotos,
            'memoria': row[8],
            'planos': row[9],
            'modelo_3d': row[11],
            'vr_tour': row[12],
            'ocr_text': row[13]
        },
        'created_at': row[14],
        # Mapeos para compatibilidad
        'm2_construidos': row[4],  # area_m2
        'architect_name': 'Arquitecto Demo',  # Placeholder por ahora
        'foto_principal': row[6] if row[6] else (galeria_fotos[0] if galeria_fotos else None),
        'galeria_fotos': galeria_fotos,
        'memoria_pdf': row[8],
        'planos_pdf': row[9],
        'modelo_3d_glb': row[11],
        'vr_tour': row[12],
        'property_type': 'Residencial',
        'estimated_cost': row[5] * 0.8 if row[5] else 0,
        'price_memoria': 1800,
        'price_cad': 2500,
        'energy_rating': 'A',
        'characteristics': {},
        'habitaciones': 3,
        'banos': 2,
        'garaje': True,
        'plantas': 2,
        'm2_parcela_minima': row[4] / 0.33 if row[4] else 0,
        'm2_parcela_maxima': row[4] / 0.2 if row[4] else 0,
        'certificacion_energetica': 'A',
        'tipo_proyecto': 'Residencial',
        'nombre': row[2]  # Alias para compatibilidad
    }

    # Título
    st.title(f"🏗️ {project['nombre']}")

    # Galería de fotos completa
    st.header("📸 Galería del Proyecto")

    # Usar las imágenes de la galería del proyecto
    if galeria_fotos and len(galeria_fotos) > 0:
        # Mostrar imágenes en grid
        cols = st.columns(min(len(galeria_fotos), 3))
        for idx, img_path in enumerate(galeria_fotos):
            with cols[idx % 3]:
                try:
                    # Asegurar que la ruta sea correcta
                    if not img_path.startswith('uploads/'):
                        img_path = f"uploads/{img_path}"
                    st.image(img_path, width='stretch', caption=f"Imagen {idx + 1}")
                except Exception as e:
                    st.warning(f"No se pudo cargar la imagen {idx + 1}")
    else:
        st.info("No hay imágenes disponibles para este proyecto")

    # Información básica del proyecto
    st.header("📋 Información del Proyecto")

    # Calcular superficie mínima requerida
    m2_proyecto = project['m2_construidos'] or project['area_m2'] or 0
    if project['m2_parcela_minima']:
        superficie_minima = project['m2_parcela_minima']
    else:
        superficie_minima = m2_proyecto / 0.33 if m2_proyecto > 0 else 0

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏠 Características Técnicas")
        st.write(f"**Superficie construida:** {m2_proyecto:.0f} m²")
        st.write(f"**Superficie mínima de terreno:** {superficie_minima:.0f} m²")
        if project['m2_parcela_maxima']:
            st.write(f"**Superficie máxima de terreno:** {project['m2_parcela_maxima']:.0f} m²")
        st.write(f"**Tipo:** {project['property_type'] or project['tipo_proyecto'] or 'Residencial'}")

        # Características específicas
        if project['habitaciones']:
            st.write(f"**Habitaciones:** {project['habitaciones']}")
        if project['banos']:
            st.write(f"**Baños:** {project['banos']}")
        if project['plantas']:
            st.write(f"**Plantas:** {project['plantas']}")
        if project['garaje']:
            st.write(f"**Garaje:** {'Sí' if project['garaje'] else 'No'}")

        # Certificación energética
        if project['certificacion_energetica'] or project['energy_rating']:
            rating = project['certificacion_energetica'] or project['energy_rating']
            st.write(f"**Certificación energética:** {rating}")

    with col2:
        st.subheader("💰 Información Económica")
        if project['estimated_cost']:
            st.write(f"**Coste de ejecución aproximado:** €{project['estimated_cost']:,.0f}")
        st.write("**Precio descarga proyecto completo:**")
        st.write(f"• PDF (Memoria completa): €{project['price_memoria']}")
        st.write(f"• CAD (Planos editables): €{project['price_cad']}")

    # Descripción
    if project['description']:
        st.header("📝 Descripción")
        st.write(project['description'])

    # Arquitecto
    if project['architect_name']:
        st.write(f"**Arquitecto:** {project['architect_name']}")

    st.markdown("---")

    # PESTAÑAS PARA ORGANIZAR EL CONTENIDO
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 DOSSIER", "🔍 ANÁLISIS IA", "📄 MEMORIA", "📐 PLANOS", "🏗️ 3D/VR", "🛒 COMPRA"
    ])

    with tab1:
        st.header("📋 DOSSIER PREVENTA")
        if st.button("📋 Generar Dossier Completo", type="primary"):
            texto = project.get('ocr_text', "No hay datos en la DB")
            with st.spinner("Analizando proyecto..."):
                resumen = ai.generate_text(f"Genera un dossier de preventa profesional para este proyecto arquitectónico resumiendo en 200 palabras: materiales, estilo, características técnicas y valor añadido: {texto[:2500]}")
                st.success("📋 DOSSIER GENERADO")
                st.write(resumen)

    with tab2:
        st.header("🔍 ANÁLISIS CON IA")
        if st.button("🤖 Analizar Proyecto con IA", type="primary"):
            texto = project.get('ocr_text', "")
            if not texto:
                # Intentar extraer texto del PDF de memoria si existe
                memoria_pdf = project.get('memoria_pdf')
                if memoria_pdf and os.path.exists(memoria_pdf):
                    try:
                        from archirapid_extract.parse_project_memoria import extract_text_from_pdf
                        texto = extract_text_from_pdf(memoria_pdf)
                        if not texto.strip():  # Si no extrajo nada útil
                            st.error("No hay datos técnicos disponibles para el análisis")
                            texto = ""
                    except Exception as e:
                        st.error(f"Error extrayendo texto del PDF: {e}")
                        texto = ""
                else:
                    st.error("No hay datos técnicos disponibles para el análisis")
                    texto = ""
            
            if texto:  # Solo proceder si tenemos texto
                with st.spinner("Analizando con IA avanzada..."):
                    analisis = ai.generate_text(f"Analiza técnicamente este proyecto arquitectónico: fortalezas, debilidades, viabilidad constructiva, eficiencia energética y recomendaciones de mejora: {texto[:3000]}")
                    st.success("🔍 ANÁLISIS COMPLETADO")
                    st.write(analisis)

    with tab3:
        st.header("📄 MEMORIA TÉCNICA")
        if st.button("📄 Generar Memoria Detallada", type="secondary"):
            # Intentar extraer texto del PDF de memoria si existe
            memoria_pdf = project.get('memoria_pdf')
            texto = project.get('ocr_text', "")
            if not texto and memoria_pdf and os.path.exists(memoria_pdf):
                try:
                    from archirapid_extract.parse_project_memoria import extract_text_from_pdf
                    texto = extract_text_from_pdf(memoria_pdf)
                except Exception as e:
                    st.warning(f"No se pudo extraer texto del PDF: {e}")
            
            if not texto:
                st.error("No hay memoria técnica disponible")
            else:
                with st.spinner("Generando memoria técnica..."):
                    memoria = ai.generate_text(f"Genera una memoria técnica completa para este proyecto basándote en la información disponible: {texto[:3000]}")
                    st.success("📄 MEMORIA GENERADA")
                    st.write(memoria)

    with tab4:
        st.header("📐 PLANOS TÉCNICOS")
        if st.button("📐 Generar Plano Arquitectónico", type="secondary"):
            with st.spinner("Generando plano visual..."):
                try:
                    # Importar función de generación visual
                    from archirapid_extract.generate_design import generate_simple_visual_plan
                    import tempfile

                    # Crear archivo temporal para el plano
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                        output_path = tmp_file.name

                    # Generar plano visual
                    result = generate_simple_visual_plan(project, output_path)

                    if os.path.exists(output_path):
                        st.success("📐 PLANO VISUAL GENERADO")
                        st.image(output_path, caption=f"Plano Arquitectónico - {project.get('title', 'Proyecto')}", width='stretch')

                        # Limpiar archivo temporal después de mostrar
                        import time
                        time.sleep(1)  # Dar tiempo a que se renderice
                        try:
                            os.unlink(output_path)
                        except:
                            pass
                    else:
                        st.error("Error generando el plano visual")

                except Exception as e:
                    st.error(f"Error generando plano visual: {e}")
                    # Fallback al plano ASCII si falla lo visual
                    st.warning("Generando plano ASCII como alternativa...")
                    try:
                        # Intentar obtener texto para el plano ASCII
                        texto = project.get('ocr_text', "")
                        memoria_pdf = project.get('memoria_pdf')

                        # Fallback 1: Extraer del PDF si no hay OCR
                        if not texto and memoria_pdf and os.path.exists(memoria_pdf):
                            try:
                                from archirapid_extract.parse_project_memoria import extract_text_from_pdf
                                texto = extract_text_from_pdf(memoria_pdf)
                            except Exception as e:
                                st.warning(f"No se pudo extraer texto del PDF: {e}")

                        # Fallback 2: Generar plano básico con datos del proyecto
                        if not texto:
                            titulo = project.get('title', 'Proyecto')
                            m2 = project.get('m2_construidos', project.get('area_m2', 0))
                            habitaciones = project.get('habitaciones', 3)
                            banos = project.get('banos', 2)
                            plantas = project.get('plantas', 1)
                            tipo = project.get('property_type', project.get('tipo_proyecto', 'Residencial'))

                            texto = f"Proyecto: {titulo}. Tipo: {tipo}. Superficie: {m2} m². Habitaciones: {habitaciones}. Baños: {banos}. Plantas: {plantas}."

                        if texto:
                            plano = ai.generate_ascii_plan_only(texto)
                            st.success("📐 PLANO ASCII GENERADO")
                            st.code(plano, language="text")
                        else:
                            st.error("No hay datos suficientes para generar el plano")
                    except Exception as e2:
                        st.error(f"Error en fallback ASCII: {e2}")

    with tab5:
        st.header("🏗️ VISUALIZACIÓN 3D / VR")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏗️ Generar Modelo 3D", type="secondary", use_container_width=True):
                # Verificar si el proyecto tiene modelo 3D
                if project.get("modelo_3d_glb"):
                    # Mostrar visor 3D completo
                    rel_path = str(project["modelo_3d_glb"]).replace("\\", "/").lstrip("/")
                    model_url = f"http://localhost:8000/{rel_path}".replace(" ", "%20")

                    # Usar la función dedicada para generar el HTML del visor 3D
                    three_html = generate_3d_viewer_html(model_url)

                    st.components.v1.html(three_html, height=700, scrolling=False)
                else:
                    st.warning('⚠️ Este proyecto específico no dispone de archivos 3D/VR originales del arquitecto.')
        with col2:
            if st.button("🥽 Visor VR Inmersivo", type="secondary", use_container_width=True):
                # Verificar si el proyecto tiene modelo 3D para VR
                if project.get("modelo_3d_glb"):
                    rel = str(project["modelo_3d_glb"]).replace("\\", "/").lstrip("/")
                    glb_url = f"http://localhost:8000/{rel}".replace(" ", "%20")
                    viewer_url = f"http://localhost:8000/static/vr_viewer.html?model={glb_url}"
                    st.markdown(
                        f'<a href="{viewer_url}" target="_blank">'
                        f'<button style="padding:10px 16px;border-radius:6px;background:#0b5cff;color:#fff;border:none;">'
                        f"Abrir experiencia VR en nueva pestaña"
                        f"</button></a>",
                        unsafe_allow_html=True,
                    )
                    st.caption("Se abrirá el visor VR en una nueva pestaña. Requiere navegador con WebXR.")
                else:
                    st.warning('⚠️ Este proyecto específico no dispone de archivos 3D/VR originales del arquitecto.')

    with tab6:
        st.header("🛒 ADQUIRIR PROYECTO")

        # Verificar si ya compró este proyecto
        conn = db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ventas_proyectos WHERE proyecto_id = ? AND cliente_email = ?", (project_id, client_email))
        ya_comprado = cursor.fetchone()
        conn.close()

        if ya_comprado:
            st.success("✅ Ya has adquirido este proyecto")
            st.info("Puedes descargar los archivos desde 'Mis Proyectos'")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📄 Descargar Memoria PDF", use_container_width=True):
                    st.info("Descarga iniciada...")
            with col2:
                if st.button("🖥️ Descargar Planos CAD", use_container_width=True):
                    st.info("Descarga iniciada...")
            with col3:
                if st.button("🏗️ Descargar Modelo 3D", use_container_width=True):
                    st.info("Descarga iniciada...")
        else:
            st.info("💳 Selecciona el producto que deseas adquirir:")

            # Opciones adicionales de servicios
            st.markdown("### 🔧 Servicios Adicionales")
            col_serv1, col_serv2 = st.columns(2)
            
            with col_serv1:
                visado_proyecto = st.checkbox("🏛️ Visado del Proyecto - €500", value=False)
                direccion_obra = st.checkbox("👷 Dirección de Obra - €800", value=False)
            
            with col_serv2:
                construccion = st.checkbox("🏗️ Construcción Completa - €1500", value=False)
                supervision = st.checkbox("👁️ Supervisión Técnica - €300", value=False)

            # Número de copias adicionales
            st.markdown("### 📋 Número de Copias Adicionales")
            num_copias = st.number_input("Número de copias adicionales (200€ cada una)", min_value=0, max_value=10, value=0, step=1)

            # Calcular precios adicionales
            precio_adicional_servicios = 0
            if visado_proyecto:
                precio_adicional_servicios += 500
            if direccion_obra:
                precio_adicional_servicios += 800
            if construccion:
                precio_adicional_servicios += 1500
            if supervision:
                precio_adicional_servicios += 300
            
            precio_adicional_copias = num_copias * 200
            precio_total_adicional = precio_adicional_servicios + precio_adicional_copias

            if precio_total_adicional > 0:
                st.info(f"💰 Costo adicional total: €{precio_total_adicional}")

            col1, col2 = st.columns(2)
            with col1:
                precio_pdf_final = 1800 + precio_total_adicional
                if st.button(f"📄 Memoria PDF - €{precio_pdf_final}", use_container_width=True, type="primary"):
                    # Registrar compra de PDF
                    with st.spinner("Procesando compra..."):
                        import time
                        time.sleep(1)
                    
                    # Determinar productos comprados
                    productos = ["PDF"]
                    if visado_proyecto:
                        productos.append("Visado del Proyecto")
                    if direccion_obra:
                        productos.append("Dirección de Obra")
                    if construccion:
                        productos.append("Construcción Completa")
                    if supervision:
                        productos.append("Supervisión Técnica")
                    if num_copias > 0:
                        productos.append(f"{num_copias} Copias Adicionales")
                    
                    productos_str = ", ".join(productos)
                    
                    # Registrar en base de datos
                    conn_buy = db_conn()
                    cursor_buy = conn_buy.cursor()
                    cursor_buy.execute("""
                        INSERT INTO ventas_proyectos
                        (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (project_id, client_email, "Compra desde panel cliente", productos_str, precio_pdf_final, "Simulado"))
                    conn_buy.commit()
                    conn_buy.close()
                    
                    st.success("🎉 PDF adquirido! Recibirás el enlace por email")
                    st.rerun()
                    
            with col2:
                precio_cad_final = 2500 + precio_total_adicional
                if st.button(f"🖥️ Planos CAD - €{precio_cad_final}", use_container_width=True, type="primary"):
                    # Registrar compra de CAD
                    with st.spinner("Procesando compra..."):
                        import time
                        time.sleep(1)
                    
                    # Determinar productos comprados
                    productos = ["CAD"]
                    if visado_proyecto:
                        productos.append("Visado del Proyecto")
                    if direccion_obra:
                        productos.append("Dirección de Obra")
                    if construccion:
                        productos.append("Construcción Completa")
                    if supervision:
                        productos.append("Supervisión Técnica")
                    if num_copias > 0:
                        productos.append(f"{num_copias} Copias Adicionales")
                    
                    productos_str = ", ".join(productos)
                    
                    # Registrar en base de datos
                    conn_buy = db_conn()
                    cursor_buy = conn_buy.cursor()
                    cursor_buy.execute("""
                        INSERT INTO ventas_proyectos
                        (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (project_id, client_email, "Compra desde panel cliente", productos_str, precio_cad_final, "Simulado"))
                    conn_buy.commit()
                    conn_buy.close()
                    
                    st.success("🎉 CAD adquirido! Recibirás el enlace por email")
                    st.rerun()

            precio_completo_final = 4000 + precio_total_adicional
            if st.button(f"🛒 Comprar Proyecto Completo - €{precio_completo_final}", use_container_width=True, type="primary"):
                # Registrar compra completa
                with st.spinner("Procesando compra..."):
                    import time
                    time.sleep(1)
                
                # Determinar productos comprados
                productos = ["PDF", "CAD", "Proyecto Completo"]
                if visado_proyecto:
                    productos.append("Visado del Proyecto")
                if direccion_obra:
                    productos.append("Dirección de Obra")
                if construccion:
                    productos.append("Construcción Completa")
                if supervision:
                    productos.append("Supervisión Técnica")
                if num_copias > 0:
                    productos.append(f"{num_copias} Copias Adicionales")
                
                productos_str = ", ".join(productos)
                
                # Registrar en base de datos
                conn_buy = db_conn()
                cursor_buy = conn_buy.cursor()
                cursor_buy.execute("""
                    INSERT INTO ventas_proyectos
                    (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """, (project_id, client_email, "Compra desde panel cliente", productos_str, precio_completo_final, "Simulado"))
                conn_buy.commit()
                conn_buy.close()
                
                st.success("🎉 Proyecto completo adquirido! Recibirás todos los archivos por email")
                st.rerun()

    # 🔍 BUSCADOR INTEGRADO DE PROYECTOS SIMILARES (solo para usuarios logueados)
    st.header("🔍 Buscar Proyectos Similares")
    st.write("Encuentra otros proyectos que se ajusten a tus necesidades específicas")

    # Formulario de búsqueda
    with st.form("similar_projects_form"):
        st.markdown("### 🎯 Especifica tus criterios")

        col1, col2 = st.columns(2)

        with col1:
            presupuesto_max = st.number_input(
                "💰 Presupuesto máximo (€)",
                min_value=0,
                value=int(project.get('price') or 0),
                step=10000,
                help="Precio máximo que estás dispuesto a pagar"
            )

            area_deseada = st.number_input(
                "📐 Área de construcción deseada (m²)",
                min_value=0,
                value=int(project.get('m2_construidos') or 0),
                step=10,
                help="Superficie aproximada que quieres construir"
            )

        with col2:
            parcela_disponible = st.number_input(
                "🏞️ Parcela disponible (m²)",
                min_value=0,
                value=int(project.get('m2_parcela_minima') or 0),
                step=50,
                help="Tamaño de terreno que tienes disponible"
            )

            # Checkbox para buscar solo proyectos que quepan
            solo_compatibles = st.checkbox(
                "Solo proyectos compatibles con mi parcela",
                value=True,
                help="Filtrar proyectos cuya parcela mínima sea ≤ a tu terreno disponible"
            )

        # Botón de búsqueda
        submitted = st.form_submit_button("🔍 Buscar Proyectos Similares", type="primary", use_container_width=True)

    # Procesar búsqueda
    if submitted:
        # Preparar parámetros
        search_params = {
            'client_budget': presupuesto_max if presupuesto_max > 0 else None,
            'client_desired_area': area_deseada if area_deseada > 0 else None,
            'client_parcel_size': parcela_disponible if parcela_disponible > 0 and solo_compatibles else None,
            'client_email': client_email
        }

        # Mostrar criterios de búsqueda
        st.markdown("### 📋 Criterios de búsqueda aplicados:")
        criterios = []
        if search_params['client_budget']:
            criterios.append(f"💰 Presupuesto ≤ €{search_params['client_budget']:,}")
        if search_params['client_desired_area']:
            criterios.append(f"📐 Área ≈ {search_params['client_desired_area']} m² (±20%)")
        if search_params['client_parcel_size']:
            criterios.append(f"🏞️ Parcela ≥ {search_params['client_parcel_size']} m²")

        if criterios:
            for criterio in criterios:
                st.write(f"• {criterio}")
        else:
            st.info("No se aplicaron filtros específicos - mostrando todos los proyectos disponibles")

        # Buscar proyectos
        with st.spinner("Buscando proyectos similares..."):
            from modules.marketplace.compatibilidad import get_proyectos_compatibles
            proyectos = get_proyectos_compatibles(**search_params)

        # Filtrar para excluir el proyecto actual
        proyectos = [p for p in proyectos if str(p['id']) != str(project_id)]

        # Mostrar resultados
        st.markdown(f"### 🏗️ Proyectos similares encontrados: {len(proyectos)}")

        if not proyectos:
            st.warning("No se encontraron proyectos que cumplan con tus criterios. Prueba ampliando los límites.")
        else:
            # Mostrar proyectos en grid
            cols = st.columns(2)
            for idx, proyecto in enumerate(proyectos):
                with cols[idx % 2]:
                    # Tarjeta de proyecto
                    with st.container():
                        # Imagen
                        foto = proyecto.get('foto_principal')
                        if foto:
                            try:
                                st.image(foto, width=250, caption=proyecto['title'])
                            except:
                                st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])
                        else:
                            st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])

                        # Información básica
                        st.markdown(f"**🏗️ {proyecto['title']}**")
                        st.write(f"📐 **Área:** {proyecto.get('m2_construidos', proyecto.get('area_m2', 'N/D'))} m²")
                        st.write(f"💰 **Precio:** €{proyecto.get('price', 0):,.0f}" if proyecto.get('price') else "💰 **Precio:** Consultar")

                        # Arquitecto
                        if proyecto.get('architect_name'):
                            st.write(f"👨‍💼 **Arquitecto:** {proyecto['architect_name']}")

                        # Compatibilidad (si hay filtros aplicados)
                        if 'client_parcel_size' in search_params and search_params['client_parcel_size'] and proyecto.get('m2_parcela_minima'):
                            if proyecto['m2_parcela_minima'] <= search_params['client_parcel_size']:
                                st.success("✅ Compatible con tu parcela")
                            else:
                                st.warning(f"⚠️ Necesita parcela ≥ {proyecto['m2_parcela_minima']} m²")

                        # Botón de detalles
                        if st.button("Ver Detalles", key=f"similar_detail_{proyecto['id']}", use_container_width=True):
                            st.query_params["selected_project"] = proyecto['id']
                            st.rerun()

                        st.markdown("---")

def show_client_interests(client_email):
    """Mostrar proyectos de interés del cliente"""
    st.subheader("⭐ Mis Proyectos de Interés")
    
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ci.project_id, ci.created_at, p.title, p.m2_construidos, p.price, p.foto_principal
        FROM client_interests ci
        JOIN projects p ON ci.project_id = p.id
        WHERE ci.email = ?
        ORDER BY ci.created_at DESC
    """, (client_email,))
    
    interests = cursor.fetchall()
    conn.close()
    
    if not interests:
        st.info("No tienes proyectos guardados como de interés. Explora el marketplace para encontrar proyectos que te gusten.")
        return
    
    # Mostrar proyectos de interés
    for interest in interests:
        project_id, saved_at, title, m2, price, foto = interest
        
        with st.expander(f"🏗️ {title}", expanded=True):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if foto:
                    try:
                        st.image(foto, width=200)
                    except:
                        st.image("assets/fincas/image1.jpg", width=200)
                else:
                    st.image("assets/fincas/image1.jpg", width=200)
            
            with col2:
                st.markdown(f"**🏗️ Proyecto:** {title}")
                st.markdown(f"**📏 Superficie:** {m2} m²" if m2 else "**📏 Superficie:** N/D")
                st.markdown(f"**💰 Precio:** €{price:,.0f}" if price else "**💰 Precio:** N/D")
                st.markdown(f"**📅 Guardado:** {saved_at}")
                
                if st.button("Ver Detalles", key=f"view_interest_{project_id}"):
                    st.query_params["selected_project"] = project_id
                    st.rerun()

def show_client_transactions(client_email):
    """Mostrar transacciones del cliente (fincas compradas)"""
    st.subheader("📋 Mis Transacciones")
    
    # Obtener transacciones del cliente
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.id, r.plot_id, r.buyer_name, r.amount, r.kind, r.created_at, 
           p.title, p.m2, p.price, p.photo_paths
    FROM reservations r
    JOIN plots p ON r.plot_id = p.id
    WHERE r.buyer_email = ?
    ORDER BY r.created_at DESC
""", (client_email,))

    transactions = cursor.fetchall()
    conn.close()

    if not transactions:
        st.info("No se encontraron transacciones para este cliente.")
        return

    # Mostrar tabla general
    st.dataframe(transactions)

    # Mostrar resumen de transacciones
    for trans in transactions:
        trans_id, plot_id, buyer_name, amount, kind, created_at, plot_title, m2, price, photo_paths = trans

        with st.expander(f"🏠 {plot_title} - {kind.upper()}", expanded=True):
            col1, col2 = st.columns([1, 2])

            # 📸 Columna izquierda: imagen
            with col1:
                if photo_paths:
                    try:
                        paths = json.loads(photo_paths)
                        if paths and isinstance(paths, list):
                            image_paths = [f"uploads/{path}" for path in paths]
                            st.image(image_paths, caption=["Foto " + str(i+1) for i in range(len(image_paths))], use_container_width=True)
                    except Exception as e:
                        st.warning(f"No se pudo cargar la imagen: {e}")

            # 📋 Columna derecha: detalles
            with col2:
                st.markdown(f"**📋 ID Transacción:** `{trans_id}`")
                st.markdown(f"**🏠 Finca:** {plot_title}")
                st.markdown(f"**📏 Superficie:** {m2} m²")
                st.markdown(f"**💰 Precio Total:** €{price}")
                st.markdown(f"**💵 Cantidad Pagada:** €{amount}")
                st.markdown(f"**📅 Fecha:** {created_at}")
                st.markdown(f"**✅ Tipo:** {kind.upper()}")

        # 🔍 PROYECTOS COMPATIBLES
        st.markdown("### 📐 Proyectos Compatibles")

        proyectos = get_proyectos_compatibles(plot_id)

        if not proyectos:
            st.info("No hay proyectos compatibles para esta finca.")
        else:
            for p in proyectos:
                st.markdown(f"**🏗️ {p.get('nombre', 'Proyecto sin nombre')}** — {p.get('total_m2', '?')} m²")

                img = p.get("imagen_principal")
                if img:
                    st.image(f"assets/projects/{img}", use_container_width=True)

                st.markdown("---")

        show_common_actions(context=f"buyer_{trans_id}")  # Acciones comunes para compradores

def show_buyer_panel(client_email):
    """Panel principal para compradores - PRIORIDAD: Mostrar la finca comprada"""
    st.header("🛒 Panel de Comprador")

    # PRIORIDAD: Buscar finca adquirida por el cliente
    conn = db_conn()
    cursor = conn.cursor()

    # Buscar la finca que el cliente ha comprado/reservado
    cursor.execute("SELECT * FROM reservations WHERE buyer_email=? ORDER BY created_at DESC LIMIT 1", (client_email,))
    reservation = cursor.fetchone()

    if reservation:
        plot_id = reservation[1]  # plot_id desde reservations

        # Obtener datos completos de la finca
        cursor.execute("""
            SELECT id, title, catastral_ref, m2, superficie_edificable, type, vertices_coordenadas,
                   registry_note_path, price, lat, lon, status, created_at, photo_paths,
                   owner_name, owner_email, owner_phone, services, type, address
            FROM plots WHERE id = ?
        """, (plot_id,))

        plot_data = cursor.fetchone()
        conn.close()

        if plot_data:
            # SECCIÓN PRINCIPAL: MI PROPIEDAD ADQUIRIDA
            st.subheader("🏡 MI PROPIEDAD ADQUIRIDA")

            # Mostrar imagen de la finca
            col1, col2 = st.columns([1, 2])

            with col1:
                photo_paths = plot_data[13]  # photo_paths
                if photo_paths:
                    try:
                        import json
                        paths = json.loads(photo_paths)
                        if paths and isinstance(paths, list):
                            img_path = f"uploads/{paths[0]}"
                            if os.path.exists(img_path):
                                st.image(img_path, width=250)
                            else:
                                st.image("assets/fincas/image1.jpg", width=250)
                        else:
                            st.image("assets/fincas/image1.jpg", width=250)
                    except:
                        st.image("assets/fincas/image1.jpg", width=250)
                else:
                    st.image("assets/fincas/image1.jpg", width=250)

            with col2:
                st.markdown(f"### 🏠 {plot_data[1]}")  # title
                st.markdown(f"**📍 Referencia Catastral:** {plot_data[2] or 'No disponible'}")  # catastral_ref
                st.markdown(f"**📏 Superficie Total:** {plot_data[3] or 0:,.0f} m²")  # m2
                st.markdown(f"**🏗️ Superficie Construible:** {plot_data[4] or 0:,.0f} m²")  # superficie_edificable
                st.markdown(f"**🌆 Clasificación:** {plot_data[5] or 'No especificada'}")  # type
                st.markdown(f"**💰 Precio de Compra:** €{reservation[4]:,.0f}")  # amount from reservation
                st.markdown(f"**📊 Tipo de Operación:** {reservation[5].capitalize()}")  # kind from reservation
                st.markdown(f"**📅 Fecha de Adquisición:** {reservation[6][:10] if reservation[6] else 'N/A'}")  # created_at

                # Información adicional urbanística
                st.markdown("---")
                st.markdown("**🏛️ Información Urbanística:**")
                st.markdown(f"• **Servicios:** {plot_data[17] or 'No especificados'}")  # services
                st.markdown(f"• **Tipo de Parcela:** {plot_data[18] or 'No especificado'}")  # type
                st.markdown(f"• **Dirección:** {plot_data[19] or 'No especificada'}")  # address

                # BOTÓN NOTA CATASTRAL - Solo aquí
                registry_note_path = plot_data[7]  # registry_note_path
                if registry_note_path and os.path.exists(registry_note_path):
                    st.markdown("---")
                    if st.button("📥 DESCARGAR NOTA CATASTRAL (PDF)", type="primary", key="download_catastral"):
                        with open(registry_note_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Descargar PDF",
                                data=f,
                                file_name=f"nota_catastral_{plot_data[2] or plot_data[1]}.pdf",
                                mime="application/pdf",
                                key="catastral_download"
                            )
                else:
                    st.info("📄 Nota catastral no disponible aún")

            st.markdown("---")

            # 🔍 VERIFICACIÓN TÉCNICA AUTOMÁTICA CON IA
            st.subheader("🔍 Verificación Técnica Automática con IA")

            # Función de verificación automática con cacheado
            def run_automatic_verification(plot_id, plot_data):
                """Ejecuta verificación automática con cacheado de 5 minutos"""
                import time

                # Cache key para esta finca específica
                cache_key = f'ia_verification_{plot_id}'
                cache_time_key = f'ia_verification_time_{plot_id}'

                # Verificar si hay cache válido (5 minutos = 300 segundos)
                current_time = time.time()
                last_verification = st.session_state.get(cache_time_key, 0)
                cache_valid = (current_time - last_verification) < 300  # 5 minutos

                # Si ya está verificado y el cache es válido, usar datos cacheados
                if st.session_state.get(cache_key) and cache_valid:
                    return st.session_state[cache_key]

                # Si no hay cache o expiró, ejecutar verificación
                try:
                    from modules.marketplace.ai_engine import extraer_datos_catastral_completo

                    # Buscar archivos PDF catastrales
                    pdf_paths = [
                        Path("archirapid_extract/catastro_output/nota_catastral.pdf"),
                        Path("uploads/nota_catastral.pdf"),
                        Path("catastro_output/nota_catastral.pdf")
                    ]

                    pdf_encontrado = None
                    for pdf_path in pdf_paths:
                        if pdf_path.exists():
                            pdf_encontrado = pdf_path
                            break

                    if pdf_encontrado:
                        datos_extraidos = extraer_datos_catastral_completo(str(pdf_encontrado))

                        if datos_extraidos and "error" not in datos_extraidos:
                            # Comparar datos extraídos con datos de la finca
                            superficie_pdf = datos_extraidos.get("superficie_m2", 0)
                            ref_catastral_pdf = datos_extraidos.get("referencia_catastral", "")

                            superficie_finca = plot_data[3] or 0  # m2
                            ref_catastral_finca = plot_data[2] or ''  # catastral_ref

                            # Verificar coincidencias
                            superficie_ok = abs(superficie_pdf - superficie_finca) < 10
                            ref_ok = ref_catastral_pdf.strip() == ref_catastral_finca.strip()

                            # Preparar datos para cache y session state
                            verification_data = {
                                'superficie_pdf': superficie_pdf,
                                'ref_catastral_pdf': ref_catastral_pdf,
                                'superficie_finca': superficie_finca,
                                'ref_catastral_finca': ref_catastral_finca,
                                'superficie_ok': superficie_ok,
                                'ref_ok': ref_ok,
                                'datos_extraidos': datos_extraidos,
                                'pdf_path': str(pdf_encontrado),
                                'timestamp': current_time
                            }

                            # Guardar en cache y session state
                            st.session_state[cache_key] = verification_data
                            st.session_state[cache_time_key] = current_time

                            # Guardar m² verificados para uso futuro
                            if superficie_ok:
                                st.session_state['verified_m2'] = superficie_pdf

                            return verification_data
                        else:
                            return {"error": datos_extraidos.get("error", "Error en extracción")}
                    else:
                        return {"error": "PDF no encontrado"}

                except Exception as e:
                    return {"error": str(e)}

            # Ejecutar verificación automática
            verification_result = run_automatic_verification(plot_id, plot_data)

            # Mostrar resultados de forma elegante
            if "error" in verification_result:
                st.warning(f"⚠️ Verificación automática pendiente: {verification_result['error']}")

                # Mantener botón manual como fallback
                if st.button("🔍 Reintentar Verificación Manual", key=f"manual_verify_{plot_id}", type="secondary"):
                    st.rerun()
            else:
                # VERIFICACIÓN EXITOSA - Mostrar resultados integrados
                data = verification_result

                # Estado de verificación
                if data['superficie_ok'] and data['ref_ok']:
                    st.success("✅ **VERIFICACIÓN AUTOMÁTICA EXITOSA** - Datos catastrales validados")
                elif data['superficie_ok']:
                    st.warning("⚠️ **Superficie verificada**, pero referencia catastral requiere revisión")
                else:
                    st.error("❌ **Discrepancia detectada** - Revisar datos catastrales")

                # Información técnica integrada
                with st.expander("📊 Detalles de Verificación Técnica", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("### 📋 Datos Catastrales Verificados")
                        st.write(f"**Superficie:** {data['superficie_pdf']} m²")
                        st.write(f"**Referencia:** {data['ref_catastral_pdf']}")
                        st.write(f"**Municipio:** {data['datos_extraidos'].get('municipio', 'N/A')}")

                    with col2:
                        st.markdown("### 🏗️ Información Técnica")
                        st.write(f"**Forma:** {data['datos_extraidos'].get('forma_geometrica', 'N/A')}")
                        st.write(f"**Vértices:** {data['datos_extraidos'].get('vertices', 0)}")
                        dims = data['datos_extraidos'].get('dimensiones', {})
                        st.write(f"**Dimensiones:** {dims.get('ancho_m', 0):.1f}m × {dims.get('largo_m', 0):.1f}m")

                    # Edificabilidad
                    ed = data['datos_extraidos'].get('edificabilidad', {})
                    if ed:
                        st.markdown("### 🏗️ Parámetros de Edificabilidad")
                        st.write(f"**Máx. Edificable:** {ed.get('max_edificable_m2', 0):.1f} m²")
                        st.write(f"**Porcentaje:** {ed.get('porcentaje_edificable', 0):.1f}%")

                    # Plano si existe
                    archivos = data['datos_extraidos'].get('archivos_generados', {})
                    plano_visualizado = archivos.get('plano_vectorizado')
                    plano_limpio = archivos.get('plano_limpio')

                    if plano_visualizado and Path(plano_visualizado).exists():
                        st.markdown("### 📐 Plano Catastral Verificado")
                        st.image(str(plano_visualizado), caption="Plano vectorizado con contornos detectados", use_container_width=True)

                        if plano_limpio and Path(plano_limpio).exists():
                            with open(plano_limpio, "rb") as file:
                                st.download_button(
                                    label="📄 Descargar Plano Técnico (PNG)",
                                    data=file,
                                    file_name="plano_catastral_verificado.png",
                                    mime="image/png",
                                    help="Plano técnico verificado para uso arquitectónico"
                                )

                # BOTÓN PDF SIEMPRE VISIBLE (como solicitado)
                registry_note_path = plot_data[7]  # registry_note_path
                if registry_note_path and os.path.exists(registry_note_path):
                    st.markdown("---")
                    col_pdf1, col_pdf2 = st.columns([3, 1])
                    with col_pdf1:
                        st.info("📄 **Nota Catastral Digital Disponible** - Descarga tu documento oficial")
                    with col_pdf2:
                        with open(registry_note_path, "rb") as f:
                            st.download_button(
                                label="📥 DESCARGAR PDF",
                                data=f,
                                file_name=f"nota_catastral_{plot_data[2] or plot_data[1]}.pdf",
                                mime="application/pdf",
                                key="catastral_download_auto"
                            )
                else:
                    st.info("📄 Nota catastral no disponible - Contacta con soporte para obtenerla")

            st.markdown("---")

            # HERRAMIENTAS DE ACCIÓN - Los 4 botones principales
            st.subheader("🛠️ Herramientas para tu Propiedad")

            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)

            with col1:
                if st.button("🎨 DISEÑAR CON IA", type="primary", use_container_width=True):
                    st.info("🎨 Función de diseño con IA próximamente disponible")
                    # TODO: Implementar navegación a diseñador IA

            with col2:
                if st.button("📐 VER PROYECTOS COMPATIBLES", type="secondary", use_container_width=True):
                    # Activar modo de búsqueda de proyectos dentro del panel
                    st.session_state['show_project_search'] = True
                    st.rerun()

            with col3:
                if st.button("💰 MIS TRANSACCIONES", type="secondary", use_container_width=True):
                    st.info("💰 Mostrando historial de transacciones...")
                    # TODO: Mostrar recibo de compra

            with col4:
                if st.button("📑 DOCUMENTACIÓN", type="secondary", use_container_width=True):
                    st.info("📑 Accediendo a documentación...")
                    # TODO: Mostrar documentos relacionados

            st.markdown("---")

            # BUSCADOR INTEGRADO DE PROYECTOS COMPATIBLES
            if st.session_state.get('show_project_search', False):
                show_integrated_project_search(client_email, plot_data)

    # Si no tiene finca adquirida, mostrar mensaje
    else:
        conn.close()
        st.info("🏠 No tienes propiedades adquiridas aún.")
        st.markdown("💡 **¿Quieres comprar una finca?**")
        st.markdown("• Explora el marketplace principal")
        st.markdown("• Contacta con propietarios directamente")
        return

    # ELIMINAR LAS PESTAÑAS GENÉRICAS - El cliente quiere ver SU finca, no catálogo
    # Las pestañas "🔍 Buscar Proyectos" y "📋 Mis Intereses" se eliminan por completo


def show_owner_panel_v2(client_email):
    """Panel para propietarios con fincas"""
    st.subheader("🏠 Mis Propiedades Publicadas")
    
    # Obtener fincas del propietario
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, cadastral_ref, surface_m2, buildable_m2, is_urban, vector_geojson, registry_note_path, price, lat, lon, status, created_at, photo_paths, owner_name, owner_email, owner_phone, sanitation_type, plot_type, propietario_direccion FROM plots WHERE owner_email = ? ORDER BY created_at DESC", (client_email,))
    
    properties = cursor.fetchall()
    conn.close()
    
    if not properties:
        st.warning("No tienes propiedades publicadas")
        return
    
    # Mostrar propiedades
    for prop in properties:
        prop_id = prop[0]
        title = prop[1]
        surface_m2 = prop[3]
        price = prop[8]
        status = prop[11]
        created_at = prop[12]
        photo_paths = prop[13]
        owner_name = prop[14]
        owner_phone = prop[16]
        
        status_emoji = "✅" if status == "published" else "⏳" if status == "pending" else "❌"
        
        with st.expander(f"{status_emoji} {title} - {surface_m2} m²", expanded=True):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Mostrar imagen de la finca
                if photo_paths:
                    try:
                        paths = json.loads(photo_paths)
                        if paths and isinstance(paths, list):
                            img_path = f"uploads/{paths[0]}"
                            if os.path.exists(img_path):
                                st.image(img_path, width=200)
                    except:
                        st.image("assets/fincas/image1.jpg", width=200)
                else:
                    st.image("assets/fincas/image1.jpg", width=200)
            
            with col2:
                st.markdown(f"**🏠 Propiedad:** {title}")
                st.markdown(f"**📏 Superficie:** {surface_m2} m²")
                st.markdown(f"**💰 Precio:** €{price}")
                st.markdown(f"**📊 Estado:** {status.capitalize()}")
                st.markdown(f"**📅 Publicada:** {created_at}")
                st.markdown(f"**📞 Contacto:** {owner_phone}")
                
                # Estadísticas de la propiedad
                st.markdown("---")
                st.markdown("**📈 Estadísticas:**")
                
                # Contar propuestas para esta finca
                conn = db_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM proposals WHERE plot_id = ?", (prop_id,))
                proposals_count = cursor.fetchone()[0]
                conn.close()
                
                col_stats1, col_stats2 = st.columns(2)
                with col_stats1:
                    st.metric("📨 Propuestas Recibidas", proposals_count)
                with col_stats2:
                    st.metric("👁️ Visitas Estimadas", "N/A")  # TODO: implementar contador de visitas
    
    # Opciones específicas para propietarios
    st.markdown("---")
    st.subheader("🎯 Gestión de Propiedades")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 VER PROPUESTAS")
        st.write("Revisa las propuestas de arquitectos para tus fincas")
        if st.button("📨 Ver Todas las Propuestas", key="view_proposals_owner", use_container_width=True, type="primary"):
            st.success("📨 Mostrando todas las propuestas...")
            st.info("Aquí podrás gestionar todas las propuestas recibidas para tus propiedades")
    
    with col2:
        st.markdown("#### ➕ PUBLICAR MÁS FINCAS")
        st.write("Añade más propiedades a tu portafolio")
        if st.button("🏠 Subir Nueva Finca", key="upload_new_property", use_container_width=True, type="primary"):
            st.success("🏠 Redirigiendo a subida de fincas...")
            st.info("Accede desde el menú lateral 'Propietarios (Subir Fincas)'")
    
    show_common_actions(context="owner")  # Acciones comunes para todos

def show_buyer_actions():
    """Acciones comunes para compradores"""
    st.markdown("---")
    
    # Opciones de acción para compradores
    st.subheader("🎯 ¿Qué deseas hacer?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key="go_designer_panel_1", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda...")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")
    
    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key="go_projects_panel", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles...")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")
    
    st.markdown("---")
    
    # Interfaz de salida profesional
    st.info('ℹ️ Tu proceso ha terminado con éxito. Puedes volver a acceder a tu finca y herramientas de diseño en cualquier momento desde el botón **ACCESO** en la página principal con tu email y contraseña.')
    
    if st.button("🚪 FINALIZAR Y CERRAR SESIÓN"):
        st.session_state.clear()
        st.session_state['selected_page'] = '🏠 Home'
        st.rerun()

# Añadir import necesario
import os
def show_common_actions(context="common"):
    """Acciones comunes para compradores y propietarios"""
    st.markdown("---")
    
    # Opciones de acción
    st.subheader("🎯 ¿Qué deseas hacer?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key=f"go_designer_panel_2_{context}", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda...")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")
    
    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key=f"go_projects_panel_{context}", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles...")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")
    
    st.markdown("---")
    
    # Interfaz de salida profesional
    st.info('ℹ️ Tu proceso ha terminado con éxito. Puedes volver a acceder a tu finca y herramientas de diseño en cualquier momento desde el botón **ACCESO** en la página principal con tu email y contraseña.')
    
    if st.button("🚪 FINALIZAR Y CERRAR SESIÓN", key=f"finalizar_sesion_{context}"):
        st.session_state.clear()
        st.session_state['selected_page'] = '🏠 Home'
        st.rerun()

def show_advanced_project_search(client_email):
    """Búsqueda avanzada de proyectos por criterios"""
    st.subheader("🔍 Buscar Proyectos Arquitectónicos")
    st.write("Encuentra proyectos compatibles con tus necesidades específicas")
    
    # Formulario de búsqueda
    with st.form("advanced_search_form"):
        st.markdown("### 🎯 Especifica tus criterios")
        
        col1, col2 = st.columns(2)
        
        with col1:
            presupuesto_max = st.number_input(
                "💰 Presupuesto máximo (€)", 
                min_value=0, 
                value=0, 
                step=10000,
                help="Precio máximo que estás dispuesto a pagar por el proyecto completo"
            )
            
            area_deseada = st.number_input(
                "📐 Área de construcción deseada (m²)", 
                min_value=0, 
                value=0, 
                step=10,
                help="Superficie aproximada que quieres construir (±20% tolerancia)"
            )
        
        with col2:
            parcela_disponible = st.number_input(
                "🏞️ Parcela disponible (m²)", 
                min_value=0, 
                value=0, 
                step=50,
                help="Tamaño de terreno que tienes disponible"
            )
            
            # Checkbox para buscar solo proyectos que quepan
            solo_compatibles = st.checkbox(
                "Solo proyectos que quepan en mi parcela", 
                value=True,
                help="Filtrar proyectos cuya parcela mínima sea ≤ a tu terreno disponible"
            )
        
        # Botón de búsqueda
        submitted = st.form_submit_button("🔍 Buscar Proyectos", type="primary", use_container_width=True)
    
    # Procesar búsqueda
    if submitted:
        # Preparar parámetros
        search_params = {
            'client_budget': presupuesto_max if presupuesto_max > 0 else None,
            'client_desired_area': area_deseada if area_deseada > 0 else None,
            'client_parcel_size': parcela_disponible if parcela_disponible > 0 and solo_compatibles else None,
            'client_email': client_email
        }
        
        # Mostrar criterios de búsqueda
        st.markdown("### 📋 Criterios de búsqueda aplicados:")
        criterios = []
        if search_params['client_budget']:
            criterios.append(f"💰 Presupuesto ≤ €{search_params['client_budget']:,}")
        if search_params['client_desired_area']:
            criterios.append(f"📐 Área ≈ {search_params['client_desired_area']} m² (±20%)")
        if search_params['client_parcel_size']:
            criterios.append(f"🏞️ Parcela ≥ {search_params['client_parcel_size']} m²")
        
        if criterios:
            for criterio in criterios:
                st.write(f"• {criterio}")
        else:
            st.info("No se aplicaron filtros específicos - mostrando todos los proyectos disponibles")
        
        # Buscar proyectos
        with st.spinner("Buscando proyectos compatibles..."):
            proyectos = get_proyectos_compatibles(**search_params)
        
        # Mostrar resultados
        st.markdown(f"### 🏗️ Resultados: {len(proyectos)} proyectos encontrados")
        
        if not proyectos:
            st.warning("No se encontraron proyectos que cumplan con tus criterios. Prueba ampliando los límites.")
            return
        
        # Mostrar proyectos en grid
        cols = st.columns(2)
        for idx, proyecto in enumerate(proyectos):
            with cols[idx % 2]:
                # Tarjeta de proyecto
                with st.container():
                    # Imagen
                    foto = proyecto.get('foto_principal')
                    if foto:
                        try:
                            st.image(foto, width=250, caption=proyecto['title'])
                        except:
                            st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])
                    else:
                        st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])
                    
                    # Información básica
                    st.markdown(f"**🏗️ {proyecto['title']}**")
                    st.write(f"📐 **Área:** {proyecto.get('m2_construidos', proyecto.get('area_m2', 'N/D'))} m²")
                    st.write(f"💰 **Precio:** €{proyecto.get('price', 0):,.0f}" if proyecto.get('price') else "💰 **Precio:** Consultar")
                    
                    # Arquitecto
                    if proyecto.get('architect_name'):
                        st.write(f"👨‍💼 **Arquitecto:** {proyecto['architect_name']}")
                    
                    # Compatibilidad
                    if search_params['client_parcel_size'] and proyecto.get('m2_parcela_minima'):
                        if proyecto['m2_parcela_minima'] <= search_params['client_parcel_size']:
                            st.success("✅ Compatible con tu parcela")
                        else:
                            st.warning(f"⚠️ Necesita parcela ≥ {proyecto['m2_parcela_minima']} m²")
                    
                    # Botón de detalles
                    if st.button("Ver Detalles", key=f"search_detail_{proyecto['id']}", use_container_width=True):
                        st.query_params["selected_project"] = proyecto['id']
                        st.rerun()
                    
                    st.markdown("---")

def show_project_interest_panel(project_id):
    from modules.marketplace.project_detail import get_project_by_id
    from modules.marketplace import ai_engine_groq as ai
    import json

    # 1. Recuperamos el proyecto con los nuevos campos (ocr_text)
    project = get_project_by_id(project_id)
    
    if not project:
        st.error("Proyecto no encontrado")
        return

    st.title(f"🏗️ {project['nombre']}")
    
    # --- BLOQUE DE IA CORREGIDO ---
    st.divider()
    st.subheader("🤖 Análisis de Inteligencia Artificial")
    
    # Recuperamos el texto que guardamos en la base de datos
    ocr_content = project.get('ocr_text', "")
    
    if not ocr_content:
        st.warning("⚠️ Este proyecto no tiene memoria técnica procesada. Súbelo de nuevo para activar el análisis.")
    else:
        # BOTÓN 1: El Dossier Preventa (Resumen corto para que no se corte)
        if st.button("📋 GENERAR DOSSIER PREVENTA", type="primary"):
            with st.spinner("Redactando dossier ejecutivo..."):
                # Forzamos a la IA a ser breve: máximo 150 palabras
                resumen = ai.generate_text(
                    f"Basado en este texto: {ocr_content[:2000]}, haz un resumen ejecutivo de calidades y estilo de máximo 150 palabras. NO TE INVENTES NOMBRES, usa el título: {project['nombre']}", 
                    max_tokens=300
                )
                st.info(resumen)

        # BOTÓN 2: El Plano Técnico (Llamada exclusiva al dibujo)
        if st.button("📐 GENERAR PLANO TÉCNICO (ASCII)"):
            with st.spinner("Delineando espacios..."):
                # Llamamos a la función dedicada que creamos antes
                plano_ascii = ai.generate_ascii_plan_only(ocr_content)
                st.markdown("#### Distribución de Planta Sugerida")
                st.code(plano_ascii, language="text")
                st.caption("Nota: Este plano es una representación esquemática basada en la memoria descriptiva.")


def show_client_project_purchases(client_email):
    """Mostrar compras de proyectos realizadas por el cliente"""
    st.subheader("🛒 Mis Compras de Proyectos")

    # Obtener compras del cliente
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vp.*, p.title as project_title, p.architect_name
        FROM ventas_proyectos vp
        LEFT JOIN projects p ON vp.proyecto_id = p.id
        WHERE vp.cliente_email = ?
        ORDER BY vp.fecha_compra DESC
    """, (client_email,))

    purchases = cursor.fetchall()
    conn.close()

    if not purchases:
        st.info("Aún no has realizado ninguna compra de proyectos.")
        st.markdown("💡 **¿Quieres comprar un proyecto?**")
        st.markdown("• Ve a la pestaña '🔍 Buscar Proyectos' para explorar opciones")
        st.markdown("• O navega por el marketplace principal")
        return

    # Mostrar estadísticas
    total_compras = len(purchases)
    total_gastado = sum(purchase[6] for purchase in purchases if purchase[6])  # total_pagado

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Compras", total_compras)
    with col2:
        st.metric("Total Gastado", f"€{total_gastado:,.0f}")
    with col3:
        st.metric("Promedio por Compra", f"€{total_gastado/total_compras:,.0f}" if total_compras > 0 else "€0")

    st.markdown("---")

    # Mostrar compras agrupadas por proyecto
    st.subheader("📋 Detalle de Compras")

    # Agrupar por proyecto
    projects_grouped = {}
    for purchase in purchases:
        project_id = purchase[1]  # proyecto_id
        if project_id not in projects_grouped:
            projects_grouped[project_id] = {
                'title': purchase[9] or f"Proyecto {project_id}",  # project_title
                'architect': purchase[10] or "No especificado",  # architect_name
                'purchases': []
            }
        projects_grouped[project_id]['purchases'].append(purchase)

    # Mostrar cada proyecto con sus compras
    for project_id, project_data in projects_grouped.items():
        with st.expander(f"🏗️ {project_data['title']} - Arquitecto: {project_data['architect']}", expanded=True):

            # Calcular total por proyecto
            project_total = sum(p[6] for p in project_data['purchases'] if p[6])

            st.markdown(f"**💰 Total invertido en este proyecto:** €{project_total:,.0f}")

            # Mostrar cada compra
            for purchase in project_data['purchases']:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                with col1:
                    producto = purchase[4]  # productos_comprados
                    st.markdown(f"**📄 {producto}**")

                with col2:
                    precio = purchase[5]  # total_pagado
                    st.markdown(f"**€{precio:,.0f}**")

                with col3:
                    metodo = purchase[6]  # metodo_pago
                    st.markdown(f"**{metodo}**")

                with col4:
                    fecha = purchase[7]  # fecha_compra
                    if fecha:
                        # Formatear fecha si es necesario
                        st.markdown(f"**{fecha[:10]}**")
                    else:
                        st.markdown("**Fecha N/D**")

                st.markdown("---")

    # Mostrar servicios contratados con proveedores
    st.markdown("### 🏗️ Servicios Profesionales Contratados")

    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sa.id, sa.servicio_tipo, sa.proveedor_id, sa.precio_servicio, sa.estado,
               sa.fecha_asignacion, sa.fecha_completado, sa.notas,
               sp.name as proveedor_name, sp.company, sp.phone, sp.specialty,
               vp.productos_comprados, p.title as project_title
        FROM service_assignments sa
        JOIN service_providers sp ON sa.proveedor_id = sp.id
        JOIN ventas_proyectos vp ON sa.venta_id = vp.id
        LEFT JOIN projects p ON sa.proyecto_id = p.id
        WHERE sa.cliente_email = ?
        ORDER BY sa.fecha_asignacion DESC
    """, (client_email,))

    services = cursor.fetchall()
    conn.close()

    if services:
        for service in services:
            (assignment_id, servicio_tipo, proveedor_id, precio_servicio, estado,
             fecha_asignacion, fecha_completado, notas,
             proveedor_name, company, phone, specialty,
             productos_comprados, project_title) = service

            estado_emoji = {
                "pendiente": "⏳",
                "en_progreso": "🔄",
                "completado": "✅",
                "cancelado": "❌"
            }.get(estado, "❓")

            servicio_nombre = {
                "direccion_obra": "Dirección de Obra",
                "visado": "Visado del Proyecto",
                "bim": "Gemelos Digitales (BIM)",
                "sostenibilidad": "Consultoría Sostenibilidad",
                "ssl": "Coordinación SSL"
            }.get(servicio_tipo, servicio_tipo.replace('_', ' ').title())

            with st.expander(f"{estado_emoji} {servicio_nombre} - {proveedor_name}", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**🏢 Proveedor:** {proveedor_name}")
                    if company:
                        st.write(f"**Empresa:** {company}")
                    st.write(f"**Especialidad:** {specialty.replace('_', ' ').title()}")
                    st.write(f"**Teléfono:** {phone}")
                    st.write(f"**Proyecto:** {project_title or f'ID: {productos_comprados}'}")

                with col2:
                    st.write(f"**💰 Precio:** €{precio_servicio:,.0f}")
                    st.write(f"**📊 Estado:** {estado.title()}")
                    st.write(f"**📅 Asignado:** {fecha_asignacion[:10]}")
                    if fecha_completado:
                        st.write(f"**✅ Completado:** {fecha_completado[:10]}")

                if notas:
                    st.write("**📝 Notas del proveedor:**")
                    for nota in notas.split('\n'):
                        if nota.strip():
                            st.write(f"• {nota.strip()}")

                # Información de contacto
                st.markdown("---")
                st.info(f"📞 **Contacto:** {phone} | Para consultas sobre el progreso del servicio")
    else:
        st.info("No tienes servicios profesionales contratados.")

    st.markdown("### 📥 Descargas Disponibles")
    st.info("Las descargas de tus proyectos estarán disponibles próximamente en esta sección.")


def show_integrated_project_search(client_email, plot_data):
    """Buscador integrado de proyectos compatibles dentro del panel de cliente"""
    from modules.marketplace import ai_engine_groq as ai

    st.markdown("---")
    st.subheader("🏗️ Buscador de Proyectos Compatibles")

    # Botón para volver al panel principal
    col_back, col_title = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Volver a Mi Finca", key="back_to_property"):
            st.session_state['show_project_search'] = False
            st.rerun()

    # Obtener superficie verificada (prioridad: verified_m2 > superficie_edificable > 33% de finca)
    verified_m2 = st.session_state.get('verified_m2')
    if verified_m2:
        max_surface = verified_m2
        source_info = "datos verificados por IA"
    else:
        # Usar superficie edificable de la tabla plots o calcular 33%
        superficie_edificable = plot_data[3] if len(plot_data) > 3 and plot_data[3] else None
        if superficie_edificable:
            max_surface = superficie_edificable
            source_info = "superficie edificable registrada"
        else:
            max_surface = plot_data[4] * 0.33 if len(plot_data) > 4 and plot_data[4] else 0
            source_info = "33% de la superficie total (estimación)"

    st.markdown(f"### 🎯 Filtro Automático Aplicado")
    st.info(f"📐 **Superficie máxima de construcción:** {max_surface:,.0f} m² ({source_info})")
    st.write("Solo se muestran proyectos cuya superficie construida sea ≤ a este límite.")

    # Buscar proyectos compatibles automáticamente
    with st.spinner("🔍 Buscando proyectos compatibles con tu finca..."):
        search_params = {
            'client_parcel_size': max_surface,
            'client_email': client_email
        }
        proyectos = get_proyectos_compatibles(**search_params)

    # Mostrar resultados
    st.markdown(f"### 🏗️ Proyectos Encontrados: {len(proyectos)}")

    if not proyectos:
        st.warning("No se encontraron proyectos que quepan en tu finca con los criterios actuales.")
        st.info("💡 Considera contactar con arquitectos para proyectos personalizados.")
        return

    # Mostrar proyectos en grid
    cols = st.columns(2)
    for idx, proyecto in enumerate(proyectos):
        with cols[idx % 2]:
            with st.container():
                # Imagen del proyecto
                foto = proyecto.get('foto_principal')
                if foto:
                    try:
                        st.image(foto, width=250, caption=proyecto['title'])
                    except:
                        st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])
                else:
                    st.image("assets/fincas/image1.jpg", width=250, caption=proyecto['title'])

                # Información básica
                st.markdown(f"**🏗️ {proyecto['title']}**")
                area_construida = proyecto.get('m2_construidos', proyecto.get('area_m2', 0))
                # Asegurar que area_construida no sea None antes de dar formato
                area_val = area_construida if area_construida is not None else 0
                st.write(f"📐 **Área construida:** {area_val:,.0f} m²")
                st.write(f"💰 **Precio:** €{proyecto.get('price', 0):,.0f}" if proyecto.get('price') else "💰 **Precio:** Consultar")

                # Arquitecto
                if proyecto.get('architect_name'):
                    st.write(f"👨‍💼 **Arquitecto:** {proyecto['architect_name']}")

                # Compatibilidad
                # Filtro de seguridad: Si el área es None, lo ignoramos para evitar el crash
                if area_construida is not None and area_construida <= max_surface:
                    st.success(f"✅ Compatible (usa {area_construida/max_surface*100:.1f}% de tu capacidad)")
                else:
                    st.error("❌ No compatible")

                # RECOMENDACIÓN DE IA
                with st.expander("🤖 Recomendación de ARCHIRAPID", expanded=False):
                    try:
                        # Preparar contexto para Gemini
                        finca_info = f"Finca de {plot_data[4]:,.0f} m², superficie edificable: {max_surface:,.0f} m²"
                        proyecto_info = f"Proyecto '{proyecto['title']}' de {area_construida:,.0f} m², precio €{proyecto.get('price', 0):,.0f}"

                        prompt = f"""Analiza por qué este proyecto arquitectónico es ideal para esta finca específica.
                        Finca: {finca_info}
                        Proyecto: {proyecto_info}
                        Responde en 2-3 frases concisas explicando la compatibilidad técnica y valor añadido."""

                        recomendacion = ai.generate_text(prompt)
                        st.write(recomendacion)
                    except Exception as e:
                        st.write("🤖 Recomendación no disponible temporalmente")

                # Botón de detalles
                if st.button("Ver Proyecto Completo", key=f"view_project_{proyecto['id']}", use_container_width=True):
                    st.session_state['selected_project_for_panel'] = proyecto['id']
                    st.session_state['show_project_search'] = False  # Ocultar búsqueda al ver detalles
                    st.rerun()

                st.markdown("---")
