"""
LOLA WIDGET - Asistente IA flotante
iframe auto-posicionado via window.frameElement (allow-same-origin)
JS ejecuta dentro del iframe normalmente — sin DOMPurify
"""

import streamlit as st
import json
import os


@st.cache_data
def _load_lola_kb():
    """Carga lola_kb.md con fallback robusto"""
    try:
        with open("lola_kb.md", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return """ArchiRapid es una plataforma proptech espanola.
Conecta propietarios de terrenos, compradores, arquitectos e inmobiliarias.
Contacto: hola@archirapid.com"""


def render_lola():
    """Renderizar Lola con iframe auto-posicionado"""

    # 1. Obtener API key
    lola_groq_key = ""
    try:
        lola_groq_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        lola_groq_key = os.getenv("GROQ_API_KEY", "")

    # 2. Preparar system prompt desde KB
    lola_kb = _load_lola_kb()
    system_prompt = (
        "Eres Lola, asistente de ArchiRapid.\n\n"
        "CONTEXTO:\n" + lola_kb + "\n\n"
        "INSTRUCCIONES:\n"
        "- Responde SOLO sobre ArchiRapid\n"
        "- Si no sabes, redirige a hola@archirapid.com\n"
        "- Maximo 150 palabras\n"
        "- Tono profesional y cercano"
    )

    groq_key_js = json.dumps(lola_groq_key)
    system_prompt_js = json.dumps(system_prompt)

    # 3. HTML completo del iframe
    iframe_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            html, body {{
                width: 100%; height: 100%;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: transparent;
                overflow: hidden;
            }}
            #lola-fab {{
                position: absolute; bottom: 0; right: 0;
                height: 50px; border-radius: 25px;
                background: linear-gradient(135deg, #1E3A5F, #2563EB);
                border: 1px solid rgba(255,255,255,.18);
                cursor: pointer;
                box-shadow: 0 4px 24px rgba(37,99,235,0.55);
                display: flex; align-items: center; gap: 8px;
                padding: 13px 20px;
                color: white; font-size: 15px; font-weight: 700;
                transition: transform .15s ease, box-shadow .15s ease;
            }}
            #lola-fab:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 32px rgba(37,99,235,0.7);
            }}
            .lola-badge {{
                background: rgba(16,185,129,.25);
                border: 1px solid #10B981;
                border-radius: 10px; padding: 1px 7px;
                font-size: 11px; font-weight: 600; color: #10B981;
            }}
            #lola-panel {{
                display: none; position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                background: #1E293B; border-radius: 20px;
                border: 1px solid rgba(245,158,11,.25);
                flex-direction: column; overflow: hidden;
            }}
            #lola-panel.open {{ display: flex; }}
            .lola-header {{
                background: linear-gradient(135deg, #1E3A5F, #0D2A4A);
                padding: 14px 16px; display: flex;
                align-items: center; gap: 10px;
                border-bottom: 1px solid rgba(245,158,11,.2);
                flex-shrink: 0;
            }}
            .lola-avatar {{ font-size: 1.5em; }}
            .lola-info {{ flex: 1; }}
            .lola-name {{ color: #F8FAFC; font-weight: 700; font-size: 15px; }}
            .lola-status {{ color: #94A3B8; font-size: 11px; margin-top: 2px; }}
            .lola-close {{
                background: rgba(255,255,255,.08); border: none;
                color: #94A3B8; width: 28px; height: 28px;
                border-radius: 50%; cursor: pointer; font-size: 14px;
                display: flex; align-items: center; justify-content: center;
                transition: background .2s, color .2s;
            }}
            .lola-close:hover {{ background: rgba(255,255,255,.18); color: white; }}
            #lola-messages {{
                flex: 1; overflow-y: auto; padding: 14px;
                display: flex; flex-direction: column; gap: 10px;
            }}
            .lola-msg {{
                max-width: 88%; padding: 10px 13px;
                border-radius: 14px; font-size: 13.5px;
                line-height: 1.55; word-wrap: break-word; white-space: pre-wrap;
            }}
            .lola-msg.bot {{
                background: rgba(30,58,95,.85);
                border: 1px solid rgba(37,99,235,.2);
                color: #E2E8F0; align-self: flex-start;
            }}
            .lola-msg.user {{
                background: linear-gradient(135deg, #2563EB, #1D4ED8);
                color: white; align-self: flex-end;
            }}
            .lola-input-area {{
                padding: 10px 12px; background: rgba(0,0,0,.2);
                border-top: 1px solid rgba(255,255,255,.06);
                display: flex; gap: 8px; flex-shrink: 0;
            }}
            .lola-input-area input {{
                flex: 1; background: rgba(255,255,255,.08);
                border: 1px solid rgba(255,255,255,.15);
                color: #F8FAFC; border-radius: 20px;
                padding: 10px 14px; font-size: 13px; font-family: inherit;
            }}
            .lola-input-area input:focus {{
                outline: none; border-color: rgba(37,99,235,.5);
                background: rgba(255,255,255,.12);
            }}
            .lola-input-area input::placeholder {{ color: #64748B; }}
            .lola-send {{
                background: #2563EB; border: none; color: white;
                width: 36px; height: 36px; border-radius: 50%;
                cursor: pointer; display: flex;
                align-items: center; justify-content: center;
                font-size: 16px; transition: background .2s;
            }}
            .lola-send:hover {{ background: #1D4ED8; }}
        </style>
    </head>
    <body>
        <button id="lola-fab" onclick="toggleLola()">
            &#x1F4AC; <span>Lola</span>
            <span class="lola-badge">&#x1F7E2; online</span>
        </button>

        <div id="lola-panel">
            <div class="lola-header">
                <div class="lola-avatar">&#x1F3E0;</div>
                <div class="lola-info">
                    <div class="lola-name">Lola</div>
                    <div class="lola-status">Asistente ArchiRapid &middot; <span style="color:#10B981;">&#x1F7E2; En l&iacute;nea</span></div>
                </div>
                <button class="lola-close" onclick="toggleLola()">&#x2715;</button>
            </div>
            <div id="lola-messages">
                <div class="lola-msg bot">Hola! Soy Lola, tu asistente de ArchiRapid.<br><br>Preguntame sobre fincas, precios, dise&ntilde;o 3D o como funciona la plataforma.</div>
            </div>
            <div class="lola-input-area">
                <input type="text" id="lola-input" placeholder="Escr&iacute;beme tu pregunta..." autocomplete="off" />
                <button class="lola-send" onclick="sendMessage()">&#x2934;</button>
            </div>
        </div>

        <script>
            // ── PASO 1: Auto-posicionar iframe desde dentro ──
            (function() {{
                try {{
                    var me = window.frameElement;
                    if (!me) {{ console.log('[Lola] No frameElement'); return; }}
                    me.style.position = 'fixed';
                    me.style.bottom = '20px';
                    me.style.right = '20px';
                    me.style.width = '160px';
                    me.style.height = '55px';
                    me.style.zIndex = '2147483647';
                    me.style.border = 'none';
                    me.style.background = 'transparent';
                    // Desbloquear overflow en contenedores padre
                    var p = me.parentElement;
                    if (p) {{ p.style.overflow = 'visible'; p.style.height = 'auto'; }}
                    if (p && p.parentElement) {{ p.parentElement.style.overflow = 'visible'; }}
                    console.log('[Lola] iframe posicionado OK');
                }} catch(e) {{ console.warn('[Lola] Error:', e); }}
            }})();

            // ── PASO 2: Variables Groq ──
            var _groqKey = {groq_key_js};
            var _sysPrompt = {system_prompt_js};
            var chatHistory = [];

            // ── PASO 3: Toggle panel ──
            function toggleLola() {{
                var panel = document.getElementById('lola-panel');
                var fab = document.getElementById('lola-fab');
                var isOpen = !panel.classList.contains('open');
                panel.classList.toggle('open');
                fab.style.display = isOpen ? 'none' : 'flex';

                // Redimensionar iframe
                try {{
                    var me = window.frameElement;
                    if (me) {{
                        me.style.width = isOpen ? '350px' : '160px';
                        me.style.height = isOpen ? '550px' : '55px';
                    }}
                }} catch(e) {{}}

                if (isOpen) {{
                    setTimeout(function() {{
                        document.getElementById('lola-input').focus();
                    }}, 200);
                }}
            }}

            // ── PASO 4: Append message ──
            function appendMsg(role, text) {{
                chatHistory.push({{ role: role === 'bot' ? 'assistant' : 'user', content: text }});
                var div = document.createElement('div');
                div.className = 'lola-msg ' + (role === 'bot' ? 'bot' : 'user');
                div.textContent = text;
                var container = document.getElementById('lola-messages');
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }}

            // ── PASO 5: Enviar mensaje via Groq ──
            async function sendMessage() {{
                var input = document.getElementById('lola-input');
                var text = (input.value || '').trim();
                if (!text) return;

                appendMsg('user', text);
                input.value = '';
                input.disabled = true;
                var btn = document.querySelector('.lola-send');
                if (btn) btn.disabled = true;

                // Indicador de escritura
                var typing = document.createElement('div');
                typing.className = 'lola-msg bot';
                typing.textContent = 'escribiendo...';
                typing.id = 'lola-typing';
                var container = document.getElementById('lola-messages');
                container.appendChild(typing);
                container.scrollTop = container.scrollHeight;

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
                    var el = document.getElementById('lola-typing');
                    if (el) el.remove();
                    var reply = (data && data.choices && data.choices[0] && data.choices[0].message)
                        ? data.choices[0].message.content.trim()
                        : 'Lo siento, hubo un problema. Escribe a hola@archirapid.com';
                    appendMsg('bot', reply);
                }} catch(e) {{
                    var el = document.getElementById('lola-typing');
                    if (el) el.remove();
                    appendMsg('bot', 'No puedo responderte ahora. Escribe a hola@archirapid.com');
                }}

                input.disabled = false;
                if (btn) btn.disabled = false;
                input.focus();
            }}

            // ── PASO 6: Event listeners ──
            document.getElementById('lola-input').addEventListener('keydown', function(e) {{
                if (e.key === 'Enter' && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});

            console.log('[Lola] Widget inicializado OK');
        </script>
    </body>
    </html>
    """

    # 4. Renderizar — height=55 para que el iframe tenga dimensiones reales
    st.components.v1.html(iframe_html, height=55, scrolling=False)
