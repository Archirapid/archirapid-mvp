# modules/marketplace/stats_public.py
"""
Dashboard público /stats — ArchiRapid
Accesible sin login. Métricas en tiempo real desde la DB.
"""
import streamlit as st
import sqlite3
import datetime


def _db():
    from modules.marketplace.utils import DB_PATH
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _q(conn, sql, default=0):
    try:
        return conn.execute(sql).fetchone()[0] or default
    except Exception:
        return default


def render():
    st.markdown("""
<style>
.stats-hero {
    background: linear-gradient(135deg, #0D1B2A 0%, #1E3A5F 100%);
    border-radius: 16px;
    padding: 40px 36px 32px;
    margin-bottom: 28px;
    text-align: center;
}
.stats-hero h1 {
    font-size: 2.4rem; font-weight: 900;
    color: #F8FAFC; margin: 0 0 8px; letter-spacing: -1px;
}
.stats-hero p {
    color: #94A3B8; font-size: 1rem; margin: 0;
}
.kpi-card {
    background: rgba(30,58,95,0.5);
    border: 1px solid rgba(245,158,11,0.25);
    border-radius: 14px;
    padding: 22px 18px;
    text-align: center;
}
.kpi-num  { font-size: 2.2rem; font-weight: 900; color: #F59E0B; line-height: 1; }
.kpi-sub  { font-size: 0.78rem; color: #94A3B8; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.8px; }
.kpi-icon { font-size: 1.6rem; margin-bottom: 8px; }
.section-title {
    font-size: 1.1rem; font-weight: 800; color: #F8FAFC;
    margin: 28px 0 14px; border-left: 3px solid #F59E0B; padding-left: 12px;
}
.badge-row {
    display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px;
}
.badge {
    background: rgba(37,99,235,0.15); border: 1px solid rgba(37,99,235,0.3);
    border-radius: 20px; padding: 5px 14px;
    font-size: 12px; color: #93C5FD; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
<div class="stats-hero">
  <div style="font-size:2rem;margin-bottom:8px;">🏗️</div>
  <h1>ArchiRapid en números</h1>
  <p>Métricas en tiempo real · Plataforma de suelo + diseño arquitectónico · España</p>
</div>
""", unsafe_allow_html=True)

    try:
        conn = _db()

        # ── Consultas ─────────────────────────────────────────────────────────
        n_plots     = _q(conn, "SELECT COUNT(*) FROM plots")
        n_avail     = _q(conn, "SELECT COUNT(*) FROM plots WHERE status='disponible'")
        total_m2    = _q(conn, "SELECT COALESCE(SUM(m2),0) FROM plots")
        n_users     = _q(conn, "SELECT COUNT(*) FROM users")
        n_clients   = _q(conn, "SELECT COUNT(*) FROM users WHERE role='client'")
        n_owners    = _q(conn, "SELECT COUNT(*) FROM users WHERE role='owner'")
        n_projects  = _q(conn, "SELECT COUNT(*) FROM projects")
        n_reserv    = _q(conn, "SELECT COUNT(*) FROM reservations")
        n_certs     = _q(conn, "SELECT COUNT(*) FROM document_certs")
        n_alerts    = _q(conn, "SELECT COUNT(*) FROM plot_alerts WHERE active=1")
        n_prefabs   = _q(conn, "SELECT COUNT(*) FROM prefab_catalog WHERE active=1")
        avg_price   = _q(conn, "SELECT AVG(price) FROM plots", default=0)

        # Ahorro medio vs arquitecto tradicional:
        # Proyecto estándar 150m²: arquitecto = ~18.000€ · ArchiRapid = ~1.200€ (suscripción + trámites)
        ahorro_pct = 93
        ahorro_abs = 16800

        # Superficie total diseñada: projects × 150m² media
        m2_disenados = n_projects * 150

        conn.close()

    except Exception as e:
        st.error(f"Error cargando métricas: {e}")
        return

    # ── KPIs fila 1 ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🗺️ Marketplace de Suelo</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)

    def _kpi(col, icon, num, label):
        col.markdown(f"""
<div class="kpi-card">
  <div class="kpi-icon">{icon}</div>
  <div class="kpi-num">{num}</div>
  <div class="kpi-sub">{label}</div>
</div>""", unsafe_allow_html=True)

    _kpi(k1, "🗺️", n_plots,      "Fincas publicadas")
    _kpi(k2, "✅", n_avail,      "Disponibles ahora")
    _kpi(k3, "📐", f"{total_m2:,.0f} m²", "Superficie total")
    _kpi(k4, "💶", f"€{avg_price:,.0f}", "Precio medio")

    st.markdown("")

    # ── KPIs fila 2 ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🏠 Diseñador Arquitectónico IA</div>', unsafe_allow_html=True)
    k5, k6, k7, k8 = st.columns(4)

    _kpi(k5, "🏗️", n_projects,          "Proyectos generados")
    _kpi(k6, "📐", f"{m2_disenados:,} m²", "m² diseñados")
    _kpi(k7, "💰", f"{ahorro_pct}%",      "Ahorro vs arquitecto")
    _kpi(k8, "🔐", n_certs,              "Docs certificados")

    st.markdown("")

    # ── KPIs fila 3 ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">👥 Comunidad</div>', unsafe_allow_html=True)
    k9, k10, k11, k12 = st.columns(4)

    _kpi(k9,  "👤", n_users,    "Usuarios registrados")
    _kpi(k10, "🏠", n_owners,   "Propietarios activos")
    _kpi(k11, "🔔", n_alerts,   "Alertas de fincas activas")
    _kpi(k12, "🏭", n_prefabs,  "Casas prefabricadas")

    st.markdown("")

    # ── Comparativa ahorro ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">💰 ArchiRapid vs Arquitecto Tradicional</div>',
                unsafe_allow_html=True)

    col_trad, col_ar = st.columns(2)
    with col_trad:
        st.markdown("""
<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);
            border-radius:12px;padding:20px;">
  <div style="font-size:14px;font-weight:800;color:#FCA5A5;margin-bottom:12px;">
    🏛️ Arquitecto tradicional
  </div>
  <div style="color:#CBD5E1;font-size:13px;line-height:1.8;">
    Proyecto básico (150 m²): <strong style="color:#F87171">~18.000 €</strong><br>
    Tiempo: <strong style="color:#F87171">3–6 meses</strong><br>
    Visitas presenciales: <strong style="color:#F87171">obligatorias</strong><br>
    Iteraciones: <strong style="color:#F87171">lentas y costosas</strong>
  </div>
</div>""", unsafe_allow_html=True)

    with col_ar:
        st.markdown("""
<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);
            border-radius:12px;padding:20px;">
  <div style="font-size:14px;font-weight:800;color:#86EFAC;margin-bottom:12px;">
    🚀 ArchiRapid IA
  </div>
  <div style="color:#CBD5E1;font-size:13px;line-height:1.8;">
    Proyecto básico (150 m²): <strong style="color:#4ADE80">~1.200 €</strong><br>
    Tiempo: <strong style="color:#4ADE80">15 minutos</strong><br>
    100% online: <strong style="color:#4ADE80">desde cualquier lugar</strong><br>
    Iteraciones: <strong style="color:#4ADE80">ilimitadas e instantáneas</strong>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Barra ahorro visual ────────────────────────────────────────────────────
    st.markdown(f"""
<div style="margin:20px 0 8px;font-size:13px;color:#94A3B8;">
  Ahorro medio por proyecto: <strong style="color:#4ADE80">€{ahorro_abs:,}</strong> ({ahorro_pct}%)
</div>
<div style="background:rgba(255,255,255,0.08);border-radius:99px;height:12px;overflow:hidden;">
  <div style="background:linear-gradient(90deg,#22C55E,#16A34A);width:{ahorro_pct}%;height:100%;border-radius:99px;"></div>
</div>
""", unsafe_allow_html=True)

    st.markdown("")

    # ── Badges tecnología ──────────────────────────────────────────────────────
    st.markdown('<div class="section-title">⚡ Tecnología</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="badge-row">
  <span class="badge">🤖 IA Generativa</span>
  <span class="badge">🏗️ Gemelo Digital BIM/IFC</span>
  <span class="badge">🔐 Blockchain SHA-256</span>
  <span class="badge">🔭 Tour Virtual 360°</span>
  <span class="badge">📐 Editor 3D Babylon.js</span>
  <span class="badge">⚡ Energía A+</span>
  <span class="badge">🌿 Sostenibilidad</span>
  <span class="badge">📱 100% Online</span>
</div>
""", unsafe_allow_html=True)

    # ── Footer CTA ────────────────────────────────────────────────────────────
    st.markdown("""
<div style="background:linear-gradient(135deg,rgba(37,99,235,0.15),rgba(30,58,95,0.3));
            border:1px solid rgba(37,99,235,0.3);border-radius:14px;
            padding:28px 32px;text-align:center;margin-top:32px;">
  <div style="font-size:1.3rem;font-weight:900;color:#F8FAFC;margin-bottom:8px;">
    ¿Tienes una finca? ¿Quieres construir?
  </div>
  <div style="color:#94A3B8;font-size:14px;margin-bottom:18px;">
    Publica tu terreno o diseña tu vivienda en minutos
  </div>
  <a href="/" style="display:inline-block;background:linear-gradient(135deg,#2563EB,#1D4ED8);
     color:#fff;font-weight:700;font-size:14px;text-decoration:none;
     padding:12px 32px;border-radius:10px;">
    Ir a ArchiRapid →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    st.markdown(
        f"<p style='color:#475569;font-size:11px;text-align:center;margin-top:20px;'>"
        f"Datos actualizados: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC · "
        f"ArchiRapid © 2026</p>",
        unsafe_allow_html=True
    )
