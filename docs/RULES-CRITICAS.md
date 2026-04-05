# ArchiRapid — Reglas Críticas (NUNCA ignorar)

## Base de datos

- Schema de BD en **DOS sitios**: `db.py` línea ~613 Y línea ~1352 — actualizar ambos siempre.
- Placeholders: `%s` en PostgreSQL, `?` en SQLite — nunca mezclar.
- **NUNCA** usar `pd.read_sql_query()` directamente — usar `conn.execute(sql, params)` + construir DataFrame manual con `cur.fetchall()` + `cur.description`. Los helpers `_read_sql9` / `_read3` / `_read_tab8` son locales de `intranet.py`.
- Conexiones DB: siempre cerrar con `try/finally: conn.close()` — especialmente en funciones llamadas N veces por render.
- `conn.execute(sql_con_?)` funciona en ambos entornos: SQLite nativo + PostgreSQL vía `_PostgresConnWrapper.execute()` que adapta `?`→`%s` automáticamente.
- `ensure_tables()` wrapeado en `@st.cache_resource`.
- Supabase usa pooler IPv4 — no direct connection.
- `_run_postgres_migrations()`: NO usar `SET lock_timeout` ni `conn.rollback()` — rompe pgbouncer transaction mode.
- Schema de inmobiliarias incluye: `trial_start_date`, `trial_active`, `trial_expired`.

## Streamlit

- `st.stop()` **NUNCA** dentro de `try/except Exception`.
- **Folium:** usar `m.get_root().render()` — NO `m._repr_html_()`. El `_repr_html_()` envuelve en srcdoc iframe con HTML-encoding, `</body>` no existe en el string externo → scripts inyectados no llegan al iframe.
- **Navegación `app.py`:** sync URL↔session_state corre en CADA rerun (no solo primera vez). `_SLUG_TO_PAGE` y `_PAGE_TO_SLUG` cubren todos los roles. "Diseñador de Vivienda" y "Propietario (Gemelo Digital)" son páginas de entrada programática (no sidebar) — intencional.

## Stripe

- Usar `_get_base_url()` de `modules/stripe_utils.py` para `success_url` / `cancel_url`.
- **NUNCA** hardcodear `archirapid.streamlit.app` en Stripe checkouts — rompe local.
- No tocar las líneas 654-658 de `mls_portal.py` (fallback `base_url` para Stripe) — son funcionales, no textos visibles.

## URLs visibles al usuario

- Usar `archirapid.com` en textos de emails, captions y mensajes al usuario.
- **NUNCA** cambiar URLs funcionales: Stripe success/cancel, webhooks, `_BASE_URL` en `mls_reservas.py`, `index.html`.

## Babylon.js

- `dispose()` para memoria en todos los meshes que se eliminen.
- `async` donde corresponda.
- Trackear `_currentStyle` (estilo activo entre rebuilds) y `_basePosData` (posiciones base para offset parcela).

## Archivos pesados

- PDFs, SVGs grandes, GLBs: solo path/URL, nunca leer completo.

## Subagentes — delegación recomendada

| Tarea | Agente |
|-------|--------|
| Cambios editor 3D, meshes, MEP | `@agent-babylon-editor` |
| Schema, ALTER TABLE, db.py | `@agent-db-migrations` |
| Todo modules/mls/ | `@agent-mls-specialist` |
| Stripe, webhooks, success_url | `@agent-stripe-specialist` |
| Planos 2D, MEP SVG | `@agent-svg-floor-plan` |
| CTE HS-5, fosa séptica, presupuesto | `@agent-budget-calculator` |
| Revisión código antes de commit | `@agent-code-reviewer` |

- **Paralelo OK:** Babylon + DB no comparten archivos.
- **Siempre secuencial:** DB migration ANTES de feature que depende de esos datos.
