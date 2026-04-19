"""
ARCHIRAPID — Stripe utilities (modo test)
Helper centralizado para crear sesiones de Checkout y verificar pagos.
"""
import os
import stripe as _stripe

# Catálogo de productos ArchiRapid (importe en céntimos de euro)
PRODUCTS = {
    "pdf_proyecto":       {"name": "Memoria PDF del Proyecto",      "amount": 180000},  # €1.800
    "planos_cad":         {"name": "Planos CAD editables",          "amount": 250000},  # €2.500
    "proyecto_completo":  {"name": "Proyecto Completo (PDF + CAD)", "amount": 400000},  # €4.000
    "bim_ifc":            {"name": "Modelo BIM/IFC",                "amount": 14900},   # €149
    "blockchain_cert":    {"name": "Certificado Blockchain",        "amount":  9900},   # €99
    # Servicios adicionales
    "visado_proyecto":    {"name": "Visado del Proyecto",                              "amount":  50000},  # €500
    "direccion_obra":     {"name": "Dirección de Obra (dirección facultativa)",        "amount": 300000},  # €3.000
    "supervision_cte":    {"name": "Supervisión/Revisión previa CTE + Asunción resp.", "amount": 200000},  # €2.000
    "deo_css":            {"name": "Dirección de Ejecución (DEO) + CSS",               "amount": 350000},  # €3.500
    "seguro_tr":          {"name": "Seguro Todo Riesgo Construcción (anual)",          "amount":  40000},  # €400
    "resp_civil":         {"name": "Responsabilidad Civil profesional",                "amount":  25000},  # €250
    "seguro_integral":    {"name": "Seguro Integral (TR + RC)",                        "amount":  60000},  # €600
    "copia_adicional":    {"name": "Copia Adicional",                                  "amount":  20000},  # €200
    # Modo Estudio (arquitectos)
    "estudio_download":   {"name": "Descarga Proyecto Modo Estudio", "amount":  1900},   # €19
    # Suscripciones de arquitectos (pago mensual recurrente — modo payment para MVP)
    "sub_basic":          {"name": "Suscripción ArchiRapid BASIC",   "amount":  2900},   # €29/mes
    "sub_pro":            {"name": "Suscripción ArchiRapid PRO",     "amount":  9900},   # €99/mes
    "sub_pro_anual":      {"name": "Suscripción ArchiRapid PRO Anual","amount": 89000},  # €890/año
    "sub_enterprise":     {"name": "Suscripción ArchiRapid ENTERPRISE","amount":29900},  # €299/mes
    # MLS — Suscripciones inmobiliarias y reservas (modo test, pago único)
    "mls_starter":        {"name": "ArchiRapid MLS STARTER (€39/mes)",    "amount":  3900},  # €39
    "mls_agency":         {"name": "ArchiRapid MLS AGENCY (€99/mes)",     "amount":  9900},  # €99
    "mls_enterprise":     {"name": "ArchiRapid MLS PRO (€199/mes)",       "amount": 19900},  # €199
    "mls_reserva":        {"name": "Reserva MLS (desc. en comisión final)","amount": 20000},  # €200
    # Constructores / Profesionales
    "sp_destacado":       {"name": "Plan Destacado Constructor (€99/30 días)", "amount": 9900},  # €99
}


def _get_key():
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("STRIPE_SECRET_KEY", "")
        except Exception:
            pass
    return key


def _get_base_url() -> str:
    """Devuelve la URL base de la app (localhost en dev, producción en cloud)."""
    try:
        import streamlit as st
        host = st.context.headers.get("host", "localhost:8501")
        is_cloud = "streamlit.app" in host or ("localhost" not in host and "127.0.0.1" not in host)
        return f"https://{host}" if is_cloud else f"http://{host}"
    except Exception:
        return "https://archirapid.streamlit.app"


def create_checkout_session(product_keys: list, project_id: str, client_email: str,
                             success_url: str, cancel_url: str,
                             extra_quantities: dict = None,
                             extra_meta: dict = None) -> tuple:
    """
    Crea una sesión de Stripe Checkout.
    Devuelve (checkout_url, session_id).
    extra_quantities: {product_key: quantity} para copias adicionales, etc.
    extra_meta: campos adicionales que se añaden a metadata (ej. services_detail).
    """
    _stripe.api_key = _get_key()
    line_items = []
    for pk in product_keys:
        if pk not in PRODUCTS:
            continue
        qty = (extra_quantities or {}).get(pk, 1)
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": PRODUCTS[pk]["name"]},
                "unit_amount": PRODUCTS[pk]["amount"],
            },
            "quantity": qty,
        })

    _meta = {
        "project_id": str(project_id),
        "client_email": str(client_email),
        "products": ",".join(product_keys),
    }
    if extra_meta:
        # Stripe metadata values must be strings ≤500 chars
        for k, v in extra_meta.items():
            _meta[str(k)[:40]] = str(v)[:500]

    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=client_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=_meta,
    )
    return session.url, session.id


def create_custom_session(line_items: list, client_email: str,
                           success_url: str, cancel_url: str,
                           metadata: dict = None) -> tuple:
    """
    Crea sesión Stripe con line_items personalizados (para el diseñador IA).
    line_items: [{"name": str, "amount_cents": int, "quantity": int}]
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_key()
    stripe_items = [
        {
            "price_data": {
                "currency": "eur",
                "product_data": {"name": item["name"][:80]},
                "unit_amount": max(item["amount_cents"], 50),
            },
            "quantity": item.get("quantity", 1),
        }
        for item in line_items
    ]
    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=stripe_items,
        mode="payment",
        customer_email=client_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return session.url, session.id



def create_reservation_checkout(plot_id: str, pending_id: str, buyer_name: str,
                                 buyer_email: str, amount_cents: int, plot_ref: str,
                                 success_url: str, cancel_url: str) -> tuple:
    """
    Crea sesion Stripe Checkout para reserva del 1%% de una finca.
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_key()
    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": f"Reserva 7 dias Finca {plot_ref[:60]}"},
                "unit_amount": max(amount_cents, 50),
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=buyer_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "plot_reservation",
            "plot_id": str(plot_id)[:100],
            "pending_id": str(pending_id)[:100],
            "buyer_name": str(buyer_name)[:100],
            "buyer_email": str(buyer_email)[:100],
            "plot_ref": str(plot_ref)[:100],
        },
    )
    return session.url, session.id


def create_destacado_checkout(provider_id: str, provider_name: str,
                              provider_email: str, cancel_url: str) -> tuple:
    """
    Crea sesión Stripe Checkout para activar Plan Destacado (€99/30 días).
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_key()
    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": PRODUCTS["sp_destacado"]["name"]},
                "unit_amount": PRODUCTS["sp_destacado"]["amount"],
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=provider_email or None,
        success_url=(
            _get_base_url()
            + "/?sp_pago_ok=1&sp_sess={CHECKOUT_SESSION_ID}"
            + f"&sp_pid={provider_id}"
        ),
        cancel_url=cancel_url,
        metadata={
            "type": "sp_destacado",
            "provider_id": str(provider_id)[:100],
            "provider_name": str(provider_name)[:100],
            "provider_email": str(provider_email)[:100],
        },
    )
    return session.url, session.id


def create_comision_checkout(offer_id: str, constructor_email: str,
                              amount_cents: int, project_name: str,
                              cancel_url: str) -> tuple:
    """
    Crea sesión Stripe Checkout para pago de comisión ArchiRapid (3% obra adjudicada).
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_key()
    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": f"Comisión ArchiRapid — {project_name[:60]}"},
                "unit_amount": max(amount_cents, 50),
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=constructor_email or None,
        success_url=(
            _get_base_url()
            + "/?sp_comision_ok=1&sp_sess={CHECKOUT_SESSION_ID}"
            + f"&offer_id={offer_id}"
        ),
        cancel_url=cancel_url,
        metadata={
            "type": "sp_comision",
            "offer_id": str(offer_id)[:100],
            "constructor_email": str(constructor_email)[:100],
            "project_name": str(project_name)[:100],
        },
    )
    return session.url, session.id


def verify_session(session_id: str):
    """Recupera y devuelve la sesión de Stripe (incluye payment_status y metadata)."""
    _stripe.api_key = _get_key()
    return _stripe.checkout.Session.retrieve(session_id)


def list_recent_sessions(limit: int = 50):
    """Devuelve las últimas sesiones de Checkout para el dashboard de intranet."""
    _stripe.api_key = _get_key()
    return _stripe.checkout.Session.list(limit=limit)


# ══════════════════════════════════════════════════════════════════════
# STRIPE CONNECT EXPRESS — Onboarding + Split automático
# ══════════════════════════════════════════════════════════════════════

def _get_connect_key():
    """Obtiene STRIPE_SECRET_KEY para Connect (misma key test)."""
    return _get_key()


def create_connect_onboarding_link(account_id: str,
                                    return_url: str,
                                    refresh_url: str) -> str:
    """
    Genera link de onboarding Express para que un profesional
    conecte su cuenta Stripe.
    Devuelve la URL del formulario alojado por Stripe.
    """
    _stripe.api_key = _get_connect_key()
    link = _stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


def create_express_account(email: str,
                            nombre: str,
                            tipo: str = "arquitecto") -> str:
    """
    Crea una cuenta Express de Stripe para un profesional.
    tipo: "arquitecto", "inmobiliaria", "constructor"
    Devuelve el account_id (acct_XXXXXXXX).
    """
    _stripe.api_key = _get_connect_key()
    account = _stripe.Account.create(
        type="express",
        country="ES",
        email=email,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        business_profile={
            "name": nombre[:50],
            "product_description": f"Profesional ArchiRapid — {tipo}",
            "url": "https://archirapid.com",
        },
        metadata={
            "tipo": tipo,
            "plataforma": "archirapid",
        }
    )
    return account.id


def create_checkout_session_connect(
        product_keys: list,
        project_id: str,
        client_email: str,
        success_url: str,
        cancel_url: str,
        stripe_account_id: str,
        fee_percent: float = 0.10,
        extra_meta: dict = None) -> tuple:
    """
    Crea sesión Checkout con split automático via Connect.
    fee_percent: porcentaje que se queda ArchiRapid (default 10%)
    El profesional recibe el resto automáticamente.
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_connect_key()
    line_items = []
    total_cents = 0
    for pk in product_keys:
        if pk not in PRODUCTS:
            continue
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": PRODUCTS[pk]["name"]},
                "unit_amount": PRODUCTS[pk]["amount"],
            },
            "quantity": 1,
        })
        total_cents += PRODUCTS[pk]["amount"]

    # IVA 21% incluido en el precio (precios ya con IVA)
    # application_fee = lo que se queda ArchiRapid
    fee_cents = int(total_cents * fee_percent)

    _meta = {
        "project_id": str(project_id),
        "client_email": str(client_email),
        "products": ",".join(product_keys),
        "stripe_account_id": str(stripe_account_id),
        "fee_percent": str(fee_percent),
    }
    if extra_meta:
        for k, v in extra_meta.items():
            _meta[str(k)[:40]] = str(v)[:500]

    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=client_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        payment_intent_data={
            "application_fee_amount": fee_cents,
            "transfer_data": {
                "destination": stripe_account_id,
            },
        },
        metadata=_meta,
    )
    return session.url, session.id


def create_mls_reserva_connect(
        finca_id: str,
        inmo_listante_account_id: str,
        precio_venta_cents: int,
        split_colaboradora_pct: float,
        buyer_email: str,
        success_url: str,
        cancel_url: str) -> tuple:
    """
    Crea sesión MLS con split automático:
    - ArchiRapid: 1% del precio de venta
    - Inmobiliaria listante: resto después del split colaboradora
    El split con colaboradora se gestiona manualmente post-venta.
    Devuelve (checkout_url, session_id).
    """
    _stripe.api_key = _get_connect_key()

    # Reserva = 10% del precio de venta
    reserva_cents = int(precio_venta_cents * 0.10)
    # Fee ArchiRapid = 1% del precio de venta
    fee_cents = int(precio_venta_cents * 0.01)
    # Fee no puede superar el importe de la reserva
    fee_cents = min(fee_cents, reserva_cents)

    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": f"Reserva MLS — Finca {finca_id[:40]}"
                },
                "unit_amount": reserva_cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=buyer_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        payment_intent_data={
            "application_fee_amount": fee_cents,
            "transfer_data": {
                "destination": inmo_listante_account_id,
            },
        },
        metadata={
            "type": "mls_reserva_connect",
            "finca_id": str(finca_id)[:100],
            "precio_venta_cents": str(precio_venta_cents),
            "split_colaboradora_pct": str(split_colaboradora_pct),
            "buyer_email": str(buyer_email)[:100],
            "fee_cents": str(fee_cents),
        },
    )
    return session.url, session.id


def get_connect_account(account_id: str) -> dict:
    """
    Recupera datos de una cuenta Express conectada.
    Útil para verificar si el onboarding está completo.
    """
    _stripe.api_key = _get_connect_key()
    try:
        account = _stripe.Account.retrieve(account_id)
        return {
            "id": account.id,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "details_submitted": account.details_submitted,
            "email": account.get("email", ""),
        }
    except Exception as e:
        return {"error": str(e)}


# ACTIVAR STRIPE LIVE EN MLS (sin cambios de código):
# 1. Añadir en Streamlit Cloud secrets:
#    STRIPE_SECRET_KEY_LIVE = sk_live_...
#    STRIPE_PUBLISHABLE_KEY_LIVE = pk_live_...
#    MLS_STRIPE_LIVE = true
# 2. Los Price IDs de test (mls_starter, mls_agency, mls_enterprise, mls_reserva)
#    deberán recrearse en el dashboard live de Stripe y añadirse como:
#    MLS_PRICE_STARTER_LIVE    = price_live_...
#    MLS_PRICE_AGENCY_LIVE     = price_live_...
#    MLS_PRICE_ENTERPRISE_LIVE = price_live_...
#    MLS_PRICE_RESERVA_LIVE    = price_live_...
# 3. Verificar con un pago real de €1 antes de abrir al público.
