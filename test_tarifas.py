"""
Test de verificacion — Mis Tarifas arquitecto.
Comprueba los 3 cambios sin levantar Streamlit.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")

PASS = 0; FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}"); PASS += 1
    else:
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else "")); FAIL += 1

print("\n=== TEST TARIFAS ARQUITECTO ===\n")

# ── 1. babylon_editor acepta cost_per_m2 ────────────────────────────────────
print("[ 1. babylon_editor.py ]")
from modules.ai_house_designer.babylon_editor import generate_babylon_html
import inspect
sig = inspect.signature(generate_babylon_html)
params = list(sig.parameters.keys())
check("parametro cost_per_m2 existe", "cost_per_m2" in params)
check("default de cost_per_m2 es 1600", sig.parameters["cost_per_m2"].default == 1600)

# Genera HTML con precio por defecto
rooms = [{"name": "salon", "x": 0, "z": 0, "width": 5, "depth": 4, "height": 2.8, "color": [0.9,0.8,0.7]}]
html_default = generate_babylon_html(rooms, 5, 4)
check("HTML generado con default 1600", "1600" in html_default)
check("COST_PER_M2 aparece en JS", "COST_PER_M2" in html_default)

# Genera HTML con precio personalizado
html_custom = generate_babylon_html(rooms, 5, 4, cost_per_m2=1850)
check("HTML generado con 1850 personalizado", "1850" in html_custom)
check("1600 NO aparece con precio personalizado", "const COST_PER_M2 = 1600" not in html_custom)

# ── 2. flow.py — _get_financials usa arch_cost_per_m2 ───────────────────────
print("\n[ 2. flow.py — _get_financials override ]")
import ast
flow_src = open("modules/ai_house_designer/flow.py", encoding="utf-8").read()
check("arch_cost_per_m2 referenciado en flow.py", "arch_cost_per_m2" in flow_src)
check("override de base_m2 implementado", "_custom_m2" in flow_src)
check("isinstance check de seguridad presente", "isinstance(_custom_m2" in flow_src)

# Verificar que generate_babylon_html se llama con cost_per_m2=
check("generate_babylon_html llamado con cost_per_m2=", "cost_per_m2=_arch_cost_m2" in flow_src)

# ── 3. architects.py — bloque Mis Tarifas ────────────────────────────────────
print("\n[ 3. architects.py — Mis Tarifas ]")
arch_src = open("modules/marketplace/architects.py", encoding="utf-8").read()
check("expander Mis Tarifas presente", "Mis Tarifas" in arch_src)
check("number_input para precio m2 presente", "arch_cost_per_m2" in arch_src)
check("UPDATE architects SET avg_project_price presente", "UPDATE architects SET avg_project_price" in arch_src)
check("guarda en session_state al guardar", 'st.session_state["arch_cost_per_m2"] = _new_price' in arch_src)
check("no guarda en BD en sandbox (not _sandbox)", "if not _sandbox:" in arch_src)
check("carga desde BD al entrar (SELECT avg_project_price)", "SELECT avg_project_price FROM architects WHERE id" in arch_src)
check("mensaje demo sin persistir", "modo demo, no se persiste" in arch_src)

# ── 4. Compatibilidad: llamadas antiguas siguen funcionando ──────────────────
print("\n[ 4. COMPATIBILIDAD BACKWARD ]")
# Llamada sin cost_per_m2 (como antes) — debe funcionar
try:
    html_old = generate_babylon_html(rooms, 5, 4, "Dos aguas (clasico)", 100.0, "Zapatas", "Moderno")
    check("llamada antigua 7 params funciona", len(html_old) > 1000)
    check("usa 1600 por defecto en llamada antigua", "1600" in html_old)
except Exception as e:
    check("llamada antigua 7 params funciona", False, str(e))

# Llamada con cost_per_m2 explicito
try:
    html_new = generate_babylon_html(rooms, 5, 4, "Dos aguas (clasico)", 100.0, "Zapatas", "Moderno", cost_per_m2=2000)
    check("llamada nueva con cost_per_m2=2000 funciona", "2000" in html_new)
except Exception as e:
    check("llamada nueva con cost_per_m2=2000 funciona", False, str(e))

# ── 5. DB — columna avg_project_price existe ────────────────────────────────
print("\n[ 5. BD — avg_project_price ]")
from src import db as _db
from modules.marketplace.utils import init_db, db_conn
init_db(); _db.ensure_tables()
conn = db_conn(); c = conn.cursor()
c.execute("PRAGMA table_info(architects)")
cols = {r[1] for r in c.fetchall()}
check("columna avg_project_price existe en BD", "avg_project_price" in cols)

# demo@archirapid.com tiene avg_project_price cargable
c.execute("SELECT avg_project_price FROM architects WHERE email='demo@archirapid.com'")
row = c.fetchone()
check("demo@archirapid.com tiene avg_project_price", row is not None)
conn.close()

# ── Resultado ────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
print(f"RESULTADO: {PASS}/{PASS+FAIL} PASS")
if FAIL == 0:
    print("TODOS LOS TESTS PASARON.")
else:
    print(f"ATENCION: {FAIL} tests fallaron.")
print('='*45)
sys.exit(0 if FAIL == 0 else 1)
