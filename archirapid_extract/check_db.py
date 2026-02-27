import sqlite3

import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# usar siempre la instalación actual sobre C: (o la carpeta donde esté clonado)
db_path = os.path.join(base_dir, 'data.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tablas en la DB:')
for t in tables:
    print(f'  - {t[0]}')

# Count plots
cursor.execute('SELECT COUNT(*) FROM plots')
print(f'\nTotal plots: {cursor.fetchone()[0]}')

# Sample plot
cursor.execute('SELECT id, address, lat, lon FROM plots LIMIT 3')
plots = cursor.fetchall()
print('\nPrimeros 3 plots:')
for p in plots:
    print(f'  ID: {p[0]}, Address: {p[1]}, Lat: {p[2]}, Lon: {p[3]}')

conn.close()
