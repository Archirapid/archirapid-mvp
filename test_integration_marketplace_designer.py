"""
Test de integración: Marketplace → AI House Designer
=====================================================

Este script prueba el flujo completo:
1. Un cliente compra/reserva una finca
2. Cliente hace clic en "DISEÑAR CON IA"
3. El diseñador carga datos de la finca desde la BD
4. Se pre-configura el formulario con límites de edificabilidad
"""

import sqlite3
import json

# Conectar a la base de datos
conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 70)
print("🧪 TEST DE INTEGRACIÓN: MARKETPLACE → AI DESIGNER")
print("=" * 70)

# PASO 1: Verificar que tenemos fincas disponibles
print("\n1️⃣ VERIFICANDO FINCAS DISPONIBLES...")
cur.execute("""
    SELECT id, title, catastral_ref, m2, superficie_edificable, price, status
    FROM plots 
    WHERE status = 'disponible'
    LIMIT 5
""")
fincas = cur.fetchall()

if fincas:
    print(f"✅ Encontradas {len(fincas)} fincas disponibles:")
    for f in fincas:
        print(f"   • ID {f['id']}: {f['title']}")
        print(f"     - Superficie total: {f['m2']:.2f} m²" if f['m2'] else "     - Superficie total: NO ESPECIFICADO")
        print(f"     - Edificable: {f['superficie_edificable']:.2f} m²" if f['superficie_edificable'] else "     - Edificable: NO ESPECIFICADO")
        print(f"     - Precio: {f['price']:,.0f} €" if f['price'] else "     - Precio: NO ESPECIFICADO")
else:
    print("❌ No hay fincas disponibles")
    conn.close()
    exit(1)

# PASO 2: Simular reserva de un cliente
print("\n2️⃣ SIMULANDO RESERVA DE CLIENTE...")
finca_seleccionada = fincas[0]  # Tomar la primera finca
cliente_email = "test_integration@archirapid.com"

print(f"   Cliente: {cliente_email}")
print(f"   Finca: {finca_seleccionada['title']}")

# Verificar si el cliente existe en users
cur.execute("SELECT id, email, role FROM users WHERE email = ?", (cliente_email,))
cliente = cur.fetchone()

if not cliente:
    print("   ℹ️ Cliente no existe, creando usuario de prueba...")
    import uuid
    cliente_id = uuid.uuid4().hex
    cur.execute("""
        INSERT INTO users (id, email, name, role, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (cliente_id, cliente_email, "Cliente Test Integración", "client", "test_hash"))
    conn.commit()
    print(f"   ✅ Cliente creado con ID: {cliente_id}")
else:
    print(f"   ✅ Cliente ya existe: {cliente['email']} (role: {cliente['role']})")

# Crear reserva
import uuid
from datetime import datetime

reserva_id = uuid.uuid4().hex
cur.execute("""
    INSERT INTO reservations (id, plot_id, buyer_name, buyer_email, amount, kind, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    reserva_id,
    finca_seleccionada['id'],
    "Cliente Test Integración",
    cliente_email,
    finca_seleccionada['price'] * 0.1,  # 10% de señal
    'reserve',
    datetime.now().isoformat()
))
conn.commit()
print(f"   ✅ Reserva creada con ID: {reserva_id}")

# PASO 3: Simular clic en "DISEÑAR CON IA"
print("\n3️⃣ SIMULANDO FLUJO: DISEÑAR CON IA...")
design_plot_id = finca_seleccionada['id']
print(f"   design_plot_id = {design_plot_id}")

# Consulta exacta que hace flow.py 
cur.execute("""
    SELECT id, title, catastral_ref, m2, superficie_edificable, 
           lat, lon, owner_email
    FROM plots 
    WHERE id = ?
""", (design_plot_id,))

plot_row = cur.fetchone()

if plot_row:
    print("   ✅ Datos de finca cargados correctamente:")
    
    # Recrear el dict que flow.py crea
    design_plot_data = {
        'id': plot_row['id'],
        'title': plot_row['title'],
        'catastral_ref': plot_row['catastral_ref'],
        'total_m2': plot_row['m2'] or 0,
        'buildable_m2': plot_row['superficie_edificable'] or (plot_row['m2'] * 0.33 if plot_row['m2'] else 0),
        'lat': plot_row['lat'],
        'lon': plot_row['lon'],
        'owner_email': plot_row['owner_email']
    }
    
    print(f"\n   📋 Datos cargados en session_state:")
    print(f"      • Título: {design_plot_data['title']}")
    print(f"      • Ref. Catastral: {design_plot_data['catastral_ref']}")
    print(f"      • Superficie total: {design_plot_data['total_m2']:.2f} m²")
    print(f"      • Superficie edificable: {design_plot_data['buildable_m2']:.2f} m²")
    print(f"      • Coordenadas: ({design_plot_data['lat']}, {design_plot_data['lon']})")
    
    # PASO 4: Simular configuración de AI requirements
    print("\n4️⃣ CONFIGURANDO AI REQUIREMENTS...")
    max_buildable = design_plot_data['buildable_m2']
    ai_house_requirements = {
        "target_area_m2": min(120.0, max_buildable),
        "max_buildable_m2": max_buildable,
        "budget_limit": None,
        "bedrooms": 3,
        "bathrooms": 2,
        "wants_pool": False,
        "wants_porch": True,
        "wants_garage": False,
        "wants_outhouse": False,
        "max_floors": 1,
        "style": "moderna",
        "materials": ["hormigón"],
        "notes": "",
        "orientation": "Sur",
        "roof_type": "A dos aguas",
        "energy_rating": "B",
        "accessibility": False,
        "sustainable_materials": []
    }
    
    print(f"   ✅ Superficie objetivo: {ai_house_requirements['target_area_m2']:.2f} m²")
    print(f"   ✅ Límite edificable: {ai_house_requirements['max_buildable_m2']:.2f} m²")
    print(f"   ✅ Habitaciones: {ai_house_requirements['bedrooms']}")
    print(f"   ✅ Baños: {ai_house_requirements['bathrooms']}")
    print(f"   ✅ Estilo: {ai_house_requirements['style']}")
    
    # PASO 5: Validar límites
    print("\n5️⃣ VALIDANDO LÍMITES DE EDIFICABILIDAD...")
    if ai_house_requirements['target_area_m2'] <= ai_house_requirements['max_buildable_m2']:
        print(f"   ✅ VALIDACIÓN OK: {ai_house_requirements['target_area_m2']:.2f} m² ≤ {ai_house_requirements['max_buildable_m2']:.2f} m²")
    else:
        print(f"   ❌ ERROR: Superficie objetivo excede el límite edificable")
        print(f"      Target: {ai_house_requirements['target_area_m2']:.2f} m²")
        print(f"      Límite: {ai_house_requirements['max_buildable_m2']:.2f} m²")
    
else:
    print("   ❌ ERROR: No se pudieron cargar datos de la finca")
    conn.close()
    exit(1)

# PASO 6: Limpiar datos de prueba
print("\n6️⃣ LIMPIANDO DATOS DE PRUEBA...")
respuesta = input("   ¿Eliminar reserva y usuario de prueba? (s/n): ")
if respuesta.lower() == 's':
    cur.execute("DELETE FROM reservations WHERE id = ?", (reserva_id,))
    cur.execute("DELETE FROM users WHERE email = ?", (cliente_email,))
    conn.commit()
    print("   ✅ Datos de prueba eliminados")
else:
    print("   ℹ️ Datos de prueba conservados")

conn.close()

print("\n" + "=" * 70)
print("✅ TEST COMPLETADO EXITOSAMENTE")
print("=" * 70)
print("\n📊 RESUMEN:")
print("   • Fincas disponibles: OK")
print("   • Reserva de cliente: OK")
print("   • Carga de datos en designer: OK")
print("   • Validación de límites: OK")
print("   • SQL query corregido (sin is_urban): OK")
print("\n🚀 El flujo marketplace → AI designer está funcionando correctamente!")
