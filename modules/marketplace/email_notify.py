# modules/marketplace/email_notify.py
# Notificaciones via Telegram Bot a @archirapid_mvp_bot
# Requiere en Secrets/env:
#   TELEGRAM_BOT_TOKEN = "8611167436:AAGohKZ9nKIhv_YbDNMqzcgkHZeIvr1V6j0"
#   TELEGRAM_CHAT_ID   = "5712417665"

import os
import requests as _requests


def _get_telegram_creds():
    token, chat_id = "", ""
    try:
        import streamlit as st
        token   = str(st.secrets.get("TELEGRAM_BOT_TOKEN", "")).strip()
        chat_id = str(st.secrets.get("TELEGRAM_CHAT_ID",   "")).strip()
    except Exception:
        pass
    if not token:
        token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID",   "").strip()
    return token, chat_id


def _send(text: str) -> bool:
    """Envía mensaje Telegram al admin. Falla silenciosamente si no hay credenciales."""
    token, chat_id = _get_telegram_creds()
    if not token or not chat_id:
        return False
    try:
        _requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        return True
    except Exception:
        return False


# ─── Notificaciones públicas ─────────────────────────────────────────────────

def notify_new_registration(name: str, email: str, role: str):
    role_label = {"client": "Cliente", "architect": "Arquitecto", "owner": "Propietario"}.get(role, role)
    _send(
        f"👤 <b>Nuevo registro</b>\n"
        f"Nombre: {name}\n"
        f"Email: {email}\n"
        f"Rol: {role_label}"
    )


def notify_new_reservation(plot_id: str, buyer_name: str, buyer_email: str,
                            amount: float, kind: str):
    kind_label = "Compra" if kind == "purchase" else "Reserva"
    plot_title = plot_id
    try:
        import sqlite3
        _c = sqlite3.connect("database.db", timeout=5)
        row = _c.execute("SELECT title FROM plots WHERE id=?", (plot_id,)).fetchone()
        _c.close()
        if row:
            plot_title = row[0]
    except Exception:
        pass
    _send(
        f"💰 <b>{kind_label} de finca</b>\n"
        f"Finca: {plot_title}\n"
        f"Comprador: {buyer_name}\n"
        f"Email: {buyer_email}\n"
        f"Importe: €{amount:,.0f}"
    )


def notify_waitlist(name: str, email: str, profile: str):
    _send(
        f"🎯 <b>Nuevo en Waitlist</b>\n"
        f"Nombre: {name}\n"
        f"Email: {email}\n"
        f"Perfil: {profile}"
    )


def notify_lead_mls(nombre: str, empresa: str, email: str,
                    telefono: str, num_fincas: str, mensaje: str) -> None:
    """
    Notificación triple al recibir un lead MLS desde la home:
      1. Telegram al admin (inmediato)
      2. Email Resend a hola@archirapid.com (copia para seguimiento)
    Falla silenciosamente en ambos canales.
    """
    import os

    # ── 1. Telegram ──────────────────────────────────────────────────────────
    _send(
        f"🏢 <b>Nuevo lead MLS</b>\n"
        f"Nombre: {nombre}\n"
        f"Empresa: {empresa}\n"
        f"Email: {email}\n"
        f"Tel: {telefono or '—'}\n"
        f"Fincas en cartera: {num_fincas or '—'}\n"
        f"Mensaje: {mensaje or '—'}"
    )

    # ── 2. Email Resend → hola@archirapid.com ────────────────────────────────
    try:
        try:
            import streamlit as _st
            _key = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            _key = os.getenv("RESEND_API_KEY", "").strip()
        if not _key:
            return

        _html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;margin:0;">
  <div style="max-width:520px;margin:0 auto;background:white;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="font-size:1.2rem;font-weight:900;color:#F5A623;margin-bottom:4px;">
      🟠 ArchiRapid MLS — Nuevo Lead
    </div>
    <div style="color:#64748b;font-size:13px;margin-bottom:24px;">
      Solicitud de demo recibida desde la home
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:8px 0;color:#64748b;width:140px;">Nombre</td>
          <td style="padding:8px 0;font-weight:700;color:#0f172a;">{nombre}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Empresa</td>
          <td style="padding:8px 4px;font-weight:700;color:#0f172a;">{empresa}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Email</td>
          <td style="padding:8px 0;"><a href="mailto:{email}" style="color:#1a5276;">{email}</a></td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Teléfono</td>
          <td style="padding:8px 4px;color:#0f172a;">{telefono or '—'}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Fincas cartera</td>
          <td style="padding:8px 0;color:#0f172a;">{num_fincas or '—'}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Mensaje</td>
          <td style="padding:8px 4px;color:#0f172a;">{mensaje or '—'}</td></tr>
    </table>
    <div style="margin-top:24px;padding:12px 16px;background:#fff7ed;border-radius:8px;
                border-left:4px solid #F5A623;font-size:13px;color:#92400e;">
      ⚡ Responder en menos de 24h para maximizar conversión.
    </div>
    <p style="color:#94a3b8;font-size:11px;margin-top:24px;text-align:center;">
      ArchiRapid · Panel admin: archirapid.streamlit.app → Intranet → Analytics → Leads MLS
    </p>
  </div>
</body></html>"""

        _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_key}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid Leads <noreply@archirapid.com>",
                "to": ["hola@archirapid.com"],
                "reply_to": email,
                "subject": f"🏢 Nuevo lead MLS — {empresa} ({nombre})",
                "html": _html,
            },
            timeout=10,
        )
    except Exception:
        pass
