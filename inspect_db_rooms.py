import sqlite3
import json

conn = sqlite3.connect('database.db')
cur = conn.cursor()

# Obtener todas las tablas
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

print("=" * 80)
print("🗄️  TABLAS EN database.db")
print("=" * 80)
for t in tables:
    print(f"  • {t[0]}")

print("\n" + "=" * 80)
print("📋 ESQUEMA COMPLETO DE TODAS LAS TABLAS")
print("=" * 80)

for table in tables:
    table_name = table[0]
    print(f"\n{'='*80}")
    print(f"📌 TABLA: {table_name}")
    print(f"{'='*80}")
    
    # Esquema de la tabla
    columns = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(f"\n  Columnas ({len(columns)}):")
    for col in columns:
        pk = "🔑 PRIMARY KEY" if col[5] == 1 else ""
        notnull = "NOT NULL" if col[3] == 1 else ""
        default = f"DEFAULT {col[4]}" if col[4] else ""
        print(f"    • {col[1]:25} {col[2]:15} {pk} {notnull} {default}")
    
    # Contar registros
    count = cur.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"\n  📊 Registros: {count}")
    
    # Si hay registros, mostrar 2 ejemplos
    if count > 0:
        rows = cur.execute(f"SELECT * FROM {table_name} LIMIT 2").fetchall()
        print(f"\n  🔍 Ejemplos de datos (primeros 2 registros):")
        for i, row in enumerate(rows, 1):
            print(f"\n    Registro {i}:")
            for j, col in enumerate(columns):
                val = row[j]
                # Si parece JSON, mostrar formateado
                if isinstance(val, str) and (val.startswith('{') or val.startswith('[')):
                    try:
                        parsed = json.loads(val)
                        val = json.dumps(parsed, indent=2, ensure_ascii=False)[:200] + "..."
                    except:
                        pass
                # Truncar valores largos
                if isinstance(val, str) and len(val) > 100:
                    val = val[:100] + "..."
                print(f"      {col[1]:20} = {val}")

print("\n" + "=" * 80)
print("🔍 BÚSQUEDA DE CAMPOS RELACIONADOS CON HABITACIONES/BAÑOS")
print("=" * 80)

keywords = ['room', 'bedroom', 'bath', 'habitacion', 'dormitorio', 'bano', 'design', 'floor', 'area', 'm2']

for table in tables:
    table_name = table[0]
    columns = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    
    matching_cols = []
    for col in columns:
        col_name = col[1].lower()
        if any(kw in col_name for kw in keywords):
            matching_cols.append(col[1])
    
    if matching_cols:
        print(f"\n📍 {table_name}:")
        for col in matching_cols:
            print(f"    ✓ {col}")

conn.close()
print("\n" + "=" * 80)
print("✅ ANÁLISIS COMPLETO")
print("=" * 80)
