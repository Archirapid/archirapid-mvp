"""
matching_engine.py
Motor de matching por zona para ArchiRapid.
Conecta clientes con profesionales (constructores/estudiantes)
de la misma provincia que el proyecto/finca.
"""
import json
import streamlit as st
from modules.marketplace.utils import db_conn

SERVICIOS_LABELS = {
    "visado":         "Visado de proyecto",
    "direccion_obra": "Dirección de obra",
    "supervision":    "Supervisión / revisión",
    "consulta":       "Consulta técnica",
}


def get_profesionales_por_provincia(provincia: str, servicio: str = None) -> list:
    """
    Devuelve hasta 5 profesionales que cubren la provincia indicada
    y tienen tarifas activas para el servicio solicitado (o cualquiera).

    Busca en service_providers via provincias_cobertura (JSON text)
    y también via service_area (texto libre) como fallback.
    Compatible SQLite (local) y PostgreSQL (producción).
    """
    if not provincia:
        return []

    patron = f"%{provincia}%"

    try:
        conn = db_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    sp.id,
                    sp.name,
                    sp.email,
                    sp.specialty,
                    sp.address,
                    sp.service_area,
                    t.servicio,
                    t.precio,
                    t.descripcion
                FROM service_providers sp
                LEFT JOIN tarifas_profesionales t
                    ON t.email = sp.email AND t.activo = 1
                WHERE sp.active = 1
                  AND (
                      sp.provincias_cobertura LIKE ?
                      OR sp.service_area LIKE ?
                  )
                ORDER BY sp.id, t.servicio
                LIMIT 20
            """, (patron, patron))
            rows = cur.fetchall()
        finally:
            conn.close()

        # Agrupar por profesional con todas sus tarifas
        profesionales: dict = {}
        for row in rows:
            sp_id, nombre, email, especialidad, direccion, area, \
                serv, precio, desc_tarifa = (
                    row[0], row[1], row[2], row[3], row[4],
                    row[5], row[6], row[7], row[8]
                )

            if sp_id not in profesionales:
                profesionales[sp_id] = {
                    "id":           sp_id,
                    "nombre":       nombre or "Profesional ArchiRapid",
                    "email":        email,
                    "especialidad": especialidad,
                    "ciudad":       direccion,
                    "service_area": area,
                    "foto_url":     None,
                    "tarifas":      [],
                }

            if serv and precio is not None:
                # Filtrar por servicio si se especificó uno
                if servicio is None or serv == servicio:
                    profesionales[sp_id]["tarifas"].append({
                        "servicio":    serv,
                        "label":       SERVICIOS_LABELS.get(serv, serv),
                        "precio":      precio,
                        "descripcion": desc_tarifa,
                    })

        return list(profesionales.values())[:5]

    except Exception:
        # Fallback silencioso — no romper el panel cliente
        return []


def get_ofertas_para_proyecto(plot_id: int, provincia: str) -> list:
    """
    Genera hasta 3 ofertas automáticas para un proyecto/finca concreto.
    Prioriza profesionales con más servicios activos en esa provincia.
    Registra las ofertas generadas para tracking admin.
    """
    if not provincia:
        return []

    profesionales = get_profesionales_por_provincia(provincia)

    # Ordenar por número de tarifas activas (más completo primero)
    profesionales_sorted = sorted(
        profesionales,
        key=lambda p: len(p["tarifas"]),
        reverse=True,
    )[:3]

    ofertas = []
    for prof in profesionales_sorted:
        ofertas.append({
            "profesional":           prof,
            "servicios_disponibles": prof["tarifas"],
            "provincia":             provincia,
            "plot_id":               plot_id,
        })
        _registrar_oferta(plot_id, prof["email"], provincia)

    return ofertas


def _registrar_oferta(plot_id: int, email_profesional: str, provincia: str):
    """Guarda en BD que se generó esta oferta — para analytics admin."""
    try:
        conn = db_conn()
        try:
            conn.execute("""
                INSERT INTO ofertas_matching
                (plot_id, email_profesional, provincia)
                VALUES (?, ?, ?)
            """, (plot_id, email_profesional, provincia))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # Fallo silencioso — no romper flujo principal


def actualizar_provincias_proveedor(email: str, provincias: list) -> bool:
    """
    Actualiza el array provincias_cobertura de un service_provider (guardado como JSON text).
    Llamar desde service_providers.py cuando el proveedor edita su perfil.
    """
    try:
        conn = db_conn()
        try:
            conn.execute("""
                UPDATE service_providers
                SET provincias_cobertura = ?
                WHERE email = ?
            """, (json.dumps(provincias), email))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False
