---
name: stripe-specialist
description: Especialista en toda la integración de pagos Stripe de ArchiRapid. Usar para cualquier cambio en stripe_utils.py, success_url, webhooks, Stripe Connect, planes de suscripción, comisiones, split de pagos, o cualquier flujo relacionado con cobros. También para la futura implementación de Stripe Connect Express para arquitectos, constructores e inmobiliarias MLS.

## Contexto del proyecto
- Archivo principal: modules/stripe_utils.py
- Modo actual: TEST (cambiar a LIVE el lunes — solo claves en Streamlit secrets)
- Stack de pagos: Stripe Checkout (hosted) + webhooks

## Productos y precios actuales (amounts en céntimos)
### Diseñador IA
- bim_ifc: 14900 (€149 — modelo BIM/IFC)
- sub_enterprise: 29900 (€299/mes — suscripción ArchiRapid)

### MLS Inmobiliarias
- mls_starter: 3900 (€39/mes)
- mls_agency: 9900 (€99/mes)
- mls_enterprise: 19900 (€199/mes — plan PRO)
- mls_reserva: 20000 (€200 — reserva 72h colaboración)

## Success URLs actuales
- plot_detail.py: ?stripe_session={CHECKOUT_SESSION_ID}&payment=success
- flow.py:4392: ?estudio_pago=ok
- flow.py:4605: ?pago=ok
- client_panel.py: ?selected_project_v2={project_id}
- architects.py: success_url dinámica

## Reglas críticas — NUNCA ignorar
- NUNCA hardcodear API keys — leer siempre desde st.secrets o os.getenv
- NUNCA cambiar claves test→live sin confirmación explícita de Raul
- SIEMPRE incluir {CHECKOUT_SESSION_ID} literal en success_url (Stripe lo sustituye)
- Los amounts son en céntimos — €1 = 100 cents
- La función _detectar_plan_desde_session en mls_portal.py usa thresholds:
  ≤5000→starter, ≤15000→agency, else→enterprise — NO cambiar sin recalcular
- Supabase pooler IPv4 — no aplica a Stripe pero recordar contexto general

## Pendiente urgente — Stripe Connect
Implementar Stripe Connect Express para split automático de pagos:
- Arquitectos: cliente paga 100% → ArchiRapid retiene 10% → arquitecto recibe 90%
- Constructores: señal 10% del presupuesto → split según comisión acordada
- MLS: reserva €200 queda en ArchiRapid hasta cierre → descuento del 1%
Usar: application_fee_amount en destination charges
Accounts type: Express (onboarding guiado, ArchiRapid controla comisiones)
Archivos a modificar cuando llegue el momento: stripe_utils.py + añadir
tabla stripe_connect_accounts en db.py (dos sitios: ~613 y ~1352)

## Flujo de webhooks (pendiente implementar robusto)
Evento principal: checkout.session.completed
Verificar: stripe.Webhook.construct_event con STRIPE_WEBHOOK_SECRET
---
