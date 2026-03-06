import io
import zipfile
from datetime import datetime


def generar_paquete_descarga(titulo_proyecto: str) -> bytes:
    """Genera un paquete ZIP simulado con los documentos clave del proyecto.

    Incluye (simulados): 'Planos_CAD.dxf', 'Memoria_Proyecto.pdf', 'Certificado_Energetico.pdf'.
    Devuelve los bytes del ZIP para descarga.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        base_name = f"{titulo_proyecto.replace(' ', '_')}_{timestamp}"

        # Simular archivos con contenido de texto mínimo
        planos_content = b"%DXF Simulated content for project: " + titulo_proyecto.encode('utf-8')
        memoria_content = b"PDF Simulated Memoria for project: " + titulo_proyecto.encode('utf-8')
        certificado_content = b"PDF Simulated Certificado Energetico for project: " + titulo_proyecto.encode('utf-8')

        z.writestr(f"{base_name}/Planos_CAD.dxf", planos_content)
        z.writestr(f"{base_name}/Memoria_Proyecto.pdf", memoria_content)
        z.writestr(f"{base_name}/Certificado_Energetico.pdf", certificado_content)

    buf.seek(0)
    return buf.getvalue()
