import fitz  # PyMuPDF
import requests  # Para llamadas directas a la API REST de Gemini (sin SDK)
from groq import Groq
from PIL import Image
import io
import os
import json
import base64
from dotenv import load_dotenv
import streamlit as st
from src.models.finca import FincaMVP


def _gemini_rest(api_key: str, prompt: str, image_bytes: bytes = None, model: str = "gemini-2.0-flash") -> str:
    """Llama a Gemini via REST API directa. Sin SDKs, funciona en cualquier plataforma.
    En caso de 429 reintenta con gemini-2.0-flash-lite."""
    import time
    models_to_try = [model] if model != "gemini-2.0-flash" else ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
    parts = [{"text": prompt}]
    if image_bytes:
        parts.insert(0, {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}})
    payload = {"contents": [{"parts": parts}]}
    last_exc = None
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 429 and m != models_to_try[-1]:
                time.sleep(2)
                continue  # Probar el siguiente modelo
            if not resp.ok:
                raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:400]}")
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            last_exc = e
            if "429" in str(e) and m != models_to_try[-1]:
                time.sleep(2)
                continue
            raise
    raise last_exc


def _get_gemini_key() -> str:
    """Obtiene la clave Gemini de secrets o env. Prueba todos los métodos de acceso."""
    _SKIP = {"", "tu_clave_gemini_aqui", "tu_clave_aqui"}
    debug = []

    def _valid(v):
        s = str(v).strip() if v else ""
        return s if s and s not in _SKIP else None

    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        # 1. st.secrets bracket
        try:
            v = _valid(st.secrets[k])
            if v:
                return v
        except Exception as e:
            debug.append(f"{k}[bracket]:{type(e).__name__}")
        # 2. env var (app.py syncs st.secrets → os.environ al arrancar)
        v = _valid(os.getenv(k, ""))
        if v:
            return v
        debug.append(f"{k}[env]:empty")

    # 3. Fallback: leer secrets.toml directamente del filesystem
    import pathlib
    _toml_candidates = [
        pathlib.Path.home() / ".streamlit" / "secrets.toml",
        pathlib.Path("/mount/src") / "archirapid-mvp" / ".streamlit" / "secrets.toml",
        pathlib.Path(__file__).resolve().parents[3] / ".streamlit" / "secrets.toml",
    ]
    try:
        import tomllib as _tl
    except ImportError:
        try:
            import tomli as _tl
        except ImportError:
            _tl = None
    if _tl:
        for p in _toml_candidates:
            try:
                if p.exists():
                    data = _tl.loads(p.read_text(encoding="utf-8"))
                    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                        v = _valid(data.get(k, ""))
                        if v:
                            return v
                    debug.append(f"toml:{p}:no_key")
                else:
                    debug.append(f"toml:{p}:missing")
            except Exception as e:
                debug.append(f"toml:{p}:{type(e).__name__}")
    try:
        st.session_state["_gemini_key_debug"] = debug
    except Exception:
        pass
    return None

# Forzar recarga de variables de entorno
load_dotenv(override=True)

def extraer_datos_catastral(pdf_path):
    """
    Función simplificada al máximo para extraer datos catastrales
    Compatible con Streamlit y con scripts, usando la misma lógica de API key que el resto.
    """
    try:
        # Cargar variables de entorno desde .env
        load_dotenv()

        api_key = None

        # Intentar usar st.secrets SOLO si estamos en Streamlit
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                api_key = (st.secrets.get("GEMINI_API_KEY") or
                           st.secrets.get("GOOGLE_API_KEY"))
        except Exception:
            pass

        # Fallback a .env para desarrollo local
        if not api_key:
            api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                return {"error": "No se encontró GEMINI_API_KEY ni GOOGLE_API_KEY en secrets/env"}

        api_key = api_key.strip()

        # Cargar PDF y convertir primera página a imagen
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)  # Primera página
        pix = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0))  # Zoom 3.0 para mejor calidad

        # Verificar que la imagen no esté vacía
        if pix.width == 0 or pix.height == 0:
            doc.close()
            return {"error": "La imagen generada del PDF está vacía o corrupta"}

        img_bytes = pix.tobytes()
        if not img_bytes or len(img_bytes) == 0:
            doc.close()
            return {"error": "No se pudieron generar bytes de imagen del PDF"}

        doc.close()

        # Prompt corto para extraer datos catastrales
        prompt = """Extrae de esta nota catastral: referencia_catastral, superficie_grafica_m2, municipio.
Devuelve solo JSON: {"referencia_catastral":"codigo","superficie_grafica_m2":numero,"municipio":"ciudad"}"""

        try:
            # Llamada directa REST (sin SDK)
            text = _gemini_rest(api_key, prompt, img_bytes)
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            if not text:
                return {"error": "Respuesta vacía del modelo gemini-1.5-flash"}

            # Convertir a diccionario Python
            try:
                resultado = json.loads(text)

                # Verificar que tenemos los campos esperados
                campos_requeridos = ['referencia_catastral', 'superficie_grafica_m2', 'municipio']
                if not all(campo in resultado for campo in campos_requeridos):
                    return {"error": "Respuesta incompleta del modelo: faltan campos requeridos"}

                return resultado

            except json.JSONDecodeError as json_error:
                return {"error": f"JSON inválido del modelo: {str(json_error)}"}

        except Exception as model_error:
            return {"error": f"Error con modelo gemini-1.5-flash: {str(model_error)}"}

    except Exception as e:
        error_msg = str(e).lower()

        if 'quota' in error_msg or '429' in error_msg:
            return {"error": "Se ha agotado la cuota de la API de Gemini. Espera unos minutos para que se resetee automáticamente."}
        elif 'key' in error_msg or 'invalid' in error_msg or 'unauthorized' in error_msg:
            return {"error": "La clave API de Gemini no es válida. Verifica tu GEMINI_API_KEY en el archivo .env"}
        elif 'network' in error_msg or 'connection' in error_msg:
            return {"error": "Error de conexión a internet. Verifica tu conexión y vuelve a intentarlo."}
        else:
            return {"error": f"Error crítico al procesar el PDF. Detalles técnicos: {str(e)}"}

def _parse_catastral_json(text: str) -> dict:
    """Limpia y parsea el JSON que devuelve Gemini."""
    for prefix in ("```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    data = json.loads(text)
    return {
        "referencia_catastral": data.get("referencia_catastral"),
        "superficie_grafica_m2": data.get("superficie_grafica_m2"),
        "municipio": data.get("municipio"),
    }


def extraer_datos_nota_catastral(pdf_path: str) -> dict:
    """
    Extrae datos catastrales de una nota simple.

    Estrategia (por orden, de menor a mayor coste de API):
    1. Extracción de texto nativa con PyMuPDF (gratis, sin API).
       Las notas catastrales son PDFs con texto seleccionable → siempre funciona.
    2. Si el PDF es un escáner (texto < 100 chars), fallback a Gemini Vision.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        raw_text = page.get_text()
        doc.close()
    except Exception as e:
        return {"error": f"No se pudo abrir el PDF: {e}"}

    # --- VÍA 1: texto nativo (sin API) ---
    if raw_text and len(raw_text.strip()) >= 100:
        try:
            api_key = _get_gemini_key()
            if not api_key:
                return {"error": "No se encontró GEMINI_API_KEY"}

            prompt = (
                "Extrae de este texto de nota catastral: referencia_catastral, "
                "superficie_grafica_m2 (número entero), municipio.\n"
                "Devuelve SOLO JSON: "
                '{"referencia_catastral":"codigo","superficie_grafica_m2":numero,"municipio":"ciudad"}\n\n'
                f"TEXTO:\n{raw_text[:3000]}"
            )
            text = _gemini_rest(api_key, prompt)   # sin imagen → ~500 tokens, gratis
            return _parse_catastral_json(text)
        except Exception as e:
            return {"error": f"Error al procesar la nota catastral: {str(e)}"}

    # --- VÍA 2: PDF escaneado → Gemini Vision (fallback) ---
    try:
        api_key = _get_gemini_key()
        if not api_key:
            return {"error": "No se encontró GEMINI_API_KEY"}

        doc2 = fitz.open(pdf_path)
        page2 = doc2.load_page(0)
        pix = page2.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
        img_bytes = pix.tobytes("png")
        doc2.close()

        prompt = (
            "Extrae de esta nota catastral: referencia_catastral, "
            "superficie_grafica_m2, municipio.\n"
            'Devuelve solo JSON: {"referencia_catastral":"codigo","superficie_grafica_m2":numero,"municipio":"ciudad"}'
        )
        text = _gemini_rest(api_key, prompt, img_bytes)
        return _parse_catastral_json(text)
    except Exception as e:
        return {"error": f"Error al procesar la nota catastral: {str(e)}"}

def extraer_datos_catastral_completo(pdf_path: str) -> dict:
    """
    Extrae datos catastrales completos incluyendo plano, medidas, geometría y orientación norte.

    Args:
        pdf_path (str): Ruta al archivo PDF de la nota catastral

    Returns:
        dict: Diccionario con datos completos extraídos o error
    """
    import subprocess
    import sys
    from pathlib import Path
    import shutil
    import os

    try:
        # Verificar que el PDF existe
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"error": f"PDF no encontrado: {pdf_path}"}

        # Crear directorio de trabajo (ruta absoluta)
        work_dir = Path.cwd() / "archirapid_extract"
        output_dir = work_dir / "catastro_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copiar PDF al directorio de trabajo como "Catastro.pdf"
        target_pdf = work_dir / "Catastro.pdf"
        shutil.copy2(pdf_path, target_pdf)

        # Cambiar al directorio de trabajo
        original_cwd = os.getcwd()
        os.chdir(work_dir)

        try:
            # Ejecutar pipeline de extracción completo
            scripts = [
                ("extract_pdf.py", "Extracción de PDF"),
                ("ocr_and_preprocess.py", "OCR y preprocesado"),
                ("vectorize_plan.py", "Vectorización de plano"),
                ("compute_edificability.py", "Cálculo de edificabilidad")
            ]

            for script, description in scripts:
                print(f"Ejecutando {description}...")
                try:
                    result = subprocess.run(
                        [sys.executable, script],
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                    print(f"✓ {description} completado")
                except subprocess.CalledProcessError as e:
                    # Solo fallar si es un error real, no una advertencia sobre librerías opcionales
                    if "module named 'pdfplumber'" in e.stderr or "module named 'pdf2image'" in e.stderr:
                        print(f"⚠️ {description} completado con advertencias (librerías opcionales faltantes)")
                    else:
                        print(f"✗ Error en {description}: {e}")
                        return {"error": f"Error ejecutando {description}: {e.stderr}"}

            # Verificar que se generaron los archivos esperados intentando leerlos
            actual_output_dir = work_dir / "catastro_output"
            
            try:
                # Leer datos de edificabilidad
                edificability_path = actual_output_dir / "edificability.json"
                with open(edificability_path, 'r', encoding='utf-8') as f:
                    edificability = json.load(f)

                # Leer datos del polígono (opcional)
                geojson_path = actual_output_dir / "plot_polygon.geojson"
                geojson_data = None
                if geojson_path.exists():
                    with open(geojson_path, 'r', encoding='utf-8') as f:
                        geojson_data = json.load(f)

                # Leer reporte de validación (opcional — no lo genera el pipeline, puede no existir)
                validation_path = actual_output_dir / "validation_report.json"
                if validation_path.exists():
                    with open(validation_path, 'r', encoding='utf-8') as f:
                        validation = json.load(f)
                else:
                    # Sintetizar desde edificability.json
                    validation = {
                        "cadastral_ref": edificability.get("cadastral_ref"),
                        "soil_type": "DESCONOCIDO",
                        "surface_m2": edificability.get("surface_m2"),
                        "surface_source": "edificability",
                        "edificability_percent": edificability.get("edificability_percent", 33) / 100,
                        "max_buildable_m2": edificability.get("max_buildable_m2"),
                        "access_detected": False,
                        "linderos_mentioned": False,
                        "is_buildable": True,
                        "issues": [],
                        "method": "synthesized_from_edificability",
                    }

            except FileNotFoundError as e:
                return {"error": f"Archivo requerido no encontrado: {e.filename}"}
            except Exception as e:
                return {"error": f"Error leyendo archivos generados: {str(e)}"}

            # Detectar PDF escaneado (sin texto extraíble)
            if edificability.get('surface_m2') is None:
                return {
                    "error": "No se pudo extraer la superficie del PDF. "
                             "El documento parece ser una imagen escaneada sin texto seleccionable. "
                             "Usa la opción 'Extraer Datos con IA (Gemini)' durante la subida de la finca."
                }

            # (geojson_data y validation ya cargados arriba)

            # Extraer medidas del polígono
            if not geojson_data or 'geometry' not in geojson_data:
                # Sin polígono: usar valores por defecto
                coords = []
                vertices = 0
                ancho_m = largo_m = ((edificability.get('surface_m2') or 1000) ** 0.5)
                forma = "Irregular"
            else:
                coords = geojson_data['geometry']['coordinates'][0]
                vertices = len(coords) - 1  # Último punto repite el primero

            # Calcular medidas aproximadas
            if vertices >= 3:
                # Para formas simples, estimar ancho y largo
                if vertices == 4:  # Rectángulo/cuadrado
                    # Calcular distancias entre puntos consecutivos
                    distances = []
                    for i in range(len(coords)-1):
                        p1 = coords[i]
                        p2 = coords[(i+1) % (len(coords)-1)]
                        dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                        distances.append(dist)

                    # Tomar las dos distancias más largas como ancho y largo
                    distances.sort(reverse=True)
                    ancho_px = distances[0]
                    largo_px = distances[1] if len(distances) > 1 else distances[0]

                    # Estimar escala (asumiendo finca típica)
                    superficie_real = edificability.get('surface_m2') or 1000
                    area_px = geojson_data['properties'].get('area_px2', 100000)

                    if area_px > 0:
                        scale_factor = (superficie_real / area_px) ** 0.5
                        ancho_m = ancho_px * scale_factor
                        largo_m = largo_px * scale_factor
                    else:
                        ancho_m = largo_m = (superficie_real ** 0.5)
                else:
                    # Para formas irregulares, aproximar como cuadrado
                    lado_m = (edificability.get('surface_m2') or 1000 ** 0.5)
                    ancho_m = largo_m = lado_m
            else:
                ancho_m = largo_m = (edificability.get('surface_m2') or 1000 ** 0.5)

            # Determinar forma geométrica
            if vertices == 4:
                # Verificar si es aproximadamente cuadrado
                ratio = min(ancho_m, largo_m) / max(ancho_m, largo_m) if max(ancho_m, largo_m) > 0 else 1
                if ratio > 0.9:
                    forma = "Cuadrado"
                else:
                    forma = "Rectangular"
            elif vertices == 3:
                forma = "Triangular"
            else:
                forma = "Irregular"

            # Extraer datos de texto si existe
            texto_extraido = ""
            texto_path = actual_output_dir / "extracted_text.txt"
            if texto_path.exists():
                with open(texto_path, 'r', encoding='utf-8') as f:
                    texto_extraido = f.read()

            # Buscar referencia catastral en texto
            import re
            ref_pattern = r'(\d{14,20})'  # Patrón para referencias catastrales
            ref_match = re.search(ref_pattern, texto_extraido)
            referencia = ref_match.group(1) if ref_match else edificability.get('cadastral_ref', '')

            # Buscar superficie en texto
            superficie_pattern = r'(\d{1,6}(?:[.,]\d{1,2})?)\s*m²'
            superficie_match = re.search(superficie_pattern, texto_extraido)
            if superficie_match:
                superficie_texto = float(superficie_match.group(1).replace(',', '.'))
            else:
                superficie_texto = edificability.get('surface_m2', 0)

            # Extraer municipio del texto (búsqueda simple)
            municipios = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga", "Murcia", "Palma", "Bilbao", "Alicante"]
            municipio = ""
            for m in municipios:
                if m.lower() in texto_extraido.lower():
                    municipio = m
                    break

            # Generar información de orientación norte (estimada)
            # En planos catastrales españoles, normalmente norte está arriba
            orientacion_norte = "Arriba (estándar en planos catastrales)"

            # Preparar resultado completo
            resultado = {
                "referencia_catastral": referencia,
                "superficie_m2": superficie_texto,
                "municipio": municipio,
                "forma_geometrica": forma,
                "vertices": vertices,
                "dimensiones": {
                    "ancho_m": round(ancho_m, 2),
                    "largo_m": round(largo_m, 2)
                },
                "edificabilidad": {
                    "max_edificable_m2": edificability.get('max_buildable_m2', 0),
                    "porcentaje_edificable": edificability.get('buildable_percentage', 0)
                },
                "orientacion_norte": orientacion_norte,
                "coordenadas_poligono": coords,
                "archivos_generados": {
                    "plano_vectorizado": str(actual_output_dir / "contours_visualization.png"),
                    "plano_limpio": str(actual_output_dir / "contours_clean.png"),
                    "geojson": str(actual_output_dir / "plot_polygon.geojson")
                },
                "pipeline_completado": True
            }

            # Mejorar el plano limpio agregando medidas
            try:
                import cv2
                import numpy as np

                plano_limpio_path = actual_output_dir / "contours_clean.png"
                if plano_limpio_path.exists():
                    # Leer la imagen existente
                    img = cv2.imread(str(plano_limpio_path))

                    if img is not None:
                        # Agregar texto con medidas
                        height, width = img.shape[:2]

                        # Texto principal con dimensiones
                        texto_principal = f"{ancho_m:.1f}m × {largo_m:.1f}m"
                        cv2.putText(img, texto_principal, (width//2 - 100, height//2),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3, cv2.LINE_AA)

                        # Texto con superficie
                        texto_superficie = f"Superficie: {superficie_texto:.0f} m²"
                        cv2.putText(img, texto_superficie, (50, height - 100),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)

                        # Texto con referencia catastral
                        if referencia:
                            texto_ref = f"Ref: {referencia}"
                            cv2.putText(img, texto_ref, (50, height - 50),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)

                        # Agregar indicador de norte si es posible
                        cv2.putText(img, "NORTE", (width - 100, 50),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2, cv2.LINE_AA)
                        # Dibujar flecha hacia arriba
                        cv2.arrowedLine(img, (width - 50, 80), (width - 50, 30), (255, 0, 0), 3, tipLength=0.3)

                        # Guardar la imagen mejorada
                        cv2.imwrite(str(plano_limpio_path), img)
                        print(f"✅ Plano técnico mejorado con medidas: {plano_limpio_path}")

            except Exception as e:
                print(f"⚠️ No se pudo mejorar el plano técnico: {e}")

            return resultado

        finally:
            # Restaurar directorio original
            os.chdir(original_cwd)

    except Exception as e:
        return {"error": f"Error en extracción completa: {str(e)}"}

def get_ai_response(prompt: str, model_name: str = 'models/gemini-2.5-flash') -> str:
    """
    Función genérica para obtener respuesta de IA usando Gemini API.
    Compatible tanto con Streamlit como con scripts normales.
    """
    try:
        # Cargar variables de entorno (.env)
        load_dotenv()

        api_key = None

        # Intentar usar st.secrets SOLO si estamos en Streamlit
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                api_key = (st.secrets.get("GEMINI_API_KEY") or
                           st.secrets.get("GOOGLE_API_KEY"))
        except Exception:
            pass

        # Fallback a .env
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return "Error: No se encontró GEMINI_API_KEY ni GOOGLE_API_KEY en secrets/env"

        api_key = api_key.strip()
        return _gemini_rest(api_key, prompt, model=model_name)

    except Exception as e:
        error_msg = str(e).lower()

        if 'quota' in error_msg or '429' in error_msg:
            return "Error: Se ha agotado la cuota de la API de Gemini. Espera unos minutos."
        elif 'key' in error_msg or 'invalid' in error_msg or 'unauthorized' in error_msg:
            return "Error: La clave API de Gemini no es válida."
        elif 'network' in error_msg or 'connection' in error_msg:
            return "Error: Error de conexión a internet."
        else:
            return f"Error al procesar la solicitud: {str(e)}"

def analisis_finca_ia(datos_finca: dict) -> str:
    """
    Genera un análisis profesional de una finca usando IA.

    Args:
        datos_finca (dict): Diccionario con datos de la finca:
            - referencia_catastral: str
            - superficie_parcela: float
            - municipio: str
            - lat: float
            - lon: float

    Returns:
        str: Análisis generado por IA en formato Markdown
    """
    try:
        # Extraer datos del diccionario
        ref = datos_finca.get('referencia_catastral', 'No especificada')
        m2 = datos_finca.get('superficie_parcela', 0)
        municipio = datos_finca.get('municipio', 'No especificado')
        lat = datos_finca.get('lat', 0)
        lon = datos_finca.get('lon', 0)

        # Construir prompt profesional
        prompt = f"""
Eres un arquitecto experto en análisis de parcelas.

Genera un informe técnico claro, preciso y accionable sobre la siguiente finca:

- Referencia catastral: {ref}
- Superficie: {m2} m²
- Municipio: {municipio}
- Coordenadas: {lat}, {lon}

Incluye:
1. Resumen ejecutivo
2. Análisis urbanístico básico
3. Oportunidades y riesgos
4. Propuesta de uso óptimo
5. Estimación de edificabilidad
6. Recomendaciones arquitectónicas
7. Próximos pasos sugeridos

Formato: Markdown, con títulos y viñetas.
"""

        # Cargar API key
        _api_key = None
        try:
            import streamlit as _st
            if hasattr(_st, "secrets"):
                _api_key = _st.secrets.get("GEMINI_API_KEY") or _st.secrets.get("GOOGLE_API_KEY")
        except Exception:
            pass
        if not _api_key:
            _api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not _api_key:
            return "Error: No se encontró GEMINI_API_KEY ni GOOGLE_API_KEY en secrets/env"

        return _gemini_rest(_api_key.strip(), prompt)

    except Exception as e:
        error_msg = str(e).lower()

        if 'quota' in error_msg or '429' in error_msg:
            return "Error: Se ha agotado la cuota de la API de Gemini. Espera unos minutos."
        elif 'key' in error_msg or 'invalid' in error_msg or 'unauthorized' in error_msg:
            return "Error: La clave API de Gemini no es válida."
        elif 'network' in error_msg or 'connection' in error_msg:
            return "Error: Error de conexión a internet."
        else:
            return f"Error al generar análisis: {str(e)}"

def generar_diseno_ia(finca: FincaMVP) -> dict:
    """
    Genera un diseño de vivienda usando IA basado en la finca proporcionada.
    
    Args:
        finca: Objeto FincaMVP con los datos de la finca
        
    Returns:
        dict: Diseño generado con estructura específica
    """
    # Construir el prompt con los datos de la finca
    finca_data = finca.a_dict()
    solar_virtual = finca.solar_virtual
    superficie_edificable = finca.superficie_edificable
    
    servicios_info = ""
    if finca.servicios.get("alcantarillado") is False:
        servicios_info += " - No hay alcantarillado: sugerir fosa séptica.\n"
    if finca.servicios.get("luz") is False:
        servicios_info += " - No hay luz: sugerir placas solares.\n"
    if finca.servicios.get("agua") is False:
        servicios_info += " - No hay agua: sugerir depósito.\n"
    
    prompt = f"""Basándote en esta finca, genera un diseño de vivienda.

Datos de la finca:
{json.dumps(finca_data, indent=2, ensure_ascii=False)}

Solar virtual: {solar_virtual}
Superficie edificable: {superficie_edificable} m²

Servicios disponibles:
{servicios_info}

Reglas estrictas:
- La suma de m2 de todas las estancias NO puede superar {superficie_edificable} m².
- Si supera, reduce automáticamente los m2.
- Máximo 2 plantas.
- Planta 0: zonas de día (salón, cocina, comedor)
- Planta 1: dormitorios y baños
- Incluye extras basados en servicios faltantes.

Devuelve SOLO un JSON con esta estructura exacta:
{{
  "total_m2": number,
  "plantas": number,
  "estancias": [
    {{
      "nombre": "string",
      "m2": number,
      "planta": number,
      "tipo": "dia|noche|servicio"
    }}
  ],
  "extras": {{
    "garaje": bool,
    "piscina": bool,
    "terraza": bool
  }}
}}

No incluyas comentarios, texto adicional ni campos inventados.
"""
    
    # Llamar a la IA
    response = get_ai_response(prompt)
    
    # Verificar si la respuesta es un error
    if response.startswith("Error:"):
        raise ValueError(f"Error de la IA: {response}")
    
    # Limpiar la respuesta
    if response.startswith('```json'):
        response = response[7:]
    if response.startswith('```'):
        response = response[3:]
    if response.endswith('```'):
        response = response[:-3]
    response = response.strip()
    
    # Parsear JSON
    try:
        resultado = json.loads(response)
        return resultado
    except json.JSONDecodeError as e:
        raise ValueError(f"Error al parsear JSON de la IA: {e}. Respuesta: {response}")

from dotenv import load_dotenv
import os

def generate_text(prompt: str, model_name: str = 'llama-3.3-70b-versatile') -> str:
    """
    Genera texto usando Groq, compatible con Streamlit y con scripts.
    """
    try:
        # Cargar .env
        load_dotenv()

        api_key = None

        # Intentar usar st.secrets SOLO si estamos en Streamlit
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]
        except:
            pass

        # Fallback a .env
        if not api_key:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return "Error: No se encontró la clave GROQ_API_KEY en secrets de Streamlit ni GROQ_API_KEY en .env"

        # Configurar cliente Groq
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
        )

        if response and response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "Error: No se pudo generar una respuesta válida"

    except Exception as e:
        error_msg = str(e).lower()

        if 'quota' in error_msg or '429' in error_msg:
            return "Error: Se ha agotado la cuota de la API de Groq. Espera unos minutos."
        elif 'key' in error_msg or 'invalid' in error_msg or 'unauthorized' in error_msg:
            return "Error: La clave API de Groq no es válida."
        elif 'network' in error_msg or 'connection' in error_msg:
            return "Error: Error de conexión a internet."
        else:
            return f"Error al procesar la solicitud: {str(e)}"


# ── Tab IA: plan_vivienda y generate_sketch_svg ──────────────────────────────

def plan_vivienda(superficie_m2: float, num_habitaciones: int) -> dict:
    """
    Genera una distribucion de vivienda simple usando Groq.
    Devuelve dict con 'descripcion', 'habitaciones' (lista de dicts), 'total_m2'.
    """
    edificable = round(superficie_m2 * 0.33, 1)
    prompt = (
        f"Genera una distribucion de vivienda unifamiliar para una parcela de {superficie_m2} m2 "
        f"(edificable {edificable} m2) con {num_habitaciones} dormitorios. "
        "Responde SOLO con JSON con esta estructura exacta, sin texto adicional:\n"
        '{"descripcion":"texto breve","total_m2":number,"habitaciones":['
        '{"nombre":"string","m2":number,"planta":0}]}'
    )
    try:
        raw = generate_text(prompt)
        import json as _j, re as _re
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if match:
            data = _j.loads(match.group())
            habs = data.get("habitaciones", [])
            habs = [{"nombre": h.get("nombre") or h.get("name", "Estancia"),
                     "m2": h.get("m2") or h.get("area", 10),
                     "planta": h.get("planta", 0)} for h in habs]
            return {
                "descripcion": data.get("descripcion", ""),
                "habitaciones": habs,
                "total_m2": data.get("total_m2", edificable),
            }
    except Exception:
        pass
    # Fallback determinista si Groq falla
    m2_hab = round(edificable / (num_habitaciones + 3), 1)
    habs_fallback = [{"nombre": f"Dormitorio {i+1}", "m2": m2_hab, "planta": 1}
                     for i in range(num_habitaciones)]
    habs_fallback += [
        {"nombre": "Salon-Comedor", "m2": round(m2_hab * 2, 1), "planta": 0},
        {"nombre": "Cocina",        "m2": m2_hab,                "planta": 0},
        {"nombre": "Bano",          "m2": round(m2_hab * 0.6, 1),"planta": 0},
    ]
    return {
        "descripcion": f"Vivienda de {num_habitaciones} dormitorios en {edificable} m2 edificables.",
        "habitaciones": habs_fallback,
        "total_m2": edificable,
    }


def generate_sketch_svg(habitaciones: list, total_m2: float) -> str:
    """Genera un SVG simple de boceto de planta a partir de la lista de habitaciones."""
    if not habitaciones:
        return '<svg width="400" height="100"><text x="10" y="50" font-size="14">Sin habitaciones</text></svg>'

    cols = 3
    cell_w, cell_h, pad = 120, 80, 8
    rows = (len(habitaciones) + cols - 1) // cols
    svg_w = cols * (cell_w + pad) + pad
    svg_h = rows * (cell_h + pad) + pad + 30

    colors = ["#DBEAFE", "#D1FAE5", "#FEF3C7", "#FCE7F3", "#EDE9FE", "#FFEDD5"]
    rects = []
    for i, h in enumerate(habitaciones):
        col = i % cols
        row = i // cols
        x = pad + col * (cell_w + pad)
        y = 30 + pad + row * (cell_h + pad)
        color = colors[i % len(colors)]
        nombre = str(h.get("nombre", ""))[:18]
        m2_val = h.get("m2", 0)
        rects.append(
            f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
            f'fill="{color}" stroke="#374151" stroke-width="1.5" rx="4"/>'
            f'<text x="{x+cell_w//2}" y="{y+cell_h//2-6}" font-size="11" '
            f'text-anchor="middle" fill="#1F2937" font-weight="600">{nombre}</text>'
            f'<text x="{x+cell_w//2}" y="{y+cell_h//2+12}" font-size="10" '
            f'text-anchor="middle" fill="#6B7280">{m2_val} m2</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:#F9FAFB;border-radius:8px;">'
        f'<text x="{svg_w//2}" y="20" font-size="13" text-anchor="middle" '
        f'fill="#374151" font-weight="700">Boceto: {total_m2:.0f} m2 edificables</text>'
        + "".join(rects) +
        "</svg>"
    )