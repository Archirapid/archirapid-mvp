---
name: archirapid-deploy
description: Checklist pre-deploy de ArchiRapid. Activar cuando el usuario vaya a hacer push a main o activar Stripe live.
---

## Checklist antes de push a main

### Secrets y seguridad
- [ ] Ninguna API key hardcodeada en código Python
- [ ] .env en .gitignore y no trackeado
- [ ] Stripe en modo correcto (test para pruebas, live para producción)
- [ ] SUPABASE_STORAGE_KEY en Streamlit secrets

### BD
- [ ] Migraciones en ambos sitios de db.py
- [ ] ensure_tables() con guard _tables_initialized

### Stripe
- [ ] `{CHECKOUT_SESSION_ID}` en todos los success_url
- [ ] amounts en céntimos correctos (39€=3900, 99€=9900, 199€=19900)
- [ ] `_detectar_plan_desde_session` thresholds: ≤5000→starter, ≤15000→agency

### Imágenes
- [ ] Supabase Storage key configurada
- [ ] Fallback a disco local funcionando
