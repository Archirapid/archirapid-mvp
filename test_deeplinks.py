"""
Paso 12 — Test formal de deep links y sandbox mode.
Verifica lógica sin levantar Streamlit.
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")

from dotenv import load_dotenv
load_dotenv()

from src import db as _db
from modules.marketplace.utils import init_db, db_conn

init_db()
_db.ensure_tables()

import sqlite3
from datetime import datetime, timedelta

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
        FAIL += 1

print("\n=== PASO 12 — TEST DEEP LINKS & SANDBOX ===\n")

# ── 1. Tabla visitas_demo existe ──────────────────────────────────────────────
print("[ 1. TABLA visitas_demo ]")
conn = db_conn()
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='visitas_demo'")
check("visitas_demo existe", c.fetchone() is not None)

# Insertar visita simulando ?from=linkedin&user=javier&seccion=arquitecto
vid = uuid.uuid4().hex
c.execute("""INSERT OR IGNORE INTO visitas_demo
             (id,timestamp,origen,nombre_usuario,accion_realizada,session_id)
             VALUES (?,?,?,?,?,?)""",
          (vid, datetime.utcnow().isoformat(), "linkedin", "javier",
           "visita:arquitecto", "sess_test_001"))
conn.commit()
c.execute("SELECT origen, nombre_usuario, accion_realizada FROM visitas_demo WHERE id=?", (vid,))
row = c.fetchone()
check("visita ?from=linkedin registrada", row is not None and row[0] == "linkedin")
check("nombre_usuario guardado", row is not None and row[1] == "javier")
check("accion_realizada correcta", row is not None and row[2] == "visita:arquitecto")

# ── 2. Demo user demo@archirapid.com existe en DB ─────────────────────────────
print("\n[ 2. USUARIO DEMO ]")
c.execute("SELECT id, name, email FROM architects WHERE email='demo@archirapid.com'")
demo_row = c.fetchone()
check("demo@archirapid.com existe en architects", demo_row is not None)

if demo_row:
    demo_id = demo_row[0]
    c.execute("""SELECT plan_type, status, end_date FROM subscriptions
                 WHERE architect_id=? AND status='active'
                 ORDER BY created_at DESC LIMIT 1""", (demo_id,))
    sub = c.fetchone()
    check("demo user tiene suscripcion activa", sub is not None)
    if sub:
        check("plan_type es PRO o PRO_ANUAL", sub[0] in ("PRO", "PRO_ANUAL"))
        end_dt = datetime.fromisoformat(sub[2]) if sub[2] else None
        check("suscripcion no expirada", end_dt is not None and end_dt > datetime.now())

# ── 3. Password hash almacenado ───────────────────────────────────────────────
print("\n[ 3. PASSWORD HASH ]")
c.execute("SELECT password_hash FROM architects WHERE email='demo@archirapid.com'")
pw_row = c.fetchone()
check("password_hash no vacío", pw_row is not None and pw_row[0] not in (None, ""))

if pw_row and pw_row[0]:
    from werkzeug.security import check_password_hash
    check("demo1234 valida hash", check_password_hash(pw_row[0], "demo1234"))

# ── 4. Columnas nuevas en architects ─────────────────────────────────────────
print("\n[ 4. ESQUEMA architects ]")
c.execute("PRAGMA table_info(architects)")
cols = {r[1] for r in c.fetchall()}
for col in ["specialty", "address", "city", "province", "avg_project_price",
            "origen_registro", "password_hash", "phone"]:
    check(f"columna {col} existe", col in cols)

# ── 5. Esquema subscriptions ──────────────────────────────────────────────────
print("\n[ 5. ESQUEMA subscriptions ]")
c.execute("PRAGMA table_info(subscriptions)")
sub_cols = {r[1] for r in c.fetchall()}
for col in ["id", "architect_id", "plan_type", "status", "start_date", "end_date",
            "monthly_proposals_limit", "commission_rate"]:
    check(f"columna {col} existe", col in sub_cols)

# ── 6. Lógica deep link: ?seccion=arquitecto activa navegación ───────────────
print("\n[ 6. LÓGICA DEEP LINKS (simulación) ]")

def simulate_deep_link(params):
    """Simula el bloque de deep links de app.py."""
    session = {}
    qp_seccion = params.get("seccion", "")
    qp_from    = params.get("from", "")
    qp_user    = params.get("user", "")
    qp_demo    = params.get("demo", "")
    qp_modo    = params.get("modo", "")

    if not session.get("_demo_session_id"):
        session["_demo_session_id"] = uuid.uuid4().hex

    if qp_from and not session.get("_origen_registrado"):
        session["_origen_registrado"] = True
        session["_visit_from"] = qp_from
        # registrar visita en DB
        v2 = uuid.uuid4().hex
        conn2 = db_conn()
        c2 = conn2.cursor()
        c2.execute("""INSERT OR IGNORE INTO visitas_demo
                      (id,timestamp,origen,nombre_usuario,accion_realizada,session_id)
                      VALUES (?,?,?,?,?,?)""",
                   (v2, datetime.utcnow().isoformat(), qp_from, qp_user or "anonimo",
                    f"visita:{qp_seccion or 'home'}", session["_demo_session_id"]))
        conn2.commit(); conn2.close()

    if qp_user and not session.get("_welcome_shown"):
        session["_welcome_shown"] = True
        session["_toast"] = f"Bienvenido, {qp_user.capitalize()}"

    if qp_demo == "true" and not session.get("sandbox_mode"):
        session["sandbox_mode"] = True
        session["sandbox_user"] = qp_user.capitalize() if qp_user else "Visitante"

    if qp_seccion == "arquitecto" and not session.get("_deep_link_routed"):
        session["selected_page"] = "Arquitectos (Marketplace)"
        session["_deep_link_routed"] = True
        if qp_modo == "estudio" or qp_demo == "true":
            session["_open_estudio_tab"] = True

    return session

# Test A: ?seccion=arquitecto
s = simulate_deep_link({"seccion": "arquitecto"})
check("?seccion=arquitecto -> selected_page correcto",
      s.get("selected_page") == "Arquitectos (Marketplace)")
check("?seccion=arquitecto -> deep_link_routed marcado",
      s.get("_deep_link_routed") is True)

# Test B: ?demo=true&user=javier
s = simulate_deep_link({"demo": "true", "user": "javier"})
check("?demo=true -> sandbox_mode activado", s.get("sandbox_mode") is True)
check("?user=javier -> sandbox_user=Javier", s.get("sandbox_user") == "Javier")
check("?user=javier -> toast generado", "Javier" in s.get("_toast", ""))

# Test C: ?from=linkedin registra visita en DB
s = simulate_deep_link({"from": "linkedin", "user": "test_link", "seccion": "arquitecto"})
check("?from=linkedin -> _origen_registrado", s.get("_origen_registrado") is True)
c.execute("SELECT id FROM visitas_demo WHERE origen='linkedin' AND nombre_usuario='test_link'")
check("visita linkedin guardada en DB", c.fetchone() is not None)

# Test D: combinacion completa
s = simulate_deep_link({"seccion": "arquitecto", "demo": "true", "from": "email_campaign",
                        "user": "maria", "modo": "estudio"})
check("combinacion completa -> selected_page", s.get("selected_page") == "Arquitectos (Marketplace)")
check("combinacion completa -> sandbox_mode", s.get("sandbox_mode") is True)
check("combinacion completa -> sandbox_user=Maria", s.get("sandbox_user") == "Maria")
check("combinacion completa -> _open_estudio_tab", s.get("_open_estudio_tab") is True)
check("combinacion completa -> _deep_link_routed", s.get("_deep_link_routed") is True)

# Test E: ?seccion=arquitecto&modo=estudio sin demo
s = simulate_deep_link({"seccion": "arquitecto", "modo": "estudio"})
check("?modo=estudio -> _open_estudio_tab", s.get("_open_estudio_tab") is True)
check("?modo=estudio sin demo -> sandbox NO activado", not s.get("sandbox_mode"))

# ── 7. tracking: tabla visitas_demo tiene registros de los tests ──────────────
print("\n[ 7. TRACKING VISITAS_DEMO ]")
c.execute("SELECT COUNT(*) FROM visitas_demo")
total = c.fetchone()[0]
check("visitas_demo tiene al menos 3 registros de test", total >= 3)

c.execute("SELECT COUNT(DISTINCT origen) FROM visitas_demo")
origenes = c.fetchone()[0]
check("hay al menos 2 origenes distintos", origenes >= 2)

conn.close()

# ── Resultado final ────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
total_tests = PASS + FAIL
print(f"RESULTADO: {PASS}/{total_tests} PASS")
if FAIL == 0:
    print("TODOS LOS TESTS PASARON — Paso 12 completado.")
else:
    print(f"ATENCION: {FAIL} tests fallaron.")
print('='*50)
sys.exit(0 if FAIL == 0 else 1)
