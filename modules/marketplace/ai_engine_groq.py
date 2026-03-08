import os
from groq import Groq
from dotenv import load_dotenv
import streamlit as st
from typing import List, Optional

# Cargar variables de entorno
load_dotenv()

def _load_api_key() -> Optional[str]:
    """Obtiene y limpia la clave GROQ de .env o st.secrets."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key and hasattr(st, "secrets"):
        api_key = st.secrets.get("GROQ_API_KEY")
    if api_key:
        api_key = api_key.strip()
        return api_key
    return None

def generate_project_report(prompt: str) -> str:
    api_key = _load_api_key()
    if not api_key: return "❌ Error: API Key"

    try:
        client = Groq(api_key=api_key)
        
        # PROMPT REFORZADO: Le decimos que el plano es OBLIGATORIO y el texto corto
        full_prompt = f"""
        {prompt}
        
        INSTRUCCIONES TÉCNICAS:
        1. Resumen: Máximo 200 palabras.
        2. PLANO ASCII: Al final, es OBLIGATORIO dibujar un esquema ASCII de la planta.
        Usa solo: +, -, |, [ ] para ventanas y ( ) para puertas.
        No te cortes, termina el dibujo.
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": "Eres un arquitecto que entrega informes directos con planos ASCII integrados."},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.3, # Bajamos temperatura para evitar que divague
            max_tokens=2048, # Aseguramos espacio suficiente
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"❌ Error: {str(exc)}"

def _generate_text_gemini(prompt: str, max_tokens: int = 500) -> str:
    """Fallback: genera texto usando Gemini REST API directa cuando GROQ falla."""
    try:
        import requests as _req
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key and hasattr(st, "secrets"):
            gemini_key = st.secrets.get("GEMINI_API_KEY")
        if not gemini_key:
            return "Error de configuración: sin API key disponible."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key.strip()}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = _req.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Error: {e}"

def generate_text(prompt: str, max_tokens: int = 500) -> str:
    """Versión para chats rápidos o resúmenes usando el modelo 8B. Fallback a Gemini si GROQ falla."""
    api_key = _load_api_key()
    if api_key:
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.2
            )
            return response.choices[0].message.content.strip()
        except Exception:
            pass  # Fallback to Gemini
    return _generate_text_gemini(prompt, max_tokens)

def generate_ascii_plan(prompt: str, max_tokens: int = 1000) -> str:
    """Generador de planos ASCII optimizado para Llama 3.1 8B (Gratis) - PLANO OBLIGATORIO"""
    api_key = _load_api_key()
    if not api_key: return "❌ Error de API Key"

    try:
        client = Groq(api_key=api_key)

        # PROMPT ULTRA-REFORZADO: PLANO OBLIGATORIO SIN EXCUSAS
        reinforced_prompt = f"""
        DIBUJA UN PLANO ASCII COMPLETO PARA: {prompt}

        REGLAS OBLIGATORIAS:
        - Usa SOLO caracteres ASCII: + - | [ ] ( )
        - + para esquinas, - para paredes horizontales, | para verticales
        - [ ] para ventanas, ( ) para puertas
        - Dibuja UNA habitación como mínimo
        - NO escribas texto explicativo, SOLO el dibujo
        - El plano DEBE ser visible y completo
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "ERES UN ARQUITECTO QUE SOLO DIBUJA PLANOS ASCII. "
                        "TU ÚNICA FUNCIÓN ES DIBUJAR PLANOS. "
                        "SIEMPRE RESPONDES CON UN DIBUJO ASCII COMPLETO. "
                        "NO ESCRIBES TEXTO, NO DAS EXPLICACIONES. "
                        "SOLO DIBUJAS EL PLANO USANDO: + - | [ ] ( )"
                    )
                },
                {"role": "user", "content": reinforced_prompt}
            ],
            temperature=0.1, # Temperatura muy baja para consistencia
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content.strip()

        # Verificación: Si no tiene caracteres de dibujo, forzamos un plano básico
        if not any(char in result for char in ['+', '-', '|', '[', ']', '(', ')']):
            result = """
+-----+
|     |
|  () |
|     |
+-----+
""".strip()

        return result
    except Exception as e:
        return f"Error generando plano: {e}"

def generate_technical_summary(datos_finca: dict, texto_pdf: str) -> str:
    """Genera un resumen usando datos validados + texto del PDF"""
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."
    
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""
        Eres un Arquitecto experto. Genera un informe técnico basado en:
        DATOS VALIDADOS:
        - Superficie: {datos_finca.get('surface_m2')} m2
        - Suelo: {datos_finca.get('soil_type')}
        - Edificabilidad: {datos_finca.get('max_buildable_m2')} m2
        
        CONTEXTO DEL PDF:
        {texto_pdf[:2000]}
        
        INSTRUCCIONES:
        1. Resume el estilo y materiales.
        2. Analiza si el proyecto cabe en los {datos_finca.get('max_buildable_m2')} m2 edificables.
        3. Si el suelo es RUSTICO, añade una advertencia legal.
        """
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generando resumen técnico: {e}"

def generate_land_analysis(validados: dict, ocr_text: str):
    """Genera un análisis técnico legal basado en datos contrastados"""
    from groq import Groq
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    
    # Construimos el contexto quirúrgico
    ctx = f"""
    FICHA TÉCNICA VERIFICADA:
    - Referencia Catastral: {validados.get('cadastral_ref')}
    - Superficie: {validados.get('surface_m2')} m2
    - Clasificación: {validados.get('soil_type')}
    - Edificabilidad: {validados.get('max_buildable_m2')} m2
    - Acceso Vial: {'Sí' if validados.get('access_detected') else 'No'}
    """

    prompt = f"{ctx}\n\nAnaliza la viabilidad técnica de esta finca usando el siguiente texto legal como soporte:\n{ocr_text[:2000]}"
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generando análisis de terreno: {e}"

def generate_validated_analysis(datos_json: dict, ocr_context: str):
    """
    Usa Llama 3.1 para redactar un informe basado en datos ya extraídos.
    Gasta el mínimo de tokens posible.
    """
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."
    
    try:
        client = Groq(api_key=api_key)
        
        # Prompt ultra-optimizado para Groq Gratis
        prompt = f"""
        SÉ BREVE Y PROFESIONAL.
        DATOS TÉCNICOS:
        - Finca: {datos_json.get('cadastral_ref')}
        - Superficie: {datos_json.get('surface_m2')} m2
        - Tipo Suelo: {datos_json.get('soil_type')}
        - Edificabilidad: {datos_json.get('max_buildable_m2')} m2
        - Acceso: {'Sí' if datos_json.get('access_detected') else 'No'}

        TAREA:
        1. Evalúa la viabilidad (Si es {datos_json.get('soil_type')} y tiene acceso).
        2. Explica qué significa esa edificabilidad para un comprador.
        3. Menciona si hay problemas: {", ".join(datos_json.get('issues', []))}
        """

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", # El más rápido y ligero
            temperature=0.2,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error generando análisis validado: {e}"

def get_expert_analysis(plot_data):
    """Analiza los datos validados del JSON sin leer todo el PDF"""
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."
    
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""
        Actúa como Arquitecto. Analiza estos datos técnicos:
        - Superficie: {plot_data.get('surface_m2')} m2
        - Clasificación: {plot_data.get('soil_type')}
        - Edificabilidad: {plot_data.get('max_buildable_m2')} m2
        - Problemas detectados: {", ".join(plot_data.get('issues', ['Ninguno']))}
        
        Genera un resumen ejecutivo de 3 puntos sobre la viabilidad de construcción.
        """
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1 # Muy bajo para que no invente nada
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error generando análisis experto: {e}"

def generar_analisis_ligero(datos_json):
    """Genera informe técnico usando Llama 3.1 8B (Gratis y Rápido)"""
    from groq import Groq
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    
    # Solo enviamos lo esencial
    prompt = f"""
    Como Arquitecto, analiza esta finca:
    - Superficie: {datos_json.get('surface_m2')} m2
    - Suelo: {datos_json.get('soil_type')}
    - Máximo Construible: {datos_json.get('max_buildable_m2')} m2
    - Incidencias: {", ".join(datos_json.get('issues', []))}

    Genera un dictamen de viabilidad en 3 frases muy breves.
    """
    
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return completion.choices[0].message.content

def generate_simple_floorplan(project_title: str):
    """Genera un esquema de planta ASCII puro para atraer al cliente."""
    from groq import Groq
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    prompt = f"""
    Dibuja un plano de planta ASCII simplificado para un proyecto llamado '{project_title}'.
    Usa este estilo:
    +-------+-------+
    | Hab 1 | Cocina|
    | [ ]   |  ( )  |
    +-------+-------+
    | Salón         |
    +---------------+

    Instrucciones:
    - Solo el dibujo ASCII.
    - Máximo 15 líneas.
    - Incluye: salón, cocina y al menos 2 habitaciones.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, # Muy bajo para que no se desvíe
        max_tokens=800
    )
    return response.choices[0].message.content

def generate_project_blueprint(text_context: str, project_name: str) -> str:
    """Extrae la distribución real de la memoria y la dibuja en ASCII."""
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        # Este prompt obliga a la IA a buscar datos numéricos en el texto
        prompt = f"""
        Eres un Arquitecto Analista. Basado en la memoria técnica del proyecto '{project_name}':
        1. Busca la distribución de habitaciones y sus m2.
        2. Dibuja un plano de planta ASCII técnico (Planta Principal).
        3. Usa este estilo: +---+ para muros, [ ] ventanas, ( ) puertas.
        4. Escribe el nombre de cada zona y su área aproximada dentro del dibujo.

        TEXTO DE LA MEMORIA:
        {text_context[:3000]} # Le pasamos el inicio de la memoria donde suelen estar los datos

        SOLO devuelve el dibujo ASCII, sin introducciones.
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generando blueprint: {e}"

def extract_area_table(text_context: str) -> str:
    """Extrae la tabla de superficies reales de la memoria."""
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        prompt = f"""
        Analiza esta memoria técnica y busca el 'Cuadro de Superficies' o 'Programa de Necesidades'.
        Extrae SOLO una lista con: Estancia y m2 útiles.
        Texto: {text_context[:4000]}
        Responde en formato tabla simple.
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error extrayendo tabla de áreas: {e}"

def generate_blueprint_from_data(areas_text: str) -> str:
    """Dibuja el plano ASCII basado estrictamente en las áreas extraídas."""
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        prompt = f"""
        Eres un delineante. Dibuja un PLANO ASCII de la planta principal usando estos datos:
        {areas_text}

        Instrucciones:
        - Usa +---+ para muros, | para paredes, [ ] ventanas.
        - El salón debe verse más grande que los dormitorios.
        - Escribe el nombre de la estancia dentro del dibujo.
        - SOLO el dibujo ASCII.
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generando plano desde datos: {e}"

def generate_ascii_plan_only(project_data: str) -> str:
    """Función dedicada exclusivamente a dibujar el plano ASCII, sin texto adicional.

    Esto evita que la IA se agote generando párrafos largos y se enfoque solo en el dibujo.
    """
    api_key = _load_api_key()
    if not api_key:
        return "❌ Error: Configura GROQ_API_KEY."

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        # TRUNCAR el texto OCR para evitar límite de tokens (6000 máximo)
        # Tomamos solo los primeros 2000 caracteres que contienen la info esencial
        truncated_data = project_data[:2000] if len(project_data) > 2000 else project_data

        prompt = f"""
        Eres un delineante especializado en planos ASCII. Tu ÚNICA tarea es dibujar el plano de la planta.

        DATOS DEL PROYECTO (truncados para optimización):
        {truncated_data}

        INSTRUCCIONES PARA EL DIBUJO:
        - Usa caracteres ASCII: +---+ para muros exteriores, | para paredes interiores
        - [ ] para ventanas, ( ) para puertas
        - Escribe el nombre de cada estancia DENTRO del rectángulo correspondiente
        - El salón/comedor debe ser el espacio más grande
        - Cocina junto al salón si es posible
        - Dormitorios en la parte trasera
        - Baños junto a dormitorios
        - NO escribas ningún texto explicativo, SOLO el dibujo ASCII
        - El dibujo debe ser completo y legible

        EJEMPLO DE FORMATO:
        +-------------------+
        |      SALON        |
        |                   |
        +---+---+---+---+---+
        |KIT|   |DOR|   |BAÑ|
        +---+---+---+---+---+
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Baja temperatura para consistencia
            max_tokens=800   # Suficiente para el dibujo, no para texto largo
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generando plano ASCII: {e}"