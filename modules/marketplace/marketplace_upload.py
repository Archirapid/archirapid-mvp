# modules/marketplace/marketplace_upload.py
"""
Marketplace de proyectos para arquitectos - ARCHIRAPID MVP
Permite subir proyectos completos al catálogo
"""

"""
⚠️ SECCIÓN BLINDADA – ARQUITECTOS (NO MODIFICAR SIN REVISIÓN)

Este archivo forma parte del núcleo Arquitectos.
- No debe ser importado directamente por otras secciones.
- El acceso debe hacerse exclusivamente vía:
  render_architects_panel(ctx)

Cambios permitidos:
- Añadir campos opcionales a proyectos
- Ajustes menores de UI internos

Cambios PROHIBIDOS:
- Importar lógica de clientes, IA o compras
- Acceder a st.session_state fuera del flujo actual
- Cambiar contratos de datos sin versión nueva

Responsable técnico: CORE MARKETPLACE
"""

import streamlit as st
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .data_access import save_proyecto, get_usuario
from .utils import save_upload
from .documentacion import generar_memoria_constructiva, generar_presupuesto_estimado
from src import db
from .export_ops import generar_paquete_descarga
from archirapid_extract.parse_project_memoria import extract_text_from_pdf, parse_memoria_text

# === CONFIGURACIÓN ===
UPLOAD_DIR = "uploads/proyectos_arquitectos"
ALLOWED_EXTENSIONS = {
    '3d': ['obj', 'fbx', 'gltf', 'glb', 'dae'],
    'rv': ['jpg', 'png', 'jpeg', 'mp4', 'webm'],
    'pdf': ['pdf'],
    'cad': ['dxf', 'dwg', 'svg'],
    'json': ['json']
}

os.makedirs(UPLOAD_DIR, exist_ok=True)

# === FUNCIONES AUXILIARES ===
def _sanitize_filename(filename: str) -> str:
    """Limpia el nombre del archivo para evitar problemas de seguridad"""
    return re.sub(r'[^\w\.-]', '_', filename)

def _save_file_to_disk(file_obj, directory: str, prefix: str = None) -> Optional[str]:
    """Guarda un archivo en el disco y devuelve la ruta"""
    if not file_obj:
        return None
    
    filename = _sanitize_filename(file_obj.name)
    if prefix:
        filename = f"{prefix}_{filename}"
    
    filepath = os.path.join(directory, filename)
    with open(filepath, 'wb') as f:
        f.write(file_obj.getbuffer())
    
    return filepath

def _sync_project_columns(project_id: str):
    """Sincroniza las columnas de la base de datos con el JSON de características"""
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        
        # Obtener el JSON de características
        cur.execute("SELECT characteristics_json FROM projects WHERE id=?", (project_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return
        
        # Convertir JSON a diccionario
        try:
            characteristics = json.loads(row[0])
        except:
            return
        
        # Preparar las actualizaciones
        updates = {}
        if 'habitaciones' in characteristics:
            updates['habitaciones'] = int(characteristics['habitaciones'])
        if 'baños' in characteristics or 'banos' in characteristics:
            banos = characteristics.get('baños') or characteristics.get('banos')
            updates['banos'] = int(banos)
        if 'plantas' in characteristics:
            updates['plantas'] = int(characteristics['plantas'])
        if 'm2_construidos' in characteristics:
            updates['m2_construidos'] = float(characteristics['m2_construidos'])
        if 'piscina' in characteristics:
            updates['piscina'] = 1 if characteristics['piscina'] else 0
        if 'garaje' in characteristics:
            updates['garaje'] = 1 if characteristics['garaje'] else 0
        if 'imagenes' in characteristics:
            updates['foto_principal'] = characteristics['imagenes']
        if 'modelo_3d_path' in characteristics:
            updates['modelo_3d_path'] = characteristics['modelo_3d_path']
        
        # Aplicar actualizaciones si hay algo que actualizar
        if updates:
            columns = ', '.join([f"{col}=?" for col in updates.keys()])
            values = list(updates.values()) + [project_id]
            sql = f"UPDATE projects SET {columns} WHERE id=?"
            cur.execute(sql, values)
            conn.commit()
            
    except Exception:
        pass  # No mostrar errores al usuario
    finally:
        try:
            conn.close()
        except:
            pass

# === FUNCIONES PRINCIPALES ===
def show_project_upload_form(arquitecto_id: int) -> Optional[Dict]:
    """
    Muestra el formulario para subir un proyecto de arquitecto
    """
    st.subheader("📤 Subir Nuevo Proyecto Arquitectónico")
    
    with st.form("project_upload_form"):
        # Información básica del proyecto
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Título del proyecto", placeholder="Casa Moderna Minimalista")
            description = st.text_area("Descripción", placeholder="Proyecto de vivienda unifamiliar...")
            tags = st.multiselect("Etiquetas", ["Moderno", "Clásico", "Minimalista", "Ecológico"])
        
        with col2:
            project_type = st.selectbox("Tipo de proyecto", ["Residencial unifamiliar", "Residencial plurifamiliar", "Comercial", "Industrial"])
            area_m2 = st.number_input("Superficie construida (m²)", min_value=50.0, value=150.0, step=10.0)
            price = st.number_input("Presupuesto ejecución (€)", min_value=1000.0, value=50000.0, step=1000.0)
        
        # Archivos requeridos
        st.markdown("---")
        st.subheader("📁 Archivos del Proyecto")
        
        col_files1, col_files2 = st.columns(2)
        with col_files1:
            memoria_pdf = st.file_uploader("Memoria descriptiva (PDF)", type=['pdf'], help="Documento técnico obligatorio")
            modelo_3d = st.file_uploader("Modelo 3D", type=ALLOWED_EXTENSIONS['3d'], help="OBJ, FBX, GLTF, etc.")
            renders = st.file_uploader("Renders/Imágenes", type=ALLOWED_EXTENSIONS['rv'], accept_multiple_files=True)
        
        with col_files2:
            planos_cad = st.file_uploader("Planos CAD (máx. 3)", type=ALLOWED_EXTENSIONS["cad"], help="DXF, DWG, SVG", accept_multiple_files=True)
            distribucion_json = st.file_uploader("Distribución (JSON)", type=['json'], help="Opcional - distribución de habitaciones")

        st.markdown("**📋 Documentación Técnica CTE/LOE (opcional pero recomendado)**")
        st.caption("Cuanta más documentación, más valor tiene el proyecto y mayor visibilidad en el catálogo.")
        doc_col1, doc_col2, doc_col3 = st.columns(3)
        with doc_col1:
            presupuesto_pdf = st.file_uploader(
                "Presupuesto y mediciones (PDF)",
                type=["pdf"], key="up_presupuesto",
                help="Presupuesto detallado por capítulos y mediciones"
            )
        with doc_col2:
            estudio_seguridad_pdf = st.file_uploader(
                "Estudio básico seguridad y salud (PDF)",
                type=["pdf"], key="up_seguridad",
                help="ESS según RD 1627/1997"
            )
        with doc_col3:
            especificaciones_pdf = st.file_uploader(
                "Especificaciones técnicas NNEE (PDF)",
                type=["pdf"], key="up_specs",
                help="Pliego de condiciones / especificaciones técnicas"
            )
        
        # Características arquitectónicas
        st.markdown("---")
        st.subheader("🏗️ Características")
        
        char_col1, char_col2 = st.columns(2)
        with char_col1:
            habitaciones = st.number_input("Habitaciones", min_value=0, value=3, step=1)
            banos = st.number_input("Baños", min_value=0, value=2, step=1)
            plantas = st.selectbox("Número de plantas", [1, 2, 3, 4, 5], index=0)
        
        with char_col2:
            piscina = st.checkbox("Piscina")
            garaje = st.checkbox("Garaje")
            jardin = st.checkbox("Jardín")
            terraza = st.checkbox("Terraza")
        
        # Botón de envío
        submitted = st.form_submit_button("🚀 Publicar Proyecto", type="primary")
        
        if submitted:
            return _process_project_upload(
                arquitecto_id=arquitecto_id,
                title=title,
                description=description,
                project_type=project_type,
                area_m2=area_m2,
                price=price,
                tags=tags,
                files={
                    'memoria_pdf': memoria_pdf,
                    'modelo_3d': modelo_3d,
                    'renders': renders,
                    'planos_cad': planos_cad,
                    'distribucion_json': distribucion_json,
                    'presupuesto_pdf': presupuesto_pdf,
                    'estudio_seguridad_pdf': estudio_seguridad_pdf,
                    'especificaciones_pdf': especificaciones_pdf,
                },
                characteristics={
                    'habitaciones': habitaciones,
                    'banos': banos,
                    'plantas': plantas,
                    'piscina': piscina,
                    'garaje': garaje,
                    'jardin': jardin,
                    'terraza': terraza
                }
            )
    
    return None

def _process_project_upload(arquitecto_id: int, title: str, description: str, project_type: str,
                          area_m2: float, price: float, tags: List[str], files: Dict, 
                          characteristics: Dict) -> Optional[Dict]:
    """
    Procesa la subida de archivos y guarda el proyecto
    """
    try:
        # Validaciones básicas
        if not title or not description:
            st.error("❌ El título y la descripción son obligatorios")
            return None
        
        if not files['memoria_pdf']:
            st.error("❌ La memoria descriptiva en PDF es obligatoria")
            return None
        
        if not files['modelo_3d']:
            st.error("❌ El modelo 3D es obligatorio")
            return None
        
        # Crear directorio para el proyecto
        import time
        timestamp = int(time.time())
        project_dir = os.path.join(UPLOAD_DIR, f"arquitecto_{arquitecto_id}_{timestamp}")
        os.makedirs(project_dir, exist_ok=True)
        
        # Guardar archivos
        saved_files = {}
        saved_files['memoria_pdf_path'] = _save_file_to_disk(files['memoria_pdf'], project_dir, 'memoria')
        saved_files['modelo_3d_path'] = _save_file_to_disk(files['modelo_3d'], project_dir, 'modelo_3d')
        saved_files['distribucion_json_path'] = _save_file_to_disk(files['distribucion_json'], project_dir, 'distribucion')

        # Guardar renders múltiples
        render_paths = []
        if files['renders']:
            for i, render_file in enumerate(files['renders']):
                render_path = _save_file_to_disk(render_file, project_dir, f'render_{i}')
                if render_path:
                    render_paths.append(render_path)

        # Guardar planos CAD múltiples (máx. 3)
        cad_paths = []
        if files['planos_cad']:
            for i, cad_file in enumerate(files['planos_cad'][:3]):
                cad_path = _save_file_to_disk(cad_file, project_dir, f'planos_{i}')
                if cad_path:
                    cad_paths.append(cad_path)

        # Subir documentación técnica CTE/LOE a Supabase (opcional)
        url_presupuesto = save_upload(files.get('presupuesto_pdf'), prefix="presupuesto_arq") if files.get('presupuesto_pdf') else None
        url_estudio_seg = save_upload(files.get('estudio_seguridad_pdf'), prefix="seguridad_arq") if files.get('estudio_seguridad_pdf') else None
        url_specs       = save_upload(files.get('especificaciones_pdf'), prefix="specs_arq")     if files.get('especificaciones_pdf') else None
        # planos_dwg: primer archivo CAD subido a Supabase
        url_planos_dwg  = save_upload(files['planos_cad'][0], prefix="dwg_arq") if files.get('planos_cad') else None

        # Preparar datos del proyecto
        project_id = f"p_{timestamp}_{arquitecto_id}"
        
        # Crear JSON de características
        characteristics_json = {
            'habitaciones': characteristics['habitaciones'],
            'baños': characteristics['banos'],
            'banos': characteristics['banos'],  # Para compatibilidad
            'plantas': characteristics['plantas'],
            'm2_construidos': area_m2,
            'piscina': characteristics['piscina'],
            'garaje': characteristics['garaje'],
            'jardin': characteristics['jardin'],
            'terraza': characteristics['terraza'],
            'imagenes': render_paths[0] if render_paths else None,
            'modelo_3d_path': saved_files['modelo_3d_path']
        }
        
        # Datos completos del proyecto
        project_data = {
            'id': project_id,
            'title': title,
            'architect_id': str(arquitecto_id),
            'area_m2': int(area_m2),
            'price': price,
            'description': description,
            'created_at': datetime.utcnow().isoformat(),
            'characteristics_json': json.dumps(characteristics_json, ensure_ascii=False),
            # Columnas individuales para compatibilidad
            'habitaciones': characteristics['habitaciones'],
            'banos': characteristics['banos'],
            'plantas': characteristics['plantas'],
            'piscina': 1 if characteristics['piscina'] else 0,
            'garaje': 1 if characteristics['garaje'] else 0,
            'foto_principal': render_paths[0] if render_paths else None,
            'modelo_3d_glb': saved_files['modelo_3d_path'],
            'imagenes': render_paths[0] if render_paths else None,
            # Rutas de archivos
            'memoria_pdf': saved_files['memoria_pdf_path'],
            'cad_dwg_path': json.dumps(cad_paths) if cad_paths else None,
            'planos_dwg': url_planos_dwg,
            'imagenes_path': render_paths[0] if render_paths else None,
            # Guardar TODAS las imágenes en la galería (la primera será la principal)
            'galeria_fotos': json.dumps(render_paths),
            # Documentación técnica CTE/LOE (Supabase)
            'presupuesto_pdf': url_presupuesto,
            'estudio_seguridad_pdf': url_estudio_seg,
            'especificaciones_pdf': url_specs,
            # Datos adicionales
            'autor_tipo': 'arquitecto',
            'autor_id': arquitecto_id,
            'tipo': project_type.lower().replace(' ', '_'),
            'total_m2': area_m2,
            'precio_venta': price,
            'etiquetas': tags,
            'estado_publicacion': 'publicada',
            'validacion_ok': True
        }
        
        # Procesar automáticamente la memoria técnica con OCR y análisis
        if saved_files.get('memoria_pdf_path'):
            try:
                # Extraemos el texto real del PDF que acabas de subir
                texto_extraido = extract_text_from_pdf(saved_files['memoria_pdf_path'])
                # Lo convertimos en datos técnicos (m2, habitaciones, etc.)
                datos_tecnicos = parse_memoria_text(texto_extraido)
                
                # Estos son los datos que irán a las nuevas columnas de la DB
                project_data['ocr_text'] = texto_extraido
                project_data['parsed_data_json'] = json.dumps(datos_tecnicos)
            except Exception as e:
                st.error(f"Error procesando memoria técnica: {e}")
        
        # Guardar en base de datos
        try:
            db.insert_project(project_data)
            _sync_project_columns(project_id)
            st.success("✅ Proyecto publicado exitosamente!")
            return project_data
        except Exception as e:
            st.error(f"❌ Error al guardar en base de datos: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando el proyecto: {str(e)}")
        return None

# === FUNCIONES DE EXPLORACIÓN ===
def get_projects_by_architect(architect_id: int) -> List[Dict]:
    """
    Obtiene los proyectos de un arquitecto específico
    """
    try:
        # Intentar usar list_proyectos si existe
        try:
            from src.db import list_proyectos
            return list_proyectos({'architect_id': str(architect_id)})
        except ImportError:
            # Fallback: usar get_all_projects y filtrar manualmente
            all_projects = db.get_all_projects()
            if hasattr(all_projects, 'to_dict'):  # Es un DataFrame
                projects_list = all_projects.to_dict('records')
            else:
                projects_list = all_projects
            
            # Filtrar por arquitecto
            return [p for p in projects_list if str(p.get('architect_id', '')) == str(architect_id)]
    except Exception:
        return []

def get_all_architect_projects() -> List[Dict]:
    """
    Obtiene todos los proyectos de arquitectos
    """
    try:
        # Intentar usar list_proyectos si existe
        try:
            from src.db import list_proyectos
            return list_proyectos({'autor_tipo': 'arquitecto'})
        except ImportError:
            # Fallback: usar get_all_projects y filtrar manualmente
            all_projects = db.get_all_projects()
            if hasattr(all_projects, 'to_dict'):  # Es un DataFrame
                projects_list = all_projects.to_dict('records')
            else:
                projects_list = all_projects
            
            # Filtrar por tipo arquitecto (si existe la columna)
            return [p for p in projects_list if p.get('autor_tipo') == 'arquitecto']
    except Exception:
        return []

def display_architect_project(project: Dict, show_buy_button: bool = True):
    """
    Muestra los detalles de un proyecto de arquitecto
    show_buy_button: Si False, oculta opciones de compra (modo competencia)
    """
    st.subheader(f"🏗️ {project.get('title', project.get('nombre', 'Proyecto'))}")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write(f"**Descripción:** {project.get('description', project.get('descripcion', 'Sin descripción'))}")
        st.write(f"**Tipo:** {project.get('tipo', 'No especificado').replace('_', ' ').title()}")
        st.write(f"**Superficie:** {project.get('area_m2', project.get('total_m2', 0))} m²")

        if project.get('etiquetas'):
            st.write(f"**Etiquetas:** {', '.join(project['etiquetas'])}")

    with col2:
        if show_buy_button:
            # Mostrar precio y opciones de compra para clientes
            price = project.get('price', project.get('precio_venta', 0))
            st.metric("Precio de venta", f"€{price:,.0f}")

            # Mostrar archivos disponibles
            archivos = []
            if project.get('modelo_3d_path'): archivos.append("3D")
            if project.get('imagenes') or project.get('foto_principal'): archivos.append("Imágenes")
            if project.get('memoria_pdf_path'): archivos.append("PDF")
            if project.get('cad_dwg_path'): archivos.append("CAD")

            if archivos:
                st.write(f"**Archivos:** {', '.join(archivos)}")

        else:
            # Modo competencia - solo mostrar archivos disponibles, sin precio ni compra
            archivos = []
            if project.get('modelo_3d_path'): archivos.append("3D")
            if project.get('imagenes') or project.get('foto_principal'): archivos.append("Imágenes")
            if project.get('memoria_pdf_path'): archivos.append("PDF")
            if project.get('cad_dwg_path'): archivos.append("CAD")

            if archivos:
                st.write(f"**Archivos:** {', '.join(archivos)}")

            # Mensaje informativo para arquitectos
            st.info("💼 Proyecto de competencia - Solo para referencia")

# === FUNCIÓN PRINCIPAL ===
def main():
    """
    Página principal del marketplace para arquitectos
    """
    # Botón volver al marketplace — siempre visible arriba
    if st.button("← Volver al marketplace", key="arq_back_home"):
        st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
        try:
            del st.query_params["page"]
        except Exception:
            pass
        st.stop()

    # si acabamos de registrarnos y no tenemos arquitecto_id, forzamos el login
    frm_key = "FormSubmitter:registro_form-🚀 Registrarme y Acceder"
    if st.session_state.get('login_role') == 'architect' and st.session_state.get(frm_key) and not st.session_state.get('arquitecto_id'):
        # asignar ID basado en email si existe, sino generar temporal
        sid = st.session_state.get('auth_prefill_email') or f"temp_{int(time.time())}"
        st.session_state['arquitecto_id'] = sid
        st.session_state.setdefault('arquitecto_plan', None)
        st.session_state['authenticated'] = True
        # eliminar flag para no repetir
        st.session_state.pop(frm_key, None)

    st.title("👷 Arquitectos - Marketplace")
    
    # si acabamos de marcar registro, saltar directamente a formulario de auth
    if st.session_state.pop('architect_redirect_registration', False):
        from modules.marketplace import auth
        auth.show_registration()
        return

    # Límites de planes
    PLAN_LIMITS = {
        'student': 1,  # Plan gratuito para estudiantes: 1 proyecto
        'basic': 1,    # Plan básico: 1 proyecto - 90€/mes
        'pro': 5       # Plan pro: 5 proyectos - 200€/mes
    }
    
    # Verificar si el usuario está logueado
    if 'arquitecto_id' not in st.session_state:
        st.info("Para gestionar proyectos, inicia sesión o regístrate como arquitecto")
        
        with st.form("architect_login"):
            col1, col2 = st.columns(2)
            with col1:
                architect_id = st.text_input("ID de Arquitecto (si ya tienes)")
                email = st.text_input("Email")
            with col2:
                name = st.text_input("Nombre completo")
                telefono = st.text_input("Teléfono", placeholder="+34 600 000 000")
            
            submitted = st.form_submit_button("Entrar / Registrarse")
            
            if submitted:
                try:
                    if architect_id and architect_id.strip().isdigit():
                        # Login con ID existente
                        aid = int(architect_id.strip())
                        architect_data = get_usuario(aid)
                        st.success(f"Bienvenido {architect_data.get('nombre', 'Arquitecto')}!")
                        st.session_state['arquitecto_id'] = aid
                        st.session_state.setdefault('arquitecto_plan', None)
                        st.rerun()
                    else:
                        # Nuevo arquitecto: marcar para redirigir al formulario rico
                        st.session_state['login_role'] = 'architect'
                        # prefills para el formulario completo
                        st.session_state['auth_prefill_name'] = name
                        st.session_state['auth_prefill_email'] = email
                        st.session_state['auth_prefill_phone'] = telefono
                        st.session_state['architect_redirect_registration'] = True
                        st.rerun()
                        return
                except Exception as e:
                    st.error(f"Error: {e}")
        return
    
    # Usuario logueado
    architect_id = st.session_state['arquitecto_id']
    current_plan = st.session_state.get('arquitecto_plan')
    
    # Si no tiene plan, mostrar selección
    if not current_plan:
        st.warning("Selecciona un plan para publicar proyectos")
        selected_plan = st.radio("Elige tu plan:", 
                                ["🎓 Estudiante (1 proyecto - GRATIS)", 
                                 "💼 Básico (1 proyecto - 90€/mes)", 
                                 "🏢 Pro (5 proyectos - 200€/mes)"])
        
        if st.button("Activar Plan"):
            if "Estudiante" in selected_plan:
                st.session_state['arquitecto_plan'] = 'student'
            elif "Básico" in selected_plan:
                st.session_state['arquitecto_plan'] = 'basic'
            else:
                st.session_state['arquitecto_plan'] = 'pro'
            st.success(f"Plan {selected_plan.split(' (')[0]} activado!")
            st.rerun()
        
        # Mostrar proyectos existentes aunque no pueda subir
        st.markdown("---")
        st.subheader("📋 Proyectos Disponibles")
        available_projects = get_all_architect_projects()
        for project in available_projects:
            display_architect_project(project, show_buy_button=False)
            st.divider()
        return
    
    # Usuario con plan activo
    plan_limit = PLAN_LIMITS.get(current_plan, 1)
    user_projects = get_projects_by_architect(architect_id)
    used_slots = len(user_projects)
    remaining_slots = max(0, plan_limit - used_slots)
    
    # Mostrar nombre del plan
    plan_names = {
        'student': '🎓 Estudiante (GRATIS)',
        'basic': '💼 Básico (90€/mes)',
        'pro': '🏢 Pro (200€/mes)'
    }
    current_plan_name = plan_names.get(current_plan, current_plan.upper())
    
    st.success(f"Conectado como Arquitecto ID {architect_id} - Plan: {current_plan_name} ({used_slots}/{plan_limit} proyectos)")
    
    # Menú de navegación
    menu_option = st.radio("¿Qué quieres hacer?", 
                          ["Ver Mis Proyectos", "Explorar Mercado", "Subir Proyecto"], 
                          horizontal=True)
    
    if menu_option == "Ver Mis Proyectos":
        st.subheader("📂 Mis Proyectos")
        if user_projects:
            for project in user_projects:
                display_architect_project(project)
                st.divider()
        else:
            st.info("Aún no tienes proyectos publicados")
    
    elif menu_option == "Explorar Mercado":
        st.subheader("🛒 Catálogo de Proyectos")
        market_projects = get_all_architect_projects()
        for project in market_projects:
            display_architect_project(project, show_buy_button=False)
            st.divider()
    
    elif menu_option == "Subir Proyecto":
        st.subheader("📤 Subir Nuevo Proyecto")
        if remaining_slots <= 0:
            st.error("Has alcanzado el límite de tu plan. Actualiza para subir más proyectos.")
        else:
            result = show_project_upload_form(architect_id)
            if result:
                st.success("Proyecto subido correctamente. Recargando...")
                st.rerun()