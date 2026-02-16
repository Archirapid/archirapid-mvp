from modules.ai_house_designer import step2_planner

print('✅ step2_planner.py importa correctamente')
print(f'✅ Clase: {step2_planner.ProfessionalFloorPlan.__name__}')

# Verificar que tiene el método generate
if hasattr(step2_planner.ProfessionalFloorPlan, 'generate'):
    print('✅ Método generate() encontrado')
else:
    print('❌ Método generate() NO encontrado')

# Contar líneas
with open("modules/ai_house_designer/step2_planner.py") as f:
    lines = len(f.readlines())
    print(f'✅ Líneas totales: {lines}')
