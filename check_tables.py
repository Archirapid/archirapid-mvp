#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('archirapid.db')
cursor = conn.cursor()

# Ver tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tablas en la BD:")
for table in tables:
    print(table[0])

conn.close()