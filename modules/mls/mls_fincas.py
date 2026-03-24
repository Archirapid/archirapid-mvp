"""
modules/mls/mls_fincas.py
Portal completo del listante MLS — ArchiRapid.

Cuatro secciones UI:
  1. ui_subir_finca()     — formulario upload + validación catastral
  2. ui_mis_fincas()      — cartera de fincas con gestión
  3. ui_solicitudes_visita() — contactos de clientes
  4. ui_estadisticas()    — métricas del listante

Importa: streamlit, mls_db, mls_comisiones, mls_notificaciones
No modifica owners.py ni marketplace.py.
Todas las operaciones BD exclusivamente via mls_db.
"""
import json
import streamlit as st
from datetime import datetime, timezone, timedelta

from modules.mls import mls_db
from modules.mls.mls_comisiones import (
    calcular_split,
    calcular_split_sugerido,
    get_siguiente_secuencial,
    generar_ref_codigo,
)
from modules.mls.mls_notificaciones import notif_finca_publicada

# =============================================================================
# CONSTANTES
# =============================================================================

_LIMITE_PLAN: dict = {
    "starter":    15,
    "agency":     75,
    "enterprise": float("inf"),
}

_ESTADOS_INACTIVOS = {"cerrada", "eliminada", "expirada"}

_BADGE: dict = {
    "pendiente_validacion":           "🟡 Pendiente validación",
    "validada_pendiente_aprobacion":  "🔵 Pendiente aprobación",
    "periodo_privado":                "🟠 Período privado",
    "publicada":                      "🟢 Publicada",
    "reservada":                      "🔒 Reservada",
    "reserva_pendiente_confirmacion": "🔒 Reserva pendiente",
    "cerrada":                        "⚫ Cerrada",
    "eliminada":                      "⚫ Eliminada",
    "expirada":                       "🔴 Expirada",
    "pausada":                        "🔴 Pausada",
}

# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _set_periodo_privado_expira(finca_id: str) -> None:
    """Guarda periodo_privado_expira = now + 48h en la finca (columna no cubierta por create_finca)."""
    from src import db as _db
    expira = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(timespec="seconds")
    conn = _db.get_conn()
    try:
        conn.execute(
            "UPDATE fincas_mls SET periodo_privado_expira = ? WHERE id = ?",
            (expira, finca_id),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _contar_fincas_activas(inmo_id: str) -> int:
    """Cuenta fincas activas (excluyendo estados inactivos)."""
    fincas = mls_db.get_fincas_by_inmo(inmo_id)
    return sum(1 for f in fincas if f.get("estado") not in _ESTADOS_INACTIVOS)


def _dias_en_mercado(finca: dict) -> int:
    """Calcula días transcurridos desde dias_en_mercado_inicio."""
    inicio_str = finca.get("dias_en_mercado_inicio")
    if not inicio_str:
        return 0
    try:
        inicio = datetime.fromisoformat(inicio_str)
        delta = datetime.now(timezone.utc) - inicio
        return max(0, delta.days)
    except Exception:
        return 0


# =============================================================================
# SECCIÓN 1 — SUBIR FINCA
# =============================================================================

def ui_subir_finca(inmo: dict) -> None:
    """Formulario completo para publicar una nueva finca MLS."""

    st.subheader("📤 Publicar nueva finca")

    # ── Guardia: límite de plan ──────────────────────────────────────────────
    plan = inmo.get("plan", "starter").lower()
    limite = _LIMITE_PLAN.get(plan, 15)
    activas = _contar_fincas_activas(inmo["id"])

    if limite != float("inf") and activas >= limite:
        st.warning(
            f"Has alcanzado el límite de **{int(limite)} fincas activas** "
            f"para el plan **{plan.upper()}**. "
            f"Cierra o vende alguna finca, o actualiza tu plan para continuar."
        )
        if st.button("⬆️ Actualizar plan", key="mls_upgrade_plan_btn"):
            st.session_state["mls_tab_force"] = "planes"
            st.rerun()
        return

    # ── Estado de validación catastral en session_state ──────────────────────
    _SS_CAT = "mls_subir_catastro"        # dict con resultado de validación
    _SS_REF = "mls_subir_ref_input"       # referencia catastral ingresada

    # ── BLOQUE 1 — Validación catastral ─────────────────────────────────────
    st.markdown("#### 📋 Paso 1 — Identificación catastral")

    # ── Opción A: subir PDF nota catastral → Gemini extrae la REF y m² ──────
    with st.expander("📄 Subir Nota Catastral (PDF) — extracción automática con IA", expanded=False):
        st.caption("Opcional. Sube el PDF y la IA extraerá la referencia catastral y la superficie automáticamente.")
        pdf_nota = st.file_uploader(
            "Nota Catastral (PDF)",
            type=["pdf"],
            key="mls_subir_nota_pdf",
        )
        if pdf_nota and st.button("👁️ Extraer datos con IA", key="mls_extraer_nota_btn"):
            with st.spinner("Analizando PDF con Gemini Vision…"):
                try:
                    import os
                    from modules.marketplace.utils import save_upload
                    save_path = save_upload(pdf_nota, prefix="nota_catastral_mls")
                    from modules.marketplace.ai_engine import extraer_datos_nota_catastral
                    resultado = extraer_datos_nota_catastral(save_path)
                    if isinstance(resultado, dict) and "error" in resultado:
                        st.error(f"Error IA: {resultado['error']}")
                    elif all(k in resultado for k in ["referencia_catastral", "superficie_grafica_m2", "municipio"]):
                        st.session_state["mls_subir_ref_catastral"] = resultado["referencia_catastral"]
                        st.session_state["mls_nota_m2_auto"] = resultado["superficie_grafica_m2"]
                        st.success(
                            f"✅ Datos extraídos  \n"
                            f"REF: **{resultado['referencia_catastral']}**  \n"
                            f"Superficie: **{resultado['superficie_grafica_m2']} m²**  \n"
                            f"Municipio: **{resultado['municipio']}**"
                        )
                        st.info("Los campos se han rellenado automáticamente. Pulsa 'Validar referencia' para confirmar.")
                        st.rerun()
                    else:
                        st.warning("No se pudieron extraer todos los datos. Introduce la referencia manualmente.")
                except Exception as exc:
                    st.error(f"Error procesando PDF: {exc}")

    ref_catastral = st.text_input(
        "Referencia Catastral *",
        placeholder="ej. 9872023VH5797S0001WX",
        help="20 caracteres. Encuéntrala en el recibo del IBI o en sede.catastro.gob.es",
        key="mls_subir_ref_catastral",
    )

    cat_data = st.session_state.get(_SS_CAT)

    if st.button("🔍 Validar referencia", key="mls_validar_catastro_btn"):
        if not ref_catastral or len(ref_catastral.strip()) < 14:
            st.error("Introduce una referencia catastral válida (mínimo 14 caracteres).")
        else:
            with st.spinner("Consultando Sede Electrónica del Catastro…"):
                try:
                    from modules.marketplace.catastro_api import fetch_by_ref_catastral
                    resultado = fetch_by_ref_catastral(ref_catastral.strip().upper())
                except Exception as exc:
                    resultado = {"estado": "error_api", "ubicacion_geo": None}

            if resultado.get("estado") == "validado_oficial":
                st.session_state[_SS_CAT] = resultado
                cat_data = resultado
                geo = resultado.get("ubicacion_geo") or {}
                st.success(
                    f"✅ Referencia catastral validada  \n"
                    f"📍 {geo.get('direccion_completa', '—')}  \n"
                    f"🏘️ Municipio: {geo.get('municipio', '—')}"
                )
            else:
                st.session_state.pop(_SS_CAT, None)
                cat_data = None
                st.error(
                    "❌ Referencia catastral no encontrada o inválida. "
                    "Verifica que los 20 caracteres son correctos."
                )

    if cat_data:
        geo = cat_data.get("ubicacion_geo") or {}
        st.caption(
            f"✅ Catastro validado · "
            f"lat={geo.get('lat', '—'):.5f} lon={geo.get('lng', '—'):.5f}"
        )
    else:
        st.info("Introduce y valida la referencia catastral para continuar.")
        return  # ← bloqueado hasta validación

    # ── BLOQUE 2 — Datos de la finca ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🏠 Paso 2 — Datos de la finca")

    titulo = st.text_input(
        "Título de la finca *",
        max_chars=100,
        placeholder="ej. Finca rústica con olivos en Extremadura",
        key="mls_subir_titulo",
    )
    descripcion_publica = st.text_area(
        "Descripción pública *(visible para colaboradoras y clientes)*",
        max_chars=500,
        height=120,
        placeholder="Describe la finca tal como la verán las colaboradoras y compradores.",
        key="mls_subir_desc_publica",
    )
    notas_privadas = st.text_area(
        "Notas privadas para colaboradoras *(NO visible en el mapa público)*",
        max_chars=300,
        height=80,
        placeholder="Información adicional solo para colaboradoras MLS.",
        key="mls_subir_notas_privadas",
    )

    col_precio, col_m2 = st.columns(2)
    with col_precio:
        precio = st.number_input(
            "Precio de venta (€) *",
            min_value=1_000.0,
            max_value=50_000_000.0,
            step=1_000.0,
            format="%.0f",
            key="mls_subir_precio",
        )
    with col_m2:
        # Prellenar con superficie catastral si disponible
        m2_cat = float(cat_data.get("superficie_m2") or 0)
        superficie_m2 = st.number_input(
            "Superficie (m²) *",
            min_value=1.0,
            max_value=1_000_000.0,
            value=m2_cat if m2_cat > 0 else 100.0,
            step=10.0,
            format="%.0f",
            help="Pre-rellenado desde el catastro. Edítalo si está desactualizado.",
            key="mls_subir_m2",
        )

    # ── BLOQUE 2b — Características del solar (mismos campos que propietarios) ─
    st.markdown("---")
    st.markdown("#### 🧩 Paso 2b — Características del solar")

    col_tipo, col_forma = st.columns(2)
    with col_tipo:
        tipo_suelo = st.selectbox(
            "Tipo de suelo *",
            ["Urbana", "Industrial"],
            help="Solo se admiten fincas Urbanas e Industriales.",
            key="mls_subir_tipo_suelo",
        )
    with col_forma:
        forma_solar = st.selectbox(
            "Forma del solar",
            ["Rectangular", "Cuadrado", "Irregular simple"],
            help="Ayuda a la IA a generar diseños más precisos.",
            key="mls_subir_forma_solar",
        )

    col_orient, col_serv = st.columns(2)
    with col_orient:
        orientacion = st.selectbox(
            "Orientación del norte",
            ["Norte arriba", "Norte derecha", "Norte abajo", "Norte izquierda"],
            help="Afecta a la luz natural y al diseño arquitectónico.",
            key="mls_subir_orientacion",
        )
    with col_serv:
        servicios_sel = st.multiselect(
            "Servicios disponibles",
            ["Agua", "Luz", "Alcantarillado", "Gas", "Fibra Óptica"],
            key="mls_subir_servicios",
        )

    # ── BLOQUE 3 — Comisión y split ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💶 Paso 3 — Comisión y reparto")

    comision_total_pct = st.slider(
        "Comisión total que cobras al comprador (%)",
        min_value=1.5,
        max_value=20.0,
        step=0.5,
        value=6.0,
        help="ArchiRapid siempre retiene el 1% fijo de esta comisión.",
        key="mls_subir_comision_total",
    )

    # Calcular split sugerido
    canal = round(comision_total_pct - 1.0, 10)
    col_sugerida_min = round(canal * 0.30, 1)
    col_sugerida_max = round(canal * 0.70, 1)
    col_sugerida_def = round(canal * 0.50, 1)

    # Mostrar tabla de split automático
    try:
        split_preview = calcular_split_sugerido(precio, comision_total_pct)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("ArchiRapid (fijo)", f"{split_preview['archirapid_pct']}%",
                      f"€{split_preview['archirapid_eur']:,.0f}")
        with col_b:
            st.metric("Para colaboradora", f"{split_preview['colaboradora_pct']}%",
                      f"€{split_preview['colaboradora_eur']:,.0f}")
        with col_c:
            st.metric("Te quedas tú", f"{split_preview['listante_pct']}%",
                      f"€{split_preview['listante_eur']:,.0f}")
    except Exception:
        pass

    # Slider de colaboradora (rango 30-70% del canal)
    step_col = 0.5
    min_col = max(step_col, round(col_sugerida_min / step_col) * step_col)
    max_col = max(min_col + step_col, round(col_sugerida_max / step_col) * step_col)
    def_col = min(max_col, max(min_col, round(col_sugerida_def / step_col) * step_col))

    colaboradora_pct = st.slider(
        "Comisión que ofreces a la colaboradora (%)",
        min_value=min_col,
        max_value=max_col,
        step=step_col,
        value=def_col,
        help="Más comisión = más colaboradoras intentarán vender tu finca. "
             "El rango obligatorio es 30%-70% del canal disponible.",
        key="mls_subir_colab_pct",
    )

    # Actualizar tabla con valor personalizado del colaboradora_pct
    try:
        split_custom = calcular_split(precio, comision_total_pct, colaboradora_pct)
        listante_pct  = split_custom["listante_pct"]
        listante_eur  = split_custom["listante_eur"]
        colab_eur     = split_custom["colaboradora_eur"]
        arch_eur      = split_custom["archirapid_eur"]
        st.caption(
            f"Con este split: ArchiRapid **€{arch_eur:,.0f}** · "
            f"Colaboradora **€{colab_eur:,.0f}** · "
            f"Tú **€{listante_eur:,.0f}**"
        )
    except Exception:
        listante_pct = col_sugerida_def

    # Preview del código REF
    anio = datetime.now(timezone.utc).year
    st.info(
        f"Código REF que se generará: "
        f"**AR-{anio}-XXXXX | {comision_total_pct}-{colaboradora_pct}-1**"
    )

    split_aceptado = st.checkbox(
        "✅ Acepto el split de comisiones descrito arriba",
        key="mls_subir_split_ok",
    )

    # ── BLOQUE 4 — Opciones adicionales ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚙️ Paso 4 — Opciones adicionales")

    periodo_privado = st.checkbox(
        "Período privado 48h — Solo yo puedo ver esta finca durante 48h antes "
        "de publicarse al mercado abierto de colaboradoras",
        key="mls_subir_periodo_privado",
    )

    fotos_subidas = st.file_uploader(
        "Fotos de la finca (máx. 5)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="mls_subir_fotos",
    )

    # ── Botón final ──────────────────────────────────────────────────────────
    st.markdown("---")
    puede_publicar = (
        cat_data is not None
        and bool(titulo.strip())
        and precio >= 1_000
        and split_aceptado
    )

    btn_publicar = st.button(
        "📤 Publicar finca",
        disabled=not puede_publicar,
        type="primary",
        key="mls_subir_publicar_btn",
    )

    if btn_publicar and puede_publicar:
        geo = cat_data.get("ubicacion_geo") or {}
        lat = geo.get("lat")
        lng = geo.get("lng")

        # 1. Guardar fotos
        photo_paths = []
        if fotos_subidas:
            try:
                from modules.marketplace.utils import save_upload
                for f in fotos_subidas[:5]:
                    path = save_upload(f, prefix="finca_mls")
                    photo_paths.append(path)
            except Exception:
                pass

        # 2. Calcular split definitivo
        try:
            split_final = calcular_split(precio, comision_total_pct, colaboradora_pct)
            colab_pct_final   = split_final["colaboradora_pct"]
            listante_pct_final = split_final["listante_pct"]
        except Exception:
            colab_pct_final    = colaboradora_pct
            listante_pct_final = round(comision_total_pct - 1.0 - colaboradora_pct, 2)

        datos = {
            "catastro_ref":             ref_catastral.strip().upper(),
            "titulo":                   titulo.strip(),
            "descripcion_publica":      descripcion_publica.strip(),
            "notas_privadas":           notas_privadas.strip(),
            "precio":                   float(precio),
            "superficie_m2":            float(superficie_m2),
            "tipo_suelo":               tipo_suelo,
            "servicios":                json.dumps(servicios_sel) if servicios_sel else None,
            "forma_solar":              forma_solar,
            "orientacion":              orientacion,
            "comision_total_pct":       comision_total_pct,
            "comision_colaboradora_pct": colab_pct_final,
            "comision_listante_pct":    listante_pct_final,
            "split_aceptado":           1,
            "image_paths":              json.dumps(photo_paths) if photo_paths else None,
            "precio_historial":         json.dumps([{"precio": float(precio),
                                                     "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds")}]),
        }

        with st.spinner("Registrando finca…"):
            # 2. create_finca → estado inicial pendiente_validacion
            finca_id = mls_db.create_finca(inmo["id"], datos)
            if not finca_id:
                st.error("Error al registrar la finca. Inténtalo de nuevo.")
                return

            # 3. Actualizar catastro + estado (+ dirección y municipio del API)
            if lat and lng:
                _cat_dir = geo.get("direccion_completa") or None
                _cat_mun = geo.get("municipio") or None
                mls_db.update_finca_catastro(
                    finca_id, lat=lat, lon=lng, validada=1,
                    direccion=_cat_dir, municipio=_cat_mun,
                )
                mls_db.update_finca_estado(finca_id, "validada_pendiente_aprobacion")
            else:
                st.warning("No se pudo obtener coordenadas del catastro. "
                           "La finca queda en revisión manual.")

            # 4. Generar REF código
            try:
                conn_seq = mls_db._get_conn()
                secuencial = get_siguiente_secuencial(conn_seq)
                conn_seq.close()
                ref_codigo = generar_ref_codigo(
                    secuencial, comision_total_pct, colab_pct_final
                )
                mls_db.update_finca_ref_codigo(finca_id, ref_codigo, secuencial)
            except Exception:
                ref_codigo = f"AR-{datetime.now(timezone.utc).year}-XXXXX"

            # 5. Período privado
            if periodo_privado:
                try:
                    mls_db.update_finca_estado(finca_id, "periodo_privado")
                    _set_periodo_privado_expira(finca_id)
                except Exception:
                    pass

            # 6. Notificación
            try:
                notif_finca_publicada(
                    ref_codigo=ref_codigo,
                    titulo=titulo.strip(),
                    precio=float(precio),
                    inmo_email=inmo.get("email", ""),
                )
            except Exception:
                pass

        # 7. Limpiar session_state de validación
        st.session_state.pop(_SS_CAT, None)

        st.success(
            f"✅ Finca enviada para aprobación. REF provisional: **{ref_codigo}**  \n"
            f"ArchiRapid la revisará antes de publicarla en el mapa."
        )
        st.rerun()


# =============================================================================
# SECCIÓN 2 — MIS FINCAS
# =============================================================================

def ui_mis_fincas(inmo: dict) -> None:
    """Cartera de fincas del listante con gestión básica."""

    st.subheader("🏠 Mis fincas")

    fincas = mls_db.get_fincas_by_inmo(inmo["id"])
    if not fincas:
        st.info("Aún no tienes fincas publicadas. Ve a **Subir Finca** para empezar.")
        return

    for finca in fincas:
        finca_id = finca["id"]
        estado   = finca.get("estado", "pendiente_validacion")
        badge    = _BADGE.get(estado, f"❓ {estado}")
        ref      = finca.get("ref_codigo") or "—"
        precio   = float(finca.get("precio") or 0)
        titulo   = finca.get("titulo") or "Sin título"
        dias     = _dias_en_mercado(finca)

        with st.container(border=True):
            col_info, col_acciones = st.columns([3, 1])

            with col_info:
                st.markdown(f"**{titulo}**  `{ref}`")
                st.caption(
                    f"{badge} · €{precio:,.0f} · {dias} días en mercado"
                )

            with col_acciones:
                # Pausar / Reactivar
                if estado == "publicada":
                    if st.button("⏸ Pausar", key=f"mls_pausar_{finca_id}"):
                        try:
                            mls_db.update_finca_estado(finca_id, "pausada")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                elif estado == "pausada":
                    if st.button("▶️ Reactivar", key=f"mls_reactivar_{finca_id}"):
                        try:
                            mls_db.update_finca_estado(finca_id, "publicada")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

            # Edición inline (solo precio y descripción)
            with st.expander(f"✏️ Editar {ref}", expanded=False):
                nuevo_precio = st.number_input(
                    "Nuevo precio (€)",
                    min_value=1_000.0,
                    value=float(precio),
                    step=1_000.0,
                    format="%.0f",
                    key=f"mls_edit_precio_{finca_id}",
                )
                nueva_desc = st.text_area(
                    "Descripción pública",
                    value=finca.get("descripcion_publica") or "",
                    max_chars=500,
                    key=f"mls_edit_desc_{finca_id}",
                )
                if st.button("💾 Guardar cambios", key=f"mls_save_{finca_id}"):
                    try:
                        from src import db as _db
                        conn = _db.get_conn()
                        conn.execute(
                            """UPDATE fincas_mls
                               SET precio = ?, descripcion_publica = ?, updated_at = ?
                               WHERE id = ?""",
                            (float(nuevo_precio), nueva_desc.strip(),
                             datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             finca_id),
                        )
                        conn.commit()
                        conn.close()
                        st.success("Cambios guardados.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error al guardar: {exc}")


# =============================================================================
# SECCIÓN 3 — SOLICITUDES DE VISITA / CONTACTO
# =============================================================================

def ui_solicitudes_visita(inmo: dict) -> None:
    """
    Lista de contactos de clientes interesados en las fincas del listante.
    El email del cliente NO se muestra — el contacto pasa siempre por ArchiRapid.
    """
    st.subheader("📬 Solicitudes de clientes")

    # Obtener notificaciones de contacto para las fincas de esta inmo
    fincas_propias = {f["id"]: f for f in mls_db.get_fincas_by_inmo(inmo["id"])}
    if not fincas_propias:
        st.info("No tienes fincas publicadas.")
        return

    # Buscar notificaciones no leídas y leídas de tipo contacto
    try:
        from src import db as _db
        conn = _db.get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, destinatario_id, tipo_evento, payload, timestamp, leida
               FROM notificaciones_mls
               WHERE tipo_evento = 'contacto_cliente_finca'
               ORDER BY timestamp DESC
               LIMIT 100"""
        )
        todas = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception:
        todas = []

    # Filtrar: solo las que pertenecen a fincas de esta inmo
    solicitudes = []
    for n in todas:
        try:
            payload = json.loads(n.get("payload") or "{}")
            if payload.get("finca_id") in fincas_propias:
                n["_payload"] = payload
                solicitudes.append(n)
        except Exception:
            pass

    if not solicitudes:
        st.info("No has recibido solicitudes de información todavía.")
    else:
        no_leidas = [s for s in solicitudes if not s.get("leida")]
        if no_leidas:
            st.caption(f"**{len(no_leidas)} sin atender**")

        for sol in solicitudes:
            pl       = sol.get("_payload", {})
            finca_id = pl.get("finca_id", "—")
            finca    = fincas_propias.get(finca_id, {})
            ref      = finca.get("ref_codigo") or finca_id
            titulo   = finca.get("titulo") or "—"
            nombre   = pl.get("nombre", "Cliente anónimo")
            mensaje  = pl.get("mensaje", "")
            ts       = sol.get("timestamp", "")[:16].replace("T", " ")
            leida    = bool(sol.get("leida"))

            with st.container(border=True):
                col_txt, col_btn = st.columns([4, 1])
                with col_txt:
                    st.markdown(
                        f"**{nombre}** · `{ref}` {titulo}  \n"
                        f"*{mensaje[:200]}*  \n"
                        f"<small style='color:gray;'>{ts}</small>",
                        unsafe_allow_html=True,
                    )
                    if leida:
                        st.caption("✅ Atendida")
                with col_btn:
                    if not leida:
                        if st.button("✅ Atendida", key=f"mls_leida_{sol['id']}"):
                            mls_db.marcar_leida(sol["id"])
                            st.rerun()

    # ── Mis solicitudes de colaboración enviadas ──────────────────────────────
    st.markdown("---")
    st.subheader("🤝 Mis solicitudes de colaboración enviadas")
    try:
        from src import db as _db_sc
        _conn_sc = _db_sc.get_conn()
        _cur_sc  = _conn_sc.cursor()
        _cur_sc.execute(
            """SELECT id, tipo_evento, payload, timestamp
               FROM notificaciones_mls
               WHERE destinatario_id = ?
                 AND tipo_evento IN (
                     'solicitud_colaboracion_enviada',
                     'solicitud_colaboracion_confirmada',
                     'solicitud_colaboracion_rechazada'
                 )
               ORDER BY timestamp DESC
               LIMIT 30""",
            (inmo["id"],),
        )
        _sol_rows = [dict(r) for r in _cur_sc.fetchall()]
        _conn_sc.close()
    except Exception:
        _sol_rows = []

    if not _sol_rows:
        st.info("No has enviado solicitudes de colaboración todavía.")
    else:
        for _sr in _sol_rows:
            try:
                _sp = json.loads(_sr.get("payload") or "{}")
            except Exception:
                _sp = {}
            _sref  = _sp.get("ref_codigo") or "—"
            _smsg  = _sp.get("mensaje") or ""
            _sts   = (_sr.get("timestamp") or "")[:16].replace("T", " ")
            _stipo = _sr.get("tipo_evento", "")
            if _stipo == "solicitud_colaboracion_confirmada":
                _badge = "✅ Confirmada"
                _color = "#22c55e"
            elif _stipo == "solicitud_colaboracion_rechazada":
                _badge = "❌ Rechazada"
                _color = "#ef4444"
            else:
                _badge = "⏳ Pendiente"
                _color = "#f59e0b"
            with st.container(border=True):
                st.markdown(
                    f"<span style='color:{_color};font-weight:700;'>{_badge}</span> "
                    f"· REF `{_sref}` · <small style='color:gray;'>{_sts}</small>",
                    unsafe_allow_html=True,
                )
                if _smsg:
                    st.caption(_smsg)


# =============================================================================
# SECCIÓN 4 — ESTADÍSTICAS
# =============================================================================

def ui_estadisticas(inmo: dict) -> None:
    """Métricas del listante."""

    st.subheader("📊 Estadísticas")

    fincas = mls_db.get_fincas_by_inmo(inmo["id"])
    if not fincas:
        st.info("Aún no tienes fincas para mostrar estadísticas.")
        return

    total   = len(fincas)
    activas = sum(1 for f in fincas if f.get("estado") not in _ESTADOS_INACTIVOS)
    cerradas = sum(1 for f in fincas if f.get("estado") == "cerrada")

    # Reservas históricas en fincas propias
    finca_ids = [f["id"] for f in fincas]
    reservas_total = 0
    try:
        from src import db as _db
        conn = _db.get_conn()
        cur = conn.cursor()
        placeholders = ",".join("?" * len(finca_ids))
        cur.execute(
            f"SELECT COUNT(*) FROM reservas_mls WHERE finca_id IN ({placeholders})",
            finca_ids,
        )
        row = cur.fetchone()
        reservas_total = int(row[0]) if row else 0
        conn.close()
    except Exception:
        pass

    # Días en mercado promedio (solo fincas activas con fecha)
    dias_lista = [_dias_en_mercado(f) for f in fincas
                  if f.get("estado") not in _ESTADOS_INACTIVOS
                  and f.get("dias_en_mercado_inicio")]
    dias_prom = round(sum(dias_lista) / len(dias_lista), 1) if dias_lista else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fincas activas", f"{activas}/{total}")
    col2.metric("Reservas recibidas", reservas_total)
    col3.metric("Días promedio en mercado", dias_prom)
    col4.metric("Fincas cerradas (vendidas)", cerradas)

    # Desglose por estado
    st.markdown("---")
    st.markdown("**Desglose por estado:**")
    conteo_estado: dict = {}
    for f in fincas:
        e = f.get("estado", "desconocido")
        conteo_estado[e] = conteo_estado.get(e, 0) + 1
    for estado, cnt in sorted(conteo_estado.items()):
        badge = _BADGE.get(estado, f"❓ {estado}")
        st.write(f"- {badge}: **{cnt}**")


# =============================================================================
# ORQUESTADOR PRINCIPAL
# =============================================================================

def main(inmo: dict) -> None:
    """
    Portal del listante MLS. Se llama desde mls_portal.py cuando el usuario
    está autenticado con rol listante.

    Guardias:
      - plan_activo = 0 → solo mensaje de activación
      - firma_hash = None → redirige a firma antes de cualquier contenido
    """

    # ── Guardia 1: plan activo ────────────────────────────────────────────────
    if not inmo.get("plan_activo"):
        st.warning(
            "Tu plan MLS no está activo. Activa un plan para empezar a publicar fincas."
        )
        if st.button("💳 Ver planes disponibles", key="mls_fincas_ver_planes"):
            st.session_state["mls_tab_force"] = "planes"
            st.rerun()
        return

    # ── Guardia 2: acuerdo firmado ────────────────────────────────────────────
    if not inmo.get("firma_hash"):
        st.warning(
            "Debes firmar el Acuerdo de Colaboración MLS antes de publicar fincas."
        )
        st.info("Ve a la sección **Acuerdo** de tu panel para firmarlo.")
        return

    # ── Tabs del portal del listante ─────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Subir Finca",
        "🏠 Mis Fincas",
        "📬 Solicitudes",
        "📊 Estadísticas",
    ])

    with tab1:
        ui_subir_finca(inmo)
    with tab2:
        ui_mis_fincas(inmo)
    with tab3:
        ui_solicitudes_visita(inmo)
    with tab4:
        ui_estadisticas(inmo)
