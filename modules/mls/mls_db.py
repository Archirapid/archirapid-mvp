"""
modules/mls/mls_db.py
Capa de acceso a BD para las 5 tablas MLS de ArchiRapid.

Patrón de conexión: src.db.get_conn() — WAL + timeout=15 + row_factory=sqlite3.Row
IDs: uuid.uuid4().hex — consistente con el resto del proyecto
"""
import uuid
import logging
from datetime import datetime, timezone

from src import db as _db

logger = logging.getLogger(__name__)

# Alias público para que mls_firma.py pueda obtener conexión directamente
_get_conn = _db.get_conn

# ─────────────────────────────────────────────────────────────────────────────
# ESTADOS VÁLIDOS — Apéndice B
# ─────────────────────────────────────────────────────────────────────────────

ESTADOS_FINCA_MLS: set = {
    "pendiente_validacion",              # creada, catastro aún no validado
    "validada_pendiente_aprobacion",     # catastro OK, admin aún no aprueba (no visible en mapa)
    "periodo_privado",                   # exclusividad privada antes del mercado abierto
    "publicada",                         # visible en mercado abierto y mapa
    "reserva_pendiente_confirmacion",    # cliente directo reservó, admin confirma en 48h
    "reservada",                         # colaboradora reservó, exclusiva 72h activa
    "cerrada",                           # operación cerrada con éxito
    "expirada",                          # reserva expirada sin operación
    "pausada",                           # listante pausó la finca temporalmente
    "eliminada",                         # borrado lógico por admin (nunca físico si hay transacciones)
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convierte sqlite3.Row a dict ordinario. Si row es None devuelve None."""
    if row is None:
        return None
    return dict(row)


def _now_utc() -> str:
    """ISO 8601 UTC. Usa timezone-aware para evitar DeprecationWarning en Python 3.12+."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ═════════════════════════════════════════════════════════════════════════════
# INMOBILIARIAS
# ═════════════════════════════════════════════════════════════════════════════

def get_inmo_by_email(email: str) -> dict | None:
    """Devuelve la inmobiliaria con ese email, o None si no existe."""
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM inmobiliarias WHERE email = ?",
            (email.strip().lower(),)
        )
        return _row_to_dict(cur.fetchone())
    except Exception as e:
        logger.error("get_inmo_by_email error: %s", e)
        return None
    finally:
        conn.close()


def get_inmo_by_id(inmo_id: str) -> dict | None:
    """Devuelve la inmobiliaria con ese id, o None si no existe."""
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM inmobiliarias WHERE id = ?",
            (inmo_id,)
        )
        return _row_to_dict(cur.fetchone())
    except Exception as e:
        logger.error("get_inmo_by_id error: %s", e)
        return None
    finally:
        conn.close()


def create_inmo(datos: dict, ip: str = None) -> str | None:
    """
    Inserta una nueva inmobiliaria en estado pendiente (activa=0).
    datos: dict con todos los campos del formulario extendido.
      Campos obligatorios: nombre, cif, email, password_hash
      Todos los demás son opcionales (None si vacío).
    Devuelve el inmo_id generado, o None si falla.
    """
    def _s(key: str, upper: bool = False, lower: bool = False) -> str | None:
        v = (datos.get(key) or "").strip()
        if not v:
            return None
        if upper:
            return v.upper()
        if lower:
            return v.lower()
        return v

    inmo_id = uuid.uuid4().hex
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO inmobiliarias
               (id, nombre, cif, email, password_hash,
                nombre_sociedad, nombre_comercial,
                telefono, telefono_secundario, telegram_contacto, web,
                direccion, localidad, provincia, codigo_postal, pais,
                contacto_nombre, contacto_cargo, contacto_email,
                contacto_telefono, contacto_telegram,
                factura_razon_social, factura_cif, factura_direccion,
                factura_email, iban, banco_nombre, banco_titular, email_login,
                plan, plan_activo, activa, ip_registro, created_at)
               VALUES (
                ?,?,?,?,?,
                ?,?,
                ?,?,?,?,
                ?,?,?,?,?,
                ?,?,?,
                ?,?,
                ?,?,?,
                ?,?,?,?,?,
                'ninguno',0,0,?,?)""",
            (
                inmo_id,
                (datos.get("nombre") or "").strip(),
                (datos.get("cif") or "").strip().upper(),
                (datos.get("email") or "").strip().lower(),
                datos.get("password_hash", ""),
                _s("nombre_sociedad"),
                _s("nombre_comercial"),
                _s("telefono"),
                _s("telefono_secundario"),
                _s("telegram_contacto"),
                _s("web"),
                _s("direccion"),
                _s("localidad"),
                _s("provincia"),
                _s("codigo_postal"),
                datos.get("pais") or "España",
                _s("contacto_nombre"),
                _s("contacto_cargo"),
                _s("contacto_email", lower=True),
                _s("contacto_telefono"),
                _s("contacto_telegram"),
                _s("factura_razon_social"),
                _s("factura_cif", upper=True),
                _s("factura_direccion"),
                _s("factura_email", lower=True),
                _s("iban", upper=True),
                _s("banco_nombre"),
                _s("banco_titular"),
                _s("email_login", lower=True),
                ip or datos.get("ip_registro") or "unknown",
                _now_utc(),
            )
        )
        conn.commit()
        return inmo_id
    except Exception as e:
        logger.error("create_inmo error: %s", e)
        raise  # propaga al caller para que muestre el error real en UI
    finally:
        conn.close()


def update_inmo_activa(inmo_id: str, activa: int) -> bool:
    """Activa (1) o suspende (0) una inmobiliaria. Llamado desde Intranet."""
    conn = _db.get_conn()
    try:
        conn.execute(
            "UPDATE inmobiliarias SET activa = ? WHERE id = ?",
            (int(activa), inmo_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_inmo_activa error: %s", e)
        return False
    finally:
        conn.close()


def update_inmo_plan(inmo_id: str, plan: str,
                     stripe_session_id: str) -> bool:
    """Actualiza plan y marca plan_activo=1 tras pago Stripe verificado."""
    conn = _db.get_conn()
    try:
        conn.execute(
            """UPDATE inmobiliarias
               SET plan = ?, plan_activo = 1, stripe_session_id = ?
               WHERE id = ?""",
            (plan, stripe_session_id, inmo_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_inmo_plan error: %s", e)
        return False
    finally:
        conn.close()


def update_inmo_firma(inmo_id: str, firma_hash: str,
                      firma_timestamp: str) -> bool:
    """Registra la firma digital del acuerdo de colaboración."""
    conn = _db.get_conn()
    try:
        conn.execute(
            """UPDATE inmobiliarias
               SET firma_hash = ?, firma_timestamp = ?
               WHERE id = ?""",
            (firma_hash, firma_timestamp, inmo_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_inmo_firma error: %s", e)
        return False
    finally:
        conn.close()


def get_inmos_pendientes() -> list:
    """
    Devuelve inmobiliarias pendientes de aprobación (activa=0).
    Usa SELECT * para incluir todos los campos extendidos (contacto, facturación, IBAN…)
    que el admin necesita revisar antes de aprobar.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM inmobiliarias
               WHERE activa = 0
               ORDER BY created_at DESC"""
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_inmos_pendientes error: %s", e)
        return []
    finally:
        conn.close()


def get_inmos_activas() -> list:
    """
    Devuelve inmobiliarias activas (activa=1).
    Incluye plan y datos de firma para Intranet.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM inmobiliarias WHERE activa = 1 ORDER BY created_at DESC"
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_inmos_activas error: %s", e)
        return []
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# FINCAS MLS
# ═════════════════════════════════════════════════════════════════════════════

# Columnas seguras para colaboradoras — NUNCA incluyen inmo_id
_COLS_COLABORADORA = (
    "id, secuencial, ref_codigo, catastro_ref, catastro_validada, "
    "catastro_lat, catastro_lon, catastro_direccion, catastro_municipio, "
    "titulo, descripcion_publica, notas_privadas, "
    "precio, superficie_m2, tipo_suelo, servicios, forma_solar, orientacion, "
    "comision_archirapid_pct, comision_colaboradora_pct, "
    "split_aceptado, estado, image_paths, precio_historial, "
    "dias_en_mercado_inicio, created_at, updated_at"
)

# Columnas mínimas para el mapa — NUNCA incluyen inmo_id
_COLS_MAPA = (
    "id, ref_codigo, titulo, precio, catastro_lat, catastro_lon, superficie_m2"
)


def create_finca(inmo_id: str, datos: dict) -> str | None:
    """
    Inserta una nueva finca MLS en estado pendiente_validacion.
    datos debe incluir: catastro_ref, titulo, descripcion_publica,
      precio, superficie_m2, comision_total_pct, comision_colaboradora_pct,
      comision_listante_pct, notas_privadas (opcional), image_paths (opcional)
    Devuelve finca_id o None si falla.
    """
    finca_id = uuid.uuid4().hex
    ahora = _now_utc()
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO fincas_mls
               (id, inmo_id, catastro_ref, titulo, descripcion_publica,
                notas_privadas, precio, superficie_m2,
                tipo_suelo, servicios, forma_solar, orientacion,
                comision_total_pct, comision_archirapid_pct,
                comision_colaboradora_pct, comision_listante_pct,
                split_aceptado, estado, image_paths,
                precio_historial, dias_en_mercado_inicio,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, 'pendiente_validacion', ?, ?, ?, ?, ?)""",
            (finca_id, inmo_id,
             datos.get("catastro_ref", "").strip(),
             datos.get("titulo", "").strip(),
             datos.get("descripcion_publica", "").strip(),
             datos.get("notas_privadas", ""),
             float(datos.get("precio", 0)),
             float(datos.get("superficie_m2", 0)),
             datos.get("tipo_suelo", "Urbana"),
             datos.get("servicios"),
             datos.get("forma_solar"),
             datos.get("orientacion"),
             float(datos.get("comision_total_pct", 0)),
             float(datos.get("comision_colaboradora_pct", 0)),
             float(datos.get("comision_listante_pct", 0)),
             int(datos.get("split_aceptado", 0)),
             datos.get("image_paths"),
             datos.get("precio_historial"),
             ahora,   # dias_en_mercado_inicio
             ahora,   # created_at
             ahora)   # updated_at
        )
        conn.commit()
        return finca_id
    except Exception as e:
        logger.error("create_finca error: %s", e)
        return None
    finally:
        conn.close()


def get_finca_by_id(finca_id: str) -> dict | None:
    """
    Devuelve la finca completa (con inmo_id).
    SOLO para uso interno/admin — NUNCA exponer a colaboradoras.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM fincas_mls WHERE id = ?",
            (finca_id,)
        )
        return _row_to_dict(cur.fetchone())
    except Exception as e:
        logger.error("get_finca_by_id error: %s", e)
        return None
    finally:
        conn.close()


def get_finca_sin_identidad_listante(finca_id: str) -> dict | None:
    """
    Devuelve la finca SIN inmo_id ni datos identificativos de la listante.
    Para uso exclusivo de colaboradoras.
    SELECT explícito — inmo_id NUNCA aparece.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_COLS_COLABORADORA} FROM fincas_mls WHERE id = ?",
            (finca_id,)
        )
        result = _row_to_dict(cur.fetchone())
        # Guardia defensiva: verificar que inmo_id no está en el resultado
        if result is not None:
            assert "inmo_id" not in result, (
                "SEGURIDAD: inmo_id filtrado en get_finca_sin_identidad_listante"
            )
        return result
    except AssertionError:
        logger.error("SEGURIDAD: inmo_id presente en resultado para colaboradora")
        return None
    except Exception as e:
        logger.error("get_finca_sin_identidad_listante error: %s", e)
        return None
    finally:
        conn.close()


def get_fincas_publicadas() -> list:
    """
    Devuelve todas las fincas en estado 'publicada'.
    SIN inmo_id — para uso de colaboradoras y mapa público.
    SELECT explícito — inmo_id NUNCA aparece.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {_COLS_COLABORADORA}
                FROM fincas_mls
                WHERE estado = 'publicada'
                ORDER BY created_at DESC"""
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
        # Guardia defensiva
        for row in rows:
            assert "inmo_id" not in row, (
                "SEGURIDAD: inmo_id filtrado en get_fincas_publicadas"
            )
        return rows
    except AssertionError:
        logger.error("SEGURIDAD: inmo_id presente en fincas publicadas")
        return []
    except Exception as e:
        logger.error("get_fincas_publicadas error: %s", e)
        return []
    finally:
        conn.close()


def get_fincas_by_inmo(inmo_id: str) -> list:
    """
    Devuelve todas las fincas de una inmobiliaria listante.
    Incluye inmo_id — solo para uso del propio listante o admin.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM fincas_mls
               WHERE inmo_id = ?
               ORDER BY created_at DESC""",
            (inmo_id,)
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_fincas_by_inmo error: %s", e)
        return []
    finally:
        conn.close()


def update_finca_estado(finca_id: str, estado: str) -> bool:
    """Actualiza el estado de una finca MLS. Lanza ValueError si el estado no es válido."""
    if estado not in ESTADOS_FINCA_MLS:
        raise ValueError(f"Estado inválido: '{estado}'. Válidos: {sorted(ESTADOS_FINCA_MLS)}")
    conn = _db.get_conn()
    try:
        conn.execute(
            "UPDATE fincas_mls SET estado = ?, updated_at = ? WHERE id = ?",
            (estado, _now_utc(), finca_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_finca_estado error: %s", e)
        return False
    finally:
        conn.close()


def update_finca_catastro(finca_id: str, lat: float,
                          lon: float, validada: int = 1,
                          direccion: str = None,
                          municipio: str = None) -> bool:
    """Registra coordenadas, dirección y marca catastro_validada=1 tras validación exitosa."""
    conn = _db.get_conn()
    try:
        conn.execute(
            """UPDATE fincas_mls
               SET catastro_lat = ?, catastro_lon = ?,
                   catastro_validada = ?,
                   catastro_direccion = COALESCE(?, catastro_direccion),
                   catastro_municipio = COALESCE(?, catastro_municipio),
                   updated_at = ?
               WHERE id = ?""",
            (float(lat), float(lon), int(validada),
             direccion, municipio,
             _now_utc(), finca_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_finca_catastro error: %s", e)
        return False
    finally:
        conn.close()


def update_finca_ref_codigo(finca_id: str, ref_codigo: str,
                            secuencial: int) -> bool:
    """Registra el código REF generado y el secuencial."""
    conn = _db.get_conn()
    try:
        conn.execute(
            """UPDATE fincas_mls
               SET ref_codigo = ?, secuencial = ?, updated_at = ?
               WHERE id = ?""",
            (ref_codigo, int(secuencial), _now_utc(), finca_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("update_finca_ref_codigo error: %s", e)
        return False
    finally:
        conn.close()


def get_fincas_mls_para_mapa() -> list:
    """
    Devuelve solo los campos necesarios para el pin naranja en el mapa folium.
    NUNCA incluye inmo_id. Solo fincas con estado 'publicada' y coordenadas válidas.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {_COLS_MAPA}
                FROM fincas_mls
                WHERE estado = 'publicada'
                  AND catastro_lat IS NOT NULL
                  AND catastro_lon IS NOT NULL
                ORDER BY created_at DESC"""
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
        # Guardia defensiva
        for row in rows:
            assert "inmo_id" not in row, (
                "SEGURIDAD: inmo_id en get_fincas_mls_para_mapa"
            )
        return rows
    except AssertionError:
        logger.error("SEGURIDAD: inmo_id presente en datos del mapa")
        return []
    except Exception as e:
        logger.error("get_fincas_mls_para_mapa error: %s", e)
        return []
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# RESERVAS MLS
# ═════════════════════════════════════════════════════════════════════════════

def create_reserva(finca_id: str, inmo_colaboradora_id: str,
                   stripe_session_id: str, importe: float = 200.0) -> str | None:
    """
    Crea una reserva de 72h.
    Calcula timestamp_expira_72h automáticamente.
    Devuelve reserva_id o None si falla.
    """
    from datetime import timedelta
    reserva_id = uuid.uuid4().hex
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(hours=72)
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO reservas_mls
               (id, finca_id, inmo_colaboradora_id, stripe_session_id,
                importe_reserva, estado, timestamp_reserva, timestamp_expira_72h)
               VALUES (?, ?, ?, ?, ?, 'activa', ?, ?)""",
            (reserva_id, finca_id, inmo_colaboradora_id,
             stripe_session_id, float(importe),
             ahora.isoformat(timespec="seconds"),
             expira.isoformat(timespec="seconds"))
        )
        conn.commit()
        return reserva_id
    except Exception as e:
        logger.error("create_reserva error: %s", e)
        return None
    finally:
        conn.close()


def get_reserva_activa_by_finca(finca_id: str) -> dict | None:
    """Devuelve la reserva activa de una finca, o None si no tiene."""
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM reservas_mls
               WHERE finca_id = ? AND estado = 'activa'
               ORDER BY timestamp_reserva DESC
               LIMIT 1""",
            (finca_id,)
        )
        return _row_to_dict(cur.fetchone())
    except Exception as e:
        logger.error("get_reserva_activa_by_finca error: %s", e)
        return None
    finally:
        conn.close()


def expire_reservas_vencidas(conn) -> None:
    """
    Lazy expiration — se llama al cargar cualquier panel MLS.
    Sin cron externo. 3 operaciones independientes con commit intermedio
    para garantizar consistencia en SQLite WAL (corrección C3).

    Recibe conn externo para que el llamador controle el ciclo de vida.
    """
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1. Marcar reservas expiradas
    conn.execute(
        """UPDATE reservas_mls SET estado = 'expirada'
           WHERE estado = 'activa' AND timestamp_expira_72h < ?""",
        (ahora,)
    )
    conn.commit()  # commit 1: reservas ya marcadas como expiradas

    # 2. Liberar fincas cuyas reservas están ahora expiradas
    #    (la subconsulta lee el estado ya commiteado en paso 1)
    conn.execute(
        """UPDATE fincas_mls SET estado = 'publicada', updated_at = ?
           WHERE estado = 'reservada'
             AND id IN (
                 SELECT finca_id FROM reservas_mls WHERE estado = 'expirada'
             )""",
        (ahora,)
    )
    conn.commit()  # commit 2

    # 3. Expirar periodo_privado (48h) → publicar la finca (corrección I2)
    conn.execute(
        """UPDATE fincas_mls SET estado = 'publicada', updated_at = ?
           WHERE estado = 'periodo_privado'
             AND periodo_privado_expira < ?""",
        (ahora, ahora)
    )
    conn.commit()  # commit 3


def create_reserva_cliente(finca_id: str, nombre_cliente: str,
                           email_cliente: str, stripe_session_id: str,
                           importe: float = 200.0) -> str | None:
    """
    Reserva directa por cliente final (no inmobiliaria colaboradora).
    - inmo_colaboradora_id = "CLIENTE_DIRECTO"  (valor especial)
    - estado = "pendiente_confirmacion_48h"
    - Expira en 48h (no 72h — admin debe confirmar disponibilidad)
    Devuelve reserva_id o None si falla.
    """
    from datetime import timedelta
    reserva_id = uuid.uuid4().hex
    ahora  = datetime.now(timezone.utc)
    expira = ahora + timedelta(hours=48)
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO reservas_mls
               (id, finca_id, inmo_colaboradora_id, stripe_session_id,
                importe_reserva, estado,
                timestamp_reserva, timestamp_expira_72h, notas)
               VALUES (?, ?, 'CLIENTE_DIRECTO', ?, ?,
                       'pendiente_confirmacion_48h', ?, ?, ?)""",
            (reserva_id, finca_id, stripe_session_id, float(importe),
             ahora.isoformat(timespec="seconds"),
             expira.isoformat(timespec="seconds"),
             f"Cliente: {nombre_cliente} | {email_cliente}")
        )
        conn.commit()
        return reserva_id
    except Exception as e:
        logger.error("create_reserva_cliente error: %s", e)
        return None
    finally:
        conn.close()


def registrar_contacto_cliente(finca_id: str, nombre: str,
                                email: str, mensaje: str) -> str | None:
    """
    Registra un contacto de cliente interesado en una finca MLS.
    Inserta en notificaciones_mls para que admin lo gestione.
    Devuelve notif_id como str, o None si falla.
    """
    import json
    payload = json.dumps({
        "finca_id": finca_id,
        "nombre":   nombre,
        "email":    email,
        "mensaje":  mensaje,
    }, ensure_ascii=False)
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO notificaciones_mls
               (destinatario_tipo, destinatario_id,
                tipo_evento, payload, timestamp, leida)
               VALUES ('archirapid', 'admin',
                       'contacto_cliente_finca', ?, ?, 0)""",
            (payload, _now_utc())
        )
        conn.commit()
        return str(cur.lastrowid)
    except Exception as e:
        logger.error("registrar_contacto_cliente error: %s", e)
        return None
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# FIRMAS DEL ACUERDO DE COLABORACIÓN
# ═════════════════════════════════════════════════════════════════════════════

def create_firma(inmo_id: str, doc_hash: str, firma_hash: str,
                 timestamp: str, ip: str, cif: str) -> int | None:
    """
    Inserta el registro de firma digital eIDAS en firmas_colaboracion.
    Devuelve el id (INTEGER AUTOINCREMENT) o None si falla.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO firmas_colaboracion
               (inmo_id, documento_version, documento_hash,
                firma_hash, timestamp, ip, cif)
               VALUES (?, '1.0', ?, ?, ?, ?, ?)""",
            (inmo_id, doc_hash, firma_hash, timestamp,
             ip or "0.0.0.0", cif)
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("create_firma error: %s", e)
        return None
    finally:
        conn.close()


def get_firma_by_inmo(inmo_id: str) -> dict | None:
    """Devuelve el registro de firma del acuerdo de la inmobiliaria, o None."""
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM firmas_colaboracion
               WHERE inmo_id = ?
               ORDER BY id DESC
               LIMIT 1""",
            (inmo_id,)
        )
        return _row_to_dict(cur.fetchone())
    except Exception as e:
        logger.error("get_firma_by_inmo error: %s", e)
        return None
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES MLS
# ═════════════════════════════════════════════════════════════════════════════

def create_notificacion(destinatario_tipo: str, destinatario_id: str,
                        tipo_evento: str, payload: str) -> int | None:
    """
    Inserta una notificación MLS en la tabla.
    payload: JSON string con detalles del evento.
    Devuelve id (INTEGER AUTOINCREMENT) o None si falla.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO notificaciones_mls
               (destinatario_tipo, destinatario_id,
                tipo_evento, payload, timestamp, leida)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (destinatario_tipo, destinatario_id,
             tipo_evento, payload, _now_utc())
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("create_notificacion error: %s", e)
        return None
    finally:
        conn.close()


def get_notificaciones_no_leidas(destinatario_id: str) -> list:
    """Devuelve las notificaciones no leídas de un destinatario."""
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM notificaciones_mls
               WHERE destinatario_id = ? AND leida = 0
               ORDER BY timestamp DESC""",
            (destinatario_id,)
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_notificaciones_no_leidas error: %s", e)
        return []
    finally:
        conn.close()


def marcar_leida(notif_id: int) -> bool:
    """Marca una notificación como leída."""
    conn = _db.get_conn()
    try:
        conn.execute(
            "UPDATE notificaciones_mls SET leida = 1 WHERE id = ?",
            (int(notif_id),)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("marcar_leida error: %s", e)
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# TRIAL 30 DÍAS
# ═════════════════════════════════════════════════════════════════════════════

_TRIAL_DAYS = 30


def activate_trial(inmo_id: str) -> bool:
    """
    Activa el trial de 30 días para una inmobiliaria recién aprobada.
    Guarda trial_start_date = fecha actual ISO (UTC), trial_active = 1.
    Es idempotente: si el trial ya estaba activo no lo reinicia.
    """
    conn = _db.get_conn()
    try:
        row = conn.execute(
            "SELECT trial_active FROM inmobiliarias WHERE id = ?",
            (inmo_id,)
        ).fetchone()
        if row and row["trial_active"] == 1:
            # Ya activo — no reiniciar
            return True
        conn.execute(
            """UPDATE inmobiliarias
               SET trial_start_date = ?,
                   trial_active      = 1,
                   trial_expired     = 0
               WHERE id = ?""",
            (_now_utc(), inmo_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("activate_trial error: %s", e)
        return False
    finally:
        conn.close()


def check_trial_status(inmo_id: str) -> dict:
    """
    Devuelve el estado actual del trial de una inmobiliaria.

    Claves del dict:
      active         bool  — trial en curso (no expirado, no sustituido por plan)
      expired        bool  — trial expirado y sin plan de pago
      days_remaining int   — días que quedan (0 si expirado o sin trial)
      on_paid_plan   bool  — tiene plan de pago activo (plan_activo=1)
      trial_day      int   — día del trial en que se encuentra (1-30, 0 si no aplica)
    """
    _default = {
        "active": False,
        "expired": False,
        "days_remaining": 0,
        "on_paid_plan": False,
        "trial_day": 0,
    }
    conn = _db.get_conn()
    try:
        row = conn.execute(
            """SELECT plan_activo, trial_start_date, trial_active, trial_expired
               FROM inmobiliarias WHERE id = ?""",
            (inmo_id,)
        ).fetchone()
    except Exception as e:
        logger.error("check_trial_status error: %s", e)
        return _default
    finally:
        conn.close()

    if row is None:
        return _default

    on_paid_plan = bool(row["plan_activo"])
    if on_paid_plan:
        return {**_default, "on_paid_plan": True}

    if not row["trial_active"] and not row["trial_expired"]:
        # Nunca activado
        return _default

    if not row["trial_start_date"]:
        return _default

    from datetime import timedelta
    try:
        start = datetime.fromisoformat(row["trial_start_date"])
        # Asegurar timezone-aware
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    except Exception:
        return _default

    now = datetime.now(timezone.utc)
    elapsed_days = (now - start).days
    days_remaining = max(0, _TRIAL_DAYS - elapsed_days)
    trial_day = min(elapsed_days + 1, _TRIAL_DAYS)

    if days_remaining > 0 and not row["trial_expired"]:
        return {
            "active": True,
            "expired": False,
            "days_remaining": days_remaining,
            "on_paid_plan": False,
            "trial_day": trial_day,
        }

    # Trial expirado — marcar en BD si aún no estaba marcado
    if not row["trial_expired"]:
        try:
            conn2 = _db.get_conn()
            conn2.execute(
                """UPDATE inmobiliarias
                   SET trial_active = 0, trial_expired = 1
                   WHERE id = ?""",
                (inmo_id,)
            )
            conn2.commit()
        except Exception as e:
            logger.error("check_trial_status mark_expired error: %s", e)
        finally:
            try:
                conn2.close()
            except Exception:
                pass

    return {
        "active": False,
        "expired": True,
        "days_remaining": 0,
        "on_paid_plan": False,
        "trial_day": _TRIAL_DAYS,
    }


def get_trial_days_remaining(inmo_id: str) -> int:
    """
    Helper simple: días que quedan del trial.
    Devuelve 0 si el trial expiró, no existe o la inmo tiene plan de pago.
    """
    return check_trial_status(inmo_id)["days_remaining"]


def get_inmos_con_trial_activo() -> list:
    """
    Devuelve lista de dicts con id, nombre, email, trial_start_date
    de todas las inmobiliarias con trial_active=1 y plan_activo=0.
    Usado por check_and_send_trial_emails() en intranet.
    """
    conn = _db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nombre, nombre_comercial, email,
                      trial_start_date, trial_active, trial_expired
               FROM inmobiliarias
               WHERE trial_active = 1 AND plan_activo = 0
               ORDER BY trial_start_date ASC"""
        )
        return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_inmos_con_trial_activo error: %s", e)
        return []
    finally:
        conn.close()
