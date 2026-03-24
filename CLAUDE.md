# ArchiRapid — Contexto del proyecto

## Qué es
SaaS PropTech español para diseño arquitectónico con IA. Stack: Streamlit + Babylon.js + Supabase (prod) / SQLite (local) + Groq + Gemini.

## Deploy
- Repo: https://github.com/Archirapid/archirapid-mvp.git (branch: main)
- Producción: https://archirapid.streamlit.app
- Local: `c:\ARCHIRAPID_PROYECT25`

## Archivos clave
| Archivo | Propósito |
|---------|-----------|
| `app.py` | Router principal (~2500 líneas) |
| `src/db.py` | DB layer — schema en línea 444 Y línea 927 |
| `src/db_compat.py` | Adaptadores SQL SQLite↔PostgreSQL |
| `flow.py` | Flujo diseñador IA — único INSERT ai_projects en línea 4641 |
| `floor_plan_svg.py` | Generador SVG planta arquitectónica |
| `modules/marketplace/intranet.py` | Admin (10 tabs) |
| `modules/mls/` | Todo el sistema MLS |

## Reglas críticas — NUNCA ignorar
- Schema de BD en DOS sitios: db.py línea 444 Y línea 927
- Placeholders: `%s` en PostgreSQL, `?` en SQLite — nunca mezclar
- NUNCA usar `pd.read_sql_query()` directamente — usar helpers `_read_sql9`, `_read3`, `_read_tab8`
- `st.stop()` NUNCA dentro de `try/except Exception`
- Supabase usa pooler IPv4 — no direct connection
- `ensure_tables()` wrapeado en `@st.cache_resource`

## Subagentes disponibles
- `@agent-babylon-editor` — editor 3D, meshes, layers, instalaciones MEP
- `@agent-db-migrations` — schema, ALTER TABLE, migraciones
- `@agent-budget-calculator` — CTE HS-5, fosa séptica, presupuesto
- `@agent-svg-floor-plan` — planos 2D, capas saneamiento/agua/eléctrico
- `@agent-code-reviewer` — revisar antes de commit

## Reglas de delegación
**Delegar a babylon-editor:** cualquier cambio en editor 3D, meshes, materiales, layers
**Delegar a db-migrations:** cambios en src/db.py, nuevas columnas, ALTER TABLE
**Delegar en paralelo:** Babylon + DB no comparten archivos → paralelo OK
**Siempre secuencial:** DB migration ANTES de feature que dependa de esos datos

## Pendientes documentados
### MLS (próxima sesión de pruebas)
- `?mls_ficha=`, `?mls_reservar=`, `?mls_contacto=` → routing a mls_publico.py (diseñado, no ejecutado)

### MEP Instalaciones (después de pruebas MLS)
- **Paso 0.5:** `req_json TEXT` en ai_projects — ALTER TABLE + db.py 444+927 + flow.py:4641
- **Paso 1:** Motor CTE HS-5 Python puro — UDs, diámetros, fosa, presupuesto desglosado
- **Paso 2:** Capa SVG saneamiento sobre floor_plan_svg.py
- **Paso 3:** Babylon MEP visual — orden: "Mejorar Babylon"

## Convenciones
- Commits en inglés, descriptivos: `fix:`, `feat:`, `refactor:`
- Probar siempre en local antes de push
- Antes de tocar cualquier archivo: leer estado actual completo