# Babylon Offset Parcela — Estado definitivo (2026-04-15)

## TL;DR (para no asustar a nadie)

- El fix de "offset parcela" ya está integrado en `main`.
- El PR #2 se cerró (no merge) porque el trabajo relevante quedó incorporado directamente en `main` de forma quirúrgica, manteniendo `houseRoot/siteRoot` intactos.
- Esta nota existe para que cualquier agente (Claude / Copilot / humano) sepa **qué se hizo, dónde está y cómo probarlo** sin tocar la lógica de negocio.

---

## Regla de oro (NO romper negocio)

- NO cambiar la lógica de costes, presupuesto ni exportaciones.
- Los cambios aquí son de **transformaciones** (offset/jerarquía) y de **reconstrucción de geometría** (roof/solar) para que sigan el movimiento correctamente.

---

## Qué problema se resolvió

Cuando el usuario movía los sliders de "Posición en parcela" (offset X/Z):

- La casa se movía pero el tejado/paneles solares se quedaban centrados (no seguían).
- MEP (saneamiento, agua, eléctrico) usaba coordenadas `roomsData` estáticas → no seguía el offset.
- Cimientos (losa/zapatas/pilotes) se posicionaban con coords originales → descuadre visual.
- `resetLayout()` no reseteaba los sliders ni la caché de posiciones base → desync al volver al origen.

---

## Solución (conceptual)

- Se normaliza y captura `_basePosByName` sin guards que bloqueen actualizaciones.
- Se aplica offset moviendo **meshes y TransformNodes** via `_applyHouseOffset(dx, dz)`.
- Tejado/paneles se **reconstruyen** con coordenadas del mundo (`getAbsolutePosition()`) — no se mueven por `.position` para evitar doble offset.
- Tras `rebuildScene()` se re-sincroniza `_basePosByName` y se reaplica el offset vigente.
- Helper `_getRoomWorldRect(idx)` centraliza la lectura de world bounding boxes via `getBoundingInfo().boundingBox`, con fallback a `roomsData` si el mesh aún no existe.

---

## Archivos afectados

| Archivo | Qué cambió |
|---------|-----------|
| `modules/ai_house_designer/babylon_editor.py` | Todo: houseRoot, _storeBaseMeshPositions, _applyHouseOffset, _getRoomWorldRect, buildMEPLayers, buildFoundation, resetLayout |
| `modules/ai_house_designer/floor_plan_svg.py` | Sin cambios en este PR. El 2D se genera a partir del `rooms_layout` exportado por el editor 3D; si el export incluye offset, el 2D lo reflejará indirectamente. |

---

## Commits de integración (fuente de verdad)

| Commit | Descripción |
|--------|-------------|
| `c3509bf` | fix: offset parcela — tejado/paneles sigan movimiento con jerarquía `houseRoot` |
| `8435c74` | refactor: usar `getAbsolutePosition()` en `buildRoof/buildSolarPanels` para coords mundiales |
| `dfee214` | docs: add Babylon offset fix design notes |
| `e8ca46d` | fix: sincronización offset para MEP, cimientos y resetLayout ← **commit de integración quirúrgica** |

---

## Estado del PR #2

- **PR #2**: CLOSED (cerrado, no mergeado).
- Motivo: la rama `copilot/fix-babylon-editor-parcel-offset` fue eliminada tras integrar los cambios útiles directamente en `main` sin rebase ni merge conflictivo.
- La rama `copilot/fix-babylon-editor-parcel-offset` fue eliminada (local + remote).

---

## Cómo probar (checklist QA)

1. Abrir editor 3D → generar una vivienda.
2. Mover sliders "Offset X / Offset Z":
   - [ ] Tejado sigue a la casa.
   - [ ] Paneles solares siguen al tejado/casa.
   - [ ] Etiquetas (`lbl_node_*`) se desplazan con la casa.
3. Cambiar dimensión de habitación (provoca `rebuildScene()`):
   - [ ] El offset actual se mantiene tras rebuild.
4. Toggle roof (ON → OFF → ON):
   - [ ] No produce "doble movimiento" ni desajuste.
5. Activar MEP desde el panel:
   - [ ] Saneamiento, agua y eléctrico siguen la posición real de la casa.
6. Activar Cimientos (losa / zapatas / pilotes):
   - [ ] Se posicionan bajo las habitaciones en su posición de offset.
7. Pulsar "Reset Layout":
   - [ ] La casa vuelve al origen.
   - [ ] Los sliders vuelven a 0.
   - [ ] Offset queda a 0 (mover sliders de nuevo funciona desde cero).

---

## Notas técnicas (para agentes)

- Si hay jerarquías (`TransformNode` parent), **NO leer `.position` local** para construir geometría global: usar `getAbsolutePosition()` o `getBoundingInfo().boundingBox`.
- Tejado y paneles deben reconstruirse con el offset vigente, **no moverse** via `.position` (evita doble offset).
- Tras cualquier `rebuildScene()`:
  1. Re-capturar base positions (`_storeBaseMeshPositions()`).
  2. Reaplicar offset actual (`_applyHouseOffset(_houseOffsetX, _houseOffsetZ)`).
- `fence_*` meshes usan `plotX/plotZ` fijos por diseño: pertenecen a la parcela, no a la casa.

---

> Documento de diseño completo: `docs/BABYLON_OFFSET_FIX_2026.md`
