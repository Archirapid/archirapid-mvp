import sqlite3
from pathlib import Path

# Buscar la base de datos
possible_paths = [
    Path('modules/marketplace/plots.db'),
    Path('marketplace.db'),
    Path('plots.db'),
    Path('data/plots.db'),
    Path('database.db')
]

db_path = None
for path in possible_paths:
    if path.exists():
        db_path = path
        break

if not db_path:
    print("❌ No se encontró ninguna base de datos")
    print("Buscando en:")
    for path in possible_paths:
        print(f"  - {path.absolute()}")
else:
    print(f"✅ Usando BD: {db_path.absolute()}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("\n=== COLUMNAS DE LA TABLA PLOTS ===")
    cursor.execute("PRAGMA table_info(plots)")
    columns = cursor.fetchall()
    
    if not columns:
        print("⚠️ La tabla 'plots' no existe o está vacía")
        
        # Mostrar todas las tablas disponibles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nTablas disponibles:")
        for table in tables:
            print(f"  • {table[0]}")
    else:
        for col in columns:
            cid, name, dtype, notnull, default, pk = col
            print(f"  • {name} ({dtype}){' [PRIMARY KEY]' if pk else ''}{' [NOT NULL]' if notnull else ''}")
    
    conn.close()
