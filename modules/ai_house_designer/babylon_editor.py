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
        <button class="tool-btn" id="btn-wall" onclick="setMode('wall')">🧱 Añadir Tabique</button>
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
            
            // ================================================
            // VENTANAS: Rectángulos azul claro en paredes laterales
            // ================================================
            const windowWidth = 1.2;  // 120cm ancho
            const windowHeight = 1.4; // 140cm alto
            const windowMat = new BABYLON.StandardMaterial(`windowMat_${{i}}`, scene);
            windowMat.diffuseColor = new BABYLON.Color3(0.5, 0.8, 1.0); // Azul claro
            windowMat.emissiveColor = new BABYLON.Color3(0.1, 0.2, 0.3); // Brillo sutil
            
            // Ventana en pared izquierda (si habitación > 8m²)
            if (room.area_m2 > 8) {{
                const leftWindow = BABYLON.MeshBuilder.CreateBox(`window_left_${{i}}`, {{
                    width: 0.12,
                    height: windowHeight,
                    depth: windowWidth
                }}, scene);
                leftWindow.position.set(
                    room.x - 0.06,
                    1.2,  // A 1.2m del suelo
                    room.z + room.depth/2
                );
                leftWindow.material = windowMat;
                leftWindow.isPickable = false;
            }}
            
            // Ventana en pared derecha (si habitación > 8m²)
            if (room.area_m2 > 8) {{
                const rightWindow = BABYLON.MeshBuilder.CreateBox(`window_right_${{i}}`, {{
                    width: 0.12,
                    height: windowHeight,
                    depth: windowWidth
                }}, scene);
                rightWindow.position.set(
                    room.x + room.width + 0.06,
                    1.2,
                    room.z + room.depth/2
                );
                rightWindow.material = windowMat;
                rightWindow.isPickable = false;
            }}
            
            console.log(`Ventanas creadas en habitación ${{i}} (${{room.name}}): ${{room.area_m2 > 8 ? '2 ventanas' : 'sin ventanas'}}`);
            
            // Etiqueta 3D flotante MÁS GRANDE
            const label = BABYLON.MeshBuilder.CreatePlane(`label_${{i}}`, {{
                width: 3.5,
                height: 1.8
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
            textBlock.text = `${{room.name}}\\n${{room.area_m2.toFixed(0)}} m²`;
            textBlock.color = "white";
            textBlock.fontSize = 52;
            textBlock.fontWeight = "bold";
            textBlock.outlineWidth = 4;
            textBlock.outlineColor = "black";
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
        gizmoManager.scaleGizmoEnabled = false;
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
                    
                    // Highlight del objeto seleccionado
                    if (window.highlightLayer) {{
                        window.highlightLayer.removeAllMeshes();
                        window.highlightLayer.addMesh(mesh, BABYLON.Color3.Yellow());
                    }}
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
                    gizmoManager.attachToMesh(selectedMesh);
                    gizmoManager.positionGizmoEnabled = true;
                    console.log('Modo: Mover (gizmo activado)');
                }} else {{
                    alert('Primero selecciona un objeto con modo Seleccionar');
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
        
        // Activar modo seleccionar por defecto
        setMode('select');
    </script>
</body>
</html>
    """
    
    return html
