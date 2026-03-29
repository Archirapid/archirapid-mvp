"""
seed_supabase.py
Migra datos demo de SQLite local → Supabase PostgreSQL.
Ejecutar UNA VEZ después de configurar Supabase.
  python seed_supabase.py
"""
import os, sys, sqlite3, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Leer URL directamente del .env (ignorar el comentario)
import re
env_content = Path(".env").read_text()
m = re.search(r'^#?\s*SUPABASE_DB_URL=(.+)$', env_content, re.MULTILINE)
if not m:
    print("ERROR: SUPABASE_DB_URL no encontrada en .env")
    sys.exit(1)

db_url = m.group(1).strip()
if db_url.startswith("#"):
    # Commented out — read from arg or prompt
    print("SUPABASE_DB_URL está comentada en .env")
    if len(sys.argv) > 1:
        db_url = sys.argv[1]
    else:
        db_url = input("Pega la SUPABASE_DB_URL: ").strip()

if not db_url.startswith("postgresql://"):
    print("ERROR: URL no válida:", db_url[:40])
    sys.exit(1)

if '?' not in db_url:
    db_url += '?sslmode=require'

print(f"Conectando a Supabase: {db_url[:50]}...")

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: instala psycopg2-binary primero: pip install psycopg2-binary")
    sys.exit(1)

# Abrir conexiones
sqlite_conn = sqlite3.connect("database.db")
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
pg_conn.autocommit = False

# Tablas a migrar (en orden para respetar FK si las hay)
TABLES = [
    'users', 'owners', 'clients', 'architects', 'arquitectos',
    'service_providers', 'inmobiliarias',
    'plots', 'projects', 'proposals',
    'subscriptions', 'reservations', 'client_interests',
    'prefab_catalog', 'waitlist',
    'document_certs', 'plot_alerts', 'visitas_demo',
    'fincas_mls', 'firmas_colaboracion',
    'planes',
]

migrated = 0
skipped = 0

for table in TABLES:
    # Check if table exists in SQLite
    sc = sqlite_conn.cursor()
    sc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    if not sc.fetchone():
        continue

    sc.execute(f"SELECT COUNT(*) FROM {table}")
    count = sc.fetchone()[0]
    if count == 0:
        continue

    sc.execute(f"SELECT * FROM {table}")
    rows = sc.fetchall()
    if not rows:
        continue

    cols = rows[0].keys()

    # Check if table exists in Postgres
    pg_cur = pg_conn.cursor()
    pg_cur.execute(
        "SELECT to_regclass(%s)",
        (table,)
    )
    exists = pg_cur.fetchone()['to_regclass']
    if not exists:
        print(f"  [SKIP] {table}: no existe en Postgres")
        skipped += 1
        continue

    # Get Postgres columns for this table
    pg_cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public'",
        (table,)
    )
    pg_cols_set = {r['column_name'] for r in pg_cur.fetchall()}

    # Only insert columns that exist in both
    shared_cols = [c for c in cols if c in pg_cols_set]
    if not shared_cols:
        print(f"  [SKIP] {table}: sin columnas coincidentes")
        skipped += 1
        continue

    inserted = 0
    errors = 0
    for row in rows:
        vals = []
        for c in shared_cols:
            v = row[c]
            # Convert bytes/blob to string if needed
            if isinstance(v, bytes):
                try:
                    v = v.decode('utf-8')
                except Exception:
                    v = None
            vals.append(v)

        placeholders = ', '.join(['%s'] * len(shared_cols))
        col_names = ', '.join(shared_cols)
        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        try:
            pg_cur.execute(sql, vals)
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    ERROR in {table}: {e}")
            pg_conn.rollback()
            # Try next row with fresh transaction
            pg_conn.autocommit = False
            continue

    pg_conn.commit()
    print(f"  [OK] {table}: {inserted}/{count} filas migradas, {errors} errores")
    migrated += inserted

# Fix sequences for SERIAL columns after bulk insert
pg_cur = pg_conn.cursor()
pg_cur.execute("""
    SELECT schemaname, tablename, columnname, sequencename
    FROM pg_sequences
    JOIN information_schema.columns
        ON table_schema = schemaname
        AND column_default LIKE 'nextval%'
    WHERE schemaname = 'public'
    LIMIT 1
""")
# Simpler approach: reset sequences for all serial columns
try:
    for table in TABLES:
        sc = sqlite_conn.cursor()
        sc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not sc.fetchone():
            continue
        pg_cur.execute(f"SELECT MAX(id) FROM {table}")
        result = pg_cur.fetchone()
        max_id = result['max'] if result else None
        if max_id:
            pg_cur.execute(f"SELECT setval('{table}_id_seq', {max_id})")
            pg_conn.commit()
except Exception as e:
    print(f"  Secuencias: {e} (no crítico)")

sqlite_conn.close()
pg_conn.close()

print(f"\n✅ Migración completada: {migrated} filas totales, {skipped} tablas saltadas")
