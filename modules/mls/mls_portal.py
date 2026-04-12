"""
ARCHIRAPID MLS — Orquestador principal
Gestiona login, registro, aprobación, planes Stripe y routing al portal operativo.
"""
from __future__ import annotations

import re
import uuid
import streamlit as st
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from src import db as _db
from modules.mls import mls_db
from modules.mls import mls_firma
from modules.mls import mls_notificaciones

# ── Constantes ────────────────────────────────────────────────────────────────

_CIF_RE = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVW]\d{8}$")
_SESSION_KEY = "mls_inmo"          # st.session_state key — sin colisión con otros portales

_PLANES = {
    "mls_starter": {
        "nombre": "STARTER",
        "precio": "€39/mes",
        "fincas": 5,
        "reservas": False,
        "descripcion": "Hasta 5 fincas activas. Acceso al mercado MLS para colaborar.",
        "color": "#4A90D9",
    },
    "mls_agency": {
        "nombre": "AGENCY",
        "precio": "€99/mes",
        "fincas": 20,
        "reservas": True,
        "descripcion": "Hasta 20 fincas. Reservas de colaboración (€200). Panel avanzado.",
        "color": "#F5A623",
    },
    "mls_enterprise": {
        "nombre": "PRO",
        "precio": "€199/mes",
        "fincas": 50,
        "reservas": True,
        "descripcion": "Hasta 50 fincas. Todas las funcionalidades. Soporte prioritario.",
        "color": "#1B2A6B",
    },
}


# ── Helpers de sesión ─────────────────────────────────────────────────────────

def _get_inmo() -> dict | None:
    """Devuelve el dict de la inmobiliaria en sesión, o None."""
    inmo = st.session_state.get(_SESSION_KEY)
    if inmo is None:
        return None
    # Refresca desde DB para tener datos actualizados (plan, activa, firma_hash…)
    try:
        conn = _db.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM inmobiliarias WHERE id = ?", (inmo["id"],)
            ).fetchone()
            if row:
                refreshed = dict(row)
                st.session_state[_SESSION_KEY] = refreshed
                return refreshed
        finally:
            conn.close()
    except Exception:
        pass
    return inmo


def _login_inmo(inmo_dict: dict) -> None:
    st.session_state[_SESSION_KEY] = inmo_dict


def _logout_inmo() -> None:
    st.session_state.pop(_SESSION_KEY, None)


def _estado_inmo(inmo: dict) -> str:
    """
    Devuelve el estado del flujo para la inmobiliaria autenticada:
      espera_aprobacion → sin_plan → firma_pendiente → operativo
    Trial activo sustituye al plan de pago para pasar de sin_plan a firma_pendiente.
    """
    from datetime import datetime, timezone
    if not inmo.get("activa"):
        return "espera_aprobacion"
    if not inmo.get("plan_activo"):
        _trial_ok = False
        if inmo.get("trial_active") and inmo.get("trial_start_date"):
            try:
                _start = datetime.fromisoformat(inmo["trial_start_date"])
                if _start.tzinfo is None:
                    _start = _start.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - _start).days <= 30:
                    _trial_ok = True
            except Exception:
                pass
        if not _trial_ok:
            return "sin_plan"
    if not inmo.get("firma_hash"):
        return "firma_pendiente"
    return "operativo"


# ── Handler ?mls_pago=ok ──────────────────────────────────────────────────────

def _handle_pago_ok(inmo: dict) -> None:
    """
    Llamado al inicio de main() cuando ?mls_pago=ok está en la URL.
    Verifica el pago con Stripe y activa plan_activo en DB.
    """
    session_id = st.query_params.get("mls_stripe_session", "")
    if not session_id:
        # Sin session_id no podemos verificar — limpiamos param y continuamos
        try:
            del st.query_params["mls_pago"]
        except Exception:
            pass
        return

    try:
        from modules.stripe_utils import verify_session
        sess = verify_session(session_id)
        paid = getattr(sess, "payment_status", "") == "paid"
    except Exception:
        paid = False

    if paid:
        # Detectar el plan desde metadata o amount_total
        plan_key = _detectar_plan_desde_session(sess)
        if plan_key:
            conn = _db.get_conn()
            try:
                conn.execute(
                    """UPDATE inmobiliarias
                          SET plan = ?, plan_activo = 1, stripe_session_id = ?
                        WHERE id = ?""",
                    (plan_key, session_id, inmo["id"]),
                )
                conn.commit()
                # Refrescar sesión
                row = conn.execute(
                    "SELECT * FROM inmobiliarias WHERE id = ?", (inmo["id"],)
                ).fetchone()
                if row:
                    st.session_state[_SESSION_KEY] = dict(row)
                try:
                    _inmo_data = dict(row) if row else inmo
                    mls_notificaciones.notif_pago_suscripcion(
                        nombre=_inmo_data.get("nombre_empresa", ""),
                        email=_inmo_data.get("email", ""),
                        plan=plan_key,
                        importe_eur=0.0,
                    )
                except Exception:
                    pass
            finally:
                conn.close()
            st.success("✅ Pago confirmado. Tu plan MLS está activo.")
        else:
            st.warning("Pago recibido pero no se pudo identificar el plan. Contacta soporte.")
    else:
        st.error("El pago no se completó. Inténtalo de nuevo.")

    # Limpiar params de URL
    for key in ("mls_pago", "mls_stripe_session"):
        try:
            del st.query_params[key]
        except Exception:
            pass


def _detectar_plan_desde_session(sess) -> str | None:
    """Detecta el product_key del plan a partir de la sesión de Stripe."""
    try:
        meta = getattr(sess, "metadata", {}) or {}
        if "mls_plan" in meta:
            return meta["mls_plan"]
        # Fallback por importe total (en céntimos)
        total = getattr(sess, "amount_total", 0) or 0
        if total <= 5000:
            return "mls_starter"
        elif total <= 15000:
            return "mls_agency"
        else:
            return "mls_enterprise"
    except Exception:
        return None


# ── UI: Login / Registro ──────────────────────────────────────────────────────

def ui_login_registro() -> None:
    # Botón volver al mapa/home (útil si un visitante llega aquí por error)
    if st.button("← Volver al marketplace", key="mls_login_volver"):
        st.session_state["selected_page"] = "🏠 Inicio / Marketplace"
        try:
            del st.query_params["page"]
        except Exception:
            pass
        st.stop()
        st.rerun()

    st.markdown("## 🏢 ArchiRapid MLS — Portal Inmobiliario")
    st.caption("Bolsa de colaboración entre inmobiliarias. Listantes + colaboradoras.")

    # ── Banner 30 días Free Trial ─────────────────────────────────────────────
    st.markdown("""
<div style="background:linear-gradient(135deg,#1e3a5f,#0f2d4a);border-radius:12px;
            padding:16px 20px;margin:12px 0 18px 0;border-left:4px solid #F5A623;">
  <div style="color:#F5A623;font-weight:700;font-size:1em;margin-bottom:6px;">
    🎁 30 días de acceso gratuito — sin tarjeta, sin compromiso
  </div>
  <div style="color:#e2e8f0;font-size:0.85em;line-height:1.6;">
    Regístrate y accede a la red MLS completa durante 30 días. Publica fincas, explora el mercado colaborativo y cierra operaciones con otras inmobiliarias.<br><br>
    <b style="color:#ffffff;">¿Cómo funciona?</b><br>
    1. Rellena el formulario de registro (pestaña <b>Registrarse</b>)<br>
    2. ArchiRapid revisa y aprueba tu solicitud en <b>24–48h hábiles</b> — recibirás un email<br>
    3. Accede con tu email y contraseña. Tu trial de 30 días empieza al ser aprobada<br>
    4. Cuando quieras continuar, elige tu plan: <b>Starter 39€/mes · Agency 99€ · PRO 199€</b>
  </div>
</div>
""", unsafe_allow_html=True)

    tab_login, tab_registro = st.tabs(["🔑 Acceder", "📝 Registrarse"])

    # ── Tab Login ─────────────────────────────────────────────────────────────
    with tab_login:
        st.markdown("### Acceso a tu cuenta MLS")
        with st.form("mls_login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="tu@inmobiliaria.com").strip().lower()
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Completa email y contraseña.")
            else:
                conn = _db.get_conn()
                row = conn.execute(
                    "SELECT * FROM inmobiliarias WHERE email_login = ? OR email = ?",
                    (email, email),
                ).fetchone()
                if row and check_password_hash(row["password_hash"], password):
                    _login_inmo(dict(row))
                    st.success(f"Bienvenido, {row['nombre']}.")
                    # Post-login: si venía de pin naranja del mapa, abrir esa finca
                    _pending_finca = st.session_state.pop("mls_goto_finca_pending", None)
                    if _pending_finca:
                        st.session_state["mls_ficha_id"] = _pending_finca
                        st.session_state["mls_vista"]    = "ficha"
                    st.rerun()
                else:
                    st.error("Email o contraseña incorrectos.")

        st.markdown("---")
        if st.button("¿Olvidaste tu contraseña?", key="mls_goto_forgot"):
            st.session_state["selected_page"] = "_mls_forgot_password"
            st.query_params.clear()
            st.rerun()

    # ── Tab Registro ──────────────────────────────────────────────────────────
    with tab_registro:
        st.markdown("### Alta de nueva inmobiliaria")
        st.info(
            "El registro requiere aprobación manual de ArchiRapid (24-48h hábiles). "
            "Recibirás un email de confirmación. Los campos marcados con * son obligatorios."
        )

        with st.form("mls_registro_form", clear_on_submit=False):

            # ── SECCIÓN 1: Datos de la empresa ─────────────────────────────
            st.subheader("1. Datos de la empresa")
            c1, c2 = st.columns(2)
            with c1:
                nombre_sociedad  = st.text_input("Nombre legal de la sociedad *", placeholder="Inmobiliaria Ejemplo S.L.")
                nombre_comercial = st.text_input("Nombre comercial / marca *", placeholder="InmoEjemplo")
                cif              = st.text_input("CIF *", placeholder="B12345678").strip().upper()
                email_corp       = st.text_input("Email corporativo *", placeholder="info@inmobiliaria.com")
            with c2:
                telefono_1 = st.text_input("Teléfono principal *", placeholder="+34 600 000 000")
                telefono_2 = st.text_input("Teléfono secundario (opcional)", placeholder="+34 911 000 000")
                telegram_c = st.text_input("Telegram @usuario (opcional)", placeholder="@miinmo")
                web        = st.text_input("Web corporativa (opcional)", placeholder="https://www.miinmo.com")

            st.divider()

            # ── SECCIÓN 2: Dirección ────────────────────────────────────────
            st.subheader("2. Dirección de la oficina")
            ca, cb, cc = st.columns([3, 2, 1])
            with ca:
                direccion = st.text_input("Calle y número *", placeholder="Calle Mayor, 1")
                localidad = st.text_input("Localidad *", placeholder="Madrid")
            with cb:
                provincia     = st.text_input("Provincia *", placeholder="Madrid")
                codigo_postal = st.text_input("Código postal *", placeholder="28001")
            with cc:
                pais = st.selectbox("País", ["España", "Portugal", "Andorra", "Otro"], index=0)

            st.divider()

            # ── SECCIÓN 3: Persona de contacto responsable ──────────────────
            st.subheader("3. Persona de contacto responsable")
            st.caption("Quien responde siempre las comunicaciones de ArchiRapid MLS.")
            cd, ce = st.columns(2)
            with cd:
                contacto_nombre   = st.text_input("Nombre completo *", placeholder="Ana García López")
                contacto_cargo    = st.text_input("Cargo (opcional)", placeholder="Directora Comercial")
                contacto_email    = st.text_input("Email directo *", placeholder="ana@inmobiliaria.com")
            with ce:
                contacto_telefono = st.text_input("Teléfono directo *", placeholder="+34 600 111 222")
                contacto_telegram = st.text_input("Telegram personal (opcional)", placeholder="@ana_garcia")

            st.divider()

            # ── SECCIÓN 4: Datos de facturación ────────────────────────────
            st.subheader("4. Datos de facturación")
            st.caption("Necesarios para procesar comisiones. Puede coincidir con los datos de empresa.")
            cf, cg = st.columns(2)
            with cf:
                factura_rs  = st.text_input("Razón social facturación *", placeholder="Igual que nombre legal si coincide")
                factura_cif = st.text_input("CIF facturación *", placeholder="Puede ser el mismo CIF")
                factura_dir = st.text_input("Dirección fiscal *", placeholder="Puede ser la misma dirección")
                factura_email = st.text_input("Email para facturas *", placeholder="facturas@inmobiliaria.com")
            with cg:
                iban          = st.text_input("IBAN bancario *", placeholder="ES9121000418450200051332",
                                              help="Formato ES + 22 dígitos. Para recibir comisiones.")
                banco_nombre  = st.text_input("Nombre del banco (opcional)", placeholder="Banco Santander")
                banco_titular = st.text_input("Titular de la cuenta *", placeholder="Inmobiliaria Ejemplo S.L.")

            st.divider()

            # ── SECCIÓN 5: Acceso al portal ─────────────────────────────────
            st.subheader("5. Acceso al portal MLS")
            ch, ci = st.columns(2)
            with ch:
                email_login = st.text_input(
                    "Email de acceso *",
                    placeholder="Puede ser el mismo que el corporativo",
                    help="Este email se usará para iniciar sesión en el portal."
                )
            with ci:
                pwd1 = st.text_input("Contraseña * (mín. 8 caracteres)", type="password", key="mls_pwd1")
                pwd2 = st.text_input("Confirmar contraseña *", type="password", key="mls_pwd2")

            st.divider()

            # ── Acuerdo de Colaboración MLS con firma digital ──
            st.markdown("---")
            st.markdown("#### 📋 Acuerdo de Colaboración MLS")
            st.caption(
                "Lee el acuerdo completo antes de firmar. "
                "La firma es electrónica (eIDAS Art. 25) con validez legal plena."
            )
            with st.expander("📄 Leer Acuerdo de Colaboración MLS completo"):
                from modules.mls.mls_firma import TEXTO_ACUERDO_MLS
                st.text_area(
                    "Acuerdo de Colaboración",
                    value=TEXTO_ACUERDO_MLS,
                    height=300,
                    disabled=True,
                    key="mls_reg_acuerdo_texto"
                )
            acuerdo_leido = st.checkbox(
                "He leído íntegramente el Acuerdo de Colaboración MLS "
                "y lo acepto en su totalidad (firma electrónica eIDAS Art. 25)",
                key="mls_reg_acuerdo_check"
            )

            aceptar = st.checkbox(
                "Acepto la política de privacidad (RGPD) y confirmo "
                "que los datos facilitados son verídicos.",
                key="mls_reg_aceptar"
            )
            enviado = st.form_submit_button("📩 Solicitar alta", use_container_width=True, type="primary")

        if enviado:
            # ── Validaciones ─────────────────────────────────────────────
            _IBAN_RE = re.compile(r"^ES\d{22}$")
            errores = []
            if not nombre_sociedad.strip():
                errores.append("Nombre legal de la sociedad obligatorio.")
            if not nombre_comercial.strip():
                errores.append("Nombre comercial obligatorio.")
            if not _CIF_RE.match(cif):
                errores.append("CIF no válido (formato: letra + 8 dígitos, ej. A08663619).")
            if not email_corp.strip() or "@" not in email_corp:
                errores.append("Email corporativo no válido.")
            if not telefono_1.strip():
                errores.append("Teléfono principal obligatorio.")
            if not direccion.strip():
                errores.append("Dirección obligatoria.")
            if not localidad.strip():
                errores.append("Localidad obligatoria.")
            if not provincia.strip():
                errores.append("Provincia obligatoria.")
            if not codigo_postal.strip():
                errores.append("Código postal obligatorio.")
            if not contacto_nombre.strip():
                errores.append("Nombre del contacto responsable obligatorio.")
            if not contacto_email.strip() or "@" not in contacto_email:
                errores.append("Email directo del contacto no válido.")
            if not contacto_telefono.strip():
                errores.append("Teléfono del contacto obligatorio.")
            if not factura_rs.strip():
                errores.append("Razón social de facturación obligatoria.")
            if not factura_cif.strip():
                errores.append("CIF de facturación obligatorio.")
            if not factura_dir.strip():
                errores.append("Dirección fiscal obligatoria.")
            if not factura_email.strip() or "@" not in factura_email:
                errores.append("Email de facturas no válido.")
            iban_clean = iban.strip().upper().replace(" ", "")
            if iban_clean and not _IBAN_RE.match(iban_clean):
                errores.append("IBAN no válido. Debe ser ES seguido de 22 dígitos (sin espacios).")
            if iban_clean and not banco_titular.strip():
                errores.append("Si introduces IBAN, el titular de la cuenta es obligatorio.")
            if not email_login.strip() or "@" not in email_login:
                errores.append("Email de acceso no válido.")
            if len(pwd1.strip()) < 8:
                errores.append("La contraseña debe tener al menos 8 caracteres.")
            if pwd1.strip() != pwd2.strip():
                errores.append("Las contraseñas no coinciden.")
            if not aceptar:
                errores.append("Debes aceptar la política de privacidad.")
            if not acuerdo_leido:
                errores.append("Debes leer y aceptar el Acuerdo de Colaboración MLS.")

            if errores:
                for e in errores:
                    st.error(e)
            else:
                _reg_success = False
                try:
                    ip = _get_client_ip()
                    datos = {
                        "nombre":            nombre_comercial.strip(),
                        "nombre_sociedad":   nombre_sociedad.strip(),
                        "nombre_comercial":  nombre_comercial.strip(),
                        "cif":               cif,
                        "email":             email_corp.strip().lower(),
                        "password_hash":     generate_password_hash(pwd1.strip()),
                        "telefono":          telefono_1.strip(),
                        "telefono_secundario": telefono_2.strip() or None,
                        "telegram_contacto": telegram_c.strip() or None,
                        "web":               web.strip() or None,
                        "direccion":         direccion.strip(),
                        "localidad":         localidad.strip(),
                        "provincia":         provincia.strip(),
                        "codigo_postal":     codigo_postal.strip(),
                        "pais":              pais,
                        "contacto_nombre":   contacto_nombre.strip(),
                        "contacto_cargo":    contacto_cargo.strip() or None,
                        "contacto_email":    contacto_email.strip().lower(),
                        "contacto_telefono": contacto_telefono.strip(),
                        "contacto_telegram": contacto_telegram.strip() or None,
                        "factura_razon_social": factura_rs.strip(),
                        "factura_cif":       factura_cif.strip().upper(),
                        "factura_direccion": factura_dir.strip(),
                        "factura_email":     factura_email.strip().lower(),
                        "iban":              iban_clean or None,
                        "banco_nombre":      banco_nombre.strip() or None,
                        "banco_titular":     banco_titular.strip() or None,
                        "email_login":       email_login.strip().lower(),
                        "ip_registro":       ip,
                    }
                    try:
                        inmo_id = mls_db.create_inmo(datos, ip=ip)
                    except Exception as _create_err:
                        st.error(f"❌ Error técnico en registro: {_create_err}")
                        inmo_id = None

                    if inmo_id:
                        # Firmar el acuerdo digitalmente con SHA-256
                        try:
                            from modules.mls import mls_firma as _mls_firma_reg
                            _firma_datos = _mls_firma_reg.firmar_acuerdo(
                                inmo_id=inmo_id,
                                cif=datos.get("cif", "").strip().upper(),
                                ip=ip or "unknown"
                            )
                            if _firma_datos and _firma_datos.get("firma_hash"):
                                mls_db.update_inmo_firma(
                                    inmo_id=inmo_id,
                                    firma_hash=_firma_datos["firma_hash"],
                                    firma_timestamp=_firma_datos["firma_timestamp"],
                                    doc_hash=_firma_datos.get("doc_hash", "")
                                )
                        except Exception as _firma_err:
                            pass  # No bloquear registro si falla la firma
                        # Notificar al admin
                        try:
                            mls_notificaciones.notif_nuevo_registro(
                                nombre=datos.get("nombre_comercial", datos.get("nombre", "")),
                                cif=datos.get("cif", ""),
                                email=datos.get("email", ""),
                                ip=ip,
                            )
                        except Exception:
                            pass
                        _reg_success = True
                    else:
                        if not st.session_state.get("_mls_create_error_shown"):
                            st.error("Error al guardar el registro. Inténtalo de nuevo.")
                except Exception as exc:
                    msg = str(exc)
                    if "UNIQUE" in msg and "cif" in msg.lower():
                        st.error("Ya existe una cuenta con ese CIF.")
                    elif "UNIQUE" in msg and "email" in msg.lower():
                        st.error("Ya existe una cuenta con ese email.")
                    else:
                        st.error(f"Error al registrar: {msg}")

                if _reg_success:
                    # Redirect robusto en Cloud/Supabase: no depender de lecturas SQL locales tras insertar por REST
                    _now_iso = datetime.now(timezone.utc).isoformat()

                    _inmo_sesion = {
                        "id": inmo_id,
                        "nombre": datos.get("nombre_comercial") or datos.get("nombre") or "Inmobiliaria",
                        "nombre_sociedad": datos.get("nombre_sociedad"),
                        "nombre_comercial": datos.get("nombre_comercial"),
                        "cif": datos.get("cif"),
                        "email": datos.get("email"),
                        "email_login": datos.get("email_login"),

                        # Campos que usa _estado_inmo()
                        "activa": False,          # aprobación manual
                        "plan_activo": False,
                        "trial_active": True,
                        "trial_start_date": _now_iso,
                        "firma_hash": "",         # activa=False manda a espera_aprobacion
                    }

                    st.session_state[_SESSION_KEY] = _inmo_sesion
                    # Copia de seguridad: clave que ningún guard de app.py toca
                    st.session_state["_mls_registro_sesion"] = _inmo_sesion
                    st.session_state["_mls_registro_ok"] = True

                    # Navegación programática al portal MLS
                    st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
                    st.session_state["_nav_programmatic"] = True

                    st.rerun()


def _get_client_ip() -> str:
    """Intenta obtener la IP del cliente desde headers de Streamlit."""
    try:
        headers = st.context.headers
        return (
            headers.get("X-Forwarded-For", "")
            or headers.get("X-Real-Ip", "")
            or "unknown"
        )
    except Exception:
        pass
    return "unknown"


# ── UI: Espera aprobación ─────────────────────────────────────────────────────

def ui_espera_aprobacion(inmo: dict) -> None:
    st.markdown("## ⏳ Cuenta pendiente de aprobación")
    st.info(
        f"**{inmo['nombre']}**, tu solicitud de acceso a ArchiRapid MLS está siendo revisada.\n\n"
        "Nuestro equipo la aprobará en **24-48 horas hábiles**. "
        "Recibirás un email en cuanto esté lista."
    )
    st.markdown(f"**CIF registrado:** `{inmo['cif']}`")
    st.markdown(f"**Email de contacto:** `{inmo['email']}`")
    st.caption("Si crees que hay un error, escríbenos a hola@archirapid.com")

    if st.button("🔄 Verificar estado", use_container_width=True):
        st.rerun()

    if st.button("Cerrar sesión", type="secondary"):
        _logout_inmo()
        st.rerun()


# ── UI: Planes de suscripción ─────────────────────────────────────────────────

def ui_planes(inmo: dict) -> None:
    st.markdown("""
    <style>
    .planes-header { text-align: center; padding: 2rem 0 1rem 0; }
    .planes-header h1 { font-size: 2.2rem; font-weight: 800; color: #0D1B3E; margin-bottom: 0.3rem; }
    .planes-header p { color: #666; font-size: 1.05rem; margin-bottom: 0; }
    .plan-card {
        background: white; border-radius: 16px; padding: 2rem 1.5rem;
        border: 2px solid #E8E8E8; text-align: center; position: relative; height: 100%;
    }
    .plan-card.featured { border-color: #E8612A; box-shadow: 0 8px 32px rgba(232,97,42,0.18); transform: translateY(-6px); }
    .plan-badge {
        position: absolute; top: -14px; left: 50%; transform: translateX(-50%);
        background: #E8612A; color: white; font-size: 0.75rem; font-weight: 700;
        padding: 4px 18px; border-radius: 20px; letter-spacing: 0.05em; white-space: nowrap;
    }
    .plan-name { font-size: 1rem; font-weight: 700; color: #0D1B3E; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem; }
    .plan-price { font-size: 3rem; font-weight: 900; color: #0D1B3E; line-height: 1; margin: 0.5rem 0 0.2rem 0; }
    .plan-price span { font-size: 1.1rem; font-weight: 500; color: #888; }
    .plan-fincas { display: inline-block; background: #F0F4FF; color: #0D1B3E; font-size: 0.85rem; font-weight: 600; padding: 4px 14px; border-radius: 20px; margin: 0.8rem 0; }
    .plan-card.featured .plan-fincas { background: #FEF0E8; color: #E8612A; }
    .plan-feature { font-size: 0.88rem; color: #444; padding: 0.35rem 0; border-bottom: 1px solid #F5F5F5; text-align: left; }
    .plan-feature:last-child { border-bottom: none; }
    .plan-feature::before { content: "✓ "; color: #2ecc71; font-weight: 700; }
    .plan-card.featured .plan-feature::before { color: #E8612A; }
    .plan-ideal { font-size: 0.8rem; color: #999; margin-top: 1rem; font-style: italic; }
    .garantia-box { background: #F8FFF8; border: 1px solid #2ecc71; border-radius: 12px; padding: 1.2rem 1.5rem; text-align: center; margin: 2rem 0 1rem 0; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="planes-header">
        <h1>Elige tu plan MLS</h1>
        <p>Sin permanencia · Sin letra pequeña · Cancela cuando quieras<br>
        <strong>30 días gratuitos para que lo compruebes tú mismo</strong></p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
        <div class="plan-card">
            <div class="plan-name">Starter</div>
            <div class="plan-price">39€<span>/mes</span></div>
            <div class="plan-fincas">Hasta 5 fincas activas</div>
            <div class="plan-feature">Acceso completo al Mercado MLS</div>
            <div class="plan-feature">Validación catastral IA</div>
            <div class="plan-feature">Proyectos compatibles por finca</div>
            <div class="plan-feature">Ficha pública sin login</div>
            <div class="plan-feature">Soporte por email</div>
            <div class="plan-ideal">Ideal para autónomos y agencias pequeñas</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Empezar con Starter", key="btn_plan_starter", use_container_width=True):
            _iniciar_checkout_plan("mls_starter", inmo)

    with col2:
        st.markdown("""
        <div class="plan-card featured">
            <div class="plan-badge">⭐ MÁS POPULAR</div>
            <div class="plan-name">Agency</div>
            <div class="plan-price">99€<span>/mes</span></div>
            <div class="plan-fincas">Hasta 20 fincas activas</div>
            <div class="plan-feature">Todo lo de Starter</div>
            <div class="plan-feature">Reservas de colaboración 72h (€200)</div>
            <div class="plan-feature">Firma digital del acuerdo MLS</div>
            <div class="plan-feature">Panel de estadísticas avanzado</div>
            <div class="plan-feature">Soporte prioritario</div>
            <div class="plan-ideal">Ideal para agencias con cartera activa de suelo</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Empezar con Agency", key="btn_plan_agency", use_container_width=True, type="primary"):
            _iniciar_checkout_plan("mls_agency", inmo)

    with col3:
        st.markdown("""
        <div class="plan-card">
            <div class="plan-name">Pro</div>
            <div class="plan-price">199€<span>/mes</span></div>
            <div class="plan-fincas">Hasta 50 fincas activas</div>
            <div class="plan-feature">Todo lo de Agency</div>
            <div class="plan-feature">Gestión de múltiples agentes</div>
            <div class="plan-feature">Redes y franquicias</div>
            <div class="plan-feature">Informes de mercado mensuales</div>
            <div class="plan-feature">Soporte telefónico directo</div>
            <div class="plan-ideal">Ideal para agencias grandes y redes</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Empezar con Pro", key="btn_plan_pro", use_container_width=True):
            _iniciar_checkout_plan("mls_enterprise", inmo)

    st.markdown("""
    <div class="garantia-box">
        🎁 <strong>30 días gratis al registrarte</strong> — sin tarjeta, sin compromiso.<br>
        <span style="color:#666;font-size:0.9rem">
        Si en 30 días no has cerrado ninguna colaboración, te ayudamos a entender por qué.
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align:center;margin-top:1.5rem;'>
        <p style='color:#888;font-size:0.85rem;'>
        ¿Tienes una red o franquicia con más de 50 fincas?
        <a href='mailto:hola@archirapid.com' style='color:#E8612A;font-weight:600;'>
        Escríbenos y diseñamos un plan a medida.</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.caption(
        "IVA no incluido. Pago mensual. Cancela cuando quieras desde tu área de cliente. "
        "ArchiRapid cobra el 1% fijo sobre el precio final de cada operación cerrada."
    )

    if st.button("Cerrar sesión", type="secondary"):
        _logout_inmo()
        st.rerun()


def _iniciar_checkout_plan(plan_key: str, inmo: dict) -> None:
    """Lanza Stripe Checkout para el plan seleccionado."""
    try:
        from modules.stripe_utils import create_checkout_session

        # URL base absoluta — Stripe exige URLs completas
        try:
            headers = st.context.headers if hasattr(st, "context") else {}
            host = headers.get("host", "archirapid.streamlit.app")
            proto = "https" if "localhost" not in host else "http"
            base_url = f"{proto}://{host}"
        except Exception:
            base_url = "https://archirapid.streamlit.app"
        success_url = f"{base_url}/?page=MLS&mls_pago=ok&mls_stripe_session={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/?page=MLS"

        url, session_id = create_checkout_session(
            product_keys=[plan_key],
            project_id=inmo["id"],
            client_email=inmo["email"],
            success_url=success_url,
            cancel_url=cancel_url,
            extra_quantities=None,
        )
        # Guardar session_id en DB para verificación post-retorno
        conn = _db.get_conn()
        try:
            conn.execute(
                "UPDATE inmobiliarias SET stripe_session_id = ? WHERE id = ?",
                (session_id, inmo["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        import streamlit.components.v1 as _stc_mls
        _stc_mls.html(f'<script>window.top.location.href="{url}";</script>', height=0)
        st.link_button("💳 Ir al pago →", url, type="primary", use_container_width=True)

    except Exception as exc:
        st.error(f"Error al iniciar pago Stripe: {type(exc).__name__}: {exc}")


# ── UI: Portal operativo ──────────────────────────────────────────────────────

def _ui_contacto_archirapid_btn(inmo: dict) -> None:
    """Botón/formulario rápido 'Contactar con ArchiRapid' — visible en todo el portal."""
    nombre_comercial = inmo.get("nombre_comercial") or inmo.get("nombre", "")
    with st.expander("💬 Contactar con ArchiRapid", expanded=False):
        with st.form("mls_contacto_archirapid_form", clear_on_submit=True):
            msg = st.text_area(
                "Tu mensaje",
                placeholder="Escríbenos tu consulta, incidencia o sugerencia…",
                height=100,
            )
            ref = st.text_input("Referencia (opcional)", placeholder="AR-2026-00001 u otra referencia")
            enviado = st.form_submit_button("Enviar consulta", use_container_width=True)
        if enviado:
            if not msg.strip():
                st.warning("Escribe un mensaje antes de enviar.")
            else:
                try:
                    from modules.mls import mls_notificaciones as _notif
                    import json
                    from modules.mls.mls_db import create_notificacion
                    payload = json.dumps({
                        "inmo_id":   inmo["id"],
                        "nombre":    nombre_comercial,
                        "email":     inmo.get("email", ""),
                        "referencia": ref.strip() or None,
                        "mensaje":   msg.strip(),
                    }, ensure_ascii=False)
                    create_notificacion("archirapid", "admin", "consulta_inmobiliaria", payload)
                    # Email a hola@archirapid.com
                    subject = f"Consulta MLS — {nombre_comercial}" + (f" — {ref.strip()}" if ref.strip() else "")
                    try:
                        _notif._send_admin_email(subject, inmo, msg.strip(), ref.strip())
                    except Exception:
                        pass
                    st.success("✅ Mensaje enviado. Te responderemos en breve.")
                except Exception as exc:
                    st.error(f"Error al enviar: {exc}")


def _ui_soporte(inmo: dict) -> None:
    """Tab Soporte — historial de tickets + formulario nuevo ticket."""
    from uuid import uuid4

    inmo_id     = inmo["id"]
    inmo_nombre = inmo.get("nombre_comercial") or inmo.get("nombre", "")

    st.markdown("### 📞 Consultas y Soporte")
    st.caption(
        "Envíanos tu consulta, incidencia o sugerencia. "
        "Te responderemos en menos de 24 horas hábiles."
    )

    # ── Formulario nuevo ticket ────────────────────────────────────────────────
    with st.expander("✉️ Enviar nueva consulta", expanded=True):
        with st.form("mls_sop_nuevo_ticket_form", clear_on_submit=True):
            asunto  = st.text_input(
                "Asunto *",
                placeholder="Resume tu consulta en pocas palabras",
                max_chars=100,
                key="mls_sop_asunto",
            )
            mensaje = st.text_area(
                "Mensaje *",
                placeholder="Detalla tu consulta, incidencia o sugerencia…",
                max_chars=500,
                height=130,
                key="mls_sop_mensaje",
            )
            enviar = st.form_submit_button("Enviar consulta", use_container_width=True, type="primary")

        if enviar:
            _asunto  = asunto.strip()
            _mensaje = mensaje.strip()
            _errores = []
            if not _asunto:
                _errores.append("El asunto es obligatorio.")
            if not _mensaje:
                _errores.append("El mensaje es obligatorio.")
            if _errores:
                for _e in _errores:
                    st.error(_e)
            else:
                _ok = False
                conn = _db.get_conn()
                try:
                    from datetime import datetime, timezone as _tz
                    _now = datetime.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                    _tid = str(uuid4())
                    conn.execute(
                        """INSERT INTO tickets_soporte
                               (id, inmo_id, inmo_nombre,
                                usuario_tipo, usuario_id, usuario_nombre, usuario_email,
                                asunto, mensaje,
                                lola_respuesta, admin_respuesta, estado, created_at, respondido_at)
                           VALUES (?, ?, ?, 'inmo', ?, ?, ?, ?, ?, NULL, NULL, 'pendiente', ?, NULL)""",
                        (_tid, inmo_id, inmo_nombre,
                         inmo_id, inmo_nombre, inmo.get("email", ""),
                         _asunto, _mensaje, _now),
                    )
                    conn.commit()
                    _ok = True
                except Exception as _exc:
                    st.error(f"Error al guardar el ticket: {_exc}")
                finally:
                    conn.close()
                if _ok:
                    # Notificar al admin por Telegram
                    try:
                        from modules.marketplace.email_notify import _send as _tg_send
                        _tg_send(
                            f"📞 <b>Nuevo ticket soporte MLS</b>\n"
                            f"Inmo: {inmo_nombre}\n"
                            f"Asunto: {_asunto}\n"
                            f"Mensaje: {_mensaje[:200]}"
                        )
                    except Exception:
                        pass
                    st.success("Consulta enviada. Te responderemos en menos de 24h.")

    st.divider()

    # ── Historial de tickets ───────────────────────────────────────────────────
    st.markdown("#### Mis consultas anteriores")

    _tickets = []
    conn = _db.get_conn()
    try:
        _rows = conn.execute(
            """SELECT id, asunto, mensaje, admin_respuesta, estado, created_at, respondido_at
                 FROM tickets_soporte
                WHERE usuario_id = ? AND usuario_tipo = 'inmo'
                ORDER BY created_at DESC""",
            (inmo_id,),
        ).fetchall()
        _tickets = [dict(r) for r in _rows]
    except Exception as _exc:
        st.warning(f"No se pudieron cargar los tickets: {_exc}")
    finally:
        conn.close()

    if not _tickets:
        st.info("No tienes ninguna consulta enviada todavía.")
        return

    _BADGE = {
        "pendiente":  "🔴 Pendiente",
        "respondido": "✅ Respondido",
        "cerrado":    "⚫ Cerrado",
    }

    for _t in _tickets:
        _estado_label = _BADGE.get(_t.get("estado", "pendiente"), _t.get("estado", ""))
        _fecha        = (_t.get("created_at") or "")[:10]
        _titulo_exp   = f"{_estado_label} — {_t['asunto']} ({_fecha})"
        with st.expander(_titulo_exp, expanded=False):
            st.markdown(f"**Tu consulta:**")
            st.write(_t["mensaje"])
            if _t.get("admin_respuesta"):
                st.markdown("---")
                st.markdown("**Respuesta de ArchiRapid:**")
                st.info(_t["admin_respuesta"])
                if _t.get("respondido_at"):
                    st.caption(f"Respondido el {str(_t['respondido_at'])[:10]}")
            else:
                st.caption("Pendiente de respuesta.")


def ui_portal_operativo(inmo: dict) -> None:
    """Portal completo — 9 tabs para inmobiliaria con plan activo y firma."""
    # ── Banner modo demo ──────────────────────────────────────────────────────
    if st.session_state.get("mls_demo_mode"):
        st.markdown(
            "<div style='background:linear-gradient(90deg,#F59E0B,#EF4444);"
            "border-radius:8px;padding:8px 16px;color:white;font-weight:700;"
            "font-size:0.88em;margin-bottom:8px;'>"
            "⚡ Modo Demo — Estás explorando ArchiRapid MLS como visitante. "
            "Los datos son de demostración. "
            "<a href='/?seccion=mls' target='_self' "
            "style='color:white;text-decoration:underline;'>Registrar mi inmobiliaria →</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Banners de trial ──────────────────────────────────────────────────────
    _trial_status = {}
    try:
        from modules.mls.mls_db import check_trial_status as _check_trial
        _trial_status = _check_trial(inmo["id"])
    except Exception:
        pass

    if _trial_status.get("active"):
        _days_rem = _trial_status["days_remaining"]
        _dias_label = "día" if _days_rem == 1 else "días"
        st.markdown(
            f"<div style='background:linear-gradient(90deg,#16A34A,#22C55E);"
            f"border-radius:8px;padding:10px 18px;color:white;font-weight:600;"
            f"font-size:0.9em;margin-bottom:6px;'>"
            f"🎁 Trial gratuito activo &mdash; "
            f"<b>{_days_rem} {_dias_label} restantes</b>"
            f" | Explora el portal y prepara tus fincas"
            f"</div>"
            f"<div style='background:#f0fdf4;border:1px solid #86efac;border-radius:6px;"
            f"padding:8px 14px;font-size:0.82em;color:#166534;margin-bottom:10px;'>"
            f"⚠️ <b>Durante el trial</b> puedes usar todas las herramientas del portal, "
            f"pero las fincas no se publican en el Mercado MLS hasta que actives un plan de pago. "
            f"Elige tu plan antes de que expire para empezar a operar."
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("Ver planes de pago", key="mls_trial_ver_planes"):
            st.session_state["mls_ir_a_planes"] = True
            st.rerun()

    elif _trial_status.get("expired") and not _trial_status.get("on_paid_plan"):
        st.markdown(
            "<div style='background:linear-gradient(90deg,#DC2626,#EF4444);"
            "border-radius:8px;padding:12px 18px;color:white;font-weight:700;"
            "font-size:0.95em;margin-bottom:12px;'>"
            "Tu trial de 30 dias ha expirado. "
            "Elige un plan para seguir operando en la red MLS."
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Elegir plan ahora", key="mls_expired_ver_planes", type="primary"):
            st.session_state["mls_ir_a_planes"] = True
            st.rerun()
        st.warning(
            "Acceso limitado — puedes consultar tus datos pero no publicar "
            "ni reservar fincas hasta activar un plan.",
            icon="⏰",
        )

    _col_titulo, _col_logout = st.columns([5, 1])
    with _col_titulo:
        st.markdown(
            f"### 🏢 Portal MLS — {inmo['nombre']} "
            f"<span style='font-size:0.75rem;color:#888;'>"
            f"Plan: **{inmo.get('plan','?').upper()}**</span>",
            unsafe_allow_html=True,
        )
    with _col_logout:
        if st.button("🚪 Salir", key="mls_header_logout", help="Cerrar sesión MLS"):
            st.session_state.pop(_SESSION_KEY, None)
            st.session_state.pop("selected_page", None)
            st.query_params.clear()
            st.rerun()
    # ── Vista directa desde pin del mapa (o navegación interna):
    #    ficha / reservar / contacto → pantalla completa sin tabs
    #    mercado → pantalla completa sin tabs si el usuario vino por pin
    _vista_actual  = st.session_state.get("mls_vista", "mercado")
    _vino_por_pin  = bool(st.session_state.get("_mls_goto_active"))
    _bypass_tabs   = (_vista_actual in ("ficha", "reservar", "contacto")
                      or (_vino_por_pin and _vista_actual == "mercado"))

    if _bypass_tabs:
        if st.button("← Volver al portal completo", key="mls_direct_back"):
            st.session_state.pop("mls_ficha_id", None)
            st.session_state.pop("mls_reservar_finca", None)
            st.session_state.pop("mls_contacto_finca", None)
            st.session_state["_mls_goto_active"] = False  # desactiva bypass, NO borrar _mls_goto_last
            st.session_state["mls_vista"] = "mercado"
            st.rerun()
        try:
            from modules.mls import mls_mercado as _mm
            _mm.main(inmo)
        except Exception as _exc:
            st.error(f"Error en vista MLS: {_exc}")
        return

    # Botón de contacto siempre visible en el portal
    _ui_contacto_archirapid_btn(inmo)

    # ── Instrucciones / bienvenida ─────────────────────────────────────────────
    with st.expander("ℹ️ Guía rápida del portal MLS", expanded=False):
        st.markdown(
            """
**Bienvenido al Portal MLS de ArchiRapid** — aquí gestionas tu cartera y colaboras con otras inmobiliarias.

- **Mis Fincas** — revisa y gestiona tus propiedades publicadas. Usa el botón **➕ Publicar nueva finca** para añadir una nueva.
- **Mercado MLS** — explora fincas de otras inmobiliarias, reserva para tu cliente y solicita información.
- **Mis Reservas** — seguimiento de las reservas de colaboración que has iniciado.
- **Solicitudes** — peticiones de información que otras inmos han enviado sobre tus fincas.
- **Estadísticas** — visitas, contactos y actividad de tu cartera.
- **Mi Cuenta** — datos de empresa, plan activo y facturación.

💬 ¿Dudas? Pregunta a **Lola**, la asistente IA de ArchiRapid (botón inferior derecho), o escríbenos desde el botón *Contactar con ArchiRapid*.
"""
        )

    tab_fincas, tab_mercado, tab_reservas, tab_solicitudes, tab_proyectos, tab_prefab, tab_stats, tab_cuenta, tab_soporte = st.tabs([
        "🏠 Mis Fincas",
        "🌐 Mercado MLS",
        "📋 Mis Reservas",
        "📬 Solicitudes",
        "🏗️ Proyectos",
        "🏡 Prefabricadas",
        "📊 Estadísticas",
        "⚙️ Mi Cuenta",
        "📞 Soporte",
    ])

    with tab_fincas:
        try:
            from modules.mls import mls_fincas
            # Lista de fincas directamente — sin sub-tabs
            mls_fincas.ui_mis_fincas(inmo)
            st.divider()
            with st.expander("➕ Publicar nueva finca", expanded=False):
                mls_fincas.ui_subir_finca(inmo)
        except Exception as exc:
            st.error(f"Error en Mis Fincas: {exc}")

    with tab_mercado:
        try:
            from modules.mls import mls_mercado
            mls_mercado.main(inmo)
        except Exception as exc:
            st.error(f"Error en Mercado MLS: {exc}")

    with tab_reservas:
        try:
            from modules.mls import mls_mercado as _merc
            _merc.ui_mis_reservas_colaboradora(inmo)
        except Exception as exc:
            st.error(f"Error en Mis Reservas: {exc}")

    with tab_solicitudes:
        try:
            from modules.mls import mls_fincas as _f
            _f.ui_solicitudes_visita(inmo)
        except Exception as exc:
            st.error(f"Error en Solicitudes: {exc}")

    with tab_proyectos:
        try:
            from modules.mls import mls_proyectos
            mls_proyectos.ui_tab_proyectos(inmo)
        except Exception as exc:
            st.error(f"Error en Proyectos: {exc}")

    with tab_prefab:
        try:
            from modules.mls import mls_prefabricadas
            mls_prefabricadas.ui_tab_prefabricadas(inmo)
        except Exception as exc:
            st.error(f"Error en Prefabricadas: {exc}")

    with tab_stats:
        try:
            from modules.mls import mls_fincas as _f
            _f.ui_estadisticas(inmo)
        except Exception as exc:
            st.error(f"Error en Estadísticas: {exc}")

    with tab_cuenta:
        _ui_mi_cuenta(inmo)

    with tab_soporte:
        try:
            _ui_soporte(inmo)
        except Exception as exc:
            st.error(f"Error en Soporte: {exc}")


def _ui_mi_cuenta(inmo: dict) -> None:
    """Gestión de cuenta: datos, contraseña y logout."""
    st.markdown("### ⚙️ Mi Cuenta")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Inmobiliaria:** {inmo['nombre']}")
        st.markdown(f"**CIF:** `{inmo['cif']}`")
        st.markdown(f"**Email:** {inmo['email']}")
    with col2:
        st.markdown(f"**Teléfono:** {inmo.get('telefono', '—')}")
        st.markdown(f"**Web:** {inmo.get('web', '—') or '—'}")
        plan = inmo.get("plan", "ninguno").upper()
        activo = "✅ Activo" if inmo.get("plan_activo") else "❌ Inactivo"
        st.markdown(f"**Plan:** {plan} — {activo}")

    if inmo.get("firma_hash"):
        st.success(f"✅ Acuerdo MLS firmado — {inmo.get('firma_timestamp', '')[:10]}")

        # ── Descarga PDF + verificación SHA-256 ───────────────────────────────
        from modules.mls import mls_firma as _firma_mod
        pdf_bytes = _firma_mod.generar_pdf_certificado(inmo)
        if pdf_bytes:
            st.download_button(
                label="📄 Descargar Acuerdo Firmado (PDF)",
                data=pdf_bytes,
                file_name=f"acuerdo_mls_{inmo['cif']}.pdf",
                mime="application/pdf",
            )

        with st.expander("🔐 Certificado de integridad SHA-256"):
            st.markdown("**Hash del documento (SHA-256):**")
            _conn_cert = _db.get_conn()
            try:
                _row_cert = _conn_cert.execute(
                    "SELECT documento_hash, ip FROM firmas_colaboracion WHERE inmo_id = ? ORDER BY id DESC LIMIT 1",
                    (inmo["id"],),
                ).fetchone()
            finally:
                _conn_cert.close()
            _doc_hash = dict(_row_cert)["documento_hash"] if _row_cert else "—"
            _ip_cert  = dict(_row_cert)["ip"] if _row_cert else "—"
            st.code(_doc_hash, language=None)
            st.markdown("**Hash de la firma (SHA-256):**")
            st.code(inmo.get("firma_hash", "—"), language=None)
            st.markdown(f"**IP de firma:** `{_ip_cert}`")
            if st.button("✅ Verificar integridad", key="btn_verificar_firma"):
                resultado = _firma_mod.verificar_firma(
                    inmo.get("firma_hash", ""),
                    inmo.get("cif", ""),
                    _ip_cert,
                    inmo.get("firma_timestamp", ""),
                )
                if resultado:
                    st.success("Integridad verificada: los hashes coinciden con el texto del acuerdo.")
                else:
                    st.error("⚠️ Los hashes no coinciden. El acuerdo puede haber sido alterado.")

    st.divider()

    # Cambio de contraseña
    with st.expander("🔑 Cambiar contraseña"):
        with st.form("mls_cambio_pwd"):
            pwd_actual = st.text_input("Contraseña actual", type="password")
            pwd_nueva1 = st.text_input("Nueva contraseña", type="password")
            pwd_nueva2 = st.text_input("Repite nueva contraseña", type="password")
            if st.form_submit_button("Actualizar contraseña"):
                if not check_password_hash(inmo["password_hash"], pwd_actual):
                    st.error("La contraseña actual no es correcta.")
                elif len(pwd_nueva1) < 8:
                    st.error("La nueva contraseña debe tener al menos 8 caracteres.")
                elif pwd_nueva1 != pwd_nueva2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    conn = _db.get_conn()
                    try:
                        conn.execute(
                            "UPDATE inmobiliarias SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(pwd_nueva1), inmo["id"]),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    st.success("Contraseña actualizada correctamente.")

    st.divider()
    if st.button("🚪 Cerrar sesión", type="secondary"):
        _logout_inmo()
        st.rerun()


# ── Password reset MLS ────────────────────────────────────────────────────────

def _init_mls_reset_table() -> None:
    """Crea la tabla de tokens de reset si no existe (compartida con users)."""
    conn = _db.get_conn()
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


def _send_mls_reset_email(email: str, token: str) -> bool:
    """Envía email de reset vía Resend + notificación Telegram al admin."""
    import os, secrets as _sec
    try:
        import requests as _req
        try:
            import streamlit as _st
            key = str(_st.secrets.get("RESEND_API_KEY", "")).strip()
        except Exception:
            key = os.getenv("RESEND_API_KEY", "").strip()
        if not key:
            return False

        reset_url = f"https://archirapid.com/?mls_reset_token={token}"
        html = f"""<!DOCTYPE html>
<html><body style="background:#0D1B2A;font-family:Arial,sans-serif;margin:0;padding:32px;">
  <div style="max-width:520px;margin:0 auto;background:#162241;border-radius:16px;
              padding:32px;border:1px solid rgba(255,165,0,0.2);">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:1.3rem;font-weight:900;color:#F5A623;">🟠 ArchiRapid MLS</div>
      <div style="color:#94A3B8;font-size:13px;">Portal Inmobiliario</div>
    </div>
    <h2 style="color:#F8FAFC;font-size:1.1rem;margin-bottom:8px;">Restablecer contraseña</h2>
    <p style="color:#94A3B8;font-size:14px;line-height:1.7;">
      Hemos recibido una solicitud para restablecer la contraseña de
      <b style="color:#F8FAFC;">{email}</b>.<br>
      El enlace es válido durante <b style="color:#F8FAFC;">1 hora</b>.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_url}"
         style="background:#1a5276;color:#fff;text-decoration:none;padding:14px 32px;
                border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
        Restablecer contraseña
      </a>
    </div>
    <p style="color:#475569;font-size:12px;text-align:center;">
      Si no solicitaste este cambio, ignora este email.<br>
      © 2026 ArchiRapid · hola@archirapid.com
    </p>
  </div>
</body></html>"""

        resp = _req.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "from": "ArchiRapid MLS <noreply@archirapid.com>",
                "to": [email],
                "subject": "Restablecer contraseña — ArchiRapid MLS",
                "html": html,
            },
            timeout=10,
        )
        ok = resp.status_code in (200, 201)
    except Exception:
        ok = False

    # Notificación Telegram al admin siempre
    try:
        from modules.marketplace.email_notify import _send
        _send(f"🔑 <b>Reset contraseña MLS solicitado</b>\nEmail: {email}\nEmail enviado: {'✅' if ok else '❌'}")
    except Exception:
        pass
    return ok


def show_mls_forgot_password() -> None:
    """Paso 1: formulario solicitud reset contraseña MLS."""
    _init_mls_reset_table()

    if st.button("← Volver al portal MLS", key="mls_forgot_back"):
        st.session_state.pop("selected_page", None)
        st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
        st.query_params.clear()
        st.rerun()

    st.markdown("## 🔑 Recuperar contraseña MLS")
    st.markdown("Introduce tu email registrado y te enviaremos un enlace para crear una nueva contraseña.")

    with st.form("mls_forgot_form"):
        email = st.text_input("Email", placeholder="tu@inmobiliaria.com").strip().lower()
        submitted = st.form_submit_button("Enviar enlace de recuperación", type="primary",
                                          use_container_width=True)

    if submitted:
        if not email or "@" not in email:
            st.error("Introduce un email válido.")
            return

        import secrets
        from datetime import timedelta

        conn = _db.get_conn()
        row = conn.execute(
            "SELECT email_login FROM inmobiliarias WHERE email_login = ? OR email = ?",
            (email, email)
        ).fetchone()
        conn.close()

        if row:
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            conn = _db.get_conn()
            conn.execute("UPDATE password_reset_tokens SET used=1 WHERE email=?", (email,))
            conn.execute(
                "INSERT INTO password_reset_tokens (token,email,expires_at,used,created_at) VALUES (?,?,?,0,?)",
                (token, email, expires, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
            _send_mls_reset_email(email, token)

        # Mensaje genérico (no revelar si el email existe)
        st.success("Si ese email está registrado, recibirás un enlace en los próximos minutos. Revisa también la carpeta de spam.")


def show_mls_reset_password(token: str) -> None:
    """Paso 2: formulario nueva contraseña con token válido."""
    _init_mls_reset_table()

    conn = _db.get_conn()
    row = conn.execute(
        "SELECT email, expires_at, used FROM password_reset_tokens WHERE token=?", (token,)
    ).fetchone()
    conn.close()

    if not row:
        st.error("El enlace de recuperación no es válido.")
        if st.button("← Volver al portal MLS", key="mls_reset_invalid_back"):
            st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
            st.query_params.clear()
            st.rerun()
        return

    email, expires_at, used = row["email"], row["expires_at"], row["used"]

    if used:
        st.error("Este enlace ya ha sido utilizado. Solicita uno nuevo.")
        if st.button("← Solicitar nuevo enlace", key="mls_reset_used_back"):
            st.session_state["selected_page"] = "_mls_forgot_password"
            st.query_params.clear()
            st.rerun()
        return

    if datetime.now(timezone.utc).isoformat() > expires_at:
        st.error("El enlace ha caducado (válido 1 hora). Solicita uno nuevo.")
        if st.button("← Solicitar nuevo enlace", key="mls_reset_expired_back"):
            st.session_state["selected_page"] = "_mls_forgot_password"
            st.query_params.clear()
            st.rerun()
        return

    st.markdown("## 🔑 Nueva contraseña MLS")
    st.markdown(f"Creando nueva contraseña para **{email}**")

    with st.form("mls_reset_form"):
        new_pass = st.text_input("Nueva contraseña", type="password", placeholder="Mínimo 8 caracteres")
        confirm  = st.text_input("Confirmar contraseña", type="password")
        submitted = st.form_submit_button("Guardar nueva contraseña", type="primary", use_container_width=True)

    if submitted:
        if len(new_pass) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            return
        if new_pass != confirm:
            st.error("Las contraseñas no coinciden.")
            return

        new_hash = generate_password_hash(new_pass)
        conn = _db.get_conn()
        conn.execute(
            "UPDATE inmobiliarias SET password_hash=? WHERE email_login=? OR email=?",
            (new_hash, email, email)
        )
        conn.execute("UPDATE password_reset_tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
        conn.close()

        st.success("Contraseña actualizada. Ya puedes iniciar sesión en el portal MLS.")
        if st.button("→ Ir al portal MLS", type="primary", key="mls_reset_ok_goto"):
            st.session_state["selected_page"] = "🏢 Inmobiliarias MLS"
            st.query_params.clear()
            st.rerun()


# ── Función principal ─────────────────────────────────────────────────────────

def main() -> None:
    """
    Punto de entrada del módulo MLS.
    Router de 5 estados con handlers de query params al inicio.
    """
    # ── 1. Handler ?mls_reserva_ok — retorno desde Stripe (reserva colaboradora) ──
    if st.query_params.get("mls_reserva_ok") == "1":
        try:
            from modules.mls import mls_reservas
            mls_reservas.ui_handler_retorno_stripe(st.query_params)
        except Exception as exc:
            st.error(f"Error al verificar reserva: {exc}")

    # ── 2. Obtener sesión ─────────────────────────────────────────────────────
    inmo = _get_inmo()

    # DEBUG — verificar que mls_inmo llega al router
    st.write(f"DEBUG inmo: {inmo is not None}, keys: {list(inmo.keys()) if inmo else 'None'}")
    st.write(f"DEBUG session keys: {[k for k in st.session_state.keys() if 'mls' in k.lower()]}")

    # Fallback robusto: si la sesión se perdió tras registro, recuperar por último id
    if inmo is None:
        _last_id = st.session_state.get("mls_last_inmo_id")
        if _last_id:
            try:
                _c = _db.get_conn()
                try:
                    _row = _c.execute(
                        "SELECT * FROM inmobiliarias WHERE id = ?", (_last_id,)
                    ).fetchone()
                    if _row:
                        _login_inmo(dict(_row))
                        inmo = _get_inmo()
                finally:
                    _c.close()
            except Exception:
                pass

    # Fallback final: recuperar sesión desde copia de seguridad post-registro
    if inmo is None:
        _backup_sesion = st.session_state.pop("_mls_registro_sesion", None)
        if _backup_sesion:
            st.session_state[_SESSION_KEY] = _backup_sesion
            inmo = _backup_sesion

    # ── 3. Handler ?mls_pago=ok — retorno desde Stripe (suscripción) ─────────
    if st.query_params.get("mls_pago") == "ok":
        if inmo is None:
            # Sesión perdida tras redirección Stripe — recuperar por stripe_session_id
            _sid = st.query_params.get("mls_stripe_session", "")
            if _sid:
                try:
                    _rc = _db.get_conn()
                    _rrow = _rc.execute(
                        "SELECT * FROM inmobiliarias WHERE stripe_session_id = ?", (_sid,)
                    ).fetchone()
                    _rc.close()
                    if _rrow:
                        _login_inmo(dict(_rrow))
                        inmo = _get_inmo()
                except Exception:
                    pass
        if inmo:
            _handle_pago_ok(inmo)
            inmo = _get_inmo()  # refrescar tras activación

    # ── 4. Expirar reservas vencidas (lazy) ───────────────────────────────────
    if inmo:
        try:
            conn = _db.get_conn()
            try:
                mls_db.expire_reservas_vencidas(conn)
            finally:
                conn.close()
        except Exception:
            pass

    # ── 5. Demo mode — auto-login con inmo demo si ?seccion=mls&demo=true ────
    if inmo is None and st.session_state.get("mls_demo_mode"):
        try:
            conn_d = _db.get_conn()
            _demo_row = conn_d.execute(
                "SELECT * FROM inmobiliarias WHERE id LIKE 'archirapid-demo-%' LIMIT 1"
            ).fetchone()
            conn_d.close()
            if _demo_row:
                _login_inmo(dict(_demo_row))
                inmo = _get_inmo()
        except Exception:
            pass

    # ── 5b. Router principal ──────────────────────────────────────────────────
    if inmo is None:
        ui_login_registro()
        return

    estado = _estado_inmo(inmo)

    # Botones "Ver planes" desde banners de trial redirigen aquí
    if st.session_state.pop("mls_ir_a_planes", False):
        ui_planes(inmo)
        return

    if estado == "espera_aprobacion":
        ui_espera_aprobacion(inmo)

    elif estado == "sin_plan":
        ui_planes(inmo)

    elif estado == "firma_pendiente":
        st.markdown(f"## 🏢 Portal MLS — {inmo['nombre']}")
        st.info("Para continuar, debes firmar el Acuerdo de Colaboración MLS.")
        firmado = mls_firma.mostrar_ui_firma(inmo)
        if firmado:
            # Refrescar sesión y redirigir al portal
            st.rerun()
        if st.button("Cerrar sesión", type="secondary"):
            _logout_inmo()
            st.rerun()

    elif estado == "operativo":
        ui_portal_operativo(inmo)

    else:
        # Estado desconocido — logout de seguridad
        st.error("Estado de sesión no reconocido. Vuelve a iniciar sesión.")
        _logout_inmo()
        st.rerun()
