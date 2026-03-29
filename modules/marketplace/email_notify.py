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
    import os as _os
    kind_label = "Compra" if kind == "purchase" else "Reserva"
    plot_title = plot_id
    try:
        from src.db import get_conn as _get_db_n
        _cn = _get_db_n()
        row = _cn.execute("SELECT title FROM plots WHERE id=?", (plot_id,)).fetchone()
        _cn.close()
        if row:
            plot_title = row[0] or plot_id
    except Exception:
        pass

    # ── 1. Telegram al admin ─────────────────────────────────────────────────
    _send(
        f"💰 <b>{kind_label} de finca confirmada</b>\n"
        f"Finca: {plot_title}\n"
        f"Comprador: {buyer_name}\n"
        f"Email: {buyer_email}\n"
        f"Importe: €{amount:,.0f}\n"
        f"👉 Intranet → Reservas para gestionar"
    )

    # ── 2. Email Resend → hola@archirapid.com ────────────────────────────────
    try:
        try:
            import streamlit as _st
            _rkey = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            _rkey = _os.getenv("RESEND_API_KEY", "").strip()
        if not _rkey:
            return
        _html_r = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;margin:0;">
  <div style="max-width:520px;margin:0 auto;background:white;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="font-size:1.2rem;font-weight:900;color:#1E3A5F;margin-bottom:4px;">
      🏡 ArchiRapid — Nueva {kind_label} de Finca
    </div>
    <div style="color:#64748b;font-size:13px;margin-bottom:24px;">
      Pago Stripe confirmado — acción requerida
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:8px 0;color:#64748b;width:140px;">Finca</td>
          <td style="padding:8px 0;font-weight:700;color:#0f172a;">{plot_title}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Comprador</td>
          <td style="padding:8px 4px;font-weight:700;color:#0f172a;">{buyer_name}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Email</td>
          <td style="padding:8px 0;"><a href="mailto:{buyer_email}" style="color:#1a5276;">{buyer_email}</a></td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Importe</td>
          <td style="padding:8px 4px;font-weight:700;color:#0f172a;">€{amount:,.0f}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Tipo</td>
          <td style="padding:8px 0;color:#0f172a;">{kind_label} · reserva 7 días</td></tr>
    </table>
    <div style="margin-top:24px;padding:12px 16px;background:#eff6ff;border-radius:8px;
                border-left:4px solid #1E3A5F;font-size:13px;color:#1e40af;">
      ⚡ Gestionar en Intranet → Reservas → Confirmar o contactar al comprador.
    </div>
    <p style="color:#94a3b8;font-size:11px;margin-top:24px;text-align:center;">
      ArchiRapid · <a href="https://archirapid.streamlit.app" style="color:#94a3b8;">archirapid.streamlit.app</a>
    </p>
  </div>
</body></html>"""
        _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_rkey}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid Reservas <noreply@archirapid.com>",
                "to": ["hola@archirapid.com"],
                "reply_to": buyer_email,
                "subject": f"🏡 {kind_label} confirmada — {plot_title} · €{amount:,.0f}",
                "html": _html_r,
            },
            timeout=10,
        )
    except Exception:
        pass


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


# ─── Notificaciones constructores / profesionales ────────────────────────────

def notify_constructor_new_project(email: str, name: str, project_name: str,
                                    province: str, area: float, total_cost: float) -> None:
    """Email al constructor Destacado cuando hay un proyecto nuevo en su zona."""
    import os
    _send(
        f"🏗️ <b>Nuevo proyecto en tablón — {province}</b>\n"
        f"Constructor: {name} ({email})\n"
        f"Proyecto: {project_name} · {area:.0f} m² · €{total_cost:,.0f}\n"
        f"Provincia: {province}"
    )
    try:
        try:
            import streamlit as _st
            _rkey = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            _rkey = os.getenv("RESEND_API_KEY", "").strip()
        if not _rkey:
            return
        _html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;margin:0;">
  <div style="max-width:520px;margin:0 auto;background:white;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="font-size:1.1rem;font-weight:900;color:#1E3A5F;margin-bottom:4px;">
      🏗️ Nuevo proyecto en tu zona — ArchiRapid
    </div>
    <div style="color:#64748b;font-size:13px;margin-bottom:24px;">
      Como constructor <b>⭐ Destacado</b> eres el primero en verlo
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:8px 0;color:#64748b;width:140px;">Proyecto</td>
          <td style="padding:8px 0;font-weight:700;color:#0f172a;">{project_name}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Provincia</td>
          <td style="padding:8px 4px;color:#0f172a;">{province}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Superficie</td>
          <td style="padding:8px 0;color:#0f172a;">{area:.0f} m²</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Presupuesto ref.</td>
          <td style="padding:8px 4px;font-weight:700;color:#0f172a;">€{total_cost:,.0f}</td></tr>
    </table>
    <div style="margin-top:24px;text-align:center;">
      <a href="https://archirapid.streamlit.app" style="display:inline-block;background:#1E3A5F;
         color:white;padding:12px 28px;border-radius:8px;text-decoration:none;
         font-weight:700;font-size:14px;">Ver proyecto y enviar oferta →</a>
    </div>
    <p style="color:#94a3b8;font-size:11px;margin-top:24px;text-align:center;">
      ArchiRapid · Panel constructor: archirapid.streamlit.app → Acceso → Servicios
    </p>
  </div>
</body></html>"""
        _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_rkey}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid Obras <noreply@archirapid.com>",
                "to": [email],
                "subject": f"🏗️ Nuevo proyecto en {province} — {area:.0f} m² · €{total_cost:,.0f}",
                "html": _html,
            },
            timeout=10,
        )
    except Exception:
        pass


def notify_constructor_offer_accepted(email: str, name: str, project_name: str,
                                       amount: float, comision_eur: float) -> None:
    """Email al constructor cuando el cliente acepta su oferta."""
    _send(
        f"✅ <b>¡Oferta ACEPTADA!</b>\n"
        f"Constructor: {name} ({email})\n"
        f"Proyecto: {project_name}\n"
        f"Importe: €{amount:,.0f} · Comisión pendiente: €{comision_eur:,.0f}\n"
        f"Accede a tu panel para pagar la comisión y ver el contacto del cliente."
    )
    try:
        try:
            import streamlit as _st
            _rkey = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            import os
            _rkey = os.getenv("RESEND_API_KEY", "").strip()
        if not _rkey:
            return
        _html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;margin:0;">
  <div style="max-width:520px;margin:0 auto;background:white;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="font-size:1.1rem;font-weight:900;color:#16a34a;margin-bottom:4px;">
      ✅ ¡Tu oferta fue aceptada! — ArchiRapid
    </div>
    <div style="color:#64748b;font-size:13px;margin-bottom:24px;">
      El cliente ha elegido tu propuesta para el proyecto <b>{project_name}</b>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:8px 0;color:#64748b;width:160px;">Proyecto</td>
          <td style="padding:8px 0;font-weight:700;color:#0f172a;">{project_name}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px 4px;color:#64748b;">Tu oferta</td>
          <td style="padding:8px 4px;font-weight:700;color:#16a34a;">€{amount:,.0f}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Comisión ArchiRapid (3%)</td>
          <td style="padding:8px 0;font-weight:700;color:#dc2626;">€{comision_eur:,.0f}</td></tr>
    </table>
    <div style="margin-top:16px;padding:12px 16px;background:#fef3c7;border-radius:8px;
                border-left:4px solid #f59e0b;font-size:13px;color:#92400e;">
      ⚡ Accede a tu panel → "Mis Ofertas" → paga la comisión para ver el contacto del cliente e iniciar la obra.
    </div>
    <div style="margin-top:24px;text-align:center;">
      <a href="https://archirapid.streamlit.app" style="display:inline-block;background:#16a34a;
         color:white;padding:12px 28px;border-radius:8px;text-decoration:none;
         font-weight:700;font-size:14px;">Ir a mi panel →</a>
    </div>
  </div>
</body></html>"""
        _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_rkey}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid Obras <noreply@archirapid.com>",
                "to": [email],
                "subject": f"✅ Tu oferta fue aceptada — {project_name}",
                "html": _html,
            },
            timeout=10,
        )
    except Exception:
        pass


def notify_client_offer_received(email: str, client_name: str,
                                  project_name: str, n_offers: int) -> None:
    """Email al cliente cuando recibe nuevas ofertas de constructores."""
    _send(
        f"📨 <b>Nuevas ofertas de construcción</b>\n"
        f"Cliente: {client_name} ({email})\n"
        f"Proyecto: {project_name}\n"
        f"Ofertas recibidas: {n_offers}"
    )
    try:
        try:
            import streamlit as _st
            _rkey = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            import os
            _rkey = os.getenv("RESEND_API_KEY", "").strip()
        if not _rkey:
            return
        _html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;margin:0;">
  <div style="max-width:520px;margin:0 auto;background:white;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="font-size:1.1rem;font-weight:900;color:#1E3A5F;margin-bottom:4px;">
      📨 Tienes {n_offers} oferta(s) para tu proyecto — ArchiRapid
    </div>
    <div style="color:#64748b;font-size:13px;margin-bottom:24px;">
      Constructores de tu zona han enviado propuestas para <b>{project_name}</b>
    </div>
    <div style="padding:16px;background:#eff6ff;border-radius:8px;font-size:14px;color:#1e40af;">
      Accede a tu panel de cliente → "🏗️ OFERTAS" para comparar y aceptar la que más te convenga.
    </div>
    <div style="margin-top:24px;text-align:center;">
      <a href="https://archirapid.streamlit.app" style="display:inline-block;background:#1E3A5F;
         color:white;padding:12px 28px;border-radius:8px;text-decoration:none;
         font-weight:700;font-size:14px;">Ver mis ofertas →</a>
    </div>
  </div>
</body></html>"""
        _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_rkey}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid Obras <noreply@archirapid.com>",
                "to": [email],
                "subject": f"📨 {n_offers} oferta(s) para tu proyecto — {project_name}",
                "html": _html,
            },
            timeout=10,
        )
    except Exception:
        pass
