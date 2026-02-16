"""
Generador de planos 2D profesionales con IA
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
from typing import List, Dict, Tuple
import io

class ProfessionalFloorPlan:
    """Generador de planos arquitectónicos profesionales"""
    
    def __init__(self, design):
        self.design = design
        self.room_colors = {
            'salon': '#E3F2FD',      # Azul claro
            'cocina': '#FFF3E0',     # Naranja claro
            'dormitorio': '#F3E5F5', # Morado claro
            'bano': '#E0F2F1',       # Verde agua
            'bodega': '#FFF9C4',     # Amarillo claro
            'piscina': '#B3E5FC',    # Azul agua
            'garaje': '#ECEFF1',     # Gris claro
            'porche': '#E8F5E9',     # Verde claro
            'paneles': '#FFE0B2',    # Naranja claro
            'pasillo': '#F5F5F5'     # Gris muy claro
        }
    
    def _get_room_color(self, room_code: str) -> str:
        """Obtiene color según tipo de habitación"""
        code_lower = room_code.lower()
        for key, color in self.room_colors.items():
            if key in code_lower:
                return color
        return '#FFFFFF'
    
    def _calculate_dimensions(self, area_m2: float) -> Tuple[float, float]:
        """Calcula dimensiones aproximadas (ancho, alto) dado área"""
        # Ratio típico 1.4:1 (más ancho que alto)
        width = np.sqrt(area_m2 * 1.4)
        height = area_m2 / width
        return round(width, 1), round(height, 1)
    
    def _layout_rooms(self) -> List[Dict]:
        """Distribuye habitaciones en grid inteligente"""
        rooms_data = []
        
        # Separar por tamaño
        large_rooms = [r for r in self.design.rooms if r.area_m2 >= 20]
        medium_rooms = [r for r in self.design.rooms if 10 <= r.area_m2 < 20]
        small_rooms = [r for r in self.design.rooms if r.area_m2 < 10]
        
        # Ordenar cada grupo
        large_rooms.sort(key=lambda r: r.area_m2, reverse=True)
        medium_rooms.sort(key=lambda r: r.area_m2, reverse=True)
        small_rooms.sort(key=lambda r: r.area_m2, reverse=True)
        
        # Layout: grandes abajo, medianas en medio, pequeñas arriba
        all_rooms = large_rooms + medium_rooms + small_rooms
        
        x, y = 0, 0
        max_width = 0
        current_row_height = 0
        row_width = 0
        
        for i, room in enumerate(all_rooms):
            width, height = self._calculate_dimensions(room.area_m2)
            
            # Si la fila actual es muy ancha, bajar
            if row_width + width > 16 and i > 0:
                y += current_row_height + 1.5
                x = 0
                row_width = 0
                current_row_height = 0
            
            rooms_data.append({
                'room': room,
                'x': x,
                'y': y,
                'width': width,
                'height': height
            })
            
            x += width + 1
            row_width += width + 1
            current_row_height = max(current_row_height, height)
            max_width = max(max_width, row_width)
        
        return rooms_data
    
    def generate(self) -> bytes:
        """Genera plano y retorna como bytes PNG"""
        
        rooms_layout = self._layout_rooms()
        
        # Calcular límites del plano
        max_x = max([r['x'] + r['width'] for r in rooms_layout]) + 3
        max_y = max([r['y'] + r['height'] for r in rooms_layout]) + 3
        
        # Crear figura MÁS GRANDE
        fig, ax = plt.subplots(figsize=(18, 14), facecolor='white', dpi=150)
        ax.set_xlim(0, max_x)
        ax.set_ylim(0, max_y)
        ax.set_aspect('equal')
        
        # Título
        total_area = sum([r.area_m2 for r in self.design.rooms])
        ax.text(
            max_x / 2, max_y - 0.5,
            f'PLANO DE DISTRIBUCIÓN - {total_area:.0f} m² TOTALES',
            ha='center', va='top',
            fontsize=16, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#f0f0f0', edgecolor='#333', linewidth=2)
        )
        
        # Dibujar cada habitación
        for item in rooms_layout:
            room = item['room']
            x, y = item['x'], item['y']
            width, height = item['width'], item['height']
            
            # Color
            color = self._get_room_color(room.room_type.code)
            
            # Rectángulo con borde
            rect = Rectangle(
                (x, y), width, height,
                facecolor=color,
                edgecolor='#333',
                linewidth=2
            )
            ax.add_patch(rect)
            
            # Nombre de habitación
            name = room.room_type.name
            ax.text(
                x + width/2, y + height/2 + 0.3,
                name,
                ha='center', va='center',
                fontsize=10, fontweight='bold'
            )
            
            # Dimensiones
            ax.text(
                x + width/2, y + height/2 - 0.2,
                f'{width:.1f}m × {height:.1f}m',
                ha='center', va='center',
                fontsize=8, color='#666'
            )
            
            # Área
            ax.text(
                x + width/2, y + height/2 - 0.6,
                f'{room.area_m2:.0f} m²',
                ha='center', va='center',
                fontsize=9, fontweight='bold',
                color='#1976D2'
            )
        
        # Quitar ejes
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        # Grid sutil
        ax.grid(True, linestyle=':', alpha=0.3, color='#ccc')
        
        plt.tight_layout()
        
        # Guardar en bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        
        return buf.getvalue()
