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
</head>
<body>
    <canvas id="renderCanvas"></canvas>
    
    <div id="toolbar">
        <h3>🛠️ Herramientas</h3>
        <button class="tool-btn">🖱️ Seleccionar</button>
        <button class="tool-btn">↔️ Mover</button>
        <button class="tool-btn">🧱 Añadir Tabique</button>
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
            
            // Etiqueta 3D flotante
            const label = BABYLON.MeshBuilder.CreatePlane(`label_${{i}}`, {{
                width: 4, height: 2
            }}, scene);
            label.position.set(room.x + room.width/2, wallHeight + 1, room.z + room.depth/2);
            label.billboardMode = BABYLON.Mesh.BILLBOARDMODE_ALL;
            
            // Textura etiqueta con GUI
            const advancedTexture = BABYLON.GUI.AdvancedDynamicTexture.CreateForMesh(label);
            const textBlock = new BABYLON.GUI.TextBlock();
            textBlock.text = `${{room.name}}\\n${{room.area_m2.toFixed(0)}} m²`;
            textBlock.color = "white";
            textBlock.fontSize = 48;
            textBlock.fontWeight = "bold";
            advancedTexture.addControl(textBlock);
        }});
        
        // Render loop
        engine.runRenderLoop(() => scene.render());
        window.addEventListener('resize', () => engine.resize());
        
        console.log('Babylon.js cargado:', roomsData.length, 'habitaciones');
    </script>
</body>
</html>
    """
    
    return html
