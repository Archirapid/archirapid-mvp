"""
Generador de planos arquitectónicos profesionales en SVG
Distribución real con paredes conectadas, pasillos y medidas
"""
import math
from typing import List, Dict, Tuple, Optional
import io

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
        """
        Distribuye habitaciones en layout tipo plano real.
        Zona día (salón/cocina) a la izquierda.
        Zona noche (dormitorios) a la derecha.
        Servicios (baños, pasillos) en el centro.
        Extras (garaje, porche) en los extremos.
        """
        layout = []
        
        # Separar por zonas
        zona_dia = []      # salón, cocina
        zona_noche = []    # dormitorios
        zona_servicio = [] # baños, pasillo, bodega
        zona_extra = []    # garaje, porche, piscina, paneles, huerto
        
        for room in self.design.rooms:
            code = room.room_type.code.lower()
            if any(x in code for x in ['salon', 'cocina']):
                zona_dia.append(room)
            elif any(x in code for x in ['dormitorio']):
                zona_noche.append(room)
            elif any(x in code for x in ['bano', 'pasillo', 'bodega', 'instalac']):
                zona_servicio.append(room)
            else:
                zona_extra.append(room)
        
        # Ordenar dormitorios (principal primero)
        zona_noche.sort(key=lambda r: r.area_m2, reverse=True)
        
        # LAYOUT GRID:
        # [EXTRA_IZQ] [DIA] [SERVICIO] [NOCHE] [EXTRA_DER]
        
        current_x = 0
        current_y = 0
        max_height = 0
        
        # Columna 1: Extras izquierda (piscina SIEMPRE va fuera)
        zona_piscina = [r for r in zona_extra if 'piscina' in r.room_type.code.lower()]
        extras_izq = [r for r in zona_extra if any(x in r.room_type.code.lower() 
                      for x in ['garaje', 'porche']) and 'piscina' not in r.room_type.code.lower()]
        
        col1_width = 0
        col1_y = 0
        for room in extras_izq:
            w, h = self._calculate_room_dimensions(room.area_m2, 1.2)
            layout.append({
                'room': room,
                'x': current_x,
                'y': col1_y,
                'width': w,
                'height': h
            })
            col1_width = max(col1_width, w)
            col1_y += h
            max_height = max(max_height, col1_y)
        
        current_x += col1_width if col1_width > 0 else 0
        
        # Columna 2: Zona día (salón-cocina)
        col2_width = 0
        col2_y = 0
        for room in zona_dia:
            w, h = self._calculate_room_dimensions(room.area_m2, 1.3)
            layout.append({
                'room': room,
                'x': current_x,
                'y': col2_y,
                'width': w,
                'height': h
            })
            col2_width = max(col2_width, w)
            col2_y += h
            max_height = max(max_height, col2_y)
        
        current_x += col2_width if col2_width > 0 else 0
        
        # Columna 3: Servicios (baños, pasillo)
        col3_width = 0
        col3_y = 0
        for room in zona_servicio:
            w, h = self._calculate_room_dimensions(room.area_m2, 0.8)
            layout.append({
                'room': room,
                'x': current_x,
                'y': col3_y,
                'width': w,
                'height': h
            })
            col3_width = max(col3_width, w)
            col3_y += h
            max_height = max(max_height, col3_y)
        
        current_x += col3_width if col3_width > 0 else 0
        
        # Columna 4: Dormitorios
        col4_width = 0
        col4_y = 0
        for room in zona_noche:
            w, h = self._calculate_room_dimensions(room.area_m2, 1.3)
            layout.append({
                'room': room,
                'x': current_x,
                'y': col4_y,
                'width': w,
                'height': h
            })
            col4_width = max(col4_width, w)
            col4_y += h
            max_height = max(max_height, col4_y)
        
        current_x += col4_width if col4_width > 0 else 0
        
        # Columna 5: Extras derecha (paneles, huerto, etc)
        extras_der = [r for r in zona_extra if r not in extras_izq and r not in zona_piscina]
        col5_y = 0
        for room in extras_der:
            w, h = self._calculate_room_dimensions(room.area_m2, 1.2)
            layout.append({
                'room': room,
                'x': current_x,
                'y': col5_y,
                'width': w,
                'height': h
            })
            col5_y += h
            max_height = max(max_height, col5_y)
        
        # Piscina exterior: siempre abajo separada de la casa
        pool_x = 0
        pool_y_offset = max_height + 3  # 3 metros de separación
        for room in zona_piscina:
            w, h = self._calculate_room_dimensions(room.area_m2, 1.8)  # más ancha que alta
            layout.append({
                'room': room,
                'x': pool_x,
                'y': pool_y_offset,
                'width': w,
                'height': h
            })
            pool_x += w + 1
            max_height = max(max_height, pool_y_offset + h)
        
        self.total_width = current_x + (extras_der[0].area_m2 ** 0.5 if extras_der else 0)
        self.total_height = max_height
        
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

        # Colores profesionales tipo arquitectónico
        colors_map = {
            'salon':    '#F5F0E8',
            'cocina':   '#F5F0E8',
            'dormitorio': '#EAE8F0',
            'bano':     '#E0EEF0',
            'garaje':   '#DCDCDC',
            'porche':   '#E8F0E8',
            'bodega':   '#F0EDE0',
            'pasillo':  '#EBEBEB',
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

            # Color de fondo
            fill = '#F5F5F5'
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

            # Dimensiones
            ax.text(px + pw / 2, py + ph * 0.38,
                    f'{item["width"]:.1f}m × {item["height"]:.1f}m',
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

            # Símbolo de puerta (arco pequeño en esquina inferior izquierda)
            if any(x in code for x in ['dormitorio', 'bano', 'despacho', 'bodega']):
                door_r = min(pw, ph) * 0.18
                door_r = min(door_r, 18)
                theta = np.linspace(0, np.pi / 2, 20)
                door_x = px + door_r * np.cos(theta)
                door_y = py + door_r * np.sin(theta)
                ax.plot(door_x, door_y, color=wall_color, lw=1.2,
                        linestyle='--', zorder=6)
                ax.plot([px, px], [py, py + door_r],
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
