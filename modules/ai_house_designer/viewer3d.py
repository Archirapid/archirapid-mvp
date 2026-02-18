"""
Visor 3D profesional usando Three.js embebido en Streamlit
Genera HTML con Three.js para visualización 3D interactiva
"""
import math
import json
from typing import List, Dict

class Viewer3D:
    """Genera visor 3D interactivo con Three.js"""
    
    WALL_HEIGHT = 2.7  # metros
    SCALE = 1  # 1 unidad = 1 metro
    
    ROOM_COLORS = {
        'salon': 0xF5F0E8,
        'cocina': 0xFFF3E0,
        'dormitorio': 0xEEF0F5,
        'bano': 0xE8F5F0,
        'garaje': 0xECEFF1,
        'porche': 0xE8F5E8,
        'bodega': 0xFFF9C4,
        'pasillo': 0xEBEBEB,
        'paneles': 0xFFF8E1,
        'piscina': 0xE3F2FD,
        'huerto': 0xDCEDC8,
        'despacho': 0xF0EEF5,
        'default': 0xF5F5F5
    }
    
    def __init__(self, design, roof_type=None):
        self.design = design
        self.roof_type = roof_type or getattr(design, 'request', {}).get('roof_type', 'Dos aguas (clásico, eficiente)')
    
    def _get_color_hex(self, code: str) -> str:
        code_lower = code.lower()
        for key, color in self.ROOM_COLORS.items():
            if key in code_lower:
                return f"0x{color:06X}"
        return f"0x{self.ROOM_COLORS['default']:06X}"
    
    def _calculate_dimensions(self, area_m2: float, ratio: float = 1.4):
        safe_area = max(area_m2, 1.0)
        width = math.sqrt(safe_area * ratio)
        if width < 0.1:
            width = 1.0
        depth = safe_area / width
        return round(width, 2), round(depth, 2)
    
    def _layout_rooms(self) -> List[Dict]:
        """Usa el motor arquitectónico v4.0 para layout coherente"""
        from .architect_layout import generate_layout
        
        # Preparar datos para el motor
        rooms_data = []
        for room in self.design.rooms:
            rooms_data.append({
                'code': room.room_type.code,
                'name': room.room_type.name,
                'area_m2': max(room.area_m2, 1.0)
            })
        
        # Obtener forma de casa del request
        house_shape = getattr(self.design, 'request', {}).get('house_shape', 'Rectangular (más común)')
        
        # Generar layout arquitectónico v4.0
        layout_result = generate_layout(rooms_data, house_shape)
        
        # Guardar dimensiones totales
        if layout_result:
            all_x = [item['x'] + item['width'] for item in layout_result]
            all_z = [item['z'] + item['depth'] for item in layout_result]
            self.total_width = max(all_x)
            self.total_depth = max(all_z)
        else:
            self.total_width = 10
            self.total_depth = 10
        
        # Convertir al formato esperado por generate()
        layout = []
        for item in layout_result:
            # Buscar el room original por código/nombre
            original_room = None
            for room in self.design.rooms:
                if (room.room_type.code == item['code'] or 
                    room.room_type.name == item['name']):
                    original_room = room
                    break
            
            # Si es pasillo auto-generado, crear room sintético
            if original_room is None:
                from .data_model import RoomType, RoomInstance
                synth_type = RoomType(
                    code=item['code'],
                    name=item['name'],
                    min_m2=1, max_m2=50,
                    base_cost_per_m2=800
                )
                original_room = RoomInstance(
                    room_type=synth_type,
                    area_m2=item['area_m2']
                )
            
            layout.append({
                'room': original_room,
                'x': item['x'],
                'z': item['z'],
                'width': item['width'],
                'depth': item['depth'],
                'zone': item.get('zone', 'day')
            })
        
        return layout
    
    def generate_html(self) -> str:
        """Genera HTML completo con Three.js"""
        
        layout = self._layout_rooms()
        
        # Serializar rooms para JavaScript
        rooms_js = []
        for item in layout:
            room = item['room']
            rooms_js.append({
                'name': room.room_type.name,
                'x': item['x'],
                'z': item['z'],
                'width': item['width'],
                'depth': item['depth'],
                'height': self.WALL_HEIGHT,
                'color': self._get_color_hex(room.room_type.code),
                'area': room.area_m2
            })
        
        rooms_json = json.dumps(rooms_js)
        total_w = self.total_width
        total_d = self.total_depth
        center_x = total_w / 2
        center_z = total_d / 2
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #1a1a2e; font-family: Arial, sans-serif; overflow: hidden; }}
        #canvas-container {{ width: 100%; height: 550px; position: relative; }}
        #info-panel {{
            position: absolute; top: 10px; left: 10px;
            background: rgba(0,0,0,0.7); color: white;
            padding: 10px 15px; border-radius: 8px; font-size: 12px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        #controls {{
            position: absolute; bottom: 10px; left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7); color: white;
            padding: 8px 15px; border-radius: 20px; font-size: 11px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        #room-label {{
            position: absolute; top: 10px; right: 10px;
            background: rgba(44,62,80,0.9); color: white;
            padding: 10px 15px; border-radius: 8px; font-size: 13px;
            border: 1px solid rgba(255,255,255,0.3);
            display: none;
        }}
        .btn-view {{
            position: absolute; background: rgba(52,152,219,0.8);
            color: white; border: none; padding: 6px 12px;
            border-radius: 5px; cursor: pointer; font-size: 11px;
        }}
        #btn-top {{ top: 50px; right: 10px; }}
        #btn-front {{ top: 85px; right: 10px; }}
        #btn-iso {{ top: 120px; right: 10px; }}
        #solar-panel {{
            position: absolute;
            bottom: 50px;
            left: 10px;
            background: rgba(0,0,0,0.75);
            color: white;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 11px;
            border: 1px solid rgba(255,200,0,0.4);
            min-width: 160px;
        }}
        #solar-compass {{
            width: 70px;
            height: 70px;
            margin: 0 auto 8px auto;
            position: relative;
        }}
        #room-detail-panel {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(20, 30, 50, 0.95);
            color: white;
            padding: 20px 25px;
            border-radius: 12px;
            font-size: 13px;
            border: 2px solid rgba(52,152,219,0.6);
            min-width: 220px;
            display: none;
            z-index: 100;
            text-align: center;
        }}
        #room-detail-panel h3 {{
            margin: 0 0 10px 0;
            color: #3498DB;
            font-size: 16px;
        }}
        #room-detail-panel .metric {{
            margin: 6px 0;
            font-size: 12px;
            color: #BDC3C7;
        }}
        #room-detail-panel .cost {{
            font-size: 18px;
            font-weight: bold;
            color: #2ECC71;
            margin: 10px 0;
        }}
        #room-detail-panel button {{
            background: #3498DB;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            cursor: pointer;
            margin-top: 8px;
            font-size: 12px;
        }}
        #room-detail-panel button:hover {{
            background: #2980B9;
        }}
        #btn-fullscreen {{
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(52,152,219,0.85);
            color: white;
            border: none;
            padding: 7px 18px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 0.5px;
            z-index: 50;
            transition: all 0.2s;
        }}
        #btn-fullscreen:hover {{
            background: rgba(41,128,185,1);
            transform: translateX(-50%) scale(1.05);
        }}
        
        /* Modal pantalla completa */
        #modal-3d {{
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: rgba(0,0,0,0.92);
            z-index: 9999;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        #modal-3d.active {{
            display: flex;
        }}
        #modal-canvas-container {{
            width: 95vw;
            height: 88vh;
            position: relative;
            border-radius: 10px;
            overflow: hidden;
            border: 2px solid rgba(52,152,219,0.5);
        }}
        #modal-close {{
            position: absolute;
            top: 15px;
            right: 20px;
            background: rgba(231,76,60,0.9);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            z-index: 10000;
        }}
        #modal-title {{
            color: white;
            font-size: 14px;
            margin-bottom: 8px;
            opacity: 0.8;
        }}
        #canvas-container:-webkit-full-screen {{
            width: 100vw !important;
            height: 100vh !important;
        }}
        #canvas-container:fullscreen {{
            width: 100vw !important;
            height: 100vh !important;
            background: #1a1a2e;
        }}
    </style>
</head>
<body>
<div id="canvas-container">
    <div id="info-panel">
        <strong>🏠 Vista 3D Interactiva</strong><br>
        Superficie: {sum(r['area'] for r in rooms_js):.0f} m²<br>
        Habitaciones: {len(rooms_js)}
    </div>
    <div id="room-label" id="room-info"></div>
    <button class="btn-view" id="btn-top" onclick="setView('top')">Vista Superior</button>
    <button class="btn-view" id="btn-front" onclick="setView('front')">Vista Frontal</button>
    <button class="btn-view" id="btn-iso" onclick="setView('iso')">Vista 3D</button>
    <button class="btn-view" id="btn-roof" onclick="toggleRoof()" 
            style="top:155px; right:10px; background:rgba(149,165,166,0.8);">
        Tejado: OFF
    </button>
    <div id="controls">🖱️ Arrastrar: rotar · Scroll: zoom · Click habitación: info</div>
    
    <!-- Botón abrir en nueva pestaña -->
    <button id="btn-fullscreen" onclick="openInNewTab()">
        ⛶ Abrir en Nueva Pestaña
    </button>
    
    <!-- Panel orientación solar -->
    <div id="solar-panel">
        <div id="solar-compass">
            <canvas id="compass-canvas" width="70" height="70"></canvas>
        </div>
        <div style="text-align:center; color:#FFD700; font-weight:bold; font-size:12px;">
            ☀️ Orientación Solar
        </div>
        <div id="solar-info" style="margin-top:6px; font-size:10px; color:#aaa; text-align:center;">
            Fachada Sur → Máximo sol
        </div>
        <div id="solar-rating" style="margin-top:4px; text-align:center;">
            <span style="color:#2ECC71; font-weight:bold;">★★★★★ Óptima</span>
        </div>
    </div>
    
    <!-- Panel detalle habitación (click) -->
    <div id="room-detail-panel">
        <button onclick="closeRoomPanel()" 
                style="position:absolute;top:8px;right:8px;background:rgba(231,76,60,0.8);
                       padding:2px 8px;border-radius:4px;font-size:11px;">✕</button>
        <h3 id="detail-name">Habitación</h3>
        <div class="metric">📐 Dimensiones: <span id="detail-dims">-</span></div>
        <div class="metric">📏 Superficie: <span id="detail-area">-</span></div>
        <div class="cost" id="detail-cost">€0</div>
        <div class="metric">💡 <span id="detail-tip">-</span></div>
        <div style="margin-top:15px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.2); text-align:center;">
            <div style="font-size:12px; color:#95A5A6; line-height:1.6;">
                💡 Para cambiar dimensiones:<br>
                <span style="color:#3498DB;">Usa los sliders en la columna izquierda</span>
            </div>
        </div>
        <button onclick="closeRoomPanel()" style="margin-top:15px;">Cerrar</button>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
// Datos de habitaciones
const rooms = {rooms_json};
const totalW = {total_w};
const totalD = {total_d};
const centerX = {center_x};
const centerZ = {center_z};

// Setup básico Three.js
const container = document.getElementById('canvas-container');
const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
renderer.setSize(container.clientWidth, 550);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);
scene.fog = new THREE.Fog(0x1a1a2e, 30, 80);

// Cámara
const camera = new THREE.PerspectiveCamera(45, container.clientWidth / 550, 0.1, 500);
camera.position.set(centerX + 20, 25, centerZ + 25);
camera.lookAt(new THREE.Vector3(centerX, 2, centerZ));

// Luces
const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(centerX + 10, 20, centerZ + 10);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 2048;
dirLight.shadow.mapSize.height = 2048;
scene.add(dirLight);

const hemiLight = new THREE.HemisphereLight(0x87CEEB, 0x8B7355, 0.4);
scene.add(hemiLight);

// Parcela completa con zona verde exterior
const groundGeo = new THREE.PlaneGeometry(totalW + 25, totalD + 25);
const groundMat = new THREE.MeshLambertMaterial({{ 
    color: 0x7CB87C,  // Verde hierba
    side: THREE.DoubleSide 
}});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.set(centerX, -0.05, centerZ);
ground.receiveShadow = true;
scene.add(ground);

// Zona pavimentada bajo la casa
const houseFloorGeo = new THREE.PlaneGeometry(totalW + 1, totalD + 1);
const houseFloorMat = new THREE.MeshLambertMaterial({{ 
    color: 0xE8E0D0,  // Beige pavimento
    side: THREE.DoubleSide 
}});
const houseFloor = new THREE.Mesh(houseFloorGeo, houseFloorMat);
houseFloor.rotation.x = -Math.PI / 2;
houseFloor.position.set(centerX, -0.02, centerZ);
scene.add(houseFloor);

// Zona piscina exterior (verde agua)
const poolZoneGeo = new THREE.PlaneGeometry(10, 8);
const poolZoneMat = new THREE.MeshLambertMaterial({{ color: 0x4FC3F7 }});
const poolZone = new THREE.Mesh(poolZoneGeo, poolZoneMat);
poolZone.rotation.x = -Math.PI / 2;
poolZone.position.set(centerX - totalW/2 - 5, -0.03, centerZ + totalD/2);
scene.add(poolZone);

// Grid
const gridHelper = new THREE.GridHelper(Math.max(totalW, totalD) + 10, 
    Math.floor(Math.max(totalW, totalD) + 10), 0x444466, 0x333355);
gridHelper.position.set(centerX, 0, centerZ);
scene.add(gridHelper);

// Habitaciones 3D
const roomMeshes = [];
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

rooms.forEach((room, index) => {{
    const color = parseInt(room.color);
    
    // Suelo de la habitación
    const floorGeo = new THREE.BoxGeometry(room.width - 0.1, 0.05, room.depth - 0.1);
    const floorMat = new THREE.MeshLambertMaterial({{ color: color }});
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.position.set(
        room.x + room.width/2,
        0.025,
        room.z + room.depth/2
    );
    floor.receiveShadow = true;
    scene.add(floor);
    
    // Paredes (4 paredes por habitación)
    const wallMat = new THREE.MeshLambertMaterial({{ 
        color: color,
        transparent: true,
        opacity: 0.85
    }});
    const wallMatDark = new THREE.MeshLambertMaterial({{ 
        color: color,
        transparent: true,
        opacity: 0.75
    }});
    
    const wallThickness = 0.15;
    
    // Pared trasera
    const backWallGeo = new THREE.BoxGeometry(room.width, room.height, wallThickness);
    const backWall = new THREE.Mesh(backWallGeo, wallMat);
    backWall.position.set(room.x + room.width/2, room.height/2, room.z);
    backWall.castShadow = true;
    backWall.userData = {{ room: room, index: index }};
    scene.add(backWall);
    roomMeshes.push(backWall);
    
    // Pared frontal (transparente para ver interior)
    const frontWallGeo = new THREE.BoxGeometry(room.width, room.height, wallThickness);
    const frontWallMat = new THREE.MeshLambertMaterial({{ 
        color: color, transparent: true, opacity: 0.3
    }});
    const frontWall = new THREE.Mesh(frontWallGeo, frontWallMat);
    frontWall.position.set(room.x + room.width/2, room.height/2, room.z + room.depth);
    scene.add(frontWall);
    
    // Pared izquierda
    const leftWallGeo = new THREE.BoxGeometry(wallThickness, room.height, room.depth);
    const leftWall = new THREE.Mesh(leftWallGeo, wallMatDark);
    leftWall.position.set(room.x, room.height/2, room.z + room.depth/2);
    leftWall.castShadow = true;
    scene.add(leftWall);
    
    // Pared derecha
    const rightWallGeo = new THREE.BoxGeometry(wallThickness, room.height, room.depth);
    const rightWall = new THREE.Mesh(rightWallGeo, wallMatDark);
    rightWall.position.set(room.x + room.width, room.height/2, room.z + room.depth/2);
    rightWall.castShadow = true;
    scene.add(rightWall);
    
    // Techo
    const ceilGeo = new THREE.BoxGeometry(room.width, 0.08, room.depth);
    const ceilMat = new THREE.MeshLambertMaterial({{ color: 0xFFFFFF, transparent: true, opacity: 0.6 }});
    const ceil = new THREE.Mesh(ceilGeo, ceilMat);
    ceil.position.set(room.x + room.width/2, room.height, room.z + room.depth/2);
    scene.add(ceil);
    
    // Etiqueta 3D (sprite)
    const canvas2d = document.createElement('canvas');
    canvas2d.width = 256;
    canvas2d.height = 128;
    const ctx = canvas2d.getContext('2d');
    
    ctx.fillStyle = 'rgba(44, 62, 80, 0.85)';
    ctx.roundRect(4, 4, 248, 120, 12);
    ctx.fill();
    
    ctx.fillStyle = 'white';
    ctx.font = 'bold 22px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(room.name, 128, 45);
    
    ctx.font = '18px Arial';
    ctx.fillStyle = '#87CEEB';
    ctx.fillText(room.area.toFixed(0) + ' m²', 128, 75);
    
    ctx.font = '14px Arial';
    ctx.fillStyle = '#aaa';
    ctx.fillText(room.width.toFixed(1) + 'm × ' + room.depth.toFixed(1) + 'm', 128, 100);
    
    const texture = new THREE.CanvasTexture(canvas2d);
    const spriteMat = new THREE.SpriteMaterial({{ map: texture, transparent: true }});
    const sprite = new THREE.Sprite(spriteMat);
    sprite.position.set(
        room.x + room.width/2,
        room.height + 1.2,
        room.z + room.depth/2
    );
    sprite.scale.set(3.5, 1.75, 1);
    scene.add(sprite);
}});

// ================================================
// TEJADO ADAPTATIVO según tipo seleccionado
// ================================================
let roofVisible = false;
const roofGroup = new THREE.Group();
const roofMat = new THREE.MeshLambertMaterial({{ color: 0xB55A30, side: THREE.DoubleSide }});

// Obtener tipo de tejado (pasado desde Python)
const roofType = "{{roof_type}}";  // Será reemplazado por Python

// Función para crear tejado según tipo
function createRoof(type) {{
    const group = new THREE.Group();
    
    if (type.includes("Dos aguas")) {{
        // Tejado DOS AGUAS clásico (cumbrera en el centro, largo de la casa)
        const ridgeHeight = 2.5;  // Altura de la cumbrera
        
        // Plano izquierdo (pendiente hacia la izquierda)
        const leftGeo = new THREE.BufferGeometry();
        const lv = new Float32Array([
            -1, 0, -1,              // Esquina frontal izquierda
            -1, 0, totalD+1,         // Esquina trasera izquierda
            totalW/2, ridgeHeight, totalD+1,  // Cumbrera trasera
            
            -1, 0, -1,
            totalW/2, ridgeHeight, totalD+1,
            totalW/2, ridgeHeight, -1   // Cumbrera frontal
        ]);
        leftGeo.setAttribute('position', new THREE.BufferAttribute(lv, 3));
        leftGeo.computeVertexNormals();
        group.add(new THREE.Mesh(leftGeo, roofMat));
        
        // Plano derecho (pendiente hacia la derecha)
        const rightGeo = new THREE.BufferGeometry();
        const rv = new Float32Array([
            totalW+1, 0, -1,
            totalW+1, 0, totalD+1,
            totalW/2, ridgeHeight, totalD+1,
            
            totalW+1, 0, -1,
            totalW/2, ridgeHeight, totalD+1,
            totalW/2, ridgeHeight, -1
        ]);
        rightGeo.setAttribute('position', new THREE.BufferAttribute(rv, 3));
        rightGeo.computeVertexNormals();
        group.add(new THREE.Mesh(rightGeo, roofMat));
        
        // Tapas triangulares (hastiales)
        const frontGeo = new THREE.BufferGeometry();
        const fv = new Float32Array([
            -1, 0, -1,
            totalW+1, 0, -1,
            totalW/2, ridgeHeight, -1
        ]);
        frontGeo.setAttribute('position', new THREE.BufferAttribute(fv, 3));
        frontGeo.computeVertexNormals();
        group.add(new THREE.Mesh(frontGeo, roofMat));
        
        const backGeo = new THREE.BufferGeometry();
        const bv = new Float32Array([
            -1, 0, totalD+1,
            totalW+1, 0, totalD+1,
            totalW/2, ridgeHeight, totalD+1
        ]);
        backGeo.setAttribute('position', new THREE.BufferAttribute(bv, 3));
        backGeo.computeVertexNormals();
        group.add(new THREE.Mesh(backGeo, roofMat));
    }}
    else if (type.includes("Plana")) {{
        // Tejado PLANO (solo una losa horizontal)
        const flatGeo = new THREE.BoxGeometry(totalW+2, 0.3, totalD+2);
        const flatMat = new THREE.MeshLambertMaterial({{ color: 0x95A5A6 }});  // Gris hormigón
        const flatRoof = new THREE.Mesh(flatGeo, flatMat);
        flatRoof.position.set(totalW/2, 0.15, totalD/2);
        group.add(flatRoof);
    }}
    else if (type.includes("Cuatro aguas")) {{
        // Tejado CUATRO AGUAS (piramidal, 4 pendientes)
        const peakHeight = 2.0;
        
        // Plano frontal
        const fGeo = new THREE.BufferGeometry();
        const fv = new Float32Array([
            -1, 0, -1,
            totalW+1, 0, -1,
            totalW/2, peakHeight, totalD/2
        ]);
        fGeo.setAttribute('position', new THREE.BufferAttribute(fv, 3));
        fGeo.computeVertexNormals();
        group.add(new THREE.Mesh(fGeo, roofMat));
        
        // Plano trasero
        const bGeo = new THREE.BufferGeometry();
        const bv = new Float32Array([
            -1, 0, totalD+1,
            totalW+1, 0, totalD+1,
            totalW/2, peakHeight, totalD/2
        ]);
        bGeo.setAttribute('position', new THREE.BufferAttribute(bv, 3));
        bGeo.computeVertexNormals();
        group.add(new THREE.Mesh(bGeo, roofMat));
        
        // Plano izquierdo
        const lGeo = new THREE.BufferGeometry();
        const lv = new Float32Array([
            -1, 0, -1,
            -1, 0, totalD+1,
            totalW/2, peakHeight, totalD/2
        ]);
        lGeo.setAttribute('position', new THREE.BufferAttribute(lv, 3));
        lGeo.computeVertexNormals();
        group.add(new THREE.Mesh(lGeo, roofMat));
        
        // Plano derecho
        const rGeo = new THREE.BufferGeometry();
        const rv = new Float32Array([
            totalW+1, 0, -1,
            totalW+1, 0, totalD+1,
            totalW/2, peakHeight, totalD/2
        ]);
        rGeo.setAttribute('position', new THREE.BufferAttribute(rv, 3));
        rGeo.computeVertexNormals();
        group.add(new THREE.Mesh(rGeo, roofMat));
    }}
    else if (type.includes("un agua")) {{
        // Tejado A UN AGUA (pendiente única hacia atrás)
        const slopeHeight = 2.0;
        
        const monoGeo = new THREE.BufferGeometry();
        const mv = new Float32Array([
            -1, slopeHeight, -1,        // Frontal alto izquierda
            totalW+1, slopeHeight, -1,   // Frontal alto derecha
            totalW+1, 0, totalD+1,       // Trasero bajo derecha
            
            -1, slopeHeight, -1,
            totalW+1, 0, totalD+1,
            -1, 0, totalD+1              // Trasero bajo izquierda
        ]);
        monoGeo.setAttribute('position', new THREE.BufferAttribute(mv, 3));
        monoGeo.computeVertexNormals();
        group.add(new THREE.Mesh(monoGeo, roofMat));
        
        // Tapas laterales
        const leftCapGeo = new THREE.BufferGeometry();
        const lcv = new Float32Array([
            -1, slopeHeight, -1,
            -1, 0, totalD+1,
            -1, slopeHeight, -1
        ]);
        leftCapGeo.setAttribute('position', new THREE.BufferAttribute(lcv, 3));
        leftCapGeo.computeVertexNormals();
        group.add(new THREE.Mesh(leftCapGeo, roofMat));
        
        const rightCapGeo = new THREE.BufferGeometry();
        const rcv = new Float32Array([
            totalW+1, slopeHeight, -1,
            totalW+1, 0, totalD+1,
            totalW+1, slopeHeight, -1
        ]);
        rightCapGeo.setAttribute('position', new THREE.BufferAttribute(rcv, 3));
        rightCapGeo.computeVertexNormals();
        group.add(new THREE.Mesh(rightCapGeo, roofMat));
    }}
    else {{
        // Por defecto: Invertida (igual que Cuatro aguas pero color diferente)
        const peakHeight = 1.8;
        const invertMat = new THREE.MeshLambertMaterial({{ color: 0x7F8C8D, side: THREE.DoubleSide }});
        
        const fGeo = new THREE.BufferGeometry();
        const fv = new Float32Array([
            -1, 0, -1, totalW+1, 0, -1, totalW/2, peakHeight, totalD/2
        ]);
        fGeo.setAttribute('position', new THREE.BufferAttribute(fv, 3));
        fGeo.computeVertexNormals();
        group.add(new THREE.Mesh(fGeo, invertMat));
        
        const bGeo = new THREE.BufferGeometry();
        const bv = new Float32Array([
            -1, 0, totalD+1, totalW+1, 0, totalD+1, totalW/2, peakHeight, totalD/2
        ]);
        bGeo.setAttribute('position', new THREE.BufferAttribute(bv, 3));
        bGeo.computeVertexNormals();
        group.add(new THREE.Mesh(bGeo, invertMat));
        
        const lGeo = new THREE.BufferGeometry();
        const lv = new Float32Array([
            -1, 0, -1, -1, 0, totalD+1, totalW/2, peakHeight, totalD/2
        ]);
        lGeo.setAttribute('position', new THREE.BufferAttribute(lv, 3));
        lGeo.computeVertexNormals();
        group.add(new THREE.Mesh(lGeo, invertMat));
        
        const rGeo = new THREE.BufferGeometry();
        const rv = new Float32Array([
            totalW+1, 0, -1, totalW+1, 0, totalD+1, totalW/2, peakHeight, totalD/2
        ]);
        rGeo.setAttribute('position', new THREE.BufferAttribute(rv, 3));
        rGeo.computeVertexNormals();
        group.add(new THREE.Mesh(rGeo, invertMat));
    }}
    
    group.position.y = {self.WALL_HEIGHT};
    return group;
}}

// Crear tejado del tipo seleccionado
roofGroup.add(createRoof(roofType));
roofGroup.visible = false;  // Oculto por defecto
scene.add(roofGroup);

// ============================================
// BRÚJULA SOLAR
// ============================================
const compassCanvas = document.getElementById('compass-canvas');
const compassCtx = compassCanvas.getContext('2d');
let solarAngle = 180; // Sur por defecto (óptimo para España)

function drawCompass(angle) {{
    compassCtx.clearRect(0, 0, 70, 70);
    
    // Fondo círculo
    compassCtx.beginPath();
    compassCtx.arc(35, 35, 32, 0, Math.PI * 2);
    compassCtx.fillStyle = 'rgba(0,0,0,0.5)';
    compassCtx.fill();
    compassCtx.strokeStyle = 'rgba(255,215,0,0.5)';
    compassCtx.lineWidth = 1.5;
    compassCtx.stroke();
    
    // Letras N, S, E, O
    compassCtx.fillStyle = '#FFD700';
    compassCtx.font = 'bold 9px Arial';
    compassCtx.textAlign = 'center';
    compassCtx.fillText('N', 35, 12);
    compassCtx.fillText('S', 35, 62);
    compassCtx.fillText('E', 62, 38);
    compassCtx.fillText('O', 10, 38);
    
    // Aguja Norte (rojo)
    const rad = (angle - 90) * Math.PI / 180;
    compassCtx.beginPath();
    compassCtx.moveTo(35, 35);
    compassCtx.lineTo(35 + 22 * Math.cos(rad), 35 + 22 * Math.sin(rad));
    compassCtx.strokeStyle = '#E74C3C';
    compassCtx.lineWidth = 2.5;
    compassCtx.stroke();
    
    // Aguja Sur (blanco)
    compassCtx.beginPath();
    compassCtx.moveTo(35, 35);
    compassCtx.lineTo(35 - 16 * Math.cos(rad), 35 - 16 * Math.sin(rad));
    compassCtx.strokeStyle = 'white';
    compassCtx.lineWidth = 2;
    compassCtx.stroke();
    
    // Centro
    compassCtx.beginPath();
    compassCtx.arc(35, 35, 3, 0, Math.PI * 2);
    compassCtx.fillStyle = '#FFD700';
    compassCtx.fill();
    
    // Sol en dirección Sur
    const sunRad = (180 - 90) * Math.PI / 180;
    const sunX = 35 + 28 * Math.cos(sunRad);
    const sunY = 35 + 28 * Math.sin(sunRad);
    compassCtx.fillStyle = '#FFD700';
    compassCtx.font = '10px Arial';
    compassCtx.fillText('☀', sunX, sunY);
}}

drawCompass(solarAngle);

// Calcular rating solar
function getSolarRating(angle) {{
    const southDiff = Math.abs(((angle - 180 + 360) % 360));
    if (southDiff < 30) return {{ stars: '★★★★★', text: 'Óptima al Sur', color: '#2ECC71' }};
    if (southDiff < 60) return {{ stars: '★★★★☆', text: 'Muy buena', color: '#27AE60' }};
    if (southDiff < 90) return {{ stars: '★★★☆☆', text: 'Buena', color: '#F39C12' }};
    if (southDiff < 135) return {{ stars: '★★☆☆☆', text: 'Regular', color: '#E67E22' }};
    return {{ stars: '★☆☆☆☆', text: 'Mejorable al Norte', color: '#E74C3C' }};
}}

// Rotar orientación de la casa
document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowLeft') {{ solarAngle = (solarAngle - 15 + 360) % 360; }}
    if (e.key === 'ArrowRight') {{ solarAngle = (solarAngle + 15) % 360; }}
    drawCompass(solarAngle);
    const rating = getSolarRating(solarAngle);
    document.getElementById('solar-rating').innerHTML = 
        '<span style="color:' + rating.color + '; font-weight:bold;">' + 
        rating.stars + ' ' + rating.text + '</span>';
}});

// ============================================
// PANEL DETALLE HABITACIÓN (CLICK)
// ============================================
const ROOM_COSTS = {{
    'salon': 1200, 'cocina': 1200, 'dormitorio': 1100,
    'bano': 900, 'garaje': 900, 'porche': 700,
    'bodega': 600, 'pasillo': 800, 'paneles': 3000,
    'piscina': 2500, 'huerto': 150, 'despacho': 1100,
    'default': 1000
}};

const ROOM_TIPS = {{
    'salon': 'Orientar al Sur para luz natural todo el día',
    'cocina': 'Mínimo 12m² recomendado por CTE',
    'dormitorio': 'Mínimo 9m² según normativa española',
    'bano': 'Mínimo 4m². Ventilación obligatoria',
    'garaje': 'Mínimo 15m² para 1 vehículo normal',
    'porche': 'Orientar al Sur para máximo aprovechamiento solar',
    'piscina': 'Requiere vallado de seguridad (normativa)',
    'bodega': 'Temperatura ideal 12-16°C, semisótano recomendado',
    'default': 'Espacio bien dimensionado para su uso'
}};

let selectedRoom = null;

function getCostPerM2(name) {{
    const nameLower = name.toLowerCase();
    for (const [key, cost] of Object.entries(ROOM_COSTS)) {{
        if (nameLower.includes(key)) return cost;
    }}
    return ROOM_COSTS.default;
}}

function getTip(name) {{
    const nameLower = name.toLowerCase();
    for (const [key, tip] of Object.entries(ROOM_TIPS)) {{
        if (nameLower.includes(key)) return tip;
    }}
    return ROOM_TIPS.default;
}}

function openRoomPanel(room) {{
    selectedRoom = room;
    const costPerM2 = getCostPerM2(room.name);
    const totalCost = room.area * costPerM2;
    
    document.getElementById('detail-name').textContent = room.name;
    document.getElementById('detail-dims').textContent = 
        room.width.toFixed(1) + 'm × ' + room.depth.toFixed(1) + 'm';
    document.getElementById('detail-area').textContent = room.area.toFixed(0) + ' m²';
    document.getElementById('detail-cost').textContent = 
        '€' + totalCost.toLocaleString('es-ES');
    document.getElementById('detail-tip').textContent = getTip(room.name);
    document.getElementById('room-detail-panel').style.display = 'block';
}}

function closeRoomPanel() {{
    document.getElementById('room-detail-panel').style.display = 'none';
    selectedRoom = null;
}}

// Controles de órbita (manual)
let isDragging = false;
let previousMousePosition = {{ x: 0, y: 0 }};
let spherical = {{ radius: 35, phi: 0.15, theta: Math.PI/4 }};

function updateCamera() {{
    const x = centerX + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
    const y = Math.max(2, spherical.radius * Math.cos(spherical.phi));
    const z = centerZ + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
    camera.position.set(x, y, z);
    camera.lookAt(new THREE.Vector3(centerX, 1, centerZ));
    camera.updateProjectionMatrix();
}}

renderer.domElement.addEventListener('mousedown', (e) => {{
    isDragging = true;
    previousMousePosition = {{ x: e.clientX, y: e.clientY }};
}});

renderer.domElement.addEventListener('click', (e) => {{
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(roomMeshes);
    if (intersects.length > 0 && intersects[0].object.userData.room) {{
        openRoomPanel(intersects[0].object.userData.room);
    }}
}});

renderer.domElement.addEventListener('mousemove', (e) => {{
    if (isDragging) {{
        const delta = {{ x: e.clientX - previousMousePosition.x, y: e.clientY - previousMousePosition.y }};
        spherical.theta -= delta.x * 0.01;
        spherical.phi = Math.max(0.1, Math.min(Math.PI/2 - 0.05, spherical.phi + delta.y * 0.01));
        previousMousePosition = {{ x: e.clientX, y: e.clientY }};
        updateCamera();
    }}
    
    // Hover sobre habitaciones
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(roomMeshes);
    
    const label = document.getElementById('room-label');
    if (intersects.length > 0 && intersects[0].object.userData.room) {{
        const r = intersects[0].object.userData.room;
        label.style.display = 'block';
        label.innerHTML = '<strong>' + r.name + '</strong><br>' +
            r.area.toFixed(0) + ' m² · ' + r.width.toFixed(1) + 'm × ' + r.depth.toFixed(1) + 'm';
    }} else {{
        label.style.display = 'none';
    }}
}});

renderer.domElement.addEventListener('mouseup', () => isDragging = false);

renderer.domElement.addEventListener('wheel', (e) => {{
    spherical.radius = Math.max(5, Math.min(60, spherical.radius + e.deltaY * 0.05));
    updateCamera();
}});

// Vistas predefinidas
function setView(type) {{
    if (type === 'top') {{
        spherical = {{ radius: 40, phi: 0.05, theta: Math.PI/4 }};
    }} else if (type === 'front') {{
        spherical = {{ radius: 30, phi: Math.PI/2.5, theta: 0 }};
    }} else {{
        spherical = {{ radius: 35, phi: Math.PI/3.5, theta: Math.PI/5 }};
    }}
    updateCamera();
}}

function toggleRoof() {{
    roofVisible = !roofVisible;
    roofGroup.visible = roofVisible;
    document.getElementById('btn-roof').textContent = 
        roofVisible ? 'Tejado: ON' : 'Tejado: OFF';
    document.getElementById('btn-roof').style.background = 
        roofVisible ? 'rgba(230,126,34,0.8)' : 'rgba(149,165,166,0.8)';
}}

// Touch support
renderer.domElement.addEventListener('touchstart', (e) => {{
    isDragging = true;
    previousMousePosition = {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
}});
renderer.domElement.addEventListener('touchmove', (e) => {{
    if (isDragging) {{
        const delta = {{ 
            x: e.touches[0].clientX - previousMousePosition.x, 
            y: e.touches[0].clientY - previousMousePosition.y 
        }};
        spherical.theta -= delta.x * 0.01;
        spherical.phi = Math.max(0.1, Math.min(Math.PI/2 - 0.05, spherical.phi + delta.y * 0.01));
        previousMousePosition = {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
        updateCamera();
    }}
}});
renderer.domElement.addEventListener('touchend', () => isDragging = false);

// Forzar primer render
updateCamera();
renderer.render(scene, camera);

// Debug: verificar que hay objetos en la escena
console.log('Objetos en escena:', scene.children.length);
console.log('Total width:', totalW, 'Total depth:', totalD);
console.log('Center:', centerX, centerZ);

// ============================================
// PANTALLA COMPLETA
// ============================================
let fullscreenRenderer = null;
let fullscreenAnimating = false;

function openInNewTab() {{
    const htmlContent = document.documentElement.outerHTML;
    const blob = new Blob([htmlContent], {{type: 'text/html'}});
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
}}

function closeFullscreen() {{
    if (document.exitFullscreen) {{
        document.exitFullscreen();
    }} else if (document.webkitExitFullscreen) {{
        document.webkitExitFullscreen();
    }}
    document.getElementById('modal-3d').classList.remove('active');
}}

// Animación
function animate() {{
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}}
animate();

// Responsive
window.addEventListener('resize', () => {{
    const w = container.clientWidth;
    camera.aspect = w / 550;
    camera.updateProjectionMatrix();
    renderer.setSize(w, 550);
}});
</script>

<!-- Modal pantalla completa -->
<div id="modal-3d">
    <p id="modal-title">🏠 Vista 3D Completa — Arrastra para rotar · Scroll para zoom · ESC para cerrar</p>
    <div id="modal-canvas-container">
        <button id="modal-close" onclick="closeFullscreen()">✕ Cerrar</button>
    </div>
</div>

</body>
</html>
"""
        # Reemplazar el tipo de tejado
        html = html.replace('{{roof_type}}', self.roof_type)
        return html
