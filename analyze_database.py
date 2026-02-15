import sqlite3
import os
from pathlib import Path

db_path = 'database.db'

print(f"✅ Base de datos: {os.path.abspath(db_path)}")
print(f"📁 Tamaño: {os.path.getsize(db_path) / 1024:.2f} KB\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Obtener todas las tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print(f"📊 TOTAL DE TABLAS: {len(tables)}\n")
print("=" * 80)

# Para cada tabla, mostrar su esquema
for table_name in tables:
    table = table_name[0]
    
    print(f"\n🔷 TABLA: {table}")
    print("-" * 80)
    
    # Obtener esquema de la tabla
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    
    print(f"Columnas ({len(columns)}):")
    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        markers = []
        if pk:
            markers.append("🔑 PRIMARY KEY")
        if notnull:
            markers.append("⚠️ NOT NULL")
        if default:
            markers.append(f"📌 DEFAULT={default}")
        
        markers_str = f" [{', '.join(markers)}]" if markers else ""
        print(f"  • {name} ({dtype}){markers_str}")
    
    # Contar registros
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"📦 Registros: {count}")
    except:
        print(f"📦 Registros: Error al contar")
    
    print()

conn.close()

print("=" * 80)
print("\n✅ Análisis completado")
