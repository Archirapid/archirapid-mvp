#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('archirapid.db')
cursor = conn.cursor()

# Contar plots
cursor.execute("SELECT COUNT(*) FROM plots;")
count = cursor.fetchone()[0]
print(f"Total de plots: {count}")

# Ver todas las plots
cursor.execute("SELECT id, title, status FROM plots;")
rows = cursor.fetchall()
print("Todas las plots:")
for row in rows:
    print(row)

# Ver reservations
cursor.execute("SELECT COUNT(*) FROM reservations;")
res_count = cursor.fetchone()[0]
print(f"Total de reservations: {res_count}")

conn.close()