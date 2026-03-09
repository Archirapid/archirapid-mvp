# modules/marketplace/alertas.py
"""
Sistema de alertas de nuevas fincas — ArchiRapid
• Suscripción por provincia + presupuesto máximo
• Envío via Resend.com REST API (no SDK, solo requests)
• Tabla: plot_alerts (email, name, province, max_price, created_at, active)
• Falla silenciosamente si no hay RESEND_API_KEY configurada
"""
import sqlite3
import os
import datetime
import streamlit as st

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn():
    from modules.marketplace.utils import DB_PATH
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS plot_alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            name       TEXT,
            province   TEXT,
            max_price  REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            active     INTEGER DEFAULT 1
        )
    """)
    c.commit()
    return c


def subscribe(email: str, name: str, province: str, max_price: float) -> bool:
    """Guarda o actualiza la suscripción. Devuelve True si es nueva."""
    try:
        db = _conn()
        existing = db.execute(
            "SELECT id FROM plot_alerts WHERE email=? AND province=?",
            (email.lower().strip(), province)
        ).fetchone()
        now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if existing:
            db.execute(
                "UPDATE plot_alerts SET name=?, max_price=?, active=1, created_at=? WHERE id=?",
                (name, max_price, now, existing[0])
            )
            db.commit(); db.close()
            return False  # ya existía
        db.execute(
            "INSERT INTO plot_alerts (email, name, province, max_price, created_at) VALUES (?,?,?,?,?)",
            (email.lower().strip(), name, province, max_price, now)
        )
        db.commit(); db.close()
        return True  # nueva suscripción
    except Exception:
        return False


def unsubscribe(email: str, province: str = None):
    try:
        db = _conn()
        if province:
            db.execute("UPDATE plot_alerts SET active=0 WHERE email=? AND province=?",
                       (email.lower().strip(), province))
        else:
            db.execute("UPDATE plot_alerts SET active=0 WHERE email=?",
                       (email.lower().strip(),))
        db.commit(); db.close()
    except Exception:
        pass


def get_subscribers(province: str = None, max_price_filter: float = None) -> list:
    """Devuelve suscriptores activos que coinciden con la finca."""
    try:
        db = _conn()
        rows = db.execute(
            "SELECT email, name, province, max_price FROM plot_alerts WHERE active=1"
        ).fetchall()
        db.close()
        result = []
        for email, name, prov, mp in rows:
            if province and prov and prov.lower() not in ("todas", "") and prov.lower() != province.lower():
                continue
            if max_price_filter and mp and mp > 0 and max_price_filter > mp:
                continue
            result.append({"email": email, "name": name, "province": prov, "max_price": mp})
        return result
    except Exception:
        return []


# ── Email via Resend REST API ─────────────────────────────────────────────────

def _resend_key() -> str:
    try:
        v = st.secrets.get("RESEND_API_KEY", "")
        if v: return str(v).strip()
    except Exception:
        pass
    return os.getenv("RESEND_API_KEY", "").strip()


def _send_email(to_email: str, to_name: str, subject: str, html: str) -> bool:
    key = _resend_key()
    if not key:
        return False
    try:
        import requests as _req
        resp = _req.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def _html_alerta(plot: dict, subscriber_name: str) -> str:
    title    = plot.get("title", "Nueva finca")
    province = plot.get("province") or plot.get("locality") or "España"
    m2       = plot.get("m2") or plot.get("surface_m2") or "—"
    price    = float(plot.get("price") or 0)
    desc     = (plot.get("description") or "")[:180]
    pid      = plot.get("id", "")
    url      = f"https://archirapid.streamlit.app/?selected_plot={pid}"
    name_hi  = subscriber_name.split()[0] if subscriber_name else "Hola"

    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0D1B2A;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0D1B2A;padding:32px 0;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="background:#1E3A5F;border-radius:16px;overflow:hidden;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1E3A5F,#0D2A4A);padding:28px 32px;border-bottom:2px solid rgba(245,158,11,0.4);">
            <div style="font-size:28px;font-weight:900;color:#F8FAFC;letter-spacing:-0.5px;">
              🏗️ ArchiRapid
            </div>
            <div style="color:#94A3B8;font-size:13px;margin-top:4px;">
              Nueva finca que coincide con tus alertas
            </div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">
            <p style="color:#CBD5E1;font-size:15px;margin:0 0 20px;">
              Hola <strong style="color:#F8FAFC;">{name_hi}</strong>,
              hemos publicado una nueva finca que encaja con tus preferencias:
            </p>

            <!-- Finca card -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:rgba(13,27,42,0.6);border:1px solid rgba(245,158,11,0.25);
                          border-radius:12px;overflow:hidden;margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <div style="font-size:18px;font-weight:800;color:#F8FAFC;margin-bottom:8px;">{title}</div>
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding-right:24px;">
                        <div style="color:#94A3B8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Precio</div>
                        <div style="color:#F59E0B;font-size:20px;font-weight:800;">€{price:,.0f}</div>
                      </td>
                      <td style="padding-right:24px;">
                        <div style="color:#94A3B8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Superficie</div>
                        <div style="color:#F8FAFC;font-size:18px;font-weight:700;">{m2} m²</div>
                      </td>
                      <td>
                        <div style="color:#94A3B8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Ubicación</div>
                        <div style="color:#F8FAFC;font-size:16px;font-weight:600;">{province}</div>
                      </td>
                    </tr>
                  </table>
                  <p style="color:#94A3B8;font-size:13px;margin:14px 0 0;">{desc}…</p>
                </td>
              </tr>
            </table>

            <!-- CTA -->
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td align="center">
                  <a href="{url}"
                     style="display:inline-block;background:linear-gradient(135deg,#2563EB,#1D4ED8);
                            color:#fff;font-weight:700;font-size:15px;text-decoration:none;
                            padding:14px 36px;border-radius:10px;">
                    Ver finca en ArchiRapid →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:rgba(0,0,0,0.3);padding:16px 32px;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="color:#475569;font-size:11px;margin:0;text-align:center;">
              © 2026 ArchiRapid · archirapid2026@gmail.com ·
              <a href="{url}&unsub=1" style="color:#475569;">Cancelar alertas</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def notify_new_plot(plot: dict) -> int:
    """Envía alertas a todos los suscriptores que coinciden. Devuelve nº enviados."""
    province   = plot.get("province") or plot.get("locality") or ""
    price      = float(plot.get("price") or 0)
    subscribers = get_subscribers(province=province, max_price_filter=price)
    sent = 0
    for sub in subscribers:
        subject = f"🏡 Nueva finca en {province} — €{price:,.0f} | ArchiRapid"
        html    = _html_alerta(plot, sub["name"] or "")
        if _send_email(sub["email"], sub["name"] or "", subject, html):
            sent += 1
    return sent


# ── Streamlit UI: formulario de suscripción ───────────────────────────────────

_PROVINCIAS = [
    "Todas las provincias",
    "Madrid", "Andalucía", "Extremadura", "Castilla y León",
    "Cataluña", "Valencia", "País Vasco", "Galicia", "Aragón",
    "Castilla-La Mancha", "Murcia", "Canarias", "Baleares", "Otras",
]


def render_subscribe_form(plot: dict = None, key_prefix: str = "alert"):
    """Formulario compacto de suscripción a alertas."""
    # Pre-rellenar provincia con la de la finca actual
    default_prov = (plot.get("province") or "Todas las provincias") if plot else "Todas las provincias"
    default_price = float(plot.get("price") or 0) * 2 if plot else 500_000.0
    default_idx = _PROVINCIAS.index(default_prov) if default_prov in _PROVINCIAS else 0

    st.markdown("""
    <div style="background:rgba(37,99,235,0.08);border:1px solid rgba(37,99,235,0.3);
                border-radius:10px;padding:14px 18px;margin-bottom:8px;">
        <div style="font-weight:700;color:#F8FAFC;font-size:14px;">
            🔔 Recibir alertas de nuevas fincas
        </div>
        <div style="color:#94A3B8;font-size:12px;margin-top:2px;">
            Te avisamos por email cuando publiquemos fincas que encajen contigo
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form(f"{key_prefix}_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            al_name  = st.text_input("Tu nombre", placeholder="Nombre", key=f"{key_prefix}_name")
            al_email = st.text_input("Email *", placeholder="tu@email.com", key=f"{key_prefix}_email")
        with c2:
            al_prov  = st.selectbox("Provincia de interés", _PROVINCIAS,
                                    index=default_idx, key=f"{key_prefix}_prov")
            al_price = st.number_input("Presupuesto máximo (€)",
                                       min_value=0.0, max_value=5_000_000.0,
                                       value=default_price, step=10_000.0,
                                       format="%.0f", key=f"{key_prefix}_price",
                                       help="0 = sin límite de precio")

        submitted = st.form_submit_button("🔔 Activar alerta", type="primary", use_container_width=True)
        if submitted:
            if not al_email or "@" not in al_email:
                st.error("Introduce un email válido.")
            else:
                prov_save = "" if al_prov == "Todas las provincias" else al_prov
                is_new = subscribe(al_email, al_name, prov_save, al_price)
                # Notificar al admin via Telegram
                try:
                    from modules.marketplace.email_notify import _send
                    _send(
                        f"🔔 <b>Nueva alerta registrada</b>\n"
                        f"Nombre: {al_name}\nEmail: {al_email}\n"
                        f"Provincia: {prov_save or 'Todas'}\nPresupuesto: €{al_price:,.0f}"
                    )
                except Exception:
                    pass
                if is_new:
                    st.success(f"✅ Alerta activada. Te avisaremos cuando haya fincas en {al_prov}.")
                else:
                    st.info("✓ Alerta actualizada con los nuevos criterios.")
