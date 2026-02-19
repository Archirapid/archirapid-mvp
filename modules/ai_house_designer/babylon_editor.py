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
            const floor = BABYLON.MeshBuilder.CreateBox(`floor_${{i}}`, {{
                width: room.width - 0.1, height: 0.05, depth: room.depth - 0.1
            }}, scene);
            floor.position.set(room.x + room.width/2, 0.025, room.z + room.depth/2);
            
            const mat = new BABYLON.StandardMaterial(`mat_${{i}}`, scene);
            mat.diffuseColor = new BABYLON.Color3(0.9, 0.9, 0.85);
            floor.material = mat;
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
