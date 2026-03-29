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


def get_tipo_suelo_desde_coordenadas(lat: float, lon: float) -> str:
    """
    Consulta el Catastro para determinar si una parcela es urbana o rústica.
    Devuelve: 'Urbana', 'Rústica', o 'Desconocida' si falla.
    Fallback siempre a 'Desconocida' — nunca lanza excepción.
    """
    try:
        import requests
        from xml.etree import ElementTree as ET

        url = (
            "https://ovc.catastro.meh.es/ovcservweb/"
            "ovcswlocalizacionrc/ovccoordenadas.asmx/Consulta_RCCOOR"
        )
        params = {
            "Coordenada_X": str(lon),
            "Coordenada_Y": str(lat),
            "SRS": "EPSG:4326"
        }
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return "Desconocida"

        root = ET.fromstring(resp.text)
        ns = {"c": "http://www.catastro.meh.es/"}

        # Buscar naturaleza en ldt (dirección devuelta)
        ldt = root.find(".//c:ldt", ns)
        if ldt is not None and ldt.text:
            texto = ldt.text.upper()
            if "RUSTIC" in texto or "POLIGONO" in texto:
                return "Rústica"
            elif "CALLE" in texto or "AVENIDA" in texto or "PLAZA" in texto or "PASEO" in texto or "VIA" in texto:
                return "Urbana"

        # Fallback: inspeccionar pc2 (referencia catastral parte 2)
        pc2 = root.find(".//c:pc2", ns)
        if pc2 is not None and pc2.text:
            rc_part = pc2.text.strip().upper()
            if rc_part.startswith("R") or len(rc_part) == 7:
                return "Rústica"
            elif rc_part.startswith("U"):
                return "Urbana"

        return "Desconocida"

    except Exception:
        return "Desconocida"