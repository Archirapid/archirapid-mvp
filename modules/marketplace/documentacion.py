# modules/marketplace/documentacion.py

from .ai_engine import get_ai_response

def generar_memoria_constructiva(plan_json, superficie_finca):
    """
    Genera una memoria constructiva básica para el MVP.
    Incluye descripción de estancias, superficies y consideraciones generales.

    Args:
        plan_json: Plan de vivienda con habitaciones y garage
        superficie_finca: Superficie total de la finca en m²

    Returns:
        str: Texto de la memoria constructiva
    """
    # Calcular total si no viene en el JSON
    total = plan_json.get("total_m2")
    if total is None:
        total = sum(float(h.get("m2", 0)) for h in plan_json.get("habitaciones", []))
        if "garage" in plan_json:
            total += float(plan_json["garage"].get("m2", 0))

    # Lista de estancias
    estancias = []
    for h in plan_json.get("habitaciones", []):
        nombre = h.get("nombre", "Estancia")
        m2 = h.get("m2", 0)
        estancias.append(f"- {nombre}: {m2} m²")

    if "garage" in plan_json:
        gm2 = plan_json["garage"].get("m2", 0)
        estancias.append(f"- Garage: {gm2} m²")

    estancias_texto = "\n".join(estancias)

    memoria = f"""
MEMORIA CONSTRUCTIVA (MVP - ARCHIRAPID)

1. DATOS GENERALES
- Superficie de la finca: {superficie_finca:.1f} m²
- Máximo construible (33%): {superficie_finca*0.33:.1f} m²
- Superficie total proyectada: {total:.1f} m²

2. DISTRIBUCIÓN DE ESTANCIAS
{estancias_texto}

3. CONSIDERACIONES TÉCNICAS
- Cimentación: Losa de hormigón armado o zapatas corridas (a definir según estudio geotécnico)
- Estructura: Pórticos de hormigón armado o entramado metálico/madera (según material elegido)
- Altura libre: 2.6 m recomendada por planta
- Cubierta: Teja cerámica o similar, con aislamiento térmico
- Fachada: Bloque de hormigón o ladrillo caravista con aislamiento

4. INSTALACIONES
- Saneamiento: Red de aguas residuales y pluviales
- Electricidad: Instalación completa con puntos de luz, tomas y protecciones
- Climatización: Sistema básico de calefacción (opcional aire acondicionado)
- Agua: Red de distribución con contador general

5. ACABADOS Y MATERIALES
- Suelos: Gres cerámico o parquet flotante
- Revestimientos: Pintura plástica lisa en paredes y techos
- Carpintería: Puertas y ventanas de PVC o aluminio con rotura de puente térmico
- Materiales: A especificar en fase de proyecto básico y ejecución

6. NORMATIVA APLICABLE
- Código Técnico de la Edificación (CTE)
- Normativa urbanística municipal
- Reglamento de Instalaciones Térmicas (RITE)
- Normativa de accesibilidad (UNE 170001)

NOTA: Esta memoria es orientativa para el MVP. Se recomienda contratar servicios profesionales
de arquitectura y dirección de obra para el desarrollo completo del proyecto.
"""

    return memoria


def generar_presupuesto_estimado(plan_json, coste_m2=900.0):
    """
    Genera un presupuesto estimado básico para el MVP.

    Args:
        plan_json: Plan de vivienda
        coste_m2: Coste orientativo por m² construido (€)

    Returns:
        dict: Detalles del presupuesto
    """
    # Calcular superficie total
    total = plan_json.get("total_m2")
    if total is None:
        total = sum(float(h.get("m2", 0)) for h in plan_json.get("habitaciones", []))
        if "garage" in plan_json:
            total += float(plan_json["garage"].get("m2", 0))

    # Cálculos básicos
    subtotal_obra = total * coste_m2
    honorarios_profesionales = subtotal_obra * 0.12  # 12% aproximado
    impuestos = (subtotal_obra + honorarios_profesionales) * 0.10  # 10% IVA aproximado
    imprevistos = subtotal_obra * 0.05  # 5% imprevistos
    total_estimado = subtotal_obra + honorarios_profesionales + impuestos + imprevistos

    return {
        "coste_m2": coste_m2,
        "superficie_total": total,
        "subtotal_obra": subtotal_obra,
        "honorarios_profesionales": honorarios_profesionales,
        "impuestos": impuestos,
        "imprevistos": imprevistos,
        "total_estimado": total_estimado,
        "nota": "Presupuesto orientativo para MVP. No incluye terrenos, licencias ni costes reales de materiales."
    }


def generar_plano_cad(plan_json):
    """
    Genera un plano CAD en formato DXF a partir del JSON del plan de vivienda.
    Utiliza IA para crear un plano técnico con distribución, cotas y etiquetas.

    Args:
        plan_json: JSON con habitaciones, garage y total_m2

    Returns:
        str: Contenido DXF válido como string
    """
    prompt = f"""
Genera un plano CAD en formato DXF a partir de este JSON de vivienda:

{json.dumps(plan_json, indent=2)}

Requisitos del plano DXF:
- Dibuja el contorno de la parcela (100x100 m como referencia base).
- Coloca cada habitación como un rectángulo proporcional a sus m².
- Añade cotas (dimensiones en metros) para cada estancia.
- Etiqueta cada estancia con su nombre y superficie (ej: "Dormitorio 1: 15.5 m²").
- Si existe garage, dibújalo aparte con su etiqueta correspondiente.
- Añade símbolos básicos de puertas (líneas cortas perpendiculares) y ventanas (líneas cortas paralelas).
- Usa capas DXF apropiadas: "Parcela", "Habitaciones", "Garage", "Cotas", "Etiquetas".
- Devuelve SOLO el contenido DXF válido, sin explicaciones adicionales.
- El DXF debe ser compatible con AutoCAD/LibreCAD.

Ejemplo de estructura DXF esperada:
0
SECTION
2
HEADER
0
ENDSEC
0
SECTION
2
TABLES
0
ENDSEC
0
SECTION
2
BLOCKS
0
ENDSEC
0
SECTION
2
ENTITIES
[Aquí van las entidades: LINE, TEXT, DIMENSION, etc.]
0
ENDSEC
0
EOF
"""

    # Llamada a IA para generar el DXF
    dxf_content = get_ai_response(prompt)

    # Limpiar respuesta (remover posibles explicaciones adicionales)
    # Buscar el inicio de SECTION y el final EOF
    start_idx = dxf_content.find("0\nSECTION")
    end_idx = dxf_content.rfind("0\nEOF")

    if start_idx != -1 and end_idx != -1:
        dxf_content = dxf_content[start_idx:end_idx+5]  # +5 para incluir "0\nEOF"

    return dxf_content