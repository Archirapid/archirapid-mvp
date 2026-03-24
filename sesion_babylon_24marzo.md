# Sesión Babylon — 24 Marzo 2026

## Estado al cierre de sesión
Rama: `main` · Último commit: `bf76755`

---

## Lo que se hizo esta sesión (en orden)

### 1. Fix imágenes home — commit `9d71750`
- Demo fincas MLS (`326cb705`, `velilla-demo`, `93ff27cc`) tenían `image_paths = NULL`
- Asignadas imágenes comprometidas en git → ya aparecen en el grid de la home

### 2. Babylon MEP — Fase 1: LayerManager — commit `f09e6d3`
**Archivo:** `modules/ai_house_designer/babylon_editor.py`
- `const MEPLayers` — 5 capas: sewage / water / electrical / rainwater / domotics
- `toggleMEPLayer(layerName)` — toggle visible + estado visual botón
- `setGroundTransparency(alpha)` — slider suelo para ver instalaciones enterradas
- `window.groundMesh` / `window.gridPlaneMesh` referencias
- Sección **⚙️ INSTALACIONES MEP** colapsable en toolbar izquierdo

### 3. Babylon MEP — Fase 2: Geometría tuberías — commit `2202374` + fix `e3892b0`
**Archivo:** `modules/ai_house_designer/babylon_editor.py`
- `buildMEPLayers(rooms)` — genera geometría `CreateLines` por capa:
  - **Saneamiento**: colector enterrado + drops wet rooms + fosa séptica (CreateBox)
  - **Agua**: manifold horizontal + branches a cocina/baño/aseo
  - **Eléctrico**: trunk a techo + drop por habitación
  - **Canalones**: canaletas perimetrales + 4 bajantes
  - **Domótica**: paralelo al eléctrico offset -0.15m
- Llamado tras `buildRoom` inicial y dentro de `rebuildScene`
- **Fix crítico**: triple try/catch — guard `rooms.length===0`, inner mepLine, outer body
  → sin este fix el canvas quedaba negro (el error mataba el render loop)

### 4. Babylon MEP — Fase 3: Planos 2D por capa — commit `28e0ded`
**Archivos:** `modules/ai_house_designer/floor_plan_svg.py` + `flow.py`
- `generate_mep_plan_png(rooms_layout, layer_name, total_w, total_d)` → PNG bytes
  - Matplotlib: planta casa + habitaciones por zona + overlay MEP capa
  - Saneamiento: colector + drops + fosa séptica box
  - Agua: manifold + ramas + label "ACOMETIDA"
  - Eléctrico: trunk + drops + CGP box (cuadro general protección)
  - Canalones: canaletas perimetrales + markers BAJANTE
  - Domótica: conduit punteado + HUB circle
- `flow.py`: guarda `babylon_initial_layout` en session_state
- Expander **"📐 Planos Técnicos MEP"** tras editor Babylon → 5 columnas, 1 plano por capa, botón ⬇️ descarga PNG

### 5. Fix MEP zonas garden + sync tejado — commit `ab204d9`
**Archivo:** `modules/ai_house_designer/babylon_editor.py`
- **Bug**: cables eléctricos/domótica iban a `paneles_solares` (zona garden, fuera casa)
- **Fix**: `habRooms` filtra `zone=garden/exterior` + códigos panel/solar/piscina/huerto
- `houseMaxX/MinX/MaxZ` calculados solo desde habitaciones interiores
- `toggleRoof()`: llama `buildMEPLayers(roomsData)` al ON y al OFF → sincronización perfecta

### 6. Paso 0.5: `req_json TEXT` en ai_projects — commit `bf76755`
**Archivos:** `src/db.py` + `modules/ai_house_designer/flow.py`
- `db.py:449` `_TABLES` CREATE TABLE — nueva columna `req_json TEXT`
- `db.py:971` `ensure_tables()` CREATE TABLE + try/except ALTER (SQLite existente)
- `db.py:712` `_PG_ALTER_MIGRATIONS` — `ADD COLUMN IF NOT EXISTS req_json TEXT`
- `flow.py:4684` INSERT guarda `ai_house_requirements` serializado como JSON

---

## Próximo paso: PASO 1 — Motor CTE HS-5

### Qué es
Motor Python puro de cálculo de saneamiento según normativa española CTE HS-5.
Sin dependencias externas. Calcula a partir del `req_json` guardado en `ai_projects`.

### Qué calcula
- **UDs** (Unidades de Descarga) por aparato sanitario (WC=4, lavabo=2, ducha=2, bañera=3, fregadero=3, lavavajillas=3, lavadora=3)
- **Diámetros de ramales** por tramo según tabla CTE HS-5
- **Colector principal** — diámetro función de UDs totales + pendiente 2%
- **Fosa séptica** — volumen mínimo según nº habitantes (200L/persona/día × 3 días)
- **Presupuesto desglosado** — coste por partida (tuberías PVC, arquetas, fosa, mano de obra)

### Archivos a crear/modificar
| Acción | Archivo | Qué |
|--------|---------|-----|
| CREAR | `modules/ai_house_designer/mep_hs5.py` | Motor CTE HS-5 completo |
| MODIFICAR | `flow.py` | Llamar motor + mostrar resultados en paso 3/4 |

### Estructura del motor (`mep_hs5.py`)
```python
def calcular_saneamiento(req: dict, rooms_layout: list) -> dict:
    """
    Entrada: req (ai_house_requirements) + rooms_layout (lista rooms Babylon)
    Salida: dict con:
      - aparatos: {nombre: {ud, count, ud_total}}
      - ramales: [{desde, hasta, ud, diametro_mm}]
      - colector: {ud_total, diametro_mm, pendiente_pct, longitud_m}
      - fosa: {habitantes, volumen_litros, tipo}
      - presupuesto: {tuberia_pvc, arquetas, fosa, mano_obra, total}
      - resumen_texto: str (para mostrar en UI)
    """
```

### Tablas CTE HS-5 que implementar
```
UDs por aparato:
  WC cisterna: 4 UD
  WC fluxor:   8 UD
  Lavabo:      2 UD
  Ducha:       2 UD
  Bañera:      3 UD
  Fregadero:   3 UD
  Lavavajillas: 3 UD
  Lavadora:    3 UD
  Bañera grande: 4 UD

Diámetro ramal (pendiente 2%):
  ≤4 UD  → 50mm
  ≤8 UD  → 63mm (o 50mm con ventilación)
  ≤12 UD → 75mm
  ≤20 UD → 90mm
  ≤32 UD → 110mm
  >32 UD → 125mm

Colector (pendiente 2%):
  ≤12 UD → 63mm
  ≤24 UD → 75mm
  ≤48 UD → 90mm
  ≤96 UD → 110mm
  ≤UD infinito → 125-160mm
```

---

## Fallos pendientes (dejar para después)
El usuario los mencionó pero son de baja prioridad y no bloquean MEP:
- Detalles visuales en el editor Babylon (no especificados)

## Fallos MLS pendientes (muy baja prioridad)
- Tab "Consultas y Soporte" en Intranet: placeholder sin implementar
- `?mls_ficha=`, `?mls_reservar=`, `?mls_contacto=` → routing pendiente

---

## Comandos útiles de referencia

```bash
# Push a GitHub (Streamlit auto-deploya)
git push origin main

# Ver último commit
git log --oneline -5

# Syntax check Python
python -c "import ast; ast.parse(open('archivo.py',encoding='utf-8').read()); print('OK')"

# Probar localmente
streamlit run app.py
```

## URLs clave
- **Producción**: https://archirapid.streamlit.app
- **Demo MLS**: https://archirapid.streamlit.app/?seccion=mls&demo=true
- **GitHub**: https://github.com/Archirapid/archirapid-mvp (branch: main)
