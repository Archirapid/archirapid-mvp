#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('archirapid.db')
cursor = conn.cursor()

# Verificar todas las tablas y contar filas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"Tabla {table_name}: {count} filas")
    except Exception as e:
        print(f"Error en tabla {table_name}: {e}")

conn.close()