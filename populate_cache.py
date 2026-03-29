"""
Script para pre-popular el caché de verificación IA en database.db.
Ejecutar UNA VEZ localmente tras actualizar la GEMINI_API_KEY en .env.
Después: git add database.db && git push
"""
import sqlite3, json, base64, time, os, sys
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "database.db"
API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={}"
PROMPT = """Extrae de esta nota catastral: referencia_catastral, superficie_grafica_m2, municipio.
Devuelve solo JSON: {"referencia_catastral":"codigo","superficie_grafica_m2":numero,"municipio":"ciudad"}"""

if not API_KEY:
    print("ERROR: GEMINI_API_KEY no encontrada en .env")
    sys.exit(1)

print(f"Usando key: {API_KEY[:20]}...")

conn = sqlite3.connect(DB_PATH, timeout=15)
conn.execute("PRAGMA journal_mode=WAL")

fincas = conn.execute(
    "SELECT id, title, plano_catastral_path, ai_verification_cache FROM plots ORDER BY title"
).fetchall()

print(f"\nFincas encontradas: {len(fincas)}\n")

updated = 0
for plot_id, title, pdf_path, existing_cache in fincas:
    print(f"→ {title}")

    if existing_cache:
        print(f"  ✓ Ya tiene caché, saltando.\n")
        continue

    if not pdf_path or not os.path.exists(pdf_path):
        print(f"  ⚠ PDF no encontrado: {pdf_path}, saltando.\n")
        continue

    # Leer PDF → imagen
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)

        # Primero intentar extracción de texto
        text = page.get_text().strip()
        doc.close()

        if len(text) > 100:
            print(f"  ℹ PDF con texto ({len(text)} chars) — caché no necesario para Gemini Vision")
            print(f"    (el pipeline OCR lo maneja sin Gemini)\n")
            continue

        # PDF escaneado — usar Gemini Vision
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes()
        doc.close()

        img_b64 = base64.b64encode(img_bytes).decode()

        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                    {"text": PROMPT}
                ]
            }]
        }

        print(f"  Llamando a Gemini Vision...", end=" ", flush=True)
        resp = requests.post(API_URL.format(API_KEY), json=payload, timeout=60)

        if resp.status_code == 429:
            print("❌ 429 Rate limit — espera 30s y reintenta")
            time.sleep(30)
            resp = requests.post(API_URL.format(API_KEY), json=payload, timeout=60)

        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Limpiar JSON
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        cache_data = {
            "superficie_m2": data.get("superficie_grafica_m2", 0),
            "referencia_catastral": data.get("referencia_catastral", ""),
            "municipio": data.get("municipio", ""),
        }

        conn.execute(
            "UPDATE plots SET ai_verification_cache=? WHERE id=?",
            (json.dumps(cache_data), plot_id)
        )
        conn.commit()
        updated += 1
        print(f"✅ {cache_data}")
        print()

        # Pausa entre llamadas para no superar 5 RPM
        time.sleep(13)

    except Exception as e:
        print(f"  ❌ Error: {e}\n")

conn.close()
print(f"Completado. {updated} fincas cacheadas.")
print("\nAhora ejecuta:")
print("  git add database.db")
print("  git commit -m 'Cache: pre-populate AI verification for all demo fincas'")
print("  git push")
