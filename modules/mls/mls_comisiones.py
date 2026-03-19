"""
modules/mls/mls_comisiones.py
Lógica pura de negocio para comisiones y código REF del sistema MLS.

Sin imports de Streamlit. Sin acceso directo a BD.
Solo stdlib: math, datetime.
"""
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_pct(pct: float) -> str:
    """Formatea porcentaje sin ceros decimales innecesarios: 3.0→'3', 3.5→'3.5'."""
    return str(int(pct)) if pct == int(pct) else str(round(pct, 10)).rstrip("0")


def _r2(value: float) -> float:
    """Redondea a 2 decimales."""
    return round(value, 2)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES PÚBLICAS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_split(precio: float, comision_total_pct: float,
                   colaboradora_pct: float) -> dict:
    """Calcula el reparto exacto de comisiones entre ArchiRapid, colaboradora y listante."""
    precio = float(precio)
    comision_total_pct = float(comision_total_pct)
    colaboradora_pct = float(colaboradora_pct)

    # Validaciones
    if comision_total_pct <= 1.0:
        raise ValueError(
            f"comision_total_pct debe ser > 1.0 "
            f"(recibido {comision_total_pct}). "
            f"ArchiRapid cobra 1% fijo — no queda margen para el canal."
        )

    archirapid_pct = 1.0
    total_canal_pct = _r2(comision_total_pct - archirapid_pct)

    if colaboradora_pct > total_canal_pct:
        raise ValueError(
            f"colaboradora_pct ({colaboradora_pct}%) supera el canal disponible "
            f"({total_canal_pct}%). Ajusta la comisión total o reduce la oferta."
        )
    if colaboradora_pct < 0:
        raise ValueError("colaboradora_pct no puede ser negativo.")

    listante_pct = _r2(total_canal_pct - colaboradora_pct)

    # Importes en euros
    archirapid_eur  = _r2(precio * archirapid_pct  / 100)
    colaboradora_eur = _r2(precio * colaboradora_pct / 100)
    listante_eur    = _r2(precio * listante_pct    / 100)
    total_canal_eur = _r2(precio * total_canal_pct  / 100)

    return {
        "archirapid_pct":   _r2(archirapid_pct),
        "archirapid_eur":   archirapid_eur,
        "colaboradora_pct": _r2(colaboradora_pct),
        "colaboradora_eur": colaboradora_eur,
        "listante_pct":     listante_pct,
        "listante_eur":     listante_eur,
        "total_canal_pct":  total_canal_pct,
        "total_canal_eur":  total_canal_eur,
    }


def calcular_split_sugerido(precio: float, comision_total_pct: float) -> dict:
    """Igual que calcular_split con colaboradora_pct = 50% del canal disponible."""
    comision_total_pct = float(comision_total_pct)

    if comision_total_pct <= 1.0:
        raise ValueError(
            f"comision_total_pct debe ser > 1.0 (recibido {comision_total_pct})."
        )

    total_canal_pct = _r2(comision_total_pct - 1.0)
    colaboradora_sugerida = _r2(total_canal_pct * 0.5)

    return calcular_split(precio, comision_total_pct, colaboradora_sugerida)


def get_siguiente_secuencial(conn) -> int:
    """SELECT COALESCE(MAX(secuencial), 0) + 1 FROM fincas_mls. El llamador gestiona la transacción."""
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(secuencial), 0) + 1 FROM fincas_mls")
    row = cur.fetchone()
    return int(row[0]) if row else 1


def generar_ref_codigo(secuencial: int, comision_total_pct: float,
                       colaboradora_pct: float,
                       archirapid_pct: float = 1.0) -> str:
    """Genera el código REF único: AR-{AÑO}-{SEC:05d} | {TOT}-{COL}-{ARCH}."""
    anio = datetime.now(timezone.utc).year
    tot  = _fmt_pct(float(comision_total_pct))
    col  = _fmt_pct(float(colaboradora_pct))
    arch = _fmt_pct(float(archirapid_pct))
    return f"AR-{anio}-{int(secuencial):05d} | {tot}-{col}-{arch}"


def validar_rango_colaboradora(comision_total_pct: float,
                               colaboradora_pct: float) -> bool:
    """True si colaboradora_pct está entre 30% y 70% del canal disponible."""
    comision_total_pct = float(comision_total_pct)
    colaboradora_pct   = float(colaboradora_pct)

    if comision_total_pct <= 1.0:
        return False

    canal = comision_total_pct - 1.0
    minimo = _r2(canal * 0.30)
    maximo = _r2(canal * 0.70)

    return minimo <= _r2(colaboradora_pct) <= maximo


# ─────────────────────────────────────────────────────────────────────────────
# TESTS INTEGRADOS
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    errores = []

    # ── Caso 1: precio 300.000, comision 8%, colab 3.5% ──────────────────────
    print("Caso 1: precio=300.000, comision=8%, colaboradora=3.5%")
    r = calcular_split(300_000, 8.0, 3.5)
    assert r["archirapid_pct"]   == 1.0,      f"archirapid_pct: {r['archirapid_pct']}"
    assert r["archirapid_eur"]   == 3000.0,   f"archirapid_eur: {r['archirapid_eur']}"
    assert r["colaboradora_pct"] == 3.5,      f"colaboradora_pct: {r['colaboradora_pct']}"
    assert r["colaboradora_eur"] == 10500.0,  f"colaboradora_eur: {r['colaboradora_eur']}"
    assert r["listante_pct"]     == 3.5,      f"listante_pct: {r['listante_pct']}"
    assert r["listante_eur"]     == 10500.0,  f"listante_eur: {r['listante_eur']}"
    assert r["total_canal_pct"]  == 7.0,      f"total_canal_pct: {r['total_canal_pct']}"
    assert r["total_canal_eur"]  == 21000.0,  f"total_canal_eur: {r['total_canal_eur']}"
    print(f"  archirapid  : {r['archirapid_pct']}%  =  {r['archirapid_eur']:,.0f} EUR")
    print(f"  colaboradora: {r['colaboradora_pct']}%  = {r['colaboradora_eur']:,.0f} EUR")
    print(f"  listante    : {r['listante_pct']}%  = {r['listante_eur']:,.0f} EUR")
    print("  PASS\n")

    # ── Caso 2: comision 1.0% → ValueError ───────────────────────────────────
    print("Caso 2: comision=1.0% → ValueError esperado")
    try:
        calcular_split(300_000, 1.0, 0.0)
        errores.append("Caso 2: debio lanzar ValueError")
        print("  FAIL — no lanzó ValueError")
    except ValueError as e:
        print(f"  ValueError OK: {e}")
        print("  PASS\n")

    # ── Caso 3: generar_ref_codigo ────────────────────────────────────────────
    print("Caso 3: generar_ref_codigo(234, 8.0, 3.5, 1.0)")
    ref = generar_ref_codigo(234, 8.0, 3.5, 1.0)
    from datetime import datetime, timezone as _tz
    anio_actual = datetime.now(_tz.utc).year
    esperado = f"AR-{anio_actual}-00234 | 8-3.5-1"
    assert ref == esperado, f"Esperado '{esperado}', obtenido '{ref}'"
    print(f"  REF generado: {ref!r}")
    print("  PASS\n")

    # ── Caso 4: validar_rango_colaboradora ────────────────────────────────────
    print("Caso 4: validar_rango_colaboradora(8.0, 3.5)")
    # canal=7.0, 30%=2.1, 70%=4.9 → 3.5 está dentro
    resultado = validar_rango_colaboradora(8.0, 3.5)
    assert resultado is True, f"Esperado True, obtenido {resultado}"
    print(f"  canal=7.0, rango=[2.1, 4.9], colaboradora=3.5 → {resultado}")
    # Extra: fuera de rango
    assert validar_rango_colaboradora(8.0, 5.0) is False, "5.0 debe ser False (>70%)"
    assert validar_rango_colaboradora(8.0, 2.0) is False, "2.0 debe ser False (<30%)"
    assert validar_rango_colaboradora(1.0, 0.0) is False, "canal<=0 debe ser False"
    print("  Fuera de rango (5.0 y 2.0): False OK")
    print("  PASS\n")

    # ── Caso 5 (extra): split sugerido ───────────────────────────────────────
    print("Caso 5 (extra): calcular_split_sugerido(300.000, 8.0)")
    r2 = calcular_split_sugerido(300_000, 8.0)
    assert r2["colaboradora_pct"] == 3.5, f"sugerido: {r2['colaboradora_pct']}"
    print(f"  colaboradora sugerida: {r2['colaboradora_pct']}% (50% de canal 7.0)")
    print("  PASS\n")

    # ── Caso 6 (extra): formato sin ceros ────────────────────────────────────
    print("Caso 6 (extra): _fmt_pct format tests")
    from modules.mls.mls_comisiones import _fmt_pct
    assert _fmt_pct(3.0)  == "3",   f"3.0 -> {_fmt_pct(3.0)}"
    assert _fmt_pct(3.5)  == "3.5", f"3.5 -> {_fmt_pct(3.5)}"
    assert _fmt_pct(10.0) == "10",  f"10.0 -> {_fmt_pct(10.0)}"
    assert _fmt_pct(1.0)  == "1",   f"1.0 -> {_fmt_pct(1.0)}"
    print("  3.0->'3', 3.5->'3.5', 10.0->'10', 1.0->'1'  OK")
    print("  PASS\n")

    if errores:
        print("ERRORES DETECTADOS:")
        for e in errores:
            print(f"  - {e}")
    else:
        print("=" * 50)
        print("TODOS LOS TESTS PASADOS OK")
        print("=" * 50)
