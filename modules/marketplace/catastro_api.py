import requests
import xml.etree.ElementTree as ET

def fetch_by_ref_catastral(ref_catastral: str) -> dict:
    """
    Obtiene datos reales del Catastro usando la referencia catastral (OVCCoordenadas).
    """
    ref1 = ref_catastral[:14]
    ref2 = ref_catastral[14:] if len(ref_catastral) > 14 else ""
    
    url = "http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx/Consulta_CPMRC"
    params = {
        "Provincia": "",
        "Municipio": "",
        "SRS": "EPSG:4326", # WGS84
        "RC": ref1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # Namespace map logic can be tricky with ElementTree, usually we can find by tag name
            # XML Structure: <consulta_coordenadas> <coordenadas> <coord> <geo> <lat> <lon>
            
            # Simple parsing (ignoring namespaces or using wildcard)
            ns = {"c": "http://www.catastro.meh.es/"}
            lat_node = root.find(".//c:ycen", ns)
            lon_node = root.find(".//c:xcen", ns)
            address_node = root.find(".//c:ldt", ns)
            
            if lat_node is not None and lon_node is not None:
                return {
                    "superficie_m2": 0, # OVCC no devuelve superficie en este endpoint ligero, requeriría scrapping o WMS
                    "ref_catastral": ref_catastral,
                    "ubicacion_geo": {
                        "lat": float(lat_node.text),
                        "lng": float(lon_node.text),
                        "municipio": "Detectado",
                        "direccion_completa": address_node.text if address_node is not None else "Dirección Catastral"
                    },
                    "nota_catastral_raw": {"fuente": "Sede Electrónica Catastro (OVCC)"},
                    "estado": "validado_oficial"
                }
    except Exception as e:
        print(f"Catastro API Error: {e}")
        
    # Fallback si falla la real (para que no rompa la demo)
    return {
        "superficie_m2": 0,
        "ref_catastral": ref_catastral,
        "ubicacion_geo": None,
        "estado": "error_api"
    }

def fetch_by_address(direccion: str, municipio: str = "Madrid") -> dict:
    """
    Busca referencia por dirección (calle/numero) - Más complejo, Stubeado por ahora.
    """
    return None