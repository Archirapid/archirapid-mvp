# modules/marketplace/password_reset.py
"""
Recuperación de contraseña — ArchiRapid
- Paso 1: usuario pide reset → se genera token → email con enlace
- Paso 2: usuario llega con ?reset_token=XXX → formulario nueva contraseña
"""
import streamlit as st
import sqlite3
import secrets
import os
from datetime import datetime, timedelta
from modules.marketplace.utils import db_conn
from werkzeug.security import generate_password_hash


# ── DB init ────────────────────────────────────────────────────────────────────

def _init_reset_table():
    conn = db_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token      TEXT PRIMARY KEY,
            email      TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ── Envío de email ─────────────────────────────────────────────────────────────

def _send_reset_email(email: str, token: str) -> bool:
    try:
        import requests as _req
        key = ""
        try:
            key = st.secrets.get("RESEND_API_KEY", "")
        except Exception:
            key = os.getenv("RESEND_API_KEY", "")
        if not key:
            return False

        reset_url = f"https://archirapid.streamlit.app/?reset_token={token}"
        html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0F172A;font-family:Arial,sans-serif;margin:0;padding:32px;">
  <div style="max-width:520px;margin:0 auto;background:#1E293B;border-radius:16px;
              padding:32px;border:1px solid rgba(255,255,255,0.08);">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:2rem;">🏗️</div>
      <div style="font-size:1.3rem;font-weight:900;color:#F8FAFC;">ArchiRapid</div>
    </div>
    <h2 style="color:#F8FAFC;font-size:1.1rem;margin-bottom:8px;">
      Restablecer contraseña
    </h2>
    <p style="color:#94A3B8;font-size:14px;line-height:1.7;">
      Hemos recibido una solicitud para restablecer la contraseña de tu cuenta
      asociada a <b style="color:#F8FAFC;">{email}</b>.
    </p>
    <p style="color:#94A3B8;font-size:14px;line-height:1.7;">
      Pulsa el botón para crear una nueva contraseña. El enlace es válido durante
      <b style="color:#F8FAFC;">1 hora</b>.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_url}"
         style="background:#2563EB;color:#fff;text-decoration:none;padding:14px 32px;
                border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
        Restablecer contraseña
      </a>
    </div>
    <p style="color:#475569;font-size:12px;text-align:center;line-height:1.7;">
      Si no solicitaste este cambio, ignora este email. Tu contraseña actual
      seguirá siendo la misma.<br><br>
      © 2026 ArchiRapid · hola@archirapid.com
    </p>
  </div>
</body>
</html>"""

        resp = _req.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid <noreply@archirapid.com>",
                "to": [email],
                "subject": "Restablecer tu contraseña — ArchiRapid",
                "html": html,
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


# ── Paso 1: formulario solicitud ───────────────────────────────────────────────

def show_forgot_password():
    _init_reset_table()

    st.markdown("### Recuperar contraseña")
    st.markdown("Introduce tu email y te enviaremos un enlace para crear una nueva contraseña.")

    with st.form("forgot_form"):
        email = st.text_input("Email", placeholder="tu@email.com")
        submitted = st.form_submit_button("Enviar enlace de recuperación", type="primary",
                                          use_container_width=True)

    if submitted:
        if not email or "@" not in email:
            st.error("Introduce un email válido.")
            return

        # Verificar si el email existe (siempre mostramos mensaje genérico por seguridad)
        conn = db_conn()
        user = conn.execute("SELECT email FROM users WHERE email=?",
                            (email.strip().lower(),)).fetchone()
        conn.close()

        if user:
            # Generar token seguro
            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            conn = db_conn()
            # Invalidar tokens anteriores del mismo email
            conn.execute("UPDATE password_reset_tokens SET used=1 WHERE email=?", (email,))
            conn.execute(
                "INSERT INTO password_reset_tokens (token,email,expires_at,used,created_at) VALUES (?,?,?,0,?)",
                (token, email.strip().lower(), expires, datetime.utcnow().isoformat())
            )
            conn.commit()
            conn.close()
            _send_reset_email(email.strip().lower(), token)

        # Mensaje genérico siempre (no revelar si el email existe o no)
        st.success("Si ese email está registrado, recibirás un enlace en los próximos minutos. Revisa también la carpeta de spam.")

    st.markdown("---")
    st.markdown("[← Volver al login](?page=Iniciar%20Sesión)")


# ── Paso 2: formulario nueva contraseña ───────────────────────────────────────

def show_reset_password(token: str):
    _init_reset_table()

    # Validar token
    conn = db_conn()
    row = conn.execute(
        "SELECT email, expires_at, used FROM password_reset_tokens WHERE token=?",
        (token,)
    ).fetchone()
    conn.close()

    if not row:
        st.error("El enlace de recuperación no es válido.")
        st.markdown("[← Volver al login](?page=Iniciar%20Sesión)")
        return

    email, expires_at, used = row

    if used:
        st.error("Este enlace ya ha sido utilizado. Solicita uno nuevo.")
        st.markdown("[← Solicitar nuevo enlace](?page=recuperar_contrasena)")
        return

    if datetime.utcnow().isoformat() > expires_at:
        st.error("El enlace ha caducado (válido 1 hora). Solicita uno nuevo.")
        st.markdown("[← Solicitar nuevo enlace](?page=recuperar_contrasena)")
        return

    st.markdown("### Nueva contraseña")
    st.markdown(f"Creando nueva contraseña para **{email}**")

    with st.form("reset_form"):
        new_pass    = st.text_input("Nueva contraseña", type="password",
                                    placeholder="Mínimo 8 caracteres")
        confirm     = st.text_input("Confirmar contraseña", type="password")
        submitted   = st.form_submit_button("Guardar nueva contraseña", type="primary",
                                            use_container_width=True)

    if submitted:
        if len(new_pass) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            return
        if new_pass != confirm:
            st.error("Las contraseñas no coinciden.")
            return

        # Actualizar contraseña y marcar token como usado
        new_hash = generate_password_hash(new_pass)
        conn = db_conn()
        conn.execute("UPDATE users SET password_hash=? WHERE email=?", (new_hash, email))
        conn.execute("UPDATE password_reset_tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
        conn.close()

        st.success("Contraseña actualizada correctamente. Ya puedes iniciar sesión.")
        st.markdown("[→ Ir al login](?page=Iniciar%20Sesión)")
