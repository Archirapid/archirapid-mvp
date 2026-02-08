import sqlite3

# Conexión a la base de datos
conn = sqlite3.connect('archirapid.db')
c = conn.cursor()

# Borrar todas las reservas
c.execute('DELETE FROM reservations;')

# Restaurar todas las fincas a disponibles
c.execute("UPDATE plots SET status = 'disponible';")

# Limpiar proyectos guardados
try:
    c.execute('DELETE FROM proyectos_guardados;')
except Exception as e:
    print(f"No existe la tabla proyectos_guardados o error: {e}")

conn.commit()
conn.close()
print('Reseteo completo de reservas, fincas y proyectos guardados.')
