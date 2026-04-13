"""
modules/mls/mls_trial_emails.py
Emails del ciclo de trial de 30 días para inmobiliarias MLS.

Usa el mismo sistema de envío que mls_notificaciones.py:
  _send_email() → modules.marketplace.alertas._send_email (Resend)

Tres tipos de email:
  bienvenida  — día 0, cuando admin aprueba la inmo
  checkin     — día 7 (days_remaining == 23)
  urgencia    — día 25 (days_remaining == 5)

check_and_send_trial_emails() es la función a llamar manualmente desde intranet.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
_TRIAL_DAYS    = 30
_CHECKIN_DAY   = 7    # día del trial en que enviamos check-in  (days_remaining == 23)
_URGENCIA_DAY  = 25   # día del trial en que enviamos urgencia  (days_remaining == 5)

_CONTACT_EMAIL = "hola@archirapid.com"
_CONTACT_PHONE = "+34 623 172 704"
_PORTAL_URL    = "https://archirapid.com"

# Colores ArchiRapid MLS (consistentes con mls_notificaciones.py)
_NAVY  = "#1B2A6B"
_GOLD  = "#F5A623"
_BG    = "#0D1B2A"
_CARD  = "#162241"
_TEXT  = "#E2E8F0"
_MUTED = "#94A3B8"

_BASE_STYLE = (
    f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
    f"background:{_BG};margin:0;padding:0;"
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body_html: str) -> None:
    """Delega al sistema Resend existente. Falla silenciosamente."""
    try:
        from modules.marketplace.alertas import _send_email as _resend
        _resend(to_email=to, to_name="", subject=subject, html=body_html)
    except Exception as e:
        logger.error("mls_trial_emails._send_email error: %s", e)


def _wrap_html(titulo: str, cuerpo: str) -> str:
    """Plantilla base MLS — idéntica a mls_notificaciones._wrap_html."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">
<title>{titulo}</title></head>
<body style="{_BASE_STYLE}">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:{_BG};padding:32px 0;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0"
           style="background:{_CARD};border-radius:16px;overflow:hidden;
                  border:1px solid rgba(245,166,35,0.25);">
      <tr>
        <td style="background:linear-gradient(135deg,{_NAVY},{_CARD});
                   padding:24px 32px;border-bottom:2px solid {_GOLD};">
          <div style="font-size:22px;font-weight:900;color:#F8FAFC;
                      letter-spacing:-0.5px;">
            🏗️ ArchiRapid <span style="color:{_GOLD};font-size:14px;
            font-weight:600;margin-left:8px;">MLS</span>
          </div>
          <div style="color:{_MUTED};font-size:12px;margin-top:3px;">
            Bolsa de Colaboración Inmobiliaria
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:28px 32px;color:{_TEXT};font-size:14px;line-height:1.6;">
          {cuerpo}
        </td>
      </tr>
      <tr>
        <td style="background:rgba(0,0,0,0.3);padding:14px 32px;
                   border-top:1px solid rgba(255,255,255,0.06);">
          <p style="color:{_MUTED};font-size:11px;margin:0;text-align:center;">
            © 2026 ArchiRapid MLS · {_CONTACT_EMAIL} ·
            <a href="{_PORTAL_URL}" style="color:{_MUTED};">{_PORTAL_URL}</a>
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _fecha_fin_trial(trial_start_date: str) -> str:
    """Devuelve la fecha de fin del trial en formato dd/mm/yyyy."""
    try:
        start = datetime.fromisoformat(trial_start_date)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        fin = start + timedelta(days=_TRIAL_DAYS)
        return fin.strftime("%d/%m/%Y")
    except Exception:
        return "—"


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def send_trial_email(
    inmo_email: str,
    inmo_nombre: str,
    tipo: str,
    days_remaining: int | None = None,
    trial_start_date: str | None = None,
) -> bool:
    """
    Envía el email de trial correspondiente al tipo indicado.

    Parámetros:
      inmo_email        — email de la inmobiliaria destinataria
      inmo_nombre       — nombre comercial de la inmobiliaria
      tipo              — "bienvenida" | "checkin" | "urgencia"
      days_remaining    — días restantes del trial (necesario para checkin/urgencia)
      trial_start_date  — ISO string de inicio del trial (para calcular fecha fin)

    Devuelve True si el envío se completó sin excepción.
    """
    tipo = tipo.strip().lower()

    if tipo == "bienvenida":
        return _send_bienvenida(inmo_email, inmo_nombre, trial_start_date)
    elif tipo == "checkin":
        return _send_checkin(inmo_email, inmo_nombre, days_remaining or 23)
    elif tipo == "urgencia":
        return _send_urgencia(inmo_email, inmo_nombre, trial_start_date)
    else:
        logger.warning("send_trial_email: tipo desconocido '%s'", tipo)
        return False


def _send_bienvenida(email: str, nombre: str, trial_start_date: str | None) -> bool:
    """Tipo 'bienvenida' — día 0 cuando admin aprueba."""
    cuerpo = f"""
<h2 style="color:{_GOLD};margin-top:0;">¡Bienvenida a ArchiRapid MLS!</h2>
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu registro como inmobiliaria colaboradora en <strong>ArchiRapid MLS</strong> ha sido aprobado por nuestro equipo.</p>

<div style="background:rgba(245,166,35,0.12);border-left:4px solid {_GOLD};
            border-radius:6px;padding:14px 18px;margin:18px 0;">
  <p style="margin:0 0 12px 0;font-weight:700;color:{_GOLD};">Para comenzar a operar, debes completar dos pasos:</p>
  <ol style="margin:0;padding-left:20px;line-height:1.8;color:{_TEXT};">
    <li><strong style="color:{_GOLD};">Firma el Acuerdo de Colaboración</strong> — accede a la plataforma y firma digitalmente el acuerdo MLS (eIDAS art. 25).</li>
    <li><strong style="color:{_GOLD};">Publica tu primera finca</strong> — introduce la referencia catastral validada, el precio y el split de comisión que ofreces a las colaboradoras.</li>
  </ol>
</div>

<p style="margin-top:24px;text-align:center;">
  <a href="{_PORTAL_URL}"
     style="background:{_NAVY};color:#fff;padding:12px 28px;
            border-radius:8px;text-decoration:none;font-weight:700;
            display:inline-block;">
    Acceder a ArchiRapid MLS →
  </a>
</p>

<p style="color:{_TEXT};margin-top:24px;">
  Si tienes cualquier duda, responde a este email o escríbenos a <a href="mailto:{_CONTACT_EMAIL}" style="color:{_GOLD};">{_CONTACT_EMAIL}</a>.
</p>

<p style="color:{_MUTED};font-size:12px;margin-top:28px;border-top:1px solid {_CARD};padding-top:16px;">
  © 2026 ArchiRapid MLS · <a href="mailto:{_CONTACT_EMAIL}" style="color:{_GOLD};">{_CONTACT_EMAIL}</a> · {_CONTACT_PHONE}<br>
  <a href="{_PORTAL_URL}" style="color:{_GOLD};">{_PORTAL_URL}</a>
</p>
"""
    _send_email(
        to=email,
        subject="¡Bienvenida a ArchiRapid MLS! Tu registro ha sido aprobado",
        body_html=_wrap_html("Bienvenida a ArchiRapid MLS", cuerpo),
    )
    return True


def _send_checkin(email: str, nombre: str, days_remaining: int) -> bool:
    """Tipo 'checkin' — día 7 del trial."""
    cuerpo = f"""
<h2 style="color:{_GOLD};margin-top:0;">¿Cómo va tu primera semana en ArchiRapid MLS?</h2>
<p>Hola <strong>{nombre}</strong>,</p>
<p>Llevas una semana en ArchiRapid MLS. ¿Has podido subir tu primera finca?</p>

<div style="background:rgba(245,166,35,0.12);border-left:4px solid {_GOLD};
            border-radius:6px;padding:14px 18px;margin:18px 0;">
  <p style="margin:0;color:{_TEXT};">Si tienes alguna duda o quieres que te acompañemos
  en los primeros pasos, responde a este email o llámanos:
  <strong>{_CONTACT_PHONE}</strong></p>
</div>

<p>Te quedan <strong>{days_remaining} {"día" if days_remaining == 1 else "días"} de trial</strong>. Aprovéchalos.</p>

<p style="margin-top:24px;">
  <a href="{_PORTAL_URL}"
     style="background:{_NAVY};color:#fff;padding:12px 28px;
            border-radius:8px;text-decoration:none;font-weight:700;
            display:inline-block;">
    Ir al portal MLS →
  </a>
</p>

<p style="color:{_MUTED};font-size:12px;margin-top:24px;">
  El equipo de ArchiRapid<br>
  <a href="mailto:{_CONTACT_EMAIL}" style="color:{_GOLD};">{_CONTACT_EMAIL}</a>
  · {_CONTACT_PHONE}
</p>
"""
    _send_email(
        to=email,
        subject="¿Cómo va tu primera semana en ArchiRapid MLS?",
        body_html=_wrap_html("Primera semana en MLS", cuerpo),
    )
    return True


def _send_urgencia(email: str, nombre: str, trial_start_date: str | None) -> bool:
    """Tipo 'urgencia' — día 25 del trial (5 días restantes)."""
    if trial_start_date:
        fecha_fin = _fecha_fin_trial(trial_start_date)
    else:
        fecha_fin = "—"

    cuerpo = f"""
<h2 style="color:{_GOLD};margin-top:0;">Tu acceso gratuito termina en 5 días</h2>
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu trial de 30 días termina el <strong>{fecha_fin}</strong>.</p>
<p>Para seguir operando en la red sin interrupciones, elige tu plan antes de esa fecha:</p>

<table width="100%" cellpadding="0" cellspacing="0"
       style="margin:18px 0;border-collapse:collapse;">
  <tr>
    <td style="padding:12px 14px;border-radius:8px;
               background:rgba(74,144,217,0.15);
               border:1px solid rgba(74,144,217,0.3);">
      <p style="margin:0;font-weight:700;color:#4A90D9;">STARTER &mdash; 39€/mes</p>
      <p style="margin:4px 0 0 0;font-size:13px;color:{_TEXT};">Hasta 5 fincas activas</p>
    </td>
  </tr>
  <tr><td style="height:8px;"></td></tr>
  <tr>
    <td style="padding:12px 14px;border-radius:8px;
               background:rgba(245,166,35,0.15);
               border:2px solid rgba(245,166,35,0.5);">
      <p style="margin:0;font-weight:700;color:{_GOLD};">AGENCY &mdash; 99€/mes
        <span style="font-size:11px;font-weight:400;margin-left:8px;
              background:{_GOLD};color:{_BG};padding:2px 8px;border-radius:12px;">
          El más contratado
        </span>
      </p>
      <p style="margin:4px 0 0 0;font-size:13px;color:{_TEXT};">Hasta 20 fincas + reservas de colaboración</p>
    </td>
  </tr>
  <tr><td style="height:8px;"></td></tr>
  <tr>
    <td style="padding:12px 14px;border-radius:8px;
               background:rgba(27,42,107,0.4);
               border:1px solid rgba(27,42,107,0.6);">
      <p style="margin:0;font-weight:700;color:{_TEXT};">PRO &mdash; 199€/mes</p>
      <p style="margin:4px 0 0 0;font-size:13px;color:{_MUTED};">Hasta 50 fincas + soporte prioritario</p>
    </td>
  </tr>
</table>

<p style="color:{_MUTED};font-size:12px;">Sin permanencia. Cancela cuando quieras.</p>

<p style="margin-top:20px;">
  <a href="{_PORTAL_URL}"
     style="background:{_GOLD};color:{_BG};padding:14px 32px;
            border-radius:8px;text-decoration:none;font-weight:800;
            display:inline-block;font-size:15px;">
    Elegir mi plan →
  </a>
</p>
<p style="color:{_MUTED};font-size:12px;">
  {_PORTAL_URL} → "Inmobiliarias MLS" → Planes
</p>

<p style="color:{_MUTED};font-size:12px;margin-top:20px;">
  ¿Tienes dudas? Llámanos: {_CONTACT_PHONE}
  o escribe a <a href="mailto:{_CONTACT_EMAIL}" style="color:{_GOLD};">{_CONTACT_EMAIL}</a><br>
  El equipo de ArchiRapid
</p>
"""
    _send_email(
        to=email,
        subject="Tu acceso gratuito a ArchiRapid MLS termina en 5 dias",
        body_html=_wrap_html("Tu trial termina pronto", cuerpo),
    )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN DE ENVÍO MASIVO — llamar desde intranet o programada
# ─────────────────────────────────────────────────────────────────────────────

def check_and_send_trial_emails() -> list[str]:
    """
    Recorre todas las inmobiliarias con trial activo (plan_activo=0)
    y envía el email de checkin (día 7) o urgencia (día 25) si aplica.

    Criterio de envío:
      - Día 7  exacto: days_remaining == 23  → tipo "checkin"
      - Día 25 exacto: days_remaining == 5   → tipo "urgencia"

    No hay deduplicación en BD — se asume que esta función se llama
    una vez al día desde intranet. Si se llama varias veces el mismo día
    enviará el email más de una vez para las inmos en criterio.

    Devuelve lista de strings describiendo cada envío realizado.
    """
    from modules.mls.mls_db import get_inmos_con_trial_activo, check_trial_status

    inmos = get_inmos_con_trial_activo()
    enviados: list[str] = []

    for inmo in inmos:
        inmo_id    = inmo.get("id", "")
        nombre     = inmo.get("nombre_comercial") or inmo.get("nombre", "?")
        email      = inmo.get("email", "")
        trial_start = inmo.get("trial_start_date")

        if not email or not inmo_id:
            continue

        status = check_trial_status(inmo_id)
        days_rem = status.get("days_remaining", 0)

        if days_rem == 23:
            # Día 7 del trial
            try:
                send_trial_email(email, nombre, "checkin",
                                 days_remaining=days_rem,
                                 trial_start_date=trial_start)
                enviados.append(f"checkin → {nombre} ({email}), {days_rem} días restantes")
                logger.info("Trial checkin enviado a %s (%s)", nombre, email)
            except Exception as e:
                logger.error("Error checkin %s: %s", email, e)

        elif days_rem == 5:
            # Día 25 del trial — email urgencia a la inmo
            try:
                send_trial_email(email, nombre, "urgencia",
                                 days_remaining=days_rem,
                                 trial_start_date=trial_start)
                enviados.append(f"urgencia → {nombre} ({email}), {days_rem} días restantes")
                logger.info("Trial urgencia enviado a %s (%s)", nombre, email)
            except Exception as e:
                logger.error("Error urgencia %s: %s", email, e)
            # Aviso a admin: trial expira en 5 días
            try:
                from modules.mls.mls_notificaciones import _send_telegram, _send_email, _ADMIN_EMAIL
                _send_telegram(
                    f"⏰ <b>Trial expira en 5 días</b>\n"
                    f"Inmo: <b>{nombre}</b>\nEmail: {email}\n"
                    f"Accede a intranet para hacer seguimiento."
                )
                _send_email(
                    to=_ADMIN_EMAIL,
                    subject=f"⏰ Trial ArchiRapid MLS expira en 5 días — {nombre}",
                    body_html=f"""
                    <p>La inmobiliaria <b>{nombre}</b> ({email}) tiene su trial de 30 días a punto de vencer.</p>
                    <p><b>Días restantes:</b> 5</p>
                    <p>Considera contactarla para ayudarla a elegir un plan antes de que expire.</p>
                    <p style="color:#64748b;font-size:0.85em;">Panel admin: archirapid.com → Intranet → MLS → Trial</p>
                    """,
                )
                enviados.append(f"admin-aviso → {nombre} trial expira en 5 días")
            except Exception as e:
                logger.error("Error aviso admin trial %s: %s", email, e)

    return enviados
