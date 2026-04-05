# ArchiRapid — Arquitectura y Estado del Proyecto

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
| `modules/mls/mls_db.py` | DB layer MLS + funciones trial (activate_trial, check_trial_status...) |
| `modules/mls/mls_trial_emails.py` | Emails ciclo trial (bienvenida/checkin/urgencia) vía Resend |
| `modules/mls/mls_publico.py` | Fichas públicas + capa profesional inmo + form reserva pin naranja |
| `modules/mls/mls_portal.py` | Portal inmo: login, registro, banner trial verde/rojo |
| `modules/mls/mls_mercado.py` | Portal inmo: mercado, reservas, guía 5 pasos |
| `modules/mls/mls_fincas.py` | Portal inmo: mis fincas, solicitudes, notificaciones + auto-clasifica suelo |
| `modules/mls/mls_mapa.py` | Pins naranjas en mapa home |
| `modules/mls/mls_reservas.py` | Lógica Stripe reservas MLS |

---

## Estado actual — AI House Designer (sprints completados 2026-04-05)

| Sprint | Qué hace | Estado |
|--------|----------|--------|
| S8 | ZIP SHA-256 + notificación "Hablar con Arquitecto" vía email_notify | ✅ |
| S1 | Constraint Solver: Paso 3 bloquea si falta Salón≥12m² o Cocina≥8m² | ✅ |
| S4 | Panel CTE semáforo (DB-HS3 ventilación/iluminación + DB-SUA1 dimensiones) en Paso 2 | ✅ |
| S6 | PDF 4 columnas Útil/Construida + Excel "Mediciones Constructivas" | ✅ |
| S5 | Saneamiento ortogonal L-shaped + plano cimentación zapatas/losa | ✅ commit eee879b |
| S2 | Borrar habitaciones doble-clic confirmación + chimenea/solar anclan tras rebuild | ✅ commit 67f71e1 |
| S7 | Sliders posición casa en parcela + retranqueo 3m enforced | ✅ commit cba21fa |
| S3 | Sección arquitectónica 1.20m desde layout 3D real (modo dual st.tabs con SVG) | ✅ commit 43da099 |

---

## Estado actual — Módulo Profesionales/Constructores

### Implementado (commit 35b5896, 2026-03-29)
- Plan Destacado €99/30 días — Stripe checkout al registrarse
- Filtrado proyectos por especialidad/partidas del constructor
- Delay 24h proyectos para plan gratuito (Destacado ve en tiempo real)
- Email notificación al constructor cuando se publica proyecto compatible
- Comisión 3% — Stripe checkout + PDF contrato (reportlab + SHA-256)

### Pendiente (a orden de Raul)
- Flujo end-to-end completo: registro → pago → oferta → cliente acepta → comisión → PDF

---

## Estado actual — GIS

### Implementado
- **GIS Fase 1:** `get_tipo_suelo_desde_coordenadas(lat, lon)` en `catastro_api.py` — auto-clasifica Urbana/Rústica al subir finca (owners.py + mls_fincas.py)

### Pendiente (aparcado)
- **GIS Fase 2:** Overlay WMS Catastro en mapa — LayerControl no aparece tras 4 intentos. Script inyectado correctamente con `get_root().render()` pero botón capa no visible. Aparcado hasta nueva orden.

---

## Estado actual del sistema MLS

### Implementado y en producción
- Registro y aprobación de inmobiliarias (Admin aprueba desde intranet)
- Portal inmo: mercado, mis fincas, reservas Stripe, notificaciones
- Fichas públicas sin login (`mls_publico.py`)
- Pins naranjos en mapa home
- Portal cliente pin naranja MLS (`show_buyer_panel_mls`) con 6 botones + botón "← Volver al mapa"
- Free trial 30 días: `activate_trial()` se llama al aprobar desde intranet
- Banners trial: verde (activo + días restantes) y rojo bloqueante (expirado)
- Emails ciclo trial: bienvenida (día 0), checkin (día 7), urgencia (día 25)
- Lola IA: system prompt MLS completo, historial reducido 12→8 mensajes
- URL routing: `?mls_view=mercado/ficha/reservar/contacto`
- Consultas y Soporte: tabla `tickets_soporte` + admin intranet + formularios en architects.py, client_panel.py, mls_portal.py

### Pendiente MLS (a orden de Raul)
- Stripe modo producción (cambiar claves test→live en Streamlit secrets)
- Stripe mode=subscription + cancelación fin de periodo + webhook
- Verificar que logout limpia claves `mls_reserva_finca_id`, `mls_show_*`

---

## Pendientes técnicos (a orden de Raul)

- **req_json TEXT en ai_projects:** ALTER TABLE + db.py líneas ~613 y ~1352 + flow.py:4641 — necesario para guardar JSON de requisitos MEP junto al proyecto
- **Flujo constructor end-to-end:** registro → pago → oferta → cliente acepta → comisión → PDF
- **Stripe live:** cambiar claves test→live + mode=subscription + cancelación + webhook
- **GIS Fase 2:** WMS overlay Catastro (aparcado)
- **Logout MLS:** verificar limpieza de claves de sesión al cerrar sesión
