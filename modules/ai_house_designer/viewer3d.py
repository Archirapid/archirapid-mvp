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
    
    def __init__(self, design, roof_type: str = "Dos aguas"):
        self.design = design
        self.roof_type = roof_type
    
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
        """
        Layout arquitectónico real:
        - INTERIOR: habitaciones dentro de la casa conectadas
        - EXTERIOR PRÓXIMO: garaje, porche pegados a la casa
        - EXTERIOR JARDÍN: piscina, huerto, caseta alejados
        """
        layout = []
        
        # CLASIFICAR HABITACIONES
        interior = []    # Dentro de la casa
        ext_close = []   # Exterior próximo (garaje, porche)
        ext_garden = []  # Exterior jardín (piscina, huerto, caseta)
        
        INTERIOR_CODES = ['salon', 'cocina', 'dormitorio', 'bano', 
                         'pasillo', 'bodega', 'despacho', 'instalac']
        EXT_CLOSE_CODES = ['garaje', 'porche', 'terraza']
        EXT_GARDEN_CODES = ['piscina', 'pool', 'huerto', 'caseta', 
                           'aperos', 'paneles', 'bomba']
        
        for room in self.design.rooms:
            code = room.room_type.code.lower()
            name = room.room_type.name.lower()
            combined = code + name
            
            if any(x in combined for x in EXT_GARDEN_CODES):
                ext_garden.append(room)
            elif any(x in combined for x in EXT_CLOSE_CODES):
                ext_close.append(room)
            else:
                interior.append(room)
        
        # Ordenar interior: salón primero, luego dormitorios, luego baños
        def room_priority(r):
            code = r.room_type.code.lower()
            if 'salon' in code or 'cocina' in code: return 0
            if 'dormitorio' in code and 'principal' in code: return 1
            if 'dormitorio' in code: return 2
            if 'bano' in code: return 3
            if 'pasillo' in code: return 4
            return 5
        
        interior.sort(key=room_priority)
        
        # =====================
        # LAYOUT INTERIOR
        # =====================
        # Distribuir habitaciones interiores en grid 2 columnas
        # Columna izquierda: zona día (salón, cocina)
        # Columna derecha: zona noche (dormitorios, baños)
        
        zona_dia = [r for r in interior if any(x in r.room_type.code.lower() 
                   for x in ['salon', 'cocina', 'despacho'])]
        zona_noche = [r for r in interior if any(x in r.room_type.code.lower() 
                     for x in ['dormitorio'])]
        zona_servicio = [r for r in interior if any(x in r.room_type.code.lower() 
                        for x in ['bano', 'pasillo', 'bodega', 'instalac'])]
        
        # Calcular ancho de cada zona
        max_dia_w = 0
        max_noche_w = 0
        max_serv_w = 0
        
        # Zona día - columna izquierda
        y_pos = 0
        for room in zona_dia:
            w, d = self._calculate_dimensions(room.area_m2, 1.4)
            layout.append({'room': room, 'x': 0, 'z': y_pos, 
                          'width': w, 'depth': d, 'zone': 'interior'})
            max_dia_w = max(max_dia_w, w)
            y_pos += d
        
        total_interior_depth = max(y_pos, 1)
        
        # Zona servicio - columna central
        x_serv = max_dia_w
        y_pos = 0
        for room in zona_servicio:
            w, d = self._calculate_dimensions(room.area_m2, 0.75)
            layout.append({'room': room, 'x': x_serv, 'z': y_pos,
                          'width': w, 'depth': d, 'zone': 'interior'})
            max_serv_w = max(max_serv_w, w)
            y_pos += d
        
        total_interior_depth = max(total_interior_depth, y_pos)
        
        # Zona noche - columna derecha
        x_noche = max_dia_w + max_serv_w
        y_pos = 0
        for room in zona_noche:
            w, d = self._calculate_dimensions(room.area_m2, 1.3)
            layout.append({'room': room, 'x': x_noche, 'z': y_pos,
                          'width': w, 'depth': d, 'zone': 'interior'})
            max_noche_w = max(max_noche_w, w)
            y_pos += d
        
        total_interior_depth = max(total_interior_depth, y_pos)
        
        # Dimensiones totales del interior
        house_width = max_dia_w + max_serv_w + max_noche_w
        house_depth = total_interior_depth
        
        # =====================
        # EXTERIOR PRÓXIMO
        # =====================
        # Garaje: a la izquierda de la casa
        # Porche: delante de la casa (z negativo)
        
        garaje_rooms = [r for r in ext_close if 'garaje' in r.room_type.code.lower()]
        porche_rooms = [r for r in ext_close if any(x in r.room_type.code.lower() 
                       for x in ['porche', 'terraza'])]
        
        # Garaje a la izquierda
        x_garaje = -8  # 8m a la izquierda
        y_garaje = 0
        for room in garaje_rooms:
            w, d = self._calculate_dimensions(room.area_m2, 1.5)
            layout.append({'room': room, 'x': x_garaje, 'z': y_garaje,
                          'width': w, 'depth': d, 'zone': 'ext_close'})
            y_garaje += d
        
        # Porche delante (z negativo = frente de la casa)
        x_porche = house_width * 0.2
        z_porche = -5  # 5m delante
        for room in porche_rooms:
            w = house_width * 0.6
            d = room.area_m2 / max(w, 1)
            layout.append({'room': room, 'x': x_porche, 'z': z_porche,
                          'width': w, 'depth': d, 'zone': 'ext_close'})
            z_porche -= d
        
        # =====================
        # EXTERIOR JARDÍN
        # =====================
        # Piscina: detrás de la casa
        # Huerto: a la derecha exterior
        # Caseta aperos: a la derecha exterior
        # Paneles solares: encima (tejado, no en suelo)
        
        piscina_rooms = [r for r in ext_garden if any(x in r.room_type.code.lower() 
                        for x in ['piscina', 'pool'])]
        huerto_rooms = [r for r in ext_garden if 'huerto' in r.room_type.code.lower()]
        caseta_rooms = [r for r in ext_garden if 'caseta' in r.room_type.code.lower()]
        paneles_rooms = [r for r in ext_garden if 'panel' in r.room_type.code.lower()]
        otros_garden = [r for r in ext_garden if r not in piscina_rooms + huerto_rooms 
                       + caseta_rooms + paneles_rooms]
        
        # Piscina detrás de la casa
        z_pool = house_depth + 5  # 5m detrás
        for room in piscina_rooms:
            w, d = self._calculate_dimensions(room.area_m2, 2.0)  # más ancha
            x_pool = (house_width - w) / 2  # centrada
            layout.append({'room': room, 'x': x_pool, 'z': z_pool,
                          'width': w, 'depth': d, 'zone': 'pool'})
            z_pool += d + 2
        
        # Huerto a la derecha exterior
        x_huerto = house_width + 4
        z_huerto = 0
        for room in huerto_rooms:
            w, d = self._calculate_dimensions(room.area_m2, 1.5)
            layout.append({'room': room, 'x': x_huerto, 'z': z_huerto,
                          'width': w, 'depth': d, 'zone': 'garden'})
            z_huerto += d + 1
        
        # Caseta aperos a la derecha (más alejada)
        x_caseta = house_width + 4
        z_caseta = z_huerto + 2
        for room in caseta_rooms:
            w, d = self._calculate_dimensions(room.area_m2, 1.2)
            layout.append({'room': room, 'x': x_caseta, 'z': z_caseta,
                          'width': w, 'depth': d, 'zone': 'ext_close'})
            z_caseta += d + 1
        
        # Paneles solares: en el tejado (ignorar en layout suelo)
        for room in paneles_rooms:
            # Los colocamos en el tejado, arriba de la casa
            layout.append({'room': room, 
                          'x': house_width * 0.3, 
                          'z': house_depth * 0.2,
                          'width': 4, 'depth': 2, 
                          'zone': 'roof',
                          'y_offset': self.WALL_HEIGHT + 0.1})
        
        # Otros extras de jardín
        x_otros = house_width + 4
        z_otros = z_caseta + 2
        for room in otros_garden:
            w, d = self._calculate_dimensions(room.area_m2, 1.3)
            layout.append({'room': room, 'x': x_otros, 'z': z_otros,
                          'width': w, 'depth': d, 'zone': 'garden'})
            z_otros += d + 1
        
        # Calcular dimensiones totales
        all_x = [item['x'] + item['width'] for item in layout]
        all_z = [item['z'] + item['depth'] for item in layout]
        min_x = min([item['x'] for item in layout] or [0])
        min_z = min([item['z'] for item in layout] or [0])
        
        self.total_width = max(all_x or [10]) - min(0, min_x)
        self.total_depth = max(all_z or [10]) - min(0, min_z)
        self.house_width = house_width
        self.house_depth = house_depth
        
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

// Tejado OPCIONAL - Por defecto oculto para ver planta
let roofVisible = false;
const roofGroup = new THREE.Group();

const roofMat = new THREE.MeshLambertMaterial({{ color: 0xB55A30, side: THREE.DoubleSide }});

// Tejado frente
const roofFrontGeo = new THREE.BufferGeometry();
const rfv = new Float32Array([
    -1, 0, -1,  totalW+1, 0, -1,  totalW/2, 2.0, totalD/2,
    -1, 0, -1,  totalW/2, 2.0, totalD/2,  -1, 0, -1
]);
roofFrontGeo.setAttribute('position', new THREE.BufferAttribute(rfv, 3));
roofFrontGeo.computeVertexNormals();
const roofFront = new THREE.Mesh(roofFrontGeo, roofMat);
roofFront.position.y = {self.WALL_HEIGHT};
roofGroup.add(roofFront);

// Tejado atrás
const roofBackGeo = new THREE.BufferGeometry();
const rbv = new Float32Array([
    -1, 0, totalD+1,  totalW+1, 0, totalD+1,  totalW/2, 2.0, totalD/2,
    -1, 0, totalD+1,  totalW/2, 2.0, totalD/2,  -1, 0, totalD+1
]);
roofBackGeo.setAttribute('position', new THREE.BufferAttribute(rbv, 3));
roofBackGeo.computeVertexNormals();
const roofBack = new THREE.Mesh(roofBackGeo, roofMat);
roofBack.position.y = {self.WALL_HEIGHT};
roofGroup.add(roofBack);

// Planos laterales
const roofLGeo = new THREE.BufferGeometry();
const rlv = new Float32Array([
    -1,0,-1,  -1,0,totalD+1,  totalW/2,2.0,totalD/2,
]);
roofLGeo.setAttribute('position', new THREE.BufferAttribute(rlv, 3));
roofLGeo.computeVertexNormals();
const roofLeft = new THREE.Mesh(roofLGeo, roofMat);
roofLeft.position.y = {self.WALL_HEIGHT};
roofGroup.add(roofLeft);

const roofRGeo = new THREE.BufferGeometry();
const rrv = new Float32Array([
    totalW+1,0,-1,  totalW+1,0,totalD+1,  totalW/2,2.0,totalD/2,
]);
roofRGeo.setAttribute('position', new THREE.BufferAttribute(rrv, 3));
roofRGeo.computeVertexNormals();
const roofRight = new THREE.Mesh(roofRGeo, roofMat);
roofRight.position.y = {self.WALL_HEIGHT};
roofGroup.add(roofRight);

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
        return html
