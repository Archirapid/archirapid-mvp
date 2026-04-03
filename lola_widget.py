"""
LOLA WIDGET - Asistente IA independiente & flotante
Usa st.components.v1.html con iframe para completa independencia de Streamlit
"""

import streamlit as st
import json
import requests
import base64


@st.cache_data
def _load_lola_kb():
    """Carga lola_kb.md con fallback robusto"""
    try:
        with open("lola_kb.md", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback: texto genérico si el archivo falta
        return """# ArchiRapid

ArchiRapid es una plataforma proptech española que conecta:
- Propietarios de terrenos
- Compradores y arquitectos
- Red MLS de inmobiliarias colaborativas

Servicios principales:
1. Explorar y comprar fincas con validación catastral por IA
2. Diseñar vivienda personalizada en 3D
3. Conectar con profesionales de construcción
4. Red MLS privada entre inmobiliarias

Contacto: hola@archirapid.com
"""


def _call_groq_lola(prompt: str, messages: list, api_key: str) -> str:
    """Llamar a Groq API para Lola usando KB con fallback"""

    if not api_key:
        raise ValueError("GROQ_API_KEY no disponible")

    lola_kb = _load_lola_kb()

    system_prompt = f"""Eres Lola, asistente de ArchiRapid.

CONTEXTO:
{lola_kb}

INSTRUCCIONES:
- Responde SOLO sobre ArchiRapid
- Si no sabes, redirige a hola@archirapid.com
- Máximo 150 palabras
- Tono profesional y cercano"""

    msgs = [{"role": "system", "content": system_prompt}]
    msgs.extend(messages[-8:])

    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': msgs,
                'max_tokens': 450,
                'temperature': 0.72
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error Groq API: {str(e)}")


def render_lola():
    """Renderizar Lola con técnica de Contenedor Inyección Directa - Preciso"""

    # 1. CSS DE NIVEL SUPERIOR (Fuera del iframe, fija el componente)
    st.markdown("""
        <style>
            /* Fijar el iframe de Lola en la esquina inferior derecha */
            iframe[srcdoc*="lola-fab"] {
                position: fixed !important;
                bottom: 20px !important;
                right: 20px !important;
                width: 350px !important;
                height: 550px !important;
                z-index: 2147483647 !important;
                border: none !important;
                background: transparent !important;
            }

            /* Móvil: botón compacto pero visible y tocable */
            @media (max-width: 768px) {
                iframe[srcdoc*="lola-fab"] {
                    width: 140px !important;
                    height: 52px !important;
                    bottom: 12px !important;
                    right: 12px !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)

    # 2. INICIALIZAR SESSION STATE
    if "lola_messages" not in st.session_state:
        st.session_state.lola_messages = []

    if not st.session_state.lola_messages:
        st.session_state.lola_messages.append({
            "role": "assistant",
            "content": "¡Hola! Soy Lola 👋 Tu asistente de ArchiRapid.\n\n¿Tienes preguntas sobre fincas, precios, el diseño 3D o cómo funciona la plataforma? Estoy aquí para ayudarte. 😊"
        })

    # 3. OBTENER API KEY
    lola_groq_key = ""
    try:
        lola_groq_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        import os
        lola_groq_key = os.getenv("GROQ_API_KEY", "")

    # 4. CONSTRUIR HTML DEL CHAT (sin position:fixed interno)
    messages_html = ""
    for msg in st.session_state.lola_messages:
        msg_class = "user" if msg["role"] == "user" else "bot"
        content = msg["content"].replace('"', '&quot;').replace('\n', '<br>')
        messages_html += f'<div class="lola-msg {msg_class}">{content}</div>'

    # Preparar system prompt desde KB
    lola_kb = _load_lola_kb()
    system_prompt = f"""Eres Lola, asistente de ArchiRapid.

CONTEXTO:
{lola_kb}

INSTRUCCIONES:
- Responde SOLO sobre ArchiRapid
- Si no sabes, redirige a hola@archirapid.com
- Maximo 150 palabras
- Tono profesional y cercano"""

    # Escapar para JS (json.dumps maneja comillas y newlines)
    import json
    groq_key_js = json.dumps(lola_groq_key)
    system_prompt_js = json.dumps(system_prompt)

    # 5. HTML DEL IFRAME (LIMPIO - sin fixed en body)
    iframe_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                width: 350px;
                height: 550px;
                background: transparent;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}

            .lola-fab {{
                position: absolute;
                bottom: 0;
                right: 0;
                width: auto;
                height: 50px;
                border-radius: 25px;
                background: linear-gradient(135deg, #1E3A5F, #2563EB);
                border: 1px solid rgba(255,255,255,.18);
                cursor: pointer;
                box-shadow: 0 4px 24px rgba(37,99,235,0.55);
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 13px 20px;
                color: white;
                font-size: 15px;
                font-weight: 700;
                transition: transform .15s ease, box-shadow .15s ease;
            }}

            .lola-fab:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 32px rgba(37,99,235,0.7);
            }}

            .lola-badge {{
                background: rgba(16,185,129,.25);
                border: 1px solid #10B981;
                border-radius: 10px;
                padding: 1px 7px;
                font-size: 11px;
                font-weight: 600;
                color: #10B981;
            }}

            .lola-panel {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: #1E293B;
                border-radius: 20px;
                border: 1px solid rgba(245,158,11,.25);
                display: none;
                flex-direction: column;
                overflow: hidden;
            }}

            .lola-panel.open {{
                display: flex;
            }}

            .lola-header {{
                background: linear-gradient(135deg, #1E3A5F, #0D2A4A);
                padding: 14px 16px;
                display: flex;
                align-items: center;
                gap: 10px;
                border-bottom: 1px solid rgba(245,158,11,.2);
                flex-shrink: 0;
            }}

            .lola-avatar {{ font-size: 1.5em; }}
            .lola-info {{ flex: 1; }}
            .lola-name {{ color: #F8FAFC; font-weight: 700; font-size: 15px; }}
            .lola-status {{ color: #94A3B8; font-size: 11px; margin-top: 2px; }}

            .lola-close {{
                background: rgba(255,255,255,.08);
                border: none;
                color: #94A3B8;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 14px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background .2s, color .2s;
            }}

            .lola-close:hover {{
                background: rgba(255,255,255,.18);
                color: white;
            }}

            .lola-messages {{
                flex: 1;
                overflow-y: auto;
                padding: 14px;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }}

            .lola-msg {{
                max-width: 88%;
                padding: 10px 13px;
                border-radius: 14px;
                font-size: 13.5px;
                line-height: 1.55;
                word-wrap: break-word;
                white-space: pre-wrap;
            }}

            .lola-msg.bot {{
                background: rgba(30,58,95,.85);
                border: 1px solid rgba(37,99,235,.2);
                color: #E2E8F0;
                align-self: flex-start;
            }}

            .lola-msg.user {{
                background: linear-gradient(135deg, #2563EB, #1D4ED8);
                color: white;
                align-self: flex-end;
            }}

            .lola-input-area {{
                padding: 10px 12px;
                background: rgba(0,0,0,.2);
                border-top: 1px solid rgba(255,255,255,.06);
                display: flex;
                gap: 8px;
                flex-shrink: 0;
            }}

            .lola-input-area input {{
                flex: 1;
                background: rgba(255,255,255,.08);
                border: 1px solid rgba(255,255,255,.15);
                color: #F8FAFC;
                border-radius: 20px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: inherit;
            }}

            .lola-input-area input:focus {{
                outline: none;
                border-color: rgba(37,99,235,.5);
                background: rgba(255,255,255,.12);
            }}

            .lola-send {{
                background: #2563EB;
                border: none;
                color: white;
                width: 36px;
                height: 36px;
                border-radius: 50%;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                transition: background .2s;
            }}

            .lola-send:hover {{
                background: #1D4ED8;
            }}
        </style>
    </head>
    <body>
        <button class="lola-fab" onclick="toggleLola()">
            💬 <span>Lola</span>
            <span class="lola-badge">🟢 online</span>
        </button>

        <div class="lola-panel" id="lola-panel">
            <div class="lola-header">
                <div class="lola-avatar">🏠</div>
                <div class="lola-info">
                    <div class="lola-name">Lola</div>
                    <div class="lola-status">Asistente ArchiRapid &nbsp;·&nbsp; <span style="color:#10B981;">🟢 En línea</span></div>
                </div>
                <button class="lola-close" onclick="toggleLola()">✕</button>
            </div>
            <div class="lola-messages" id="lola-messages">
                {messages_html}
            </div>
            <div class="lola-input-area">
                <input type="text" id="lola-input" placeholder="Escríbeme tu pregunta..." />
                <button class="lola-send" onclick="sendMessage()">⤴</button>
            </div>
        </div>

        <script>
            var _groqKey = {groq_key_js};
            var _sysPrompt = {system_prompt_js};
            var chatHistory = [];

            function toggleLola() {{
                var panel = document.getElementById('lola-panel');
                panel.classList.toggle('open');
                if (panel.classList.contains('open')) {{
                    setTimeout(function() {{
                        document.getElementById('lola-input').focus();
                    }}, 100);
                }}
            }}

            function appendMsg(role, text) {{
                chatHistory.push({{ role: role === 'bot' ? 'assistant' : 'user', content: text }});
                var div = document.createElement('div');
                div.className = 'lola-msg ' + (role === 'bot' ? 'bot' : 'user');
                div.textContent = text;
                document.getElementById('lola-messages').appendChild(div);
                var c = document.getElementById('lola-messages');
                c.scrollTop = c.scrollHeight;
            }}

            async function sendMessage() {{
                var input = document.getElementById('lola-input');
                var text = input.value.trim();
                if (!text) return;

                // Mostrar mensaje del usuario
                appendMsg('user', text);
                input.value = '';
                input.disabled = true;
                document.querySelector('.lola-send').disabled = true;

                // Indicador de escritura
                var typing = document.createElement('div');
                typing.className = 'lola-msg bot';
                typing.textContent = 'escribiendo...';
                typing.id = 'lola-typing';
                document.getElementById('lola-messages').appendChild(typing);
                var c = document.getElementById('lola-messages');
                c.scrollTop = c.scrollHeight;

                // Llamar a Groq directamente
                try {{
                    var msgs = [{{ role: 'system', content: _sysPrompt }}].concat(chatHistory.slice(-8));
                    var resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {{
                        method: 'POST',
                        headers: {{
                            'Authorization': 'Bearer ' + _groqKey,
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            model: 'llama-3.3-70b-versatile',
                            messages: msgs,
                            max_tokens: 450,
                            temperature: 0.72
                        }})
                    }});
                    var data = await resp.json();
                    document.getElementById('lola-typing').remove();
                    var reply = (data && data.choices && data.choices[0] && data.choices[0].message)
                        ? data.choices[0].message.content.trim()
                        : 'Lo siento, hubo un problema. Escribe a hola@archirapid.com';
                    appendMsg('bot', reply);
                }} catch(e) {{
                    document.getElementById('lola-typing').remove();
                    appendMsg('bot', 'No puedo responderte ahora. Escribe a hola@archirapid.com');
                }}

                input.disabled = false;
                document.querySelector('.lola-send').disabled = false;
                input.focus();
            }}

            document.getElementById('lola-input').addEventListener('keydown', function(e) {{
                if (e.key === 'Enter' && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});

            // Auto-scroll inicial
            var msgContainer = document.getElementById('lola-messages');
            msgContainer.scrollTop = msgContainer.scrollHeight;
        </script>
    </body>
    </html>
    """

    # 6. ENCAPSULAR EN CONTENEDOR
    with st.container():
        st.components.v1.html(iframe_html, height=0, scrolling=False)
