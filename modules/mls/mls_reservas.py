"""
modules/mls/mls_reservas.py
Gestión completa de reservas MLS — ArchiRapid.

Cuatro funciones principales (sin Streamlit — lógica pura):
  1. iniciar_reserva_colaboradora()            — URL Stripe para inmo colaboradora
  2. verificar_pago_reserva_colaboradora()     — confirma pago y crea reserva en BD
  3. iniciar_reserva_cliente_directo()         — URL Stripe para cliente desde pin naranja
  4. verificar_pago_reserva_cliente()          — confirma pago cliente y notifica admin

Dos funciones UI (importan streamlit):
  5. ui_handler_retorno_stripe()               — handler de ?mls_reserva_ok=1
  6. ui_formulario_reserva_cliente_directo()   — formulario del popup del mapa

Reglas de seguridad:
  - get_finca_by_id() SOLO en verificar_pago_reserva_colaboradora() paso 5,
    únicamente para obtener el email de la listante para notificación interna.
    Documentado explícitamente — nunca expuesto a la colaboradora ni al cliente.
  - Toda lógica de BD via mls_db
  - try/except en todas las llamadas Stripe
"""
from urllib.parse import urlencode

from modules.mls import mls_db
from modules.mls.mls_notificaciones import (
    notif_finca_reservada,
    notif_reserva_cliente,
)
from modules.stripe_utils import create_checkout_session, verify_session

# URL base de la app (Streamlit Cloud)
_BASE_URL = "https://archirapid.streamlit.app"


# =============================================================================
# FUNCIÓN 1 — iniciar_reserva_colaboradora
# =============================================================================

def iniciar_reserva_colaboradora(finca_id: str, inmo_id: str) -> str:
    """
    Genera la URL de Stripe Checkout para reserva de €200 por inmobiliaria
    colaboradora.

    No crea registro en BD — la reserva se persiste en
    verificar_pago_reserva_colaboradora() tras confirmar el pago.

    Devuelve checkout_url (str).
    Lanza ValueError si la finca ya está reservada o no existe.
    """
    # 1. Verificar que no hay reserva activa
    reserva_existente = mls_db.get_reserva_activa_by_finca(finca_id)
    if reserva_existente:
        raise ValueError(
            f"Finca ya reservada — existe reserva activa: {reserva_existente.get('id')}"
        )

    # 2. Obtener datos de la finca (sin identidad listante)
    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        raise ValueError(f"Finca no encontrada o no disponible: {finca_id}")

    # 3. Obtener email de la inmo colaboradora para Stripe
    inmo = mls_db.get_inmo_by_id(inmo_id)
    inmo_email = (inmo.get("email") or "") if inmo else ""

    # 4. Generar URLs de retorno — {CHECKOUT_SESSION_ID} es template Stripe
    success_params = urlencode({
        "mls_reserva_ok": "1",
        "finca_id":        finca_id,
        "inmo_id":         inmo_id,
        "tipo":            "colaboradora",
        "session_id":      "{CHECKOUT_SESSION_ID}",
    })
    cancel_params = urlencode({
        "mls_reserva_cancel": "1",
        "finca_id":            finca_id,
    })
    success_url = f"{_BASE_URL}/?{success_params}"
    cancel_url  = f"{_BASE_URL}/?{cancel_params}"

    # 5. Crear sesión Stripe
    try:
        checkout_url, _session_id = create_checkout_session(
            product_keys=["mls_reserva"],
            project_id=finca_id,
            client_email=inmo_email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:
        raise ValueError(f"Error al crear sesión Stripe: {exc}") from exc

    return checkout_url


# =============================================================================
# FUNCIÓN 2 — verificar_pago_reserva_colaboradora
# =============================================================================

def verificar_pago_reserva_colaboradora(
    finca_id: str,
    inmo_colaboradora_id: str,
    stripe_session_id: str,
) -> bool:
    """
    Verifica el pago Stripe y persiste la reserva en BD.
    Se llama cuando el usuario regresa con ?mls_reserva_ok=1&tipo=colaboradora.

    Devuelve True si todo OK, False si el pago no está confirmado o la finca
    ya fue reservada por otra colaboradora mientras el usuario pagaba.
    """
    # 1. Verificar pago con Stripe
    try:
        session = verify_session(stripe_session_id)
        if session.payment_status != "paid":
            return False
    except Exception:
        return False

    # 2. Verificar de nuevo que la finca sigue libre (race condition)
    reserva_existente = mls_db.get_reserva_activa_by_finca(finca_id)
    if reserva_existente:
        # La finca fue reservada mientras el usuario pagaba.
        # Admin debe gestionar la devolución manualmente.
        try:
            from src import db as _db
            import json
            conn = _db.get_conn()
            conn.execute(
                """INSERT INTO notificaciones_mls
                   (destinatario_tipo, destinatario_id, tipo_evento,
                    payload, timestamp, leida)
                   VALUES ('archirapid', 'admin',
                           'reserva_colision_devolucion', ?, datetime('now'), 0)""",
                (json.dumps({
                    "finca_id":              finca_id,
                    "inmo_colaboradora_id":  inmo_colaboradora_id,
                    "stripe_session_id":     stripe_session_id,
                    "motivo":                "Finca reservada por tercero durante el pago",
                }),),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        return False

    # 3. Crear reserva en BD
    reserva_id = mls_db.create_reserva(
        finca_id=finca_id,
        inmo_colaboradora_id=inmo_colaboradora_id,
        stripe_session_id=stripe_session_id,
        importe=200.0,
    )
    if not reserva_id:
        return False

    # 4. Actualizar estado de la finca
    try:
        mls_db.update_finca_estado(finca_id, "reservada")
    except Exception:
        pass  # reserva creada — estado fallará de forma contenida

    # 5. Obtener email de la LISTANTE para notificación interna.
    #    EXCEPCIÓN CONTROLADA: aquí sí se usa get_finca_by_id() porque esta función
    #    es ejecutada por ArchiRapid para gestión interna (no por la colaboradora).
    #    El email de la listante NO se transmite a la colaboradora en ningún momento.
    try:
        finca_completa = mls_db.get_finca_by_id(finca_id)  # ← solo para notif interna
        ref_codigo     = (finca_completa or {}).get("ref_codigo") or "—"
        listante_inmo_id = (finca_completa or {}).get("inmo_id")
        listante_email = ""
        if listante_inmo_id:
            listante_inmo = mls_db.get_inmo_by_id(listante_inmo_id)
            listante_email = (listante_inmo or {}).get("email") or ""
    except Exception:
        ref_codigo    = "—"
        listante_email = ""

    # 6. Notificar a la listante
    try:
        notif_finca_reservada(
            ref_codigo=ref_codigo,
            inmo_listante_email=listante_email,
        )
    except Exception:
        pass

    return True


# =============================================================================
# FUNCIÓN 3 — iniciar_reserva_cliente_directo
# =============================================================================

def iniciar_reserva_cliente_directo(
    finca_id: str,
    nombre_cliente: str,
    email_cliente: str,
) -> str:
    """
    Genera URL Stripe para reserva de cliente directo desde el pin naranja del mapa.
    No requiere inmo logueada.

    Devuelve checkout_url (str).
    Lanza ValueError si la finca ya está reservada o no existe.
    """
    # 1. Verificar que no hay reserva activa
    reserva_existente = mls_db.get_reserva_activa_by_finca(finca_id)
    if reserva_existente:
        raise ValueError("Finca ya reservada por otra parte.")

    # 2. Verificar que la finca existe y es pública
    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        raise ValueError(f"Finca no encontrada: {finca_id}")

    # 3. Generar URLs de retorno — {CHECKOUT_SESSION_ID} es template Stripe
    success_params = urlencode({
        "mls_reserva_ok": "1",
        "finca_id":        finca_id,
        "tipo":            "cliente_directo",
        "nombre":          nombre_cliente,
        "email":           email_cliente,
        "session_id":      "{CHECKOUT_SESSION_ID}",
    })
    cancel_params = urlencode({
        "mls_reserva_cancel": "1",
        "finca_id":            finca_id,
    })
    success_url = f"{_BASE_URL}/?{success_params}"
    cancel_url  = f"{_BASE_URL}/?{cancel_params}"

    # 4. Crear sesión Stripe
    try:
        checkout_url, _session_id = create_checkout_session(
            product_keys=["mls_reserva"],
            project_id=finca_id,
            client_email=email_cliente,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:
        raise ValueError(f"Error al crear sesión Stripe: {exc}") from exc

    return checkout_url


# =============================================================================
# FUNCIÓN 4 — verificar_pago_reserva_cliente
# =============================================================================

def verificar_pago_reserva_cliente(
    finca_id: str,
    nombre_cliente: str,
    email_cliente: str,
    stripe_session_id: str,
) -> bool:
    """
    Verifica pago de cliente directo y crea reserva con estado
    'reserva_pendiente_confirmacion' (admin tiene 48h para confirmar disponibilidad).

    Devuelve True si OK, False si el pago no está confirmado o la finca ya fue tomada.
    """
    # 1. Verificar pago Stripe
    try:
        session = verify_session(stripe_session_id)
        if session.payment_status != "paid":
            return False
    except Exception:
        return False

    # 2. Verificar finca libre
    if mls_db.get_reserva_activa_by_finca(finca_id):
        return False

    # 3. Crear reserva de cliente en BD
    reserva_id = mls_db.create_reserva_cliente(
        finca_id=finca_id,
        nombre_cliente=nombre_cliente,
        email_cliente=email_cliente,
        stripe_session_id=stripe_session_id,
        importe=200.0,
    )
    if not reserva_id:
        return False

    # 4. Actualizar estado de la finca
    try:
        mls_db.update_finca_estado(finca_id, "reserva_pendiente_confirmacion")
    except Exception:
        pass

    # 5. Obtener datos para notificación
    try:
        finca = mls_db.get_finca_sin_identidad_listante(finca_id)
        ref_codigo = (finca or {}).get("ref_codigo") or "—"
        precio     = float((finca or {}).get("precio") or 0)
    except Exception:
        ref_codigo = "—"
        precio     = 0.0

    # 6. Notificar a ArchiRapid (admin gestiona la confirmación en 48h)
    try:
        notif_reserva_cliente(
            ref_codigo=ref_codigo,
            nombre_cliente=nombre_cliente,
            precio=precio,
        )
    except Exception:
        pass

    return True


# =============================================================================
# UI 1 — Handler de retorno Stripe (?mls_reserva_ok=1)
# =============================================================================

def ui_handler_retorno_stripe(query_params: dict) -> None:
    """
    Se llama desde mls_portal.py al detectar ?mls_reserva_ok=1 en la URL.
    Lee tipo (colaboradora | cliente_directo) y llama al verificador correspondiente.
    """
    import streamlit as st

    finca_id          = query_params.get("finca_id", "")
    tipo              = query_params.get("tipo", "")
    stripe_session_id = query_params.get("session_id", "")

    if not finca_id:
        st.error("Parámetro finca_id ausente en la URL de retorno.")
        return

    # ── Colaboradora ──────────────────────────────────────────────────────────
    if tipo == "colaboradora":
        inmo_id = query_params.get("inmo_id", "")
        if not inmo_id:
            st.error("Parámetro inmo_id ausente.")
            return

        # Si Stripe no incluyó session_id, buscar la sesión más reciente
        # (en test mode el redirect no siempre incluye session_id)
        if not stripe_session_id:
            st.info(
                "Verificando pago… Si la pantalla no avanza en 10 segundos, "
                "recarga la página."
            )
            return

        ok = verificar_pago_reserva_colaboradora(
            finca_id=finca_id,
            inmo_colaboradora_id=inmo_id,
            stripe_session_id=stripe_session_id,
        )
        if ok:
            st.success(
                "✅ Reserva confirmada. 72 horas de exclusiva activas.  \n"
                "La inmobiliaria listante ha sido notificada. Coordinad "
                "los siguientes pasos a través de ArchiRapid."
            )
        else:
            st.error(
                "Lo sentimos, esta finca acaba de ser reservada por otra colaboradora "
                "mientras realizabas el pago. Tu pago de €200 será devuelto "
                "en 3–5 días hábiles. ArchiRapid ha sido notificado."
            )
            try:
                from modules.mls.mls_notificaciones import _send_telegram
                _send_telegram(
                    f"⚠️ <b>Colisión de reserva</b>\n"
                    f"Finca: {finca_id}\nInmo colaboradora: {inmo_id}\n"
                    f"Sesión Stripe: {stripe_session_id}\n"
                    f"→ Gestionar devolución manual"
                )
            except Exception:
                pass

    # ── Cliente directo ───────────────────────────────────────────────────────
    elif tipo == "cliente_directo":
        nombre_cliente = query_params.get("nombre", "Cliente")
        email_cliente  = query_params.get("email", "")

        ok = verificar_pago_reserva_cliente(
            finca_id=finca_id,
            nombre_cliente=nombre_cliente,
            email_cliente=email_cliente,
            stripe_session_id=stripe_session_id,
        )
        if ok:
            st.success(
                f"✅ Reserva recibida.  \n"
                f"ArchiRapid confirmará la disponibilidad en menos de **48 horas**.  \n"
                f"Recibirás un email en **{email_cliente}** con la confirmación."
            )
        else:
            st.error(
                "Lo sentimos, esta finca acaba de ser reservada. "
                "Tu pago de €200 será devuelto en 3–5 días hábiles."
            )

    else:
        st.warning(f"Tipo de reserva desconocido: `{tipo}`")


# =============================================================================
# UI 2 — Formulario reserva cliente directo (popup del pin naranja)
# =============================================================================

def ui_formulario_reserva_cliente_directo(finca: dict) -> None:
    """
    Formulario visible desde el popup del pin naranja cuando el cliente pulsa
    'Reservar €200'. Inicia el flujo Stripe para cliente directo.
    """
    import streamlit as st

    finca_id  = finca.get("id", "")
    ref       = finca.get("ref_codigo") or "—"
    titulo    = finca.get("titulo") or "Finca MLS"
    precio    = float(finca.get("precio") or 0)

    st.subheader("💳 Reservar finca")
    st.markdown(f"**`{ref}`** — {titulo}  ·  €{precio:,.0f}")

    st.info(
        "Al reservar aceptas que ArchiRapid gestione tu solicitud. "
        "La reserva de **€200** es reembolsable si la finca no está disponible. "
        "ArchiRapid confirmará disponibilidad en menos de **48 horas**."
    )

    with st.form("mls_reserva_cliente_form", clear_on_submit=False):
        nombre = st.text_input(
            "Nombre completo *",
            placeholder="Tu nombre y apellidos",
            key="mls_rc_nombre",
        )
        email = st.text_input(
            "Email *",
            placeholder="tu@email.com",
            key="mls_rc_email",
        )
        telefono = st.text_input(
            "Teléfono (opcional)",
            placeholder="+34 600 000 000",
            key="mls_rc_telefono",
        )
        mensaje = st.text_area(
            "Mensaje (opcional)",
            max_chars=200,
            placeholder="¿Alguna pregunta antes de reservar?",
            key="mls_rc_mensaje",
        )
        aceptado = st.checkbox(
            "He leído el aviso legal y acepto las condiciones de la reserva.",
            key="mls_rc_acepta",
        )
        submitted = st.form_submit_button(
            "Reservar y pagar €200 →",
            type="primary",
        )

    if submitted and aceptado:
        # Validaciones básicas
        if not nombre.strip():
            st.error("Introduce tu nombre completo.")
            return
        if not email.strip() or "@" not in email:
            st.error("Introduce un email válido.")
            return

        with st.spinner("Preparando el pago…"):
            try:
                checkout_url = iniciar_reserva_cliente_directo(
                    finca_id=finca_id,
                    nombre_cliente=nombre.strip(),
                    email_cliente=email.strip().lower(),
                )
                # Redirigir a Stripe Checkout
                st.markdown(
                    f'<meta http-equiv="refresh" content="0; url={checkout_url}">',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"[💳 Ir al pago seguro →]({checkout_url})",
                )
            except ValueError as e:
                st.error(str(e))
            except Exception as exc:
                st.error(f"Error inesperado: {exc}")


# STRIPE CONNECT — ACTIVAR EN LIVE (fase futura):
# Cuando se active producción, el cierre de operación MLS usará Stripe Connect para:
# 1. Cobrar el importe total al comprador
# 2. Transferir automáticamente a la listante:
#    precio_venta * comision_listante_pct / 100
# 3. Transferir a la colaboradora si aplica:
#    precio_venta * comision_colaboradora_pct / 100
# 4. ArchiRapid retiene el 1% fijo automáticamente
# 5. Generar factura automática via Stripe Invoices
#    con IVA (21% en España) para cada parte
# 6. El IBAN registrado en inmobiliarias.iban
#    se usa como cuenta de destino en Stripe Connect
# Prerequisitos:
# - Cada inmobiliaria debe crear cuenta Stripe Connect
# - IBAN verificado por Stripe (KYC)
# - Activar STRIPE_CONNECT_SECRET_KEY en Streamlit Cloud secrets
