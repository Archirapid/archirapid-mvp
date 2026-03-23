"""
modules/mls/mls_mercado.py
Portal de la inmobiliaria colaboradora MLS — ArchiRapid.

Cinco secciones UI:
  1. ui_mercado_mls()               — lista de fincas disponibles con filtros
  2. ui_ficha_finca()               — ficha completa sin identidad listante
  3. ui_hacer_reserva()             — reserva 72h (STUB → Paso 12)
  4. ui_contacto_archirapid()       — consulta a ArchiRapid sobre una finca
  5. ui_mis_reservas_colaboradora() — historial de reservas propias

Función especial:
  lanzar_disenador_desde_mls()     — inyecta finca MLS en el diseñador IA 6-step

SEGURIDAD:
  - NUNCA se llama get_finca_by_id() en este módulo
  - NUNCA se muestra inmo_id en ningún elemento UI
  - comision_total_pct y comision_listante_pct de la listante NUNCA se exponen
"""
import json
import streamlit as st
from datetime import datetime, timezone

from modules.mls import mls_db
from modules.mls.mls_notificaciones import notif_finca_reservada


# =============================================================================
# CONSTANTES
# =============================================================================

_ESTADOS_VISIBLES_COLAB = (
    "publicada",
    "reservada",
    "reserva_pendiente_confirmacion",
)

_BADGE_COLAB: dict = {
    "publicada":                      "🟢 Disponible",
    "reservada":                      "🔒 Reservada",
    "reserva_pendiente_confirmacion": "🕐 Reserva pendiente",
}

_PLANES_RESERVA = {"agency", "enterprise"}


# =============================================================================
# HELPERS PRIVADOS
# =============================================================================

def _dias_en_mercado(finca: dict) -> int:
    """Calcula días transcurridos desde dias_en_mercado_inicio."""
    inicio_str = finca.get("dias_en_mercado_inicio")
    if not inicio_str:
        return 0
    try:
        inicio = datetime.fromisoformat(inicio_str)
        delta  = datetime.now(timezone.utc) - inicio
        return max(0, delta.days)
    except Exception:
        return 0


def _horas_restantes(timestamp_expira: str) -> float:
    """Horas restantes hasta timestamp_expira. Negativo si ya expiró."""
    if not timestamp_expira:
        return 0.0
    try:
        expira = datetime.fromisoformat(timestamp_expira)
        delta  = expira - datetime.now(timezone.utc)
        return round(delta.total_seconds() / 3600, 1)
    except Exception:
        return 0.0


def _get_fincas_mercado_visible(exclude_inmo_id: str | None = None) -> list:
    """
    Devuelve fincas visibles para colaboradoras:
    estado IN ('publicada', 'reservada', 'reserva_pendiente_confirmacion')
    con catastro_validada=1.
    exclude_inmo_id: filtra las fincas propias del listante (no aparecen en su mercado).
    Columnas seguras — inmo_id NUNCA incluido en el resultado.
    Devuelve [] en caso de error.
    """
    _COLS = (
        "id, secuencial, ref_codigo, catastro_ref, catastro_validada, "
        "catastro_lat, catastro_lon, titulo, descripcion_publica, notas_privadas, "
        "precio, superficie_m2, comision_archirapid_pct, comision_colaboradora_pct, "
        "split_aceptado, estado, image_paths, precio_historial, "
        "dias_en_mercado_inicio, created_at, updated_at"
    )
    try:
        from src import db as _db
        conn = _db.get_conn()
        cur  = conn.cursor()
        if exclude_inmo_id:
            cur.execute(
                f"""SELECT {_COLS}
                    FROM fincas_mls
                    WHERE catastro_validada = 1
                      AND inmo_id != ?
                      AND estado IN (
                          'publicada',
                          'reservada',
                          'reserva_pendiente_confirmacion'
                      )
                    ORDER BY created_at DESC""",
                (exclude_inmo_id,),
            )
        else:
            cur.execute(
                f"""SELECT {_COLS}
                    FROM fincas_mls
                    WHERE catastro_validada = 1
                      AND estado IN (
                          'publicada',
                          'reservada',
                          'reserva_pendiente_confirmacion'
                      )
                    ORDER BY created_at DESC"""
            )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        # Guardia defensiva
        for row in rows:
            assert "inmo_id" not in row, "SEGURIDAD: inmo_id en mercado visible"
        return rows
    except Exception:
        return []


def _colab_split_display(finca: dict) -> tuple[float, float, float, float]:
    """
    Devuelve (colab_pct, colab_eur, arch_pct, arch_eur) para mostrar a la colaboradora.
    comision_total_pct y listante_pct NO se exponen (seguridad).
    """
    precio     = float(finca.get("precio") or 0)
    colab_pct  = float(finca.get("comision_colaboradora_pct") or 0)
    arch_pct   = float(finca.get("comision_archirapid_pct") or 1.0)
    colab_eur  = round(precio * colab_pct  / 100, 2)
    arch_eur   = round(precio * arch_pct   / 100, 2)
    return colab_pct, colab_eur, arch_pct, arch_eur


# =============================================================================
# FUNCIÓN ESPECIAL — lanzar_disenador_desde_mls  (Corrección C2)
# =============================================================================

def lanzar_disenador_desde_mls(finca: dict) -> None:
    """
    Lanza el diseñador IA de 6 pasos (app.py línea 1475) con datos de la finca MLS.

    Corrección C2 aplicada:
      1. Elimina design_plot_id ANTES de inyectar datos (evita que flow.py línea 714
         sobrescriba design_plot_data desde la tabla plots).
      2. Limpia todos los campos de sesión que podrían contaminar la sesión anterior.
      3. Usa query params → rerun para enrutar al diseñador correcto (línea 1475),
         NUNCA importa disenador_vivienda.main().
    """
    # 1. Eliminar design_plot_id PRIMERO — evita sobreescritura en flow.py L714
    st.session_state.pop("design_plot_id",          None)
    st.session_state.pop("_last_design_plot_id",    None)

    # 2. Limpiar campos que sobrescribirían los datos MLS inyectados
    for _k in (
        "ai_room_proposal",
        "babylon_modified_layout",
        "current_floor_plan",
        "babylon_editor_used",
        "ai_house_requirements",
        "pago_completado",
    ):
        st.session_state.pop(_k, None)

    # 3. Marcar origen MLS para mostrar botón "Volver" en el diseñador
    st.session_state["mls_origin"] = True

    # 4. Inyectar datos de la finca MLS en design_plot_data
    superficie = float(finca.get("superficie_m2") or 0)
    st.session_state["design_plot_data"] = {
        "id":            finca["id"],
        "title":         finca["titulo"],
        "catastral_ref": finca["catastro_ref"],
        "total_m2":      superficie,
        "buildable_m2":  superficie * 0.33,
        "lat":           finca.get("catastro_lat"),
        "lon":           finca.get("catastro_lon"),
        "origen":        "mls",
    }

    # 5. Forzar paso 1 del diseñador
    st.session_state["ai_house_step"] = 1

    # 6. Navegar al diseñador 6-step (app.py L1475) — NUNCA disenador_vivienda.main()
    st.query_params["page"] = "Diseñador de Vivienda"
    st.rerun()


# =============================================================================
# SECCIÓN 1 — MERCADO MLS (vista de lista)
# =============================================================================

def ui_mercado_mls(inmo: dict) -> None:
    """Vista principal del mercado — lista de fincas disponibles para colaborar."""

    st.subheader("🏘️ Mercado MLS")

    # ── Guía de flujo (colapsada por defecto) ────────────────────────────────
    with st.expander("📖 ¿Cómo funciona la colaboración MLS? (5 pasos)", expanded=False):
        st.markdown("""
**El flujo es simple y protege a todas las partes:**

| Paso | Qué haces tú | Qué hace ArchiRapid |
|---|---|---|
| **1. Encuentras la finca** | Buscas en este mercado por precio, m², comisión | — |
| **2. Ves la ficha profesional** | REF, comisión %, importe estimado, notas privadas del listante | — |
| **3. Reservas para tu cliente (€200, 72h)** | Pulsas "Reservar €200" y pagas — exclusiva activada | Notifica al listante que hay colaboradora activa |
| **4. Coordinación de visita** | Contacta a ArchiRapid: **hola@archirapid.com** con el REF | Coordina acceso con el listante (identidad protegida) |
| **5. Cierre y comisión** | Presenta la oferta de tu cliente a ArchiRapid | Gestiona contrato, arras y reparto en notaría |

---
**Preguntas frecuentes:**

- **¿Quién es el listante?** — La identidad queda protegida hasta el cierre. Tú gestionas tu cliente, ArchiRapid coordina con el listante.
- **¿Cuánto cobro?** — Lo que ves en "Tu comisión %" y el importe en €. Se descuentan los €200 de reserva al cobrar.
- **¿Qué pasa si expira la reserva?** — La finca vuelve a estar disponible automáticamente a las 72h.
- **¿Cómo se formaliza?** — Arras → contrato privado → escritura notarial. ArchiRapid distribuye las comisiones.
- **¿Si mi cliente no compra?** — La reserva de €200 es tu coste de exclusiva. Hablamos si hubo causa justificada.
        """)

    fincas_todas = _get_fincas_mercado_visible(exclude_inmo_id=inmo.get("id"))

    if not fincas_todas:
        st.info("No hay fincas disponibles en el mercado en este momento.")
        return

    # ── Filtros ──────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros y ordenación", expanded=False):
        precios = [float(f.get("precio") or 0) for f in fincas_todas]
        p_min_global = int(min(precios)) if precios else 0
        p_max_global = int(max(precios)) if precios else 10_000_000

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            precio_rango = st.slider(
                "Rango de precio (€)",
                min_value=p_min_global,
                max_value=max(p_max_global, p_min_global + 1),
                value=(p_min_global, p_max_global),
                step=10_000,
                format="€%d",
                key="mls_merc_precio_rango",
            )
            m2_min = st.number_input(
                "Superficie mínima (m²)",
                min_value=0.0,
                value=0.0,
                step=50.0,
                format="%.0f",
                key="mls_merc_m2_min",
            )
        with col_f2:
            estado_filtro = st.selectbox(
                "Estado",
                ["Todas", "Disponibles", "Reservadas"],
                key="mls_merc_estado",
            )
            orden = st.selectbox(
                "Ordenar por",
                [
                    "Precio ↑",
                    "Precio ↓",
                    "Superficie ↑",
                    "Días en mercado ↑",
                    "Comisión colaboradora ↓",
                ],
                key="mls_merc_orden",
            )

    # ── Aplicar filtros ───────────────────────────────────────────────────────
    fincas = fincas_todas[:]

    if estado_filtro == "Disponibles":
        fincas = [f for f in fincas if f.get("estado") == "publicada"]
    elif estado_filtro == "Reservadas":
        fincas = [f for f in fincas if f.get("estado") in ("reservada", "reserva_pendiente_confirmacion")]

    fincas = [
        f for f in fincas
        if precio_rango[0] <= float(f.get("precio") or 0) <= precio_rango[1]
        and float(f.get("superficie_m2") or 0) >= m2_min
    ]

    _sort_map = {
        "Precio ↑":               lambda f: float(f.get("precio") or 0),
        "Precio ↓":               lambda f: -float(f.get("precio") or 0),
        "Superficie ↑":           lambda f: float(f.get("superficie_m2") or 0),
        "Días en mercado ↑":      lambda f: _dias_en_mercado(f),
        "Comisión colaboradora ↓": lambda f: -float(f.get("comision_colaboradora_pct") or 0),
    }
    fincas.sort(key=_sort_map.get(orden, lambda f: 0))

    st.caption(f"**{len(fincas)}** fincas encontradas")

    # ── Tarjetas ──────────────────────────────────────────────────────────────
    for finca in fincas:
        estado     = finca.get("estado", "publicada")
        badge      = _BADGE_COLAB.get(estado, f"❓ {estado}")
        ref        = finca.get("ref_codigo") or "—"
        titulo     = finca.get("titulo") or "Sin título"
        precio     = float(finca.get("precio") or 0)
        m2         = float(finca.get("superficie_m2") or 0)
        dias       = _dias_en_mercado(finca)
        colab_pct, colab_eur, _, _ = _colab_split_display(finca)

        with st.container(border=True):
            col_datos, col_btn = st.columns([4, 1])

            with col_datos:
                st.markdown(f"**{titulo}**  `{ref}`  {badge}")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Precio", f"€{precio:,.0f}")
                col_m2.metric("Superficie", f"{m2:,.0f} m²")
                col_m3.metric("Tu comisión", f"{colab_pct}%  (€{colab_eur:,.0f})")
                col_m4.metric("Días en mercado", f"{dias}d")

            with col_btn:
                if st.button(
                    "Ver ficha →",
                    key=f"mls_ver_ficha_{finca['id']}",
                    type="secondary",
                ):
                    st.session_state["mls_ficha_id"]  = finca["id"]
                    st.session_state["mls_vista"]     = "ficha"
                    st.rerun()


# =============================================================================
# SECCIÓN 2 — FICHA COMPLETA DE FINCA
# =============================================================================

def ui_ficha_finca(finca_id: str, inmo: dict) -> None:
    """
    Ficha completa de una finca para la colaboradora.
    SIEMPRE usa get_finca_sin_identidad_listante() — NUNCA get_finca_by_id().
    """

    if st.button("← Volver al mercado", key="mls_ficha_back"):
        st.session_state.pop("mls_ficha_id", None)
        st.session_state["mls_vista"] = "mercado"
        st.rerun()

    finca = mls_db.get_finca_sin_identidad_listante(finca_id)
    if finca is None:
        st.error("Finca no encontrada o no disponible.")
        return

    # Guardia defensiva: inmo_id nunca debe estar presente
    assert "inmo_id" not in finca, "SEGURIDAD: inmo_id en ficha colaboradora"

    estado    = finca.get("estado", "publicada")
    badge     = _BADGE_COLAB.get(estado, f"❓ {estado}")
    ref       = finca.get("ref_codigo") or "—"
    titulo    = finca.get("titulo") or "Sin título"
    precio    = float(finca.get("precio") or 0)
    m2        = float(finca.get("superficie_m2") or 0)
    dias      = _dias_en_mercado(finca)
    colab_pct, colab_eur, arch_pct, arch_eur = _colab_split_display(finca)

    # ── Cabecera ─────────────────────────────────────────────────────────────
    st.subheader(titulo)
    st.caption(f"`{ref}`  ·  {badge}  ·  {dias} días en mercado")

    col_p, col_m, col_d = st.columns(3)
    col_p.metric("Precio de venta", f"€{precio:,.0f}")
    col_m.metric("Superficie", f"{m2:,.0f} m²")
    col_d.metric("Edificabilidad estimada", f"{m2 * 0.33:,.0f} m²")

    # ── Descripción pública ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Descripción**")
    st.write(finca.get("descripcion_publica") or "—")

    # ── Notas privadas para colaboradoras ─────────────────────────────────────
    notas = finca.get("notas_privadas")
    if notas:
        st.markdown("---")
        with st.expander("📋 Notas para colaboradoras MLS *(Solo visible para miembros)*"):
            st.info(notas)

    # ── Split visible para la colaboradora ───────────────────────────────────
    st.markdown("---")
    st.markdown("**Reparto de comisiones si tú cierras la venta:**")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(
            f"| Concepto | % | Importe |\n"
            f"|---|---|---|\n"
            f"| **Tu comisión** | **{colab_pct}%** | **€{colab_eur:,.0f}** |\n"
            f"| ArchiRapid (fijo) | {arch_pct}% | €{arch_eur:,.0f} |\n"
            f"| Listante (confidencial) | — | — |"
        )

    # ── Botón diseñador IA ────────────────────────────────────────────────────
    with col_s2:
        if finca.get("catastro_lat") and finca.get("catastro_lon"):
            if st.button(
                "🏗️ Ver potencial constructivo con IA →",
                key=f"mls_diseñador_{finca_id}",
                help=f"Edificabilidad estimada: {m2 * 0.33:,.0f} m²",
            ):
                lanzar_disenador_desde_mls(finca)

    # ── Datos catastrales ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Datos catastrales validados:**")
    cat_ref = finca.get("catastro_ref") or "—"
    cat_lat = finca.get("catastro_lat")
    cat_lon = finca.get("catastro_lon")
    st.caption(
        f"REF catastral: `{cat_ref}`  "
        + (f"·  📍 lat={cat_lat:.5f} lon={cat_lon:.5f}" if cat_lat and cat_lon else "")
    )

    # ── Acciones según estado ─────────────────────────────────────────────────
    st.markdown("---")

    if estado == "publicada":
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button(
                "🔒 Reservar para mi cliente (€200)",
                key=f"mls_reservar_{finca_id}",
                type="primary",
            ):
                st.session_state["mls_reservar_finca"] = finca
                st.session_state["mls_vista"]          = "reservar"
                st.rerun()
        with col_r2:
            if st.button(
                "📩 Solicitar más información",
                key=f"mls_contacto_{finca_id}",
            ):
                st.session_state["mls_contacto_finca"] = finca
                st.session_state["mls_vista"]          = "contacto"
                st.rerun()

    elif estado == "reservada":
        st.warning("⏳ Esta finca tiene una reserva activa de otra colaboradora.")

    elif estado == "reserva_pendiente_confirmacion":
        st.info("🕐 Reserva de cliente pendiente de confirmación por ArchiRapid.")


# =============================================================================
# SECCIÓN 3 — HACER RESERVA (colaboradora)
# =============================================================================

def ui_hacer_reserva(finca: dict, inmo: dict) -> None:
    """
    Flujo de reserva para inmobiliaria colaboradora.
    STUB: delega el pago Stripe a mls_reservas.iniciar_reserva_colaboradora()
    que se implementará en el Paso 12.
    """

    if st.button("← Volver a la ficha", key="mls_reserva_back"):
        st.session_state["mls_vista"] = "ficha"
        st.rerun()

    st.subheader("🔒 Reservar finca")

    # ── Guardia de plan ───────────────────────────────────────────────────────
    plan = (inmo.get("plan") or "starter").lower()
    if plan not in _PLANES_RESERVA or not inmo.get("plan_activo"):
        st.warning(
            f"Las reservas como colaboradora requieren plan **AGENCY** o **ENTERPRISE**. "
            f"Tu plan actual es **{plan.upper()}**."
        )
        if st.button("⬆️ Actualizar a AGENCY", key="mls_reserva_upgrade"):
            st.session_state["mls_tab_force"] = "planes"
            st.rerun()
        return

    finca_id = finca["id"]

    # ── Verificar que no hay reserva activa ───────────────────────────────────
    reserva_existente = mls_db.get_reserva_activa_by_finca(finca_id)
    if reserva_existente:
        st.error(
            "Esta finca ya tiene una reserva activa de otra colaboradora. "
            "Podrá reservarse cuando expire (72h)."
        )
        return

    # ── Resumen de la reserva ─────────────────────────────────────────────────
    ref      = finca.get("ref_codigo") or "—"
    titulo   = finca.get("titulo") or "Sin título"
    precio   = float(finca.get("precio") or 0)
    colab_pct, colab_eur, _, _ = _colab_split_display(finca)

    st.markdown(f"**Finca:** `{ref}` — {titulo}")

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Precio de venta", f"€{precio:,.0f}")
    col_r2.metric("Tu comisión si cierras", f"€{colab_eur:,.0f}  ({colab_pct}%)")
    col_r3.metric("Importe de reserva", "€200")

    st.info(
        "✅ Los €200 de reserva se descontarán de tu comisión al cierre de la operación.  \n"
        "🔒 La exclusiva es de **72 horas** desde el momento del pago.  \n"
        "🔐 La identidad de la inmobiliaria listante se revelará tras el pago exitoso."
    )

    confirmado = st.checkbox(
        "Confirmo que tengo un cliente interesado y acepto las condiciones de la reserva.",
        key="mls_reserva_confirm",
    )

    if st.button(
        "💳 Pagar reserva €200",
        disabled=not confirmado,
        type="primary",
        key="mls_reserva_pagar_btn",
    ):
        try:
            from modules.mls import mls_reservas
            checkout_url = mls_reservas.iniciar_reserva_colaboradora(
                finca_id=finca_id,
                inmo_id=inmo["id"],
            )
            if checkout_url:
                # Auto-redirect a Stripe (misma pestaña) + botón de fallback
                st.components.v1.html(
                    f'<script>window.top.location.href="{checkout_url}";</script>',
                    height=0,
                )
                st.link_button(
                    "💳 Ir a Stripe para completar el pago →",
                    checkout_url,
                    type="primary",
                    use_container_width=True,
                )
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Error al iniciar el pago: {exc}")


# =============================================================================
# SECCIÓN 4 — CONTACTO / CONSULTA A ARCHIRAPID
# =============================================================================

def ui_contacto_archirapid(finca: dict, inmo: dict) -> None:
    """Formulario para que la colaboradora solicite información sobre una finca."""

    if st.button("← Volver a la ficha", key="mls_contacto_back"):
        st.session_state["mls_vista"] = "ficha"
        st.rerun()

    ref    = finca.get("ref_codigo") or "—"
    titulo = finca.get("titulo") or "Sin título"

    st.subheader("📩 Solicitar información")
    st.markdown(f"**Finca:** `{ref}` — {titulo}")
    st.caption(
        "ArchiRapid actúa como intermediario. Tu consulta llegará a nuestro equipo, "
        "que coordinará la respuesta con la inmobiliaria listante."
    )

    mensaje = st.text_area(
        "Tu consulta",
        max_chars=300,
        placeholder="ej. ¿Hay servidumbre de paso? ¿Se admiten ofertas?",
        key="mls_contacto_mensaje",
    )

    if st.button("📩 Enviar consulta", key="mls_contacto_enviar_btn", type="primary"):
        if not mensaje.strip():
            st.warning("Escribe un mensaje antes de enviar.")
            return

        # Registrar en notificaciones_mls con tipo 'consulta_colaboradora'
        try:
            payload = json.dumps({
                "finca_id":  finca["id"],
                "ref":       ref,
                "inmo_id":   inmo["id"],        # la colaboradora que consulta
                "nombre":    inmo.get("nombre", "—"),
                "mensaje":   mensaje.strip(),
            }, ensure_ascii=False)

            from src import db as _db
            conn = _db.get_conn()
            conn.execute(
                """INSERT INTO notificaciones_mls
                   (destinatario_tipo, destinatario_id, tipo_evento,
                    payload, timestamp, leida)
                   VALUES ('archirapid', 'admin', 'consulta_colaboradora',
                           ?, datetime('now'), 0)""",
                (payload,),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        # Notificar a ArchiRapid (no a la listante)
        try:
            notif_finca_reservada(
                ref_codigo=ref,
                inmo_listante_email="admin@archirapid.com",
            )
        except Exception:
            pass

        st.success(
            "✅ Consulta enviada. ArchiRapid te responderá en menos de 24 horas."
        )


# =============================================================================
# SECCIÓN 5 — MIS RESERVAS (colaboradora)
# =============================================================================

def ui_mis_reservas_colaboradora(inmo: dict) -> None:
    """Historial de reservas activas e históricas de esta colaboradora."""

    st.subheader("📋 Mis reservas")

    try:
        from src import db as _db
        conn = _db.get_conn()
        cur  = conn.cursor()
        # JOIN con fincas_mls para obtener REF y título, SIN inmo_id de la finca
        cur.execute(
            """SELECT r.id, r.finca_id, r.estado, r.importe_reserva,
                      r.timestamp_reserva, r.timestamp_expira_72h, r.notas,
                      f.ref_codigo, f.titulo, f.precio,
                      f.comision_colaboradora_pct
               FROM reservas_mls r
               LEFT JOIN fincas_mls f ON r.finca_id = f.id
               WHERE r.inmo_colaboradora_id = ?
               ORDER BY r.timestamp_reserva DESC""",
            (inmo["id"],),
        )
        reservas = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception:
        reservas = []

    if not reservas:
        st.info("No tienes reservas registradas todavía.")
        return

    activas = [r for r in reservas if r.get("estado") == "activa"]
    if activas:
        st.caption(f"**{len(activas)} reserva(s) activa(s)**")

    for res in reservas:
        estado_res  = res.get("estado", "—")
        ref         = res.get("ref_codigo") or "—"
        titulo      = res.get("titulo") or "—"
        precio      = float(res.get("precio") or 0)
        importe     = float(res.get("importe_reserva") or 200)
        ts_reserva  = (res.get("timestamp_reserva") or "")[:16].replace("T", " ")
        ts_expira   = res.get("timestamp_expira_72h") or ""
        colab_pct   = float(res.get("comision_colaboradora_pct") or 0)
        colab_eur   = round(precio * colab_pct / 100, 0)
        horas_left  = _horas_restantes(ts_expira)

        with st.container(border=True):
            col_i, col_m = st.columns([3, 1])
            with col_i:
                st.markdown(f"**`{ref}`** — {titulo}")
                st.caption(f"Reservada el {ts_reserva}  ·  Importe: €{importe:.0f}")
            with col_m:
                if estado_res == "activa" and horas_left > 0:
                    st.metric("Tiempo restante", f"{horas_left:.1f}h")
                    st.caption("Exclusiva activa")
                else:
                    st.caption(f"Estado: **{estado_res}**")

            if precio > 0 and colab_pct > 0:
                st.caption(f"Comisión potencial si cierras: **€{colab_eur:,.0f}** ({colab_pct}%)")

            # Próximos pasos — solo para reservas activas con tiempo restante
            if estado_res == "activa" and horas_left > 0:
                with st.expander("📋 ¿Qué hago ahora? — Próximos pasos", expanded=True):
                    st.markdown(f"""
**Tu exclusiva de 72h está activa.** Tienes **{horas_left:.1f}h** para avanzar.

**① Coordina la visita ahora mismo**
Escribe a ArchiRapid indicando el REF `{ref}`:
- 📧 **hola@archirapid.com**
- O usa el botón "📩 Solicitar más información" en la ficha de la finca

**② Presenta la oferta de tu cliente**
Si tu cliente quiere comprar, comunícalo a ArchiRapid con:
- Precio de oferta
- Forma de pago (hipoteca / contado)
- Plazo deseado para arras

**③ ArchiRapid coordina con el listante**
La identidad del listante y sus datos de contacto se revelan en esta fase, coordinados por ArchiRapid.

**④ Firma de arras y escritura**
Contrato privado → notaría → ArchiRapid distribuye comisiones.
Tu comisión de **€{colab_eur:,.0f}** se abona al cierre (menos los €200 ya pagados).

---
*¿Tienes dudas? Contacta: hola@archirapid.com · Ref: `{ref}`*
                    """)


# =============================================================================
# ORQUESTADOR PRINCIPAL
# =============================================================================

def main(inmo: dict) -> None:
    """
    Portal de la colaboradora MLS. Llamado desde mls_portal.py.

    Guardias:
      - plan_activo = 0 → solo mensaje de activación
      - firma_hash = None → redirige a firma
    """

    # ── Guardia 1: plan activo ────────────────────────────────────────────────
    if not inmo.get("plan_activo"):
        st.warning(
            "Tu plan MLS no está activo. Activa un plan para acceder al mercado."
        )
        if st.button("💳 Ver planes disponibles", key="mls_mercado_ver_planes"):
            st.session_state["mls_tab_force"] = "planes"
            st.rerun()
        return

    # ── Guardia 2: acuerdo firmado ────────────────────────────────────────────
    if not inmo.get("firma_hash"):
        st.warning(
            "Debes firmar el Acuerdo de Colaboración MLS antes de acceder al mercado."
        )
        st.info("Ve a la sección **Acuerdo** de tu panel para firmarlo.")
        return

    # ── Router de vistas ─────────────────────────────────────────────────────
    vista = st.session_state.get("mls_vista", "mercado")

    if vista == "mercado":
        tab_mercado, tab_mis_reservas = st.tabs([
            "🏘️ Mercado",
            "📋 Mis Reservas",
        ])
        with tab_mercado:
            ui_mercado_mls(inmo)
        with tab_mis_reservas:
            ui_mis_reservas_colaboradora(inmo)

    elif vista == "ficha":
        finca_id = st.session_state.get("mls_ficha_id")
        if finca_id:
            ui_ficha_finca(finca_id, inmo)
        else:
            st.session_state["mls_vista"] = "mercado"
            st.rerun()

    elif vista == "reservar":
        finca = st.session_state.get("mls_reservar_finca")
        if finca:
            ui_hacer_reserva(finca, inmo)
        else:
            st.session_state["mls_vista"] = "mercado"
            st.rerun()

    elif vista == "contacto":
        finca = st.session_state.get("mls_contacto_finca")
        if finca:
            ui_contacto_archirapid(finca, inmo)
        else:
            st.session_state["mls_vista"] = "mercado"
            st.rerun()

    else:
        st.session_state["mls_vista"] = "mercado"
        st.rerun()
