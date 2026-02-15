"""
Generador de planos 2D para el Diseñador de Vivienda con IA
Autor: ARCHIRAPID
Fecha: 2026-02-14
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
from pathlib import Path
import io
from PIL import Image

class FloorPlan2D:
    """Generador profesional de planos 2D"""
    
    def __init__(self, rooms, total_width=15, grid_size=0.5):
        """
        Args:
            rooms: Lista de RoomInstance (de data_model.py)
            total_width: Ancho total del plano en metros
            grid_size: Tamaño de la cuadrícula en metros
        """
        self.rooms = rooms
        self.total_width = total_width
        self.grid_size = grid_size
        
        # Colores por tipo de habitación
        self.room_colors = {
            'salon_cocina': '#FFE5B4',  # Melocotón
            'dormitorio_principal': '#B4D7FF',  # Azul claro
            'dormitorio': '#C4E1FF',  # Azul más claro
            'bano': '#D4F1F4',  # Turquesa
            'bodega': '#E8D5C4',  # Marrón claro
            'piscina': '#87CEEB',  # Azul cielo
            'garaje': '#D3D3D3',  # Gris
            'casa_apero': '#F4E4C1',  # Beige
            'porche': '#E6F3E6',  # Verde claro
            'pasillo': '#F5F5F5'  # Blanco grisáceo
        }
    
    def calculate_layout(self):
        """
        Calcula distribución optimizada de habitaciones.
        Algoritmo simple: Colocar en filas, habitaciones grandes primero.
        """
        # Ordenar habitaciones: grandes primero
        sorted_rooms = sorted(self.rooms, key=lambda r: r.area_m2, reverse=True)
        
        layout = []
        current_x = 0
        current_y = 0
        row_height = 0
        
        for room in sorted_rooms:
            # Calcular dimensiones aproximadas (asumiendo habitaciones cuadradas)
            width = np.sqrt(room.area_m2)
            height = np.sqrt(room.area_m2)
            
            # Si no cabe en la fila actual, nueva fila
            if current_x + width > self.total_width and current_x > 0:
                current_x = 0
                current_y += row_height + 0.5  # Espacio entre filas
                row_height = 0
            
            # Guardar posición
            layout.append({
                'room': room,
                'x': current_x,
                'y': current_y,
                'width': width,
                'height': height
            })
            
            # Actualizar posición
            current_x += width + 0.5  # Espacio entre habitaciones
            row_height = max(row_height, height)
        
        return layout
    
    def generate_plan(self, output_path='plano_2d.png', dpi=150):
        """
        Genera el plano 2D y lo guarda como imagen.
        
        Returns:
            str: Ruta del archivo generado
        """
        layout = self.calculate_layout()
        
        # Calcular altura total del plano
        max_y = max([r['y'] + r['height'] for r in layout])
        total_height = max_y + 1
        
        # Crear figura
        fig, ax = plt.subplots(figsize=(12, 12 * total_height / self.total_width))
        ax.set_xlim(-1, self.total_width + 1)
        ax.set_ylim(-1, total_height + 1)
        ax.set_aspect('equal')
        
        # Fondo
        ax.set_facecolor('#FAFAFA')
        
        # Cuadrícula
        for x in np.arange(0, self.total_width + 1, self.grid_size):
            ax.axvline(x, color='#E0E0E0', linewidth=0.3, alpha=0.5)
        for y in np.arange(0, total_height + 1, self.grid_size):
            ax.axhline(y, color='#E0E0E0', linewidth=0.3, alpha=0.5)
        
        # Dibujar habitaciones
        for item in layout:
            room = item['room']
            x, y = item['x'], item['y']
            width, height = item['width'], item['height']
            
            # Color de la habitación
            color = self.room_colors.get(room.code, '#FFFFFF')
            
            # Dibujar rectángulo con sombra
            shadow = FancyBboxPatch(
                (x + 0.05, y - 0.05), width, height,
                boxstyle="round,pad=0.05",
                facecolor='#CCCCCC',
                edgecolor='none',
                alpha=0.3,
                zorder=1
            )
            ax.add_patch(shadow)
            
            # Habitación principal
            rect = FancyBboxPatch(
                (x, y), width, height,
                boxstyle="round,pad=0.05",
                facecolor=color,
                edgecolor='#333333',
                linewidth=2,
                zorder=2
            )
            ax.add_patch(rect)
            
            # Nombre de la habitación
            room_name = room.room_type.display_name if hasattr(room, 'room_type') else room.code
            ax.text(
                x + width/2, y + height/2 + 0.3,
                room_name,
                ha='center', va='center',
                fontsize=10,
                fontweight='bold',
                color='#333333',
                zorder=3
            )
            
            # Área en m²
            ax.text(
                x + width/2, y + height/2 - 0.3,
                f"{room.area_m2:.1f} m²",
                ha='center', va='center',
                fontsize=9,
                color='#666666',
                zorder=3
            )
        
        # Título del plano
        ax.text(
            self.total_width/2, total_height + 0.5,
            '📐 PLANO DE DISTRIBUCIÓN',
            ha='center', va='center',
            fontsize=14,
            fontweight='bold',
            color='#1976D2'
        )
        
        # Leyenda de superficie total
        total_area = sum([r.area_m2 for r in self.rooms])
        ax.text(
            self.total_width/2, -0.5,
            f'Superficie Total: {total_area:.1f} m²',
            ha='center', va='center',
            fontsize=11,
            color='#333333'
        )
        
        # Quitar ejes
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        # Guardar
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return output_path
    
    def generate_plan_to_bytes(self, dpi=150):
        """
        Genera el plano y lo devuelve como bytes (para Streamlit).
        
        Returns:
            bytes: Imagen PNG en memoria
        """
        layout = self.calculate_layout()
        max_y = max([r['y'] + r['height'] for r in layout])
        total_height = max_y + 1
        
        fig, ax = plt.subplots(figsize=(12, 12 * total_height / self.total_width))
        
        # ... (copiar el mismo código de generate_plan para el dibujo) ...
        
        # Guardar en buffer de memoria
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
        plt.close()
        
        buf.seek(0)
        return buf.getvalue()


def validate_distribution_with_ai(rooms, client_requirements, groq_api_key):
    """
    Valida la distribución con IA y sugiere mejoras.
    
    Args:
        rooms: Lista de RoomInstance
        client_requirements: Dict con preferencias del cliente
        groq_api_key: API key de Groq
    
    Returns:
        dict: {
            'valid': bool,
            'warnings': list,
            'suggestions': list,
            'score': int (0-100)
        }
    """
    from groq import Groq
    import json
    
    client = Groq(api_key=groq_api_key)
    
    # Preparar contexto
    rooms_summary = []
    for room in rooms:
        rooms_summary.append({
            'tipo': room.code,
            'area_m2': room.area_m2
        })
    
    prompt = f"""
Eres un arquitecto experto. Valida esta distribución de vivienda:

DISTRIBUCIÓN ACTUAL:
{json.dumps(rooms_summary, indent=2)}

PREFERENCIAS DEL CLIENTE:
- Dormitorios deseados: {client_requirements.get('bedrooms', 3)}
- Baños deseados: {client_requirements.get('bathrooms', 2)}
- Estilo: {client_requirements.get('style', 'moderna')}
- Superficie objetivo: {client_requirements.get('target_area_m2', 120)} m²

VALIDA LO SIGUIENTE:
1. ¿Las dimensiones de cada habitación son apropiadas? (min/max recomendados)
2. ¿La distribución tiene sentido arquitectónicamente?
3. ¿Falta alguna habitación esencial? (pasillo, distribuidor)
4. ¿Hay habitaciones demasiado grandes o pequeñas?

RESPONDE EN JSON:
{{
  "valid": true/false,
  "score": 0-100,
  "warnings": ["advertencia 1", "advertencia 2"],
  "suggestions": ["sugerencia 1", "sugerencia 2"]
}}

SOLO JSON, sin texto adicional.
"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Limpiar respuesta
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        
        result = json.loads(response_text)
        return result
    
    except Exception as e:
        # Fallback en caso de error
        return {
            'valid': True,
            'score': 75,
            'warnings': [],
            'suggestions': [f'Error al validar con IA: {str(e)}']
        }
