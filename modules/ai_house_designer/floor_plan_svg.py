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
        """Genera el plano SVG completo como bytes PNG"""
        import subprocess
        import tempfile
        import os
        
        layout = self._layout_rooms()
        
        # Dimensiones del SVG
        svg_width = int(self.total_width * self.SCALE + self.MARGIN * 3)
        svg_height = int(self.total_height * self.SCALE + self.MARGIN * 4)
        
        total_area = sum(r.area_m2 for r in self.design.rooms)
        
        # Cabecera SVG
        svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{svg_width}" height="{svg_height}"
     viewBox="0 0 {svg_width} {svg_height}">
    
    <!-- Fondo blanco -->
    <rect width="{svg_width}" height="{svg_height}" fill="white"/>
    
    <!-- Definiciones (flechas para cotas) -->
    <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" 
                refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#888"/>
        </marker>
    </defs>
    
    <!-- Título -->
    <rect x="10" y="10" width="{svg_width-20}" height="40" 
          fill="#2C3E50" rx="5"/>
    <text x="{svg_width/2}" y="35" text-anchor="middle"
          font-family="Arial, sans-serif" font-size="16" 
          font-weight="bold" fill="white">
        PLANO DE DISTRIBUCIÓN — {total_area:.0f} m² TOTALES
    </text>
    
    <!-- Subtítulo -->
    <text x="{svg_width/2}" y="65" text-anchor="middle"
          font-family="Arial, sans-serif" font-size="10" fill="#666">
        Escala aproximada 1:100 · Medidas en metros
    </text>
    
    <!-- Grid de referencia -->
    <g opacity="0.15">
"""
        
        # Grid sutil
        grid_step = self.SCALE  # 1 metro por línea
        for gx in range(self.MARGIN, svg_width, grid_step):
            svg_content += f'<line x1="{gx}" y1="{self.MARGIN}" x2="{gx}" y2="{svg_height - self.MARGIN}" stroke="#999" stroke-width="0.5" stroke-dasharray="2,4"/>\n'
        for gy in range(self.MARGIN, svg_height, grid_step):
            svg_content += f'<line x1="{self.MARGIN}" y1="{gy}" x2="{svg_width - self.MARGIN}" y2="{gy}" stroke="#999" stroke-width="0.5" stroke-dasharray="2,4"/>\n'
        
        svg_content += "</g>\n"
        
        # Añadir habitaciones
        for item in layout:
            svg_content += self._room_to_svg(item, svg_width, svg_height)
        
        # Norte
        svg_content += f"""
    <!-- Indicador Norte -->
    <g transform="translate({svg_width - 50}, {svg_height - 60})">
        <circle cx="20" cy="20" r="18" fill="none" stroke="#2C3E50" stroke-width="2"/>
        <text x="20" y="14" text-anchor="middle" font-family="Arial" 
              font-size="12" font-weight="bold" fill="#2C3E50">N</text>
        <polygon points="20,3 16,20 20,17 24,20" fill="#2C3E50"/>
    </g>
    
    <!-- Leyenda -->
    <g transform="translate(10, {svg_height - 50})">
        <text font-family="Arial" font-size="9" fill="#666">
            Plano generado por ArchiRapid AI · Proyecto en desarrollo
        </text>
    </g>

</svg>"""
        
        # Convertir SVG a PNG usando matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
        
        # Generar PNG directamente con matplotlib (más fiable)
        fig_w = svg_width / 100
        fig_h = svg_height / 100
        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='white')
        ax.set_xlim(0, svg_width)
        ax.set_ylim(0, svg_height)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Título
        ax.add_patch(mpatches.FancyBboxPatch(
            (10, svg_height-55), svg_width-20, 45,
            boxstyle="round,pad=2",
            facecolor='#2C3E50', edgecolor='none'
        ))
        ax.text(svg_width/2, svg_height-30, 
                f'PLANO DE DISTRIBUCIÓN — {total_area:.0f} m² TOTALES',
                ha='center', va='center',
                fontsize=14, fontweight='bold', color='white',
                fontfamily='monospace')
        
        # Grid sutil
        for gx in range(self.MARGIN, int(svg_width), self.SCALE):
            ax.axvline(x=gx, color='#CCCCCC', linewidth=0.3, linestyle='--', alpha=0.5)
        for gy in range(self.MARGIN, int(svg_height), self.SCALE):
            ax.axhline(y=gy, color='#CCCCCC', linewidth=0.3, linestyle='--', alpha=0.5)
        
        # Dibujar habitaciones
        colors_map = {
            'salon': '#F5F0E8', 'cocina': '#F5F0E8',
            'dormitorio': '#EEF0F5', 'bano': '#E8F5F0',
            'garaje': '#F0F0F0', 'porche': '#E8F5E8',
            'bodega': '#F5F5E8', 'pasillo': '#EBEBEB',
            'paneles': '#FFF8E8', 'piscina': '#E8F4FF',
            'default': '#F5F5F5'
        }
        
        for item in layout:
            room = item['room']
            
            px = item['x'] * self.SCALE + self.MARGIN
            py = (self.total_height - item['y'] - item['height']) * self.SCALE + self.MARGIN
            pw = item['width'] * self.SCALE
            ph = item['height'] * self.SCALE
            
            # Color
            color = '#F5F5F5'
            code_lower = room.room_type.code.lower()
            for key, c in colors_map.items():
                if key in code_lower:
                    color = c
                    break
            
            # Rectángulo con borde grueso (pared)
            rect = mpatches.Rectangle(
                (px, py), pw, ph,
                linewidth=3,
                edgecolor='#2C3E50',
                facecolor=color
            )
            ax.add_patch(rect)
            
            # Nombre
            ax.text(px + pw/2, py + ph/2 + ph*0.1,
                   room.room_type.name,
                   ha='center', va='center',
                   fontsize=max(7, min(11, pw/15)),
                   fontweight='bold', color='#2C3E50')
            
            # Dimensiones
            ax.text(px + pw/2, py + ph/2 - ph*0.05,
                   f'{item["width"]:.1f}m × {item["height"]:.1f}m',
                   ha='center', va='center',
                   fontsize=max(6, min(9, pw/18)),
                   color='#555555')
            
            # Área en azul
            ax.text(px + pw/2, py + ph/2 - ph*0.22,
                   f'{room.area_m2:.0f} m²',
                   ha='center', va='center',
                   fontsize=max(7, min(10, pw/16)),
                   fontweight='bold', color='#1565C0')
            
            # Cota superior
            ax.annotate('', 
                       xy=(px + pw, py - 12),
                       xytext=(px, py - 12),
                       arrowprops=dict(arrowstyle='<->', color='#888888', lw=1))
            ax.text(px + pw/2, py - 18,
                   f'{item["width"]:.1f} m',
                   ha='center', va='center',
                   fontsize=7, color='#666666')
            
            # Cota lateral
            ax.annotate('',
                       xy=(px - 12, py + ph),
                       xytext=(px - 12, py),
                       arrowprops=dict(arrowstyle='<->', color='#888888', lw=1))
            ax.text(px - 22, py + ph/2,
                   f'{item["height"]:.1f} m',
                   ha='center', va='center',
                   fontsize=7, color='#666666',
                   rotation=90)
        
        # Norte
        ax.text(svg_width - 35, 35, 'N',
               ha='center', va='center',
               fontsize=14, fontweight='bold', color='#2C3E50')
        circle = plt.Circle((svg_width - 35, 35), 18,
                           fill=False, edgecolor='#2C3E50', linewidth=2)
        ax.add_patch(circle)
        ax.annotate('', 
                   xy=(svg_width - 35, 20),
                   xytext=(svg_width - 35, 35),
                   arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=2))
        
        # Pie de página
        ax.text(svg_width/2, 15,
               'ArchiRapid AI · Plano de distribución · Escala aprox. 1:100',
               ha='center', va='center',
               fontsize=8, color='#999999', style='italic')
        
        plt.tight_layout(pad=0)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close()
        buf.seek(0)
        return buf.getvalue()
