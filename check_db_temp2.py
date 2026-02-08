#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('archirapid.db')
cursor = conn.cursor()

# Ver esquema de plots
cursor.execute("PRAGMA table_info(plots);")
columns = cursor.fetchall()
print("Columnas de plots:")
for col in columns:
    print(col)

conn.close()