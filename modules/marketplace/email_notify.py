# modules/marketplace/email_notify.py
# Notificaciones por email a archirapid2026@gmail.com
# Requiere: GMAIL_APP_PASSWORD en secrets / .env
# Gmail: Cuenta → Seguridad → Verificación en 2 pasos → Contraseñas de aplicación

import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = "archirapid2026@gmail.com"
GMAIL_NOTIFY_TO = "archirapid2026@gmail.com"


def _get_gmail_password() -> str:
    try:
        import streamlit as st
        v = st.secrets.get("GMAIL_APP_PASSWORD", "")
        if v and str(v).strip():
            return str(v).strip()
    except Exception:
        pass
    return os.getenv("GMAIL_APP_PASSWORD", "").strip()


def _send(subject: str, body_html: str) -> bool:
    """Envía email al admin. Falla silenciosamente si no hay credenciales."""
    pwd = _get_gmail_password()
    if not pwd:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_NOTIFY_TO
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_USER, pwd)
            smtp.sendmail(GMAIL_USER, GMAIL_NOTIFY_TO, msg.as_string())
        return True
    except Exception:
        return False


# ─── Notificaciones públicas ────────────────────────────────────────────────

def notify_new_registration(name: str, email: str, role: str):
    """Avisa al admin cuando se registra un nuevo usuario."""
    role_label = {"client": "Cliente", "architect": "Arquitecto", "owner": "Propietario"}.get(role, role)
    subject = f"[ARCHIRAPID] Nuevo registro: {name}"
    body = f"""
    <div style="font-family:sans-serif;max-width:500px;">
      <h2 style="color:#1E3A5F;">Nuevo usuario registrado</h2>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:6px 12px;color:#555;"><b>Nombre</b></td><td style="padding:6px 12px;">{name}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:6px 12px;color:#555;"><b>Email</b></td>
            <td style="padding:6px 12px;"><a href="mailto:{email}">{email}</a></td></tr>
        <tr><td style="padding:6px 12px;color:#555;"><b>Rol</b></td><td style="padding:6px 12px;">{role_label}</td></tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px;">ARCHIRAPID MVP · notificación automática</p>
    </div>"""
    _send(subject, body)


def notify_new_reservation(plot_id: str, buyer_name: str, buyer_email: str,
                            amount: float, kind: str):
    """Avisa al admin cuando se hace una reserva o compra de finca."""
    kind_label = "Compra" if kind == "purchase" else "Reserva"
    plot_title = plot_id  # fallback
    try:
        import sqlite3
        _c = sqlite3.connect("database.db", timeout=5)
        row = _c.execute("SELECT title FROM plots WHERE id=?", (plot_id,)).fetchone()
        _c.close()
        if row:
            plot_title = row[0]
    except Exception:
        pass

    subject = f"[ARCHIRAPID] {kind_label}: {plot_title} — {buyer_name}"
    body = f"""
    <div style="font-family:sans-serif;max-width:500px;">
      <h2 style="color:#1E3A5F;">Nueva {kind_label.lower()} de finca</h2>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:6px 12px;color:#555;"><b>Finca</b></td><td style="padding:6px 12px;">{plot_title}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:6px 12px;color:#555;"><b>Comprador</b></td><td style="padding:6px 12px;">{buyer_name}</td></tr>
        <tr><td style="padding:6px 12px;color:#555;"><b>Email</b></td>
            <td style="padding:6px 12px;"><a href="mailto:{buyer_email}">{buyer_email}</a></td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:6px 12px;color:#555;"><b>Importe</b></td>
            <td style="padding:6px 12px;font-weight:bold;color:#1E3A5F;">€{amount:,.0f}</td></tr>
        <tr><td style="padding:6px 12px;color:#555;"><b>Tipo</b></td><td style="padding:6px 12px;">{kind_label}</td></tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px;">ARCHIRAPID MVP · notificación automática</p>
    </div>"""
    _send(subject, body)


def notify_waitlist(name: str, email: str, profile: str):
    """Avisa al admin cuando alguien se une a la waitlist."""
    subject = f"[ARCHIRAPID] Waitlist: {name} ({profile})"
    body = f"""
    <div style="font-family:sans-serif;max-width:500px;">
      <h2 style="color:#1E3A5F;">Nueva solicitud de acceso anticipado</h2>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:6px 12px;color:#555;"><b>Nombre</b></td><td style="padding:6px 12px;">{name}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:6px 12px;color:#555;"><b>Email</b></td>
            <td style="padding:6px 12px;"><a href="mailto:{email}">{email}</a></td></tr>
        <tr><td style="padding:6px 12px;color:#555;"><b>Perfil</b></td><td style="padding:6px 12px;">{profile}</td></tr>
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px;">ARCHIRAPID MVP · notificación automática</p>
    </div>"""
    _send(subject, body)
