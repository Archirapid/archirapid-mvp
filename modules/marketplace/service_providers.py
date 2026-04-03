# modules/marketplace/service_providers.py
"""
Panel de Proveedores / Constructores — ArchiRapid
• Registro con especialidades múltiples y tarifas €/m²
• Panel: Tablón de Obras · Mis Ofertas · Mi Perfil
• Sincronizado con presupuesto del Diseñador IA (paso 5)
"""
import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
from .utils import db_conn
from werkzeug.security import generate_password_hash

# ── Provincias de cobertura para matching ─────────────────────────────────────
_PROVINCIAS_ESPAÑA = [
    "Álava", "Albacete", "Alicante", "Almería", "Asturias", "Ávila",
    "Badajoz", "Barcelona", "Burgos", "Cáceres", "Cádiz", "Cantabria",
    "Castellón", "Ciudad Real", "Córdoba", "Cuenca", "Girona", "Granada",
    "Guadalajara", "Guipúzcoa", "Huelva", "Huesca", "Islas Baleares",
    "Jaén", "La Coruña", "La Rioja", "Las Palmas", "León", "Lérida",
    "Lugo", "Madrid", "Málaga", "Murcia", "Navarra", "Ourense", "Palencia",
    "Pontevedra", "Salamanca", "Santa Cruz de Tenerife", "Segovia",
    "Sevilla", "Soria", "Tarragona", "Teruel", "Toledo", "Valencia",
    "Valladolid", "Vizcaya", "Zamora", "Zaragoza", "Ceuta", "Melilla",
]

# ── Especialidades disponibles ─────────────────────────────────────────────────
_ESPECIALIDADES = [
    "constructor",
    "estructura",
    "cimentacion",
    "cerramientos",
    "instalaciones_electricas",
    "instalaciones_fontaneria",
    "climatizacion",
    "acabados_interiores",
    "tejados_cubiertas",
    "sostenibilidad_energia",
    "direccion_obra",
    "aparejador",
    "reformas_integrales",
    "prefabricadas",
    "topografia",
    "bim",
]

_ESP_LABELS = {
    "constructor":              "🏗️ Constructor general",
    "estructura":               "🏛️ Estructura",
    "cimentacion":              "⚓ Cimentación",
    "cerramientos":             "🧱 Cerramientos y fachada",
    "instalaciones_electricas": "⚡ Instalaciones eléctricas",
    "instalaciones_fontaneria": "🚿 Fontanería y saneamiento",
    "climatizacion":            "❄️ Climatización / HVAC",
    "acabados_interiores":      "🎨 Acabados interiores",
    "tejados_cubiertas":        "🏠 Tejados y cubiertas",
    "sostenibilidad_energia":   "🌿 Sostenibilidad / Energía",
    "direccion_obra":           "📋 Dirección de obra",
    "aparejador":               "📐 Aparejador / Jefe de obra",
    "reformas_integrales":      "🔨 Reformas integrales",
    "prefabricadas":            "🏭 Casas prefabricadas",
    "topografia":               "🗺️ Topografía",
    "bim":                      "💻 BIM / Modelado",
}


# ── DB init (seguro — ALTER TABLE si columna no existe) ────────────────────────

def _is_featured(provider_id: str) -> bool:
    """True si el constructor tiene plan Destacado vigente (activado por admin o Stripe)."""
    try:
        conn = db_conn()
        row = conn.execute(
            "SELECT is_featured, featured_until FROM service_providers WHERE id=?",
            (provider_id,)
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            return False
        if row[1]:  # fecha de caducidad
            return datetime.utcnow().isoformat() < row[1]
        return bool(row[0])
    except Exception:
        return False


def _offers_this_month(provider_id: str) -> int:
    """Número de ofertas enviadas en el mes actual."""
    try:
        month = datetime.utcnow().strftime("%Y-%m")
        conn = db_conn()
        n = conn.execute(
            "SELECT COUNT(*) FROM construction_offers WHERE provider_id=? AND created_at LIKE ?",
            (provider_id, f"{month}%")
        ).fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def _init_sp_tables():
    """Crea/migra tablas de constructores. Siempre seguro."""
    conn = db_conn()
    # Nuevas columnas en service_providers
    # Usamos SAVEPOINT para que un ALTER TABLE fallido (columna ya existe)
    # no deje la conexión PostgreSQL en estado InFailedSqlTransaction.
    for col, typedef in [
        ("specialties",           "TEXT"),
        ("price_per_m2_no_mat",   "REAL DEFAULT 0"),
        ("price_per_m2_with_mat", "REAL DEFAULT 0"),
        ("description",           "TEXT"),
        ("active",                "INTEGER DEFAULT 1"),
        ("is_featured",           "INTEGER DEFAULT 0"),
        ("featured_until",        "TEXT"),
        ("featured_plan",         "TEXT DEFAULT 'free'"),
    ]:
        try:
            conn.execute("SAVEPOINT _sp_col")
            conn.execute(f"ALTER TABLE service_providers ADD COLUMN {col} {typedef}")
            conn.execute("RELEASE SAVEPOINT _sp_col")
        except Exception:
            try:
                conn.execute("ROLLBACK TO SAVEPOINT _sp_col")
            except Exception:
                pass  # SQLite no necesita rollback explícito

    # Tablón de obras (proyectos que buscan constructor)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_tablon (
            id           TEXT PRIMARY KEY,
            client_email TEXT,
            client_name  TEXT,
            project_name TEXT,
            province     TEXT,
            style        TEXT,
            total_area   REAL,
            total_cost   REAL,
            coste_m2     REAL,
            budget_json  TEXT,
            created_at   TEXT,
            active       INTEGER DEFAULT 1
        )
    """)

    # Ofertas de construcción
    conn.execute("""
        CREATE TABLE IF NOT EXISTS construction_offers (
            id                TEXT PRIMARY KEY,
            tablon_id         TEXT,
            provider_id       TEXT,
            provider_name     TEXT,
            provider_email    TEXT,
            client_email      TEXT,
            project_name      TEXT,
            total_area        REAL,
            price_no_mat      REAL,
            price_with_mat    REAL,
            includes_materials INTEGER DEFAULT 0,
            plazo_semanas     INTEGER,
            garantia_anos     INTEGER DEFAULT 5,
            nota_tecnica      TEXT,
            breakdown_json    TEXT,
            estado            TEXT DEFAULT 'enviada',
            created_at        TEXT
        )
    """)
    # Migraciones de columnas nuevas en tablas existentes (SAVEPOINT — seguro en pgbouncer)
    for _tbl, _col, _typedef in [
        ("project_tablon",     "partidas_solicitadas",    "TEXT DEFAULT '[\"todos\"]'"),
        ("construction_offers","comision_pagada",          "INTEGER DEFAULT 0"),
        ("construction_offers","comision_stripe_session",  "TEXT"),
        ("construction_offers","contrato_sha256",          "TEXT"),
        ("construction_offers","contrato_pdf_b64",         "TEXT"),
    ]:
        try:
            conn.execute("SAVEPOINT _sp_mgr")
            conn.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typedef}")
            conn.execute("RELEASE SAVEPOINT _sp_mgr")
        except Exception:
            try:
                conn.execute("ROLLBACK TO SAVEPOINT _sp_mgr")
            except Exception:
                pass

    conn.commit()
    conn.close()


# ── Registro ──────────────────────────────────────────────────────────────────

def show_service_provider_registration():
    _init_sp_tables()
    st.markdown("""
<div style="background:linear-gradient(135deg,#1E3A5F,#0D2A4A);border-radius:14px;
            padding:24px 28px;margin-bottom:20px;">
  <div style="font-size:1.5rem;font-weight:900;color:#F8FAFC;">🏗️ Registro de Constructor / Profesional</div>
  <div style="color:#94A3B8;font-size:13px;margin-top:4px;">
    Únete a la red ArchiRapid · Recibe proyectos de clientes en tu zona · Sin cuota de alta
  </div>
</div>""", unsafe_allow_html=True)

    with st.form("service_provider_registration"):
        c1, c2 = st.columns(2)
        with c1:
            name     = st.text_input("Nombre / Razón social *", key="sp_name")
            email    = st.text_input("Email *", key="sp_email")
            phone    = st.text_input("Teléfono *", key="sp_phone")
            nif      = st.text_input("NIF / CIF *", key="sp_nif")
            company  = st.text_input("Empresa (opcional)", key="sp_company")
        with c2:
            experience_years = st.number_input("Años de experiencia", 0, 50, 5, key="sp_experience")
            service_area     = st.text_input("Provincia(s) donde trabajas *",
                                             placeholder="ej: Madrid, Toledo, Guadalajara",
                                             key="sp_area")
            price_no_mat  = st.number_input("€/m² sin materiales",  0.0, 5000.0, 650.0,  50.0, key="sp_nm")
            price_with_mat= st.number_input("€/m² con materiales",  0.0, 5000.0, 1100.0, 50.0, key="sp_wm",
                                            help="Incluye estructura, cerramientos, acabados y materiales")

        specialties = st.multiselect(
            "Especialidades * (selecciona todas las que apliquen)",
            options=list(_ESP_LABELS.keys()),
            format_func=lambda x: _ESP_LABELS.get(x, x),
            default=["constructor"],
            key="sp_specialties"
        )

        description   = st.text_area("Descripción profesional (para los clientes)", height=80, key="sp_desc",
                                     placeholder="Ej: Empresa constructora con 15 años en obra nueva unifamiliar...")
        address       = st.text_area("Dirección completa", key="sp_address")
        certifications= st.text_area("Certificaciones / Titulaciones (una por línea)", key="sp_certs",
                                     placeholder="Arquitecto Técnico\nCoordinador SSL\nCertificado ISO 9001...")

        c3, c4 = st.columns(2)
        with c3: password  = st.text_input("Contraseña *", type="password", key="sp_password")
        with c4: confirm   = st.text_input("Confirmar contraseña *", type="password", key="sp_confirm")

        st.markdown("---")
        st.markdown("**Elige tu plan:**")
        plan_cols = st.columns(2)
        with plan_cols[0]:
            st.markdown("""
<div style="border:2px solid rgba(255,255,255,0.15);border-radius:10px;padding:14px;text-align:center;">
  <div style="font-weight:800;color:#F8FAFC;font-size:15px;">🆓 Plan Gratuito</div>
  <div style="color:#4ADE80;font-size:1.3rem;font-weight:900;margin:6px 0;">€0/mes</div>
  <div style="color:#94A3B8;font-size:11px;line-height:1.8;">
    ✅ Registro y perfil<br>
    ✅ Ver tablón de obras<br>
    ✅ 3 ofertas/mes<br>
    ❌ Sin badge Destacado<br>
    ❌ Proyectos con 24h retraso
  </div>
</div>""", unsafe_allow_html=True)
        with plan_cols[1]:
            st.markdown("""
<div style="border:2px solid #F59E0B;border-radius:10px;padding:14px;text-align:center;
            background:rgba(245,158,11,0.06);">
  <div style="font-weight:800;color:#F59E0B;font-size:15px;">⭐ Plan Destacado</div>
  <div style="color:#F59E0B;font-size:1.3rem;font-weight:900;margin:6px 0;">€99/mes</div>
  <div style="color:#CBD5E1;font-size:11px;line-height:1.8;">
    ✅ Todo lo gratuito<br>
    ✅ Ofertas ilimitadas<br>
    ✅ Badge ⭐ VERIFICADO<br>
    ✅ Primero en comparativas<br>
    ✅ Notificación inmediata
  </div>
</div>""", unsafe_allow_html=True)

        plan_elegido = st.radio("", ["free", "destacado"],
                                format_func=lambda x: "🆓 Plan Gratuito (€0/mes)" if x == "free"
                                                      else "⭐ Plan Destacado (€99/mes) — Activación tras confirmación de pago",
                                key="sp_plan", horizontal=True)

        gdpr = st.checkbox("Acepto la Política de Privacidad y el tratamiento de mis datos profesionales.",
                           key="sp_gdpr")

        submitted = st.form_submit_button("✅ Registrarme como Constructor/Profesional",
                                          type="primary", use_container_width=True)

        if submitted:
            if not all([name, email, phone, nif, service_area, password, confirm, specialties]):
                st.error("Completa todos los campos obligatorios (*).")
                return
            if not gdpr:
                st.error("Debes aceptar la Política de Privacidad.")
                return
            if password != confirm:
                st.error("Las contraseñas no coinciden.")
                return
            if len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
                return
            try:
                conn = db_conn()
                if conn.execute("SELECT id FROM service_providers WHERE email=?", (email,)).fetchone():
                    st.error("Ya existe un profesional registrado con ese email.")
                    conn.close()
                    return
                pid = f"sp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                sp_json = json.dumps(specialties)
                sp_primary = specialties[0] if specialties else "constructor"
                _plan = st.session_state.get("sp_plan", "free")
                conn.execute("""
                    INSERT INTO service_providers
                        (id,name,email,nif,specialty,specialties,company,phone,address,
                         certifications,experience_years,service_area,
                         price_per_m2_no_mat,price_per_m2_with_mat,description,
                         active,featured_plan,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
                """, (pid, name, email, nif, sp_primary, sp_json, company, phone, address,
                      certifications, experience_years, service_area,
                      price_no_mat, price_with_mat, description, _plan,
                      datetime.utcnow().isoformat()))
                pwd_hash = generate_password_hash(password)
                conn.execute("""
                    INSERT INTO users (id,email,password_hash,full_name,role,created_at)
                    VALUES (?,?,?,?,'services',?)
                """, (pid, email, pwd_hash, name, datetime.utcnow().isoformat()))
                conn.commit()
                conn.close()
                # Notificar admin
                try:
                    from modules.marketplace.email_notify import _send
                    _plan_txt = "⭐ DESTACADO (€99/mes) — pendiente activación" if _plan == "destacado" else "🆓 Gratuito"
                    _send(f"🏗️ <b>Nuevo constructor registrado</b>\n{name} ({email})\nPlan: {_plan_txt}\nZona: {service_area}")
                except Exception:
                    pass
                if _plan == "destacado":
                    # Crear checkout Stripe directamente
                    try:
                        from modules.stripe_utils import create_destacado_checkout as _cdc, _get_base_url as _gbu
                        _s_url, _ = _cdc(
                            provider_id=pid,
                            provider_name=name,
                            provider_email=email,
                            cancel_url=_gbu() + "/?page=registro_profesional",
                        )
                        st.success("✅ ¡Registro completado! Completa el pago para activar tu badge ⭐ DESTACADO.")
                        st.markdown(
                            f'<a href="{_s_url}" target="_blank" style="display:inline-block;'
                            'background:#F59E0B;color:#000;padding:14px 28px;border-radius:8px;'
                            'font-weight:800;font-size:15px;text-decoration:none;margin-top:8px;">'
                            '⭐ Pagar Plan Destacado — €99</a>',
                            unsafe_allow_html=True,
                        )
                        st.caption("Pago seguro con Stripe. Activación inmediata al confirmar el pago.")
                    except Exception as _ep:
                        st.success("✅ ¡Registro completado! Tu plan Destacado está pendiente de activación.")
                        st.info(f"💳 Contacta con hola@archirapid.com para confirmar el pago. Error Stripe: {_ep}")
                else:
                    st.success("✅ ¡Registro completado! Accede desde Home → Acceso → Servicios.")
                st.balloons()
            except Exception as e:
                st.error(f"Error en el registro: {e}")


# ── Panel principal ────────────────────────────────────────────────────────────

def show_service_provider_panel():
    _init_sp_tables()

    if not st.session_state.get("logged_in") or st.session_state.get("role") != "services":
        st.error("Debes iniciar sesión como constructor/profesional.")
        return

    user_email = st.session_state.get("user_email", "")
    conn = db_conn()
    row = conn.execute("""
        SELECT id,name,specialty,specialties,company,phone,address,certifications,
               experience_years,service_area,
               price_per_m2_no_mat,price_per_m2_with_mat,description,
               is_featured,featured_until,featured_plan,active
        FROM service_providers WHERE email=?
    """, (user_email,)).fetchone()
    conn.close()

    if not row:
        st.error("No se encontró el perfil. Contacta con soporte.")
        return

    (pid, name, specialty_old, specialties_json,
     company, phone, address, certifications,
     exp_years, service_area,
     p_nm, p_wm, description,
     is_feat_db, featured_until, featured_plan, sp_active) = row

    if not sp_active:
        st.error("🚫 Tu cuenta ha sido desactivada. Contacta con hola@archirapid.com para más información.")
        return

    try:
        specialties = json.loads(specialties_json) if specialties_json else [specialty_old]
    except Exception:
        specialties = [specialty_old] if specialty_old else ["constructor"]

    p_nm       = float(p_nm  or 650)
    p_wm       = float(p_wm  or 1100)
    featured   = _is_featured(pid)
    n_ofertas_mes = _offers_this_month(pid)
    LIMITE_FREE = 3

    # ── Banner de plan ─────────────────────────────────────────────────────────
    if featured:
        feat_exp = featured_until[:10] if featured_until else "indefinido"
        st.markdown(f"""
<div style="background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(245,158,11,0.05));
            border:1px solid #F59E0B;border-radius:10px;padding:10px 16px;margin-bottom:12px;
            display:flex;align-items:center;gap:10px;">
  <div style="font-size:1.4rem;">⭐</div>
  <div>
    <div style="font-weight:800;color:#F59E0B;font-size:13px;">PLAN DESTACADO ACTIVO — €99/mes</div>
    <div style="color:#CBD5E1;font-size:11px;">Bienvenido al plan profesional. Acceso a subastas en tiempo real, solicitudes ilimitadas y presentar ofertas a clientes. Válido hasta {feat_exp}</div>
  </div>
</div>""", unsafe_allow_html=True)
    elif featured_plan == 'destacado':
        # Seleccionó plan de pago pero admin aún no ha activado
        st.markdown("""
<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);
            border-radius:10px;padding:10px 16px;margin-bottom:12px;
            display:flex;align-items:center;gap:10px;">
  <div style="font-size:1.4rem;">⏳</div>
  <div>
    <div style="font-weight:800;color:#F59E0B;font-size:13px;">PLAN DESTACADO — Pendiente de activación</div>
    <div style="color:#94A3B8;font-size:11px;">Tu plan Destacado está siendo verificado por el equipo de ArchiRapid. Contacta hola@archirapid.com si tienes dudas.</div>
  </div>
</div>""", unsafe_allow_html=True)
    else:
        ofertas_restantes = max(0, LIMITE_FREE - n_ofertas_mes)
        st.markdown(f"""
<div style="background:rgba(30,58,95,0.3);border:1px solid rgba(255,255,255,0.1);
            border-radius:10px;padding:10px 16px;margin-bottom:12px;
            display:flex;align-items:center;justify-content:space-between;gap:10px;">
  <div>
    <div style="font-weight:700;color:#F8FAFC;font-size:12px;">🆓 Plan Gratuito
      — <span style="color:{'#4ADE80' if ofertas_restantes>0 else '#F87171'}">
        {ofertas_restantes}/{LIMITE_FREE} ofertas restantes este mes
      </span>
    </div>
    <div style="color:#64748B;font-size:11px;">Pasa a Destacado para ofertas ilimitadas + primera posición</div>
  </div>
  <div style="font-size:11px;color:#F59E0B;font-weight:700;white-space:nowrap;">⭐ €99/mes →</div>
</div>""", unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    feat_badge = ' <span style="background:#F59E0B;color:#000;font-size:10px;font-weight:800;padding:2px 8px;border-radius:10px;">⭐ DESTACADO</span>' if featured else ''
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#1E3A5F,#0D2A4A);border-radius:14px;
            padding:20px 24px;margin-bottom:16px;display:flex;align-items:center;gap:16px;">
  <div style="font-size:2.5rem;">🏗️</div>
  <div>
    <div style="font-size:1.3rem;font-weight:900;color:#F8FAFC;">{name}{feat_badge}</div>
    <div style="color:#94A3B8;font-size:13px;">{company or 'Profesional independiente'} · {service_area} · {exp_years} años exp.</div>
    <div style="margin-top:6px;">
      {''.join(f'<span style="background:rgba(37,99,235,0.2);border:1px solid rgba(37,99,235,0.3);border-radius:12px;padding:2px 10px;font-size:11px;color:#93C5FD;margin-right:4px;">{_ESP_LABELS.get(s,s)}</span>' for s in specialties)}
    </div>
  </div>
  <div style="margin-left:auto;text-align:right;">
    <div style="font-size:1.1rem;font-weight:800;color:#4ADE80;">€{p_nm:,.0f}/m²</div>
    <div style="font-size:10px;color:#64748B;">sin materiales</div>
    <div style="font-size:1.1rem;font-weight:800;color:#F59E0B;margin-top:2px;">€{p_wm:,.0f}/m²</div>
    <div style="font-size:10px;color:#64748B;">con materiales</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Botón cerrar sesión ──────────────────────────────────────────────────
    if st.button("🚪 Cerrar sesión", key="sp_logout"):
        for k in ['logged_in', 'user_id', 'user_email', 'role', 'user_name',
                   'viewing_login', 'login_role', 'selected_page']:
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Tablón de Obras", "📨 Mis Ofertas", "👤 Mi Perfil", "💶 Mis tarifas"])

    # ── TAB 1: TABLÓN DE OBRAS ────────────────────────────────────────────────
    with tab1:
        st.markdown("#### Proyectos que buscan constructor en tu zona")
        st.caption("Estos proyectos han sido diseñados en ArchiRapid y sus propietarios buscan constructor.")

        # ── Fase 3: retraso 24h para plan gratuito ────────────────────────────
        if not featured:
            st.markdown("""
<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);
            border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:12px;">
  ⏳ <b>Estás viendo proyectos con 24h de retraso.</b>
  Con el Plan Destacado los ves en tiempo real y llegas primero.<br>
  <span style="color:#F59E0B;">⭐ Actualiza a Destacado (€99/mes) desde tu registro o contacta hola@archirapid.com</span>
</div>""", unsafe_allow_html=True)

        conn = db_conn()
        # Filtrar por provincia (match parcial en service_area del constructor)
        areas = [a.strip().lower() for a in service_area.split(",") if a.strip()]

        # Fase 3: Gratuito solo ve proyectos de más de 24h; Destacado ve todos
        if featured:
            tablon_rows = conn.execute("""
                SELECT id,client_name,project_name,province,style,total_area,total_cost,
                       coste_m2,budget_json,created_at,
                       COALESCE(partidas_solicitadas,'["todos"]') as partidas_solicitadas,
                       client_email
                FROM project_tablon WHERE active=1
                ORDER BY created_at DESC
            """).fetchall()
        else:
            cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            tablon_rows = conn.execute("""
                SELECT id,client_name,project_name,province,style,total_area,total_cost,
                       coste_m2,budget_json,created_at,
                       COALESCE(partidas_solicitadas,'["todos"]') as partidas_solicitadas,
                       client_email
                FROM project_tablon WHERE active=1
                  AND created_at <= ?
                ORDER BY created_at DESC
            """, (cutoff_24h,)).fetchall()
        conn.close()

        # Filtro local por provincia + especialidad (Fase 2)
        def _match_area(prov):
            if not prov:
                return True
            prov_l = prov.lower()
            return any(a in prov_l or prov_l in a for a in areas) if areas else True

        def _match_specialty(partidas_json):
            """True si las partidas solicitadas incluyen 'todos' o alguna especialidad del constructor."""
            try:
                partidas = json.loads(partidas_json) if partidas_json else ["todos"]
            except Exception:
                partidas = ["todos"]
            if "todos" in partidas:
                return True
            # Match: alguna especialidad del constructor está en partidas solicitadas
            return any(s in partidas for s in specialties)

        visible = [r for r in tablon_rows if _match_area(r[3]) and _match_specialty(r[10])]

        if not visible:
            st.info("No hay proyectos disponibles en tu área ahora mismo. Te notificaremos cuando haya nuevos.")
        else:
            for r in visible:
                (tid, cname, pname, province, style, area, total_cost, coste_m2,
                 budget_json, created_at, _partidas_sol, client_email_tbl) = r

                # ¿Ya hice oferta?
                conn2 = db_conn()
                ya_ofertado = conn2.execute(
                    "SELECT id FROM construction_offers WHERE tablon_id=? AND provider_id=?",
                    (tid, pid)
                ).fetchone()
                conn2.close()

                badge = "✅ Oferta enviada" if ya_ofertado else "🆕 Sin oferta"
                with st.expander(f"{badge} · {pname or 'Proyecto'} — {area:.0f} m² · {province} · €{total_cost:,.0f}", expanded=not ya_ofertado):
                    # Presupuesto del cliente
                    col_inf, col_of = st.columns([1, 1])
                    with col_inf:
                        st.markdown(f"""
<div style="background:rgba(13,27,42,0.6);border:1px solid rgba(245,158,11,0.2);
            border-radius:10px;padding:14px;">
  <div style="font-size:13px;font-weight:700;color:#F59E0B;margin-bottom:8px;">📐 Datos del proyecto</div>
  <div style="color:#CBD5E1;font-size:12px;line-height:2;">
    <b>Superficie:</b> {area:.0f} m²<br>
    <b>Estilo:</b> {style or '—'}<br>
    <b>Provincia:</b> {province or '—'}<br>
    <b>Presupuesto cliente:</b> €{total_cost:,.0f}<br>
    <b>€/m² estimado:</b> €{coste_m2:,.0f}<br>
    <b>Publicado:</b> {created_at[:10] if created_at else '—'}
  </div>
</div>""", unsafe_allow_html=True)

                        # Desglose del cliente
                        if budget_json:
                            try:
                                budget = json.loads(budget_json)
                                st.markdown("**Desglose presupuesto cliente:**")
                                for partida in budget.get("partidas", []):
                                    st.markdown(
                                        f"<div style='font-size:11px;color:#94A3B8;'>"
                                        f"• {partida['name']}: <b style='color:#F8FAFC'>{partida['cost']}</b></div>",
                                        unsafe_allow_html=True
                                    )
                            except Exception:
                                pass

                    with col_of:
                        if ya_ofertado:
                            st.success("Ya enviaste una oferta para este proyecto.")
                            conn3 = db_conn()
                            of = conn3.execute("""
                                SELECT price_no_mat,price_with_mat,includes_materials,
                                       plazo_semanas,garantia_anos,nota_tecnica,estado
                                FROM construction_offers WHERE tablon_id=? AND provider_id=?
                            """, (tid, pid)).fetchone()
                            conn3.close()
                            if of:
                                st.markdown(f"""
<div style="font-size:12px;color:#CBD5E1;line-height:2;">
  {'<b style="color:#4ADE80">Con materiales:</b> €{of[1]:,.0f}' if of[2] else '<b style="color:#4ADE80">Sin materiales:</b> €{of[0]:,.0f}'}<br>
  <b>Plazo:</b> {of[3]} semanas<br>
  <b>Garantía:</b> {of[4]} años<br>
  <b>Estado:</b> {of[6].title()}<br>
  <b>Nota:</b> {of[5] or '—'}
</div>""", unsafe_allow_html=True)
                        else:
                            st.markdown("**Enviar oferta:**")
                            # Pre-cálculo automático con las tarifas del constructor
                            _pre_nm = int(p_nm * area)
                            _pre_wm = int(p_wm * area)

                            _incl_mat = st.checkbox("Incluye materiales", value=True, key=f"mat_{tid}")
                            _precio_nm = st.number_input(
                                f"Precio SIN materiales (€) [sugerido: €{_pre_nm:,}]",
                                0.0, 9_999_999.0, float(_pre_nm), 1000.0, key=f"pnm_{tid}"
                            )
                            _precio_wm = st.number_input(
                                f"Precio CON materiales (€) [sugerido: €{_pre_wm:,}]",
                                0.0, 9_999_999.0, float(_pre_wm), 1000.0, key=f"pwm_{tid}"
                            )
                            _plazo = st.slider("Plazo de ejecución (semanas)", 4, 104, 32, 2, key=f"plazo_{tid}")
                            _garantia = st.slider("Garantía (años)", 1, 15, 5, key=f"gar_{tid}")
                            _nota = st.text_area("Nota técnica para el cliente", height=80, key=f"nota_{tid}",
                                                 placeholder="Describe tu método, equipo, referencias de obra similar...")

                            # Desglose por partidas (pre-calculado)
                            _breakdown = _build_breakdown(area, _precio_nm, _precio_wm, _incl_mat)

                            # Límite plan gratuito
                            if not featured and n_ofertas_mes >= LIMITE_FREE:
                                st.warning(f"⚠️ Has alcanzado el límite de {LIMITE_FREE} ofertas/mes del plan gratuito.")
                                st.markdown("""
<div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);
            border-radius:8px;padding:10px 14px;font-size:12px;color:#FCD34D;">
  ⭐ <b>Plan Destacado (€99/mes)</b> — ofertas ilimitadas + primera posición en comparativas.<br>
  Contacta con <b>hola@archirapid.com</b> para activarlo.
</div>""", unsafe_allow_html=True)
                            elif st.button("📨 Enviar oferta", key=f"send_{tid}", type="primary", use_container_width=True):
                                try:
                                    oid = f"of_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{pid[:6]}"
                                    conn4 = db_conn()
                                    conn4.execute("""
                                        INSERT INTO construction_offers
                                            (id,tablon_id,provider_id,provider_name,provider_email,
                                             client_email,project_name,total_area,
                                             price_no_mat,price_with_mat,includes_materials,
                                             plazo_semanas,garantia_anos,nota_tecnica,
                                             breakdown_json,estado,created_at)
                                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'enviada',?)
                                    """, (oid, tid, pid, name, user_email,
                                          client_email_tbl, pname, area,
                                          _precio_nm, _precio_wm, int(_incl_mat),
                                          _plazo, _garantia, _nota,
                                          json.dumps(_breakdown),
                                          datetime.utcnow().isoformat()))
                                    conn4.commit()
                                    conn4.close()
                                    # Notificar admin
                                    try:
                                        from modules.marketplace.email_notify import (
                                            _send,
                                            notify_client_offer_received as _ncor,
                                        )
                                        _precio_show = _precio_wm if _incl_mat else _precio_nm
                                        _send(
                                            f"🏗️ <b>Nueva oferta de construcción</b>\n"
                                            f"Constructor: {name} ({user_email})\n"
                                            f"Proyecto: {pname} · {area:.0f} m² · {province}\n"
                                            f"Precio: €{_precio_show:,.0f} · Plazo: {_plazo} sem."
                                        )
                                        # Contar total de ofertas para ese proyecto y notificar al cliente
                                        if cname:
                                            try:
                                                _conn_cnt = db_conn()
                                                _n_of_tot = _conn_cnt.execute(
                                                    "SELECT COUNT(*) FROM construction_offers WHERE tablon_id=?", (tid,)
                                                ).fetchone()[0]
                                                _conn_cnt.close()
                                                _ncor(client_email_tbl, cname, pname or "Tu proyecto", _n_of_tot)
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                    st.success("✅ Oferta enviada. El cliente recibirá notificación.")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error enviando oferta: {ex}")

    # ── TAB 2: MIS OFERTAS ────────────────────────────────────────────────────
    with tab2:
        st.markdown("#### Historial de mis ofertas")
        conn = db_conn()
        ofertas = conn.execute("""
            SELECT id,project_name,total_area,price_no_mat,price_with_mat,
                   includes_materials,plazo_semanas,garantia_anos,nota_tecnica,
                   estado,created_at,client_email,
                   COALESCE(comision_pagada,0) as comision_pagada,
                   COALESCE(contrato_sha256,'') as contrato_sha256
            FROM construction_offers WHERE provider_id=?
            ORDER BY created_at DESC
        """, (pid,)).fetchall()
        conn.close()

        if not ofertas:
            st.info("Aún no has enviado ninguna oferta. Visita el Tablón de Obras para empezar.")
        else:
            _estado_color = {
                "enviada":  "#F59E0B",
                "aceptada": "#4ADE80",
                "rechazada":"#F87171",
                "caducada": "#64748B",
            }
            for of in ofertas:
                (oid, pname, area, pnm, pwm, incl_mat,
                 plazo, garantia, nota, estado, created_at, cemail,
                 comision_pagada, contrato_sha256) = of
                precio_show = float(pwm or 0) if incl_mat else float(pnm or 0)
                mat_label = "con materiales" if incl_mat else "sin materiales"
                comision_eur = round(precio_show * 0.03, 2)
                color = _estado_color.get(estado, "#94A3B8")
                _icon = "✅" if estado == "aceptada" else "📨"
                _comision_str = f" · 💳 Comisión pendiente €{comision_eur:,.0f}" if estado == "aceptada" and not comision_pagada else ""
                with st.expander(
                    f"{_icon} {pname or 'Proyecto'} — "
                    f"€{precio_show:,.0f} · {plazo} sem · Estado: {estado.upper()}{_comision_str}"
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"""
<div style="font-size:12px;color:#CBD5E1;line-height:2;">
  <b>Precio ({mat_label}):</b> <span style="color:{color};font-size:1.1em;">€{precio_show:,.0f}</span><br>
  <b>€/m² ofertado:</b> €{precio_show/area:.0f}<br>
  <b>Plazo:</b> {plazo} semanas ({plazo//4} meses aprox.)<br>
  <b>Garantía:</b> {garantia} años<br>
  <b>Estado:</b> <span style="color:{color};font-weight:700;">{estado.upper()}</span>
</div>""", unsafe_allow_html=True)
                    with c2:
                        if estado == "aceptada" and comision_pagada:
                            # Comisión pagada → mostrar contacto del cliente
                            st.markdown(f"""
<div style="background:rgba(74,222,128,0.1);border:1px solid #4ADE80;border-radius:8px;
            padding:10px 14px;font-size:12px;color:#CBD5E1;line-height:2;">
  ✅ <b style="color:#4ADE80">Comisión pagada — Obra confirmada</b><br>
  <b>Cliente:</b> {cemail or '—'}<br>
  <b>Superficie:</b> {area:.0f} m²<br>
  <b>Enviada:</b> {created_at[:10] if created_at else '—'}<br>
  <b>Nota:</b> {(nota or '—')[:80]}
  {f'<br><b>Hash contrato:</b> <span style="font-size:9px;color:#64748B">{contrato_sha256[:32]}…</span>' if contrato_sha256 else ''}
</div>""", unsafe_allow_html=True)
                        elif estado == "aceptada" and not comision_pagada:
                            # Pendiente de pago de comisión
                            st.markdown(f"""
<div style="background:rgba(245,158,11,0.1);border:1px solid #F59E0B;border-radius:8px;
            padding:10px 14px;font-size:12px;color:#CBD5E1;margin-bottom:10px;">
  ⭐ <b style="color:#F59E0B">¡Tu oferta fue aceptada!</b><br>
  Paga la comisión de intermediación para confirmar la obra y ver el contacto del cliente.
  <br><b>Comisión ArchiRapid (3%):</b> <span style="color:#F59E0B;font-weight:700;">€{comision_eur:,.0f}</span>
</div>""", unsafe_allow_html=True)
                            try:
                                from modules.stripe_utils import create_comision_checkout as _ccc, _get_base_url as _gbu2
                                _cc_url, _ = _ccc(
                                    offer_id=oid,
                                    constructor_email=user_email,
                                    amount_cents=int(comision_eur * 100),
                                    project_name=pname or "Proyecto",
                                    cancel_url=_gbu2() + "/",
                                )
                                st.markdown(
                                    f'<a href="{_cc_url}" target="_blank" style="display:inline-block;'
                                    'background:#F59E0B;color:#000;padding:10px 20px;border-radius:8px;'
                                    'font-weight:800;font-size:13px;text-decoration:none;">'
                                    f'💳 Pagar comisión — €{comision_eur:,.0f}</a>',
                                    unsafe_allow_html=True,
                                )
                            except Exception:
                                st.info(f"Para pagar la comisión contacta hola@archirapid.com · Referencia oferta: {oid}")
                        else:
                            st.markdown(f"""
<div style="font-size:12px;color:#CBD5E1;line-height:2;">
  <b>Cliente:</b> {'*****@***' if estado == 'enviada' else (cemail or '—')}<br>
  <b>Superficie:</b> {area:.0f} m²<br>
  <b>Enviada:</b> {created_at[:10] if created_at else '—'}<br>
  <b>Nota:</b> {(nota or '—')[:80]}
</div>""", unsafe_allow_html=True)

    # ── TAB 3: MI PERFIL ──────────────────────────────────────────────────────
    with tab3:
        st.markdown("#### Editar perfil y tarifas")

        # Cargar provincias de cobertura actuales (fuera del form para usar como default)
        _prov_conn = db_conn()
        try:
            _prov_row = _prov_conn.execute(
                "SELECT provincias_cobertura FROM service_providers WHERE id = ?", (pid,)
            ).fetchone()
            _provincias_actuales = json.loads(_prov_row[0] or "[]") if _prov_row and _prov_row[0] else []
        except Exception:
            _provincias_actuales = []
        finally:
            _prov_conn.close()

        with st.form("edit_sp_profile"):
            ec1, ec2 = st.columns(2)
            with ec1:
                new_desc     = st.text_area("Descripción profesional", value=description or "", height=100, key="ep_desc")
                new_area     = st.text_input("Provincias donde trabajas (texto libre)", value=service_area or "", key="ep_area")
                new_phone    = st.text_input("Teléfono", value=phone or "", key="ep_phone")
                new_certs    = st.text_area("Certificaciones", value=certifications or "", key="ep_certs")
                new_provincias = st.multiselect(
                    "Provincias de cobertura (matching automático)",
                    options=_PROVINCIAS_ESPAÑA,
                    default=[p for p in _provincias_actuales if p in _PROVINCIAS_ESPAÑA],
                    key="ep_provincias",
                    help="Los clientes de estas provincias te verán automáticamente en su panel.",
                )
            with ec2:
                new_nm = st.number_input("€/m² SIN materiales",  0.0, 5000.0, float(p_nm),  50.0, key="ep_nm")
                new_wm = st.number_input("€/m² CON materiales",  0.0, 5000.0, float(p_wm),  50.0, key="ep_wm")
                new_esp = st.multiselect(
                    "Especialidades",
                    options=list(_ESP_LABELS.keys()),
                    format_func=lambda x: _ESP_LABELS.get(x, x),
                    default=specialties,
                    key="ep_esp"
                )
                new_addr = st.text_area("Dirección", value=address or "", key="ep_addr")

            if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                try:
                    conn = db_conn()
                    sp_new = new_esp[0] if new_esp else (specialty_old or "constructor")
                    conn.execute("""
                        UPDATE service_providers
                        SET specialty=?, specialties=?, price_per_m2_no_mat=?,
                            price_per_m2_with_mat=?, description=?, service_area=?,
                            phone=?, address=?, certifications=?, provincias_cobertura=?
                        WHERE id=?
                    """, (sp_new, json.dumps(new_esp), new_nm, new_wm,
                          new_desc, new_area, new_phone, new_addr, new_certs,
                          json.dumps(new_provincias), pid))
                    conn.commit()
                    conn.close()
                    st.success("✅ Perfil actualizado.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error guardando: {ex}")

        # ── Estadísticas del perfil ────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Mis estadísticas")
        conn = db_conn()
        n_ofertas = conn.execute(
            "SELECT COUNT(*) FROM construction_offers WHERE provider_id=?", (pid,)
        ).fetchone()[0]
        n_aceptadas = conn.execute(
            "SELECT COUNT(*) FROM construction_offers WHERE provider_id=? AND estado='aceptada'", (pid,)
        ).fetchone()[0]
        conn.close()

        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("📨 Ofertas enviadas", n_ofertas)
        sc2.metric("✅ Ofertas aceptadas", n_aceptadas)
        sc3.metric("📊 Tasa de éxito", f"{int(n_aceptadas/n_ofertas*100)}%" if n_ofertas else "—")

        # ── CTA upgrade si es plan gratuito ───────────────────────────────────
        if not featured:
            st.markdown("---")
            st.markdown("""
<div style="background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(245,158,11,0.05));
            border:2px solid rgba(245,158,11,0.4);border-radius:14px;padding:20px 24px;">
  <div style="font-size:1.1rem;font-weight:900;color:#F59E0B;margin-bottom:8px;">
    ⭐ Pasa a Plan Destacado — €99/mes
  </div>
  <div style="color:#CBD5E1;font-size:13px;line-height:1.9;margin-bottom:14px;">
    ✅ Ofertas ilimitadas (ahora tienes 3/mes)<br>
    ✅ Primera posición en la comparativa del cliente<br>
    ✅ Badge <b>⭐ DESTACADO · VERIFICADO</b> en tu tarjeta<br>
    ✅ Notificación inmediata de nuevos proyectos<br>
    ✅ Apareces en fichas de fincas de tu provincia
  </div>
  <div style="font-size:12px;color:#94A3B8;">
    💳 Para activarlo contacta con <b>hola@archirapid.com</b> o al <b>+34 XXX XXX XXX</b>.<br>
    Activación en menos de 24h.
  </div>
</div>""", unsafe_allow_html=True)
            # Botón simulado para MVP
            if st.button("⭐ Solicitar Plan Destacado (€99/mes)", type="primary", use_container_width=True,
                         key="btn_upgrade_destacado"):
                try:
                    from modules.marketplace.email_notify import _send
                    _send(f"⭐ <b>Solicitud Plan Destacado</b>\n{name} ({user_email})\nZona: {service_area}")
                except Exception:
                    pass
                st.success("✅ Solicitud enviada. El equipo ArchiRapid te contactará en menos de 24h para activar tu plan.")
                st.balloons()

    # ── TAB 4: MIS TARIFAS ────────────────────────────────────────────────────
    with tab4:
        try:
            from estudiantes import _mostrar_tarifas_profesional as _mtf
        except ImportError:
            st.error("No se pudo cargar el módulo de tarifas.")
        else:
            _mtf(email=user_email, proveedor_id=pid, tipo="arquitecto")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_breakdown(area: float, price_nm: float, price_wm: float, with_mat: bool) -> dict:
    """Desglosa la oferta del constructor por partidas (proporcional al presupuesto del diseñador)."""
    base = price_wm if with_mat else price_nm
    return {
        "total": base,
        "includes_materials": with_mat,
        "coste_m2": round(base / area, 0) if area else 0,
        "partidas": [
            {"name": "Cimentación",              "cost": round(base * 0.14), "pct": "14%"},
            {"name": "Estructura y cubierta",    "cost": round(base * 0.28), "pct": "28%"},
            {"name": "Cerramientos / fachada",   "cost": round(base * 0.16), "pct": "16%"},
            {"name": "Instalaciones",            "cost": round(base * 0.14), "pct": "14%"},
            {"name": "Acabados interiores",      "cost": round(base * 0.20), "pct": "20%"},
            {"name": "Honorarios / gestión",     "cost": round(base * 0.08), "pct": "8%"},
        ]
    }


def publish_to_tablon(client_email: str, client_name: str, project_name: str,
                      province: str, style: str, total_area: float,
                      total_cost: float, partidas_list: list,
                      partidas_solicitadas: list = None) -> str:
    """
    Publica un proyecto en el Tablón de Obras.
    Llamado desde flow.py paso 5.
    partidas_solicitadas: lista de especialidades que el cliente quiere contratar,
                          p.ej. ["instalaciones_electricas", "instalaciones_fontaneria"].
                          None o vacío = ["todos"] (obra completa).
    Devuelve el ID del tablón creado.
    """
    _init_sp_tables()
    coste_m2 = round(total_cost / total_area, 0) if total_area else 0
    budget = {
        "partidas": [
            {"name": p[0], "cost": p[1], "pct": p[2], "desc": p[3]}
            for p in partidas_list
        ]
    }
    _parts_json = json.dumps(partidas_solicitadas if partidas_solicitadas else ["todos"])
    tid = f"tab_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    conn = db_conn()
    conn.execute("""
        INSERT INTO project_tablon
            (id,client_email,client_name,project_name,province,style,
             total_area,total_cost,coste_m2,budget_json,created_at,active,partidas_solicitadas)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)
    """, (tid, client_email, client_name, project_name, province, style,
          total_area, total_cost, coste_m2, json.dumps(budget),
          datetime.utcnow().isoformat(), _parts_json))
    conn.commit()

    # Fase 4: Notificar a constructores Destacados de la zona (solo ellos reciben aviso inmediato)
    try:
        _prov_l = (province or "").lower()
        destacados = conn.execute("""
            SELECT name, email, service_area, specialties
            FROM service_providers
            WHERE is_featured=1 AND active=1
        """).fetchall()
        conn.close()
        from modules.marketplace.email_notify import notify_constructor_new_project as _ncnp
        _parts_list = partidas_solicitadas or ["todos"]
        for _d in destacados:
            _dname, _demail, _darea, _dspecs_json = _d
            # Verificar provincia
            _areas = [a.strip().lower() for a in (_darea or "").split(",") if a.strip()]
            _area_ok = any(a in _prov_l or _prov_l in a for a in _areas) if _areas else True
            if not _area_ok:
                continue
            # Verificar especialidad
            try:
                _dspecs = json.loads(_dspecs_json) if _dspecs_json else []
            except Exception:
                _dspecs = []
            _spec_ok = "todos" in _parts_list or any(s in _parts_list for s in _dspecs)
            if not _spec_ok:
                continue
            try:
                _ncnp(_demail, _dname, project_name, province, total_area, total_cost)
            except Exception:
                pass
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

    return tid


# ── Mantener compatibilidad con código legacy ──────────────────────────────────

def show_service_contracts(provider_id, specialty):
    st.info("Las asignaciones se gestionan desde el Tablón de Obras.")

def show_services_marketplace():
    show_service_provider_panel()

def update_assignment_status(assignment_id, new_status):
    conn = db_conn()
    conn.execute("UPDATE service_assignments SET estado=? WHERE id=?", (new_status, assignment_id))
    conn.commit(); conn.close()

def add_assignment_note(assignment_id, note):
    conn = db_conn()
    r = conn.execute("SELECT notas FROM service_assignments WHERE id=?", (assignment_id,)).fetchone()
    existing = r[0] if r and r[0] else ""
    new_notes = f"{existing}\n{datetime.utcnow().isoformat()}: {note}".strip()
    conn.execute("UPDATE service_assignments SET notas=? WHERE id=?", (new_notes, assignment_id))
    conn.commit(); conn.close()
