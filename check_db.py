import sqlite3
import json

conn = sqlite3.connect('archirapid.db')
cursor = conn.cursor()

print('Tablas en la base de datos:')
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
for table in tables:
    print('-', table[0])

print('\nContenido de projects:')
cursor.execute('SELECT id, title, files_json FROM projects')
for row in cursor.fetchall():
    try:
        data = json.loads(row[2])
        print(f'ID: {row[0]}, Title: {row[1]}')
        print(f'  Files: {data}')
        if 'modelo_3d_glb' in data:
            print(f'  ✅ Tiene modelo 3D: {data["modelo_3d_glb"]}')
        else:
            print('  ❌ No tiene modelo 3D')
    except Exception as e:
        print(f'ID: {row[0]}, Error: {e}')

conn.close()