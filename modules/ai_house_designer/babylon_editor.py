"""
Editor 3D avanzado usando Babylon.js
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


    js_scale_observer = """
                    // Solo permitir escalar en X y Z (no en Y/altura)
                    gizmoManager.gizmos.scaleGizmo.xGizmo.isEnabled = true;
                    gizmoManager.gizmos.scaleGizmo.yGizmo.isEnabled = false;
                    gizmoManager.gizmos.scaleGizmo.zGizmo.isEnabled = true;

                    console.log('Modo: Escalar (arrastra cubos en esquinas)');

                    gizmoManager.gizmos.scaleGizmo.onDragEndObservable.clear();

                    if (selectedMesh.name.startsWith('floor_')) {
                        const roomIndex = parseInt(selectedMesh.name.split('_')[1]);
                        console.log('DEBUG: Añadiendo observable para roomIndex=' + roomIndex);
                        gizmoManager.gizmos.scaleGizmo.onDragEndObservable.add(() => {
                            console.log('DEBUG: Drag finalizado!');
                            scene.registerAfterRender(function waitFrame() {
                                scene.unregisterAfterRender(waitFrame);
                                updateRoomInfo(selectedMesh, roomIndex);
                                updateBudget();
                                console.log('Paneles actualizados roomIndex=' + roomIndex);
                            });
                        });
                    } else {
                        alert('Primero selecciona una habitación con modo Seleccionar');
                        setMode('select');
                    }
"""


    js_move_observer = """
                    gizmoManager.attachToMesh(selectedMesh);
                    gizmoManager.positionGizmoEnabled = true;

                    // Bloquear eje Y para que NO floten
                    gizmoManager.gizmos.positionGizmo.xGizmo.isEnabled = true;
                    gizmoManager.gizmos.positionGizmo.yGizmo.isEnabled = false;
                    gizmoManager.gizmos.positionGizmo.zGizmo.isEnabled = true;

                    console.log('Modo: Mover (gizmo activado, eje Y bloqueado)');

                    gizmoManager.gizmos.positionGizmo.onDragEndObservable.clear();

                    const roomIndexMove = selectedMesh.name.startsWith('floor_')
                        ? parseInt(selectedMesh.name.split('_')[1])
                        : parseInt(selectedMesh.name.split('_').pop());

                    gizmoManager.gizmos.positionGizmo.onDragEndObservable.add(() => {
                        scene.registerAfterRender(function waitFrameMove() {
                            scene.unregisterAfterRender(waitFrameMove);
                            updateRoomInfo(selectedMesh, roomIndexMove);
                            updateBudget();
                            console.log('Paneles actualizados tras mover roomIndex=' + roomIndexMove);
                            console.log('DEBUG: Llamando updateRoomInfo...');
                            console.log('DEBUG: Llamando updateBudget...');
                        });
                    });
"""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ArchiRapid - Editor 3D</title>
    <style>
        * {{ margin: 0; padding: 0; }}
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; }}
        #renderCanvas {{ width: 100vw; height: 100vh; display: block; }}
        #toolbar {{
            position: absolute; top: 20px; left: 20px;
            background: rgba(0,0,0,0.85); padding: 15px;
            border-radius: 12px; color: white; min-width: 200px;
        }}
        #info-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.85);
            padding: 15px;
            border-radius: 12px;
            color: white;
            width: 250px;
            border: 1px solid rgba(52,152,219,0.3);
        }}
        #info-panel h3 {{
            margin: 0 0 10px 0;
            color: #3498DB;
            font-size: 16px;
        }}
        #room-info p {{
            margin: 5px 0;
            font-size: 13px;
        }}
        #budget-panel {{
            position: absolute;
            top: 350px;
            right: 20px;
            background: rgba(46, 204, 113, 0.15);
            padding: 12px;
            border-radius: 8px;
            color: white;
            width: 250px;
            border: 2px solid #2ECC71;
        }}
        #budget-panel h3 {{
            margin: 0 0 8px 0;
            color: #2ECC71;
            font-size: 15px;
        }}
        #budget-info p {{
            margin: 3px 0;
            font-size: 12px;
        }}
        #warning-panel {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(230, 126, 34, 0.15);
            padding: 12px;
            border-radius: 8px;
            color: white;
            width: 250px;
            border: 2px solid #E67E22;
        }}
        #warning-panel h3 {{
            margin: 0 0 8px 0;
            color: #E67E22;
            font-size: 15px;
        }}
        .tool-btn {{
            display: block; width: 100%; padding: 8px;
            margin: 5px 0; background: rgba(52,152,219,0.2);
            border: 1px solid #3498DB; color: white;
            border-radius: 6px; cursor: pointer;
        }}
    </style>
    <script src="https://cdn.babylonjs.com/babylon.js"></script>
    <script src="https://cdn.babylonjs.com/gui/babylon.gui.min.js"></script>
    <script src="https://cdn.babylonjs.com/materialsLibrary/babylonjs.materials.min.js"></script>
</head>
<body>
    <canvas id="renderCanvas"></canvas>
    
    <div id="toolbar">
        <h3>🛠️ Herramientas</h3>
        <button class="tool-btn" id="btn-select" onclick="setMode('select')">🖱️ Seleccionar</button>
        <button class="tool-btn" id="btn-move" onclick="setMode('move')">↔️ Mover</button>
        <button class="tool-btn" id="btn-scale" onclick="setMode('scale')">⤢ Escalar</button>
        <button class="tool-btn" id="btn-wall" onclick="setMode('wall')">🧱 Añadir Tabique</button>
        <hr style="margin: 10px 0; border-color: rgba(255,255,255,0.2);">
        <button class="tool-btn" onclick="setTopView()">🔝 Vista Planta</button>
        <button class="tool-btn" id="btn-save" onclick="saveChanges()" style="background: rgba(46,204,113,0.3); border-color: #2ECC71;">💾 Guardar Cambios</button>
    </div>

    <div id="info-panel">
        <h3>📊 Info Habitación</h3>
        <div id="room-info">
            <p style="color: #888;">Selecciona una habitación</p>
        </div>
    </div>

    <div id="budget-panel">
        <h3>💰 Presupuesto</h3>
        <div id="budget-info">
            <p><strong>Superficie:</strong> <span id="total-area">0</span> m²</p>
            <p><strong>Coste:</strong> <span id="total-cost">€0</span></p>
            <p style="font-size: 11px; color: #888; margin-top: 5px;" id="budget-diff"></p>
        </div>
    </div>

    <div id="warning-panel">
        <h3>⚠️ Importante</h3>
        <p style="font-size: 12px; line-height: 1.5;">
            Los cambios realizados en este editor requieren <strong>validación por un arquitecto</strong> antes de construcción.
        </p>
        <p style="font-size: 11px; color: #E67E22; margin-top: 8px;">
            ⚠️ No garantizan cumplimiento normativa CTE
        </p>
    </div>

    <script>
        const roomsData = {rooms_js};
        const totalWidth = {total_width};
        const totalDepth = {total_depth};
        console.log('=== DEBUG BABYLON ===');
        console.log('Rooms data:', roomsData);
        console.log('Total rooms:', roomsData ? roomsData.length : 0);
        console.log('Total width:', totalWidth);
        console.log('Total depth:', totalDepth);
        console.log('====================');
        
        const canvas = document.getElementById('renderCanvas');
        const engine = new BABYLON.Engine(canvas, true);
        const scene = new BABYLON.Scene(engine);
        scene.clearColor = new BABYLON.Color4(0.1, 0.1, 0.18, 1);
        
        // Cámara
        const camera = new BABYLON.ArcRotateCamera(
            "camera", Math.PI/4, Math.PI/3, totalWidth * 2,
            new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2), scene
        );
        camera.attachControl(canvas, true);
        
        // Luces
        new BABYLON.HemisphericLight("light1", new BABYLON.Vector3(0, 1, 0), scene);
        
        // Suelo
        const ground = BABYLON.MeshBuilder.CreateGround("ground", {{
            width: totalWidth + 20, height: totalDepth + 20
        }}, scene);
        const groundMat = new BABYLON.StandardMaterial("groundMat", scene);
        groundMat.diffuseColor = new BABYLON.Color3(0.48, 0.72, 0.48);
        ground.material = groundMat;
        
        // ================================================
        // GRID VISIBLE (cuadrícula blanca 1m x 1m)
        // ================================================
        const gridSize = Math.max(totalWidth, totalDepth) + 15;
        const gridDivisions = gridSize; // 1 división = 1 metro
        
        // Grid principal (líneas cada 1m)
        const gridHelper = new BABYLON.GridMaterial("gridMaterial", scene);
        gridHelper.majorUnitFrequency = 5;  // Línea gruesa cada 5m
        gridHelper.minorUnitVisibility = 0.5;  // Visibilidad líneas finas
        gridHelper.gridRatio = 1;  // Espaciado 1 metro
        gridHelper.mainColor = new BABYLON.Color3(1, 1, 1);  // Blanco
        gridHelper.lineColor = new BABYLON.Color3(0.3, 0.5, 0.7);  // Azul claro
        gridHelper.opacity = 0.6;
        gridHelper.backFaceCulling = false;
        
        const gridPlane = BABYLON.MeshBuilder.CreateGround("gridPlane", {{
            width: gridSize, height: gridSize
        }}, scene);
        gridPlane.material = gridHelper;
        gridPlane.position.y = 0.01;  // Ligeramente sobre el suelo
        gridPlane.isPickable = false;
        
        console.log('Grid creado:', gridSize, 'm x', gridSize, 'm con divisiones cada 1m');
        
        // Cargar habitaciones
        roomsData.forEach((room, i) => {{
            // Suelo habitación
            const floor = BABYLON.MeshBuilder.CreateBox(`floor_${{i}}`, {{
                width: room.width - 0.1, height: 0.05, depth: room.depth - 0.1
            }}, scene);
            floor.position.set(room.x + room.width/2, 0.025, room.z + room.depth/2);
            
            const floorMat = new BABYLON.StandardMaterial(`floorMat_${{i}}`, scene);
            floorMat.diffuseColor = new BABYLON.Color3(0.95, 0.94, 0.92); // Beige claro
            floor.material = floorMat;
            
            // PAREDES (4 por habitación)
            const wallHeight = 2.7;
            const wallThickness = 0.15;
            
            // Material paredes oscuras
            const wallMat = new BABYLON.StandardMaterial(`wallMat_${{i}}`, scene);
            wallMat.diffuseColor = new BABYLON.Color3(0.17, 0.24, 0.31); // Gris oscuro
            
            // Pared trasera
            const backWall = BABYLON.MeshBuilder.CreateBox(`wall_back_${{i}}`, {{
                width: room.width, height: wallHeight, depth: wallThickness
            }}, scene);
            backWall.position.set(room.x + room.width/2, wallHeight/2, room.z);
            backWall.material = wallMat;
            
            // Pared frontal (semi-transparente para ver interior)
            const frontWall = BABYLON.MeshBuilder.CreateBox(`wall_front_${{i}}`, {{
                width: room.width, height: wallHeight, depth: wallThickness
            }}, scene);
            frontWall.position.set(room.x + room.width/2, wallHeight/2, room.z + room.depth);
            const frontMat = new BABYLON.StandardMaterial(`frontMat_${{i}}`, scene);
            frontMat.diffuseColor = new BABYLON.Color3(0.17, 0.24, 0.31);
            frontMat.alpha = 0.3; // Transparente
            frontWall.material = frontMat;
            
            // Pared izquierda
            const leftWall = BABYLON.MeshBuilder.CreateBox(`wall_left_${{i}}`, {{
                width: wallThickness, height: wallHeight, depth: room.depth
            }}, scene);
            leftWall.position.set(room.x, wallHeight/2, room.z + room.depth/2);
            leftWall.material = wallMat;
            
            // Pared derecha
            const rightWall = BABYLON.MeshBuilder.CreateBox(`wall_right_${{i}}`, {{
                width: wallThickness, height: wallHeight, depth: room.depth
            }}, scene);
            rightWall.position.set(room.x + room.width, wallHeight/2, room.z + room.depth/2);
            rightWall.material = wallMat;
            
            // ================================================
            // PUERTA: Rectángulo amarillo brillante (MÁS VISIBLE)
            // ================================================
            const doorWidth = 0.9;
            const doorHeight = 2.0;
            
            // Material puerta amarillo neón (imposible no verlo)
            const doorMat = new BABYLON.StandardMaterial(`doorMat_${{i}}`, scene);
            doorMat.diffuseColor = new BABYLON.Color3(1, 0.9, 0); // Amarillo
            doorMat.emissiveColor = new BABYLON.Color3(0.5, 0.45, 0); // Brillo
            
            // Puerta como BOX GRANDE y visible
            const doorMarker = BABYLON.MeshBuilder.CreateBox(`door_${{i}}`, {{
                width: doorWidth,
                height: doorHeight,
                depth: 0.3  // MÁS GRUESA para verse mejor
            }}, scene);
            
            // Posición: FUERA de la pared (hacia adelante)
            doorMarker.position.set(
                room.x + room.width/2,
                doorHeight/2,
                room.z - 0.3  // MÁS hacia adelante
            );
            doorMarker.material = doorMat;
            
            console.log(`Puerta creada en habitación ${{i}}: x=${{doorMarker.position.x}}, z=${{doorMarker.position.z}}`);
            
            // Etiqueta 3D flotante MÁS GRANDE
            const label = BABYLON.MeshBuilder.CreatePlane(`label_${{i}}`, {{
                width: 2.2,  // Reducido de 3.5
                height: 1.2  // Reducido de 1.8
            }}, scene);
            label.position.set(room.x + room.width/2, wallHeight + 1.5, room.z + room.depth/2);
            label.billboardMode = BABYLON.Mesh.BILLBOARDMODE_ALL;
            
            // Textura etiqueta con GUI
            const advancedTexture = BABYLON.GUI.AdvancedDynamicTexture.CreateForMesh(label);
            
            // Fondo semi-transparente oscuro
            const bgRect = new BABYLON.GUI.Rectangle();
            bgRect.width = 1;
            bgRect.height = 1;
            bgRect.background = "rgba(44, 62, 80, 0.85)";  // Fondo oscuro
            bgRect.cornerRadius = 20;
            advancedTexture.addControl(bgRect);
            
            const textBlock = new BABYLON.GUI.TextBlock();
            // Nombre más pequeño + medidas más grandes
            textBlock.text = `${{room.name}}\\n\\n${{room.width.toFixed(1)}}m × ${{room.depth.toFixed(1)}}m\\n${{room.area_m2.toFixed(0)}} m²`;
            textBlock.color = "#FFFFFF";  // Blanco puro
            textBlock.fontSize = 48;  // Un poco más pequeño
            textBlock.fontWeight = "600";  // Menos bold
            textBlock.outlineWidth = 3;
            textBlock.outlineColor = "#000000";
            textBlock.lineSpacing = "8px";  // Espacio entre líneas
            bgRect.addControl(textBlock);
        }});
        
        // ================================================
        // SISTEMA DE SELECCIÓN Y GIZMO
        // ================================================
        let selectedMesh = null;
        let gizmoManager = null;
        let currentMode = 'select';
        
        // Crear Gizmo Manager (para mover objetos)
        gizmoManager = new BABYLON.GizmoManager(scene);
        gizmoManager.positionGizmoEnabled = false;  // Desactivado por defecto
        gizmoManager.rotationGizmoEnabled = false;
        gizmoManager.scaleGizmoEnabled = false;  // Se activa en modo escalar
        gizmoManager.boundingBoxGizmoEnabled = false;
        
        // Click para seleccionar objetos
        scene.onPointerDown = function(evt, pickResult) {{
            if (pickResult.hit && currentMode === 'select') {{
                const mesh = pickResult.pickedMesh;
                
                // Solo seleccionar paredes y suelos
                if (mesh && (mesh.name.startsWith('floor_') || 
                            mesh.name.startsWith('wall_'))) {{
                    selectedMesh = mesh;
                    console.log('Seleccionado:', mesh.name);
                    
                    // Extraer índice de habitación del nombre del mesh
                    const roomIndex = parseInt(mesh.name.split('_').pop());
                    
                    // Highlight del objeto seleccionado
                    if (window.highlightLayer) {{
                        window.highlightLayer.removeAllMeshes();
                        window.highlightLayer.addMesh(mesh, BABYLON.Color3.Yellow());
                    }}
                    
                    // Actualizar panel info
                    updateRoomInfo(mesh, roomIndex);
                }}
            }}
        }};
        
        // Crear highlight layer para objetos seleccionados
        window.highlightLayer = new BABYLON.HighlightLayer("highlight", scene);
        
        // Render loop
        engine.runRenderLoop(() => scene.render());
        window.addEventListener('resize', () => engine.resize());
        
        console.log('Babylon.js cargado:', roomsData.length, 'habitaciones');
        
        // ================================================
        // FUNCIONES DE LOS BOTONES
        // ================================================
        function setMode(mode) {{
            currentMode = mode;
            
            // Actualizar botones visualmente
            document.querySelectorAll('.tool-btn').forEach(btn => {{
                btn.style.background = 'rgba(52,152,219,0.2)';
            }});
            
            if (mode === 'select') {{
                document.getElementById('btn-select').style.background = 'rgba(52,152,219,0.6)';
                gizmoManager.positionGizmoEnabled = false;
                console.log('Modo: Seleccionar');
            }}
            else if (mode === 'move') {{
                document.getElementById('btn-move').style.background = 'rgba(52,152,219,0.6)';
                
                if (selectedMesh) {{
                    {js_move_observer}
                }} else {{
                    alert('Primero selecciona un objeto con modo Seleccionar');
                    setMode('select');
                }}
            }}
            else if (mode === 'scale') {{
                document.getElementById('btn-scale').style.background = 'rgba(52,152,219,0.6)';
                
                if (selectedMesh) {{
                    gizmoManager.attachToMesh(selectedMesh);
                    gizmoManager.positionGizmoEnabled = false;
                    gizmoManager.scaleGizmoEnabled = true;
                    
                    {js_scale_observer}
                }} else {{
                    alert('Primero selecciona una habitación con modo Seleccionar');
                    setMode('select');
                }}
            }}
            else if (mode === 'wall') {{
                document.getElementById('btn-wall').style.background = 'rgba(52,152,219,0.6)';
                gizmoManager.positionGizmoEnabled = false;
                console.log('Modo: Añadir Tabique');
                alert('Función "Añadir Tabique" en desarrollo');
            }}
        }}
        
        // ================================================
        // GUARDAR CAMBIOS
        // ================================================
        function saveChanges() {{
            // Recopilar coordenadas actuales de todas las paredes
            const currentLayout = [];
            
            roomsData.forEach((room, i) => {{
                // Buscar paredes de esta habitación
                const backWall = scene.getMeshByName(`wall_back_${{i}}`);
                const frontWall = scene.getMeshByName(`wall_front_${{i}}`);
                const leftWall = scene.getMeshByName(`wall_left_${{i}}`);
                const rightWall = scene.getMeshByName(`wall_right_${{i}}`);
                const floor = scene.getMeshByName(`floor_${{i}}`);
                
                if (floor) {{
                    // Calcular dimensiones reales desde bounds
                    const bounds = floor.getBoundingInfo().boundingBox;
                    const actualWidth = bounds.maximumWorld.x - bounds.minimumWorld.x;
                    const actualDepth = bounds.maximumWorld.z - bounds.minimumWorld.z;
                    
                    currentLayout.push({{
                        index: i,
                        name: room.name,
                        original_area: room.area_m2,
                        // Coordenadas esquina inferior izquierda
                        x: bounds.minimumWorld.x,
                        z: bounds.minimumWorld.z,
                        // Dimensiones REALES
                        width: parseFloat(actualWidth.toFixed(2)),
                        depth: parseFloat(actualDepth.toFixed(2)),
                        // Nueva área real
                        new_area: parseFloat((actualWidth * actualDepth).toFixed(2))
                    }});
                }}
            }});
            
            // Mostrar JSON en consola
            console.log('=== LAYOUT MODIFICADO ===');
            console.log(JSON.stringify(currentLayout, null, 2));
            console.log('========================');
            
            // Descargar como archivo
            const dataStr = JSON.stringify(currentLayout, null, 2);
            const dataBlob = new Blob([dataStr], {{type: 'application/json'}});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'archirapid_layout_modificado.json';
            link.click();
            
            // Mostrar warning
            alert('⚠️ CAMBIOS GUARDADOS\\n\\n📄 Archivo JSON descargado\\n\\n⚠️ IMPORTANTE: Este diseño requiere validación por un arquitecto antes de construcción.\\n\\nLos cambios NO garantizan cumplimiento de normativa CTE.');
        }}
        
        // ================================================
        // ACTUALIZAR PANEL INFO
        // ================================================
        function updateRoomInfo(mesh, roomIndex) {{
            console.log('updateRoomInfo llamado para roomIndex:', roomIndex);
            const room = roomsData[roomIndex];
            if (!room) return;
            
            // Calcular dimensiones actuales desde mesh
            const floor = scene.getMeshByName(`floor_${{roomIndex}}`);
            if (floor) {{
                const bounds = floor.getBoundingInfo().boundingBox;
                const actualWidth = bounds.maximumWorld.x - bounds.minimumWorld.x;
                const actualDepth = bounds.maximumWorld.z - bounds.minimumWorld.z;
                const actualArea = actualWidth * actualDepth;
                
                const infoDiv = document.getElementById('room-info');
                infoDiv.innerHTML = `
                    <p><strong>${{room.name}}</strong></p>
                    <p>📐 Ancho: <strong>${{actualWidth.toFixed(2)}}m</strong></p>
                    <p>📐 Fondo: <strong>${{actualDepth.toFixed(2)}}m</strong></p>
                    <p>📦 Área: <strong>${{actualArea.toFixed(1)}}m²</strong></p>
                    <p style="color: #888;">Original: ${{room.area_m2}}m²</p>
                `;
                
                // Recalcular presupuesto total
                updateBudget();
            }}
        }}
        
        // ================================================
        // VISTA PLANTA (CENITAL)
        // ================================================
        function setTopView() {{
            // Posición: Justo encima del centro de la casa
            const centerX = totalWidth / 2;
            const centerZ = totalDepth / 2;
            
            // Animar cámara a posición cenital
            camera.setPosition(new BABYLON.Vector3(centerX, totalWidth * 1.5, centerZ));
            camera.setTarget(new BABYLON.Vector3(centerX, 0, centerZ));
            
            console.log('Vista planta activada');
        }}
        
        // ================================================
        // ACTUALIZAR PRESUPUESTO TOTAL
        // ================================================
        const COST_PER_M2 = 1500;  // €/m² promedio construcción
        let originalTotalArea = 0;
        
        // Calcular área original al inicio
        roomsData.forEach(room => {{
            originalTotalArea += room.area_m2 || 0;
        }});
        
        function updateBudget() {{
            console.log('updateBudget llamado');
            let totalArea = 0;
            
            // Calcular área actual de todos los suelos
            roomsData.forEach((room, i) => {{
                const floor = scene.getMeshByName(`floor_${{i}}`);
                if (floor) {{
                    const bounds = floor.getBoundingInfo().boundingBox;
                    const actualWidth = bounds.maximumWorld.x - bounds.minimumWorld.x;
                    const actualDepth = bounds.maximumWorld.z - bounds.minimumWorld.z;
                    totalArea += (actualWidth * actualDepth);
                }}
            }});
            
            const totalCost = totalArea * COST_PER_M2;
            const originalCost = originalTotalArea * COST_PER_M2;
            const diff = totalCost - originalCost;
            
            // Actualizar panel
            document.getElementById('total-area').textContent = totalArea.toFixed(1);
            document.getElementById('total-cost').textContent = '€' + totalCost.toLocaleString('es-ES', {{maximumFractionDigits: 0}});
            
            const diffElem = document.getElementById('budget-diff');
            if (Math.abs(diff) > 100) {{
                const sign = diff > 0 ? '+' : '';
                diffElem.textContent = `${{sign}}€${{diff.toLocaleString('es-ES', {{maximumFractionDigits: 0}})}} vs original`;
                diffElem.style.color = diff > 0 ? '#E67E22' : '#2ECC71';
            }} else {{
                diffElem.textContent = 'Sin cambios significativos';
                diffElem.style.color = '#888';
            }}
        }}
        
        // Calcular presupuesto inicial
        updateBudget();
        
        // Activar modo seleccionar por defecto
        setMode('select');
    </script>
</body>
</html>
    """
    
    return html
