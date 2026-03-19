"""
modules/mls/mls_firma.py
Texto del acuerdo MLS, funciones de firma SHA-256 y UI Streamlit de firma.

Sección 1 — TEXTO_ACUERDO_MLS   : constante (stdlib only)
Sección 2 — Funciones de firma  : stdlib only (hashlib, datetime)
Sección 3 — UI Streamlit        : importa streamlit y mls_db
"""
import hashlib
from datetime import datetime, timezone


# =============================================================================
# SECCIÓN 1 — TEXTO DEL ACUERDO (constante — versión 1.0)
# =============================================================================

TEXTO_ACUERDO_MLS = """\
ACUERDO DE COLABORACIÓN INMOBILIARIA — ARCHIRAPID MLS
Versión 1.0
================================================================================

El presente Acuerdo regula la participación de agencias inmobiliarias en la
Bolsa de Colaboración ArchiRapid MLS, plataforma neutral gestionada por
ArchiRapid S.L. (en adelante, «ArchiRapid»).

Al completar el proceso de firma digital, la inmobiliaria declara haber leído,
comprendido y aceptado íntegramente las condiciones que se detallan a
continuación.

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 1 — OBJETO DEL ACUERDO
────────────────────────────────────────────────────────────────────────────────

1.1. El presente Acuerdo tiene por objeto establecer las condiciones bajo las
     cuales la inmobiliaria firmante (en adelante, «la Inmobiliaria») accede y
     opera dentro de la Bolsa de Colaboración ArchiRapid MLS.

1.2. ArchiRapid MLS es un sistema de listado múltiple (Multiple Listing
     Service) que permite a inmobiliarias registradas publicar fincas («rol
     listante») y colaborar en la captación de compradores para fincas
     publicadas por terceros («rol colaboradora»), bajo las condiciones de
     reparto de comisiones pactadas en el momento de publicación.

1.3. ArchiRapid actúa exclusivamente como plataforma neutral y árbitro técnico.
     No es parte en las operaciones de compraventa ni asume responsabilidad
     sobre la veracidad de los datos aportados por las inmobiliarias.

1.4. La Inmobiliaria actúa por cuenta propia o en representación de su red de
     agentes, asumiendo plena responsabilidad por el cumplimiento de la
     normativa aplicable (LCI, LAU, LOPD/RGPD y demás disposiciones vigentes).

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 2 — REPARTO DE COMISIONES
────────────────────────────────────────────────────────────────────────────────

2.1. COMISIÓN FIJA DE PLATAFORMA: ArchiRapid retiene el 1 % (uno por ciento)
     del precio de cierre de cada operación formalizada a través de la
     plataforma, con independencia del plan contratado. Este porcentaje es
     irrenunciable e invariable.

2.2. CANAL DE COLABORACIÓN: El porcentaje restante de la comisión total
     pactada con el vendedor (comisión total − 1 % ArchiRapid) constituye el
     «canal de colaboración», distribuido entre:
       a) Inmobiliaria listante: porcentaje acordado en el momento de
          publicación de la finca.
       b) Inmobiliaria colaboradora: porcentaje ofertado públicamente por la
          listante, visible antes de cualquier acción de colaboración.

2.3. OFERTA MÍNIMA AL CANAL: La inmobiliaria listante se compromete a ofrecer
     a la colaboradora un mínimo del 30 % y un máximo del 70 % del canal de
     colaboración disponible. Ofertas fuera de este rango serán rechazadas
     automáticamente por la plataforma.

2.4. IRREVOCABILIDAD DEL SPLIT: Una vez publicada la finca con un split
     específico y aceptado por una inmobiliaria colaboradora, el reparto no
     puede modificarse unilateralmente. Cualquier ajuste requiere acuerdo
     escrito entre ambas partes y validación de ArchiRapid.

2.5. PAGO: Las comisiones se liquidan directamente entre las partes a la firma
     de la escritura pública de compraventa. ArchiRapid factura su 1 % de forma
     independiente a cada inmobiliaria participante en la operación.

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 3 — CONFIDENCIALIDAD E IDENTIDAD DEL LISTANTE
────────────────────────────────────────────────────────────────────────────────

3.1. PROTECCIÓN DE IDENTIDAD: La identidad de la inmobiliaria listante (nombre,
     CIF, datos de contacto) permanece protegida frente a las inmobiliarias
     colaboradoras hasta el cierre formal de la operación. La plataforma
     muestra exclusivamente los datos técnicos de la finca (referencia catastral
     validada, precio, superficie, comisión ofertada) sin revelar el origen.

3.2. PROHIBICIÓN EXPRESA: Queda terminantemente prohibido a la colaboradora:
       a) Intentar identificar a la inmobiliaria listante por medios directos
          o indirectos (búsqueda catastral, redes sociales, contacto con el
          propietario, etc.).
       b) Contactar directamente al propietario de la finca listada.
       c) Compartir la información de la finca con terceros no registrados en
          ArchiRapid MLS sin consentimiento expreso de la listante.

3.3. INCUMPLIMIENTO Y SANCIONES: La infracción de cualquiera de las
     prohibiciones del Art. 3.2 supone:
       a) Expulsión inmediata e irreversible de la plataforma.
       b) Pérdida de todas las reservas activas sin derecho a reembolso.
       c) Comunicación del incidente a las asociaciones profesionales del sector
          (COAPI, API) y, en su caso, acción legal por daños y perjuicios.

3.4. DEBER DE RESERVA RECÍPROCA: La inmobiliaria listante tampoco podrá
     revelar a terceros la identidad de la colaboradora durante el período de
     reserva activa.

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 4 — RESERVAS Y EXCLUSIVA DE 72 HORAS
────────────────────────────────────────────────────────────────────────────────

4.1. RESERVA: La inmobiliaria colaboradora con plan AGENCY o ENTERPRISE puede
     reservar una finca publicada mediante el pago de 200 € (doscientos euros)
     a través de la pasarela de pago de ArchiRapid (Stripe, modo test durante
     el período MVP).

4.2. EXCLUSIVA: Durante 72 horas desde el momento del pago, ninguna otra
     colaboradora puede reservar la misma finca. La exclusiva es intransferible.

4.3. EXPIRACIÓN AUTOMÁTICA: Si transcurridas 72 horas no se ha comunicado
     una operación en curso, la reserva expira automáticamente y la finca vuelve
     a estar disponible para otras colaboradoras. El importe de reserva se
     descuenta de la comisión final si la operación se cierra; en caso contrario,
     no es reembolsable salvo error técnico acreditado de la plataforma.

4.4. PERÍODO PRIVADO INICIAL: La inmobiliaria listante puede establecer un
     período de exclusividad privada antes de la publicación en el mercado
     abierto MLS. Durante ese período, solo las colaboradoras invitadas
     explícitamente pueden acceder a la finca.

4.5. PLAN STARTER: Las inmobiliarias con plan STARTER solo pueden operar como
     listantes. No tienen acceso al sistema de reservas como colaboradoras.

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 5 — VALIDEZ LEGAL Y FIRMA DIGITAL
────────────────────────────────────────────────────────────────────────────────

5.1. EIDAS ART. 25: El presente acuerdo se suscribe mediante firma electrónica
     simple conforme al artículo 25 del Reglamento (UE) N.º 910/2014 (eIDAS).
     La firma consiste en un hash SHA-256 calculado sobre el texto íntegro del
     acuerdo, el timestamp UTC de la firma, el CIF de la entidad firmante y la
     dirección IP de la conexión.

5.2. IDENTIFICACIÓN DEL FIRMANTE: La identificación del firmante se basa en el
     CIF y email registrados, únicos en el sistema. La dirección IP es dato
     auxiliar de contexto y no constituye identificación principal conforme al
     Reglamento (UE) 2016/679 (RGPD).

5.3. CONSERVACIÓN: ArchiRapid conserva el hash de firma, el hash del documento,
     el timestamp y los datos identificativos durante un mínimo de 5 años desde
     la firma, conforme a la Ley 34/2002 (LSSI-CE).

5.4. NO REPUDIO: La generación del hash de firma en el sistema implica la
     aceptación irrevocable de este acuerdo. La Inmobiliaria reconoce que no
     podrá alegar desconocimiento del contenido una vez generada la firma.

────────────────────────────────────────────────────────────────────────────────
ARTÍCULO 6 — JURISDICCIÓN Y LEY APLICABLE
────────────────────────────────────────────────────────────────────────────────

6.1. El presente Acuerdo se rige por la legislación española vigente.

6.2. Para la resolución de cualquier controversia derivada de la interpretación
     o ejecución de este Acuerdo, las partes se someten expresamente a los
     Juzgados y Tribunales de la ciudad de Madrid, con renuncia expresa a
     cualquier otro fuero que pudiera corresponderles.

6.3. En caso de discrepancia entre la versión en pantalla y el texto cuyo hash
     SHA-256 consta en la firma digital, prevalecerá el texto cuyo hash coincida
     con el registrado en la base de datos de ArchiRapid en el momento de la
     firma.

================================================================================
ArchiRapid MLS — Acuerdo de Colaboración Inmobiliaria — Versión 1.0
© ArchiRapid S.L. — Madrid, España
================================================================================
"""

# Hash determinista del documento (calculado una sola vez al importar el módulo)
_DOCUMENTO_HASH: str = hashlib.sha256(TEXTO_ACUERDO_MLS.encode("utf-8")).hexdigest()


# =============================================================================
# SECCIÓN 2 — FUNCIONES DE FIRMA (stdlib only, sin Streamlit, sin src.db)
# =============================================================================

def get_documento_hash() -> str:
    """
    Devuelve el SHA-256 del TEXTO_ACUERDO_MLS en UTF-8.
    Determinista: siempre el mismo hash para la misma versión del texto.
    El hash NO incluye timestamp ni datos del firmante.
    """
    return _DOCUMENTO_HASH


def firmar_acuerdo(inmo_id: str, cif: str, ip: str) -> dict:
    """
    Genera la firma digital del acuerdo MLS para una inmobiliaria.

    El firma_hash se calcula sobre:
        TEXTO_ACUERDO_MLS + timestamp + cif + ip
    (mismo patrón que blockchain_cert.py)

    Devuelve:
        {
            "doc_hash":  str,   # SHA-256 del texto (determinista)
            "firma_hash": str,  # SHA-256(texto + timestamp + cif + ip)
            "timestamp": str,   # ISO 8601 UTC con segundos
            "cif":       str,
            "ip":        str,
            "version":   "1.0"
        }
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc_hash  = get_documento_hash()

    payload = TEXTO_ACUERDO_MLS + timestamp + str(cif) + str(ip)
    firma_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return {
        "doc_hash":   doc_hash,
        "firma_hash": firma_hash,
        "timestamp":  timestamp,
        "cif":        str(cif),
        "ip":         str(ip),
        "version":    "1.0",
    }


def verificar_firma(firma_hash: str, cif: str, ip: str, timestamp: str) -> bool:
    """
    Verifica una firma recalculando el hash con los mismos inputs.
    Devuelve True si el hash recalculado coincide con firma_hash.
    Para uso en auditoría futura.
    """
    payload = TEXTO_ACUERDO_MLS + str(timestamp) + str(cif) + str(ip)
    recalculado = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return recalculado == firma_hash


# =============================================================================
# SECCIÓN 3 — UI STREAMLIT
# =============================================================================

def mostrar_ui_firma(inmo: dict) -> bool:
    """
    Muestra la interfaz de firma del acuerdo MLS.

    Parámetros:
        inmo: dict con campos de la tabla inmobiliarias
              (id, nombre, cif, firma_hash, firma_timestamp, ...)

    Retorna:
        True  → la firma se completó en esta llamada
        False → ya estaba firmado, o el usuario aún no ha firmado
    """
    import streamlit as st
    from modules.mls import mls_db

    # ── 1. Ya firmado ────────────────────────────────────────────────────────
    if inmo.get("firma_hash"):
        fecha_raw = inmo.get("firma_timestamp", "")
        try:
            fecha_dt  = datetime.fromisoformat(fecha_raw)
            fecha_fmt = fecha_dt.strftime("%d/%m/%Y %H:%M UTC")
        except Exception:
            fecha_fmt = fecha_raw

        st.success(f"Acuerdo firmado el {fecha_fmt}")
        st.caption(
            f"Firma digital (SHA-256): `{inmo['firma_hash'][:16]}…`  |  "
            f"Documento: `{get_documento_hash()[:16]}…`"
        )
        return False

    # ── 2. Pendiente de firma ────────────────────────────────────────────────
    st.warning(
        "Antes de operar en ArchiRapid MLS debes firmar el Acuerdo de "
        "Colaboración Inmobiliaria. La firma es electrónica (eIDAS art. 25) "
        "y tiene plena validez legal."
    )

    with st.expander("Leer Acuerdo de Colaboración"):
        st.text_area(
            label="Acuerdo de Colaboración Inmobiliaria — Versión 1.0",
            value=TEXTO_ACUERDO_MLS,
            height=400,
            disabled=True,
            key="mls_firma_texto",
        )

    leido = st.checkbox(
        "He leído y entendido el Acuerdo de Colaboración Inmobiliaria",
        key="mls_firma_leido",
    )

    if st.button(
        "Firmar digitalmente",
        disabled=not leido,
        key="mls_firma_btn",
        type="primary",
    ):
        ip = st.context.headers.get("X-Forwarded-For", "0.0.0.0")
        datos = firmar_acuerdo(
            inmo_id=inmo["id"],
            cif=inmo["cif"],
            ip=ip,
        )

        try:
            conn = mls_db._get_conn()
            mls_db.create_firma(
                conn=conn,
                inmo_id=inmo["id"],
                doc_hash=datos["doc_hash"],
                firma_hash=datos["firma_hash"],
                timestamp=datos["timestamp"],
                ip=datos["ip"],
                cif=datos["cif"],
            )
            mls_db.update_inmo_firma(
                conn=conn,
                inmo_id=inmo["id"],
                firma_hash=datos["firma_hash"],
                firma_timestamp=datos["timestamp"],
            )
            conn.close()
        except Exception as exc:
            st.error(f"Error al registrar la firma: {exc}")
            return False

        st.success(
            f"Acuerdo firmado correctamente.  \n"
            f"Firma SHA-256: `{datos['firma_hash'][:16]}…`"
        )
        st.balloons()
        return True

    return False


# =============================================================================
# TESTS INTEGRADOS
# =============================================================================

if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    errores = []

    # ── Test 1: get_documento_hash() determinista ─────────────────────────────
    print("Test 1: get_documento_hash() — mismo hash en dos llamadas")
    h1 = get_documento_hash()
    h2 = get_documento_hash()
    assert h1 == h2, f"Hashes distintos: {h1} vs {h2}"
    assert len(h1) == 64, f"Longitud esperada 64 hex chars, obtenida {len(h1)}"
    print(f"  Hash 1: {h1[:32]}…")
    print(f"  Hash 2: {h2[:32]}…")
    print("  PASS\n")

    # ── Test 2: firmar_acuerdo — doc_hash determinista, firma_hash único ──────
    print("Test 2: firmar_acuerdo('id1', 'B12345678A', '1.2.3.4')")
    f1 = firmar_acuerdo("id1", "B12345678A", "1.2.3.4")
    assert f1["doc_hash"]   == h1,    f"doc_hash difiere: {f1['doc_hash']}"
    assert f1["version"]    == "1.0", f"version: {f1['version']}"
    assert f1["cif"]        == "B12345678A"
    assert f1["ip"]         == "1.2.3.4"
    assert len(f1["firma_hash"]) == 64, "firma_hash debe tener 64 chars hex"
    print(f"  doc_hash   : {f1['doc_hash'][:32]}…  (determinista OK)")
    print(f"  firma_hash : {f1['firma_hash'][:32]}…")
    print(f"  timestamp  : {f1['timestamp']}")
    print(f"  version    : {f1['version']}")
    print("  PASS\n")

    # ── Test 3: verificar_firma con datos correctos → True ────────────────────
    print("Test 3: verificar_firma con datos correctos → True")
    ok = verificar_firma(
        firma_hash=f1["firma_hash"],
        cif=f1["cif"],
        ip=f1["ip"],
        timestamp=f1["timestamp"],
    )
    assert ok is True, f"Esperado True, obtenido {ok}"
    print(f"  verificar_firma(...) → {ok}")
    print("  PASS\n")

    # ── Test 4: verificar_firma con IP cambiada → False ───────────────────────
    print("Test 4: verificar_firma con IP cambiada → False")
    ko = verificar_firma(
        firma_hash=f1["firma_hash"],
        cif=f1["cif"],
        ip="9.9.9.9",               # IP distinta
        timestamp=f1["timestamp"],
    )
    assert ko is False, f"Esperado False, obtenido {ko}"
    print(f"  verificar_firma(ip='9.9.9.9') → {ko}")
    print("  PASS\n")

    # ── Confirmación adicional: doc_hash no cambia entre ejecuciones ─────────
    print("Confirmación: doc_hash es el SHA-256 puro del texto del acuerdo")
    control = hashlib.sha256(TEXTO_ACUERDO_MLS.encode("utf-8")).hexdigest()
    assert control == h1, "doc_hash no coincide con cálculo directo"
    print(f"  SHA-256 directo del texto: {control[:32]}…")
    print(f"  get_documento_hash()     : {h1[:32]}…")
    print("  Coinciden — PASS\n")

    if errores:
        print("ERRORES DETECTADOS:")
        for e in errores:
            print(f"  - {e}")
    else:
        print("=" * 50)
        print("TODOS LOS TESTS PASADOS OK")
        print("=" * 50)
