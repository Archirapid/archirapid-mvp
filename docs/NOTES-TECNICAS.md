# ArchiRapid — Notas Técnicas

## Repositorio y deploy

- Repo: https://github.com/Archirapid/archirapid-mvp.git (branch: main)
- Producción: https://archirapid.com → https://archirapid.streamlit.app
- Local: `c:\ARCHIRAPID_PROYECT25`
- `database.db` está commitado a git (demo data).
- `catastro_output/` y `uploads/` están en `.gitignore` — no existen en Cloud.
- Solo imágenes demo específicas de fincas están commitadas en `uploads/`.

## Streamlit Cloud

- `packages.txt` debe estar **vacío** (no libgl1-mesa-glx, no libglib2.0-0 — broken en Debian trixie).
- Secrets formato TOML: `KEY = "value"` — Streamlit elimina las comillas automáticamente.
- Secrets se inyectan como env vars → `os.getenv()` funciona en Cloud igual que local.

## Gemini — solución definitiva

- **NO usar ningún SDK de Gemini** — `google-genai` y `google-generativeai` fallan en Streamlit Cloud.
- **Solución:** REST API directa con `requests` (ya en requirements.txt).
- Helper en `ai_engine.py`: `_gemini_rest(api_key, prompt, image_bytes=None, model="gemini-1.5-flash")`
- URL: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}`
- Response: `resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()`

## SQLite

- Siempre usar: `conn = sqlite3.connect(DB_PATH, timeout=15)` + `conn.execute("PRAGMA journal_mode=WAL")`
- Tanto `db_conn()` en `utils.py` como `get_conn()` en `src/db.py` tienen esto.

## Imágenes y rutas

- Siempre normalizar backslashes: `path.replace("\\", "/")`
- Guardar rutas relativas en DB (ej. `"MODELOS/espinosa.pdf"`, `"uploads/finca_xxx.jpg"`)
- `MODELOS/` tiene notas catastrales PDF de fincas demo.

## URL routing

- `st.query_params`: nunca eliminar params tras leer — deben persistir en la URL.
- Plot detail: `?selected_plot=ID`
- Project detail: `?selected_project_v2=ID`
- Prefab detail: `?selected_prefab=X`
- MLS: `?mls_view=mercado/ficha/reservar/contacto`

## MLS — detalles internos

- `mls_plot` tuple para funciones blue-pin: índices `[0]`=finca_id, `[2]`=catastro_ref, `[3]`=m2, `[4]`=m2×0.33, `[7]`=None, `[8]`=precio.
- Botones panel MLS usan keys con prefijo `mls_dsh_*` para no colisionar con panel azul.
- `ventas_proyectos` solo existe en PostgreSQL — fallback en `compatibilidad.py` lo gestiona.
- `activate_trial()` es idempotente: no reinicia si ya está activo, no activa si hay plan de pago.
- Emails trial usan Resend — mismo sistema que `mls_notificaciones.py`.
- `check_and_send_trial_emails()` llamable manualmente desde intranet sección G.
- Popup map button: `<a href="/?selected_plot=ID" target="_blank">` — URL relativa funciona en srcdoc iframes.

## Pipeline catastral en Cloud

- `validation_report.json` NO lo genera ningún script de pipeline.
- Cuando falta: sintetizar desde `edificability.json` (corregido en `ai_engine.py`).
- `plot_polygon.geojson` también es opcional.
- PDFs escaneados → pipeline no puede extraer `surface_m2` → fallback a Gemini Vision.

## floor_plan_svg.py — 4 funciones públicas

| Función | Qué genera |
|---------|-----------|
| `FloorPlanSVG(design).generate()` | Plano SVG clásico desde DesignData abstracto |
| `generate_mep_plan_png(rooms, layer)` | Plano MEP por capa (sewage/water/electrical/rainwater/domotics) |
| `generate_section_plan_png(rooms)` | Sección arquitectónica 1.20m desde layout 3D real |
| `generate_cimentacion_plan_png(rooms, type)` | Plano cimentación zapatas/losa |

- Capa `sewage`: routing ortogonal L-shaped, arqueta en cada codo, etiqueta Ø ramal.
- `generate_section_plan_png`: coordenadas reales X/Z del editor Babylon, cotas totales, escala gráfica, norte, leyenda zonas.

## babylon_editor.py — variables de estado clave

- `_currentStyle`: trackea el estilo arquitectónico activo entre rebuilds de escena.
- `_basePosData`: guarda posiciones base (X/Z) de todas las habitaciones antes de aplicar offset de parcela — se resetea tras borrar habitación o cambiar dimensiones.
- `_houseOffsetX` / `_houseOffsetZ`: offset actual de la casa dentro de la parcela.
- `RETRANQUEO = 3.0`: retranqueo legal estándar (metros) para slider parcela.
- `rebuildScene()`: tras rebuild llama `buildStyleExtras(_currentStyle)` + `buildSolarPanels()` para anclar chimenea y paneles al tejado.
- `deleteSelected()`: doble-clic para confirmar, guard mínimo 2 habitaciones interiores, guarda snapshot para undo.
