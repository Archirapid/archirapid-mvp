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
    "visado_proyecto":    {"name": "Visado del Proyecto",           "amount": 50000},   # €500
    "direccion_obra":     {"name": "Dirección de Obra",             "amount": 80000},   # €800
    "construccion":       {"name": "Construcción Completa",         "amount": 150000},  # €1.500
    "supervision":        {"name": "Supervisión Técnica",           "amount": 30000},   # €300
    "copia_adicional":    {"name": "Copia Adicional",               "amount": 20000},   # €200
    # Modo Estudio (arquitectos)
    "estudio_download":   {"name": "Descarga Proyecto Modo Estudio", "amount":  1900},   # €19
    # Suscripciones de arquitectos (pago mensual recurrente — modo payment para MVP)
    "sub_basic":          {"name": "Suscripción ArchiRapid BASIC",   "amount":  2900},   # €29/mes
    "sub_pro":            {"name": "Suscripción ArchiRapid PRO",     "amount":  9900},   # €99/mes
    "sub_pro_anual":      {"name": "Suscripción ArchiRapid PRO Anual","amount": 89000},  # €890/año
    "sub_enterprise":     {"name": "Suscripción ArchiRapid ENTERPRISE","amount":29900},  # €299/mes
    # MLS — Suscripciones inmobiliarias y reservas (modo test, pago único)
    "mls_starter":        {"name": "ArchiRapid MLS STARTER (€49/mes)",    "amount":  4900},  # €49
    "mls_agency":         {"name": "ArchiRapid MLS AGENCY (€149/mes)",    "amount": 14900},  # €149
    "mls_enterprise":     {"name": "ArchiRapid MLS ENTERPRISE (€349/mes)","amount": 34900},  # €349
    "mls_reserva":        {"name": "Reserva MLS (desc. en comisión final)","amount": 20000},  # €200
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


def create_checkout_session(product_keys: list, project_id: str, client_email: str,
                             success_url: str, cancel_url: str,
                             extra_quantities: dict = None) -> tuple:
    """
    Crea una sesión de Stripe Checkout.
    Devuelve (checkout_url, session_id).
    extra_quantities: {product_key: quantity} para copias adicionales, etc.
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

    session = _stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=client_email or None,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "project_id": str(project_id),
            "client_email": str(client_email),
            "products": ",".join(product_keys),
        },
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


def verify_session(session_id: str):
    """Recupera y devuelve la sesión de Stripe (incluye payment_status y metadata)."""
    _stripe.api_key = _get_key()
    return _stripe.checkout.Session.retrieve(session_id)


def list_recent_sessions(limit: int = 50):
    """Devuelve las últimas sesiones de Checkout para el dashboard de intranet."""
    _stripe.api_key = _get_key()
    return _stripe.checkout.Session.list(limit=limit)


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
