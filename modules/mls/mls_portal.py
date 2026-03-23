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
        row = conn.execute(
            "SELECT * FROM inmobiliarias WHERE id = ?", (inmo["id"],)
        ).fetchone()
        if row:
            refreshed = dict(row)
            st.session_state[_SESSION_KEY] = refreshed
            return refreshed
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
    """
    if not inmo.get("activa"):
        return "espera_aprobacion"
    if not inmo.get("plan_activo"):
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
    st.markdown("## 🏢 ArchiRapid MLS — Portal Inmobiliario")
    st.caption("Bolsa de colaboración entre inmobiliarias. Listantes + colaboradoras.")

    # ── Pantalla post-registro: muestra SOLO el aviso, sin form ─────────────────
    _reg_ok = st.session_state.pop("mls_registro_ok", False)
    if _reg_ok:
        st.success("✅ Solicitud de alta enviada correctamente")
        st.info(
            "**¿Qué pasa ahora?**\n\n"
            "1. Nuestro equipo revisará tu solicitud en **24-48 horas hábiles**.\n"
            "2. Recibirás un **email de confirmación** cuando tu cuenta esté aprobada.\n"
            "3. Una vez aprobada, vuelve aquí y accede con tu email y contraseña."
        )
        st.markdown("---")
        if st.button("🔑 Ir a Acceder", type="primary"):
            st.rerun()
        return  # ← no renderiza tabs ni formulario

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
                    st.rerun()
                else:
                    st.error("Email o contraseña incorrectos.")

    # ── Tab Registro ──────────────────────────────────────────────────────────
    with tab_registro:
        # Si acabamos de registrar, Streamlit mantiene este tab activo por memoria
        # de widgets. Mostramos confirmación en vez del formulario para evitar confusión.
        if _reg_ok:
            st.success("✅ Tu solicitud ha sido enviada correctamente.")
            st.info("Cuando tu cuenta sea aprobada (24-48h hábiles) podrás iniciar sesión en la pestaña **🔑 Acceder**.")
            st.stop()

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
                        "- Recibirás un **email de confirmación** en cuanto sea aprobada (24-48h hábiles).\n"
                        "- Una vez aprobada, vuelve aquí y accede con tu email y contraseña."
                    )
                    st.link_button("🏠 Volver a la home", "/")


def _get_client_ip() -> str:
    """Intenta obtener la IP del cliente desde headers de Streamlit."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx:
            from streamlit.web.server.websocket_headers import _get_websocket_headers
            headers = _get_websocket_headers()
            if headers:
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
        conn.execute(
            "UPDATE inmobiliarias SET stripe_session_id = ? WHERE id = ?",
            (session_id, inmo["id"]),
        )
        conn.commit()

        import streamlit.components.v1 as _stc_mls
        _stc_mls.html(f'<script>window.top.location.href="{url}";</script>', height=0)
        st.link_button("💳 Ir al pago →", url, type="primary", use_container_width=True)

    except ImportError:
        st.error("Stripe no disponible en este entorno.")
    except Exception as exc:
        st.error(f"Error al iniciar pago: {exc}")


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
    """Portal completo — 6 tabs para inmobiliaria con plan activo y firma."""
    st.markdown(
        f"### 🏢 Portal MLS — {inmo['nombre']} "
        f"<span style='font-size:0.75rem;color:#888;'>"
        f"Plan: **{inmo.get('plan','?').upper()}**</span>",
        unsafe_allow_html=True,
    )
    # Botón de contacto siempre visible en el portal
    _ui_contacto_archirapid_btn(inmo)

    tab_fincas, tab_mercado, tab_reservas, tab_solicitudes, tab_stats, tab_cuenta = st.tabs([
        "🏠 Mis Fincas",
        "🌐 Mercado MLS",
        "📋 Mis Reservas",
        "📬 Solicitudes",
        "📊 Estadísticas",
        "⚙️ Mi Cuenta",
    ])

    with tab_fincas:
        try:
            from modules.mls import mls_fincas
            _sf, _mf = st.tabs(["📤 Subir Finca", "🏠 Mis Fincas"])
            with _sf:
                mls_fincas.ui_subir_finca(inmo)
            with _mf:
                mls_fincas.ui_mis_fincas(inmo)
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
            _row_cert = _conn_cert.execute(
                "SELECT documento_hash, ip FROM firmas_colaboracion WHERE inmo_id = ? ORDER BY id DESC LIMIT 1",
                (inmo["id"],),
            ).fetchone()
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
                    conn.execute(
                        "UPDATE inmobiliarias SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(pwd_nueva1), inmo["id"]),
                    )
                    conn.commit()
                    st.success("Contraseña actualizada correctamente.")

    st.divider()
    if st.button("🚪 Cerrar sesión", type="secondary"):
        _logout_inmo()
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
            mls_db.expire_reservas_vencidas(conn)
        except Exception:
            pass

    # ── 5. Router principal ───────────────────────────────────────────────────
    if inmo is None:
        ui_login_registro()
        return

    estado = _estado_inmo(inmo)

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
