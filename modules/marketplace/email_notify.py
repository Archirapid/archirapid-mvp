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
