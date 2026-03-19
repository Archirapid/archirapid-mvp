"""
BLOQUEO DOCUMENTAL - SECCIÓN "PROYECTOS DISPONIBLES"

Esta sección está BLINDADA y protegida contra modificaciones no autorizadas.

INPUTS (lectura):
- Parámetros: client_email (email del cliente logueado)
- Session State: last_search_params_v2 (parámetros de búsqueda previos), client_logged_in (estado de login)
- DB Reads: projects (lista de proyectos), ventas_proyectos (verificación de compras previas)
- Dependencias: get_proyectos_compatibles() (función de filtrado)

OUTPUTS (efectos):
- Session State: last_search_params_v2 (actualización de filtros)
- Query Params: selected_project_v2 (ID de proyecto seleccionado para navegación)
- DB Writes: ventas_proyectos (registro de compras PDF/CAD)
- UI Effects: Grid de proyectos, filtros, mensajes de compra, reruns

ADVERTENCIA: NO modificar lógica interna sin romper contrato.
Cualquier cambio debe pasar por el wrapper render_projects_available(ctx).
Usar solo el wrapper como punto de entrada desde fuera de la sección.
"""

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import os

# Streamlit Cloud: sync secrets → os.environ so all os.getenv() calls work in production
try:
    import streamlit as _st_secrets
    for _sk, _sv in _st_secrets.secrets.items():
        if isinstance(_sv, str):
            os.environ.setdefault(_sk, _sv)
except Exception:
    pass
import threading
import http.server
import socketserver
import functools
import time
from pathlib import Path
from src import db as _db
from modules.marketplace.utils import init_db, db_conn
from modules.marketplace.marketplace import get_project_display_image
from modules.ai_house_designer import flow as ai_house_flow

# Inicializar base de datos
init_db()
_db.ensure_tables()  # crea tablas src/db (incluyendo estudio_projects, architects, etc.)

# Configurar página con layout amplio
import streamlit as st
st.set_page_config(layout='wide')

# ── CSS responsivo móvil (solo activa en <= 768px, desktop intacto) ───────────
from modules.marketplace.mobile_css import inject as _inject_mobile_css
_inject_mobile_css()

# Ocultar sidebar visualmente (navegación se mantiene funcional vía session_state)
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Widget flotante Lola — chat bubble visible en todas las páginas ───────────
import streamlit.components.v1 as _stc
_lola_groq_key = ""
try:
    _lola_groq_key = st.secrets.get("GROQ_API_KEY", "")
except Exception:
    pass
if not _lola_groq_key:
    import os as _os_lola
    _lola_groq_key = _os_lola.getenv("GROQ_API_KEY", "")

st.markdown(f"""
<style>
#lola-panel {{
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 360px;
    height: 500px;
    background: linear-gradient(180deg, #0D1B2A 0%, #0a1520 100%);
    border-radius: 20px;
    border: 1px solid rgba(245,158,11,0.25);
    box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04);
    display: none;
    flex-direction: column;
    z-index: 99998;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
#lola-panel.open {{ display: flex; }}
#lola-header {{
    background: linear-gradient(135deg, #1E3A5F, #0D2A4A);
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid rgba(245,158,11,0.2);
    flex-shrink: 0;
}}
#lola-header .lh-avatar {{ font-size: 1.5em; }}
#lola-header .lh-info {{ flex: 1; }}
#lola-header .lh-name {{ color: #F8FAFC; font-weight: 700; font-size: 15px; line-height: 1.2; }}
#lola-header .lh-status {{ color: #94A3B8; font-size: 11px; margin-top: 2px; }}
#lola-close {{
    background: rgba(255,255,255,0.08);
    border: none;
    color: #94A3B8;
    width: 28px; height: 28px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s, color 0.2s;
    flex-shrink: 0;
}}
#lola-close:hover {{ background: rgba(255,255,255,0.18); color: white; }}
#lola-messages {{
    flex: 1;
    overflow-y: auto;
    padding: 14px 14px 8px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.1) transparent;
}}
.lola-msg {{
    max-width: 88%;
    padding: 10px 13px;
    border-radius: 14px;
    font-size: 13.5px;
    line-height: 1.55;
    animation: lola-fadein 0.2s ease;
    word-wrap: break-word;
    white-space: pre-wrap;
}}
@keyframes lola-fadein {{
    from {{ opacity:0; transform:translateY(5px); }}
    to   {{ opacity:1; transform:none; }}
}}
.lola-msg.bot {{
    background: rgba(30,58,95,0.85);
    border: 1px solid rgba(37,99,235,0.2);
    color: #E2E8F0;
    align-self: flex-start;
    border-bottom-left-radius: 4px;
}}
.lola-msg.user {{
    background: linear-gradient(135deg, #2563EB, #1D4ED8);
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 4px;
}}
.lola-msg.typing {{ color: #64748B; font-style: italic; }}
#lola-input-area {{
    padding: 10px 12px;
    border-top: 1px solid rgba(255,255,255,0.06);
    display: flex;
    gap: 8px;
    flex-shrink: 0;
    background: rgba(0,0,0,0.2);
    align-items: center;
}}
#lola-input {{
    flex: 1;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 22px;
    padding: 9px 15px;
    color: #F8FAFC;
    font-size: 13.5px;
    outline: none;
    transition: border-color 0.2s;
    font-family: inherit;
}}
#lola-input::placeholder {{ color: #64748B; }}
#lola-input:focus {{ border-color: rgba(37,99,235,0.5); }}
#lola-send {{
    background: linear-gradient(135deg, #2563EB, #1E40AF);
    border: none;
    color: white;
    width: 38px; height: 38px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 15px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: transform 0.15s, opacity 0.15s;
}}
#lola-send:hover {{ transform: scale(1.08); }}
#lola-send:disabled {{ opacity: 0.4; cursor: not-allowed; transform: none; }}
#lola-fab {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 99999;
    background: linear-gradient(135deg, #1E3A5F, #2563EB);
    color: white;
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 50px;
    padding: 13px 20px;
    font-size: 15px;
    font-weight: 700;
    box-shadow: 0 4px 24px rgba(37,99,235,0.55);
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    animation: lola-pulse 3s ease-in-out infinite;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
#lola-fab:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(37,99,235,0.7);
    animation: none;
}}
@keyframes lola-pulse {{
    0%, 100% {{ box-shadow: 0 4px 24px rgba(37,99,235,0.55); }}
    50%       {{ box-shadow: 0 4px 32px rgba(37,99,235,0.85); }}
}}
.lola-badge {{
    background: rgba(16,185,129,0.25);
    border: 1px solid #10B981;
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 11px;
    font-weight: 600;
    color: #10B981;
}}
</style>

<!-- Panel de chat Lola -->
<div id="lola-panel">
    <div id="lola-header">
        <div class="lh-avatar">🏗️</div>
        <div class="lh-info">
            <div class="lh-name">Lola</div>
            <div class="lh-status">Asistente ArchiRapid &nbsp;·&nbsp; <span style="color:#10B981;">● En línea</span></div>
        </div>
        <button id="lola-close" onclick="toggleLola()" title="Cerrar">✕</button>
    </div>
    <div id="lola-messages"></div>
    <div id="lola-input-area">
        <input id="lola-input" type="text" placeholder="Escríbeme lo que necesites..."/>
        <button id="lola-send" onclick="sendLolaMsg()" title="Enviar">➤</button>
    </div>
</div>

<!-- FAB toggle -->
<button id="lola-fab" onclick="window.toggleLola && window.toggleLola()">
    💬 <span>Lola</span>
    <span class="lola-badge">● online</span>
</button>
""", unsafe_allow_html=True)

# JS en iframe separado — st.components.v1.html SÍ ejecuta scripts
_stc.html(f"""<script>
(function() {{
    var GROQ_KEY = "{_lola_groq_key}";
    var SYS = "Eres Lola, la asistente virtual de ArchiRapid, plataforma proptech espanola que conecta propietarios de terrenos, compradores y arquitectos mediante IA.\\n\\nLO QUE HACE ARCHIRAPID:\\n- Explorar fincas y terrenos reales en Espana con validacion catastral por IA\\n- Reservar o comprar terrenos directamente en la plataforma\\n- Disenar una vivienda personalizada en 3D con asistente de IA incluido\\n- Obtener presupuesto orientativo y documentacion arquitectonica descargable\\n- Conectar con arquitectos y proveedores de servicios de construccion\\n\\nDATOS CLAVE:\\n- Acceso gratuito para los primeros 50 usuarios registrados (beta privada)\\n- Fincas disponibles: Madrid, Andalucia, Extremadura, Castilla y Leon\\n- Precio orientativo: 900-2000 euros/m2 segun calidad y zona\\n- Contacto: hola@archirapid.com\\n\\nGUIA DEL DISENADOR DE VIVIENDA (paso a paso):\\nEl disenador tiene 6 pasos que el usuario recorre en orden:\\n1. PARCELA: el usuario indica la superficie del terreno disponible (m2), la forma (rectangular, irregular) y la orientacion (norte, sur, este, oeste).\\n2. PROGRAMA: elige el numero de habitaciones (1-6), banos (1-4), si quiere salon-comedor abierto o separado, cocina independiente o integrada, y si necesita garaje o trastero.\\n3. ESTILO: selecciona el estilo arquitectonico (moderno, mediterraneo, rustico, minimalista, industrial) y los materiales de fachada (hormigon, ladrillo, madera, mixto, revestimiento).\\n4. CUBIERTA (tejado): elige el tipo de cubierta: plana transitable, inclinada a un agua, inclinada a dos aguas, o cubierta verde. Tambien indica si quiere instalar paneles solares.\\n5. INSTALACIONES: marca las instalaciones deseadas: aerotermia, suelo radiante, domótica, placas solares fotovoltaicas, recuperacion de aguas grises.\\n6. RESUMEN Y GENERACION: revisa todos los parametros y pulsa el boton para que la IA genere la memoria descriptiva, el presupuesto orientativo y el modelo 3D.\\n\\nPREGUNTAS FRECUENTES DEL DISENADOR:\\n- Tejado o cubierta: esta en el paso 4 (Cubierta). Elige entre plana, inclinada a un agua, a dos aguas o verde.\\n- Cerramiento o fachada: esta en el paso 3 (Estilo), apartado materiales de fachada.\\n- Habitaciones o dormitorios: se configuran en el paso 2 (Programa).\\n- Banos: tambien en el paso 2 (Programa).\\n- Garaje: en el paso 2 (Programa), marca la casilla garaje.\\n- Paneles solares: en el paso 4 (Cubierta) y en el paso 5 (Instalaciones).\\n- Estilo moderno, rustico, etc.: paso 3 (Estilo).\\n- Presupuesto: se genera automaticamente en el paso 6 segun m2, calidad y zona.\\n- Modelo 3D: se genera en el paso 6 al pulsar el boton de generacion.\\n- Memoria descriptiva: documento PDF que se genera en el paso 6, descargable.\\n\\nTU MISION: Responder con calidez y concision. Guiar al usuario en el disenador si pregunta por alguna funcion especifica. Si preguntan por fincas, guiar a explorar el mapa. Si muestran interes en ser contactados, pedir nombre y email.\\n\\nREGLAS: Responde SIEMPRE en espanol. Maximo 3-4 frases por respuesta. NO inventes precios de fincas concretas. NO menciones tecnologias internas.";

    var P = parent;
    var chatHistory = [];
    var panelOpen = false;
    var initialized = false;

    function el(id) {{ return P.document.getElementById(id); }}

    function toggleLola() {{
        panelOpen = !panelOpen;
        var panel = el('lola-panel');
        if (!panel) return;
        if (panelOpen) {{
            panel.classList.add('open');
            if (!initialized) {{
                initialized = true;
                appendMsg('bot', '\\u00a1Hola! Soy Lola \\ud83d\\udc4b Tu asistente de ArchiRapid.\\n\\n\\u00bfTienes preguntas sobre fincas, precios, el dise\\u00f1o 3D o c\\u00f3mo funciona la plataforma? Estoy aqu\\u00ed para ayudarte. \\ud83d\\ude0a');
            }}
            setTimeout(function() {{ var i = el('lola-input'); if(i) i.focus(); }}, 150);
        }} else {{
            panel.classList.remove('open');
        }}
    }}

    function appendMsg(role, text) {{
        chatHistory.push({{ role: role === 'bot' ? 'assistant' : 'user', content: text }});
        var box = el('lola-messages');
        if (!box) return;
        var div = P.document.createElement('div');
        div.className = 'lola-msg ' + (role === 'bot' ? 'bot' : 'user');
        div.textContent = text;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    }}

    async function sendLolaMsg() {{
        var inp = el('lola-input');
        if (!inp) return;
        var text = (inp.value || '').trim();
        if (!text) return;
        inp.value = '';
        appendMsg('user', text);

        var sendBtn = el('lola-send');
        if (sendBtn) sendBtn.disabled = true;
        inp.disabled = true;

        var box = el('lola-messages');
        var typing = P.document.createElement('div');
        typing.className = 'lola-msg bot typing';
        typing.textContent = '\\u2726 escribiendo...';
        if (box) {{ box.appendChild(typing); box.scrollTop = box.scrollHeight; }}

        try {{
            var messages = [{{ role: 'system', content: SYS }}].concat(chatHistory.slice(-12));
            var resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {{
                method: 'POST',
                headers: {{ 'Authorization': 'Bearer ' + GROQ_KEY, 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ model: 'llama-3.3-70b-versatile', messages: messages, max_tokens: 280, temperature: 0.72 }})
            }});
            var data = await resp.json();
            typing.remove();
            var reply = (data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content)
                ? data.choices[0].message.content.trim()
                : 'Lo siento, hubo un problema t\\u00e9cnico. Escr\\u00edbenos a hola@archirapid.com';
            appendMsg('bot', reply);
        }} catch(e) {{
            typing.remove();
            appendMsg('bot', 'En este momento no puedo responderte. Escr\\u00edbenos a hola@archirapid.com \\ud83d\\ude4f');
        }}

        if (sendBtn) sendBtn.disabled = false;
        inp.disabled = false;
        inp.focus();
    }}

    P.window.toggleLola  = toggleLola;
    P.window.sendLolaMsg = sendLolaMsg;

    // Bind Enter key on input
    var inp = el('lola-input');
    if (inp) {{
        inp.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendLolaMsg(); }}
        }});
    }}
    // Bind send button
    var sb = el('lola-send');
    if (sb) sb.addEventListener('click', sendLolaMsg);
    // Bind close button
    var cb = el('lola-close');
    if (cb) cb.addEventListener('click', toggleLola);
    // Bind FAB
    var fab = el('lola-fab');
    if (fab) fab.addEventListener('click', toggleLola);
}})();
</script>""", height=0)

# HARDCODE DE ROL PARA PRUEBA
if st.session_state.get('email') == 'asdfg@lkj.com': st.session_state['role'] = 'owner'

# 🛡️ BLINDAJE ABSOLUTO OWNER
if st.session_state.get("role") == "owner":
    from modules.marketplace import owners
    owners.main()
    st.stop()

# === FUNCIONES AUXILIARES V2 ===

def detalles_proyecto_v2(project_id: str):
    """Muestra la página de vista previa de un proyecto arquitectónico - VERSIÓN V2"""
    # Verificar si el usuario está logueado como cliente
    client_logged_in = st.session_state.get("client_logged_in", False)
    client_email = st.session_state.get("client_email", "")

    if client_logged_in and client_email:
        # Usuario registrado: mostrar panel completo con pestaña COMPRA
        from modules.marketplace import client_panel
        client_panel.show_selected_project_panel(client_email, project_id)
    else:
        # Usuario no registrado: mostrar vista previa limitada
        from modules.marketplace.project_detail import show_project_detail_page
        show_project_detail_page(project_id)

def panel_cliente_v2():
    from modules.marketplace import owners
    return owners.main()


def route_main_panel():
    selected_page = st.session_state.get("selected_page")
    # Bloque de Seguridad: Si el rol es owner, la página DEBE ser Propietarios
    if st.session_state.get('role') == 'owner':
        st.session_state['selected_page'] = "🏠 Propietarios"
    user_role = st.session_state.get("user_role", "buyer")
    
    if selected_page == "🏠 Propietarios":
        from modules.marketplace import owners
        owners.main()
    elif selected_page == "👤 Panel de Cliente":
        if user_role == "buyer":
            from modules.marketplace import client_panel
            client_panel.main()
        elif user_role == "owner":
            from modules.marketplace import owners
            owners.main()
        elif user_role == "architect":
            from modules.marketplace import architects
            architects.main()
        else:
            st.error("Error: Rol de usuario no reconocido para el panel de cliente")


def show_selected_project_panel_v2(client_email: str, project_id: str):
    """Panel para mostrar proyecto seleccionado con detalles completos y opciones de compra - V2"""
    st.subheader("🏗️ Proyecto Arquitectónico Seleccionado V2")

    # Obtener datos completos del proyecto
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, m2_construidos, area_m2, price, estimated_cost,
               price_memoria, price_cad, property_type, foto_principal, galeria_fotos,
               memoria_pdf, planos_pdf, planos_dwg, modelo_3d_glb, vr_tour, energy_rating,
               architect_name, characteristics_json, habitaciones, banos, garaje, plantas,
               m2_parcela_minima, m2_parcela_maxima, certificacion_energetica, tipo_proyecto
        FROM projects
        WHERE id = ?
    """, (project_id,))
    row = cursor.fetchone()

    if not row:
        st.error("❌ Proyecto no encontrado")
        conn.close()
        return

    # Extraer datos del proyecto
    project_data = {
        'id': row[0],
        'title': row[1],
        'description': row[2],
        'm2_construidos': row[3],
        'area_m2': row[4],
        'price': row[5],
        'estimated_cost': row[6],
        'price_memoria': row[7] or 1800,
        'price_cad': row[8] or 2500,
        'property_type': row[9],
        'foto_principal': row[10],
        'galeria_fotos': row[11],
        'memoria_pdf': row[12],
        'planos_pdf': row[13],
        'planos_dwg': row[14],
        'modelo_3d_glb': row[15],
        'vr_tour': row[16],
        'energy_rating': row[17],
        'architect_name': row[18],
        'characteristics': json.loads(row[19]) if row[19] else {},
        'habitaciones': row[20],
        'banos': row[21],
        'garaje': row[22],
        'plantas': row[23],
        'm2_parcela_minima': row[24],
        'm2_parcela_maxima': row[25],
        'certificacion_energetica': row[26],
        'tipo_proyecto': row[27]
    }

    # Calcular superficie mínima requerida
    m2_proyecto = project_data['m2_construidos'] or project_data['area_m2'] or 0
    if project_data['m2_parcela_minima']:
        superficie_minima = project_data['m2_parcela_minima']
    else:
        superficie_minima = m2_proyecto / 0.33 if m2_proyecto > 0 else 0

    # Título principal
    st.title(f"🏗️ {project_data['title']}")
    st.markdown(f"**👨‍💼 Arquitecto:** {project_data['architect_name'] or 'No especificado'}")

    # Galería completa de fotos
    st.header("📸 Galería Completa del Proyecto")

    # Obtener imágenes válidas usando la función existente
    project_images = get_project_display_image(project_id, 'gallery')

    if project_images:
        # Mostrar imágenes en grid responsivo
        cols = st.columns(min(len(project_images), 3))
        for idx, img_path in enumerate(project_images):
            with cols[idx % 3]:
                try:
                    st.image(img_path, width='stretch', caption=f"Imagen {idx + 1}")
                except Exception as e:
                    st.warning(f"No se pudo cargar la imagen {idx + 1}")
    else:
        st.info("No hay imágenes disponibles para este proyecto")

    # Información técnica completa
    st.header("📋 Información Técnica Completa")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏠 Características Constructivas")
        st.write(f"**Superficie construida:** {m2_proyecto:.0f} m²")
        st.write(f"**Superficie mínima de terreno:** {superficie_minima:.0f} m²")
        if project_data['m2_parcela_maxima']:
            st.write(f"**Superficie máxima de terreno:** {project_data['m2_parcela_maxima']:.0f} m²")
        st.write(f"**Tipo:** {project_data['property_type'] or project_data['tipo_proyecto'] or 'Residencial'}")

        # Características específicas
        if project_data['habitaciones']:
            st.write(f"**Habitaciones:** {project_data['habitaciones']}")
        if project_data['banos']:
            st.write(f"**Baños:** {project_data['banos']}")
        if project_data['plantas']:
            st.write(f"**Plantas:** {project_data['plantas']}")
        if project_data['garaje']:
            st.write(f"**Garaje:** {'Sí' if project_data['garaje'] else 'No'}")

        # Certificación energética
        if project_data.get('certificacion_energetica') or project_data.get('energy_rating'):
            rating = project_data.get('certificacion_energetica') or project_data.get('energy_rating', 'A')
            st.write(f"**Certificación energética:** {rating}")

    with col2:
        st.subheader("💰 Información Económica")
        if project_data['estimated_cost']:
            st.write(f"**Coste de ejecución aproximado:** €{project_data['estimated_cost']:,.0f}")
        st.write("**Precio descarga proyecto completo:**")
        st.write(f"• 📄 PDF (Memoria completa): €{project_data['price_memoria']}")
        st.write(f"• 🖥️ CAD (Planos editables): €{project_data['price_cad']}")
        total_price = project_data['price_memoria'] + project_data['price_cad']
        st.write(f"• 💰 **TOTAL:** €{total_price}")

    # Descripción completa
    if project_data['description']:
        st.header("📝 Descripción del Proyecto")
        st.write(project_data['description'])

    # Características adicionales
    if project_data['characteristics']:
        st.header("✨ Características Adicionales")
        chars = project_data['characteristics']
        if isinstance(chars, dict):
            for key, value in chars.items():
                st.write(f"• **{key}:** {value}")

    # SISTEMA DE COMPRA
    st.header("🛒 Adquirir Proyecto Completo")

    # Verificar si ya compró este proyecto
    cursor.execute("SELECT id FROM ventas_proyectos WHERE proyecto_id = ? AND cliente_email = ?", (project_id, client_email))
    ya_comprado = cursor.fetchone()
    conn.close()

    if ya_comprado:
        st.success("✅ **Ya has adquirido este proyecto**")
        st.info("Puedes descargar los archivos desde la sección 'Mis Proyectos'")

        # Mostrar botones de descarga
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 Descargar Memoria PDF", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col2:
            if st.button("🖥️ Descargar Planos CAD", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")
        with col3:
            if st.button("🏗️ Descargar Modelo 3D", use_container_width=True, type="primary"):
                st.info("Descarga iniciada... (simulado)")

    else:
        st.info("💳 Selecciona el producto que deseas adquirir:")

        col_pdf, col_cad = st.columns(2)

        with col_pdf:
            if st.button(f"📄 Comprar Memoria PDF - €{project_data['price_memoria']}", use_container_width=True, type="primary"):
                # Simular compra directa de PDF
                with st.spinner("Procesando compra de PDF..."):
                    import time
                    time.sleep(1)
                st.success("🎉 **PDF comprado con éxito!**")
                st.info("📧 Recibirás el enlace de descarga por email")

        with col_cad:
            if st.button(f"🖥️ Comprar Planos CAD - €{project_data['price_cad']}", use_container_width=True, type="primary"):
                # Simular compra directa de CAD
                with st.spinner("Procesando compra de CAD..."):
                    import time
                    time.sleep(1)
                st.success("🎉 **CAD comprado con éxito!**")
                st.info("📧 Recibirás el enlace de descarga por email")

    # FINCAS COMPATIBLES DEL USUARIO
    st.header("🏠 Fincas Compatibles")

    # Obtener fincas del usuario (compradas o propias)
    conn = db_conn()
    cursor = conn.cursor()

    # Fincas compradas
    cursor.execute("""
        SELECT p.id, p.title, p.surface_m2, p.buildable_m2
        FROM reservations r
        JOIN plots p ON r.plot_id = p.id
        WHERE r.buyer_email = ?
    """, (client_email,))

    fincas_compradas = cursor.fetchall()

    # Fincas propias (si es propietario)
    cursor.execute("""
        SELECT id, title, surface_m2, buildable_m2
        FROM plots
        WHERE owner_email = ?
    """, (client_email,))

    fincas_propias = cursor.fetchall()
    conn.close()

    fincas_usuario = fincas_compradas + fincas_propias

    if fincas_usuario:
        for finca in fincas_usuario:
            finca_id, finca_title, surface_m2, buildable_m2 = finca

            # Calcular superficie edificable
            superficie_edificable = buildable_m2 if buildable_m2 else surface_m2 * 0.33

            # Verificar compatibilidad
            compatible = False
            if m2_proyecto <= superficie_edificable:
                compatible = True

            with st.expander(f"🏠 {finca_title} - {'✅ Compatible' if compatible else '❌ No compatible'}", expanded=compatible):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Superficie total:** {surface_m2} m²")
                    st.write(f"**Superficie edificable:** {superficie_edificable:.0f} m²")
                    st.write(f"**Proyecto requiere:** {m2_proyecto:.0f} m²")

                with col2:
                    if compatible:
                        st.success("🎯 **¡Perfecto match!** Este proyecto cabe en tu finca")
                        if st.button(f"🚀 Diseñar en {finca_title}", key=f"design_v2_{finca_id}", width="stretch"):
                            st.info("🎨 Redirigiendo al diseñador... (próximamente)")
                    else:
                        deficit = m2_proyecto - superficie_edificable
                        st.warning(f"⚠️ Necesitas {deficit:.0f} m² más de superficie edificable")
    else:
        st.info("No tienes fincas registradas. Para usar este proyecto, primero compra una finca compatible.")

    # ACCIONES ADICIONALES
    st.header("🎯 ¿Qué deseas hacer ahora?")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📋 Ver Más Proyectos", width="stretch"):
            st.query_params.clear()
            st.query_params["page"] = "🏠 HOME"
            st.rerun()

    with col2:
        if st.button("🛒 Mi Historial de Compras", use_container_width=True):
            # Limpiar proyecto seleccionado para mostrar panel normal
            if "selected_project_v2" in st.query_params:
                del st.query_params["selected_project_v2"]
            st.rerun()

    with col3:
        if st.button("📧 Contactar Arquitecto", use_container_width=True):
            st.info(f"📧 Contacto: {project_data['architect_name'] or 'Equipo ARCHIRAPID'}")
            st.write("Email: proyectos@archirapid.com")
            st.write("Teléfono: +34 900 123 456")


def registro_v2():
    """Página de registro de usuario - Versión Profesional"""
    st.title("📝 Registro de Usuario - ARCHIRAPID")
    st.info("Regístrate para acceder a todos los proyectos y funcionalidades avanzadas")

    with st.form("registro_simple_v2"):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre", placeholder="Tu nombre")
            apellidos = st.text_input("Apellidos", placeholder="Tus apellidos")
            telefono = st.text_input("Teléfono", placeholder="+34 600 000 000")

        with col2:
            email = st.text_input("Email", placeholder="tu@email.com")
            confirmar_email = st.text_input("Confirmar Email", placeholder="tu@email.com")
            direccion = st.text_input("Dirección", placeholder="Calle, Ciudad, Provincia")

        submitted = st.form_submit_button("🚀 Registrarme", type="primary", width='stretch')

        if submitted:
            # Validaciones básicas
            if not nombre or not apellidos or not email:
                st.error("Por favor completa nombre, apellidos y email")
            elif email != confirmar_email:
                st.error("Los emails no coinciden")
            elif "@" not in email:
                st.error("Por favor introduce un email válido")
            else:
                # Registrar usuario en base de datos
                try:
                    from src import db
                    conn = db.get_conn()
                    cursor = conn.cursor()

                    # Verificar si el email ya existe
                    cursor.execute("SELECT id FROM clients WHERE email = ?", (email,))
                    existing = cursor.fetchone()

                    if existing:
                        st.info("Ya estabas registrado. Accediendo...")
                    else:
                        # Insertar nuevo cliente (combinar nombre y apellidos)
                        full_name = f"{nombre} {apellidos}".strip()
                        cursor.execute("""
                            INSERT INTO clients (name, email, phone, address, created_at)
                            VALUES (?, ?, ?, ?, datetime('now'))
                        """, (full_name, email, telefono, direccion))

                        st.info("Registro completado. Accediendo...")

                    conn.commit()
                    conn.close()

                    # Auto-login
                    st.session_state["client_logged_in"] = True
                    st.session_state["client_email"] = email
                    st.session_state["user_role"] = "buyer"
                    st.session_state["has_transactions"] = False
                    st.session_state["has_properties"] = False

                    # Si venía viendo un proyecto específico, guardarlo para mostrar los botones de compra
                    if "proyecto_seleccionado" in st.session_state and st.session_state["proyecto_seleccionado"]:
                        project_id = st.session_state["proyecto_seleccionado"].get("id")
                        if project_id:
                            st.session_state["selected_project_for_panel"] = project_id

                    # Redirigir de vuelta al Marketplace con sesión activa
                    st.query_params["page"] = "🏠 Inicio / Marketplace"
                    st.rerun()

                except Exception as e:
                    st.error(f"Error en el registro: {e}")

    st.markdown("---")
    st.info("💡 **¿Ya tienes cuenta?** Si has realizado compras anteriores, accede directamente desde el panel de cliente.")


# === FUNCIONES AUXILIARES V2 ===

def show_buyer_panel_v2(client_email):
    """Panel principal para compradores - V2"""
    st.header("🛒 Panel de Comprador V2")

    # Tabs para diferentes secciones
    tab1, tab2, tab3 = st.tabs(["🔍 Buscar Proyectos", "📋 Mis Intereses", "📊 Mis Transacciones"])

    with tab1:
        # Búsqueda avanzada de proyectos
        show_advanced_project_search_v2(client_email)

    with tab2:
        # Mostrar proyectos guardados/interesantes
        show_client_interests_v2(client_email)

    with tab3:
        # Mostrar transacciones realizadas
        show_client_transactions_v2(client_email)


def show_owner_panel_v2(client_email):
    """Panel para propietarios con fincas - V2"""
    st.subheader("🏠 Mis Propiedades Publicadas V2")

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
    st.subheader("🎯 Gestión de Propiedades V2")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 VER PROPUESTAS")
        st.write("Revisa las propuestas de arquitectos para tus fincas")
        if st.button("📨 Ver Todas las Propuestas", key="view_proposals_owner_v2", use_container_width=True, type="primary"):
            st.success("📨 Mostrando todas las propuestas... (V2)")
            st.info("Aquí podrás gestionar todas las propuestas recibidas para tus propiedades")

    with col2:
        st.markdown("#### ➕ PUBLICAR MÁS FINCAS")
        st.write("Añade más propiedades a tu portafolio")
        if st.button("🏠 Subir Nueva Finca", key="upload_new_property_v2", use_container_width=True, type="primary"):
            st.success("🏠 Redirigiendo a subida de fincas... (V2)")
            st.info("Accede desde el menú lateral 'Propietarios (Subir Fincas)'")

    show_common_actions_v2(context="owner")


def show_client_interests_v2(client_email):
    """Mostrar proyectos de interés del cliente - V2"""
    st.subheader("⭐ Mis Proyectos de Interés V2")

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

                if st.button("Ver Detalles", key=f"view_interest_v2_{project_id}"):
                    st.query_params["selected_project_v2"] = project_id
                    st.rerun()


def show_client_transactions_v2(client_email):
    """Mostrar transacciones del cliente (fincas compradas) - V2"""
    st.subheader("📋 Mis Transacciones V2")

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

        show_common_actions_v2(context=f"buyer_{trans_id}")  # Acciones comunes para compradores


def show_common_actions_v2(context="common"):
    """Acciones comunes para compradores y propietarios - V2"""
    st.markdown("---")

    # Opciones de acción
    st.subheader("🎯 ¿Qué deseas hacer? V2")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏡 DISEÑAR VIVIENDA")
        st.write("Crea tu casa ideal con nuestros arquitectos")
        if st.button("🚀 Ir al Diseñador", key=f"go_designer_panel_2_{context}", use_container_width=True, type="primary"):
            st.success("🎨 Redirigiendo al Diseñador de Vivienda... (V2)")
            st.info("En esta sección podrás diseñar tu vivienda personalizada")

    with col2:
        st.markdown("#### 📐 VER PROYECTOS")
        st.write("Explora proyectos compatibles con tu finca")
        if st.button("📋 Ver Proyectos", key=f"go_projects_panel_{context}", use_container_width=True, type="primary"):
            st.success("📐 Mostrando proyectos disponibles... (V2)")
            st.info("Aquí verás todos los proyectos arquitectónicos compatibles")

    st.markdown("---")

    # Opciones adicionales
    st.subheader("🔧 Opciones Adicionales V2")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("🗺️ Volver al Marketplace", key=f"back_to_marketplace_{context}", use_container_width=True):
            st.success("🏠 Volviendo al marketplace... (V2)")
            st.info("Puedes seguir explorar más fincas y proyectos")

    with col_b:
        if st.button("📧 Contactar Soporte", key=f"contact_support_{context}", use_container_width=True):
            st.info("📧 Contacto con soporte:")
            st.write("**Email:** soporte@archirapid.com")
            st.write("**Teléfono:** +34 900 123 456")

    with col_c:
        if st.button("📄 Descargar Documentación", key=f"download_docs_{context}", use_container_width=True):
            st.info("📄 Descarga disponible próximamente")
            st.write("Pronto podrás descargar todos los documentos de tu transacción")


def show_advanced_project_search_v2(client_email):
    """Búsqueda avanzada de proyectos por criterios - V2"""
    st.subheader("🔍 Buscar Proyectos Arquitectónicos V2")
    st.write("Encuentra proyectos compatibles con tus necesidades específicas")

    # Formulario de búsqueda
    with st.form("advanced_search_form_v2"):
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
        submitted = st.form_submit_button("🔍 Buscar Proyectos", type="primary", width='stretch')

    # Mostrar proyectos disponibles (todos al inicio, filtrados si se buscó)
    search_params = {'client_email': client_email}  # Parámetros por defecto

    # Si se hizo una búsqueda, usar esos parámetros
    if 'last_search_params_v2' in st.session_state:
        search_params = st.session_state['last_search_params_v2']

    # Buscar proyectos
    with st.spinner("Cargando proyectos..."):
        proyectos = get_proyectos_compatibles(**search_params)

    # Mostrar contador
    st.markdown(f"### 🏗️ Proyectos Disponibles: {len(proyectos)}")

    if not proyectos:
        st.info("No hay proyectos disponibles en este momento.")
        return

    # Formulario de búsqueda (siempre visible)
    with st.expander("🔍 Filtrar Proyectos", expanded=False):
        with st.form("advanced_search_form_v2"):
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
            submitted = st.form_submit_button("🔍 Aplicar Filtros", type="primary", width='stretch')

        if submitted:
            # Preparar parámetros de búsqueda
            search_params = {
                'client_budget': presupuesto_max if presupuesto_max > 0 else None,
                'client_desired_area': area_deseada if area_deseada > 0 else None,
                'client_parcel_size': parcela_disponible if parcela_disponible > 0 and solo_compatibles else None,
                'client_email': client_email
            }
            st.session_state['last_search_params_v2'] = search_params

            # Mostrar criterios aplicados
            st.markdown("### 📋 Filtros aplicados:")
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
                st.info("Mostrando todos los proyectos")

            # Re-buscar con filtros
            with st.spinner("Aplicando filtros..."):
                proyectos = get_proyectos_compatibles(**search_params)
            st.markdown(f"### 🏗️ Resultados filtrados: {len(proyectos)} proyectos")

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
                if 'last_search_params_v2' in st.session_state and st.session_state['last_search_params_v2'].get('client_parcel_size'):
                    parcel_size = st.session_state['last_search_params_v2']['client_parcel_size']
                    if proyecto.get('m2_parcela_minima'):
                        if proyecto['m2_parcela_minima'] <= parcel_size:
                            st.success("✅ Compatible con tu parcela")
                        else:
                            st.warning(f"⚠️ Necesita parcela ≥ {proyecto['m2_parcela_minima']} m²")

                # Botón de detalles
                if st.button("Ver Detalles", key=f"search_detail_v2_{proyecto['id']}", use_container_width=True):
                    st.query_params["selected_project_v2"] = proyecto['id']
                    st.rerun()

                # Botones de compra directa (si está logueado)
                if st.session_state.get("client_logged_in", False):
                    # Verificar si ya compró este proyecto
                    conn_check = db_conn()
                    cursor_check = conn_check.cursor()
                    cursor_check.execute("SELECT id FROM ventas_proyectos WHERE proyecto_id = ? AND cliente_email = ?", (proyecto['id'], client_email))
                    ya_compro = cursor_check.fetchone()
                    conn_check.close()

                    if ya_compro:
                        st.success("✅ Ya adquirido")
                    else:
                        # Botones de compra
                        col_buy_pdf, col_buy_cad = st.columns(2)
                        with col_buy_pdf:
                            if st.button(f"📄 PDF €{proyecto.get('price_memoria', 1800)}", key=f"buy_pdf_{proyecto['id']}", use_container_width=True):
                                # Simular compra de PDF
                                with st.spinner("Procesando compra..."):
                                    import time
                                    time.sleep(1)
                                # Registrar compra
                                conn_buy = db_conn()
                                cursor_buy = conn_buy.cursor()
                                cursor_buy.execute("""
                                    INSERT INTO ventas_proyectos
                                    (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (proyecto['id'], client_email, "Compra directa", "PDF", proyecto.get('price_memoria', 1800), "Simulado"))
                                conn_buy.commit()
                                conn_buy.close()
                                st.success("🎉 PDF comprado!")
                                st.rerun()

                        with col_buy_cad:
                            if st.button(f"🖥️ CAD €{proyecto.get('price_cad', 2500)}", key=f"buy_cad_{proyecto['id']}", use_container_width=True):
                                # Simular compra de CAD
                                with st.spinner("Procesando compra..."):
                                    import time
                                    time.sleep(1)
                                # Registrar compra
                                conn_buy = db_conn()
                                cursor_buy = conn_buy.cursor()
                                cursor_buy.execute("""
                                    INSERT INTO ventas_proyectos
                                    (proyecto_id, cliente_email, nombre_cliente, productos_comprados, total_pagado, metodo_pago, fecha_compra)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (proyecto['id'], client_email, "Compra directa", "CAD", proyecto.get('price_cad', 2500), "Simulado"))
                                conn_buy.commit()
                                conn_buy.close()
                                st.success("🎉 CAD comprado!")
                                st.rerun()

                st.markdown("---")


# === SCROLL TO TOP ON NAVIGATION ===
_nav_route = str(dict(st.query_params)) + "|" + st.session_state.get('selected_page', '')
if st.session_state.get('_nav_route') != _nav_route:
    st.session_state['_nav_route'] = _nav_route
    st.components.v1.html(
        "<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>",
        height=0
    )

# ═══════════════════════════════════════════════════════════════════════
# DEEP LINKS — tracking de origen y modo demo
# Soporta: ?seccion=arquitecto  ?from=linkedin  ?user=javier  ?demo=true
# ═══════════════════════════════════════════════════════════════════════
def _registrar_visita_demo(origen, nombre, accion):
    """Guarda una visita en visitas_demo. Silencioso si falla."""
    try:
        import uuid as _uuid
        from datetime import datetime as _dt
        from modules.marketplace.utils import db_conn as _dbc
        _conn = _dbc(); _c = _conn.cursor()
        _c.execute("""INSERT OR IGNORE INTO visitas_demo
                      (id,timestamp,origen,nombre_usuario,accion_realizada,session_id)
                      VALUES (?,?,?,?,?,?)""",
                   (_uuid.uuid4().hex, _dt.utcnow().isoformat(),
                    origen, nombre, accion,
                    st.session_state.get("_demo_session_id", "")))
        _conn.commit(); _conn.close()
    except Exception:
        pass

_qp_seccion = st.query_params.get("seccion", "")
_qp_from    = st.query_params.get("from", "")
_qp_ref     = st.query_params.get("ref", "")   # alias de ?from — para links de campaña
_qp_user    = st.query_params.get("user", "")
_qp_demo    = st.query_params.get("demo", "")
_qp_modo    = st.query_params.get("modo", "")

# ── Handlers retorno Stripe MLS y deep links MLS ─────────────────────────────
_qp_mls_pago    = st.query_params.get("mls_pago", "")
_qp_mls_reserva = st.query_params.get("mls_reserva_ok", "")
_qp_mls_ficha   = st.query_params.get("mls_ficha", "")
_qp_mls_reservar = st.query_params.get("mls_reservar", "")
_qp_mls_contacto = st.query_params.get("mls_contacto", "")

if _qp_mls_pago == "ok":
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_verificar_pago"] = True

if _qp_mls_reserva == "1":
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_reserva_ok_params"] = {
        "finca_id": st.query_params.get("finca_id", ""),
        "inmo_id":  st.query_params.get("inmo_id", ""),
        "tipo":     st.query_params.get("tipo", ""),
        "nombre":   st.query_params.get("nombre", ""),
        "email":    st.query_params.get("email", ""),
    }

if _qp_mls_ficha:
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_ficha_id"] = _qp_mls_ficha

if _qp_mls_reservar:
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_reservar_id"] = _qp_mls_reservar

if _qp_mls_contacto:
    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
    st.session_state["mls_contacto_id"] = _qp_mls_contacto
# ─────────────────────────────────────────────────────────────────────────────

# ref y from son equivalentes; ref tiene prioridad si ambos presentes
_qp_origen = _qp_ref or _qp_from

# Generar session_id único para esta visita (solo una vez por sesión)
if "_demo_session_id" not in st.session_state:
    import uuid as _uuid_mod
    st.session_state["_demo_session_id"] = _uuid_mod.uuid4().hex

# Registrar origen una sola vez por sesión (demo=true o seccion=arquitecto)
_es_visita_demo = _qp_demo == "true" or _qp_seccion == "arquitecto"
if _es_visita_demo and not st.session_state.get("_origen_registrado"):
    _origen_final = _qp_origen or "directo"
    _registrar_visita_demo(_origen_final, _qp_user or "anonimo", f"visita:{_qp_seccion or 'home'}")
    st.session_state["_origen_registrado"] = True
    st.session_state["_visit_from"] = _origen_final

# Mensaje de bienvenida personalizado
if _qp_user and not st.session_state.get("_welcome_shown"):
    _nombre_display = _qp_user.capitalize()
    st.toast(f"Bienvenido, {_nombre_display}. Prueba ArchiRapid en directo.", icon="👋")
    st.session_state["_welcome_shown"] = True

# Activar sandbox si ?demo=true
if _qp_demo == "true" and not st.session_state.get("sandbox_mode"):
    st.session_state["sandbox_mode"] = True
    st.session_state["sandbox_user"] = _qp_user.capitalize() if _qp_user else "Visitante"

# Navegar directo al portal del arquitecto si ?seccion=arquitecto
if _qp_seccion == "arquitecto" and not st.session_state.get("_deep_link_routed"):
    st.session_state["selected_page"] = "Arquitectos (Marketplace)"
    st.session_state["_deep_link_routed"] = True
    # Si sandbox + modo estudio, marcar para abrir esa pestaña al entrar
    if _qp_modo == "estudio" or _qp_demo == "true":
        st.session_state["_open_estudio_tab"] = True

# === RUTA PÚBLICA: ?page=stats (sin login) ===
if st.query_params.get("page") == "stats":
    try:
        from modules.marketplace.stats_public import render as _render_stats
        _render_stats()
    except Exception as _se:
        st.error(f"Error cargando estadísticas: {_se}")
    st.stop()

# === RUTA PÚBLICA: ?page=privacidad ===
if st.query_params.get("page") == "privacidad":
    try:
        from modules.marketplace.privacidad import render as _render_priv
        _render_priv()
    except Exception as _pe:
        st.error(f"Error cargando política de privacidad: {_pe}")
    st.stop()

# === RUTA PÚBLICA: ?reset_token=XXX (recuperar contraseña) ===
if st.query_params.get("reset_token"):
    try:
        from modules.marketplace.password_reset import show_reset_password
        show_reset_password(st.query_params["reset_token"])
    except Exception as _re:
        st.error(f"Error en recuperación de contraseña: {_re}")
    st.stop()

# === RUTA PÚBLICA: ?page=recuperar_contrasena ===
if st.query_params.get("page") == "recuperar_contrasena":
    try:
        from modules.marketplace.password_reset import show_forgot_password
        show_forgot_password()
    except Exception as _fe:
        st.error(f"Error en recuperación de contraseña: {_fe}")
    st.stop()

# === STRIPE: verificar pago al volver de Checkout ===
if st.query_params.get("stripe_session") and st.query_params.get("payment") == "success":
    _ss_id = st.query_params["stripe_session"]
    if not st.session_state.get(f"stripe_verified_{_ss_id}"):
        try:
            from modules.stripe_utils import verify_session as _stripe_verify
            import sqlite3 as _sq3
            _sess = _stripe_verify(_ss_id)
            if _sess.payment_status == "paid":
                _meta = _sess.metadata or {}
                _proj_id  = _meta.get("project_id", "")
                _cli_mail = _meta.get("client_email", "") or (_sess.customer_email or "")
                _prods    = _meta.get("products", "")
                _amount   = (_sess.amount_total or 0) / 100
                _con3 = _sq3.connect("database.db", timeout=15)
                _con3.execute("PRAGMA journal_mode=WAL")
                _exists3 = _con3.execute(
                    "SELECT id FROM ventas_proyectos WHERE stripe_session_id = ?", (_ss_id,)
                ).fetchone()
                if not _exists3:
                    _con3.execute("""
                        INSERT INTO ventas_proyectos
                        (proyecto_id, cliente_email, nombre_cliente, productos_comprados,
                         total_pagado, metodo_pago, fecha_compra, stripe_session_id)
                        VALUES (?, ?, ?, ?, ?, 'Stripe', datetime('now'), ?)
                    """, (_proj_id, _cli_mail, _cli_mail, _prods, _amount, _ss_id))
                    _con3.commit()
                _con3.close()
                st.session_state[f"stripe_verified_{_ss_id}"] = True
                st.toast("🎉 Pago completado. Ya puedes descargar tus archivos.", icon="✅")
        except Exception as _se:
            st.toast(f"Error verificando pago Stripe: {_se}", icon="⚠️")
    # Limpiar params de Stripe sin perder el proyecto
    try:
        del st.query_params["stripe_session"]
        del st.query_params["payment"]
    except Exception:
        pass

# === NUEVAS RUTAS V2 (BORRÓN Y CUENTA NUEVA) ===
page_from_query = False  # Variable para controlar si la página viene de query params
if "selected_prefab" in st.query_params and not page_from_query:
    try:
        from modules.marketplace import prefab_detail
        prefab_detail.show(int(st.query_params["selected_prefab"]))
    except Exception as e:
        st.error(f"Error mostrando detalle de prefabricada: {e}")
    st.stop()

if "selected_project_v2" in st.query_params and not page_from_query:
    try:
        project_id = st.query_params["selected_project_v2"]
        detalles_proyecto_v2(project_id)
    except Exception as e:
        st.error(f"Error mostrando detalles del proyecto v2: {e}")
    st.stop()  # Detener la ejecución para no mostrar el resto de la app

if "selected_plot" in st.query_params and not page_from_query:
    try:
        plot_id = st.query_params["selected_plot"]
        from modules.marketplace.plot_detail import show_plot_detail_page
        show_plot_detail_page(plot_id)
    except Exception as e:
        st.error(f"Error mostrando finca: {e}")
    st.stop()

if st.query_params.get("page") == "👤 Panel de Cliente" and st.session_state.get('selected_page') != "🏠 Propietarios":
    try:
        panel_cliente_v2()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando panel cliente v2: {e}")

if st.query_params.get("page") == "Registro de Usuario":
    try:
        registro_v2()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando registro v2: {e}")


if st.query_params.get("page") == "Diseñador de Vivienda":
    try:
        with st.container():
            ai_house_flow.main()
            st.stop()
    except Exception as e:
        st.error(f"Error mostrando diseñador de vivienda: {e}")

if st.query_params.get("page") == "Arquitectos (Marketplace)":
    try:
        from modules.marketplace import architects as _arch_mod
        _arch_mod.main()
        st.stop()
    except Exception as e:
        st.error(f"Error mostrando portal arquitectos: {e}")


# Page configuration and navigation - SIMPLIFIED VERSION
PAGES = {
    "🏠 Inicio / Marketplace": ("modules.marketplace.marketplace", "main"),
    "🏠 Propietarios": ("modules.marketplace.owners", "main"),
    "🏢 Inmobiliarias MLS": ("modules.mls.mls_portal", "main"),
    "🔍 Detalle de Finca": ("modules.marketplace.plot_detail", "show_plot_detail_page"),
    "Intranet": ("modules.marketplace.intranet", "main"),
    "👤 Panel de Proveedor": ("modules.marketplace.service_providers", "show_service_provider_panel"),
    "📝 Registro de Proveedor de Servicios": ("modules.marketplace.service_providers", "show_service_provider_registration"),
    "Arquitectos (Marketplace)": ("modules.marketplace.marketplace_upload", "main"),
    "👤 Panel de Cliente": ("modules.marketplace.client_panel", "main"),
    "Iniciar Sesión": ("modules.marketplace.auth", "show_login"),
    "Registro de Usuario": ("modules.marketplace.auth", "show_registration"),
    "💬 Lola": ("modules.marketplace.virtual_assistant", "main"),
}
PAGES = list(PAGES.keys())

# Helper: start a simple static server for local assets (with CORS)
def _start_static_server(root_dir: Path, port: int = 8765):
    # If already started, return existing port
    if st.session_state.get("static_server_started"):
        return st.session_state.get("static_server_port")
    try:
        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                super().end_headers()
            def do_OPTIONS(self):
                self.send_response(200, "OK")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.end_headers()

        Handler = functools.partial(CORSRequestHandler, directory=str(root_dir))
        httpd = socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler)
    except Exception:
        return None
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    st.session_state["static_server_started"] = True
    st.session_state["static_server_port"] = port
    st.session_state["static_server_obj"] = httpd
    return port


def render_portal_cliente_proyecto():
    from modules.marketplace.utils import db_conn
    st.header("📂 Portal de Cliente — Proyecto Seleccionado")

    proyecto = st.session_state.get("proyecto_seleccionado")
    interes_id = st.session_state.get("interes_proyecto_id")
    interes_titulo = st.session_state.get("interes_proyecto_titulo")
    email = st.session_state.get("email", "")
    rol = st.session_state.get("role", "cliente")  # futuro: cliente / propietario / arquitecto / admin

    if not proyecto and not interes_id:
        st.warning("No hay ningún proyecto seleccionado para mostrar en el portal de cliente.")
        return

    st.markdown("### 🏡 Información del Proyecto")

    if proyecto:
        st.write(f"**Título:** {proyecto.get('title', 'N/D')}")
        st.write(f"**💰 Precio:** {proyecto.get('price', 'N/D')} €")
        st.write(f"**📐 Superficie:** {proyecto.get('m2_construidos', 'N/D')} m²")
        st.write(f"**🛏️ Habitaciones:** {proyecto.get('habitaciones', 'N/D')}")
        st.write(f"**🛁 Baños:** {proyecto.get('banos', 'N/D')}")
        st.write(f"**🏠 Plantas:** {proyecto.get('plantas', 'N/D')}")
    else:
        st.warning("No hay proyecto seleccionado.")

    st.markdown("---")

    # VISUALIZACIONES (pestañas: 3D / VR / Fotos)
    st.markdown("### 🏗️ Visualizaciones del Proyecto")

    tab_3d, tab_vr, tab_fotos = st.tabs(["🎥 3D", "🥽 VR", "🖼️ Fotos / Planos"])

    # --- Pestaña 3D ---
    with tab_3d:
        st.markdown("#### 🎥 Visor 3D del Proyecto")

        if proyecto:
            # Usamos GLB siempre que exista
            glb_path = proyecto.get("modelo_3d_glb")

            if glb_path:
                rel_path = str(glb_path).replace("\\", "/").lstrip("/")
                # Obtener STATIC_URL si está definido, si no usar fallback
                STATIC_URL = globals().get('STATIC_URL', 'http://127.0.0.1:8765/')
                model_url = f"{STATIC_URL}{rel_path}".replace(" ", "%20")

                try:
                    html_final = three_html_for(model_url, str(proyecto.get("id")))
                    st.components.v1.html(html_final, height=700, scrolling=False)
                except Exception as e:
                    st.error(f"Error cargando visor 3D: {e}")
            else:
                st.info("Este proyecto no tiene modelo GLB. Próximamente convertiremos OBJ a GLB automáticamente.")
        else:
            st.warning("No hay proyecto seleccionado en el portal.")

    # --- Pestaña VR ---
    with tab_vr:
        st.markdown("#### 🥽 Visor de Realidad Virtual")

        model_glb = None
        if proyecto and proyecto.get("modelo_3d_glb"):
            model_glb = proyecto.get("modelo_3d_glb")

        if model_glb:
            rel = str(model_glb).replace("\\", "/").lstrip("/")
            glb_url = f"http://localhost:8000/{rel}".replace(" ", "%20") + "?v=123"
            viewer_url = f"http://localhost:8000/static/vr_viewer.html?model={glb_url}"

            st.markdown(
                f'<iframe src="{viewer_url}" width="100%" height="600" allow="accelerometer; gyroscope; xr-spatial-tracking; vr" frameborder="0"></iframe>',
                unsafe_allow_html=True,
            )
            st.caption("Visor VR integrado. Si no funciona, verifica permisos del navegador.")
        else:
            st.info("Este proyecto todavía no tiene modelo VR asociado. Usaremos el modelo 3D como base en futuras versiones.")

    # --- Pestaña Fotos / Planos ---
    with tab_fotos:
        st.markdown("#### 🖼️ Galería de Fotos y Planos")

        # Foto principal
        foto = proyecto.get("foto_principal")
        if foto:
            rel = foto.replace("\\", "/").lstrip("/")
            url = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel}"
            st.image(url, width=400)

        # Imagen adicional dentro de characteristics_json
        try:
            import json
            chars = json.loads(proyecto.get("characteristics_json", "{}"))
            img2 = chars.get("imagenes")
            # Evitar duplicados
            if img2 and img2 == foto:
                img2 = None
            if img2:
                rel2 = img2.replace("\\", "/").lstrip("/")
                url2 = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel2}"
                st.image(url2, width=400)
        except:
            pass

        # Galería completa
        galeria_fotos = proyecto.get('files', {}).get('fotos', [])
        if galeria_fotos:
            st.subheader("Galería Completa")
            for foto in galeria_fotos:
                if foto and isinstance(foto, str) and not foto.isdigit() and foto.strip():
                    rel = foto.replace("\\", "/").lstrip("/")
                    url = f"{globals().get('STATIC_URL','http://127.0.0.1:8765/')}{rel}"
                    st.image(url, width=300)

    st.markdown("---")
    st.markdown("### 🛒 Acciones del Cliente")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛒 COMPRAR ESTE PROYECTO (simulado)", key="btn_comprar_proyecto_portal"):
            st.success("Simulando compra. Nuestro equipo comercial se pondrá en contacto contigo.")
    with col2:
        if st.button("📞 QUIERO QUE ME LLAMEN", key="btn_llamar_proyecto_portal"):
            st.success("Hemos registrado tu interés para que te llame el equipo comercial.")

    st.caption(f"Portal vinculado al email: {email or 'No registrado'}")

    st.markdown("---")
    st.markdown("### 🔧 Módulos Profesionales (Futuro)")
    st.info("Estos módulos estarán disponibles en futuras versiones para monetización:")
    st.write("- 🎨 Decoradores (packs de interiorismo)")
    st.write("- 🏗️ Constructores (presupuestos automáticos)")
    st.write("- 🧱 Prefabricadas (catálogo integrado)")
    st.write("- 🛡️ Aseguradoras (pólizas vinculadas)")
    st.write("- 🧰 Materiales de construcción (marketplace)")
    st.write("- 🧑‍💼 Arquitectos (gestión avanzada)")
    st.write("- 🧑‍💼 Propietarios (seguimiento de obra)")



# Lógica de navegación robusta

# El sidebar DEBE leer de session_state obligatoriamente
selected_page = st.sidebar.radio(
    "Navegación",
    options=PAGES,
    index=PAGES.index(st.session_state.get('selected_page', "🏠 Inicio / Marketplace")) if st.session_state.get('selected_page', "🏠 Inicio / Marketplace") in PAGES else 0
)

# Sincronizamos por si el usuario cambia el radio manualmente
st.session_state['selected_page'] = selected_page

# Lógica de Redirección
if st.session_state.get('selected_page') == "🏠 Inicio / Marketplace":
    if "selected_plot" not in st.query_params and "selected_project_v2" not in st.query_params and "selected_prefab" not in st.query_params:
        st.query_params.clear()
elif st.session_state.get('selected_page') in ["👤 Panel de Proveedor", "📝 Registro de Proveedor de Servicios"]:
    st.query_params["page"] = st.session_state.get('selected_page')

# Inicializar vista_actual si no existe (no altera comportamiento por defecto)
if "vista_actual" not in st.session_state:
    st.session_state["vista_actual"] = None

# Obtener rol del usuario actual para mostrar botones condicionalmente
current_user_role = None
client_logged_in = st.session_state.get("client_logged_in", False)
client_email = st.session_state.get("client_email", "")

if client_logged_in and client_email:
    try:
        from modules.marketplace.utils import get_user_by_email
        user_data = get_user_by_email(client_email)
        if user_data:
            current_user_role = user_data.get('role')
    except:
        current_user_role = None

# REMOVED: Conditional sidebar buttons for service providers - navigation is now simplified



# Only handle special pages here; other pages delegate to modules
if st.session_state.get('selected_page') == "🔍 Detalle de Finca":
    if 'selected_plot' in st.session_state:
        from modules.marketplace.plot_detail import show_plot_detail_page
        show_plot_detail_page(st.session_state['selected_plot'])
        st.stop()
    else:
        st.error("No se ha seleccionado ninguna finca para mostrar detalles.")
        st.session_state['selected_page'] = "🏠 Inicio / Marketplace"
        st.rerun()

if st.session_state.get('selected_page') == "🏠 Inicio / Marketplace":
    # Redirigir propietarios a su panel
    if st.session_state.get('role') == 'owner':
        st.session_state['selected_page'] = "🏠 Propietarios"
        st.rerun()
    
    STATIC_ROOT = Path(r"C:/ARCHIRAPID_PROYECT25")
    STATIC_PORT = _start_static_server(STATIC_ROOT, port=8000)
    # URL base del servidor estático (definida temprano para usar en el header de diagnóstico)
    if STATIC_PORT:
        STATIC_URL = f"http://localhost:{STATIC_PORT}/"
    else:
        STATIC_URL = "http://localhost:8000/"

    # Header
    with st.container():
        try:
            from components.header import render_header
            cols = render_header()
            access_col = cols[2]
        except Exception:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                try:
                    st.image("assets/branding/logo.png", width=140)
                except Exception:
                    st.markdown("# 🏗️ ARCHIRAPID")
            with cols[1]:
                st.markdown("### IA Avanzada + Precios en Vivo + Exportación Profesional")
            access_col = cols[2]

        with access_col:
            if st.button("🔑 Acceder", key="btn_acceder"):
                if st.session_state.get('role') == 'admin':
                    st.session_state['selected_page'] = 'Intranet'
                    st.rerun()
                else:
                    st.session_state['show_role_selector'] = True
                    st.rerun()

# ========== HOME: LANDING + MARKETPLACE + PROYECTOS ==========

    # Mostrar formulario de login si viewing_login es True
    if st.session_state.get('viewing_login', False):
        st.markdown("---")
        login_role_label = st.session_state.get('login_role', '').title()
        st.header(f"🔐 Iniciar Sesión - {login_role_label}")
        
        modo_registro = st.checkbox("¿Es tu primera vez? Activa el modo registro", key="modo_registro")
        
        with st.form("login_form"):
            if modo_registro:
                st.subheader("📝 Registro de Nuevo Usuario")
                name = st.text_input("Nombre completo *", placeholder="Tu nombre completo")
                email = st.text_input("Email *", placeholder="tu@email.com")
                password = st.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
                password_confirm = st.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("🚀 Registrarme y Acceder", type="primary")
                with col2:
                    if st.form_submit_button("⬅️ Volver al login"):
                        st.session_state['modo_registro'] = False
                        st.rerun()
                
                if submitted:
                    if not name or not email or not password:
                        st.error("Por favor, completa los campos obligatorios marcados con *.")
                    elif password != password_confirm:
                        st.error("Las contraseñas no coinciden.")
                    elif len(password) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                    else:
                        try:
                            from werkzeug.security import generate_password_hash
                            hashed_password = generate_password_hash(password)
                            
                            conn = db_conn()
                            c = conn.cursor()
                            
                            # determinar rol en función de login_role
                            new_role = 'client'
                            if st.session_state.get('login_role') == 'owner':
                                new_role = 'owner'
                            c.execute("""
                                INSERT INTO users (email, full_name, role, is_professional, password_hash, created_at)
                                VALUES (?, ?, ?, ?, ?, datetime('now'))
                            """, (
                                email, name, new_role,
                                0,  # is_professional
                                hashed_password
                            ))
                            
                            user_id = c.lastrowid
                            conn.commit()
                            conn.close()
                            
                            st.success("🎉 ¡Registro completado exitosamente!")
                            
                            # Login automático
                            st.session_state['user_id'] = user_id
                            st.session_state['user_email'] = email
                            st.session_state['role'] = new_role
                            st.session_state['user_name'] = name
                            st.session_state['logged_in'] = True
                            st.session_state['viewing_login'] = False
                            st.session_state['show_role_selector'] = False
                            
                            # Redirigir según el rol (owner va al portal de propietarios)
                            if st.session_state['role'] == 'client':
                                st.session_state['selected_page'] = "👤 Panel de Cliente"
                            elif st.session_state['role'] == 'architect':
                                st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                            elif st.session_state['role'] == 'services':
                                st.session_state['selected_page'] = "👤 Panel de Proveedor"
                            elif st.session_state['role'] == 'admin':
                                st.session_state['selected_page'] = "Intranet"
                            elif st.session_state['role'] == 'owner':
                                st.session_state['selected_page'] = "🏠 Propietarios"
                            
                            st.success(f"¡Bienvenido {name}!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error en el registro: {e}")
            else:
                email = st.text_input("📧 Email", key="login_email")
                password = st.text_input("🔒 Contraseña", type="password", key="login_password")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("🚀 Entrar", type="primary")
                with col2:
                    if st.form_submit_button("⬅️ Volver al selector"):
                        st.session_state['viewing_login'] = False
                        st.session_state['show_role_selector'] = True
                        st.rerun()
                
                if submitted:
                    if not email or not password:
                        st.error("Por favor, completa todos los campos.")
                    else:
                        # Usar la función de autenticación existente
                        from modules.marketplace.auth import authenticate_user
                        user_data = authenticate_user(email, password)
                        
                        if user_data and user_data.get('role') == st.session_state.get('login_role'):
                            # Login exitoso
                            st.session_state['user_id'] = user_data['id']
                            st.session_state['user_email'] = user_data['email']
                            st.session_state['role'] = user_data['role']
                            st.session_state['user_name'] = user_data.get('full_name') or user_data.get('name') or user_data.get('email', 'Usuario')
                            st.session_state['logged_in'] = True
                            st.session_state['viewing_login'] = False
                            st.session_state['show_role_selector'] = False
                            
                            # Redirigir según el rol
                            if st.session_state['role'] == 'client':
                                st.session_state['selected_page'] = "👤 Panel de Cliente"
                            elif st.session_state['role'] == 'architect':
                                st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                            elif st.session_state['role'] == 'services':
                                st.session_state['selected_page'] = "👤 Panel de Proveedor"
                            elif st.session_state['role'] == 'owner':
                                st.session_state['selected_page'] = "🏠 Propietarios"
                            elif st.session_state['role'] == 'admin':
                                st.session_state['selected_page'] = "Intranet"
                            
                            st.success(f"¡Bienvenido {st.session_state['user_name']}!")
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas o rol no coincide.")
        
        st.stop()  # Detener el resto de la Home

    if st.session_state.get('show_role_selector', False):
        # Pantalla de Selector de Rol
        st.markdown("---")
        st.header("🔐 Selecciona tu Perfil de Acceso")
        st.markdown("Elige el tipo de usuario que eres para acceder a las funcionalidades correspondientes.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("### 🏠 Cliente")
            st.markdown("Accede a tus proyectos y compras.")
            if st.button("🔑 Acceso Cliente", key="select_client", use_container_width=True):
                st.session_state['login_role'] = 'client'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col2:
            st.markdown("### 🏗️ Arquitecto")
            st.markdown("Gestiona tus diseños y fincas.")
            if st.button("🔑 Acceso Arquitecto", key="select_architect", use_container_width=True):
                st.session_state['login_role'] = 'architect'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col3:
            st.markdown("### 🏡 Propietario")
            st.markdown("Administra tus propiedades.")
            if st.button("🔑 Acceso Propietario", key="select_owner", use_container_width=True):
                st.session_state['login_role'] = 'owner'
                st.session_state['viewing_login'] = True
                st.rerun()

        with col4:
            st.markdown("### 🛠️ Servicios")
            st.markdown("Gestiona tus servicios profesionales.")
            if st.button("🔑 Acceso Servicios", key="select_services", use_container_width=True):
                st.session_state['login_role'] = 'services'
                st.session_state['viewing_login'] = True
                st.rerun()

        # Botón discreto para admin
        st.markdown("---")
        col_admin = st.columns([10, 1])[1]
        with col_admin:
            if st.button("🔐 Admin", key="admin_access"):
                st.session_state['login_role'] = 'admin'
                st.session_state['viewing_login'] = True
                st.rerun()

        # Botón para volver
        st.markdown("---")
        if st.button("⬅️ Volver", key="back_to_home"):
            st.session_state['show_role_selector'] = False
            st.rerun()
        st.stop()  # Detenemos el resto de la Home

    else:
        # ── MURO DE INVITACIÓN ──────────────────────────────────────────────────
        try:
            import sqlite3 as _sq3
            _wconn = _sq3.connect("database.db")
            _wc = _wconn.cursor()
            _wc.execute("SELECT COUNT(*) FROM waitlist")
            _taken = _wc.fetchone()[0]
            _wconn.close()
        except Exception:
            _taken = 0
        _MAX = 50
        _left = max(_MAX - _taken, 0)
        _pct = min(int(_taken / _MAX * 100), 100)

        # ── HERO COMPACTO: banner 75% + waitlist 25% ────────────────────────
        _hbanner, _hwaitlist = st.columns([3, 1], gap="small")

        with _hbanner:
            st.markdown(f"""
<div style="background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:12px;
            padding:12px 20px;border:1px solid rgba(245,158,11,0.3);
            display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;height:100%;">
  <div>
    <span style="font-size:10px;font-weight:700;color:#F59E0B;letter-spacing:2px;
                 text-transform:uppercase;">Beta Privada · Acceso Anticipado</span>
    <div style="font-size:1em;font-weight:800;color:#F8FAFC;line-height:1.2;">
      Acceso gratuito para los primeros {_MAX} usuarios
      <span style="font-size:0.75em;font-weight:400;color:#94A3B8;margin-left:10px;">
        ⚖️ Información orientativa basada en datos catastrales públicos. No sustituye el asesoramiento técnico, jurídico o urbanístico de un profesional colegiado.
      </span>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="background:rgba(255,255,255,0.06);border-radius:8px;padding:6px 12px;white-space:nowrap;">
      <span style="color:#F59E0B;font-weight:700;">{_taken}</span>
      <span style="color:#94A3B8;font-size:0.85em;"> / {_MAX}</span>
      &nbsp;
      <span style="color:#10B981;font-weight:600;font-size:0.85em;">{_left} disponibles</span>
    </div>
    <div style="background:rgba(255,255,255,0.08);border-radius:6px;height:8px;width:80px;overflow:hidden;">
      <div style="background:linear-gradient(90deg,#F59E0B,#EF4444);
                  width:{_pct}%;height:100%;border-radius:6px;"></div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        _wl_key = "waitlist_submitted"
        with _hwaitlist:
            if not st.session_state.get(_wl_key):
                with st.expander("✋ Solicitar plaza gratuita", expanded=False):
                    with st.form("waitlist_form", clear_on_submit=True):
                        _wname  = st.text_input("Nombre", placeholder="Tu nombre")
                        _wemail = st.text_input("Email",  placeholder="tu@email.com")
                        _wprofile = st.selectbox("Soy...",
                            ["Comprador / Particular", "Propietario de terreno",
                             "Arquitecto / Profesional", "Inversor / Empresa"])
                        _wmsg = st.text_input("¿Qué buscas?", placeholder="Construir, invertir...")
                        _wsub = st.form_submit_button(
                            "Solicitar plaza" if _left > 0 else "Lista de espera",
                            type="primary", use_container_width=True)
                        if _wsub:
                            if not _wname or not _wemail or "@" not in _wemail:
                                st.error("Nombre y email requeridos.")
                            else:
                                try:
                                    import sqlite3 as _sq3b
                                    _wconn2 = _sq3b.connect("database.db")
                                    _wconn2.cursor().execute(
                                        "INSERT INTO waitlist (name, email, profile) VALUES (?,?,?)",
                                        (_wname.strip(), _wemail.strip().lower(), _wprofile))
                                    _wconn2.commit(); _wconn2.close()
                                    st.session_state[_wl_key] = True
                                    st.session_state["waitlist_name"] = _wname.strip()
                                    try:
                                        from modules.marketplace.email_notify import notify_waitlist
                                        notify_waitlist(_wname.strip(), _wemail.strip().lower(), _wprofile)
                                    except Exception:
                                        pass
                                    st.rerun()
                                except Exception as _we:
                                    if "UNIQUE" in str(_we):
                                        st.info("Ya estás en la lista.")
                                    else:
                                        st.error(f"Error: {_we}")
            else:
                _wname_saved = st.session_state.get("waitlist_name", "")
                st.success(f"✅ Plaza reservada{', ' + _wname_saved if _wname_saved else ''}.")

        # ── 4 tarjetas de acceso en columnas iguales ─────────────────────────
        _hc1, _hc2, _hc3, _hc4 = st.columns(4, gap="small")

        with _hc1:
            st.markdown("""
<div style="background:white;border-radius:10px;padding:14px 16px;
            border-top:3px solid #F5A623;box-shadow:0 2px 8px rgba(0,0,0,0.07);
            margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:22px;">🏗️</span>
    <div>
      <div style="font-weight:800;color:#0D1B2A;font-size:0.95em;">Tengo un Terreno</div>
      <div style="color:#64748B;font-size:0.78em;">Publica tu finca y recibe propuestas de arquitectos.</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Subir Mi Finca →", key="hp_btn_prop", use_container_width=True):
                if st.session_state.get("logged_in") and st.session_state.get("role") == "owner":
                    st.query_params["page"] = "🏠 Propietarios"
                    st.rerun()
                else:
                    st.session_state['login_role'] = 'owner'
                    st.session_state['viewing_login'] = True
                    st.rerun()

        with _hc2:
            st.markdown("""
<div style="background:white;border-radius:10px;padding:14px 16px;
            border-top:3px solid #2563EB;box-shadow:0 2px 8px rgba(0,0,0,0.07);
            margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:22px;">📐</span>
    <div>
      <div style="font-weight:800;color:#0D1B2A;font-size:0.95em;">Soy Arquitecto</div>
      <div style="color:#64748B;font-size:0.78em;">Comparte proyectos ejecutables y conecta con clientes reales.</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Acceso Arquitectos →", key="hp_btn_arq", use_container_width=True):
                st.session_state['selected_page'] = "Arquitectos (Marketplace)"
                st.query_params["page"] = "Arquitectos (Marketplace)"
                st.rerun()

        with _hc3:
            st.markdown("""
<div style="background:white;border-radius:10px;padding:14px 16px;
            border-top:3px solid #F59E0B;box-shadow:0 2px 8px rgba(0,0,0,0.07);
            margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:22px;">🛠️</span>
    <div>
      <div style="font-weight:800;color:#0D1B2A;font-size:0.95em;">¿Eres profesional?</div>
      <div style="color:#64748B;font-size:0.78em;">Constructor, reformista o proveedor. Únete a la red.</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Registrarme como Profesional →", key="hp_btn_pro", use_container_width=True):
                st.session_state['selected_page'] = "📝 Registro de Proveedor de Servicios"
                st.rerun()

        with _hc4:
            st.markdown("""
<div style="background:white;border-radius:10px;padding:14px 16px;
            border-top:3px solid #1B2A6B;box-shadow:0 2px 8px rgba(0,0,0,0.07);
            margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:22px;">🏢</span>
    <div>
      <div style="font-weight:800;color:#0D1B2A;font-size:0.95em;">¿Eres Inmobiliaria?</div>
      <div style="color:#64748B;font-size:0.78em;">Bolsa MLS colaborativa. Comparte fincas, multiplica ventas.</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Acceder a ArchiRapid MLS →", key="hp_btn_mls", use_container_width=True):
                st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
                st.rerun()

        # PASO 1: Renderizar MARKETPLACE (mapa, fincas y proyectos)
        try:
            from modules.marketplace import marketplace
            marketplace.main()
        except Exception as e:
            import traceback
            st.error(f"Error cargando marketplace: {e}")
            st.code(traceback.format_exc())


        # PASO 3: Renderizar PROYECTOS ARQUITECTÓNICOS
        st.markdown("---")
        st.markdown("#### 🏗️ Proyectos Arquitectónicos Disponibles")

        try:
            from src import db
            from modules.marketplace.marketplace import get_project_display_image
            projects = db.get_featured_projects(limit=10)

            if projects:
                import base64, io
                N = 5
                cols = st.columns(N)
                for idx, p in enumerate(projects[:N*2]):
                    with cols[idx % N]:
                        # Imagen con altura fija via HTML para uniformidad
                        thumbnail = get_project_display_image(p['id'], image_type='main')
                        try:
                            if isinstance(thumbnail, bytes):
                                b64 = base64.b64encode(thumbnail).decode()
                            else:
                                buf = io.BytesIO()
                                thumbnail.save(buf, format='JPEG')
                                b64 = base64.b64encode(buf.getvalue()).decode()
                            st.markdown(
                                f'<img src="data:image/jpeg;base64,{b64}" '
                                f'style="width:100%;height:160px;object-fit:cover;'
                                f'border-radius:10px;display:block;">',
                                unsafe_allow_html=True
                            )
                        except Exception:
                            st.image(thumbnail, use_container_width=True)
                        title = p.get('title', 'Proyecto')
                        st.markdown(f"**{title[:28]}{'…' if len(title)>28 else ''}**")
                        st.caption(f"💰 €{p.get('price',0):,.0f}  ·  📐 {p.get('area_m2',0)} m²")
                        if st.button("Ver Detalles →", key=f"proj_home_{p['id']}", use_container_width=True):
                            st.query_params["selected_project_v2"] = p['id']
                            st.rerun()
            else:
                st.info("No hay proyectos arquitectónicos disponibles aún.")
        except Exception as e:
            st.error(f"Error cargando proyectos: {e}")

    # Sección casas prefabricadas
    st.markdown("---")
    st.markdown("#### 🏠 Adquiere tu Finca y Ponle una Casa Prefabricada")
    st.caption("Modelos entregables desde 45 m² · Madera · Acero modular · Hormigón prefab · Mixto")
    try:
        from src import db as _db
        _conn = _db.get_conn()
        _cur = _conn.cursor()
        _cur.execute("SELECT id, name, m2, rooms, bathrooms, floors, material, price, image_path, image_paths, price_label FROM prefab_catalog WHERE active=1 ORDER BY m2 LIMIT 10")
        prefabs = _cur.fetchall()
        _conn.close()
        if prefabs:
            import base64 as _b64, json as _pfjson
            _N = 5
            _cols = st.columns(_N)
            for _idx, _pf in enumerate(prefabs[:_N * 2]):
                _pf_id, _nm, _m2, _rms, _bths, _fls, _mat, _prc, _img, _imgs_j, _plbl = _pf
                # Primera foto válida
                _thumb = None
                try:
                    for _ip in (_pfjson.loads(_imgs_j) if _imgs_j else []):
                        if _ip:
                            _ip = _ip.replace("\\", "/")
                            if os.path.exists(_ip):
                                _thumb = _ip; break
                    if not _thumb and _img:
                        _img = _img.replace("\\", "/")
                        if os.path.exists(_img):
                            _thumb = _img
                except Exception:
                    pass
                # Precio
                _pdsp = (_plbl.strip() if _plbl and _plbl.strip() else
                         (f"€{float(_prc):,.0f}" if _prc and float(_prc) > 0 else "PRECIO A CONSULTAR"))
                with _cols[_idx % _N]:
                    if _thumb:
                        try:
                            with open(_thumb, "rb") as _tf:
                                _tb64 = _b64.b64encode(_tf.read()).decode()
                            _ext = _thumb.rsplit(".", 1)[-1].lower()
                            _mime = "image/png" if _ext == "png" else "image/jpeg"
                            st.markdown(f'<img src="data:{_mime};base64,{_tb64}" style="width:100%;height:140px;object-fit:cover;border-radius:10px;display:block;margin-bottom:6px;">', unsafe_allow_html=True)
                        except Exception:
                            st.markdown('<div style="height:140px;background:#F0F9FF;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2.5em;margin-bottom:6px;">🏠</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="height:140px;background:#F0F9FF;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2.5em;margin-bottom:6px;">🏠</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-weight:700;font-size:0.85em;color:#0D1B2A;">{_nm}</div><div style="font-size:0.76em;color:#64748B;">{_m2} m² · {_rms}hab · {_mat}</div><div style="font-weight:700;color:#2563EB;font-size:0.88em;margin-top:4px;">{_pdsp}</div>', unsafe_allow_html=True)
                    if st.button("Ver modelo →", key=f"prefab_home_{_pf_id}", use_container_width=True):
                        st.query_params["selected_prefab"] = str(_pf_id)
                        st.rerun()
    except Exception as _e:
        st.info("Catálogo de prefabricadas próximamente disponible.")

    # Footer
    st.markdown("""
    <div style="margin-top:40px;padding:20px 24px 16px;background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:12px;font-family:'Segoe UI',sans-serif;">
        <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;padding:12px 16px;margin-bottom:16px;">
            <span style="color:#FCD34D;font-size:0.84em;">💼 <strong>Investors & Partners — Join the PropTech revolution in Spain.</strong>
            ARCHIRAPID is a <strong>PropTech · Real Estate Marketplace · SaaS</strong> platform built on AI:
            we connect landowners, architects and buyers in a single end-to-end ecosystem —
            from raw land discovery to architectural project delivery.
            Scalable, data-driven and ready to grow. <strong>Let's talk.</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:14px;">
            <div>
                <span style="color:#F8FAFC;font-size:0.8em;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">🏗️ ARCHIRAPID</span><br>
                <span style="color:#64748B;font-size:0.78em;">PropTech · Real Estate Marketplace · SaaS · AI · Madrid, Spain</span>
            </div>
            <div style="text-align:right;">
                <span style="color:#94A3B8;font-size:0.78em;">
                    📍 Avda. de Europa 15, 28224 Pozuelo de Alarcón (Madrid)<br>
                    ✉️ <a href="mailto:hola@archirapid.com" style="color:#94A3B8;text-decoration:none;">hola@archirapid.com</a>
                    &nbsp;·&nbsp; 📞 <a href="tel:+35623172704" style="color:#94A3B8;text-decoration:none;">+356 23 17 27 04</a>
                </span>
            </div>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:10px;margin-bottom:8px;">
            <span style="color:#64748B;font-size:0.72em;">⚖️ <em>ArchiRapid proporciona información orientativa basada en datos catastrales públicos. Esta información no sustituye el asesoramiento técnico, jurídico o urbanístico de un profesional colegiado.</em></span>
        </div>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;">
            <span style="color:#475569;font-size:0.74em;">© 2026 ARCHIRAPID — All rights reserved. Proyecto ARCHIRAPID S.L. (en constitución)</span>
            <span style="color:#475569;font-size:0.74em;">Built with AI · Madrid, Spain 🇪🇸</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.stop()  # Detener ejecución para Home

elif st.session_state.get('selected_page') == "🏠 Propietarios":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        # Propietarios suben fincas al marketplace inmobiliario
        from modules.marketplace import owners
        owners.main()

elif st.session_state.get('selected_page') == "Propietario (Gemelo Digital)":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        # Flujo principal: Propietario sube finca → IA genera plan
        from modules.marketplace import gemelo_digital
        gemelo_digital.main()

elif st.session_state.get('selected_page') == "Diseñador de Vivienda":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        # Flujo secundario: Cliente diseña vivienda personalizada
        from modules.marketplace import disenador_vivienda
        disenador_vivienda.main()

# "Inmobiliaria (Mapa)" route removed — Home now uses `marketplace.main()` directly.

elif st.session_state.get('selected_page') == "Arquitectos (Marketplace)":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        # Portal completo del arquitecto (con Modo Estudio, IA, planes, etc.)
        from modules.marketplace import architects
        architects.main()

elif st.session_state.get('selected_page') == "Intranet":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    st.write("Cargando Panel de Control...")
    with st.container():
        from modules.marketplace import intranet
        intranet.main()

elif st.session_state.get('selected_page') == "👤 Panel de Cliente":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    # escape owners que intenten ir al panel de cliente
    if st.session_state.get('role') == 'owner':
        from modules.marketplace import owners
        owners.main()
        st.stop()
    route_main_panel()

elif st.session_state.get('selected_page') == "👤 Panel de Proveedor":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        from modules.marketplace import service_providers
        service_providers.show_service_provider_panel()

elif st.session_state.get('selected_page') == "📝 Registro de Proveedor de Servicios":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        from modules.marketplace import service_providers
        service_providers.show_service_provider_registration()

elif st.session_state.get('selected_page') == "Iniciar Sesión":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        from modules.marketplace import auth
        auth.show_login()
        st.stop()

elif st.session_state.get('selected_page') == "Registro de Usuario":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        from modules.marketplace import auth
        auth.show_registration()
        st.stop()

elif st.session_state.get('selected_page') == "💬 Lola":
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)
    with st.container():
        from modules.marketplace import virtual_assistant
        virtual_assistant.main()
        st.stop()

elif st.session_state.get('selected_page') == "🏢 Inmobiliarias MLS":
    st.components.v1.html(
        "<script>window.parent.document"
        ".querySelector('section.main')"
        ".scrollTo(0,0);</script>",
        height=0
    )
    with st.container():
        from modules.mls import mls_portal
        mls_portal.main()
