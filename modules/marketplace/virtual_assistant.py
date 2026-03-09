"""
Marina — Asistente Virtual de ArchiRapid
IA conversacional con GROQ · Notifica al admin via Telegram
"""
import streamlit as st
import os
import requests as _req

# ── Prompt de personalidad ────────────────────────────────────────────────────
_SYSTEM = """Eres Marina, la asistente virtual de ArchiRapid, plataforma proptech española
que conecta propietarios de terrenos, compradores y arquitectos mediante IA.

LO QUE HACE ARCHIRAPID:
- Explorar fincas y terrenos reales en España con validación catastral por IA
- Reservar o comprar terrenos directamente en la plataforma (modo demo actualmente)
- Diseñar una vivienda personalizada en 3D con asistente de IA incluido
- Obtener presupuesto orientativo y documentación arquitectónica descargable
- Conectar con arquitectos y proveedores de servicios de construcción

DATOS CLAVE:
- Acceso gratuito para los primeros 50 usuarios registrados (beta privada)
- Fincas disponibles actualmente: Madrid, Andalucía, Extremadura, Castilla y León
- Precio orientativo de construcción: 900 € – 2.000 €/m² según calidad y zona
- Contacto directo: archirapid2026@gmail.com
- Plataforma en modo demostración — los datos son reales pero las operaciones no tienen validez jurídica

TU MISIÓN:
1. Responder preguntas sobre fincas, el proceso y la plataforma con calidez y concisión
2. Guiar al usuario: ver finca → verificar con IA → reservar → diseñar en 3D → documentación
3. Si muestran interés en ser contactados, pedir su nombre y email educadamente
4. Ser cálida, directa y moderna — como una asesora inmobiliaria joven y experta
5. Si no sabes algo concreto, invita a escribir a archirapid2026@gmail.com

REGLAS:
- Responde SIEMPRE en español
- Máximo 3-4 frases por respuesta — sé concisa y útil
- NO inventes precios de fincas concretas ni plazos de obra específicos
- NO menciones tecnologías internas (Babylon, Streamlit, GROQ, Gemini…)
"""


def _get_groq_key() -> str:
    for k in ("GROQ_API_KEY",):
        try:
            v = st.secrets[k]
            if v and str(v).strip():
                return str(v).strip()
        except Exception:
            pass
        v = os.getenv(k, "").strip()
        if v:
            return v
    return ""


def _groq_reply(history: list) -> str:
    key = _get_groq_key()
    if not key:
        return "Lo siento, tengo un problema técnico ahora mismo. Escríbenos a archirapid2026@gmail.com y te respondo enseguida. 📧"
    try:
        messages = [{"role": "system", "content": _SYSTEM}] + history[-12:]
        r = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages,
                  "max_tokens": 280, "temperature": 0.72},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return "En este momento no puedo responderte. Por favor escríbenos a archirapid2026@gmail.com 🙏"


def _notify(user_msg: str):
    try:
        from modules.marketplace.email_notify import _send
        _send(f"💬 <b>Marina — mensaje recibido</b>\n{user_msg[:400]}")
    except Exception:
        pass


def main():
    # ── Cabecera ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0D1B2A,#1E3A5F);border-radius:14px;
                padding:20px 28px;margin-bottom:20px;border:1px solid rgba(245,158,11,0.25);">
        <div style="display:flex;align-items:center;gap:14px;">
            <div style="font-size:2.4em;">🏗️</div>
            <div>
                <div style="font-size:1.3em;font-weight:800;color:#F8FAFC;">Marina</div>
                <div style="font-size:0.88em;color:#94A3B8;">
                    Asistente virtual de ArchiRapid · Online ahora
                </div>
            </div>
            <div style="margin-left:auto;">
                <span style="background:rgba(16,185,129,0.15);border:1px solid #10B981;
                             border-radius:20px;padding:4px 12px;color:#10B981;font-size:0.78em;
                             font-weight:600;">● En línea</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Inicializar historial ──────────────────────────────────────────────────
    if "marina_history" not in st.session_state:
        st.session_state.marina_history = [
            {
                "role": "assistant",
                "content": (
                    "¡Hola! Soy Marina 👋 Tu asistente de ArchiRapid.\n\n"
                    "Puedo ayudarte con:\n"
                    "- 🏡 Información sobre fincas y terrenos disponibles\n"
                    "- 🔍 Cómo funciona la verificación catastral con IA\n"
                    "- 🏠 El proceso de diseño de tu vivienda en 3D\n"
                    "- 💶 Precios orientativos y cómo empezar\n\n"
                    "¿Qué te gustaría saber?"
                )
            }
        ]

    # ── Mostrar historial ──────────────────────────────────────────────────────
    for msg in st.session_state.marina_history:
        with st.chat_message(
            "assistant" if msg["role"] == "assistant" else "user",
            avatar="🏗️" if msg["role"] == "assistant" else "👤"
        ):
            st.markdown(msg["content"])

    # ── Input ──────────────────────────────────────────────────────────────────
    if prompt := st.chat_input("Escríbeme lo que necesites..."):
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        st.session_state.marina_history.append({"role": "user", "content": prompt})

        _notify(prompt)

        with st.chat_message("assistant", avatar="🏗️"):
            with st.spinner(""):
                reply = _groq_reply(st.session_state.marina_history)
            st.markdown(reply)
        st.session_state.marina_history.append({"role": "assistant", "content": reply})

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.caption("📧 Contacto directo: archirapid2026@gmail.com  ·  Marina responde en segundos")
    with c2:
        if st.button("← Volver al inicio", use_container_width=True):
            st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
            st.rerun()
    with c3:
        if st.button("🗑️ Nueva conversación", use_container_width=True):
            del st.session_state["marina_history"]
            st.rerun()
