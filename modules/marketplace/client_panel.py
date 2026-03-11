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
import base64 as _b64
from pathlib import Path
from modules.marketplace.compatibilidad import get_proyectos_compatibles
from modules.ai_house_designer import flow as ai_house_flow


def _get_glb_url(db_path: str) -> str | None:
    """Construye una URL válida para un GLB en cualquier entorno.

    - static/*  → Streamlit static serving (Cloud y localhost)
    - uploads/* → base64 data URL embebido (upload fresco en sesión)
    - no existe → None
    """
    rel = str(db_path).replace("\\", "/").lstrip("/")

    # Caso 1: archivo en static/ → usar static serving de Streamlit
    if rel.startswith("static/"):
        rel_no_static = rel[len("static/"):]
        try:
            host = st.context.headers.get("host", "localhost:8501")
        except Exception:
            host = "localhost:8501"
        protocol = "https" if ("." in host and "localhost" not in host) else "http"
        return f"{protocol}://{host}/app/static/{rel_no_static}"

    # Caso 2: archivo en disco (upload fresco) → base64
    if os.path.isfile(rel):
        with open(rel, "rb") as fh:
            b64data = _b64.b64encode(fh.read()).decode()
        return f"data:model/gltf-binary;base64,{b64data}"

    return None


def _get_vr_url(db_path: str) -> str | None:
    """Construye la URL del visor VR estático con el modelo incrustado."""
    glb_url = _get_glb_url(db_path)
    if not glb_url:
        return None
    try:
        host = st.context.headers.get("host", "localhost:8501")
    except Exception:
        host = "localhost:8501"
    protocol = "https" if ("." in host and "localhost" not in host) else "http"
    import urllib.parse
    return f"{protocol}://{host}/app/static/vr_viewer.html?model={urllib.parse.quote(glb_url, safe='')}"


def generate_3d_viewer_html(model_url: str, fmt: str = "glb") -> str:
    """Genera un visor Three.js para GLB/GLTF, OBJ y DAE.

    fmt: 'glb' | 'gltf' | 'obj' | 'dae'  (auto-detectado si se llama
    via _get_glb_url que ya normaliza la URL)
    """
    # unpkg es el CDN oficial y más estable para three.js
    _THREE_CORE   = "https://unpkg.com/three@0.128.0/build/three.module.js"
    _THREE_JSM    = "https://unpkg.com/three@0.128.0/examples/jsm"
    fmt = fmt.lower().lstrip(".")

    if fmt == "obj":
        _loader_import = f"import {{ OBJLoader }}     from '{_THREE_JSM}/loaders/OBJLoader.js';"
        _loader_cb = """
  const loader = new OBJLoader();
  fetch(MODEL_URL).then(r=>{{if(!r.ok)throw new Error('HTTP '+r.status);return r.text();}})
    .then(t=>{{const obj=loader.parse(t);scene.add(obj);_fit(obj);}}).catch(_err);"""
    elif fmt == "dae":
        _loader_import = f"import {{ ColladaLoader }} from '{_THREE_JSM}/loaders/ColladaLoader.js';"
        _loader_cb = """
  const loader = new ColladaLoader();
  fetch(MODEL_URL).then(r=>{{if(!r.ok)throw new Error('HTTP '+r.status);return r.text();}})
    .then(t=>{{const c=loader.parse(t);scene.add(c.scene);_fit(c.scene);}}).catch(_err);"""
    elif fmt == "fbx":
        _loader_import = f"import {{ FBXLoader }}     from '{_THREE_JSM}/loaders/FBXLoader.js';"
        _loader_cb = """
  const loader = new FBXLoader();
  fetch(MODEL_URL).then(r=>{{if(!r.ok)throw new Error('HTTP '+r.status);return r.arrayBuffer();}})
    .then(buf=>{{const obj=loader.parse(buf);scene.add(obj);_fit(obj);}}).catch(_err);"""
    else:  # glb / gltf — fetch ArrayBuffer + parse con callback (three.js 0.128.0)
        _loader_import = f"import {{ GLTFLoader }}    from '{_THREE_JSM}/loaders/GLTFLoader.js';"
        _loader_cb = """
  const loader = new GLTFLoader();
  fetch(MODEL_URL)
    .then(r=>{{if(!r.ok)throw new Error('HTTP '+r.status);return r.arrayBuffer();}})
    .then(buf=>{{loader.parse(buf,'',g=>{{scene.add(g.scene);_fit(g.scene);}},_err);}})
    .catch(_err);"""

    # Escapar la URL del modelo para JS (las data-URLs con base64 son seguras; las HTTPS también)
    _js_model_url = model_url.replace("\\", "\\\\").replace("`", "\\`")

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body{{margin:0;background:#0f172a;overflow:hidden;}}
  canvas{{display:block;}}
  #info{{position:absolute;top:10px;width:100%;text-align:center;
         font:13px/1 sans-serif;color:#e2e8f0;pointer-events:none;
         text-shadow:0 1px 4px #000;}}
  #badge{{position:absolute;top:10px;right:12px;
          background:rgba(37,99,235,.8);color:#fff;
          font:bold 11px monospace;padding:3px 9px;border-radius:6px;}}
</style>
</head>
<body>
<div id="info">⏳ Cargando modelo 3D…</div>
<div id="badge">.{fmt.upper()}</div>
<script type="importmap">
{{"imports":{{"three":"{_THREE_CORE}","three/examples/jsm/":"{_THREE_JSM}/"}}}}
</script>
<script type="module">
  import * as THREE from 'three';
  import {{ OrbitControls }} from 'three/examples/jsm/controls/OrbitControls.js';
  {_loader_import}

  const MODEL_URL = `{_js_model_url}`;
  const info = document.getElementById('info');
  const W = window.innerWidth, H = window.innerHeight;

  const renderer = new THREE.WebGLRenderer({{antialias:true}});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
  renderer.setSize(W,H);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.shadowMap.enabled = true;
  document.body.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f172a);
  scene.add(new THREE.GridHelper(500,50,0x334155,0x1e293b));

  const camera = new THREE.PerspectiveCamera(45,W/H,0.01,50000);
  camera.position.set(20,15,25);

  scene.add(new THREE.AmbientLight(0xffffff,0.7));
  const sun = new THREE.DirectionalLight(0xfff4e0,1.2);
  sun.position.set(200,400,200); sun.castShadow=true; scene.add(sun);
  const fill = new THREE.DirectionalLight(0xc9d9ff,0.35);
  fill.position.set(-100,100,-100); scene.add(fill);

  const ctrl = new OrbitControls(camera,renderer.domElement);
  ctrl.enableDamping=true; ctrl.dampingFactor=0.08;

  function _fit(obj){{
    const box=new THREE.Box3().setFromObject(obj);
    const c=box.getCenter(new THREE.Vector3());
    const s=box.getSize(new THREE.Vector3());
    const d=Math.max(s.x,s.y,s.z);
    obj.position.sub(c);
    camera.position.set(d*1.4,d*0.9,d*1.8);
    camera.lookAt(0,0,0); ctrl.target.set(0,0,0); ctrl.update();
    info.innerText='✅ Modelo cargado · Arrastra para rotar · Rueda para zoom';
  }}
  function _err(e){{
    console.error(e);
    info.innerText='⚠️ '+String(e.message||e);
  }}
  {_loader_cb}

  (function loop(){{requestAnimationFrame(loop);ctrl.update();renderer.render(scene,camera);}})();
  window.addEventListener('resize',()=>{{
    camera.aspect=window.innerWidth/window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth,window.innerHeight);
  }});
</script>
</body>
</html>'''

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

    # REDIRECT OWNERS: Si un propietario accede aquí por error, redirigirlo a su panel
    if st.session_state.get('logged_in') and st.session_state.get('role') == 'owner':
        from modules.marketplace import owners
        owners.main()
        return

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
            # st.session_state["user_role"] = "buyer"  # DESACTIVADO: Asignación ilegal
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
                    # st.session_state["user_role"] = "buyer"  # DESACTIVADO: Asignación ilegal
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
                    _db_path_3d = project["modelo_3d_glb"]
                    _fmt_3d = os.path.splitext(str(_db_path_3d))[1].lstrip(".").lower() or "glb"
                    _model_url = _get_glb_url(_db_path_3d)
                    if _model_url:
                        three_html = generate_3d_viewer_html(_model_url, fmt=_fmt_3d)
                        st.components.v1.html(three_html, height=700, scrolling=False)
                    else:
                        st.warning('⚠️ Modelo 3D no disponible en este entorno. Contacta con ArchiRapid.')
                else:
                    st.warning('⚠️ Este proyecto específico no dispone de archivos 3D/VR originales del arquitecto.')
        with col2:
            if st.button("🥽 Visor VR Inmersivo", type="secondary", use_container_width=True):
                if project.get("modelo_3d_glb"):
                    viewer_url = _get_vr_url(project["modelo_3d_glb"])
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

                # Consultar DB: ai_verification_cache y plano_catastral_path
                _plano_path_from_db = None
                try:
                    import sqlite3 as _sqlite3, json as _json_cache
                    _c2 = _sqlite3.connect("database.db", timeout=10)
                    _row = _c2.execute(
                        "SELECT ai_verification_cache, plano_catastral_path FROM plots WHERE id=?",
                        (plot_id,)
                    ).fetchone()
                    _c2.close()
                    if _row:
                        _plano_path_from_db = _row[1]
                        if _row[0]:
                            _cached = _json_cache.loads(_row[0])
                            superficie_pdf = float(_cached.get("superficie_m2", 0))
                            ref_catastral_pdf = _cached.get("referencia_catastral", "")
                            superficie_finca = plot_data[3] or 0
                            ref_catastral_finca = plot_data[2] or ''
                            superficie_ok = abs(superficie_pdf - superficie_finca) < 10
                            ref_ok = ref_catastral_pdf.strip() == ref_catastral_finca.strip()
                            verification_data = {
                                'superficie_pdf': superficie_pdf,
                                'ref_catastral_pdf': ref_catastral_pdf,
                                'superficie_finca': superficie_finca,
                                'ref_catastral_finca': ref_catastral_finca,
                                'superficie_ok': superficie_ok,
                                'ref_ok': ref_ok,
                                'datos_extraidos': {
                                    'superficie_m2': superficie_pdf,
                                    'referencia_catastral': ref_catastral_pdf,
                                    'municipio': _cached.get('municipio', ''),
                                },
                                'pdf_path': 'db_cache',
                                'timestamp': current_time,
                            }
                            st.session_state[cache_key] = verification_data
                            st.session_state[cache_time_key] = current_time
                            return verification_data
                except Exception:
                    pass

                # Si no hay cache o expiró, ejecutar verificación
                try:
                    from modules.marketplace.ai_engine import extraer_datos_catastral_completo

                    # Buscar archivos PDF catastrales
                    pdf_paths = [
                        Path("archirapid_extract/catastro_output/nota_catastral.pdf"),
                        Path("uploads/nota_catastral.pdf"),
                        Path("catastro_output/nota_catastral.pdf")
                    ]
                    # Añadir PDF específico de la finca si existe en DB
                    if _plano_path_from_db:
                        _p = Path(_plano_path_from_db.replace("\\", "/"))
                        if _p not in pdf_paths:
                            pdf_paths.insert(0, _p)

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

            # HERRAMIENTAS DE ACCIÓN - 5 botones independientes
            st.subheader("🛠️ Herramientas para tu Propiedad")

            col1, col2, col3 = st.columns(3)
            col4, col5, col6 = st.columns(3)

            with col1:
                if st.button("🎨 DISEÑAR CON IA", type="primary", use_container_width=True):
                    st.session_state["design_plot_id"] = plot_data[0]
                    st.session_state["ai_house_step"] = 1
                    st.session_state['show_project_search'] = False
                    st.session_state['show_prefab_config'] = False
                    st.query_params["page"] = "Diseñador de Vivienda"
                    st.rerun()

            with col2:
                if st.button("📐 PROYECTOS COMPATIBLES", type="secondary", use_container_width=True):
                    st.session_state['show_project_search'] = True
                    st.session_state['show_prefab_config'] = False
                    st.rerun()

            with col3:
                if st.button("🏠 CASA PREFABRICADA", type="secondary", use_container_width=True):
                    st.session_state['show_prefab_config'] = True
                    st.session_state['show_project_search'] = False
                    st.rerun()

            with col4:
                if st.button("💰 MIS TRANSACCIONES", type="secondary", use_container_width=True):
                    st.session_state['show_prefab_config'] = False
                    st.session_state['show_project_search'] = False
                    st.session_state['show_construccion_offers'] = False
                    st.info("💰 Mostrando historial de transacciones...")

            with col5:
                if st.button("📑 DOCUMENTACIÓN", type="secondary", use_container_width=True):
                    st.session_state['show_prefab_config'] = False
                    st.session_state['show_project_search'] = False
                    st.session_state['show_construccion_offers'] = False
                    st.info("📑 Accediendo a documentación...")

            with col6:
                # Contar ofertas pendientes para badge
                try:
                    _conn_of = db_conn()
                    _n_of = _conn_of.execute("""
                        SELECT COUNT(*) FROM construction_offers co
                        JOIN project_tablon pt ON co.tablon_id = pt.id
                        WHERE pt.client_email=? AND co.estado='enviada'
                    """, (client_email,)).fetchone()[0]
                    _conn_of.close()
                except Exception:
                    _n_of = 0
                _of_label = f"🏗️ OFERTAS ({_n_of})" if _n_of > 0 else "🏗️ OFERTAS"
                _of_type  = "primary" if _n_of > 0 else "secondary"
                if st.button(_of_label, type=_of_type, use_container_width=True):
                    st.session_state['show_prefab_config'] = False
                    st.session_state['show_project_search'] = False
                    st.session_state['show_construccion_offers'] = True
                    st.rerun()

            st.markdown("---")

            # SECCIONES INDEPENDIENTES — solo una activa a la vez
            if st.session_state.get('show_prefab_config', False):
                show_prefab_configurator(plot_data)
            elif st.session_state.get('show_project_search', False):
                show_integrated_project_search(client_email, plot_data)
            elif st.session_state.get('show_construccion_offers', False):
                show_construccion_offers(client_email)

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


def show_construccion_offers(client_email: str):
    """Comparativa de ofertas de constructores recibidas."""
    import json as _json

    st.markdown("### 🏗️ Ofertas de Construcción Recibidas")

    conn = db_conn()
    # Proyectos del cliente en el tablón
    proyectos = conn.execute("""
        SELECT id, project_name, province, style, total_area, total_cost, coste_m2, created_at
        FROM project_tablon WHERE client_email=? AND active=1 ORDER BY created_at DESC
    """, (client_email,)).fetchall()
    conn.close()

    if not proyectos:
        st.markdown("""
<div style="background:rgba(37,99,235,0.08);border:1px solid rgba(37,99,235,0.25);
            border-radius:12px;padding:20px 24px;text-align:center;">
  <div style="font-size:1.5rem;margin-bottom:8px;">🏗️</div>
  <div style="font-weight:700;color:#F8FAFC;margin-bottom:6px;">Aún no has publicado ningún proyecto</div>
  <div style="color:#94A3B8;font-size:13px;">
    Diseña tu vivienda con el Diseñador IA y al final pulsa<br>
    <b>"Publicar en Tablón de Obras"</b> para recibir ofertas de constructores.
  </div>
</div>""", unsafe_allow_html=True)
        return

    for proy in proyectos:
        tid, pname, province, style, area, total_cost, coste_m2, created_at = proy

        conn2 = db_conn()
        ofertas = conn2.execute("""
            SELECT co.id, co.provider_name, co.provider_email,
                   co.price_no_mat, co.price_with_mat, co.includes_materials,
                   co.plazo_semanas, co.garantia_anos, co.nota_tecnica,
                   co.breakdown_json, co.estado, co.created_at,
                   sp.experience_years, sp.specialties, sp.description, sp.service_area,
                   COALESCE(sp.is_featured, 0) as is_feat
            FROM construction_offers co
            LEFT JOIN service_providers sp ON co.provider_id = sp.id
            WHERE co.tablon_id=?
            ORDER BY COALESCE(sp.is_featured, 0) DESC, co.created_at ASC
        """, (tid,)).fetchall()
        conn2.close()

        n_of = len(ofertas)
        with st.expander(
            f"📋 {pname or 'Mi proyecto'} — {area:.0f} m² · {province} · "
            f"{'🆕 ' + str(n_of) + ' oferta(s) nueva(s)' if n_of else '⏳ Sin ofertas aún'}",
            expanded=True
        ):
            # Info del proyecto
            st.markdown(f"""
<div style="background:rgba(13,27,42,0.5);border:1px solid rgba(245,158,11,0.2);
            border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:12px;color:#CBD5E1;">
  <b>Presupuesto de referencia:</b> €{total_cost:,.0f} · €{coste_m2:,.0f}/m² · Estilo: {style or '—'} · Publicado: {created_at[:10]}
</div>""", unsafe_allow_html=True)

            if not ofertas:
                st.info("⏳ Aún no has recibido ofertas. Los constructores de tu zona serán notificados.")
                continue

            # ── Comparativa lado a lado (máx 3 por fila) ────────────────────
            cols = st.columns(min(len(ofertas), 3))
            for idx, of in enumerate(ofertas):
                (oid, prov_name, prov_email,
                 p_nm, p_wm, incl_mat,
                 plazo, garantia, nota,
                 breakdown_json, estado, of_date,
                 exp_years, specialties_json, sp_desc, sp_area,
                 is_feat) = of

                precio_show = float(p_wm or 0) if incl_mat else float(p_nm or 0)
                mat_label   = "con materiales" if incl_mat else "sin materiales"
                ahorro_pct  = int((1 - precio_show / total_cost) * 100) if total_cost else 0
                plazo_meses = round(plazo / 4.3, 1) if plazo else 0
                featured_c  = bool(is_feat)

                try:
                    specs = _json.loads(specialties_json) if specialties_json else []
                    from modules.marketplace.service_providers import _ESP_LABELS
                    specs_str = " · ".join(_ESP_LABELS.get(s, s) for s in specs[:3])
                except Exception:
                    specs_str = ""

                estado_color = {
                    "enviada":  "#F59E0B",
                    "aceptada": "#4ADE80",
                    "rechazada":"#F87171",
                }.get(estado, "#94A3B8")
                border_color = "#F59E0B" if featured_c else (estado_color + "55")

                col_idx = idx % 3
                with cols[col_idx]:
                    # Desglose partidas
                    breakdown_html = ""
                    try:
                        bd = _json.loads(breakdown_json) if breakdown_json else {}
                        for p in bd.get("partidas", []):
                            breakdown_html += (
                                f"<div style='display:flex;justify-content:space-between;font-size:11px;"
                                f"color:#94A3B8;border-bottom:1px solid rgba(255,255,255,0.05);padding:2px 0;'>"
                                f"<span>{p['name']}</span><span style='color:#F8FAFC'>€{p['cost']:,}</span></div>"
                            )
                    except Exception:
                        pass

                    feat_html = '<div style="display:inline-block;background:#F59E0B;color:#000;font-size:10px;font-weight:900;padding:2px 10px;border-radius:10px;margin-bottom:8px;">⭐ DESTACADO · VERIFICADO</div><br>' if featured_c else ''
                    st.markdown(f"""
<div style="background:{'rgba(245,158,11,0.08)' if featured_c else 'rgba(30,58,95,0.4)'};
            border:2px solid {border_color};
            border-radius:12px;padding:16px;margin-bottom:12px;">

  {feat_html}
  <div style="font-size:14px;font-weight:800;color:#F8FAFC;margin-bottom:2px;">
    🏗️ {prov_name or 'Constructor'}
  </div>
  <div style="font-size:11px;color:#64748B;margin-bottom:10px;">
    {sp_area or ''} · {exp_years or 0} años exp.
  </div>

  <div style="font-size:1.4rem;font-weight:900;color:#4ADE80;margin-bottom:2px;">
    €{precio_show:,.0f}
  </div>
  <div style="font-size:11px;color:#94A3B8;margin-bottom:8px;">{mat_label}</div>

  <div style="font-size:11px;color:#CBD5E1;line-height:1.9;">
    <b>€/m²:</b> €{precio_show/area:.0f}<br>
    <b>Plazo:</b> {plazo} sem ({plazo_meses:.0f} meses)<br>
    <b>Garantía:</b> {garantia} años<br>
    {'<b>Vs presupuesto:</b> <span style="color:' + ('#4ADE80' if ahorro_pct > 0 else '#F87171') + '">' + ('+' if ahorro_pct < 0 else '-') + str(abs(ahorro_pct)) + '%</span><br>' if ahorro_pct else ''}
    <b>Estado:</b> <span style="color:{estado_color};font-weight:700;">{estado.upper()}</span>
  </div>

  {('<div style="margin-top:10px;border-top:1px solid rgba(255,255,255,0.08);padding-top:8px;">' + breakdown_html + '</div>') if breakdown_html else ''}

  {('<div style="margin-top:8px;font-size:11px;color:#94A3B8;font-style:italic;">💬 ' + nota[:100] + ('…' if len(nota) > 100 else '') + '</div>') if nota else ''}
</div>""", unsafe_allow_html=True)

                    # Botones de acción
                    if estado == "enviada":
                        ba, br = st.columns(2)
                        with ba:
                            if st.button("✅ Aceptar", key=f"ac_{oid}", type="primary", use_container_width=True):
                                try:
                                    conn3 = db_conn()
                                    # Aceptar esta
                                    conn3.execute(
                                        "UPDATE construction_offers SET estado='aceptada' WHERE id=?", (oid,)
                                    )
                                    # Rechazar las demás del mismo proyecto
                                    conn3.execute(
                                        "UPDATE construction_offers SET estado='rechazada' WHERE tablon_id=? AND id!=?",
                                        (tid, oid)
                                    )
                                    conn3.commit(); conn3.close()
                                    try:
                                        from modules.marketplace.email_notify import _send
                                        _send(
                                            f"✅ <b>Oferta ACEPTADA</b>\n"
                                            f"Constructor: {prov_name} ({prov_email})\n"
                                            f"Proyecto: {pname} · €{precio_show:,.0f} · {plazo} sem\n"
                                            f"Cliente: {client_email}"
                                        )
                                    except Exception:
                                        pass
                                    st.success(f"✅ Oferta de {prov_name} aceptada. Le contactaremos para iniciar el proceso.")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error: {ex}")
                        with br:
                            if st.button("❌ Rechazar", key=f"re_{oid}", use_container_width=True):
                                try:
                                    conn4 = db_conn()
                                    conn4.execute(
                                        "UPDATE construction_offers SET estado='rechazada' WHERE id=?", (oid,)
                                    )
                                    conn4.commit(); conn4.close()
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error: {ex}")
                    elif estado == "aceptada":
                        st.success("✅ Oferta aceptada")
                        st.markdown(f"<div style='font-size:12px;color:#94A3B8;'>Contacto: {prov_email}</div>",
                                    unsafe_allow_html=True)


def show_prefab_configurator(plot_data):
    """Configurador de casa prefabricada para la finca adquirida.
    Limita el catálogo al 33% de la superficie edificable de la parcela."""
    conn = db_conn()
    cursor = conn.cursor()

    superficie_edificable = plot_data[4] or 0   # superficie_edificable de la finca
    superficie_total = plot_data[3] or 0         # m2 total
    base_m2 = superficie_edificable if superficie_edificable > 0 else superficie_total
    prefab_max_m2 = base_m2 * 0.33

    st.subheader("🏠 Configurador de Casa Prefabricada")
    st.markdown(
        f"**Superficie edificable de tu parcela:** {base_m2:,.0f} m²  ·  "
        f"**Máximo permitido para prefabricada (33%):** "
        f"<span style='color:#2563EB;font-weight:700'>{prefab_max_m2:,.0f} m²</span>",
        unsafe_allow_html=True
    )

    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        mat_filter = st.selectbox("Material", ["Todos", "Madera", "Modular acero", "Contenedor", "Hormigón prefab", "Mixto"], key="pf_mat")
    with col_f2:
        rooms_filter = st.selectbox("Habitaciones mínimas", [0, 1, 2, 3, 4, 5], key="pf_rooms")
    with col_f3:
        floors_filter = st.selectbox("Plantas", [0, 1, 2], format_func=lambda x: "Todas" if x == 0 else str(x), key="pf_floors")

    # Consulta catálogo con límite de m²
    query = "SELECT id, name, m2, rooms, bathrooms, floors, material, price, description FROM prefab_catalog WHERE active=1 AND m2 <= ?"
    params = [prefab_max_m2 if prefab_max_m2 > 0 else 9999]
    if mat_filter != "Todos":
        query += " AND material = ?"
        params.append(mat_filter)
    if rooms_filter > 0:
        query += " AND rooms >= ?"
        params.append(rooms_filter)
    if floors_filter > 0:
        query += " AND floors = ?"
        params.append(floors_filter)
    query += " ORDER BY m2"

    cursor.execute(query, params)
    prefabs = cursor.fetchall()
    conn.close()

    if not prefabs:
        st.warning(f"No hay modelos prefabricados que quepan en tu parcela con esos filtros (máx. {prefab_max_m2:,.0f} m²).")
        return

    st.markdown(f"**{len(prefabs)} modelo(s) compatibles con tu parcela:**")

    # Grid 5 columnas
    N = 5
    cols = st.columns(N)
    for idx, pf in enumerate(prefabs):
        pf_id, name, m2, rooms, bathrooms, floors, material, price, description = pf
        with cols[idx % N]:
            selected = st.session_state.get('prefab_selected_id') == pf_id
            border_color = "#2563EB" if selected else "#E2E8F0"
            bg_color = "#EFF6FF" if selected else "#F8FAFC"
            st.markdown(
                f'<div style="background:{bg_color};border:2px solid {border_color};border-radius:10px;'
                f'padding:12px 8px 8px;text-align:center;margin-bottom:6px;">'
                f'<div style="font-size:1.8em;">🏠</div>'
                f'<div style="font-weight:700;font-size:0.82em;color:#0D1B2A;line-height:1.2;">{name}</div>'
                f'<div style="font-size:0.75em;color:#64748B;margin:4px 0;">{m2} m² · {rooms}hab · {bathrooms}baños · {floors}pl</div>'
                f'<div style="font-size:0.73em;color:#475569;margin-bottom:4px;">{material}</div>'
                f'<div style="font-weight:700;color:#2563EB;font-size:0.88em;">€{price:,.0f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("Seleccionar" if not selected else "✓ Elegido", key=f"pf_sel_{pf_id}", use_container_width=True):
                st.session_state['prefab_selected_id'] = pf_id
                st.rerun()

    # Detalle del modelo seleccionado
    selected_id = st.session_state.get('prefab_selected_id')
    if selected_id:
        conn2 = db_conn()
        cur2 = conn2.cursor()
        cur2.execute("SELECT id, name, m2, rooms, bathrooms, floors, material, price, description FROM prefab_catalog WHERE id=?", (selected_id,))
        sel = cur2.fetchone()
        conn2.close()
        if sel:
            pf_id, name, m2, rooms, bathrooms, floors, material, price, description = sel
            st.markdown("---")
            st.markdown(f"### ✅ Modelo seleccionado: **{name}**")
            col_d1, col_d2 = st.columns([2, 1])
            with col_d1:
                st.markdown(f"_{description}_")
                st.markdown(f"- **Superficie:** {m2} m²  ·  **Habitaciones:** {rooms}  ·  **Baños:** {bathrooms}  ·  **Plantas:** {floors}")
                st.markdown(f"- **Material:** {material}")
            with col_d2:
                finca_price = plot_data[8] or 0  # price column from plots
                install_est = round(m2 * 180, -2)  # €180/m² instalación estimada
                total = finca_price + price + install_est
                st.metric("Precio prefabricada", f"€{price:,.0f}")
                st.metric("Instalación estimada", f"€{install_est:,.0f}")
                st.metric("TOTAL finca + casa", f"€{total:,.0f}", delta="precio orientativo")

            if st.button("📨 Solicitar Presupuesto Detallado", type="primary", use_container_width=True, key="pf_request"):
                st.success(f"✅ Solicitud enviada para **{name}** sobre tu finca **{plot_data[1]}**. Recibirás respuesta en 24-48h en tu email.")
                st.balloons()


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
    """Proyectos compatibles con la finca del cliente.
    Filtro automático: 33% de superficie edificable. Único filtro manual: presupuesto."""
    from modules.marketplace.marketplace import get_project_display_image
    import base64, io

    st.markdown("---")
    st.subheader("📐 Proyectos Compatibles con tu Finca")

    if st.button("⬅️ Volver", key="back_to_property"):
        st.session_state['show_project_search'] = False
        st.rerun()

    # Calcular superficie máxima edificable
    # plot_data[3] = m2 total, plot_data[4] = superficie_edificable
    superficie_edificable = plot_data[4] if (len(plot_data) > 4 and plot_data[4]) else None
    m2_total = plot_data[3] if (len(plot_data) > 3 and plot_data[3]) else 0

    verified_m2 = st.session_state.get('verified_m2')
    if verified_m2:
        max_surface = float(verified_m2)
        source_info = "verificado por IA desde nota catastral"
    elif superficie_edificable:
        max_surface = float(superficie_edificable)
        source_info = "superficie edificable registrada"
    else:
        max_surface = float(m2_total) * 0.33
        source_info = "33% del total de la parcela (estimación)"

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.info(f"📐 **Máx. construible:** {max_surface:,.0f} m²  ·  _{source_info}_")
    with col_i2:
        max_precio = st.number_input(
            "Presupuesto máximo (€)",
            min_value=0, value=0, step=5000,
            help="0 = sin límite de precio",
            key="proj_max_precio"
        )

    # Buscar proyectos compatibles
    with st.spinner("Buscando proyectos compatibles..."):
        proyectos = get_proyectos_compatibles(client_parcel_size=max_surface, client_email=client_email)

    # Filtrar por presupuesto si se indicó
    if max_precio > 0:
        proyectos = [p for p in proyectos if (p.get('price') or 0) <= max_precio]

    if not proyectos:
        st.warning(f"No hay proyectos que quepan en tu parcela ({max_surface:,.0f} m² máx.)" +
                   (f" con presupuesto ≤ €{max_precio:,.0f}" if max_precio > 0 else "") + ".")
        st.info("💡 Contacta con nosotros para proyectos personalizados.")
        return

    st.markdown(f"**{len(proyectos)} proyecto(s) compatibles:**")

    N = 5
    cols = st.columns(N)
    for idx, proyecto in enumerate(proyectos):
        area = proyecto.get('m2_construidos') or proyecto.get('area_m2') or 0
        precio = proyecto.get('price') or 0
        with cols[idx % N]:
            # Imagen base64 altura fija
            thumb = get_project_display_image(proyecto['id'], image_type='main')
            _shown = False
            try:
                import os as _os
                if isinstance(thumb, str) and _os.path.exists(thumb):
                    with open(thumb, 'rb') as _tf:
                        _raw = _tf.read()
                    _ext = thumb.rsplit('.', 1)[-1].lower()
                    _mime = "image/png" if _ext == "png" else "image/jpeg"
                    b64 = base64.b64encode(_raw).decode()
                elif isinstance(thumb, bytes):
                    b64 = base64.b64encode(thumb).decode()
                    _mime = "image/jpeg"
                else:
                    buf = io.BytesIO()
                    thumb.save(buf, format='JPEG')
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    _mime = "image/jpeg"
                st.markdown(
                    f'<img src="data:{_mime};base64,{b64}" '
                    f'style="width:100%;height:130px;object-fit:cover;border-radius:8px;display:block;">',
                    unsafe_allow_html=True
                )
                _shown = True
            except Exception:
                pass
            if not _shown:
                st.markdown('<div style="height:130px;background:#F1F5F9;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:2em;">🏗️</div>', unsafe_allow_html=True)

            title = proyecto.get('title', 'Proyecto')
            pct = f"{area/max_surface*100:.0f}%" if max_surface > 0 and area > 0 else "—"
            st.markdown(f"**{title[:26]}{'…' if len(title)>26 else ''}**")
            st.caption(f"📐 {area:,.0f} m²  ({pct} de tu parcela)")
            st.caption(f"💰 €{precio:,.0f}" if precio else "💰 Consultar")
            if st.button("Ver proyecto →", key=f"ips_proj_{proyecto['id']}", use_container_width=True):
                st.session_state['selected_project_for_panel'] = proyecto['id']
                st.session_state['show_project_search'] = False
                st.rerun()
