"""
Visor 3D isométrico de viviendas
"""
import plotly.graph_objects as go
import numpy as np
from typing import List, Dict, Tuple

class Isometric3DViewer:
    """Generador de vistas 3D isométricas"""
    
    def __init__(self, design):
        self.design = design
        self.wall_height = 2.7  # metros
        
        # Colores con transparencia
        self.room_colors = {
            'salon': 'rgba(227, 242, 253, 0.8)',
            'cocina': 'rgba(255, 243, 224, 0.8)',
            'dormitorio': 'rgba(243, 229, 245, 0.8)',
            'bano': 'rgba(224, 242, 241, 0.8)',
            'bodega': 'rgba(255, 249, 196, 0.8)',
            'piscina': 'rgba(179, 229, 252, 0.8)',
            'garaje': 'rgba(236, 239, 241, 0.8)',
            'porche': 'rgba(232, 245, 233, 0.8)',
            'paneles': 'rgba(255, 224, 178, 0.8)',
            'pasillo': 'rgba(245, 245, 245, 0.8)'
        }
    
    def _get_room_color(self, room_code: str) -> str:
        """Obtiene color según tipo"""
        code_lower = room_code.lower()
        for key, color in self.room_colors.items():
            if key in code_lower:
                return color
        return 'rgba(255, 255, 255, 0.8)'
    
    def _calculate_dimensions(self, area_m2: float) -> Tuple[float, float]:
        """Calcula ancho y alto dado área"""
        width = np.sqrt(area_m2 * 1.4)
        height = area_m2 / width
        return round(width, 1), round(height, 1)
    
    def _layout_rooms(self) -> List[Dict]:
        """Distribuye habitaciones en grid"""
        rooms_data = []
        
        # Separar por tamaño
        large_rooms = [r for r in self.design.rooms if r.area_m2 >= 20]
        medium_rooms = [r for r in self.design.rooms if 10 <= r.area_m2 < 20]
        small_rooms = [r for r in self.design.rooms if r.area_m2 < 10]
        
        all_rooms = large_rooms + medium_rooms + small_rooms
        
        x, y = 0, 0
        current_row_height = 0
        row_width = 0
        
        for i, room in enumerate(all_rooms):
            width, depth = self._calculate_dimensions(room.area_m2)
            
            # Nueva fila si es muy ancho
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
                'depth': depth
            })
            
            x += width + 1
            row_width += width + 1
            current_row_height = max(current_row_height, depth)
        
        return rooms_data
    
    def _create_room_box(self, x, y, z, width, depth, height, color, name):
        """Crea una caja 3D para una habitación"""
        
        # Vértices de la caja
        vertices = [
            [x, y, z],                          # 0: esquina inferior trasera izquierda
            [x + width, y, z],                  # 1: esquina inferior trasera derecha
            [x + width, y + depth, z],          # 2: esquina inferior frontal derecha
            [x, y + depth, z],                  # 3: esquina inferior frontal izquierda
            [x, y, z + height],                 # 4: esquina superior trasera izquierda
            [x + width, y, z + height],         # 5: esquina superior trasera derecha
            [x + width, y + depth, z + height], # 6: esquina superior frontal derecha
            [x, y + depth, z + height]          # 7: esquina superior frontal izquierda
        ]
        
        # Caras (índices de vértices)
        faces = [
            [0, 1, 5, 4],  # Trasera
            [1, 2, 6, 5],  # Derecha
            [2, 3, 7, 6],  # Frontal
            [3, 0, 4, 7],  # Izquierda
            [4, 5, 6, 7],  # Superior
        ]
        
        # Crear mesh
        mesh = go.Mesh3d(
            x=[v[0] for v in vertices],
            y=[v[1] for v in vertices],
            z=[v[2] for v in vertices],
            i=[f[0] for f in faces],
            j=[f[1] for f in faces],
            k=[f[2] for f in faces],
            color=color,
            opacity=0.8,
            name=name,
            hovertemplate=f"<b>{name}</b><br>Área: {width * depth:.0f} m²<extra></extra>"
        )
        
        return mesh
    
    def generate(self) -> go.Figure:
        """Genera vista 3D completa"""
        
        rooms_layout = self._layout_rooms()
        
        fig = go.Figure()
        
        # Añadir cada habitación
        for item in rooms_layout:
            room = item['room']
            x, y = item['x'], item['y']
            width, depth = item['width'], item['depth']
            
            color = self._get_room_color(room.room_type.code)
            name = room.room_type.name
            
            mesh = self._create_room_box(
                x, y, 0,
                width, depth, self.wall_height,
                color, name
            )
            
            fig.add_trace(mesh)
            
            # Etiqueta con nombre
            fig.add_trace(go.Scatter3d(
                x=[x + width/2],
                y=[y + depth/2],
                z=[self.wall_height/2],
                mode='text',
                text=[f"<b>{name}</b><br>{room.area_m2:.0f}m²"],
                textfont=dict(size=10, color='black'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Layout
        fig.update_layout(
            scene=dict(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                zaxis=dict(visible=False),
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.2),
                    center=dict(x=0, y=0, z=0)
                ),
                aspectmode='data'
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(
                text=f"<b>VISTA 3D ISOMÉTRICA - {sum([r.area_m2 for r in self.design.rooms]):.0f} m² TOTALES</b>",
                x=0.5,
                xanchor='center'
            ),
            showlegend=False,
            hovermode='closest'
        )
        
        return fig
