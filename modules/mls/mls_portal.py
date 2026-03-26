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
        "precio": "€49/mes",
        "fincas": 15,
        "reservas": False,
        "descripcion": "Hasta 15 fincas activas. Acceso al mercado MLS para colaborar.",
        "color": "#4A90D9",
    },
    "mls_agency": {
        "nombre": "AGENCY",
        "precio": "€149/mes",
        "fincas": 75,
        "reservas": True,
        "descripcion": "Hasta 75 fincas. Reservas de colaboración (€200). Panel avanzado.",
        "color": "#F5A623",
    },
    "mls_enterprise": {
        "nombre": "ENTERPRISE",
        "precio": "€349/mes",
        "fincas": 0,  # 0 = ilimitado
        "reservas": True,
        "descripcion": "Fincas ilimitadas. Todas las funcionalidades. Soporte prioritario.",
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
                    mls_notificaciones.notif_pago_suscripcion(dict(row) if row else inmo, plan_key)
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
    if st.button("← Volver al mapa", key="mls_login_volver"):
        st.session_state.pop("selected_page", None)
        st.session_state.pop("mls_goto_finca_pending", None)
        st.query_params.clear()
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
    4. Cuando quieras continuar, elige tu plan: <b>Starter 49€/mes · Agency 149€ · Enterprise 349€</b>
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

            aceptar = st.checkbox(
                "Acepto las condiciones de uso de ArchiRapid MLS, el Acuerdo de Colaboración "
                "y la política de privacidad (RGPD). Confirmo que los datos facilitados son verídicos."
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
                errores.append("Debes aceptar las condiciones de uso y la política de privacidad.")

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
                    inmo_id = mls_db.create_inmo(datos, ip=ip)
                    if inmo_id:
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
                        st.error("Error al guardar. Comprueba que el CIF y el email de acceso no estén ya registrados.")
                except Exception as exc:
                    msg = str(exc)
                    if "UNIQUE" in msg and "cif" in msg.lower():
                        st.error("Ya existe una cuenta con ese CIF.")
                    elif "UNIQUE" in msg and "email" in msg.lower():
                        st.error("Ya existe una cuenta con ese email.")
                    else:
                        st.error(f"Error al registrar: {msg}")

                if _reg_success:
                    st.success("✅ ¡Solicitud de alta enviada correctamente!")
                    st.info(
                        "**Tu solicitud está siendo revisada.**\n\n"
                        "Recibirás un **email de confirmación** en cuanto sea aprobada (24-48h hábiles).\n\n"
                        "Una vez aprobada, vuelve aquí e inicia sesión en la pestaña **🔑 Acceder**."
                    )
                    st.stop()


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
    st.markdown("## 💳 Elige tu plan MLS")
    st.markdown(
        "Activa tu suscripción para comenzar a publicar fincas y colaborar en el mercado MLS. "
        "Pago seguro con Stripe — modo test activo."
    )

    cols = st.columns(3)
    plan_keys = ["mls_starter", "mls_agency", "mls_enterprise"]

    for col, pk in zip(cols, plan_keys):
        plan = _PLANES[pk]
        fincas_str = "Ilimitadas" if plan["fincas"] == 0 else str(plan["fincas"])
        reservas_str = "✅ Incluidas" if plan["reservas"] else "❌ No incluidas"

        with col:
            st.markdown(
                f"""
                <div style="border:2px solid {plan['color']};border-radius:10px;
                            padding:20px;text-align:center;min-height:260px;">
                  <h3 style="color:{plan['color']};margin:0 0 8px 0;">{plan['nombre']}</h3>
                  <p style="font-size:1.6rem;font-weight:700;margin:0 0 12px 0;">{plan['precio']}</p>
                  <p style="font-size:0.85rem;color:#555;margin:0 0 12px 0;">{plan['descripcion']}</p>
                  <p style="margin:4px 0;font-size:0.85rem;">🏠 Fincas: <b>{fincas_str}</b></p>
                  <p style="margin:4px 0;font-size:0.85rem;">🤝 Reservas: {reservas_str}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("")
            if st.button(
                f"Contratar {plan['nombre']}",
                key=f"btn_plan_{pk}",
                use_container_width=True,
            ):
                _iniciar_checkout_plan(pk, inmo)

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


def ui_portal_operativo(inmo: dict) -> None:
    """Portal completo — 8 tabs para inmobiliaria con plan activo y firma."""
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

    tab_fincas, tab_mercado, tab_reservas, tab_solicitudes, tab_proyectos, tab_prefab, tab_stats, tab_cuenta = st.tabs([
        "🏠 Mis Fincas",
        "🌐 Mercado MLS",
        "📋 Mis Reservas",
        "📬 Solicitudes",
        "🏗️ Proyectos",
        "🏡 Prefabricadas",
        "📊 Estadísticas",
        "⚙️ Mi Cuenta",
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

        reset_url = f"https://archirapid.streamlit.app/?mls_reset_token={token}"
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
