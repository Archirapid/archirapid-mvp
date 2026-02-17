"""
Test del generador de planos 2D con el nuevo motor arquitectónico
"""
import sys
sys.path.insert(0, 'C:/ARCHIRAPID_PROYECT25')

from modules.ai_house_designer.data_model import HouseDesign, RoomType, RoomInstance, Plot
from modules.ai_house_designer.floor_plan_svg import FloorPlanSVG

# Crear parcela de prueba
plot = Plot(
    id="test_plot",
    area_m2=500,
    buildable_ratio=0.6,
    shape="rectangular"
)

# Crear diseño de prueba
design = HouseDesign(
    plot=plot,
    style="Mediterráneo",
    rooms=[],
    budget_limit=150000
)

# Añadir habitaciones de prueba
rooms_test = [
    {'code': 'salon_cocina', 'name': 'Salón-Cocina', 'area_m2': 30},
    {'code': 'dormitorio_principal', 'name': 'Dormitorio Principal', 'area_m2': 18},
    {'code': 'dormitorio', 'name': 'Dormitorio 1', 'area_m2': 12},
    {'code': 'dormitorio', 'name': 'Dormitorio 2', 'area_m2': 10},
    {'code': 'bano', 'name': 'Baño cortesía', 'area_m2': 5},
    {'code': 'bano', 'name': 'Baño suite', 'area_m2': 6},
    {'code': 'garaje', 'name': 'Garaje', 'area_m2': 20},
    {'code': 'porche', 'name': 'Porche', 'area_m2': 12},
    {'code': 'piscina', 'name': 'Piscina', 'area_m2': 30},
]

for r in rooms_test:
    room_type = RoomType(
        code=r['code'],
        name=r['name'],
        min_m2=1, max_m2=100,
        base_cost_per_m2=800
    )
    room_instance = RoomInstance(
        room_type=room_type,
        area_m2=r['area_m2']
    )
    design.rooms.append(room_instance)

print(f"✅ Diseño creado con {len(design.rooms)} habitaciones\n")

# Generar plano 2D
try:
    print("🎨 Generando plano 2D profesional...")
    planner = FloorPlanSVG(design)
    png_bytes = planner.generate()
    
    # Guardar PNG
    output_path = 'test_floor_plan_output.png'
    with open(output_path, 'wb') as f:
        f.write(png_bytes)
    
    print(f"✅ Plano 2D generado exitosamente: {output_path}")
    print(f"   Tamaño: {len(png_bytes) / 1024:.1f} KB\n")
    
    # Verificar layout generado
    layout = planner._layout_rooms()
    print(f"📐 Layout generado: {len(layout)} espacios\n")
    for item in layout:
        room = item['room']
        print(f"  {room.room_type.name:25s} → "
              f"x={item['x']:5.1f} y={item['y']:5.1f} "
              f"{item['width']:.1f}x{item['height']:.1f}m "
              f"(zona: {item['zone']})")
    
except Exception as e:
    print(f"❌ ERROR al generar plano 2D:")
    print(f"   {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
