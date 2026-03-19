"""
modules/mls/mls_notificaciones.py
Notificaciones combinadas para eventos ArchiRapid MLS.

Canales:
  - Telegram admin  → email_notify._send()     (existente)
  - Email via Resend → alertas._send_email()    (existente)

Sin imports de Streamlit en este módulo.
Sin acceso directo a BD en este módulo.
Todos los envíos con try/except silencioso — ningún fallo interrumpe el flujo.
"""

# =============================================================================
# HELPERS PRIVADOS — reutilizan funciones base existentes del proyecto
# =============================================================================

def _send_telegram(mensaje: str) -> None:
    """
    Envía mensaje Telegram al admin via email_notify._send() (existente).
    Falla silenciosamente.
    """
    try:
        from modules.marketplace.email_notify import _send
        _send(mensaje)
    except Exception:
        pass


def _send_email(to: str, subject: str, body_html: str) -> None:
    """
    Envía email via alertas._send_email() (existente).
    from: "ArchiRapid <noreply@archirapid.com>" (hardcoded en alertas.py).
    Falla silenciosamente.
    """
    try:
        from modules.marketplace.alertas import _send_email as _resend
        _resend(to_email=to, to_name="", subject=subject, html=body_html)
    except Exception:
        pass


# ── Constantes de estilo HTML (colores ArchiRapid MLS) ───────────────────────
_NAVY  = "#1B2A6B"
_GOLD  = "#F5A623"
_BG    = "#0D1B2A"
_CARD  = "#162241"
_TEXT  = "#E2E8F0"
_MUTED = "#94A3B8"

_ADMIN_EMAIL = "admin@archirapid.com"

_BASE_STYLE = (
    f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
    f"background:{_BG};margin:0;padding:0;"
)

def _wrap_html(titulo: str, cuerpo: str) -> str:
    """Envuelve el cuerpo en la plantilla base MLS con header navy/gold."""
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

      <!-- Header -->
      <tr>
        <td style="background:linear-gradient(135deg,{_NAVY},{_CARD});
                   padding:24px 32px;
                   border-bottom:2px solid {_GOLD};">
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

      <!-- Body -->
      <tr>
        <td style="padding:28px 32px;color:{_TEXT};font-size:14px;
                   line-height:1.6;">
          {cuerpo}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:rgba(0,0,0,0.3);padding:14px 32px;
                   border-top:1px solid rgba(255,255,255,0.06);">
          <p style="color:{_MUTED};font-size:11px;margin:0;text-align:center;">
            © 2026 ArchiRapid MLS · admin@archirapid.com ·
            <a href="https://archirapid.streamlit.app"
               style="color:{_MUTED};">archirapid.streamlit.app</a>
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _tabla_html(filas: list[tuple]) -> str:
    """Genera tabla HTML de dos columnas con pares (clave, valor)."""
    rows = ""
    for clave, valor in filas:
        rows += (
            f'<tr>'
            f'<td style="padding:8px 12px;color:{_MUTED};font-size:12px;'
            f'text-transform:uppercase;letter-spacing:0.8px;'
            f'white-space:nowrap;width:140px;">{clave}</td>'
            f'<td style="padding:8px 12px;color:{_TEXT};font-size:14px;'
            f'font-weight:600;">{valor}</td>'
            f'</tr>'
        )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:rgba(0,0,0,0.25);border-radius:10px;'
        f'border:1px solid rgba(245,166,35,0.15);margin:16px 0;'
        f'border-collapse:collapse;">'
        f'{rows}</table>'
    )


# =============================================================================
# EVENTOS — una función pública por evento
# =============================================================================

def notif_nuevo_registro(nombre: str, cif: str, email: str, ip: str) -> None:
    """
    Evento: nueva inmobiliaria registrada, pendiente de aprobación admin.
    → Telegram admin + Email admin
    """
    # Telegram
    _send_telegram(
        f"🏢 <b>Nueva inmo pendiente</b>: {nombre} | "
        f"CIF: {cif} | {email} | IP: {ip}"
    )

    # Email admin
    tabla = _tabla_html([
        ("Nombre",     nombre),
        ("CIF",        cif),
        ("Email",      email),
        ("IP registro", ip),
        ("Estado",     "Pendiente de aprobación"),
    ])
    cuerpo = (
        f"<p>Se ha registrado una nueva inmobiliaria y está pendiente de "
        f"revisión y aprobación en la intranet.</p>"
        f"{tabla}"
        f"<p style='margin-top:20px;'>"
        f"<a href='https://archirapid.streamlit.app' "
        f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;'>"
        f"Revisar en Intranet →</a></p>"
    )
    _send_email(
        to=_ADMIN_EMAIL,
        subject=f"Nueva inmobiliaria pendiente — {nombre}",
        body_html=_wrap_html(f"Nueva inmobiliaria: {nombre}", cuerpo),
    )


def notif_aprobacion(nombre: str, email: str, aprobada: bool) -> None:
    """
    Evento: admin aprueba o rechaza una inmobiliaria.
    → Telegram admin + Email admin + (si aprobada) Email a la inmo
    """
    estado = "Aprobada" if aprobada else "Rechazada"
    icono  = "✅" if aprobada else "❌"

    # Telegram
    _send_telegram(f"{icono} <b>{estado}</b>: {nombre}")

    # Email admin (confirmación de acción)
    tabla_adm = _tabla_html([
        ("Inmobiliaria", nombre),
        ("Email",        email),
        ("Acción",       estado),
    ])
    _send_email(
        to=_ADMIN_EMAIL,
        subject=f"[MLS Admin] {estado}: {nombre}",
        body_html=_wrap_html(
            f"{estado}: {nombre}",
            f"<p>Se ha registrado la siguiente acción de moderación:</p>"
            f"{tabla_adm}",
        ),
    )

    # Email a la inmo — solo si aprobada
    if aprobada:
        cuerpo_inmo = (
            f"<h2 style='color:{_GOLD};margin-top:0;'>¡Bienvenida a ArchiRapid MLS!</h2>"
            f"<p>Tu registro como inmobiliaria colaboradora en <strong>ArchiRapid MLS</strong> "
            f"ha sido aprobado por nuestro equipo.</p>"
            f"<p>Para comenzar a operar, debes completar dos pasos:</p>"
            f"<ol style='color:{_TEXT};line-height:2;'>"
            f"<li><strong style='color:{_GOLD};'>Firma el Acuerdo de Colaboración</strong> — "
            f"accede a la plataforma y firma digitalmente el acuerdo MLS (eIDAS art. 25).</li>"
            f"<li><strong style='color:{_GOLD};'>Publica tu primera finca</strong> — "
            f"introduce la referencia catastral validada, el precio y el split de comisión "
            f"que ofreces a las colaboradoras.</li>"
            f"</ol>"
            f"<p style='margin-top:20px;'>"
            f"<a href='https://archirapid.streamlit.app' "
            f"style='background:{_NAVY};color:#fff;padding:12px 28px;"
            f"border-radius:8px;text-decoration:none;font-weight:700;"
            f"display:inline-block;'>"
            f"Acceder a ArchiRapid MLS →</a></p>"
            f"<p style='color:{_MUTED};font-size:12px;margin-top:20px;'>"
            f"Si tienes cualquier duda, responde a este email o escríbenos a "
            f"<a href='mailto:{_ADMIN_EMAIL}' style='color:{_GOLD};'>{_ADMIN_EMAIL}</a>.</p>"
        )
        _send_email(
            to=email,
            subject="Tu registro en ArchiRapid MLS ha sido aprobado",
            body_html=_wrap_html("Bienvenida a ArchiRapid MLS", cuerpo_inmo),
        )


def notif_firma_acuerdo(nombre: str, cif: str, email: str,
                         firma_hash: str) -> None:
    """
    Evento: inmobiliaria firma el acuerdo de colaboración.
    → Telegram admin + Email a la inmo (confirmación legal)
    """
    from datetime import datetime, timezone
    timestamp_fmt = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # Telegram
    _send_telegram(
        f"✍️ <b>Firma acuerdo</b>: {nombre} | {firma_hash[:16]}..."
    )

    # Email a la inmo — confirmación legal con hash completo
    tabla = _tabla_html([
        ("Inmobiliaria", nombre),
        ("CIF",          cif),
        ("Fecha firma",  timestamp_fmt),
        ("Versión",      "1.0"),
        ("SHA-256 firma", f'<span style="font-family:monospace;font-size:11px;'
                          f'color:{_GOLD};">{firma_hash}</span>'),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Confirmación de firma digital</h2>"
        f"<p>Se ha registrado tu firma del <strong>Acuerdo de Colaboración "
        f"Inmobiliaria ArchiRapid MLS</strong> con los siguientes datos:</p>"
        f"{tabla}"
        f"<p style='color:{_MUTED};font-size:12px;margin-top:16px;'>"
        f"Esta firma electrónica tiene validez legal conforme al artículo 25 "
        f"del Reglamento (UE) N.º 910/2014 (eIDAS). ArchiRapid conservará "
        f"este registro durante un mínimo de 5 años conforme a la Ley 34/2002 "
        f"(LSSI-CE). El hash SHA-256 identifica de forma unívoca el documento "
        f"firmado y el momento de la firma.</p>"
    )
    _send_email(
        to=email,
        subject="Confirmación de firma — ArchiRapid MLS",
        body_html=_wrap_html("Confirmación de firma digital MLS", cuerpo),
    )


def notif_finca_publicada(ref_codigo: str, titulo: str,
                           precio: float, inmo_email: str) -> None:
    """
    Evento: finca MLS publicada en el mercado abierto.
    → Telegram admin + Email a la inmo listante
    """
    # Telegram
    _send_telegram(
        f"🏠 <b>Finca MLS publicada</b>: {ref_codigo} | "
        f"{titulo} | €{precio:,.0f}"
    )

    # Email a la inmo listante
    tabla = _tabla_html([
        ("REF código", ref_codigo),
        ("Título",     titulo),
        ("Precio",     f"€{precio:,.0f}"),
        ("Estado",     "Publicada en mercado abierto MLS"),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Tu finca está publicada</h2>"
        f"<p>Tu finca ya es visible para todas las inmobiliarias colaboradoras "
        f"de <strong>ArchiRapid MLS</strong>. Aparece en el mapa con un "
        f"<span style='color:{_GOLD};font-weight:700;'>pin naranja</span> "
        f"que la distingue de las fincas de propietario directo.</p>"
        f"{tabla}"
        f"<p style='margin-top:20px;'>"
        f"<a href='https://archirapid.streamlit.app' "
        f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;'>"
        f"Ver pin en el mapa →</a></p>"
    )
    _send_email(
        to=inmo_email,
        subject=f"Tu finca {ref_codigo} está publicada en ArchiRapid MLS",
        body_html=_wrap_html(f"Finca publicada: {ref_codigo}", cuerpo),
    )


def notif_finca_reservada(ref_codigo: str,
                           inmo_listante_email: str) -> None:
    """
    Evento: una colaboradora ha reservado una finca (exclusiva 72h).
    → Telegram admin + Email a la listante
    La identidad de la colaboradora NO se revela.
    """
    # Telegram
    _send_telegram(f"🔒 <b>Reserva</b>: {ref_codigo}")

    # Email a la listante — sin revelar quién es la colaboradora
    tabla = _tabla_html([
        ("REF código", ref_codigo),
        ("Exclusiva",  "72 horas desde el momento de la reserva"),
        ("Estado",     "Reservada — no disponible para otras colaboradoras"),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Tu finca ha recibido una reserva</h2>"
        f"<p>Una inmobiliaria colaboradora ha reservado tu finca con "
        f"<strong>exclusiva de 72 horas</strong>.</p>"
        f"{tabla}"
        f"<p style='color:{_MUTED};font-size:13px;margin-top:16px;'>"
        f"Durante las próximas 72 horas la finca no estará disponible para "
        f"otras colaboradoras. ArchiRapid coordinará el siguiente paso. "
        f"La identidad de la inmobiliaria colaboradora se revelará en el "
        f"momento del cierre de la operación, conforme al Artículo 3 del "
        f"Acuerdo de Colaboración.</p>"
    )
    _send_email(
        to=inmo_listante_email,
        subject=f"Tu finca {ref_codigo} ha recibido una reserva",
        body_html=_wrap_html(f"Reserva recibida: {ref_codigo}", cuerpo),
    )


def notif_pago_suscripcion(nombre: str, email: str,
                            plan: str, importe_eur: float) -> None:
    """
    Evento: inmobiliaria realiza pago de suscripción MLS.
    → Telegram admin + Email admin (registro contable) + Email a la inmo
    """
    from datetime import datetime, timezone
    fecha_pago = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    _LIMITES_PLAN = {
        "starter":    "Hasta 5 fincas listadas · Solo rol listante",
        "agency":     "Hasta 20 fincas listadas · Rol listante + colaboradora · Reservas",
        "enterprise": "Fincas ilimitadas · Todos los roles · Reservas · Soporte prioritario",
    }
    limites = _LIMITES_PLAN.get(plan.lower(), "Consultar condiciones del plan")

    # Telegram
    _send_telegram(
        f"💶 <b>Pago MLS</b>: {nombre} | {plan.upper()} | €{importe_eur:.2f}"
    )

    # Email admin (registro contable)
    tabla_adm = _tabla_html([
        ("Inmobiliaria", nombre),
        ("Email",        email),
        ("Plan",         plan.upper()),
        ("Importe",      f"€{importe_eur:.2f}"),
        ("Fecha pago",   fecha_pago),
    ])
    _send_email(
        to=_ADMIN_EMAIL,
        subject=f"[MLS Contabilidad] Pago {plan.upper()} — {nombre} — €{importe_eur:.2f}",
        body_html=_wrap_html(
            f"Pago MLS: {nombre}",
            f"<p>Registro de pago de suscripción MLS:</p>{tabla_adm}",
        ),
    )

    # Email a la inmo (confirmación del pago)
    tabla_inmo = _tabla_html([
        ("Plan activo",  plan.upper()),
        ("Importe",      f"€{importe_eur:.2f}"),
        ("Fecha pago",   fecha_pago),
        ("Renovación",   "30 días desde la fecha de pago"),
        ("Capacidades",  limites),
    ])
    cuerpo_inmo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Pago confirmado</h2>"
        f"<p>Hemos recibido tu pago para el plan "
        f"<strong style='color:{_GOLD};'>{plan.upper()}</strong>. "
        f"Tu cuenta está activa y puedes operar en ArchiRapid MLS.</p>"
        f"{tabla_inmo}"
        f"<p style='margin-top:20px;'>"
        f"<a href='https://archirapid.streamlit.app' "
        f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;'>"
        f"Acceder a ArchiRapid MLS →</a></p>"
        f"<p style='color:{_MUTED};font-size:12px;margin-top:16px;'>"
        f"Conserva este email como justificante de pago. Para cualquier "
        f"consulta escríbenos a "
        f"<a href='mailto:{_ADMIN_EMAIL}' style='color:{_GOLD};'>"
        f"{_ADMIN_EMAIL}</a>.</p>"
    )
    _send_email(
        to=email,
        subject=f"Confirmación de pago — Plan {plan.upper()} | ArchiRapid MLS",
        body_html=_wrap_html(f"Pago confirmado: Plan {plan.upper()}", cuerpo_inmo),
    )


def notif_reserva_expirada(ref_codigo: str,
                            inmo_listante_email: str) -> None:
    """
    Evento: reserva de 72h expirada sin operación — finca vuelve al mercado.
    → Telegram admin + Email a la listante
    """
    # Telegram
    _send_telegram(f"⏰ <b>Reserva expirada</b>: {ref_codigo}")

    # Email a la listante
    tabla = _tabla_html([
        ("REF código", ref_codigo),
        ("Estado",     "Disponible — de nuevo en el mercado abierto MLS"),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Tu finca vuelve al mercado</h2>"
        f"<p>La reserva de exclusiva de 72 horas sobre tu finca "
        f"<strong>{ref_codigo}</strong> ha expirado sin que se haya "
        f"comunicado una operación en curso.</p>"
        f"{tabla}"
        f"<p>Tu finca está nuevamente disponible para todas las inmobiliarias "
        f"colaboradoras de ArchiRapid MLS. Si recibes otra reserva, el proceso "
        f"se reinicia con una nueva exclusiva de 72 horas.</p>"
        f"<p style='margin-top:20px;'>"
        f"<a href='https://archirapid.streamlit.app' "
        f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;'>"
        f"Ver estado en ArchiRapid MLS →</a></p>"
    )
    _send_email(
        to=inmo_listante_email,
        subject=f"Tu finca {ref_codigo} vuelve al mercado MLS",
        body_html=_wrap_html(f"Reserva expirada: {ref_codigo}", cuerpo),
    )


def notif_reserva_cliente(ref_codigo: str, nombre_cliente: str,
                           precio: float) -> None:
    """
    Evento: cliente final reserva directamente una finca MLS.
    → Telegram admin + Email admin
    Admin tiene 48h para confirmar disponibilidad.
    """
    # Telegram
    _send_telegram(
        f"🔔 <b>RESERVA CLIENTE DIRECTO</b>: {ref_codigo} | "
        f"{nombre_cliente} | €{precio:,.0f} | "
        f"48h para confirmar disponibilidad"
    )

    # Email admin
    tabla = _tabla_html([
        ("REF código",    ref_codigo),
        ("Cliente",       nombre_cliente),
        ("Precio finca",  f"€{precio:,.0f}"),
        ("Importe reserva", "€200,00"),
        ("Plazo admin",   "48h para confirmar disponibilidad"),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Reserva directa recibida</h2>"
        f"<p>Un cliente final ha realizado una reserva directa sobre una finca MLS. "
        f"Tienes <strong>48 horas</strong> para confirmar la disponibilidad.</p>"
        f"{tabla}"
        f"<p style='margin-top:20px;'>"
        f"<a href='https://archirapid.streamlit.app' "
        f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;'>"
        f"Confirmar disponibilidad en Intranet →</a></p>"
    )
    _send_email(
        to=_ADMIN_EMAIL,
        subject=f"Reserva directa — {ref_codigo}",
        body_html=_wrap_html(f"Reserva directa: {ref_codigo}", cuerpo),
    )


def notif_confirmacion_reserva_cliente(email_cliente: str,
                                        nombre_cliente: str,
                                        ref_codigo: str,
                                        confirmada: bool) -> None:
    """
    Evento: admin confirma o rechaza la disponibilidad de la finca reservada por cliente.
    → Email al cliente (solo)
    """
    if confirmada:
        tabla = _tabla_html([
            ("REF código",   ref_codigo),
            ("Estado",       "Reserva confirmada"),
            ("Exclusiva",    "72 horas desde la confirmación"),
            ("Próximo paso", "ArchiRapid te contactará para los siguientes pasos"),
        ])
        cuerpo = (
            f"<h2 style='color:{_GOLD};margin-top:0;'>Tu reserva está confirmada</h2>"
            f"<p>Hola <strong>{nombre_cliente}</strong>,</p>"
            f"<p>Tu reserva sobre la finca <strong>{ref_codigo}</strong> ha sido "
            f"<strong style='color:{_GOLD};'>confirmada</strong>. La finca está "
            f"disponible y tiene una exclusiva de <strong>72 horas</strong> para ti.</p>"
            f"{tabla}"
            f"<p>Nuestro equipo se pondrá en contacto contigo en breve para coordinar "
            f"los siguientes pasos. Conserva el número de referencia "
            f"<strong>{ref_codigo}</strong> para cualquier consulta.</p>"
            f"<p style='color:{_MUTED};font-size:12px;margin-top:16px;'>"
            f"¿Tienes alguna pregunta? Escríbenos a "
            f"<a href='mailto:{_ADMIN_EMAIL}' style='color:{_GOLD};'>{_ADMIN_EMAIL}</a>.</p>"
        )
        _send_email(
            to=email_cliente,
            subject=f"Tu reserva está confirmada — {ref_codigo}",
            body_html=_wrap_html(f"Reserva confirmada: {ref_codigo}", cuerpo),
        )
    else:
        cuerpo = (
            f"<h2 style='color:#E53E3E;margin-top:0;'>Finca no disponible</h2>"
            f"<p>Hola <strong>{nombre_cliente}</strong>,</p>"
            f"<p>Lamentamos informarte de que la finca <strong>{ref_codigo}</strong> "
            f"no está disponible en este momento. Tu reserva ha sido cancelada.</p>"
            f"<table width='100%' cellpadding='0' cellspacing='0' "
            f"style='background:rgba(0,0,0,0.25);border-radius:10px;"
            f"border:1px solid rgba(229,62,62,0.3);margin:16px 0;border-collapse:collapse;'>"
            f"<tr><td style='padding:12px 16px;color:{_MUTED};font-size:12px;"
            f"text-transform:uppercase;letter-spacing:0.8px;'>Reembolso</td>"
            f"<td style='padding:12px 16px;color:{_TEXT};font-size:14px;font-weight:600;'>"
            f"€200,00 en 3–5 días hábiles</td></tr>"
            f"</table>"
            f"<p>Te animamos a explorar otras fincas disponibles en ArchiRapid. "
            f"Hay propiedades similares que pueden interesarte.</p>"
            f"<p style='margin-top:20px;'>"
            f"<a href='https://archirapid.streamlit.app' "
            f"style='background:{_NAVY};color:#fff;padding:10px 24px;"
            f"border-radius:8px;text-decoration:none;font-weight:700;'>"
            f"Ver otras fincas →</a></p>"
            f"<p style='color:{_MUTED};font-size:12px;margin-top:16px;'>"
            f"Si tienes alguna duda sobre el reembolso, escríbenos a "
            f"<a href='mailto:{_ADMIN_EMAIL}' style='color:{_GOLD};'>{_ADMIN_EMAIL}</a>.</p>"
        )
        _send_email(
            to=email_cliente,
            subject=f"Lo sentimos — {ref_codigo} no disponible",
            body_html=_wrap_html(f"Finca no disponible: {ref_codigo}", cuerpo),
        )


def _send_admin_email(subject: str, inmo: dict, mensaje: str,
                      referencia: str = "") -> None:
    """
    Envía email de consulta de inmobiliaria a hola@archirapid.com.
    Llamado desde el botón 'Contactar con ArchiRapid' del portal operativo.
    """
    nombre   = inmo.get("nombre_comercial") or inmo.get("nombre", "")
    email    = inmo.get("email", "")
    plan     = (inmo.get("plan") or "ninguno").upper()
    ref_txt  = referencia.strip() if referencia else "—"

    tabla = _tabla_html([
        ("Inmobiliaria", nombre),
        ("Email",        email),
        ("Plan",         plan),
        ("Referencia",   ref_txt),
    ])
    cuerpo = (
        f"<h2 style='color:{_GOLD};margin-top:0;'>Consulta desde el portal MLS</h2>"
        f"{tabla}"
        f"<div style='background:rgba(255,255,255,0.05);border-left:4px solid {_GOLD};"
        f"padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0;'>"
        f"<p style='color:{_TEXT};margin:0;white-space:pre-wrap;'>{mensaje}</p>"
        f"</div>"
    )
    _send_email(
        to="hola@archirapid.com",
        subject=subject,
        body_html=_wrap_html(f"Consulta MLS — {nombre}", cuerpo),
    )
    _send_telegram(f"📩 Consulta MLS de {nombre} ({email}): {mensaje[:120]}")
