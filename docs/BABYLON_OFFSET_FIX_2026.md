---
name: Offset Parcela — Tejado + Paneles Solares Seguimiento Correcto
description: Arquitectura completa de jerarquía houseRoot/siteRoot + fix triple (meshes, TransformNodes, rebuild)
type: project
---

## Problema Reportado (2026-04-15)

El tejado (y paneles solares) **no seguían el movimiento** cuando el usuario movía los sliders "Posición en parcela" (offset X/Z). El tejado se quedaba en el centro mientras la casa se movía.

## Causa Raíz (Diagnosticada)

Tres problemas entrelazados:

1. **_storeBaseMeshPositions()** guard bloqueaba actualización de posiciones tras normalización
2. **TransformNodes** (etiquetas de habitaciones) no eran tracked ni movidas
3. **rebuildScene()** no re-sincronizaba base positions tras cambios de dimensiones

## Solución Implementada

### Commits

```
c3509bf fix: offset parcela — tejado/paneles sigan movimiento con jerarquía houseRoot
8435c74 refactor: usar getAbsolutePosition() en buildRoof/buildSolarPanels
```

### 1. Jerarquía houseRoot/siteRoot (Líneas 611-643)

```javascript
const houseRoot = new BABYLON.TransformNode("houseRoot", scene);
const siteRoot  = new BABYLON.TransformNode("siteRoot",  scene);

function isHouseRoom(room) {
    const zone = (room.zone || '').toLowerCase();
    const code = (room.code || '').toLowerCase();
    if (code.includes('porche')) return true;
    return zone !== 'garden' && zone !== 'exterior';
}
```

**Propósito**: Contenedores jerárquicos para que Babylon.js gestione transformaciones consistentemente.

**Parenting** (distribuido en buildRoom + buildWalls):
- `floor.parent = houseRoot` (si isHouseRoom)
- `[bw, fw, lw, rw].parent = houseRoot` (todas las paredes)
- Puertas, ventanas → houseRoot
- `lbl_node_*.parent = houseRoot` (etiquetas)
- Exterior (garden) → siteRoot

### 2. Fix _storeBaseMeshPositions() (Líneas 909-920)

**Antes**: Guard `if (!_basePosByName[m.name])` prevenía actualización de posiciones existentes

```javascript
// ❌ ANTES: Guard bloqueaba updates tras normalizaciónif (!_basePosByName[m.name]) {
    _basePosByName[m.name] = { x: m.position.x, z: m.position.z };
}
```

**Después**: Siempre sobrescribir + agregar TransformNodes

```javascript
// ✅ DESPUÉS: Always overwrite — called after generateLayoutJS normalizationscene.meshes.forEach(m => {
    if (_ENV_NAMES.has(m.name) || m.name.startsWith('border_')) return;
    _basePosByName[m.name] = { x: m.position.x, z: m.position.z };
});
scene.transformNodes.forEach(n => {
    if (n.name.startsWith('lbl_node_')) {
        _basePosByName[n.name] = { x: n.position.x, z: n.position.z };
    }
});
```

### 3. Fix _applyHouseOffset() (Líneas 922-952)

**Nuevo comportamiento**:

```javascript
function _applyHouseOffset(dx, dz) {
    // Dispose tejado ANTES del for-loop — evita que se mueva por position
    if (typeof roofActive !== 'undefined' && roofActive) {
        if (roofMesh) { roofMesh.dispose(); roofMesh = null; }
        for (let _ri = 0; _ri < 4; _ri++) {
            const _rm = scene.getMeshByName('roof_' + _ri);
            if (_rm) _rm.dispose();
        }
    }
    
    // Snapshot any new meshes que aparecieron (roof, foundation, etc.)
    scene.meshes.forEach(m => {
        if (_ENV_NAMES.has(m.name) || m.name.startsWith('border_')) return;
        if (!_basePosByName[m.name]) {
            // Mesh appeared AFTER initial store — its current position already carries
            // the previous offset, so record base = current - previous offset
            _basePosByName[m.name] = {
                x: m.position.x - _houseOffsetX,
                z: m.position.z - _houseOffsetZ
            };
        }
    });
    
    // Mover meshes E TransformNodes
    for (const [nm, base] of Object.entries(_basePosByName)) {
        const m = scene.getMeshByName(nm);
        if (m) { 
            m.position.x = base.x + dx; 
            m.position.z = base.z + dz; 
            continue; 
        }
        const tn = scene.getTransformNodeByName(nm);
        if (tn) { 
            tn.position.x = base.x + dx; 
            tn.position.z = base.z + dz; 
        }
    }
    
    // Reconstruir tejado y paneles con offset correcto (vértices, no position)
    if (typeof roofActive !== 'undefined' && roofActive) {
        buildRoof(dx, dz);
        solarMeshes.forEach(m => {
            try { m.material && m.material.dispose(); m.dispose(); } catch(e) {}
        });
        solarMeshes = [];
        buildSolarPanels(dx, dz);
    }
}
```

**Cambios clave**:
- Manejar AMBOS meshes y TransformNodes en el for-loop
- Disponer tejado/paneles ANTES de mover (evita doble movimiento)
- Reconstruir roof y solar con el `dx, dz` actualizado

### 4. Fix rebuildScene() (Líneas 1277-1281)

**Después de reconstruir habitaciones**:

```javascript
// Re-sync base positions with rebuilt room positions, then re-apply current offset
_storeBaseMeshPositions();
if (_houseOffsetX !== 0 || _houseOffsetZ !== 0) {
    _applyHouseOffset(_houseOffsetX, _houseOffsetZ);
}
updateBudget();
```

**Propósito**: Cuando el usuario cambia dimensiones → rebuildScene reconstruye rooms → recaptura posiciones base → re-aplica offset actual

### 5. Fix buildRoof() (Líneas 1981-2010)

**Cambios**:

```javascript
function buildRoof(ox, oz) {
    ox = (ox !== undefined) ? ox : _houseOffsetX;
    oz = (oz !== undefined) ? oz : _houseOffsetZ;
    if (roofMesh) { roofMesh.dispose(); roofMesh = null; }
    
    const interiorZones = ['day','night','wet','circ','service'];
    const houseRooms = roomsData.filter(r => 
        interiorZones.includes((r.zone||'').toLowerCase())
    );
    if (houseRooms.length === 0) return;
    
    // ✅ NUEVO: Leer posición REAL de los suelos con getAbsolutePosition()
    let minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity;
    houseRooms.forEach(r => {
        const idx = roomsData.indexOf(r);
        const fl = scene.getMeshByName('floor_' + idx);
        if (!fl) return;
        const absPos = fl.getAbsolutePosition();  // ← WORLD COORDINATES
        minX = Math.min(minX, absPos.x - r.width / 2);
        minZ = Math.min(minZ, absPos.z - r.depth / 2);
        maxX = Math.max(maxX, absPos.x + r.width / 2);
        maxZ = Math.max(maxZ, absPos.z + r.depth / 2);
    });
    if (!isFinite(minX)) return;
    
    const hW = maxX - minX;
    const hD = maxZ - minZ;
    const hCX = minX + hW / 2;  // centro X real (con offset)
    const hCZ = minZ + hD / 2;  // centro Z real (con offset)
    // ... rest of roof construction uses minX, maxX, minZ, maxZ ...
}
```

**Por qué getAbsolutePosition()**:
- Floor meshes están parented a houseRoot
- Leer `floor.position` retorna posición LOCAL al padre (houseRoot)
- Necesitamos WORLD coordinates para construir roof correctamente
- `getAbsolutePosition()` retorna: parentPos + localPos

### 6. Fix buildSolarPanels() (Idéntico patrón)

Mismo cambio: `fl.position` → `fl.getAbsolutePosition()`

### 7. Integración en changeOverhang() + toggleRoof()

```javascript
function changeOverhang(val) {
    currentOverhang = parseFloat(val) / 10;
    if (roofActive) { buildRoof(_houseOffsetX, _houseOffsetZ); }  // ✅ Pasar offset
}

function toggleRoof() {
    if (roofActive) {
        // ...dispose...
    } else {
        buildRoof(_houseOffsetX, _houseOffsetZ);    // ✅ Pasar offset
        roofActive = true;
        // ...
        buildSolarPanels(_houseOffsetX, _houseOffsetZ);  // ✅ Pasar offset
    }
}
```

### 8. _ENV_NAMES Actualizado (Líneas 2096-2098)

```javascript
if (roofMesh) {
    _ENV_NAMES.add('roof');
    for (let _ri = 0; _ri < 4; _ri++) _ENV_NAMES.add('roof_' + _ri);
}
```

**Propósito**: Prevenir que roof sea movido nuevamente por _storeBaseMeshPositions o _applyHouseOffset (ya está reconstruido)

## Flujo de Ejecución

### Al mover slider "Posición en parcela":

1. **slider.oninput** → `_houseOffsetX = newValue` → `_applyHouseOffset(newX, newZ)`
2. **_applyHouseOffset()** hace:
   - Dispone roof/solar previos
   - Itera `_basePosByName` → mueve todos los meshes (floor, walls, doors, windows, labels)
   - Llama `buildRoof(dx, dz)` → lee posiciones REALES (world) de floors → construye nuevos vertices
   - Llama `buildSolarPanels(dx, dz)` → igual

### Al cambiar dimensión de habitación:

1. **applyDimensions()** → cambia roomsData[i].width/depth
2. Llama `rebuildScene(newLayout)` (o `generateLayoutJS` + rebuildScene)
3. **rebuildScene()**:
   - Dispone meshes antiguos
   - Reconstruye rooms con nuevas dimensiones
   - Llama `_storeBaseMeshPositions()` → captura NUEVAS posiciones base
   - Si `_houseOffsetX/Z ≠ 0` → llama `_applyHouseOffset()` → re-aplica offset
   - Llama `updateBudget()`

### Al togglear roof:

1. **toggleRoof()** → si ON: `buildRoof(_houseOffsetX, _houseOffsetZ)`
2. Aunque el slider esté en 0, el roof se construye con offset actual (por si cambió después)

## Pendientes (Secondary Issues)

Documentados pero NO resueltos en esta fase:

| Componente | Problema | Línea |
|-----------|----------|------|
| buildMEPLayers() | No sigue offset (usa roomsData.x/z directamente) | 1545+ |
| buildFoundation() | No sigue offset (usa roomsData.x/z directamente) | 2720+ |
| buildFence() | Nunca se mueve (usa constantes plotX/plotZ) | 1805+ |
| resetLayout() | No resetea `_houseOffsetX/Z` ni sliders | — |

Estos quedan para fase posterior (MEP visualization epic).

## Testing

✅ Sintaxis verificada  
⏳ **Local test pendiente**: Abrir editor 3D, mover sliders X/Z, verificar que tejado siga la casa  
⏳ **Verificar**: Solar panels, overhang changes, dimension edits, rebuild consistency

## Commits Relacionados

- `5273396` fix: eliminar posición parcela duplicada fuera del editor Babylon (antecesor)
- `c3509bf` fix: offset parcela — tejado/paneles sigan movimiento con jerarquía houseRoot
- `8435c74` refactor: usar getAbsolutePosition() en buildRoof/buildSolarPanels para coordenadas mundiales
