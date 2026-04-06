"""
Generador de planos arquitectónicos profesionales en SVG
FIX 2026-04-05: #7 dimensiones desde layout real (no recalcular desde área)
"""
import math
from typing import List, Dict, Tuple, Optional
import io

# Forzar backend sin pantalla ANTES de cualquier import de pyplot
import matplotlib
matplotlib.use('Agg')

from .architect_layout import ArchitectLayout, ZONE_DAY, ZONE_NIGHT, ZONE_WET, ZONE_CIRCULATION, ZONE_SERVICE, ZONE_EXTERIOR, ZONE_GARDEN

class FloorPlanSVG:
    """Genera planos arquitectónicos reales en SVG"""
    
    # Escala: 1 metro = 50 pixels
    SCALE = 50
    MARGIN = 60
    WALL_THICKNESS = 6
    
    # Colores profesionales por tipo
    ROOM_COLORS = {
        'salon': '#F5F0E8',
        'cocina': '#F5F0E8', 
        'dormitorio': '#EEF0F5',
        'bano': '#E8F5F0',
        'garaje': '#F0F0F0',
        'porche': '#E8F5E8',
        'bodega': '#F5F5E8',
        'pasillo': '#EBEBEB',
        'paneles': '#FFF8E8',
        'piscina': '#E8F4FF',
        'huerto': '#E8F5E8',
        'despacho': '#F0EEF5',
        'default': '#F5F5F5'
    }
    
    def __init__(self, design):
        self.design = design
        self.rooms_layout = []
    
    def _get_color(self, code: str) -> str:
        code_lower = code.lower()
        for key, color in self.ROOM_COLORS.items():
            if key in code_lower:
                return color
        return self.ROOM_COLORS['default']
    
    def _calculate_room_dimensions(self, area_m2: float, ratio: float = 1.4) -> Tuple[float, float]:
        """Calcula ancho y alto en metros con ratio dado"""
        # Protección contra área 0 o negativa
        safe_area = max(area_m2, 1.0)
        width = math.sqrt(safe_area * ratio)
        # Protección contra width 0
        if width < 0.1:
            width = 1.0
        height = safe_area / width
        if height < 0.1:
            height = 1.0
        return round(width, 1), round(height, 1)
    
    def _layout_rooms(self) -> List[Dict]:
        """Usa el motor arquitectónico real para layout coherente"""
        
        # Preparar datos para el motor
        rooms_data = []
        for room in self.design.rooms:
            rooms_data.append({
                'code': room.room_type.code,
                'name': room.room_type.name,
                'area_m2': max(room.area_m2, 1.0)
            })
        
        # Generar layout arquitectónico
        house_shape = getattr(self.design, 'request', {}).get('house_shape', 'Rectangular (más común)')
        engine = ArchitectLayout(rooms_data, house_shape)
        layout_raw = engine.generate()
        
        # Post-pass: reempaquetar filas para eliminar huecos (packRows equivalente Python)
        _SNAP = 0.6
        _rows: dict = {}
        for item in layout_raw:
            z_key = None
            for k in _rows:
                if abs(float(k) - item['z']) < _SNAP:
                    z_key = k
                    break
            if z_key is None:
                z_key = f"{item['z']:.2f}"
                _rows[z_key] = []
            _rows[z_key].append(item)
        for z_key, row in _rows.items():
            row.sort(key=lambda i: i['x'])
            cur_x = min(i['x'] for i in row)
            row_d = max(i['depth'] for i in row)
            for item in row:
                item['x'] = round(cur_x, 3)
                item['depth'] = row_d
                cur_x += item['width']

        # Guardar dimensiones totales
        all_x = [item['x'] + item['width'] for item in layout_raw]
        all_z = [item['z'] + item['depth'] for item in layout_raw]
        self.total_width = max(all_x) if all_x else 10
        self.total_height = max(all_z) if all_z else 10
        
        # Convertir al formato esperado por generate()
        # Cruzar de vuelta con los room objects originales para tener room_type
        layout = []
        for i, item in enumerate(layout_raw):
            # Buscar el room original por nombre/código
            original_room = None
            for room in self.design.rooms:
                if (room.room_type.code == item['code'] or 
                    room.room_type.name == item['name']):
                    original_room = room
                    break
            
            # Si es el pasillo auto-generado, crear room sintético
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
                'y': item['z'],      # El SVG usa 'y' para la profundidad
                'width': item['width'],
                'height': item['depth'],  # El SVG usa 'height' para profundidad
                'zone': item.get('zone', 'day')
            })
        
        return layout
    
    def _room_to_svg(self, item: Dict, svg_width: int, svg_height: int) -> str:
        """Convierte una habitación a SVG con paredes profesionales"""
        
        room = item['room']
        
        # Convertir metros a pixels
        px = item['x'] * self.SCALE + self.MARGIN
        py = (self.total_height - item['y'] - item['height']) * self.SCALE + self.MARGIN
        pw = item['width'] * self.SCALE
        ph = item['height'] * self.SCALE
        
        color = self._get_color(room.room_type.code)
        name = room.room_type.name
        area = room.area_m2
        w_m = item['width']
        h_m = item['height']
        
        # ID para el elemento
        room_id = room.room_type.code.replace('_', '-')
        
        svg = f"""
        <!-- {name} -->
        <g id="{room_id}">
            <!-- Fondo habitación -->
            <rect x="{px}" y="{py}" width="{pw}" height="{ph}"
                  fill="{color}" stroke="#2C3E50" stroke-width="{self.WALL_THICKNESS}"/>
            
            <!-- Nombre habitación -->
            <text x="{px + pw/2}" y="{py + ph/2 - 12}"
                  text-anchor="middle" dominant-baseline="middle"
                  font-family="Arial, sans-serif" font-size="11" 
                  font-weight="bold" fill="#2C3E50">
                {name}
            </text>
            
            <!-- Dimensiones en metros -->
            <text x="{px + pw/2}" y="{py + ph/2 + 6}"
                  text-anchor="middle" dominant-baseline="middle"
                  font-family="Arial, sans-serif" font-size="9" fill="#555">
                {w_m:.1f}m × {h_m:.1f}m
            </text>
            
            <!-- Área -->
            <text x="{px + pw/2}" y="{py + ph/2 + 20}"
                  text-anchor="middle" dominant-baseline="middle"
                  font-family="Arial, sans-serif" font-size="10" 
                  font-weight="bold" fill="#1565C0">
                {area:.0f} m²
            </text>
            
            <!-- Cotas superiores -->
            <line x1="{px}" y1="{py - 15}" x2="{px + pw}" y2="{py - 15}"
                  stroke="#888" stroke-width="1" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
            <text x="{px + pw/2}" y="{py - 20}"
                  text-anchor="middle" font-family="Arial" font-size="8" fill="#666">
                {w_m:.1f} m
            </text>
            
            <!-- Cotas laterales -->
            <line x1="{px - 15}" y1="{py}" x2="{px - 15}" y2="{py + ph}"
                  stroke="#888" stroke-width="1"/>
            <text x="{px - 20}" y="{py + ph/2}"
                  text-anchor="middle" font-family="Arial" font-size="8" 
                  fill="#666" transform="rotate(-90, {px - 20}, {py + ph/2})">
                {h_m:.1f} m
            </text>
        </g>
        """
        return svg
    
    def generate(self) -> bytes:
        """Genera plano cenital profesional tipo arquitectónico"""
        import matplotlib.pyplot as plt
        import numpy as np
        import io

        layout = self._layout_rooms()

        # Canvas proporcional
        svg_width = max(int(self.total_width * self.SCALE + self.MARGIN * 3), 600)
        svg_height = max(int(self.total_height * self.SCALE + self.MARGIN * 4), 400)

        fig_w = svg_width / 100
        fig_h = svg_height / 100
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor='#F2EDE4')
        ax.set_xlim(0, svg_width)
        ax.set_ylim(0, svg_height)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('#F2EDE4')

        # Colores por zona arquitectónica (preferencia)
        zone_colors = {
            ZONE_DAY:         '#F5F0E8',  # Beige cálido - zona día
            ZONE_NIGHT:       '#EAE8F0',  # Lila suave - dormitorios
            ZONE_WET:         '#E0EEF0',  # Azul agua - baños
            ZONE_CIRCULATION: '#F0F0F0',  # Gris claro - pasillo
            ZONE_SERVICE:     '#E8E8E8',  # Gris - servicios
            ZONE_EXTERIOR:    '#E8F0E8',  # Verde suave - exterior
            ZONE_GARDEN:      '#D4EDDA',  # Verde jardín
        }
        
        # También mantener por código como fallback
        colors_map = {
            'salon':    '#F5F0E8',
            'cocina':   '#F5F0E8',
            'dormitorio': '#EAE8F0',
            'bano':     '#E0EEF0',
            'garaje':   '#DCDCDC',
            'porche':   '#E8F0E8',
            'bodega':   '#F0EDE0',
            'pasillo':  '#F0F0F0',
            'piscina':  '#B8DFF0',
            'huerto':   '#C8E6C9',
            'caseta':   '#D7CCC8',
            'despacho': '#EDE7F6',
            'default':  '#F5F5F5'
        }

        wall_color = '#2C2C2C'
        wall_lw = 3.5

        total_area = sum(r.area_m2 for r in self.design.rooms)

        # Barra de título superior
        title_h = 45
        ax.add_patch(plt.Rectangle(
            (0, svg_height - title_h), svg_width, title_h,
            facecolor='#2C3E50', zorder=10
        ))
        ax.text(svg_width / 2, svg_height - title_h / 2,
                f'PLANO DE DISTRIBUCIÓN  —  {total_area:.0f} m² TOTALES',
                ha='center', va='center',
                fontsize=13, fontweight='bold', color='white',
                fontfamily='monospace', zorder=11)

        # Subtítulo
        ax.text(svg_width / 2, svg_height - title_h - 14,
                'Escala aproximada 1:100  ·  Medidas en metros',
                ha='center', va='center',
                fontsize=8, color='#888888', style='italic')

        for item in layout:
            room = item['room']
            code = room.room_type.code.lower()
            name = room.room_type.name

            px = item['x'] * self.SCALE + self.MARGIN
            py = (self.total_height - item['y'] - item['height']) * self.SCALE + self.MARGIN
            pw = item['width'] * self.SCALE
            ph = item['height'] * self.SCALE

            # Color por zona primero, luego por código
            zone = item.get('zone', '')
            fill = zone_colors.get(zone, '#F5F5F5')
            if fill == '#F5F5F5':  # Fallback por código
                for key, c in colors_map.items():
                    if key in code:
                        fill = c
                        break

            # Fondo con sombra sutil
            shadow = plt.Rectangle(
                (px + 2, py - 2), pw, ph,
                facecolor='#00000015', zorder=1
            )
            ax.add_patch(shadow)

            # Habitación principal
            room_rect = plt.Rectangle(
                (px, py), pw, ph,
                facecolor=fill,
                edgecolor=wall_color,
                linewidth=wall_lw,
                zorder=2
            )
            ax.add_patch(room_rect)

            # Textura de suelo (líneas diagonales sutiles para zonas húmedas)
            if any(x in code for x in ['bano', 'cocina']):
                for offset in range(0, int(pw + ph), 8):
                    x0 = px + max(0, offset - ph)
                    x1 = px + min(pw, offset)
                    y0 = py + max(0, ph - offset)
                    y1 = py + min(ph, ph + pw - offset)
                    if x0 < x1:
                        ax.plot([x0, x1], [y0, y1],
                                color='#00000008', lw=0.5, zorder=3)

            # Nombre de habitación
            font_size = max(6.5, min(10, pw / 12))
            ax.text(px + pw / 2, py + ph * 0.58,
                    name,
                    ha='center', va='center',
                    fontsize=font_size,
                    fontweight='bold',
                    color='#2C3E50',
                    zorder=5)

            # FIX #7: usar dimensiones reales del layout (no recalcular desde área)
            _disp_w = round(item["width"], 1)
            _disp_h = round(item["height"], 1)
            ax.text(px + pw / 2, py + ph * 0.38,
                    f'{_disp_w:.1f}m × {_disp_h:.1f}m',
                    ha='center', va='center',
                    fontsize=max(5.5, font_size - 1.5),
                    color='#666666',
                    zorder=5)

            # Área en azul
            ax.text(px + pw / 2, py + ph * 0.20,
                    f'{room.area_m2:.0f} m²',
                    ha='center', va='center',
                    fontsize=max(6, font_size - 0.5),
                    fontweight='bold',
                    color='#1565C0',
                    zorder=5)

            # Cota ancho (arriba)
            cota_y = py + ph + 8
            ax.annotate('', xy=(px + pw, cota_y),
                        xytext=(px, cota_y),
                        arrowprops=dict(arrowstyle='<->', color='#999999',
                                        lw=0.8, mutation_scale=6),
                        zorder=4)
            ax.plot([px, px], [py + ph, cota_y], color='#BBBBBB', lw=0.5, zorder=4)
            ax.plot([px + pw, px + pw], [py + ph, cota_y],
                    color='#BBBBBB', lw=0.5, zorder=4)
            ax.text(px + pw / 2, cota_y + 5,
                    f'{item["width"]:.1f} m',
                    ha='center', va='bottom',
                    fontsize=6, color='#888888', zorder=5)

            # Cota alto (lado izquierdo)
            cota_x = px - 12
            ax.annotate('', xy=(cota_x, py + ph),
                        xytext=(cota_x, py),
                        arrowprops=dict(arrowstyle='<->', color='#999999',
                                        lw=0.8, mutation_scale=6),
                        zorder=4)
            ax.plot([cota_x, px], [py, py], color='#BBBBBB', lw=0.5, zorder=4)
            ax.plot([cota_x, px], [py + ph, py + ph],
                    color='#BBBBBB', lw=0.5, zorder=4)
            ax.text(cota_x - 3, py + ph / 2,
                    f'{item["height"]:.1f} m',
                    ha='right', va='center',
                    fontsize=6, color='#888888',
                    rotation=90, zorder=5)

            # ================================================
            # PUERTAS — lógica de circulación completa
            # En pantalla: sur=abajo(porche/entrada), norte=arriba(fondo/privado)
            # ================================================
            door_r = min(pw, ph) * 0.18
            door_r = min(door_r, 18)
            theta = np.linspace(0, np.pi / 2, 20)

            if any(x in code for x in ['dormitorio', 'bano', 'despacho', 'bodega']):
                # Pared SUPERIOR — da al pasillo (norte=privado)
                door_x = px + door_r * np.cos(theta)
                door_y = (py + ph) - door_r * np.sin(theta)
                ax.plot(door_x, door_y, color=wall_color, lw=1.2,
                        linestyle='--', zorder=6)
                ax.plot([px, px + door_r], [py + ph, py + ph],
                        color=wall_color, lw=1.2, zorder=6)

            elif any(x in code for x in ['salon', 'cocina', 'salón']):
                # Puerta INFERIOR — da al porche (entrada sur)
                door_x = px + door_r * np.cos(theta)
                door_y = py + door_r * np.sin(theta)
                ax.plot(door_x, door_y, color=wall_color, lw=1.2,
                        linestyle='--', zorder=6)
                ax.plot([px, px], [py, py + door_r],
                        color=wall_color, lw=1.2, zorder=6)
                # Segunda puerta SUPERIOR — da al pasillo (hacia dormitorios)
                door_x2 = px + door_r * np.cos(theta)
                door_y2 = (py + ph) - door_r * np.sin(theta)
                ax.plot(door_x2, door_y2, color=wall_color, lw=1.2,
                        linestyle='--', zorder=6)
                ax.plot([px, px + door_r], [py + ph, py + ph],
                        color=wall_color, lw=1.2, zorder=6)

            elif any(x in code for x in ['porche', 'terraza']):
                # Puerta SUPERIOR — da al salón (entrada a la casa)
                door_x = px + pw/2 - door_r/2 + door_r * np.cos(theta)
                door_y = (py + ph) - door_r * np.sin(theta)
                ax.plot(door_x, door_y, color=wall_color, lw=1.8,
                        linestyle='--', zorder=6)
                ax.plot([px + pw/2 - door_r/2, px + pw/2 + door_r/2],
                        [py + ph, py + ph],
                        color=wall_color, lw=1.8, zorder=6)

            elif 'garaje' in code or 'garage' in code:
                # Portón vehículo — pared INFERIOR (fachada sur, desde calle)
                ax.plot([px + pw * 0.15, px + pw * 0.85],
                        [py, py],
                        color='#E67E22', lw=3.5, zorder=6)
                # Puerta peatonal — pared IZQUIERDA (acceso desde salón/cocina)
                mid_y = py + ph / 2
                door_x_p = px + door_r * np.sin(theta)
                door_y_p = mid_y + door_r * np.cos(theta)
                ax.plot(door_x_p, door_y_p, color=wall_color, lw=1.2,
                        linestyle='--', zorder=6)
                ax.plot([px, px], [mid_y, mid_y + door_r],
                        color=wall_color, lw=1.2, zorder=6)

        # Brújula Norte
        cx, cy, cr = svg_width - 35, 70, 22
        circle_n = plt.Circle((cx, cy), cr, fill=False,
                               edgecolor='#2C3E50', linewidth=1.5, zorder=10)
        ax.add_patch(circle_n)
        ax.annotate('', xy=(cx, cy + cr - 4),
                    xytext=(cx, cy),
                    arrowprops=dict(arrowstyle='->', color='#E74C3C',
                                    lw=2, mutation_scale=10),
                    zorder=11)
        ax.text(cx, cy + cr + 8, 'N',
                ha='center', va='bottom',
                fontsize=10, fontweight='bold', color='#2C3E50', zorder=11)

        # Leyenda colores
        legend_x = 15
        legend_y = svg_height - title_h - 35
        legend_items = [
            ('Zona Día', '#F5F0E8'),
            ('Dormitorios', '#EAE8F0'),
            ('Baños', '#E0EEF0'),
            ('Exterior', '#E8F0E8'),
        ]
        for i, (label, color) in enumerate(legend_items):
            bx = legend_x + i * 90
            ax.add_patch(plt.Rectangle((bx, legend_y), 12, 10,
                                        facecolor=color,
                                        edgecolor='#999999', lw=0.8, zorder=10))
            ax.text(bx + 15, legend_y + 5, label,
                    va='center', fontsize=7, color='#555555', zorder=10)

        # Pie de página
        ax.text(svg_width / 2, 10,
                'ArchiRapid AI  ·  Plano de distribución  ·  © 2025',
                ha='center', va='bottom',
                fontsize=7, color='#AAAAAA', style='italic')

        plt.tight_layout(pad=0)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150,
                    bbox_inches='tight',
                    facecolor='#F2EDE4', edgecolor='none')
        plt.close()
        buf.seek(0)
        return buf.getvalue()


# ─── Planos Técnicos MEP ──────────────────────────────────────────────────────

def generate_mep_plan_png(rooms_layout, layer_name: str,
                          total_width: float = None, total_depth: float = None) -> bytes:
    """
    Genera un plano técnico 2D en PNG para una capa MEP específica.

    Args:
        rooms_layout : lista de dicts {x, z, width, depth, name, code, zone, area_m2}
                       o JSON string equivalente
        layer_name   : 'sewage' | 'water' | 'electrical' | 'rainwater' | 'domotics'
        total_width/depth : dimensiones casa (se calculan si None)

    Returns:
        PNG bytes
    """
    import json
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import io as _io

    if isinstance(rooms_layout, str):
        try:
            rooms_layout = json.loads(rooms_layout)
        except Exception:
            return None
    if not rooms_layout:
        return None

    SCALE  = 50   # px / metro
    MARGIN = 70

    if total_width is None:
        total_width  = max(r['x'] + r['width']  for r in rooms_layout)
    if total_depth is None:
        total_depth  = max(r['z'] + r['depth']  for r in rooms_layout)

    house_max_z = max(r['z'] + r['depth']  for r in rooms_layout)
    house_max_x = max(r['x'] + r['width']  for r in rooms_layout)
    house_min_x = min(r['x']               for r in rooms_layout)

    LAYERS_CFG = {
        'sewage':     {'label': 'SANEAMIENTO',          'color': '#555555', 'bg': '#F9F9F9'},
        'water':      {'label': 'AGUA FRÍA / CALIENTE', 'color': '#1565C0', 'bg': '#F0F8FF'},
        'electrical': {'label': 'INSTALACIÓN ELÉCTRICA','color': '#BF360C', 'bg': '#FFF8F0'},
        'rainwater':  {'label': 'RECOGIDA PLUVIAL',     'color': '#1B5E20', 'bg': '#F0FFF0'},
        'domotics':   {'label': 'DOMÓTICA / RED DATOS', 'color': '#4A148C', 'bg': '#F8F0FF'},
    }
    cfg = LAYERS_CFG.get(layer_name, LAYERS_CFG['electrical'])
    lc  = cfg['color']

    # Canvas
    svg_w = int(total_width  * SCALE + MARGIN * 3 + 60)
    svg_h = int(total_depth  * SCALE + MARGIN * 4 + 60)

    fig, ax = plt.subplots(figsize=(svg_w / 100, svg_h / 100), facecolor=cfg['bg'])
    ax.set_xlim(0, svg_w)
    ax.set_ylim(0, svg_h)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(cfg['bg'])

    def to_px(x_m, z_m):
        """Metros → píxeles (z invertido: arriba = z pequeño)"""
        return MARGIN + x_m * SCALE, MARGIN + (total_depth - z_m) * SCALE

    def pline(x1, z1, x2, z2, color=None, lw=2.0, ls='-', zo=6):
        c = color or lc
        px1, py1 = to_px(x1, z1)
        px2, py2 = to_px(x2, z2)
        ax.plot([px1, px2], [py1, py2], color=c, linewidth=lw,
                linestyle=ls, zorder=zo, solid_capstyle='round')

    # ── Dibujar habitaciones ──────────────────────────────────────────────────
    ZONE_FILL = {
        'day':        '#FFF8E1',
        'night':      '#EDE7F6',
        'wet':        '#E0F2F1',
        'service':    '#ECEFF1',
        'garage':     '#E0E0E0',
        'exterior':   '#E8F5E9',
        'circulation':'#F5F5F5',
    }
    for r in rooms_layout:
        zone = (r.get('zone') or '').lower()
        code = (r.get('code') or '').lower()
        # Color por zona o código
        if any(c in code for c in ['bano', 'aseo', 'cocina']):
            fill = ZONE_FILL['wet']
        else:
            fill = ZONE_FILL.get(zone, '#F5F5F5')

        px, py = to_px(r['x'], r['z'] + r['depth'])
        pw, ph = r['width'] * SCALE, r['depth'] * SCALE
        rect = mpatches.Rectangle((px, py), pw, ph,
                                   linewidth=2, edgecolor='#333333',
                                   facecolor=fill, zorder=2)
        ax.add_patch(rect)
        cx, cy = px + pw / 2, py + ph / 2
        ax.text(cx, cy + 5, r.get('name', ''), ha='center', va='center',
                fontsize=6.5, color='#333333', fontweight='bold', zorder=5)
        ax.text(cx, cy - 7, f"{r['width']:.1f}×{r['depth']:.1f}m",
                ha='center', va='center', fontsize=5.5, color='#777777', zorder=5)

    # Wet rooms list (shared)
    wet_codes = ['bano', 'aseo', 'cocina']
    wet_rooms = [r for r in rooms_layout
                 if any(c in (r.get('code','') + r.get('name','')).lower() for c in wet_codes)]

    # ── Capa MEP ─────────────────────────────────────────────────────────────
    if layer_name == 'sewage':
        # Colector principal horizontal en la parte baja del plano
        col_z = house_max_z + 0.7
        col_x0, col_x1 = house_min_x - 0.3, house_max_x + 0.3
        pline(col_x0, col_z, col_x1, col_z, lw=3.5)
        # Etiqueta colector
        col_label_px, col_label_py = to_px((col_x0 + col_x1) / 2, col_z)
        ax.text(col_label_px, col_label_py - 12, 'COLECTOR Ø110', ha='center',
                fontsize=6, color=lc, fontweight='bold', zorder=8)

        # Ramales ortogonales: horizontal al eje X del colector, luego vertical al colector
        for i, r in enumerate(wet_rooms):
            cx  = r['x'] + r['width'] / 2
            cz  = r['z'] + r['depth'] / 2
            code = (r.get('code') or r.get('name') or '').lower()
            # Diámetro de ramal según tipo
            if 'cocina' in code:
                diam = 'Ø50'
            elif 'bano' in code or 'aseo' in code:
                diam = 'Ø40'
            else:
                diam = 'Ø40'

            # Punto codo: salir horizontalmente de la estancia hasta un carril lateral,
            # luego subir verticalmente hasta el colector
            codo_x = house_min_x - 0.6 - i * 0.35   # cada ramal sale por un carril distinto
            codo_z = col_z                             # altura del colector

            # Ramal salida de la estancia → punto de codo (horizontal)
            pline(cx, cz, codo_x, cz, lw=1.8, ls='--')
            # Tramo vertical codo → colector
            pline(codo_x, cz, codo_x, codo_z, lw=1.8, ls='--')
            # Tramo horizontal final al colector
            pline(codo_x, codo_z, col_x0, codo_z, lw=1.8, ls='--')

            # Arqueta en el codo (cuadrado pequeño)
            arq_px, arq_py = to_px(codo_x, cz)
            sq = 7
            ax.add_patch(mpatches.Rectangle((arq_px - sq/2, arq_py - sq/2), sq, sq,
                                             linewidth=1.5, edgecolor=lc,
                                             facecolor='white', zorder=8))

            # Punto de descarga en la estancia (círculo)
            ppx, ppy = to_px(cx, cz)
            ax.plot(ppx, ppy, 'o', color=lc, markersize=6, zorder=7)

            # Etiqueta diámetro ramal
            ax.text(arq_px - 10, arq_py - 14, diam, fontsize=5.5, color=lc,
                    ha='center', va='top', zorder=8)

        # Fosa séptica exterior (derecha)
        fx, fz_c = house_max_x + 2.3, house_max_z * 0.45
        fpx, fpy = to_px(fx, fz_c + 0.8)
        ax.add_patch(mpatches.Rectangle((fpx, fpy - 0.8 * SCALE), 2.2 * SCALE, 1.6 * SCALE,
                                         linewidth=2, edgecolor=lc, facecolor='#DDDDDD', zorder=6))
        ax.text(fpx + 1.1 * SCALE, fpy - 0.4 * SCALE, 'FOSA\nSÉPTICA',
                ha='center', va='center', fontsize=5.5, color=lc, fontweight='bold', zorder=7)
        # Conexión colector → fosa
        pline(col_x1, col_z, house_max_x + 2.3, col_z, lw=2.5)
        pline(house_max_x + 2.3, col_z, fx, fz_c, lw=2.5)

    elif layer_name == 'water':
        mz = house_max_z * 0.5
        pline(house_min_x - 0.7, mz, house_max_x + 0.3, mz, lw=3)
        for r in wet_rooms:
            cx, cz = r['x'] + r['width']/2, r['z'] + r['depth']/2
            pline(cx, mz, cx, cz, lw=1.8)
            ppx, ppy = to_px(cx, cz)
            ax.plot(ppx, ppy, 's', color=lc, markersize=5, zorder=7)
        epx, epy = to_px(house_min_x - 0.7, mz)
        ax.text(epx - 4, epy, 'ACOMETIDA', ha='right', va='center',
                fontsize=5.5, color=lc, fontweight='bold', rotation=90)

    elif layer_name == 'electrical':
        tz = rooms_layout[0]['z'] + rooms_layout[0]['depth']/2
        px0 = house_min_x + 0.3
        pline(px0, tz, house_max_x + 0.2, tz, lw=3)
        for r in rooms_layout:
            cx, cz = r['x'] + r['width']/2, r['z'] + r['depth']/2
            pline(cx, tz, cx, cz, lw=1.2, ls='--')
            ppx, ppy = to_px(cx, cz)
            ax.plot(ppx, ppy, '^', color=lc, markersize=4, zorder=7)
        # Panel (CGP)
        ppx, ppy = to_px(px0, tz)
        ax.add_patch(mpatches.Rectangle((ppx-10, ppy-12), 20, 24,
                                         linewidth=1.5, edgecolor=lc, facecolor='#FFE082', zorder=8))
        ax.text(ppx, ppy, 'CGP', ha='center', va='center',
                fontsize=5, color='#333333', fontweight='bold', zorder=9)

    elif layer_name == 'rainwater':
        for z_val in [house_max_z + 0.3, -0.3]:
            pline(house_min_x - 0.3, z_val, house_max_x + 0.3, z_val, lw=2.5)
        for dx, dz in [(house_min_x-0.3, house_max_z+0.3), (house_max_x+0.3, house_max_z+0.3),
                       (house_min_x-0.3, -0.3),             (house_max_x+0.3, -0.3)]:
            ppx, ppy = to_px(dx, dz)
            ax.plot(ppx, ppy, 'v', color=lc, markersize=9, zorder=7)
            ax.text(ppx, ppy - 14, 'BAJANTE', ha='center', va='top',
                    fontsize=5, color=lc, fontweight='bold')

    elif layer_name == 'domotics':
        tz = rooms_layout[0]['z'] + rooms_layout[0]['depth']/2 - 0.4
        px0 = house_min_x + 0.3
        pline(px0, tz, house_max_x + 0.2, tz, lw=2, ls='-.')
        for r in rooms_layout:
            cx, cz = r['x'] + r['width']/2, r['z'] + r['depth']/2
            pline(cx, tz, cx, cz, lw=1, ls=':')
            ppx, ppy = to_px(cx, cz)
            ax.plot(ppx, ppy, 'D', color=lc, markersize=4, zorder=7)
        # Hub
        ppx, ppy = to_px(px0, tz)
        ax.add_patch(mpatches.Circle((ppx, ppy), 10, linewidth=1.5,
                                      edgecolor=lc, facecolor='#E1BEE7', zorder=8))
        ax.text(ppx, ppy, 'HUB', ha='center', va='center',
                fontsize=5, color='#333333', fontweight='bold', zorder=9)

    # ── Título ────────────────────────────────────────────────────────────────
    title_h = 44
    ax.add_patch(mpatches.Rectangle((0, svg_h - title_h), svg_w, title_h,
                                     facecolor='#1A237E', zorder=10))
    ax.text(svg_w/2, svg_h - title_h/2,
            f'PLANO DE {cfg["label"]}  ·  Escala aprox. 1:100',
            ha='center', va='center', fontsize=10, fontweight='bold',
            color='white', fontfamily='monospace', zorder=11)

    # ── Pie ───────────────────────────────────────────────────────────────────
    ax.text(MARGIN, 10, f'Capa: {cfg["label"]}', color=lc,
            fontsize=6.5, fontweight='bold', va='bottom')
    ax.text(svg_w - MARGIN, 10, 'ArchiRapid AI  ·  © 2026',
            color='#AAAAAA', fontsize=6, ha='right', va='bottom')

    buf = _io.BytesIO()
    plt.tight_layout(pad=0)
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=cfg['bg'], edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─── Plano de Cimentación ─────────────────────────────────────────────────────

def _resolve_foundation_type(foundation_type_arg: str | None) -> str:
    """
    Lookup dinámico — prioridad:
      1. foundation_type_arg (si se pasa explícitamente, tiene MÁXIMA prioridad)
      2. st.session_state['selected_foundation'] (selector Paso 2)
      3. st.session_state['ai_house_requirements']['foundation_type']
      4. Fallback: 'zapatas'
    """
    # PRIORIDAD #1: argumento explícito siempre gana
    if foundation_type_arg and foundation_type_arg.strip():
        return foundation_type_arg.strip()
    try:
        import streamlit as _st
        # PRIORIDAD #2: session_state['selected_foundation']
        ft = _st.session_state.get("selected_foundation")
        if ft:
            return ft
    except Exception:
        pass
    try:
        import streamlit as _st
        ft = (_st.session_state.get("ai_house_requirements") or {}).get("foundation_type")
        if ft:
            return ft
    except Exception:
        pass
    return "zapatas"


def generate_cimentacion_plan_png(
    rooms_layout,
    foundation_type: str | None = None,   # None → lookup dinámico en session_state
    total_width=None,
    total_depth=None,
) -> bytes | None:
    """
    Genera plano PNG de cimentación a partir del layout de habitaciones.
    El tipo de cimentación se resuelve en orden:
      1. Argumento foundation_type si se pasa explícitamente.
      2. st.session_state['selected_foundation'] (selector Paso 2).
      3. st.session_state['ai_house_requirements']['foundation_type'].
      4. Fallback: 'zapatas'.

    Args:
        rooms_layout : lista de dicts con x, z, width, depth, name, code
        foundation_type : None (lookup dinámico) | "zapatas" | "losa" | "pilotes"
        total_width/depth : dimensiones casa (se calculan si None)

    Returns:
        PNG bytes o None si hay error.
    """
    foundation_type = _resolve_foundation_type(foundation_type)
    # Normalizar el tipo a tokens exactos (sin override de session_state)
    _ft_lower = (foundation_type or '').lower()
    if 'pilote' in _ft_lower:
        foundation_type = 'pilotes'
    elif 'losa' in _ft_lower:
        foundation_type = 'losa'
    elif 'zapata' in _ft_lower:
        foundation_type = 'zapatas'
    # Si no coincide ninguno, fallback zapatas
    if foundation_type not in ('zapatas', 'losa', 'pilotes'):
        foundation_type = 'zapatas'
    import json
    import math
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import io as _io

    if isinstance(rooms_layout, str):
        try:
            rooms_layout = json.loads(rooms_layout)
        except Exception:
            return None
    if not rooms_layout:
        return None

    SCALE  = 55   # px / metro
    MARGIN = 80
    BG     = '#FAFAF8'
    LC     = '#3E2723'    # marrón cimentación
    ZAP_W  = 0.40         # vuelo de zapata corrida (m) a cada lado del muro

    if total_width is None:
        total_width  = max(r['x'] + r['width']  for r in rooms_layout)
    if total_depth is None:
        total_depth  = max(r['z'] + r['depth']  for r in rooms_layout)

    house_max_x = max(r['x'] + r['width']  for r in rooms_layout)
    house_max_z = max(r['z'] + r['depth']  for r in rooms_layout)
    house_min_x = min(r['x']               for r in rooms_layout)
    house_min_z = min(r['z']               for r in rooms_layout)

    svg_w = int(total_width  * SCALE + MARGIN * 3 + 80)
    svg_h = int(total_depth  * SCALE + MARGIN * 4 + 80)

    fig, ax = plt.subplots(figsize=(svg_w / 100, svg_h / 100), facecolor=BG)
    ax.set_xlim(0, svg_w)
    ax.set_ylim(0, svg_h)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG)

    def to_px(x_m, z_m):
        return MARGIN + x_m * SCALE, MARGIN + (total_depth - z_m) * SCALE

    def prect(x_m, z_m, w_m, d_m, fc, ec, lw=1.5, zo=3, alpha=1.0):
        px, py = to_px(x_m, z_m + d_m)
        ax.add_patch(mpatches.Rectangle(
            (px, py), w_m * SCALE, d_m * SCALE,
            linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zo, alpha=alpha
        ))

    # ── Huella interior de habitaciones (gris claro) ──────────────────────────
    for r in rooms_layout:
        prect(r['x'], r['z'], r['width'], r['depth'],
              fc='#EEEEEE', ec='#BDBDBD', lw=1.0, zo=2, alpha=0.7)
        cx_px, cy_px = to_px(r['x'] + r['width']/2, r['z'] + r['depth']/2)
        ax.text(cx_px, cy_px, r.get('name', ''),
                ha='center', va='center', fontsize=5.5, color='#757575', zorder=3)

    # FIX #3: normalizar tipo de cimentación para cubrir variantes de pilotes
    _ft_norm = foundation_type.lower()
    if 'pilote' in _ft_norm or 'micropilote' in _ft_norm or _ft_norm.startswith('pil'):
        foundation_type = 'pilotes'
    elif 'losa' in _ft_norm or 'placa' in _ft_norm:
        foundation_type = 'losa'
    else:
        foundation_type = 'zapatas'

    if foundation_type == "pilotes":
        # ── PILOTES: círculos en esquinas + losa de encepado ─────────────────
        pil_r = 0.25  # radio pilote 50cm diámetro
        pil_positions = []
        for r in rooms_layout:
            for cx, cz in [(r['x'] + pil_r, r['z'] + pil_r),
                           (r['x'] + r['width'] - pil_r, r['z'] + pil_r),
                           (r['x'] + pil_r, r['z'] + r['depth'] - pil_r),
                           (r['x'] + r['width'] - pil_r, r['z'] + r['depth'] - pil_r)]:
                key = (round(cx, 1), round(cz, 1))
                if key not in pil_positions:
                    pil_positions.append(key)
                    ppx, ppy = to_px(cx, cz)
                    circ = mpatches.Circle((ppx, ppy), pil_r * SCALE,
                                           linewidth=2, edgecolor=LC, facecolor='#BCAAA4', zorder=5)
                    ax.add_patch(circ)
                    ax.text(ppx, ppy, 'Ø50', ha='center', va='center',
                            fontsize=4.5, color='white', fontweight='bold', zorder=6)
        # Encepado (losa de remate sobre los pilotes)
        enx, enz = house_min_x - ZAP_W, house_min_z - ZAP_W
        enw = (house_max_x - house_min_x) + 2 * ZAP_W
        end_ = (house_max_z - house_min_z) + 2 * ZAP_W
        prect(enx, enz, enw, end_, fc='#D7CCC815', ec=LC, lw=2.5, zo=4, alpha=0.25)
        # ── Cuadro de leyendas técnico (pilotes) ─────────────────────────────
        leg_px, leg_py = to_px(house_min_x, house_min_z - 1.2)
        # Fondo del cuadro
        box_w_px = min(enw * SCALE, svg_w - MARGIN - leg_px - 10)
        ax.add_patch(mpatches.FancyBboxPatch(
            (leg_px - 4, leg_py - 42), max(box_w_px, 280), 46,
            boxstyle='round,pad=2', linewidth=1.2,
            edgecolor=LC, facecolor='#EFEBE9', zorder=10
        ))
        ax.text(leg_px, leg_py - 4,
                'CIMENTACIÓN POR PILOTES', fontsize=7.5, color=LC,
                fontweight='bold', va='top', zorder=11)
        specs = [
            ('Tipo',       'Pilote barrenado in situ (CPI-8)'),
            ('Diámetro',   'Ø 50 cm'),
            ('Hormigón',   'HA-30/B/20/IIa — XC2'),
            ('Armadura',   '6Ø20 + cercos Ø8/15'),
            ('Encepado',   f'e = 50 cm  ·  HA-25  ·  {enw:.2f}×{end_:.2f} m'),
            ('Longitud',   'Según estudio geotécnico previo (EHE-08 Art.58)'),
        ]
        for k_idx, (label, value) in enumerate(specs):
            row_y = leg_py - 14 - k_idx * 8
            ax.text(leg_px + 2,  row_y, f'{label}:', fontsize=5.5, color='#5D4037',
                    fontweight='bold', va='top', zorder=11)
            ax.text(leg_px + 48, row_y, value,        fontsize=5.5, color='#3E2723',
                    va='top', zorder=11)
        # Símbolo pilote en leyenda
        sym_cx = leg_px + box_w_px - 18 if box_w_px > 60 else leg_px + 240
        sym_cy = leg_py - 22
        ax.add_patch(mpatches.Circle((sym_cx, sym_cy), 10,
                                      linewidth=1.5, edgecolor=LC, facecolor='#BCAAA4', zorder=12))
        ax.text(sym_cx, sym_cy, 'Ø50', ha='center', va='center',
                fontsize=5, color='white', fontweight='bold', zorder=13)
    elif foundation_type == "losa":
        # ── LOSA: rectángulo relleno con hatch ────────────────────────────────
        lx, lz = house_min_x - ZAP_W, house_min_z - ZAP_W
        lw_m   = (house_max_x - house_min_x) + 2 * ZAP_W
        ld_m   = (house_max_z - house_min_z) + 2 * ZAP_W
        px, py = to_px(lx, lz + ld_m)
        ax.add_patch(mpatches.Rectangle(
            (px, py), lw_m * SCALE, ld_m * SCALE,
            linewidth=2.5, edgecolor=LC, facecolor='#D7CCC8',
            hatch='///', zorder=4
        ))
        # Cota longitud
        cpx1, cpy = to_px(lx, lz - 0.5)
        cpx2, _   = to_px(lx + lw_m, lz - 0.5)
        ax.annotate('', xy=(cpx2, cpy), xytext=(cpx1, cpy),
                    arrowprops=dict(arrowstyle='<->', color=LC, lw=1.2), zorder=9)
        ax.text((cpx1+cpx2)/2, cpy - 10, f'{lw_m:.2f} m',
                ha='center', va='top', fontsize=6.5, color=LC, fontweight='bold')
        # Cota profundidad
        cpy1, cpx = to_px(lx - 0.5, lz), to_px(lx - 0.5, lz)[0]
        cpy2, _   = to_px(lx - 0.5, lz + ld_m)[1], None
        _, cpy1v  = to_px(lx - 0.5, lz)
        _, cpy2v  = to_px(lx - 0.5, lz + ld_m)
        ax.annotate('', xy=(cpx, cpy2v), xytext=(cpx, cpy1v),
                    arrowprops=dict(arrowstyle='<->', color=LC, lw=1.2), zorder=9)
        ax.text(cpx - 8, (cpy1v+cpy2v)/2, f'{ld_m:.2f} m',
                ha='right', va='center', fontsize=6.5, color=LC, fontweight='bold', rotation=90)
        # Leyenda
        leg_px, leg_py = to_px(house_min_x, house_min_z - 1.4)
        ax.text(leg_px, leg_py, 'LOSA DE CIMENTACIÓN  ·  e=25 cm  ·  HA-25/B/20/IIa',
                fontsize=6.5, color=LC, fontweight='bold', va='top')

    else:
        # ── ZAPATAS: corrida perimetral + puntuales interiores ────────────────
        # Zapata corrida perimetral — doble línea (vuelo ZAP_W a cada lado)
        for (x1, z1, x2, z2, label) in [
            (house_min_x - ZAP_W, house_min_z - ZAP_W,
             house_max_x + ZAP_W, house_min_z + ZAP_W, f'{(house_max_x - house_min_x + 2*ZAP_W):.2f} m'),
            (house_min_x - ZAP_W, house_max_z - ZAP_W,
             house_max_x + ZAP_W, house_max_z + ZAP_W, ''),
            (house_min_x - ZAP_W, house_min_z - ZAP_W,
             house_min_x + ZAP_W, house_max_z + ZAP_W, f'{(house_max_z - house_min_z + 2*ZAP_W):.2f} m'),
            (house_max_x - ZAP_W, house_min_z - ZAP_W,
             house_max_x + ZAP_W, house_max_z + ZAP_W, ''),
        ]:
            prect(x1, z1, x2 - x1, z2 - z1,
                  fc='#BCAAA4', ec=LC, lw=2.0, zo=5)
            if label:
                mpx, mpy = to_px((x1+x2)/2, (z1+z2)/2)
                ax.text(mpx, mpy, label, ha='center', va='center',
                        fontsize=5.5, color='white', fontweight='bold', zorder=6)

        # Zapatas aisladas interiores bajo muros de carga (medianeras entre habitaciones)
        # Detectar muros verticales (bordes Z de habitaciones adyacentes)
        interior_x_walls = set()
        for r in rooms_layout:
            interior_x_walls.add(round(r['x'], 2))
            interior_x_walls.add(round(r['x'] + r['width'], 2))
        # Filtrar solo las que están en el interior (no perimetrales)
        eps = 0.05
        interior_x_walls = {
            xw for xw in interior_x_walls
            if house_min_x + eps < xw < house_max_x - eps
        }
        for xw in sorted(interior_x_walls):
            # Zapata corrida interior: franja de 0.3m a cada lado del muro
            prect(xw - 0.15, house_min_z - ZAP_W * 0.5,
                  0.30, house_max_z - house_min_z + ZAP_W,
                  fc='#D7CCC8', ec=LC, lw=1.5, zo=4)

        # Leyenda dimensiones zapata corrida perimetral
        sec_w = 0.40 + 0.40          # total 0.80 m sección
        leg_px, leg_py = to_px(house_min_x, house_min_z - 1.5)
        ax.text(leg_px, leg_py,
                f'ZAPATA CORRIDA PERIMETRAL  ·  0.80×0.50 m  ·  HA-25/B/20/IIa  ·  ϕ12@20',
                fontsize=6.5, color=LC, fontweight='bold', va='top')
        leg_py2 = leg_py - 14
        ax.text(leg_px, leg_py2,
                'ZAPATAS INTERIORES  ·  0.30×0.45 m  ·  HA-25  ·  ϕ12@20',
                fontsize=6, color=LC, va='top')

    # ── Norte simbólico ───────────────────────────────────────────────────────
    npx, npy = svg_w - MARGIN + 10, svg_h - MARGIN - 10
    ax.annotate('N', xy=(npx, npy + 20), xytext=(npx, npy),
                fontsize=8, color=LC, ha='center', va='bottom', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=LC, lw=1.5))

    # ── Escala gráfica ────────────────────────────────────────────────────────
    sc_x0, sc_y = to_px(house_min_x, house_min_z - 2.0)
    sc_x1 = sc_x0 + 5 * SCALE   # 5 metros
    ax.plot([sc_x0, sc_x1], [sc_y, sc_y], color=LC, lw=2.5, zorder=9)
    for xsc in [sc_x0, sc_x1]:
        ax.plot([xsc, xsc], [sc_y - 4, sc_y + 4], color=LC, lw=2.0, zorder=9)
    ax.text((sc_x0+sc_x1)/2, sc_y - 9, '5 m', ha='center', va='top',
            fontsize=6, color=LC, fontweight='bold')
    ax.text(sc_x0, sc_y - 9, '0', ha='center', va='top', fontsize=5.5, color=LC)

    # ── Título ────────────────────────────────────────────────────────────────
    title_h = 44
    ax.add_patch(mpatches.Rectangle((0, svg_h - title_h), svg_w, title_h,
                                     facecolor='#3E2723', zorder=10))
    ax.text(svg_w/2, svg_h - title_h/2,
            f'PLANO DE CIMENTACIÓN PARA CONSTRUCCIÓN  ·  Escala 1:100',
            ha='center', va='center', fontsize=10, fontweight='bold',
            color='white', fontfamily='monospace', zorder=11)

    # ── Pie ───────────────────────────────────────────────────────────────────
    ax.text(MARGIN, 10, f'Tipo: {foundation_type.upper()}', color=LC,
            fontsize=6.5, fontweight='bold', va='bottom')
    ax.text(svg_w - MARGIN, 10, 'ArchiRapid AI  ·  © 2026',
            color='#AAAAAA', fontsize=6, ha='right', va='bottom')

    buf = _io.BytesIO()
    plt.tight_layout(pad=0)
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=BG, edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─── Sección arquitectónica desde layout 3D (S3) ─────────────────────────────

def generate_section_plan_png(
    rooms_layout,
    total_width=None,
    total_depth=None,
    cut_height: float = 1.20,
) -> bytes | None:
    """
    Genera plano de planta arquitectónico (sección horizontal a cut_height metros)
    a partir del layout de habitaciones exportado por el editor 3D Babylon.

    A diferencia de FloorPlanSVG (que usa el DesignData abstracto), esta función
    toma coordenadas reales X/Z/width/depth tal como las produce generateLayoutJS.

    Args:
        rooms_layout : lista de dicts {x, z, width, depth, name, code, zone, area_m2}
        total_width/depth : bounding box de la casa (se calcula si None)
        cut_height  : altura de sección (por defecto 1.20m — CTE DB-SU)

    Returns:
        PNG bytes o None si hay error.
    """
    import json
    import math
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.patheffects as pe
    import io as _io

    if isinstance(rooms_layout, str):
        try:
            rooms_layout = json.loads(rooms_layout)
        except Exception:
            return None
    if not rooms_layout:
        return None

    SCALE  = 60   # px / metro — más grande que MEP para leer bien medidas
    MARGIN = 90
    WALL_T = 0.15  # grosor muro (m)
    BG     = '#FFFFFF'
    WALL_C = '#2C2C2C'
    DIM_C  = '#1565C0'

    ZONE_FILL = {
        'day':        '#FFF9E6',
        'night':      '#EDE7F6',
        'wet':        '#E0F7FA',
        'service':    '#ECEFF1',
        'garden':     '#E8F5E9',
        'exterior':   '#E8F5E9',
        'circulation':'#F5F5F5',
    }

    if total_width is None:
        total_width  = max(r['x'] + r['width']  for r in rooms_layout)
    if total_depth is None:
        total_depth  = max(r['z'] + r['depth']  for r in rooms_layout)

    house_min_x = min(r['x']               for r in rooms_layout)
    house_min_z = min(r['z']               for r in rooms_layout)
    house_max_x = max(r['x'] + r['width']  for r in rooms_layout)
    house_max_z = max(r['z'] + r['depth']  for r in rooms_layout)

    # Canvas — margen extra para cotas
    svg_w = int(total_width  * SCALE + MARGIN * 3 + 80)
    svg_h = int(total_depth  * SCALE + MARGIN * 4 + 90)

    fig, ax = plt.subplots(figsize=(svg_w / 100, svg_h / 100), facecolor=BG)
    ax.set_xlim(0, svg_w)
    ax.set_ylim(0, svg_h)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG)

    def to_px(x_m, z_m):
        return MARGIN + x_m * SCALE, MARGIN + (total_depth - z_m) * SCALE

    def m2px(m):
        return m * SCALE

    # ── Habitaciones ──────────────────────────────────────────────────────────
    for r in rooms_layout:
        code = (r.get('code') or r.get('name') or '').lower()
        zone = (r.get('zone') or '').lower()

        if any(c in code for c in ['bano', 'aseo', 'cocina', 'wc']):
            fill = ZONE_FILL['wet']
        else:
            fill = ZONE_FILL.get(zone, '#F8F8F8')

        px, py = to_px(r['x'], r['z'] + r['depth'])
        pw, ph = m2px(r['width']), m2px(r['depth'])

        # Relleno zona
        ax.add_patch(mpatches.Rectangle((px, py), pw, ph,
                                         linewidth=0, facecolor=fill, zorder=2))

        # Muros (línea gruesa alrededor de cada habitación)
        wt = max(2.5, WALL_T * SCALE)  # grosor muro en px
        for (x0, y0, dx, dy) in [
            (px, py + ph - wt/2,   pw, wt),    # norte
            (px, py,               pw, wt),    # sur
            (px, py,               wt, ph),    # oeste
            (px + pw - wt, py,     wt, ph),    # este
        ]:
            ax.add_patch(mpatches.Rectangle((x0, y0), dx, dy,
                                             linewidth=0, facecolor=WALL_C, zorder=3))

        # Etiqueta: nombre + área
        cx, cy = px + pw / 2, py + ph / 2
        area   = r.get('area_m2') or round(r['width'] * r['depth'], 1)
        ax.text(cx, cy + 6, r.get('name', code.upper()),
                ha='center', va='center', fontsize=6.5,
                color='#333333', fontweight='bold', zorder=5)
        ax.text(cx, cy - 7, f"{area:.1f} m²",
                ha='center', va='center', fontsize=5.5, color='#666666', zorder=5)

        # Dimensiones interiores (ancho × fondo)
        ax.text(cx, py + 10, f"{r['width']:.1f}",
                ha='center', va='bottom', fontsize=5, color=DIM_C, zorder=5)
        ax.text(px + 8, cy, f"{r['depth']:.1f}",
                ha='left', va='center', fontsize=5, color=DIM_C,
                rotation=90, zorder=5)

    # ── Cota total Ancho ─────────────────────────────────────────────────────
    dim_z_top = house_min_z - 0.8
    px_l, py_dim = to_px(house_min_x, dim_z_top)
    px_r, _      = to_px(house_max_x, dim_z_top)
    ax.annotate('', xy=(px_r, py_dim), xytext=(px_l, py_dim),
                arrowprops=dict(arrowstyle='<->', color=DIM_C, lw=1.2), zorder=9)
    ax.text((px_l + px_r) / 2, py_dim - 10,
            f'{(house_max_x - house_min_x):.2f} m',
            ha='center', va='top', fontsize=7, color=DIM_C, fontweight='bold')

    # ── Cota total Fondo ─────────────────────────────────────────────────────
    dim_x_right = house_max_x + 0.8
    px_dim, py_b = to_px(dim_x_right, house_min_z)
    _,      py_t = to_px(dim_x_right, house_max_z)
    ax.annotate('', xy=(px_dim, py_t), xytext=(px_dim, py_b),
                arrowprops=dict(arrowstyle='<->', color=DIM_C, lw=1.2), zorder=9)
    ax.text(px_dim + 10, (py_b + py_t) / 2,
            f'{(house_max_z - house_min_z):.2f} m',
            ha='left', va='center', fontsize=7, color=DIM_C,
            fontweight='bold', rotation=90)

    # ── Contorno exterior grueso ──────────────────────────────────────────────
    out_px, out_py = to_px(house_min_x, house_max_z)
    out_w  = (house_max_x - house_min_x) * SCALE
    out_h  = (house_max_z - house_min_z) * SCALE
    ax.add_patch(mpatches.Rectangle((out_px, out_py), out_w, out_h,
                                     linewidth=3.0, edgecolor=WALL_C,
                                     facecolor='none', zorder=7))

    # ── Escala gráfica ────────────────────────────────────────────────────────
    sc_x0, sc_y = to_px(house_min_x, house_min_z - 1.6)
    sc_x1 = sc_x0 + 5 * SCALE
    ax.plot([sc_x0, sc_x1], [sc_y, sc_y], color='#333', lw=2.5, zorder=9)
    for xsc in [sc_x0, sc_x1]:
        ax.plot([xsc, xsc], [sc_y - 5, sc_y + 5], color='#333', lw=2.0, zorder=9)
    ax.text((sc_x0 + sc_x1) / 2, sc_y - 10, '5 m',
            ha='center', va='top', fontsize=7, color='#333', fontweight='bold')
    ax.text(sc_x0, sc_y - 10, '0', ha='center', va='top', fontsize=6, color='#333')

    # ── Norte ────────────────────────────────────────────────────────────────
    npx, npy = svg_w - MARGIN + 10, svg_h - MARGIN - 15
    ax.annotate('N', xy=(npx, npy + 22), xytext=(npx, npy),
                fontsize=9, color='#1A237E', ha='center', va='bottom',
                fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#1A237E', lw=2.0))

    # ── Leyenda zona ─────────────────────────────────────────────────────────
    leg_items = [
        ('#FFF9E6', 'Zona día'),
        ('#EDE7F6', 'Zona noche'),
        ('#E0F7FA', 'Zona húmeda'),
        ('#E8F5E9', 'Exterior'),
    ]
    leg_x0, leg_y0 = MARGIN, 14
    for idx_l, (fc, lbl) in enumerate(leg_items):
        rx = leg_x0 + idx_l * (svg_w // len(leg_items))
        ax.add_patch(mpatches.Rectangle((rx, leg_y0), 18, 10,
                                         linewidth=0.8, edgecolor='#999',
                                         facecolor=fc, zorder=8))
        ax.text(rx + 22, leg_y0 + 5, lbl, va='center', fontsize=6, color='#555')

    # ── Título y nota de sección ──────────────────────────────────────────────
    title_h = 48
    ax.add_patch(mpatches.Rectangle((0, svg_h - title_h), svg_w, title_h,
                                     facecolor='#1A237E', zorder=10))
    ax.text(svg_w / 2, svg_h - title_h / 2,
            f'PLANTA ARQUITECTÓNICA — Sección a {cut_height:.2f}m  ·  Escala 1:100',
            ha='center', va='center', fontsize=10, fontweight='bold',
            color='white', fontfamily='monospace', zorder=11)

    ax.text(MARGIN, svg_h - title_h + 6,
            f'ArchiRapid AI  ·  Sección real desde editor 3D  ·  Sup. construida: '
            f'{sum((r.get("area_m2") or r["width"] * r["depth"]) for r in rooms_layout):.1f} m²',
            fontsize=6, color='#90CAF9', va='bottom', zorder=11)

    buf = _io.BytesIO()
    plt.tight_layout(pad=0)
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=BG, edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─── Alias público para sincronización Babylon → 2D ──────────────────────────

def generate_from_babylon_layout(babylon_layout, cut_height: float = 1.20) -> bytes | None:
    """
    Genera plano 2D arquitectónico directamente desde el JSON exportado por el
    editor Babylon (babylon_modified_layout).  Delega en generate_section_plan_png.

    Args:
        babylon_layout: lista de dicts o string JSON con {x, z, width, depth, name, code, zone}
        cut_height: altura de sección (default 1.20m — CTE DB-SU)
    Returns:
        PNG bytes o None si hay error.
    """
    import json as _json
    if isinstance(babylon_layout, str):
        try:
            babylon_layout = _json.loads(babylon_layout)
        except Exception:
            return None
    if not babylon_layout:
        return None
    return generate_section_plan_png(babylon_layout, cut_height=cut_height)