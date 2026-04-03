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
| `app.py` | Router principal (~2500 líneas) + navegación bidireccional URL↔session_state |
| `src/db.py` | DB layer — schema en línea ~613 Y ~1352 (actualizado tras trial MLS) |
| `src/db_compat.py` | Adaptadores SQL SQLite↔PostgreSQL |
| `flow.py` | Flujo diseñador IA — único INSERT ai_projects en línea 4641 |
| `floor_plan_svg.py` | Generador SVG planta arquitectónica |
| `modules/marketplace/marketplace.py` | Mapa Folium con pins azules + WMS Catastro inyectado vía JS |
| `modules/marketplace/catastro_api.py` | API Catastro + `get_tipo_suelo_desde_coordenadas(lat, lon)` |
| `modules/marketplace/owners.py` | Subida fincas propietario — auto-clasifica suelo al subir |
| `modules/marketplace/intranet.py` | Admin (10 tabs + sección G trial MLS) |
| `modules/marketplace/client_panel.py` | Panel cliente pin azul + pin naranja MLS |
| `modules/marketplace/service_providers.py` | Portal constructor completo (plan Destacado, filtrado, comisión 3%) |
| `modules/marketplace/contrato_obra.py` | Generador PDF contrato obra con SHA-256 |
| `modules/marketplace/email_notify.py` | Notificaciones email a constructores |
| `modules/mls/` | Todo el sistema MLS |
| `modules/mls/mls_db.py` | DB layer MLS + funciones trial (activate_trial, check_trial_status...) |
| `modules/mls/mls_trial_emails.py` | Emails ciclo trial (bienvenida/checkin/urgencia) vía Resend |
| `modules/mls/mls_publico.py` | Fichas públicas + capa profesional inmo + form reserva pin naranja |
| `modules/mls/mls_portal.py` | Portal inmo: login, registro, banner trial verde/rojo |
| `modules/mls/mls_mercado.py` | Portal inmo: mercado, reservas, guía 5 pasos |
| `modules/mls/mls_fincas.py` | Portal inmo: mis fincas, solicitudes, notificaciones + auto-clasifica suelo |
| `modules/mls/mls_mapa.py` | Pins naranjas en mapa home |
| `modules/mls/mls_reservas.py` | Lógica Stripe reservas MLS |

## Reglas críticas — NUNCA ignorar
- Schema de BD en DOS sitios: db.py línea ~613 Y línea ~1352
- Placeholders: `%s` en PostgreSQL, `?` en SQLite — nunca mezclar
- NUNCA usar `pd.read_sql_query()` directamente — usar `conn.execute(sql, params)` + construir DataFrame manual con `cur.fetchall()` + `cur.description`. Los helpers `_read_sql9/_read3/_read_tab8` son locales de intranet.py
- `st.stop()` NUNCA dentro de `try/except Exception`
- Supabase usa pooler IPv4 — no direct connection
- `ensure_tables()` wrapeado en `@st.cache_resource`
- Schema de inmobiliarias incluye ahora: `trial_start_date`, `trial_active`, `trial_expired`
- **Folium en Streamlit:** usar `m.get_root().render()` — NO `m._repr_html_()`. El `_repr_html_()` envuelve en srcdoc iframe con HTML-encoding, `</body>` no existe en el string externo → scripts inyectados no llegan al iframe
- **Navegación app.py:** sync URL↔session_state corre en CADA rerun (no solo primera vez). `_SLUG_TO_PAGE` y `_PAGE_TO_SLUG` cubren todos los roles. "Diseñador de Vivienda" y "Propietario (Gemelo Digital)" son páginas de entrada programática (no sidebar) — intencional
- **Stripe URLs dinámicas:** usar `_get_base_url()` de `modules/stripe_utils.py` para success_url/cancel_url. NUNCA hardcodear `archirapid.streamlit.app` en Stripe checkouts — rompe local
- **Conexiones DB:** `conn.execute(sql_con_?)` funciona en ambos entornos: SQLite nativo + PostgreSQL vía `_PostgresConnWrapper.execute()` que adapta `?`→`%s` automáticamente

## Subagentes disponibles
- `@agent-babylon-editor` — editor 3D, meshes, layers, instalaciones MEP
- `@agent-db-migrations` — schema, ALTER TABLE, migraciones
- `@agent-mls-specialist` — todo el módulo MLS: inmos, fincas, mercado, reservas, trial
- `@agent-budget-calculator` — CTE HS-5, fosa séptica, presupuesto
- `@agent-svg-floor-plan` — planos 2D, capas saneamiento/agua/eléctrico
- `@agent-code-reviewer` — revisar antes de commit
- `@agent-stripe-specialist` — stripe_utils.py, webhooks, success_url, Stripe Connect, planes, comisiones, split de pagos

## Reglas de delegación
**Delegar a babylon-editor:** cualquier cambio en editor 3D, meshes, materiales, layers
**Delegar a db-migrations:** cambios en src/db.py, nuevas columnas, ALTER TABLE
**Delegar a mls-specialist:** cualquier cambio en modules/mls/ o flujos de inmo
**Delegar a stripe-specialist:** cualquier cambio en stripe_utils.py, success_url, webhooks, Stripe Connect
**Delegar en paralelo:** Babylon + DB no comparten archivos → paralelo OK
**Siempre secuencial:** DB migration ANTES de feature que dependa de esos datos

## Estado actual — Módulo Profesionales/Constructores
### Implementado (commit 35b5896, 2026-03-29)
- Plan Destacado €99/30 días — Stripe checkout al registrarse
- Filtrado proyectos por especialidad/partidas del constructor
- Delay 24h proyectos para plan gratuito (Destacado ve en tiempo real)
- Email notificación al constructor cuando se publica proyecto compatible
- Comisión 3% — Stripe checkout + PDF contrato (reportlab + SHA-256)

### Pendiente (revisar con Raul)
- Flujo end-to-end completo: registro → pago → oferta → cliente acepta → comisión → PDF

## Estado actual — GIS
### Implementado
- **GIS Fase 1:** `get_tipo_suelo_desde_coordenadas(lat, lon)` en `catastro_api.py` — auto-clasifica Urbana/Rústica al subir finca (owners.py + mls_fincas.py)
### Pendiente
- **GIS Fase 2:** Overlay WMS Catastro en mapa — botón de capa no aparece. Investigar: script se inyecta correctamente con `get_root().render()` pero LayerControl no visible. Pendiente de resolver.

## Estado actual del sistema MLS
### Implementado y en producción
- Registro y aprobación de inmobiliarias (Admin aprueba desde intranet)
- Portal inmo: mercado, mis fincas, reservas Stripe, notificaciones
- Fichas públicas sin login (mls_publico.py)
- Pins naranjos en mapa home
- Portal cliente pin naranja MLS (show_buyer_panel_mls) con 6 botones + botón "← Volver al mapa"
- Free trial 30 días: activate_trial() se llama al aprobar desde intranet
- Banners trial: verde (activo + días restantes) y rojo bloqueante (expirado)
- Emails ciclo trial: bienvenida (día 0), checkin (día 7), urgencia (día 25)
- Lola IA: system prompt MLS completo, historial reducido 12→8 mensajes
- URL routing: ?mls_view=mercado/ficha/reservar/contacto

### Pendiente MLS
- Stripe modo producción (cambiar claves test→live en Streamlit secrets cuando llegue el momento)
- Verificar que logout limpia claves mls_reserva_finca_id, mls_show_*

## Pendientes MEP Instalaciones (después de pruebas MLS completas)
- **Paso 0.5:** `req_json TEXT` en ai_projects — ALTER TABLE + db.py 613+1352 + flow.py:4641
- **Paso 1:** Motor CTE HS-5 Python puro — UDs, diámetros, fosa, presupuesto desglosado
- **Paso 2:** Capa SVG saneamiento sobre floor_plan_svg.py
- **Paso 3:** Babylon MEP visual — orden de ejecución: "Mejorar Babylon"

## Notas técnicas importantes
- `mls_plot` tuple para funciones blue-pin: índices [0]=finca_id [2]=catastro_ref [3]=m2 [4]=m2*0.33 [7]=None [8]=precio
- Botones panel MLS usan keys prefijo `mls_dsh_*` para no colisionar con panel azul
- `ventas_proyectos` solo existe en PostgreSQL — fallback en compatibilidad.py lo gestiona
- Trial: activate_trial() es idempotente (no reinicia si ya está activo, no activa si hay plan de pago)
- Emails trial usan Resend — mismo sistema que mls_notificaciones.py
- check_and_send_trial_emails() llamable manualmente desde intranet sección G
- _run_postgres_migrations(): NO usar SET lock_timeout ni conn.rollback() — rompe pgbouncer transaction mode
- Conexiones DB: siempre cerrar con try/finally: conn.close() — especialmente en funciones llamadas N veces por render

## Convenciones
- Commits en inglés, descriptivos: `fix:`, `feat:`, `refactor:`
- Probar siempre en local antes de push
- Antes de tocar cualquier archivo: leer estado actual completo
