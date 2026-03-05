"""
Generador de planos arquitectónicos profesionales en SVG
Distribución real con paredes conectadas, pasillos y medidas
"""
import math
from typing import List, Dict, Tuple, Optional
import io
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
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch
        import matplotlib.patheffects as pe
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

            # Dimensiones calculadas desde área original del slider
            _geo_ratio = item["width"] / item["height"] if item["height"] > 0 else 1.4
            _area_src = item.get("area_original", room.area_m2)
            _safe_area = max(_area_src, 1.0)
            _disp_w = round(math.sqrt(_safe_area * _geo_ratio), 1)
            _disp_h = round(_safe_area / _disp_w, 1) if _disp_w > 0 else 1.0
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