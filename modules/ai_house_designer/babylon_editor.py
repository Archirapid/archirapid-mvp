"""
Editor 3D avanzado usando Babylon.js
v3.0 - Panel numérico + paredes sincronizadas + CTE + GLB
"""

def generate_babylon_html(rooms_data, total_width, total_depth):
    """
    Genera HTML con Babylon.js editor

    Args:
        rooms_data: Lista de habitaciones con coordenadas
        total_width: Ancho total de la casa
        total_depth: Profundidad total de la casa

    Returns:
        str: HTML completo con Babylon.js
    """

    import json
    rooms_js = json.dumps(rooms_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ArchiRapid - Editor 3D</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; overflow: hidden; }}
        #renderCanvas {{ width: 100vw; height: 100vh; display: block; }}

        /* TOOLBAR IZQUIERDO */
        #toolbar {{
            position: absolute; top: 20px; left: 20px;
            background: rgba(0,0,0,0.88); padding: 14px;
            border-radius: 12px; color: white; min-width: 210px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        #toolbar h3 {{ margin: 0 0 10px 0; font-size: 14px; opacity: 0.8; }}
        .tool-btn {{
            display: block; width: 100%; padding: 8px 10px;
            margin: 4px 0; background: rgba(52,152,219,0.2);
            border: 1px solid rgba(52,152,219,0.5); color: white;
            border-radius: 6px; cursor: pointer; font-size: 13px;
            transition: background 0.2s;
        }}
        .tool-btn:hover {{ background: rgba(52,152,219,0.4); }}
        .tool-btn.active {{ background: rgba(52,152,219,0.7); border-color: #3498DB; }}
        .tool-btn.green {{ background: rgba(46,204,113,0.25); border-color: #2ECC71; }}
        .tool-btn.green:hover {{ background: rgba(46,204,113,0.45); }}
        hr.divider {{ margin: 8px 0; border: none; border-top: 1px solid rgba(255,255,255,0.15); }}

        /* PANEL NUMÉRICO DE EDICIÓN */
        #edit-panel {{
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: rgba(52,152,219,0.1);
            border: 1px solid rgba(52,152,219,0.4);
            border-radius: 8px;
        }}
        #edit-panel h4 {{ margin: 0 0 8px 0; font-size: 12px; color: #3498DB; }}
        #edit-panel label {{ font-size: 11px; opacity: 0.7; display: block; margin-top: 6px; }}
        #edit-panel input {{
            width: 100%; padding: 5px 8px; margin-top: 3px;
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px; color: white; font-size: 13px;
        }}
        #edit-panel input:focus {{ outline: none; border-color: #3498DB; }}
        #btn-apply {{
            display: block; width: 100%; padding: 7px;
            margin-top: 8px; background: rgba(46,204,113,0.3);
            border: 1px solid #2ECC71; color: white;
            border-radius: 5px; cursor: pointer; font-size: 13px;
        }}
        #btn-apply:hover {{ background: rgba(46,204,113,0.55); }}

        /* CTE SEMÁFORO */
        #cte-status {{
            margin-top: 8px; padding: 6px 8px;
            border-radius: 6px; font-size: 11px;
            display: none;
        }}
        #cte-status.ok {{ background: rgba(46,204,113,0.2); border: 1px solid #2ECC71; color: #2ECC71; }}
        #cte-status.warn {{ background: rgba(230,126,34,0.2); border: 1px solid #E67E22; color: #E67E22; }}
        #cte-status.fail {{ background: rgba(231,76,60,0.2); border: 1px solid #E74C3C; color: #E74C3C; }}

        /* PANEL INFO DERECHO */
        #info-panel {{
            position: absolute; top: 20px; right: 20px;
            background: rgba(0,0,0,0.88); padding: 14px;
            border-radius: 12px; color: white; width: 230px;
            border: 1px solid rgba(52,152,219,0.3);
        }}
        #info-panel h3 {{ margin: 0 0 8px 0; color: #3498DB; font-size: 14px; }}
        #room-info p {{ margin: 4px 0; font-size: 12px; }}

        /* PANEL PRESUPUESTO */
        #budget-panel {{
            position: absolute; top: 260px; right: 20px;
            background: rgba(46,204,113,0.12); padding: 12px;
            border-radius: 8px; color: white; width: 230px;
            border: 2px solid #2ECC71;
        }}
        #budget-panel h3 {{ margin: 0 0 6px 0; color: #2ECC71; font-size: 14px; }}
        #budget-info p {{ margin: 3px 0; font-size: 12px; }}

        /* PANEL AVISO */
        #warning-panel {{
            position: absolute; bottom: 20px; right: 20px;
            background: rgba(230,126,34,0.12); padding: 10px;
            border-radius: 8px; color: white; width: 230px;
            border: 2px solid #E67E22;
        }}
        #warning-panel h3 {{ margin: 0 0 6px 0; color: #E67E22; font-size: 13px; }}
        #warning-panel p {{ font-size: 11px; line-height: 1.5; margin: 3px 0; }}
    </style>
    <script src="https://cdn.babylonjs.com/babylon.js"></script>
    <script src="https://cdn.babylonjs.com/gui/babylon.gui.min.js"></script>
    <script src="https://cdn.babylonjs.com/materialsLibrary/babylonjs.materials.min.js"></script>
    <script src="https://cdn.babylonjs.com/serializers/babylonjs.serializers.min.js"></script>
</head>
<body>
    <canvas id="renderCanvas"></canvas>

    <!-- TOOLBAR IZQUIERDO -->
    <div id="toolbar">
        <h3>🛠️ Herramientas</h3>
        <button class="tool-btn active" id="btn-select" onclick="setMode('select')">🖱️ Seleccionar</button>
        <button class="tool-btn" id="btn-move"   onclick="setMode('move')">↔️ Mover habitación</button>
        <button class="tool-btn" id="btn-scale"  onclick="setMode('scale')">📐 Editar dimensiones</button>
        <button class="tool-btn" id="btn-wall"   onclick="setMode('wall')">🏗️ Cerramiento Finca</button>
        <hr class="divider">
        <button class="tool-btn" onclick="setTopView()">🔝 Vista Planta</button>
        <button class="tool-btn" onclick="setIsoView()">🏠 Vista 3D</button>
        <hr class="divider">
        <button class="tool-btn green" onclick="saveChanges()">💾 Guardar JSON</button>
        <button class="tool-btn green" id="btn-glb" onclick="exportGLB()">📦 Exportar 3D (.glb)</button>

        <!-- PANEL NUMÉRICO — aparece al seleccionar en modo Editar dimensiones -->
        <div id="edit-panel">
            <h4>✏️ Editar dimensiones</h4>
            <div id="edit-room-name" style="font-size:12px; font-weight:bold; margin-bottom:4px;"></div>
            <label>Ancho (m)</label>
            <input type="number" id="input-width" min="1" max="20" step="0.1">
            <label>Fondo (m)</label>
            <input type="number" id="input-depth" min="1" max="20" step="0.1">
            <button id="btn-apply" onclick="applyDimensions()">✅ Aplicar</button>
            <div id="cte-status"></div>
        </div>
    </div>

    <!-- PANEL INFO DERECHO -->
    <div id="info-panel">
        <h3>📊 Info Habitación</h3>
        <div id="room-info">
            <p style="color:#888;">Selecciona una habitación</p>
        </div>
    </div>

    <!-- PANEL PRESUPUESTO -->
    <div id="budget-panel">
        <h3>💰 Presupuesto</h3>
        <div id="budget-info">
            <p><strong>Superficie:</strong> <span id="total-area">0</span> m²</p>
            <p><strong>Coste aprox:</strong> <span id="total-cost">€0</span></p>
            <p style="font-size:11px; color:#888; margin-top:4px;" id="budget-diff"></p>
        </div>
    </div>

    <!-- PANEL AVISO -->
    <div id="warning-panel">
        <h3>⚠️ Importante</h3>
        <p>Los cambios requieren <strong>validación por arquitecto</strong> antes de construcción.</p>
        <p style="color:#E67E22; margin-top:4px;">⚠️ No garantizan cumplimiento CTE</p>
    </div>

    <script>
        // ================================================
        // DATOS
        // ================================================
        const roomsData = {rooms_js};
        const totalWidth = {total_width};
        const totalDepth = {total_depth};
        const WALL_H = 2.7;
        const WALL_T = 0.15;
        const COST_PER_M2 = 1500;

        // Mínimos CTE por tipo de habitación (m²)
        const CTE_MIN = {{
            'salon': 14, 'cocina': 6, 'dormitorio_principal': 10,
            'dormitorio': 6, 'bano': 2.5, 'aseo': 1.5,
            'pasillo': 0, 'garaje': 12, 'porche': 0,
            'distribuidor': 0, 'piscina': 0, 'huerto': 0
        }};

        // ================================================
        // ESCENA
        // ================================================
        const canvas = document.getElementById('renderCanvas');
        const engine = new BABYLON.Engine(canvas, true);
        const scene  = new BABYLON.Scene(engine);
        scene.clearColor = new BABYLON.Color4(0.1, 0.1, 0.18, 1);

        // Cámara isométrica
        const camera = new BABYLON.ArcRotateCamera(
            "cam", Math.PI/4, Math.PI/3.2, Math.max(totalWidth, totalDepth) * 2.2,
            new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2), scene
        );
        camera.attachControl(canvas, true);
        camera.lowerRadiusLimit = 5;
        camera.upperRadiusLimit = 80;

        // Luces
        const hemi = new BABYLON.HemisphericLight("hemi", new BABYLON.Vector3(0,1,0), scene);
        hemi.intensity = 0.85;
        const dirLight = new BABYLON.DirectionalLight("dir", new BABYLON.Vector3(-1,-2,-1), scene);
        dirLight.intensity = 0.4;

        // Suelo verde
        const ground = BABYLON.MeshBuilder.CreateGround("ground", {{
            width: totalWidth + 30, height: totalDepth + 30
        }}, scene);
        const groundMat = new BABYLON.StandardMaterial("gMat", scene);
        groundMat.diffuseColor = new BABYLON.Color3(0.42, 0.68, 0.42);
        ground.material = groundMat;

        // Grid 1m
        const gridSize = Math.max(totalWidth, totalDepth) + 20;
        const gridMat = new BABYLON.GridMaterial("gridMat", scene);
        gridMat.majorUnitFrequency = 5;
        gridMat.minorUnitVisibility = 0.45;
        gridMat.gridRatio = 1;
        gridMat.mainColor  = new BABYLON.Color3(1,1,1);
        gridMat.lineColor  = new BABYLON.Color3(0.3,0.5,0.7);
        gridMat.opacity    = 0.55;
        gridMat.backFaceCulling = false;
        const gridPlane = BABYLON.MeshBuilder.CreateGround("gridPlane",
            {{width: gridSize, height: gridSize}}, scene);
        gridPlane.material  = gridMat;
        gridPlane.position.y = 0.01;
        gridPlane.isPickable = false;

        // ================================================
        // HIGHLIGHT
        // ================================================
        const hlLayer = new BABYLON.HighlightLayer("hl", scene);

        // ================================================
        // CONSTRUIR HABITACIONES
        // ================================================
        // roomsData[i] → suelo + 4 paredes + etiqueta
        // Guardamos referencias para reconstruir paredes

        function buildRoom(i) {{
            const room = roomsData[i];
            const rx = room.x, rz = room.z, rw = room.width, rd = room.depth;

            // Suelo
            const floor = BABYLON.MeshBuilder.CreateBox(`floor_${{i}}`, {{
                width: rw - 0.05, height: 0.06, depth: rd - 0.05
            }}, scene);
            floor.position.set(rx + rw/2, 0.03, rz + rd/2);
            const fMat = new BABYLON.StandardMaterial(`fMat_${{i}}`, scene);

            // Color por zona
            const zone = (room.zone || '').toLowerCase();
            if (zone === 'day')        fMat.diffuseColor = new BABYLON.Color3(0.96, 0.94, 0.88);
            else if (zone === 'night') fMat.diffuseColor = new BABYLON.Color3(0.88, 0.93, 0.98);
            else if (zone === 'wet')   fMat.diffuseColor = new BABYLON.Color3(0.85, 0.95, 0.98);
            else if (zone === 'exterior' || zone === 'garden')
                                        fMat.diffuseColor = new BABYLON.Color3(0.75, 0.90, 0.70);
            else                        fMat.diffuseColor = new BABYLON.Color3(0.94, 0.93, 0.90);

            floor.material = fMat;

            // Paredes
            _buildWalls(i, rx, rz, rw, rd);

            // Etiqueta
            _buildLabel(i, rx, rz, rw, rd);
        }}

        function _buildWalls(i, rx, rz, rw, rd) {{
            const wMat = new BABYLON.StandardMaterial(`wMat_${{i}}`, scene);
            wMat.diffuseColor = new BABYLON.Color3(0.18, 0.25, 0.32);

            // Trasera (z-)
            const bw = BABYLON.MeshBuilder.CreateBox(`wall_back_${{i}}`,
                {{width: rw, height: WALL_H, depth: WALL_T}}, scene);
            bw.position.set(rx+rw/2, WALL_H/2, rz);
            bw.material = wMat;

            // Frontal (z+) semi-transparente
            const fw = BABYLON.MeshBuilder.CreateBox(`wall_front_${{i}}`,
                {{width: rw, height: WALL_H, depth: WALL_T}}, scene);
            fw.position.set(rx+rw/2, WALL_H/2, rz+rd);
            const fwMat = wMat.clone(`fwMat_${{i}}`);
            fwMat.alpha = 0.28;
            fw.material = fwMat;

            // Izquierda
            const lw = BABYLON.MeshBuilder.CreateBox(`wall_left_${{i}}`,
                {{width: WALL_T, height: WALL_H, depth: rd}}, scene);
            lw.position.set(rx, WALL_H/2, rz+rd/2);
            lw.material = wMat;

            // Derecha
            const rw_ = BABYLON.MeshBuilder.CreateBox(`wall_right_${{i}}`,
                {{width: WALL_T, height: WALL_H, depth: rd}}, scene);
            rw_.position.set(rx+rw, WALL_H/2, rz+rd/2);
            rw_.material = wMat;
        }}

        function _disposeWalls(i) {{
            // Eliminar paredes
            ['wall_back_','wall_front_','wall_left_','wall_right_'].forEach(prefix => {{
                const m = scene.getMeshByName(prefix + i);
                if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
            }});
            // Eliminar materiales huérfanos de esta habitación
            ['wMat_','fwMat_'].forEach(prefix => {{
                const mat = scene.getMaterialByName(prefix + i);
                if (mat) mat.dispose();
            }});
        }}

        function _buildLabel(i, rx, rz, rw, rd) {{
            const oldLabel = scene.getMeshByName(`label_${{i}}`);
            if (oldLabel) oldLabel.dispose();

            const label = BABYLON.MeshBuilder.CreatePlane(`label_${{i}}`,
                {{width: 2.0, height: 1.1}}, scene);
            label.position.set(rx+rw/2, WALL_H + 1.4, rz+rd/2);
            label.billboardMode = BABYLON.Mesh.BILLBOARDMODE_ALL;
            label.isPickable = false;

            const adv = BABYLON.GUI.AdvancedDynamicTexture.CreateForMesh(label);
            const bg  = new BABYLON.GUI.Rectangle();
            bg.width = 1; bg.height = 1;
            bg.background = "rgba(20,30,45,0.82)";
            bg.cornerRadius = 18;
            adv.addControl(bg);

            const txt = new BABYLON.GUI.TextBlock();
            const room = roomsData[i];
            const area = (rw * rd).toFixed(1);
            txt.text = `${{room.name}}\\n${{rw.toFixed(1)}}m × ${{rd.toFixed(1)}}m\\n${{area}} m²`;
            txt.color = "#FFFFFF";
            txt.fontSize = 44;
            txt.fontWeight = "600";
            txt.lineSpacing = "6px";
            bg.addControl(txt);
        }}

        // Construir todas las habitaciones
        roomsData.forEach((_, i) => buildRoom(i));

        // Área original para presupuesto
        let originalTotalArea = roomsData.reduce((s, r) => s + (r.area_m2 || 0), 0);

        // ================================================
        // GIZMO — solo para MOVER
        // ================================================
        const gizmoManager = new BABYLON.GizmoManager(scene);
        gizmoManager.positionGizmoEnabled = false;
        gizmoManager.rotationGizmoEnabled = false;
        gizmoManager.scaleGizmoEnabled    = false;

        let selectedMesh  = null;
        let selectedIndex = null;
        let currentMode   = 'select';

        // ================================================
        // SELECCIÓN POR CLICK
        // ================================================
        scene.onPointerDown = function(evt, pickResult) {{
            if (currentMode === 'wall') return; // el modo wall tiene su propio handler

            if (!pickResult.hit) return;
            const mesh = pickResult.pickedMesh;
            if (!mesh) return;

            // Solo seleccionar suelos y paredes de habitaciones
            const isFloor = mesh.name.startsWith('floor_');
            const isWall  = mesh.name.startsWith('wall_');
            if (!isFloor && !isWall) return;

            // Extraer índice
            const parts = mesh.name.split('_');
            const idx = parseInt(parts[parts.length - 1]);
            if (isNaN(idx)) return;

            selectedMesh  = scene.getMeshByName(`floor_${{idx}}`);
            selectedIndex = idx;

            // Highlight
            hlLayer.removeAllMeshes();
            hlLayer.addMesh(selectedMesh, BABYLON.Color3.Yellow());

            updateRoomInfo(idx);

            // Si estamos en modo mover, enganchar gizmo
            if (currentMode === 'move') {{
                gizmoManager.attachToMesh(selectedMesh);
                gizmoManager.positionGizmoEnabled = true;
                gizmoManager.gizmos.positionGizmo.xGizmo.isEnabled = true;
                gizmoManager.gizmos.positionGizmo.yGizmo.isEnabled = false;
                gizmoManager.gizmos.positionGizmo.zGizmo.isEnabled = true;
            }}

            // Si estamos en modo scale, mostrar panel numérico
            if (currentMode === 'scale') {{
                showEditPanel(idx);
            }}
        }};

        // ================================================
        // MODOS
        // ================================================
        function setMode(mode) {{
            currentMode = mode;

            // Reset visual botones
            document.querySelectorAll('.tool-btn').forEach(b =>
                b.classList.remove('active'));

            // Desconectar gizmo
            gizmoManager.positionGizmoEnabled = false;
            gizmoManager.scaleGizmoEnabled    = false;
            gizmoManager.attachToMesh(null);

            // Ocultar panel edición
            document.getElementById('edit-panel').style.display = 'none';
            document.getElementById('cte-status').style.display = 'none';

            if (mode === 'select') {{
                document.getElementById('btn-select').classList.add('active');

            }} else if (mode === 'move') {{
                document.getElementById('btn-move').classList.add('active');
                if (selectedMesh && selectedIndex !== null) {{
                    gizmoManager.attachToMesh(selectedMesh);
                    gizmoManager.positionGizmoEnabled = true;
                    gizmoManager.gizmos.positionGizmo.xGizmo.isEnabled = true;
                    gizmoManager.gizmos.positionGizmo.yGizmo.isEnabled = false;
                    gizmoManager.gizmos.positionGizmo.zGizmo.isEnabled = true;
                    // Al soltar, actualizar paredes y label
                    gizmoManager.gizmos.positionGizmo.onDragEndObservable.clear();
                    gizmoManager.gizmos.positionGizmo.onDragEndObservable.add(() => {{
                        syncWallsToFloor(selectedIndex);
                        updateRoomInfo(selectedIndex);
                        updateBudget();
                    }});
                }} else {{
                    showToast('Primero selecciona una habitación');
                    setMode('select');
                }}

            }} else if (mode === 'scale') {{
                document.getElementById('btn-scale').classList.add('active');
                if (selectedIndex !== null) {{
                    showEditPanel(selectedIndex);
                }} else {{
                    showToast('Primero selecciona una habitación');
                    setMode('select');
                }}

            }} else if (mode === 'wall') {{
                document.getElementById('btn-wall').classList.add('active');
                startWallMode();
            }}
        }}

        // ================================================
        // SINCRONIZAR PAREDES AL SUELO (tras mover)
        // ================================================
        function syncWallsToFloor(i) {{
            const floor = scene.getMeshByName(`floor_${{i}}`);
            if (!floor) return;
            const bounds = floor.getBoundingInfo().boundingBox;
            const rx = bounds.minimumWorld.x;
            const rz = bounds.minimumWorld.z;
            const rw = bounds.maximumWorld.x - rx;
            const rd = bounds.maximumWorld.z - rz;

            // Actualizar roomsData
            roomsData[i].x = rx;
            roomsData[i].z = rz;
            roomsData[i].width = rw;
            roomsData[i].depth = rd;

            _disposeWalls(i);
            _buildWalls(i, rx, rz, rw, rd);
            _buildLabel(i, rx, rz, rw, rd);
        }}

        // ================================================
        // MOTOR LAYOUT JS — puerto de architec_layout.py
        // Redistribuye toda la planta sin colisiones
        // ================================================
        function classifyZone(code, name) {{
            const c = (code + name).toLowerCase();
            if (['piscin','pool','huerto','caseta','apero','panel','solar','bomba'].some(x => c.includes(x))) return 'garden';
            if (['porche','terraza'].some(x => c.includes(x))) return 'exterior';
            if (['garaje','garage','bodega'].some(x => c.includes(x))) return 'service';
            if (['pasillo','distribuidor','hall','recibidor'].some(x => c.includes(x))) return 'circ';
            if (['bano','baño','aseo','wc'].some(x => c.includes(x))) return 'wet';
            if (['dormitorio','habitacion','suite'].some(x => c.includes(x))) return 'night';
            return 'day';
        }}

        function generateLayoutJS(rooms) {{
            const FILA1_D = 4.5, FILA3_D = 3.5, PASILLO_H = 1.2;
            const rs = rooms.map(r => ({{
                ...r,
                area: Math.max(r.area_m2 || 2, 2),
                zone: r.zone || classifyZone(r.code||'', r.name||'')
            }}));
            const day   = rs.filter(r => r.zone === 'day');
            const night = rs.filter(r => r.zone === 'night').sort((a,b) => b.area - a.area);
            const wet   = rs.filter(r => r.zone === 'wet');
            const svc   = rs.filter(r => r.zone === 'service');
            const ext   = rs.filter(r => r.zone === 'exterior');
            const gdn   = rs.filter(r => r.zone === 'garden');
            const garajes   = svc.filter(r => (r.code||'').toLowerCase().includes('garaje') || (r.code||'').toLowerCase().includes('garage'));
            const otrosSvc  = svc.filter(r => !garajes.includes(r));
            const piscinas  = gdn.filter(r => (r.code||'').toLowerCase().includes('piscin') || (r.code||'').toLowerCase().includes('pool'));
            const laterales = gdn.filter(r => !piscinas.includes(r));
            const layout = [];
            // Ancho casa desde fila noche
            const nightW = night.map(r => Math.max(Math.round(r.area/FILA3_D*10)/10, 2.8));
            const banoW  = wet.map(r => Math.min(Math.max(Math.round(r.area/FILA3_D*10)/10, 1.5), 2.5));
            const fila3 = [];
            let bi = 0;
            for (let i=0; i<night.length; i++) {{
                if (bi < wet.length) {{ fila3.push({{r:wet[bi], w:banoW[bi], d:FILA3_D}}); bi++; }}
                fila3.push({{r:night[i], w:nightW[i], d:FILA3_D}});
            }}
            while (bi < wet.length) {{ fila3.push({{r:wet[bi], w:banoW[bi], d:FILA3_D}}); bi++; }}
            let houseW = Math.min(Math.max(fila3.reduce((s,i)=>s+i.w,0), 8), 18);
            // Fila 1: día + garaje
            let garajeW = 0;
            const garajeItems = garajes.map(r => {{ const gw=Math.max(Math.round(r.area/FILA1_D*10)/10,3.5); garajeW+=gw; return {{r,w:gw}}; }});
            const dayAvail = Math.max(houseW - garajeW, 5);
            const dayTotal = day.reduce((s,r)=>s+r.area,0) || 1;
            let xd = 0;
            day.forEach((r,idx) => {{
                let w = idx===day.length-1 ? Math.max(dayAvail-xd,3) : Math.max(Math.round(dayAvail*(r.area/dayTotal)*10)/10,3);
                layout.push({{x:xd, z:0, width:w, depth:FILA1_D, name:r.name, code:r.code, zone:r.zone, area_m2:r.area}});
                xd += w;
            }});
            let xo = xd;
            otrosSvc.forEach(r => {{ const w=Math.max(Math.round(r.area/FILA1_D*10)/10,2); layout.push({{x:xo,z:0,width:w,depth:FILA1_D,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); xo+=w; }});
            let xg = houseW - garajeW;
            garajeItems.forEach(item => {{ layout.push({{x:xg,z:0,width:item.w,depth:FILA1_D,name:item.r.name,code:item.r.code,zone:item.r.zone,area_m2:item.r.area}}); xg+=item.w; }});
            // Pasillo
            const pasilloR = rs.find(r=>r.zone==='circ');
            layout.push({{x:0, z:FILA1_D, width:houseW, depth:PASILLO_H, name:pasilloR?pasilloR.name:'Distribuidor', code:pasilloR?pasilloR.code:'pasillo', zone:'circ', area_m2:houseW*PASILLO_H}});
            // Fila 3: noche
            const zF3 = FILA1_D + PASILLO_H;
            let xc = 0;
            fila3.forEach(item => {{ layout.push({{x:xc,z:zF3,width:item.w,depth:item.d,name:item.r.name,code:item.r.code,zone:item.r.zone,area_m2:item.r.area}}); xc+=item.w; }});
            const zBot = zF3 + FILA3_D;
            // Porche
            ext.forEach(r => {{ const d=Math.max(Math.round(r.area/houseW*10)/10,2); layout.push({{x:0,z:zBot,width:houseW,depth:d,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); }});
            // Piscina
            piscinas.forEach(r => {{ const pw=Math.max(Math.round(Math.sqrt(r.area*2)*10)/10,5); const pd=Math.round(r.area/pw*10)/10; layout.push({{x:(houseW-pw)/2,z:-pd-3,width:pw,depth:pd,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); }});
            // Laterales
            let xl=houseW+3, zl=0;
            laterales.forEach(r => {{ const lw=Math.round(Math.sqrt(r.area*1.3)*10)/10; const ld=Math.round(r.area/lw*10)/10; layout.push({{x:xl,z:zl,width:lw,depth:ld,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); zl+=ld+1; }});
            // Normalizar
            if (layout.length > 0) {{
                const minX = Math.min(...layout.map(i=>i.x));
                const minZ = Math.min(...layout.map(i=>i.z));
                const ox = Math.max(0,-minX)+2, oz = Math.max(0,-minZ)+2;
                layout.forEach(i => {{ i.x+=ox; i.z+=oz; }});
            }}
            return layout;
        }}

        function rebuildScene(newLayout) {{
            // Eliminar todos los meshes de habitaciones
            roomsData.forEach((_,i) => {{
                ['floor','wall_back','wall_front','wall_left','wall_right','door','label'].forEach(prefix => {{
                    const m = scene.getMeshByName(`${{prefix}}_${{i}}`);
                    if (m) m.dispose();
                }});
            }});
            hlLayer.removeAllMeshes();
            // Actualizar roomsData con nueva geometría
            newLayout.forEach((item, i) => {{
                if (roomsData[i]) {{
                    roomsData[i].x = item.x;
                    roomsData[i].z = item.z;
                    roomsData[i].width = item.width;
                    roomsData[i].depth = item.depth;
                    roomsData[i].area_m2 = item.area_m2;
                }}
            }});
            // Reconstruir todos
            roomsData.forEach((_,i) => buildRoom(i));
            selectedMesh = null;
            selectedIndex = null;
            updateBudget();
            showToast('✅ Planta redistribuida sin colisiones');
        }}

        // ================================================
        // PANEL NUMÉRICO — EDITAR DIMENSIONES
        // ================================================
        function showEditPanel(i) {{
            const room = roomsData[i];
            document.getElementById('edit-room-name').textContent = room.name;
            document.getElementById('input-width').value = room.width.toFixed(2);
            document.getElementById('input-depth').value = room.depth.toFixed(2);
            document.getElementById('edit-panel').style.display = 'block';
            checkCTE(i, room.width, room.depth);
        }}

        function applyDimensions() {{
            if (selectedIndex === null) return;
            const newW = parseFloat(document.getElementById('input-width').value);
            const newD = parseFloat(document.getElementById('input-depth').value);
            if (isNaN(newW) || isNaN(newD) || newW < 0.5 || newD < 0.5) {{
                showToast('Dimensiones no válidas (mínimo 0.5m)');
                return;
            }}
            // Actualizar área de la habitación seleccionada
            roomsData[selectedIndex].area_m2 = parseFloat((newW * newD).toFixed(2));
            // Regenerar layout completo y reconstruir escena
            const newLayout = generateLayoutJS(roomsData);
            rebuildScene(newLayout);
            // Validar CTE de la habitación que se editó
            checkCTE(selectedIndex, newW, newD);
        }}

        // ================================================
        // VALIDACIÓN CTE
        // ================================================
        function checkCTE(i, w, d) {{
            const room  = roomsData[i];
            const code  = (room.code || room.name || '').toLowerCase();
            const area  = w * d;
            const minW  = 2.5; // ancho mínimo CTE cualquier habitación habitable

            let minArea = 0;
            for (const key in CTE_MIN) {{
                if (code.includes(key)) {{ minArea = CTE_MIN[key]; break; }}
            }}

            const cteEl = document.getElementById('cte-status');
            cteEl.style.display = 'block';

            if (area < minArea) {{
                cteEl.className = 'fail';
                cteEl.textContent = `❌ CTE: mínimo ${{minArea}}m² para ${{room.name}} (actual ${{area.toFixed(1)}}m²)`;
            }} else if (w < minW && minArea > 0) {{
                cteEl.className = 'warn';
                cteEl.textContent = `⚠️ Ancho mínimo CTE: 2.5m (actual ${{w.toFixed(2)}}m)`;
            }} else if (area < minArea * 1.1 && minArea > 0) {{
                cteEl.className = 'warn';
                cteEl.textContent = `⚠️ Cerca del mínimo CTE: ${{minArea}}m²`;
            }} else {{
                cteEl.className = 'ok';
                cteEl.textContent = `✅ Cumple CTE (${{area.toFixed(1)}}m²)`;
            }}
        }}

        // ================================================
        // ACTUALIZAR PANEL INFO
        // ================================================
        function updateRoomInfo(i) {{
            const floor = scene.getMeshByName(`floor_${{i}}`);
            if (!floor) return;
            const bounds = floor.getBoundingInfo().boundingBox;
            const w = bounds.maximumWorld.x - bounds.minimumWorld.x;
            const d = bounds.maximumWorld.z - bounds.minimumWorld.z;
            const area = w * d;
            const room = roomsData[i];

            document.getElementById('room-info').innerHTML = `
                <p><strong style="color:#3498DB;">${{room.name}}</strong></p>
                <p>📐 Ancho: <strong>${{w.toFixed(2)}}m</strong></p>
                <p>📐 Fondo: <strong>${{d.toFixed(2)}}m</strong></p>
                <p>📦 Área: <strong>${{area.toFixed(1)}}m²</strong></p>
                <p style="color:#888; font-size:11px;">Original: ${{room.area_m2}}m²</p>
            `;
        }}

        // ================================================
        // PRESUPUESTO
        // ================================================
        function updateBudget() {{
            let total = 0;
            roomsData.forEach((r, i) => {{
                const f = scene.getMeshByName(`floor_${{i}}`);
                if (f) {{
                    const b = f.getBoundingInfo().boundingBox;
                    total += (b.maximumWorld.x - b.minimumWorld.x) *
                             (b.maximumWorld.z - b.minimumWorld.z);
                }}
            }});
            const cost = total * COST_PER_M2;
            const origCost = originalTotalArea * COST_PER_M2;
            const diff = cost - origCost;
            document.getElementById('total-area').textContent = total.toFixed(1);
            document.getElementById('total-cost').textContent =
                '€' + cost.toLocaleString('es-ES', {{maximumFractionDigits:0}});
            const de = document.getElementById('budget-diff');
            if (Math.abs(diff) > 100) {{
                const sign = diff > 0 ? '+' : '';
                de.textContent = `${{sign}}€${{diff.toLocaleString('es-ES',{{maximumFractionDigits:0}})}} vs original`;
                de.style.color = diff > 0 ? '#E67E22' : '#2ECC71';
            }} else {{
                de.textContent = 'Sin cambios significativos';
                de.style.color = '#888';
            }}
        }}
        updateBudget();

        // ================================================
        // VISTAS CÁMARA
        // ================================================
        function setTopView() {{
            camera.setPosition(new BABYLON.Vector3(totalWidth/2, Math.max(totalWidth,totalDepth)*1.6, totalDepth/2));
            camera.setTarget(new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2));
        }}
        function setIsoView() {{
            camera.alpha  = Math.PI/4;
            camera.beta   = Math.PI/3.2;
            camera.radius = Math.max(totalWidth, totalDepth) * 2.2;
            camera.setTarget(new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2));
        }}

        // ================================================
        // GUARDAR JSON (cable intacto con Python)
        // ================================================
        function saveChanges() {{
            const layout = [];
            roomsData.forEach((room, i) => {{
                const floor = scene.getMeshByName(`floor_${{i}}`);
                if (floor) {{
                    const b = floor.getBoundingInfo().boundingBox;
                    const w = b.maximumWorld.x - b.minimumWorld.x;
                    const d = b.maximumWorld.z - b.minimumWorld.z;
                    layout.push({{
                        index: i,
                        name:  room.name,
                        original_area: room.area_m2,
                        x: parseFloat(b.minimumWorld.x.toFixed(2)),
                        z: parseFloat(b.minimumWorld.z.toFixed(2)),
                        width: parseFloat(w.toFixed(2)),
                        depth: parseFloat(d.toFixed(2)),
                        new_area: parseFloat((w*d).toFixed(2))
                    }});
                }}
            }});

            // Añadir tabiques custom si existen
            if (window.customWalls && window.customWalls.length > 0) {{
                layout.push({{
                    index: 'custom_walls',
                    name: 'Tabiques personalizados',
                    custom_walls: window.customWalls,
                    original_area: 0, new_area: 0
                }});
            }}

            const json = JSON.stringify(layout, null, 2);
            const blob = new Blob([json], {{type:'application/json'}});
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href     = url;
            a.download = 'archirapid_layout_modificado.json';
            a.click();

            showToast('✅ JSON guardado. Súbelo en Documentación (Paso 4)');
        }}

        // ================================================
        // EXPORTAR GLB
        // ================================================
        function exportGLB() {{
            showToast('⏳ Generando modelo 3D...');
            BABYLON.GLTF2Export.GLBAsync(scene, "archirapid_modelo3d", {{
                shouldExportNode: (node) => {{
                    // Excluir suelo, grid y cámara — solo exportar habitaciones
                    const n = node.name || '';
                    return !n.startsWith('ground') && !n.startsWith('gridPlane') &&
                           !n.startsWith('cam') && !n.startsWith('hemi') &&
                           !n.startsWith('dir') && !n.startsWith('label');
                }}
            }}).then(glb => {{
                glb.downloadFiles();
                showToast('✅ Modelo 3D descargado (.glb)');
            }}).catch(err => {{
                console.error('GLB error:', err);
                showToast('⚠️ Error exportando GLB: ' + err.message);
            }});
        }}

        // ================================================
        // MODO CERRAMIENTO FINCA (tabiques libres)
        // ================================================
        window.customWalls = [];

        function startWallMode() {{
            let wallPoint1 = null;
            let marker1    = null;
            const infoDiv  = document.getElementById('room-info');

            infoDiv.innerHTML = '<p style="color:#E67E22;"><strong>🏗️ Cerramiento</strong></p>'
                + '<p>Click 1: punto inicio</p><p>Click 2: punto fin</p>';

            const origDown = scene.onPointerDown;

            scene.onPointerDown = function(evt, pick) {{
                if (currentMode !== 'wall') {{
                    scene.onPointerDown = origDown; return;
                }}
                const ray  = scene.createPickingRay(scene.pointerX, scene.pointerY,
                                 BABYLON.Matrix.Identity(), camera);
                const hit  = scene.pickWithRay(ray,
                                 m => m.name === 'ground' || m.name === 'gridPlane');
                const pt   = (hit && hit.hit) ? hit.pickedPoint
                           : (pick.hit ? pick.pickedPoint : null);
                if (!pt) return;

                if (!wallPoint1) {{
                    wallPoint1 = pt.clone();
                    if (marker1) marker1.dispose();
                    marker1 = BABYLON.MeshBuilder.CreateSphere('wm1', {{diameter:0.28}}, scene);
                    marker1.position = wallPoint1.clone();
                    marker1.position.y = 0.14;
                    const mm = new BABYLON.StandardMaterial('mmMat', scene);
                    mm.diffuseColor  = new BABYLON.Color3(1,0.2,0.2);
                    mm.emissiveColor = new BABYLON.Color3(0.5,0.1,0.1);
                    marker1.material = mm;
                    infoDiv.innerHTML = '<p style="color:#E67E22;"><strong>🏗️ Punto 1 marcado</strong></p>'
                        + '<p>Ahora click en punto final</p>';
                }} else {{
                    const pt2  = pt.clone();
                    const dx   = pt2.x - wallPoint1.x;
                    const dz   = pt2.z - wallPoint1.z;
                    const len  = Math.sqrt(dx*dx + dz*dz);
                    const ang  = Math.atan2(dx, dz);
                    if (len > 0.3) {{
                        const wid = 'cwall_' + window.customWalls.length;
                        const cw  = BABYLON.MeshBuilder.CreateBox(wid,
                            {{width:len, height:WALL_H, depth:WALL_T}}, scene);
                        cw.position.x = (wallPoint1.x + pt2.x)/2;
                        cw.position.y = WALL_H/2;
                        cw.position.z = (wallPoint1.z + pt2.z)/2;
                        cw.rotation.y = ang;
                        const cm = new BABYLON.StandardMaterial(wid+'m', scene);
                        cm.diffuseColor = new BABYLON.Color3(0.65,0.45,0.25);
                        cw.material = cm;
                        window.customWalls.push({{
                            id: wid,
                            x1: wallPoint1.x, z1: wallPoint1.z,
                            x2: pt2.x, z2: pt2.z,
                            length: parseFloat(len.toFixed(2))
                        }});
                        infoDiv.innerHTML = '<p style="color:#2ECC71;">✅ Tabique creado: '
                            + len.toFixed(1) + 'm</p><p>Click para otro</p>';
                    }}
                    if (marker1) {{ marker1.dispose(); marker1 = null; }}
                    wallPoint1 = null;
                }}
            }};
        }}

        // ================================================
        // TOAST (mensajes flotantes)
        // ================================================
        function showToast(msg) {{
            let t = document.getElementById('toast');
            if (!t) {{
                t = document.createElement('div');
                t.id = 'toast';
                t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);'
                    + 'background:rgba(0,0,0,0.85);color:white;padding:10px 20px;'
                    + 'border-radius:20px;font-size:13px;z-index:9999;pointer-events:none;'
                    + 'transition:opacity 0.3s;';
                document.body.appendChild(t);
            }}
            t.textContent = msg;
            t.style.opacity = '1';
            clearTimeout(window._toastTimer);
            window._toastTimer = setTimeout(() => t.style.opacity = '0', 3000);
        }}

        // ================================================
        // RENDER LOOP
        // ================================================
        engine.runRenderLoop(() => scene.render());
        window.addEventListener('resize', () => engine.resize());

        setMode('select');
        console.log('ArchiRapid Editor 3D v3.0 —', roomsData.length, 'habitaciones cargadas');
    </script>
</body>
</html>"""

    return html