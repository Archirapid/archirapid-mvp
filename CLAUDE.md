# ArchiRapid — Contexto del proyecto

## Qué es
SaaS PropTech español para diseño arquitectónico con IA. Stack: Streamlit + Babylon.js + Supabase (prod) / SQLite (local) + Groq + Gemini.

## Deploy
- Repo: https://github.com/Archirapid/archirapid-mvp.git (branch: main)
- Producción: https://archirapid.com (redirige a https://archirapid.streamlit.app)
- Local: `c:\ARCHIRAPID_PROYECT25`

## Archivos clave
| Archivo | Propósito |
|---------|-----------|
| `app.py` | Router principal (~2500 líneas) + navegación bidireccional URL↔session_state |
| `src/db.py` | DB layer — schema en línea ~613 Y ~1352 (actualizado tras trial MLS) |
| `src/db_compat.py` | Adaptadores SQL SQLite↔PostgreSQL |
| `flow.py` | Flujo diseñador IA — único INSERT ai_projects en línea 4641 |
| `modules/ai_house_designer/floor_plan_svg.py` | Planos 2D: SVG clásico + sección 3D + MEP (saneamiento/agua/eléctrico) + cimentación |
| `modules/ai_house_designer/babylon_editor.py` | Editor 3D Babylon.js — borrar habitaciones, posición parcela, chimenea/paneles anclados |
| `modules/ai_house_designer/constraint_solver.py` | Validación semántica: supervivencia (Salón≥12m², Cocina≥8m²), exterior isolation |
| `modules/ai_house_designer/cte_checker.py` | Checks DB-HS3 (ventilación, iluminación) + DB-SUA1 (dimensiones mínimas) |
| `modules/ai_house_designer/mep_hs5.py` | Motor CTE HS-5: UDs, diámetros ramales, colector, fosa séptica, presupuesto |
| `modules/marketplace/marketplace.py` | Mapa Folium con pins azules + WMS Catastro inyectado vía JS |
| `modules/marketplace/catastro_api.py` | API Catastro + `get_tipo_suelo_desde_coordenadas(lat, lon)` |
| `modules/marketplace/owners.py` | Subida fincas propietario — auto-clasifica suelo al subir |
| `modules/marketplace/intranet.py` | Admin (10 tabs) — incluye Consultas y Soporte con tabla tickets_soporte |
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
- **URLs visibles al usuario:** usar `archirapid.com`. NUNCA cambiar URLs funcionales (Stripe, webhooks, fallback base_url de mls_portal.py lines 654-658)

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
**Siempre secuencial:** DB migration ANTES de feature que depende de esos datos

## Estado actual — AI House Designer (sprints completados 2026-04-04)
| Sprint | Qué hace | Estado |
|--------|----------|--------|
| S8 | ZIP SHA-256 + notificación Telegram "Hablar con Arquitecto" | ✅ commit eee… |
| S1 | Constraint Solver: Paso 3 bloquea si falta Salón≥12m² o Cocina≥8m² | ✅ |
| S4 | Panel CTE semáforo (DB-HS3 ventilación/iluminación + DB-SUA1 dimensiones) en Paso 2 | ✅ |
| S6 | PDF 4 columnas Útil/Construida + Excel "Mediciones Constructivas" | ✅ |
| S5 | Saneamiento ortogonal L-shaped + plano cimentación zapatas/losa | ✅ commit eee879b |
| S2 | Borrar habitaciones doble-clic confirmación + chimenea/solar anclan tras rebuild | ✅ commit 67f71e1 |
| S7 | Sliders posición casa en parcela + retranqueo 3m enforced | ✅ commit cba21fa |
| S3 | Sección arquitectónica 1.20m desde layout 3D real (modo dual st.tabs con SVG) | ✅ commit 43da099 |

## Estado actual — Módulo Profesionales/Constructores
### Implementado (commit 35b5896, 2026-03-29)
- Plan Destacado €99/30 días — Stripe checkout al registrarse
- Filtrado proyectos por especialidad/partidas del constructor
- Delay 24h proyectos para plan gratuito (Destacado ve en tiempo real)
- Email notificación al constructor cuando se publica proyecto compatible
- Comisión 3% — Stripe checkout + PDF contrato (reportlab + SHA-256)

### Pendiente (a orden de Raul)
- Flujo end-to-end completo: registro → pago → oferta → cliente acepta → comisión → PDF

## Estado actual — GIS
### Implementado
- **GIS Fase 1:** `get_tipo_suelo_desde_coordenadas(lat, lon)` en `catastro_api.py` — auto-clasifica Urbana/Rústica al subir finca (owners.py + mls_fincas.py)
### Pendiente (aparcado)
- **GIS Fase 2:** Overlay WMS Catastro en mapa — LayerControl no aparece tras 4 intentos. Script inyectado correctamente con `get_root().render()` pero botón capa no visible. Aparcado.

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

### Pendiente MLS (a orden de Raul)
- Stripe modo producción (cambiar claves test→live en Streamlit secrets)
- Stripe mode=subscription + cancelación fin de periodo + webhook
- Verificar que logout limpia claves mls_reserva_finca_id, mls_show_*

## Pendientes técnicos (a orden de Raul)
- **req_json TEXT en ai_projects:** ALTER TABLE + db.py líneas ~613 y ~1352 + flow.py:4641 — necesario para guardar JSON de requisitos MEP junto al proyecto
- **Consultas y Soporte:** tabla `tickets_soporte` + intranet admin + formularios usuario YA implementados en architects.py, client_panel.py, mls_portal.py

## Notas técnicas importantes
- `mls_plot` tuple para funciones blue-pin: índices [0]=finca_id [2]=catastro_ref [3]=m2 [4]=m2*0.33 [7]=None [8]=precio
- Botones panel MLS usan keys prefijo `mls_dsh_*` para no colisionar con panel azul
- `ventas_proyectos` solo existe en PostgreSQL — fallback en compatibilidad.py lo gestiona
- Trial: activate_trial() es idempotente (no reinicia si ya está activo, no activa si hay plan de pago)
- Emails trial usan Resend — mismo sistema que mls_notificaciones.py
- check_and_send_trial_emails() llamable manualmente desde intranet sección G
- _run_postgres_migrations(): NO usar SET lock_timeout ni conn.rollback() — rompe pgbouncer transaction mode
- Conexiones DB: siempre cerrar con try/finally: conn.close() — especialmente en funciones llamadas N veces por render
- floor_plan_svg.py ahora tiene 4 funciones públicas: `FloorPlanSVG`, `generate_mep_plan_png`, `generate_section_plan_png`, `generate_cimentacion_plan_png`
- babylon_editor.py: `_currentStyle` trackea estilo activo entre rebuilds; `_basePosData` guarda posiciones base para offset parcela

## Convenciones
- Commits en inglés, descriptivos: `fix:`, `feat:`, `refactor:`
- Probar siempre en local antes de push
- Antes de tocar cualquier archivo: leer estado actual completo
