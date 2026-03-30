---
name: archirapid-review
description: Code review específico de ArchiRapid. Activar cuando el usuario pida revisar código, hacer auditoría, o antes de un commit importante.
---

## Proceso de revisión — en este orden

### Paso 1 — Bugs críticos (bloquean producción)
- ¿Hay `conn = get_conn()` sin `finally: conn.close()`?
- ¿Hay `st.stop()` dentro de `except Exception`?
- ¿Hay schema BD modificado en un solo sitio?
- ¿Hay `{CHECKOUT_SESSION_ID}` en todos los success_url de Stripe?
- ¿Hay API keys hardcodeadas en el código?

### Paso 2 — Performance
- ¿Hay funciones de lectura frecuente sin `@st.cache_data`?
- ¿Hay llamadas a `ensure_tables()` fuera del guard `_tables_initialized`?

### Paso 3 — Compatibilidad
- ¿Se mezclan placeholders `?` y `%s` en el mismo archivo?
- ¿Hay `os.path.exists()` sobre URLs `http://`?

### Formato de salida
Agrupar por severidad: CRÍTICO / IMPORTANTE / MENOR
Para cada issue: archivo, línea, problema, fix sugerido
Terminar con: "✅ Listo para commit" o "🚫 X issues críticos a resolver"
