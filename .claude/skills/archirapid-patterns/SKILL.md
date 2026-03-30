---
name: archirapid-patterns
description: Patrones obligatorios de ArchiRapid. Activar automáticamente en cualquier tarea de código Python del proyecto. Contiene reglas críticas de BD, Streamlit, Stripe y manejo de imágenes específicas de este proyecto.
---

## Reglas críticas — aplicar siempre

### Conexiones BD
SIEMPRE envolver en try/finally:
```python
conn = get_conn()
try:
    c = conn.cursor()
    c.execute(...)
    return c.fetchall()
finally:
    conn.close()
```

### Schema BD
Cambios de schema SIEMPRE en DOS sitios:
- src/db.py línea ~613 (ensure_tables)
- src/db.py línea ~1352 (_run_postgres_migrations)

### Placeholders SQL
- PostgreSQL (Supabase producción): `%s`
- SQLite (local): `?`
NUNCA mezclar en el mismo archivo

### st.stop()
NUNCA dentro de `except Exception` — causa errores fantasma en Streamlit
SIEMPRE en bloque `else` o fuera del try/except

### Imágenes
SIEMPRE verificar si es URL o ruta local antes de st.image():
```python
if isinstance(path, str) and path.startswith("http"):
    st.image(path)
elif os.path.exists(path):
    st.image(path)
```

### Stripe
SIEMPRE incluir `{CHECKOUT_SESSION_ID}` literal en success_url
NUNCA hardcodear API keys — leer desde `st.secrets` o `os.getenv`
amounts en céntimos: €1 = 100 cents

### Caché
Funciones que leen listas frecuentes (plots, fincas, proyectos):
```python
@st.cache_data(ttl=60)
```

### GIS/Catastro
SIEMPRE timeout=5 en llamadas WMS
SIEMPRE fallback silencioso si API falla — nunca lanzar excepción
