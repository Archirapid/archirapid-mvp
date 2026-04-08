# modules/marketplace/intranet.py - GESTIÓN INTERNA DE LA EMPRESA
import streamlit as st
from modules.marketplace.utils import db_conn, list_published_plots, list_projects
import json

def _admin_token(pw: str) -> str:
    """Token determinista derivado de la contraseña. No expira salvo que cambie ADMIN_PASSWORD."""
    import hashlib
    return hashlib.sha256(f"archirapid-admin-salt-{pw}".encode()).hexdigest()[:28]


def render_admin_actions(item_id: str, table_name: str, section_slug: str, item_name: str = "", actions: list = None):
    """
    Renderiza botones de acción unificados para admin.

    Args:
        item_id: ID del item a gestionar
        table_name: Nombre de tabla SQL
        section_slug: slug único de sección (ej: "fincas", "profesionales", "estudiantes")
        item_name: Nombre del item para confirmaciones
        actions: Lista de dicts con {'label': '...', 'action': 'approve'/'suspend'/'delete', 'type': 'primary'/'secondary'}
    """
    if not actions:
        return

    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4]

    for idx, action in enumerate(actions[:4]):
        if idx >= len(cols):
            break
        with cols[idx]:
            label = action.get('label', '')
            action_type = action.get('action', '')
            btn_type = action.get('type', 'secondary')

            if action_type == 'delete':
                # DELETE usa popover para confirmación (no anidamiento)
                with st.popover(label, use_container_width=True):
                    st.error(f"⚠️ ¿Eliminar '{item_name}'?")
                    st.caption("Esta acción no se puede deshacer.")
                    if st.button("❌ Sí, eliminar", key=f"btn_{section_slug}_del_yes_{item_id}", type="primary"):
                        try:
                            _conn_del = db_conn()
                            _conn_del.execute(f"DELETE FROM {table_name} WHERE id=?", (item_id,))
                            _conn_del.commit()
                            _conn_del.close()
                            st.success("✅ Eliminado")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                # Otros botones updatean directamente sin confirmación
                if st.button(label, key=f"btn_{section_slug}_{action_type}_{item_id}", type=btn_type, use_container_width=True):
                    try:
                        status_map = {
                            'approve': 'activo',
                            'pending': 'pendiente',
                            'suspend': 'suspendido',
                            'cancel': 'anulado',
                        }
                        new_status = status_map.get(action_type, action_type)
                        is_active = 1 if action_type == 'approve' else 0

                        _conn_upd = db_conn()
                        _conn_upd.execute(
                            f"UPDATE {table_name} SET status=?, is_active=? WHERE id=?",
                            (new_status, is_active, item_id)
                        )
                        _conn_upd.commit()
                        _conn_upd.close()
                        st.success(f"✅ {label}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


def _update_project_status(pid: str, new_status: str) -> bool:
    """
    Actualiza el estado de un proyecto con lógica blindada de is_active.

    Estados activos (is_active=1): activo, reservado
    Estados inactivos (is_active=0): vendido, no_disponible, suspendido
    """
    is_active_map = {
        'activo': 1,
        'reservado': 1,
        'vendido': 0,
        'no_disponible': 0,
        'suspendido': 0,
    }
    is_active = is_active_map.get(new_status, 1)

    try:
        _conn = db_conn()
        _conn.execute(
            "UPDATE projects SET status=?, is_active=? WHERE id=?",
            (new_status, is_active, pid)
        )
        _conn.commit()
        _conn.close()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error actualizando proyecto: {e}")
        return False


def _update_plot_status(pid: str, new_status: str) -> bool:
    """
    Actualiza el estado de un plot con lógica blindada de is_active.

    Estados con is_active=1: disponible, published, reserved
    Estados con is_active=0: sold, suspended, no_disponible
    """
    is_active_map = {
        'disponible': 1, 'published': 1, 'reserved': 1,
        'sold': 0, 'suspended': 0, 'no_disponible': 0
    }
    is_active = is_active_map.get(new_status, 0)

    try:
        _conn = db_conn()
        try:
            _conn.execute(
                "UPDATE plots SET status=?, is_active=? WHERE id=?",
                (new_status, is_active, pid)
            )
            _conn.commit()
        finally:
            _conn.close()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error actualizando estado: {e}")
        return False


def main():
    st.title("🔐 Intranet — Gestión Interna de ARCHIRAPID")

    # Leer contraseña admin de secrets
    try:
        _admin_pw = st.secrets.get("ADMIN_PASSWORD", "admin123")
    except Exception:
        _admin_pw = "admin123"

    _valid_token = _admin_token(_admin_pw)

    # Restaurar sesión desde token en URL (sobrevive reinicios del servidor)
    _url_tok = st.query_params.get("admin_token", "")
    if _url_tok == _valid_token and st.session_state.get("rol") != "admin":
        st.session_state["rol"] = "admin"

    # Verificar si ya está logueado como admin
    if st.session_state.get("rol") == "admin":
        _col_info, _col_exit = st.columns([5, 1])
        with _col_info:
            st.success("✅ Acceso autorizado a Intranet (sesión activa)")
        with _col_exit:
            if st.button("🚪 Salir", key="intranet_logout", help="Cerrar sesión Admin"):
                st.session_state.pop("rol", None)
                st.session_state.pop("selected_page", None)
                try:
                    del st.query_params["admin_token"]
                except Exception:
                    pass
                st.rerun()
    else:
        # SOLO ACCESO CON CONTRASEÑA DE ADMIN
        password = st.text_input("Contraseña de Acceso Administrativo", type="password")
        if st.button("🔐 Acceder", key="admin_login_btn", type="primary", use_container_width=True):
            if password == _admin_pw:
                st.session_state["rol"] = "admin"
                st.query_params["admin_token"] = _valid_token
                st.rerun()
            else:
                st.error("🔒 Contraseña incorrecta.")
        elif not password:
            st.info("🔒 Acceso restringido. Solo personal autorizado de ARCHIRAPID.")
        return

    # PANEL DE GESTIÓN INTERNA
    # ── Inyectar CSS + JS para colorear botones por acción ────────────────────────
    st.markdown("""
    <style>
    /* Botones normales - mantener color por defecto */
    .stButton > button[kind="secondary"] {
        border-color: #475569 !important;
    }

    /* Botones primary - color base (se sobrescribe con JS) */
    .stButton > button[kind="primary"] {
        color: white !important;
    }

    /* Clases para diferentes acciones */
    .btn-activo[kind="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
    }

    .btn-vendido[kind="primary"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
    }

    .btn-suspender[kind="primary"] {
        background-color: #dc3545 !important;
        border-color: #dc3545 !important;
    }

    .btn-reservado[kind="primary"] {
        background-color: #ffc107 !important;
        border-color: #ffc107 !important;
        color: #000 !important;
    }

    .btn-no-disponible[kind="primary"] {
        background-color: #343a40 !important;
        border-color: #343a40 !important;
    }

    /* Mejorar visibilidad de popovers */
    .stPopover {
        z-index: 100;
    }
    </style>

    <script>
    // Colorear botones de proyectos basados en su contenido
    document.addEventListener('DOMContentLoaded', function() {
        const buttons = document.querySelectorAll('.stButton > button[kind="primary"]');
        buttons.forEach(btn => {
            const text = btn.innerText || btn.textContent;
            if (text.includes('Activo')) {
                btn.classList.add('btn-activo');
            } else if (text.includes('Vendido')) {
                btn.classList.add('btn-vendido');
            } else if (text.includes('Suspender')) {
                btn.classList.add('btn-suspender');
            } else if (text.includes('Reservado')) {
                btn.classList.add('btn-reservado');
            } else if (text.includes('No disponible')) {
                btn.classList.add('btn-no-disponible');
            }
        });
    });

    // Reintentar coloreo después de rerun (Streamlit agrega elementos dinámicamente)
    const observer = new MutationObserver(function() {
        const buttons = document.querySelectorAll('.stButton > button[kind="primary"]:not([data-colored="true"])');
        buttons.forEach(btn => {
            const text = btn.innerText || btn.textContent;
            if (text.includes('Activo')) {
                btn.classList.add('btn-activo');
            } else if (text.includes('Vendido')) {
                btn.classList.add('btn-vendido');
            } else if (text.includes('Suspender')) {
                btn.classList.add('btn-suspender');
            } else if (text.includes('Reservado')) {
                btn.classList.add('btn-reservado');
            } else if (text.includes('No disponible')) {
                btn.classList.add('btn-no-disponible');
            }
            btn.setAttribute('data-colored', 'true');
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
    </script>
    """, unsafe_allow_html=True)

    # Badge en Analytics: cuenta leads MLS nuevos para alertar al admin
    _leads_nuevos_badge = ""
    try:
        import sqlite3 as _sq_badge
        _bc_conn = _sq_badge.connect("database.db")
        try:
            _bc = _bc_conn.execute(
                "SELECT COUNT(*) FROM leads_mls WHERE estado='nuevo'"
            ).fetchone()
        finally:
            _bc_conn.close()
        if _bc and _bc[0] > 0:
            _leads_nuevos_badge = f" 🔴{_bc[0]}"
    except Exception:
        pass

    _ADMIN_SECCIONES = [
        "📋 Gestión de Fincas",
        "🏗️ Gestión de Proyectos",
        "💰 Ventas y Transacciones",
        "💎 Suscripciones & Proyectos AI",
        "📞 Consultas y Soporte",
        "🛠️ Profesionales",
        "⚙️ Admin",
        "🎯 Waitlist",
        "📬 Actividad",
        "📊 Analytics",
        "🏢 MLS — Inmobiliarias",
        "⚖️ Disclaimers Legales",
        "🎓 Estudiantes",
        "🏠 Prefabricadas",
    ]
    # Badge de leads MLS en la opción Analytics
    _analytics_label = f"📊 Analytics{_leads_nuevos_badge}" if _leads_nuevos_badge else "📊 Analytics"
    _ADMIN_DISPLAY_MAP = {s: s for s in _ADMIN_SECCIONES}
    _ADMIN_DISPLAY_MAP["📊 Analytics"] = _analytics_label

    _nav_c1, _nav_c2, _nav_c3 = st.columns([3, 1, 1])
    with _nav_c1:
        _admin_seccion = st.selectbox(
            "🗂️ Sección del panel",
            _ADMIN_SECCIONES,
            format_func=lambda s: _ADMIN_DISPLAY_MAP[s],
            key="admin_nav_select",
            label_visibility="collapsed",
        )
    st.markdown("---")

    if _admin_seccion == "📋 Gestión de Fincas":
        try:
            st.header("Gestión de Fincas Publicadas")
            plots = list_published_plots()
            if plots:
                _STATUS_ICONS = {
                    "disponible": "🟢", "published": "🟢",
                    "reserved": "🟡", "reservada": "🟡",
                    "sold": "🔵", "vendida": "🔵",
                    "no_disponible": "⚫", "suspended": "🔴", "suspendida": "🔴",
                }
                for p in plots:
                    _icon = _STATUS_ICONS.get(p.get("status",""), "⚪")
                    with st.expander(f"{_icon} {p['title']} — {p.get('status','?')} | {p.get('owner_name','Sin propietario')}"):
                        _fi1, _fi2 = st.columns([3, 2])
                        with _fi1:
                            st.markdown("**📋 Datos de la finca**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| ID | `{p['id'][:16]}…` |
| Superficie | {p.get('surface_m2', '—')} m² |
| Precio | €{p.get('price', 0):,.0f} |
| Estado | **{p.get('status','—')}** |
| Dirección | {p.get('address') or '—'} |
| Ref. catastral | `{p.get('catastral_ref') or '—'}` |
| Fecha subida | {str(p.get('created_at') or '—')[:10]} |
""")
                            st.markdown("**👤 Propietario**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {p.get('owner_name') or '—'} |
| Email | {p.get('owner_email') or '—'} |
| Teléfono | {p.get('owner_phone') or '—'} |
""")
                            # Nota catastral
                            _reg = p.get("registry_note_path")
                            if _reg:
                                st.markdown(f"📄 **Nota catastral:** `{_reg}`")
                            else:
                                st.caption("📄 Sin nota catastral adjunta")

                        with _fi2:
                            st.markdown("**⚙️ Cambiar estado**")
                            _current_status = p.get('status', 'published')
                            _btn_col1, _btn_col2, _btn_col3 = st.columns(3)

                            # DISPONIBLE / PUBLICADA
                            with _btn_col1:
                                _is_primary = _current_status in ('disponible', 'published')
                                if st.button("✅ Disponible", key=f"p_btn_disponible_{p['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_plot_status(p['id'], 'disponible'):
                                        st.success("✅ Finca disponible")
                                        st.rerun()

                            # SUSPENDIDA
                            with _btn_col2:
                                _is_primary = _current_status == 'suspended'
                                if st.button("🚫 Suspender", key=f"p_btn_suspended_{p['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_plot_status(p['id'], 'suspended'):
                                        st.warning("🚫 Finca suspendida")
                                        st.rerun()

                            # VENDIDA
                            with _btn_col3:
                                _is_primary = _current_status in ('sold', 'vendida')
                                if st.button("🔵 Vendida", key=f"p_btn_sold_{p['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_plot_status(p['id'], 'sold'):
                                        st.info("🔵 Marcada como vendida")
                                        st.rerun()

                            _btn_col4, _btn_col5, _btn_col6 = st.columns(3)

                            # RESERVADA
                            with _btn_col4:
                                _is_primary = _current_status in ('reserved', 'reservada')
                                if st.button("🟡 Reservada", key=f"p_btn_reserved_{p['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_plot_status(p['id'], 'reserved'):
                                        st.info("🟡 Marcada como reservada")
                                        st.rerun()

                            # NO DISPONIBLE
                            with _btn_col5:
                                _is_primary = _current_status == 'no_disponible'
                                if st.button("⚫ No disponible", key=f"p_btn_no_disponible_{p['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_plot_status(p['id'], 'no_disponible'):
                                        st.warning("⚫ No disponible")
                                        st.rerun()

                            # ELIMINAR (POPOVER)
                            with _btn_col6:
                                with st.popover("🗑️ Eliminar", use_container_width=True):
                                    st.error(f"⚠️ ¿Eliminar '{p['title']}'?")
                                    st.caption("Irreversible. Se eliminará de la base de datos.")
                                    if st.button("❌ Sí, eliminar", key=f"p_btn_delete_{p['id']}", type="primary", use_container_width=True):
                                        try:
                                            _uc = db_conn()
                                            _uc.execute("DELETE FROM plots WHERE id=?", (p["id"],))
                                            _uc.commit()
                                            _uc.close()
                                            st.success("✅ Finca eliminada.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al eliminar: {e}")

                            st.markdown("---")
                            if st.button("📢 Alertar", key=f"p_btn_alert_{p['id']}",
                                         use_container_width=True):
                                try:
                                    from modules.marketplace.alertas import notify_new_plot
                                    _n = notify_new_plot(dict(p))
                                    st.success(f"✅ {_n} email(s)" if _n > 0 else "Sin suscriptores")
                                except Exception as _ae:
                                    st.error(f"Error alertas: {_ae}")

                        # ── Tour 360° ──────────────────────────────────────────
                        st.markdown("---")
                        _has_360 = bool(p.get("tour_360_b64", ""))
                        st.markdown(f"**🔭 Tour Virtual 360°:** {'✅ Activo' if _has_360 else '⬜ Sin tour'}")
                        _up360 = st.file_uploader(
                            "Subir foto equirectangular (JPG/PNG — cualquier móvil en modo 360°)",
                            type=["jpg", "jpeg", "png"],
                            key=f"tour360_{p['id']}"
                        )
                        if _up360:
                            try:
                                import io as _io360
                                import base64 as _b64mod
                                from PIL import Image as _PIL360
                                _img = _PIL360.open(_up360).convert("RGB")
                                if _img.width > 2048:
                                    _ratio = 2048 / _img.width
                                    _img = _img.resize(
                                        (2048, int(_img.height * _ratio)),
                                        _PIL360.Resampling.LANCZOS
                                    )
                                _buf360 = _io360.BytesIO()
                                _img.save(_buf360, format="JPEG", quality=82)
                                _b64_val = _b64mod.b64encode(_buf360.getvalue()).decode()
                                _conn360 = db_conn()
                                try:
                                    _conn360.execute("ALTER TABLE plots ADD COLUMN tour_360_b64 TEXT")
                                    _conn360.commit()
                                except Exception:
                                    pass  # columna ya existe
                                try:
                                    _conn360.execute(
                                        "UPDATE plots SET tour_360_b64=? WHERE id=?",
                                        (_b64_val, p["id"])
                                    )
                                    _conn360.commit()
                                finally:
                                    _conn360.close()
                                st.success("✅ Tour 360° guardado.")
                                st.rerun()
                            except Exception as _e360:
                                st.error(f"Error guardando tour 360°: {_e360}")
            else:
                st.info("No hay fincas publicadas")
        except Exception as e:
            st.error(f"Error en Gestión de Fincas: {e}")

    elif _admin_seccion == "🏗️ Gestión de Proyectos":
        try:
            # Añadir columna status si no existe (ALTER TABLE idempotente)
            try:
                _pc = db_conn()
                _pc.execute("ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'activo'")
                _pc.commit()
                _pc.close()
            except Exception:
                try:
                    _pc.close()
                except Exception:
                    pass

            st.header("Gestión de Proyectos Arquitectónicos")
            projects = list_projects()
            if projects:
                _PROJ_STATUS_ICONS = {
                    "activo": "🟢", "publicado": "🟢",
                    "reservado": "🟡", "vendido": "🔵",
                    "no_disponible": "⚫", "suspendido": "🔴", "eliminado": "🗑️",
                }
                for proj in projects:
                    _pstatus = proj.get("status") or "activo"
                    _picon = _PROJ_STATUS_ICONS.get(_pstatus, "⚪")
                    with st.expander(
                        f"{_picon} {proj['title']} — {proj['architect_name']} | €{proj.get('price',0):,.0f} | {_pstatus}"
                    ):
                        _pj1, _pj2 = st.columns([3, 2])
                        with _pj1:
                            # Imagen
                            _img_path = proj.get('foto_principal') or "assets/branding/logo.png"
                            import os as _os_pj
                            if _img_path and _os_pj.path.exists(_img_path):
                                st.image(_img_path, width=150, caption="Imagen principal")

                            st.markdown("**📋 Datos del proyecto**")
                            _proj_fecha = str(proj.get('created_at') or '—')[:10]
                            _proj_autor = proj.get('architect_name') or '—'
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| ID | `{proj['id'][:16]}…` |
| Título | {proj['title']} |
| Área | {proj.get('area_m2') or '—'} m² |
| Precio | €{proj.get('price', 0):,.0f} |
| Estado | **{_pstatus}** |
| Autor | {_proj_autor} |
| Fecha subida | {_proj_fecha} |
""")
                            st.markdown("**👤 Creado por**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {proj.get('architect_name') or '—'} |
| Empresa | {proj.get('company') or '—'} |
| Email | {proj.get('architect_email') or '—'} |
| Teléfono | {proj.get('architect_phone') or '—'} |
""")
                            if proj.get('description'):
                                with st.expander("Ver descripción"):
                                    st.write(proj['description'])

                        with _pj2:
                            st.markdown("**⚙️ Cambiar estado**")
                            _pb1, _pb2, _pb3 = st.columns(3)

                            # ACTIVO
                            with _pb1:
                                _is_primary = _pstatus == 'activo'
                                if st.button("✅ Activo", key=f"pj_btn_activo_{proj['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_project_status(proj['id'], 'activo'):
                                        st.success("✅ Proyecto activo")
                                        st.rerun()

                            # RESERVADO
                            with _pb2:
                                _is_primary = _pstatus == 'reservado'
                                if st.button("🟡 Reservado", key=f"pj_btn_reservado_{proj['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_project_status(proj['id'], 'reservado'):
                                        st.info("🟡 Proyecto reservado")
                                        st.rerun()

                            # VENDIDO
                            with _pb3:
                                _is_primary = _pstatus in ('vendido', 'vendida')
                                if st.button("🔵 Vendido", key=f"pj_btn_vendido_{proj['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_project_status(proj['id'], 'vendido'):
                                        st.info("🔵 Marcado como vendido")
                                        st.rerun()

                            _pb4, _pb5, _pb6 = st.columns(3)

                            # NO DISPONIBLE
                            with _pb4:
                                _is_primary = _pstatus == 'no_disponible'
                                if st.button("⚫ No disponible", key=f"pj_btn_no_disponible_{proj['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_project_status(proj['id'], 'no_disponible'):
                                        st.warning("⚫ No disponible")
                                        st.rerun()

                            # SUSPENDER
                            with _pb5:
                                _is_primary = _pstatus == 'suspendido'
                                if st.button("🔴 Suspender", key=f"pj_btn_suspendido_{proj['id']}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    if _update_project_status(proj['id'], 'suspendido'):
                                        st.warning("🔴 Proyecto suspendido")
                                        st.rerun()

                            # ELIMINAR (POPOVER)
                            with _pb6:
                                with st.popover("🗑️ Eliminar", use_container_width=True):
                                    st.error(f"⚠️ ¿Eliminar '{proj['title']}'?")
                                    st.caption("Irreversible. Se eliminará de la base de datos.")
                                    if st.button("❌ Sí, eliminar", key=f"pj_btn_delete_{proj['id']}",
                                                 type="primary", use_container_width=True):
                                        try:
                                            _cup = db_conn()
                                            _cup.execute("DELETE FROM projects WHERE id=?", (proj["id"],))
                                            _cup.commit()
                                            _cup.close()
                                            st.success("✅ Proyecto eliminado")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay proyectos publicados aún.")
        except Exception as e:
            st.error(f"Error en Gestión de Proyectos: {e}")

    elif _admin_seccion == "💰 Ventas y Transacciones":
        st.header("💰 Ventas y Transacciones — Todos los flujos")
        import sqlite3 as _sq3, pandas as _pd3

        def _read3(conn, sql):
            cur = conn.execute(sql)
            rows = cur.fetchall()
            if not rows:
                return _pd3.DataFrame()
            cols = [d[0] for d in (cur.description or [])]
            data = []
            for r in rows:
                try:
                    data.append([r[i] for i in range(len(cols))])
                except Exception:
                    data.append([r[c] for c in cols])
            return _pd3.DataFrame(data, columns=cols)

        # ── KPIs de ingresos ──────────────────────────────────────────────────
        try:
            _db3 = db_conn()

            _rev_fincas = float(_db3.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()[0])
            _n_res3     = _db3.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]

            _n_subs, _mrr = 0, 0.0
            try:
                _subs_row = _db3.execute(
                    "SELECT COUNT(*), COALESCE(SUM(price),0) FROM subscriptions WHERE status='active'"
                ).fetchone()
                _n_subs, _mrr = int(_subs_row[0]), float(_subs_row[1])
            except Exception:
                pass

            _n_ai_proj = 0
            try:
                _n_ai_proj = _db3.execute("SELECT COUNT(*) FROM ai_projects").fetchone()[0]
            except Exception:
                pass

            _n_estudio = 0
            try:
                _n_estudio = _db3.execute("SELECT COUNT(*) FROM estudio_projects").fetchone()[0]
            except Exception:
                pass

            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("🏡 Ingresos fincas", f"€{_rev_fincas:,.0f}", delta=f"{_n_res3} operaciones")
            _k2.metric("💎 Suscripciones activas", _n_subs, delta=f"MRR €{_mrr:,.0f}")
            _k3.metric("🏠 Proyectos AI pagados", _n_ai_proj)
            _k4.metric("🎨 Proyectos Modo Estudio", _n_estudio)
            _db3.close()
        except Exception as _ek3:
            st.warning(f"Error KPIs: {_ek3}")

        st.markdown("---")

        # ── 1. Reservas y compras de fincas ──────────────────────────────────
        st.subheader("🏡 Reservas y Compras de Fincas")
        try:
            _db3b = db_conn()
            # Asegurar que columnas de comprador existen (migraciones antiguas)
            for _col_r, _def_r in [("buyer_dni","TEXT"), ("buyer_domicilio","TEXT"), ("buyer_province","TEXT")]:
                try:
                    _db3b.execute(f"ALTER TABLE reservations ADD COLUMN {_col_r} {_def_r}")
                    _db3b.commit()
                except Exception:
                    pass
            _df_res3 = _read3(
                _db3b,
                """SELECT r.id, r.buyer_name, r.buyer_email,
                          COALESCE(r.buyer_dni, '—') as buyer_dni,
                          COALESCE(r.buyer_domicilio, '—') as buyer_domicilio,
                          COALESCE(r.buyer_province, '—') as buyer_province,
                          p.title as finca,
                          r.amount, r.kind, r.created_at
                   FROM reservations r LEFT JOIN plots p ON r.plot_id=p.id
                   ORDER BY r.created_at DESC"""
            )
            _db3b.close()
            if not _df_res3.empty:
                _STATUS_LABELS = {
                    "purchase": "✅ Compra", "reservation": "🔒 Reserva 7d",
                    "pending": "⏳ Pendiente pago", "en_tramitacion": "⚙️ En tramitación",
                    "aceptado": "✅ Aceptada", "compra_completa": "🏡 Compra completada",
                }
                _df_res3["estado"] = _df_res3["kind"].map(_STATUS_LABELS).fillna(_df_res3["kind"])

                # Vista compacta con todos los datos
                st.dataframe(
                    _df_res3[[
                        "id","buyer_name","buyer_email","finca","amount","estado","created_at"
                    ]].rename(columns={
                        "id": "ID", "buyer_name": "Comprador", "buyer_email": "Email",
                        "finca": "Finca", "amount": "Importe (€)",
                        "estado": "Estado", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )

                # Fichas detalladas de cada comprador
                st.markdown("**👤 Ficha detallada por comprador:**")
                for _, _rrow in _df_res3.iterrows():
                    with st.expander(
                        f"{_rrow['estado']} — {_rrow['buyer_name']} | {_rrow['finca']} | €{_rrow['amount']:,.0f}",
                        expanded=False
                    ):
                        _rc1, _rc2 = st.columns(2)
                        with _rc1:
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {_rrow['buyer_name']} |
| Email | {_rrow['buyer_email']} |
| DNI/NIE | {_rrow['buyer_dni']} |
| Domicilio | {_rrow['buyer_domicilio']} |
| Provincia | {_rrow['buyer_province']} |
| Fecha | {str(_rrow['created_at'])[:16]} |
""")
                        with _rc2:
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Finca | {_rrow['finca']} |
| Importe | €{_rrow['amount']:,.0f} |
| Estado | {_rrow['estado']} |
| ID reserva | `{str(_rrow['id'])[:16]}` |
""")
                            # Mailto directo
                            st.markdown(f"[✉️ Escribir al comprador](mailto:{_rrow['buyer_email']})")

                # Gestión de estado
                st.markdown("**⚙️ Actualizar estado de reserva:**")
                _col_r1, _col_r2, _col_r3, _col_r4 = st.columns(4)
                with _col_r1:
                    _res_ids = _df_res3["id"].tolist()
                    _res_sel = st.selectbox("Reserva a gestionar", _res_ids, key="intra_res_sel") if _res_ids else None
                with _col_r2:
                    _new_status = st.selectbox(
                        "Nuevo estado", ["en_tramitacion", "aceptado", "compra_completa"],
                        key="intra_res_status"
                    )
                with _col_r3:
                    if _res_sel and _new_status and st.button("✅ Actualizar", key="intra_res_update", type="primary", use_container_width=True):
                        try:
                            _db_up = db_conn()
                            _db_up.execute(
                                "UPDATE reservations SET kind=? WHERE id=?", (_new_status, _res_sel)
                            )
                            _db_up.commit()
                            _db_up.close()
                            try:
                                _buyer_r = _df_res3[_df_res3["id"]==_res_sel].iloc[0]
                                from modules.marketplace.email_notify import _send as _t_send
                                _lbl = {"en_tramitacion":"⚙️ en tramitación","aceptado":"✅ aceptada","compra_completa":"🏡 completada"}
                                _t_send(f"📋 Admin actualizó reserva {str(_res_sel)[:8]}… → {_lbl.get(_new_status, _new_status)}\nComprador: {_buyer_r['buyer_email']}")
                            except Exception:
                                pass
                            st.success(f"Estado actualizado a '{_new_status}'")
                            st.rerun()
                        except Exception as _eu:
                            st.error(f"Error: {_eu}")

                with _col_r4:
                    if _res_sel:
                        with st.popover("🗑️ Eliminar", use_container_width=True):
                            st.error("⚠️ ¿Eliminar reserva?")
                            st.caption("La acción no se puede deshacer.")
                            if st.button("❌ Sí, eliminar", key=f"intra_res_del_yes_{_res_sel}", type="primary", use_container_width=True):
                                try:
                                    _db_del = db_conn()
                                    _db_del.execute("DELETE FROM reservations WHERE id=?", (_res_sel,))
                                    _db_del.commit()
                                    _db_del.close()
                                    st.success("✅ Reserva eliminada.")
                                    st.rerun()
                                except Exception as _edel:
                                    st.error(f"Error al eliminar: {_edel}")
            else:
                st.info("Sin reservas ni compras todavía.")
        except Exception as _er3:
            st.error(f"Error reservas: {_er3}")

        st.markdown("---")

        # ── 2. Suscripciones de Arquitectos ──────────────────────────────────
        st.subheader("💎 Suscripciones de Arquitectos (Planes BASIC / PRO / ENTERPRISE)")
        try:
            _db3c = db_conn()
            _df_subs = _read3(
                _db3c,
                """SELECT s.id, COALESCE(a.name, u.name) as arquitecto,
                          COALESCE(a.email, u.email) as email,
                          s.plan_type as plan, s.price as precio_mes,
                          s.monthly_proposals_limit as limite,
                          s.commission_rate as comision,
                          s.status, s.start_date, s.end_date
                   FROM subscriptions s
                   LEFT JOIN architects a ON s.architect_id = a.id
                   LEFT JOIN users u ON s.architect_id = u.id
                   ORDER BY s.created_at DESC"""
            )
            _db3c.close()
            if not _df_subs.empty:
                _df_subs["precio_mes"] = _df_subs["precio_mes"].apply(lambda x: f"€{x:,.0f}/mes")
                _df_subs["comision"]   = _df_subs["comision"].apply(lambda x: f"{x}%")
                st.dataframe(
                    _df_subs.rename(columns={
                        "id": "Sub ID", "arquitecto": "Arquitecto", "email": "Email",
                        "plan": "Plan", "precio_mes": "Precio", "limite": "Proyectos",
                        "comision": "Comisión", "status": "Estado",
                        "start_date": "Inicio", "end_date": "Vencimiento"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin suscripciones activas todavía.")
        except Exception as _es3:
            st.error(f"Error suscripciones: {_es3}")

        st.markdown("---")

        # ── 3. Proyectos AI Designer pagados ─────────────────────────────────
        st.subheader("🏠 Proyectos AI Designer — Pagos Realizados")
        try:
            _db3d = db_conn()
            _df_ai = _read3(
                _db3d,
                """SELECT client_email, project_name, total_area, total_cost,
                          style, energy_label, status, created_at
                   FROM ai_projects ORDER BY created_at DESC"""
            )
            _db3d.close()
            if not _df_ai.empty:
                _df_ai["total_cost"] = _df_ai["total_cost"].apply(lambda x: f"€{x:,.0f}")
                _df_ai["total_area"] = _df_ai["total_area"].apply(lambda x: f"{x:.0f} m²")
                st.dataframe(
                    _df_ai.rename(columns={
                        "client_email": "Email cliente", "project_name": "Proyecto",
                        "total_area": "Superficie", "total_cost": "Coste total",
                        "style": "Estilo", "energy_label": "Energía",
                        "status": "Estado", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin proyectos AI Designer pagados todavía.")
        except Exception as _eai3:
            st.error(f"Error proyectos AI: {_eai3}")

        st.markdown("---")

        # ── 4. Proyectos Modo Estudio ─────────────────────────────────────────
        st.subheader("🎨 Proyectos Modo Estudio — Arquitectos")
        try:
            _db3e = db_conn()
            _df_est = _read3(
                _db3e,
                """SELECT ep.architect_id,
                          COALESCE(a.name, u.name) as arquitecto,
                          COALESCE(a.email, u.email) as email,
                          ep.address, ep.surface_m2, ep.style, ep.budget,
                          ep.total_cost, ep.paid, ep.created_at
                   FROM estudio_projects ep
                   LEFT JOIN architects a ON ep.architect_id = a.id
                   LEFT JOIN users u ON ep.architect_id = u.id
                   ORDER BY ep.created_at DESC"""
            )
            _db3e.close()
            if not _df_est.empty:
                _df_est["paid"]       = _df_est["paid"].map({1: "✅ Pagado", 0: "⏳ Pendiente"})
                _df_est["budget"]     = _df_est["budget"].apply(lambda x: f"€{x:,.0f}" if x else "—")
                _df_est["total_cost"] = _df_est["total_cost"].apply(lambda x: f"€{x:,.0f}" if x else "—")
                _df_est["surface_m2"] = _df_est["surface_m2"].apply(lambda x: f"{x:.0f} m²" if x else "—")
                st.dataframe(
                    _df_est.rename(columns={
                        "arquitecto": "Arquitecto", "email": "Email",
                        "address": "Dirección", "surface_m2": "Superficie",
                        "style": "Estilo", "budget": "Presupuesto",
                        "total_cost": "Coste generado", "paid": "Pago", "created_at": "Fecha"
                    }).drop(columns=["architect_id"], errors="ignore"),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin proyectos Modo Estudio todavía.")
        except Exception as _ee3:
            st.error(f"Error proyectos estudio: {_ee3}")

        st.markdown("---")

        # ── 5. Stripe — Todos los pagos ───────────────────────────────────────
        with st.expander("💳 Stripe — Todos los pagos (tiempo real)", expanded=False):
            try:
                from modules.stripe_utils import list_recent_sessions as _lrs3
                _stripe_all = _lrs3(limit=100)
                _rows3 = []
                _stripe_data3 = getattr(_stripe_all, "data", None) or list(_stripe_all)
                for _ss3 in _stripe_data3:
                    try:
                        _meta3 = dict(getattr(_ss3, "metadata", None) or {})
                    except Exception:
                        _meta3 = {}
                    _rows3.append({
                        "Fecha":      _pd3.to_datetime(getattr(_ss3, "created", 0), unit="s").strftime("%d/%m/%Y %H:%M"),
                        "Email":      getattr(_ss3, "customer_email", None) or _meta3.get("client_email", "—"),
                        "Concepto":   _meta3.get("products", _meta3.get("mode", _meta3.get("project", "—"))),
                        "Importe (€)": (getattr(_ss3, "amount_total", 0) or 0) / 100,
                        "Estado":     "✅ Pagado" if getattr(_ss3, "payment_status", "") == "paid" else "⏳ Pendiente",
                        "Session ID": (getattr(_ss3, "id", "") or "")[-20:],
                    })
                if _rows3:
                    _df_st3 = _pd3.DataFrame(_rows3)
                    _paid3  = _df_st3[_df_st3["Estado"] == "✅ Pagado"]["Importe (€)"].sum()
                    _sc1, _sc2 = st.columns(2)
                    _sc1.metric("💶 Total cobrado (Stripe)", f"€{_paid3:,.2f}")
                    _sc2.metric("🧾 Sesiones totales", len(_rows3))
                    st.dataframe(_df_st3, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin sesiones Stripe todavía. Usa tarjeta 4242 4242 4242 4242 para test.")
            except Exception as _est3:
                st.warning(f"Stripe error: {type(_est3).__name__}: {_est3}")

    elif _admin_seccion == "💎 Suscripciones & Proyectos AI":
        try:
            st.header("💎 Suscripciones & Proyectos AI — Gestión de Estados")

            # Tabs para separar gestión
            _tab_subs, _tab_ai = st.tabs(["📋 Suscripciones", "🏠 Proyectos AI"])

            with _tab_subs:
                st.subheader("Suscripciones de Arquitectos")
                _db_subs = db_conn()
                try:
                    _subs_rows = _db_subs.execute("""
                        SELECT s.id, COALESCE(a.name, u.name) as nombre, COALESCE(a.email, u.email) as email,
                               s.plan_type as plan, s.price, s.status, s.start_date, s.end_date, s.created_at
                        FROM subscriptions s
                        LEFT JOIN architects a ON s.architect_id = a.id
                        LEFT JOIN users u ON s.architect_id = u.id
                        ORDER BY s.created_at DESC
                    """).fetchall()
                finally:
                    _db_subs.close()

                if not _subs_rows:
                    st.info("Sin suscripciones todavía.")
                else:
                    for _srow in _subs_rows:
                        _sid, _sname, _semail, _splan, _sprice, _sstatus, _sstart, _send, _scat = _srow
                        _status_icon = "✅" if _sstatus == "active" else ("⏳" if _sstatus == "pending" else "❌")
                        with st.expander(f"{_status_icon} {_sname} — Plan {_splan} | {_sstatus}"):
                            _sc1, _sc2 = st.columns([3, 2])
                            with _sc1:
                                st.markdown(f"""
| Campo | Valor |
|---|---|
| Email | {_semail} |
| Plan | {_splan} |
| Precio | €{_sprice:.0f}/mes |
| Estado | **{_sstatus}** |
| Inicio | {(_sstart or '—')[:10]} |
| Vencimiento | {(_send or '—')[:10]} |
| Registrado | {(_scat or '—')[:10]} |
""")
                            with _sc2:
                                st.markdown("**Cambiar estado**")
                                _is_primary = _sstatus == 'pending'
                                if st.button("⏳ En trámite", key=f"sub_pending_{_sid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _sc_conn = db_conn()
                                    _sc_conn.execute("UPDATE subscriptions SET status=?, is_active=0 WHERE id=?", ("pending", _sid))
                                    _sc_conn.commit(); _sc_conn.close()
                                    st.info("En trámite")
                                    st.rerun()
                                _is_primary = _sstatus == 'active'
                                if st.button("✅ Autorizada", key=f"sub_active_{_sid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _ac_conn = db_conn()
                                    _ac_conn.execute("UPDATE subscriptions SET status=?, is_active=1 WHERE id=?", ("active", _sid))
                                    _ac_conn.commit(); _ac_conn.close()
                                    st.success("Autorizada ✅")
                                    st.rerun()
                                _is_primary = _sstatus == 'suspended'
                                if st.button("🔴 Suspender", key=f"sub_suspended_{_sid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _sus_conn = db_conn()
                                    _sus_conn.execute("UPDATE subscriptions SET status=?, is_active=0 WHERE id=?", ("suspended", _sid))
                                    _sus_conn.commit(); _sus_conn.close()
                                    st.warning("Suspendida")
                                    st.rerun()
                                _is_primary = _sstatus == 'cancelled'
                                if st.button("❌ Anular", key=f"sub_cancelled_{_sid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _can_conn = db_conn()
                                    _can_conn.execute("UPDATE subscriptions SET status=?, is_active=0 WHERE id=?", ("cancelled", _sid))
                                    _can_conn.commit(); _can_conn.close()
                                    st.error("Anulada")
                                    st.rerun()
                                with st.popover("🗑️ Eliminar", use_container_width=True):
                                    st.error(f"⚠️ ¿Eliminar suscripción de {_sname}?")
                                    st.caption("Irreversible.")
                                    if st.button("❌ Sí, eliminar", key=f"sub_del_yes_{_sid}",
                                                 type="primary", use_container_width=True):
                                        _del_conn = db_conn()
                                        _del_conn.execute("DELETE FROM subscriptions WHERE id=?", (_sid,))
                                        _del_conn.commit(); _del_conn.close()
                                        st.success("Suscripción eliminada")
                                        st.rerun()

            with _tab_ai:
                st.subheader("Proyectos AI Designer")
                _db_ai = db_conn()
                try:
                    _ai_rows = _db_ai.execute("""
                        SELECT id, client_email, project_name, total_area, total_cost, style,
                               status, created_at
                        FROM ai_projects
                        ORDER BY created_at DESC
                    """).fetchall()
                finally:
                    _db_ai.close()

                if not _ai_rows:
                    st.info("Sin proyectos AI todavía.")
                else:
                    for _arow in _ai_rows:
                        _aid, _aemail, _aname, _aarea, _acost, _astyle, _astatus, _acat = _arow
                        _ai_status_icon = "✅" if _astatus == "activo" else ("⏳" if _astatus == "en_tramite" else "❌")
                        with st.expander(f"{_ai_status_icon} {_aname} — €{_acost:,.0f} | {_astatus}"):
                            _aic1, _aic2 = st.columns([3, 2])
                            with _aic1:
                                st.markdown(f"""
| Campo | Valor |
|---|---|
| Cliente | {_aemail} |
| Proyecto | {_aname} |
| Área | {_aarea:.0f} m² |
| Coste | €{_acost:,.0f} |
| Estilo | {_astyle} |
| Estado | **{_astatus}** |
| Fecha | {(_acat or '—')[:10]} |
""")
                            with _aic2:
                                st.markdown("**Cambiar estado**")
                                _is_primary = _astatus == 'en_tramite'
                                if st.button("⏳ En trámite", key=f"ai_pending_{_aid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _ai_conn = db_conn()
                                    _ai_conn.execute("UPDATE ai_projects SET status=?, is_active=0 WHERE id=?", ("en_tramite", _aid))
                                    _ai_conn.commit(); _ai_conn.close()
                                    st.info("En trámite")
                                    st.rerun()
                                _is_primary = _astatus == 'activo'
                                if st.button("✅ Autorizado", key=f"ai_active_{_aid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _aiac_conn = db_conn()
                                    _aiac_conn.execute("UPDATE ai_projects SET status=?, is_active=1 WHERE id=?", ("activo", _aid))
                                    _aiac_conn.commit(); _aiac_conn.close()
                                    st.success("Autorizado ✅")
                                    st.rerun()
                                _is_primary = _astatus == 'suspendido'
                                if st.button("🔴 Suspender", key=f"ai_suspended_{_aid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _ai_sus = db_conn()
                                    _ai_sus.execute("UPDATE ai_projects SET status=?, is_active=0 WHERE id=?", ("suspendido", _aid))
                                    _ai_sus.commit(); _ai_sus.close()
                                    st.warning("Suspendido")
                                    st.rerun()
                                _is_primary = _astatus == 'anulado'
                                if st.button("❌ Anular", key=f"ai_cancelled_{_aid}",
                                             use_container_width=True, type="primary" if _is_primary else "secondary"):
                                    _ai_can = db_conn()
                                    _ai_can.execute("UPDATE ai_projects SET status=?, is_active=0 WHERE id=?", ("anulado", _aid))
                                    _ai_can.commit(); _ai_can.close()
                                    st.error("Anulado")
                                    st.rerun()
                                with st.popover("🗑️ Eliminar", use_container_width=True):
                                    st.error(f"⚠️ ¿Eliminar proyecto '{_aname}'?")
                                    st.caption("Irreversible.")
                                    if st.button("❌ Sí, eliminar", key=f"ai_del_yes_{_aid}",
                                                 type="primary", use_container_width=True):
                                        _ai_del = db_conn()
                                        _ai_del.execute("DELETE FROM ai_projects WHERE id=?", (_aid,))
                                        _ai_del.commit(); _ai_del.close()
                                        st.success("Proyecto eliminado")
                                        st.rerun()

        except Exception as _e_subs_ai:
            st.error(f"Error en Suscripciones & Proyectos AI: {_e_subs_ai}")

    elif _admin_seccion == "📞 Consultas y Soporte":
        try:
            st.header("📞 Consultas y Soporte")
            _ts_conn = db_conn()
            try:
                # ── KPIs ─────────────────────────────────────────────────────
                _n_pend  = _ts_conn.execute("SELECT COUNT(*) FROM tickets_soporte WHERE estado='pendiente'").fetchone()[0]
                _n_resp  = _ts_conn.execute("SELECT COUNT(*) FROM tickets_soporte WHERE estado='respondido'").fetchone()[0]
                _n_total = _ts_conn.execute("SELECT COUNT(*) FROM tickets_soporte").fetchone()[0]
                _tc1, _tc2, _tc3 = st.columns(3)
                _tc1.metric("Total consultas", _n_total)
                _tc2.metric("⏳ Pendientes", _n_pend)
                _tc3.metric("✅ Respondidas", _n_resp)

                # ── Filtro estado ─────────────────────────────────────────────
                _ts_fil = st.selectbox("Estado", ["Todos", "pendiente", "respondido", "cerrado"], key="ts_estado_fil")
                _ts_where = f"WHERE estado='{_ts_fil}'" if _ts_fil != "Todos" else ""

                _tickets = _ts_conn.execute(f"""
                    SELECT id,
                           COALESCE(usuario_nombre, inmo_nombre, '—') as nombre,
                           COALESCE(usuario_tipo, 'inmo') as tipo,
                           COALESCE(usuario_email, '') as email,
                           asunto, mensaje, lola_respuesta,
                           admin_respuesta, estado, created_at
                    FROM tickets_soporte {_ts_where}
                    ORDER BY created_at DESC
                """).fetchall()

                if not _tickets:
                    st.info("No hay consultas todavía. Cuando un usuario envíe una pregunta aparecerá aquí.")
                else:
                    _tipo_ico = {"inmo": "🏢", "cliente": "👤", "arquitecto": "🏗️"}
                    for _tkt in _tickets:
                        _tid, _tnom, _ttipo, _temail, _tasunto, _tmsg, _tlola, _tadmin, _testado, _tdate = _tkt
                        _badge = {"pendiente": "🔴", "respondido": "✅", "cerrado": "⚫"}.get(_testado, "❓")
                        _ico = _tipo_ico.get(_ttipo, "❓")
                        with st.expander(
                            f"{_badge} {_ico} {_tnom} — {_tasunto or 'Sin asunto'} · {(_tdate or '')[:10]}",
                            expanded=(_testado == "pendiente")
                        ):
                            st.caption(f"Tipo: **{_ttipo}** · {_temail or '—'}")
                            st.markdown(f"**Consulta:**\n\n{_tmsg}")
                            if _tlola:
                                st.markdown(f"**Lola respondió automáticamente:**\n\n_{_tlola}_")
                            if _tadmin:
                                st.markdown(f"**Tu respuesta:**\n\n{_tadmin}")

                            if _testado == "pendiente":
                                _resp_txt = st.text_area("Escribe tu respuesta:", key=f"ts_resp_{_tid}", height=120)
                                _rb1, _rb2 = st.columns([2, 1])
                                if _rb1.button("Enviar respuesta", key=f"ts_send_{_tid}", type="primary"):
                                    if _resp_txt.strip():
                                        _ts_conn.execute(
                                            """UPDATE tickets_soporte
                                               SET admin_respuesta=?, estado='respondido',
                                                   respondido_at=datetime('now')
                                               WHERE id=?""",
                                            (_resp_txt.strip(), _tid)
                                        )
                                        _ts_conn.commit()
                                        st.success("Respuesta enviada.")
                                        st.rerun()
                                    else:
                                        st.warning("Escribe una respuesta antes de enviar.")
                                if _rb2.button("Cerrar ticket", key=f"ts_close_{_tid}"):
                                    _ts_conn.execute(
                                        "UPDATE tickets_soporte SET estado='cerrado' WHERE id=?", (_tid,)
                                    )
                                    _ts_conn.commit()
                                    st.rerun()
            finally:
                _ts_conn.close()
        except Exception as e:
            st.error(f"Error en Consultas y Soporte: {e}")

    elif _admin_seccion == "🛠️ Profesionales":
        try:
            st.header("🛠️ Gestión de Profesionales / Constructores")

            _conn5 = db_conn()
            # Añadir columnas si no existen
            for _col, _def in [("is_featured","INTEGER DEFAULT 0"),
                                ("featured_until","TEXT"),
                                ("featured_plan","TEXT DEFAULT 'free'"),
                                ("active","INTEGER DEFAULT 0"),
                                ("status","TEXT DEFAULT 'pendiente'"),
                                ("is_active","INTEGER DEFAULT 0")]:
                try:
                    _conn5.execute(f"ALTER TABLE service_providers ADD COLUMN {_col} {_def}")
                    _conn5.commit()
                except Exception:
                    try:
                        _conn5.rollback()
                    except Exception:
                        pass

            # RESET: Forzar todos los profesionales a pendiente (solo UNA VEZ por sesión)
            if not st.session_state.get("_reset_professionals_done", False):
                try:
                    _conn5.execute("UPDATE service_providers SET status='pendiente' WHERE status IS NULL OR status = '' OR status = 'activo'")
                    _conn5.commit()
                    st.session_state["_reset_professionals_done"] = True
                except Exception:
                    pass

            _providers5 = _conn5.execute("""
                SELECT id, name, email, company, specialty, experience_years,
                       service_area, is_featured, featured_until, featured_plan,
                       created_at, active, status, is_active
                FROM service_providers ORDER BY is_featured DESC, name
            """).fetchall()
            _conn5.close()

            if not _providers5:
                st.info("No hay profesionales registrados aún.")
            else:
                # KPIs
                _n_feat = sum(1 for p in _providers5 if p[7])
                _n_free = len(_providers5) - _n_feat
                _n_blocked = sum(1 for p in _providers5 if not p[11])
                def _kpi_tarifas_activas() -> int:
                    try:
                        _tc = db_conn()
                        try:
                            _tr = _tc.execute(
                                "SELECT COUNT(*) FROM tarifas_profesionales WHERE activo = 1"
                            ).fetchone()
                            return _tr[0] if _tr else 0
                        finally:
                            _tc.close()
                    except Exception:
                        return 0

                _k1, _k2, _k3, _k4, _k5 = st.columns(5)
                _k1.metric("👷 Total constructores", len(_providers5))
                _k2.metric("⭐ Destacados (€99/mes)", _n_feat,
                           delta=f"€{_n_feat*99}/mes MRR")
                _k3.metric("🆓 Plan gratuito", _n_free)
                _k4.metric("🚫 Bloqueados", _n_blocked)
                _k5.metric("💶 Tarifas activas", _kpi_tarifas_activas())

                st.markdown("---")
                st.caption("Gestiona el estado de cada profesional: activar Destacado, aprobar, bloquear o eliminar.")

                for _p5 in _providers5:
                    (_pid5, _name5, _email5, _comp5, _spec5, _exp5,
                     _area5, _feat5, _funtil5, _fplan5, _cat5, _active5, _status5, _is_active5) = _p5
                    # Ícono basado en status, no en active
                    if _status5 == 'activo':
                        _status_icon = "🟢"
                    elif _status5 == 'bloqueado':
                        _status_icon = "🔴"
                    else:  # pendiente, tramite, NULL
                        _status_icon = "🟡"
                    _badge = "⭐ DESTACADO" if _feat5 else "🆓 Gratuito"
                    with st.expander(f"{_status_icon} {_badge} · {_name5} ({_email5}) — {_area5}"):
                        _ci1, _ci2 = st.columns(2)
                        with _ci1:
                            st.markdown(f"""
<div style="font-size:12px;color:#CBD5E1;line-height:1.9;">
  <b>Empresa:</b> {_comp5 or '—'}<br>
  <b>Especialidad:</b> {_spec5 or '—'}<br>
  <b>Experiencia:</b> {_exp5} años<br>
  <b>Zona:</b> {_area5 or '—'}<br>
  <b>Plan solicitado:</b> {_fplan5 or 'free'}<br>
  <b>Registrado:</b> {(_cat5 or '')[:10]}<br>
  <b>Estado:</b> {_status5 or 'pendiente'}
</div>""", unsafe_allow_html=True)
                        with _ci2:
                            # ── Destacado ──
                            st.markdown("**Plan Destacado**", help="Marca esta casilla para conceder acceso Destacado (pagado o cortesía)")
                            _new_feat = st.checkbox(
                                "Activar Destacado (€99/mes o cortesía)",
                                value=bool(_feat5),
                                key=f"feat_{_pid5}"
                            )
                            _new_until = st.text_input(
                                "Válido hasta (YYYY-MM-DD)",
                                value=_funtil5 or "",
                                key=f"until_{_pid5}",
                                placeholder="2026-12-31"
                            )
                            if st.button("💾 Guardar Destacado", key=f"savefeat_{_pid5}",
                                         type="primary", use_container_width=True,
                                         help="Guarda el estado Destacado y la fecha de validez para este profesional"):
                                try:
                                    _conn_upd = db_conn()
                                    _conn_upd.execute(
                                        "UPDATE service_providers SET is_featured=?, featured_until=? WHERE id=?",
                                        (int(_new_feat), _new_until or None, _pid5)
                                    )
                                    _conn_upd.commit()
                                    _conn_upd.close()
                                    st.cache_data.clear()
                                    try:
                                        from modules.marketplace.email_notify import _send
                                        _status = "ACTIVADO ⭐" if _new_feat else "desactivado"
                                        _send(f"⭐ <b>Plan Destacado {_status}</b>\n{_name5} ({_email5})\nVálido hasta: {_new_until or 'indefinido'}")
                                    except Exception:
                                        pass
                                    st.success(f"✅ Destacado de {_name5} actualizado.")
                                    st.rerun()
                                except Exception as _err_feat:
                                    st.error(f"Error guardando destacado: {_err_feat}")

                            st.markdown("---")
                            # DEBUG
                            st.caption(f"🔧 Status BD: `{_status5}` | Active: `{_active5}` | is_active: `{_is_active5}` | ID: `{_pid5}`")

                            # ── Aprobar / Bloquear ──
                            _bc1, _bc2, _bc3 = st.columns(3)
                            with _bc1:
                                _is_prim_apr = (_status5 == 'activo')
                                if st.button("✅ APROBAR 🟢", key=f"btn_prof_approve_{_pid5}",
                                             use_container_width=True,
                                             type="primary" if _is_prim_apr else "secondary"):
                                    try:
                                        _ca = db_conn()
                                        try:
                                            _ca.execute("UPDATE service_providers SET active=1, status=?, is_active=? WHERE id=?", ("activo", 1, _pid5))
                                            _ca.commit()
                                        finally:
                                            _ca.close()
                                        st.cache_data.clear()
                                        st.success(f"✅ {_name5} aprobado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")

                            with _bc2:
                                _is_prim_tram = (_status5 == 'tramite')
                                if st.button("⏳ EN TRÁMITE 🟡", key=f"btn_prof_tramite_{_pid5}",
                                             use_container_width=True,
                                             type="primary" if _is_prim_tram else "secondary"):
                                    try:
                                        _cp = db_conn()
                                        try:
                                            _cp.execute("UPDATE service_providers SET status=?, is_active=? WHERE id=?", ("tramite", 0, _pid5))
                                            _cp.commit()
                                        finally:
                                            _cp.close()
                                        st.cache_data.clear()
                                        st.info("En trámite")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                                        import traceback
                                        st.code(traceback.format_exc())

                            with _bc3:
                                _is_prim_bloq = (_status5 == 'bloqueado')
                                if st.button("🚫 BLOQUEAR 🔴", key=f"btn_prof_block_{_pid5}",
                                             use_container_width=True,
                                             type="primary" if _is_prim_bloq else "secondary"):
                                    try:
                                        _cb = db_conn()
                                        try:
                                            _cb.execute("UPDATE service_providers SET active=0, is_featured=0, status=? WHERE id=?", ("bloqueado", _pid5))
                                            _cb.commit()
                                        finally:
                                            _cb.close()
                                        st.cache_data.clear()
                                        st.warning(f"🚫 {_name5} bloqueado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")

        except Exception as e:
            st.error(f"Error en Gestión de Profesionales: {e}")

        # ── Tablón de obras + comisiones ─────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🏗️ Tablón de Obras y Comisiones")
        try:
            from modules.marketplace.utils import db_conn as _dc_tab
            _ct = _dc_tab()
            # KPIs
            _n_tab   = (_ct.execute("SELECT COUNT(*) FROM project_tablon WHERE active=1").fetchone() or [0])[0]
            _n_of    = (_ct.execute("SELECT COUNT(*) FROM construction_offers").fetchone() or [0])[0]
            _n_acep  = (_ct.execute("SELECT COUNT(*) FROM construction_offers WHERE estado='aceptada'").fetchone() or [0])[0]
            _n_com   = (_ct.execute("SELECT COUNT(*) FROM construction_offers WHERE estado='aceptada' AND comision_pagada=1").fetchone() or [0])[0]
            _n_pend  = _n_acep - _n_com
            # Ingresos comisiones
            _ing_com = _ct.execute("""
                SELECT COALESCE(SUM(CASE WHEN includes_materials=1 THEN price_with_mat ELSE price_no_mat END * 0.03),0)
                FROM construction_offers WHERE estado='aceptada' AND comision_pagada=1
            """).fetchone()
            _ing_eur = float((_ing_com or [0])[0] or 0)
            _ct.close()

            _ki1, _ki2, _ki3, _ki4, _ki5 = st.columns(5)
            _ki1.metric("📋 Proyectos activos", _n_tab)
            _ki2.metric("📨 Ofertas enviadas", _n_of)
            _ki3.metric("✅ Ofertas aceptadas", _n_acep)
            _ki4.metric("💳 Comisiones pendientes", _n_pend,
                        delta=f"€{_n_pend * 0:.0f}" if _n_pend == 0 else None)
            _ki5.metric("💰 Ingresos comisiones", f"€{_ing_eur:,.0f}")

            # Proyectos activos
            st.markdown("**Proyectos en el tablón:**")
            _ct2 = _dc_tab()
            _tabs_rows = _ct2.execute("""
                SELECT id,client_email,project_name,province,total_area,total_cost,created_at,
                       (SELECT COUNT(*) FROM construction_offers co WHERE co.tablon_id=pt.id) as n_ofertas
                FROM project_tablon pt WHERE active=1 ORDER BY created_at DESC LIMIT 20
            """).fetchall()
            _ct2.close()
            if _tabs_rows:
                for _tr in _tabs_rows:
                    _tid_a, _cemail_a, _pname_a, _prov_a, _area_a, _cost_a, _cat_a, _nof_a = _tr
                    st.markdown(
                        f"• **{_pname_a or '—'}** · {_prov_a} · {_area_a:.0f} m² · €{_cost_a:,.0f} "
                        f"· {_nof_a} oferta(s) · `{(_cat_a or '')[:10]}`",
                    )
            else:
                st.info("No hay proyectos activos en el tablón.")

            # Comisiones pendientes de pago
            if _n_pend > 0:
                st.markdown("**⚠️ Comisiones pendientes de cobro:**")
                _ct3 = _dc_tab()
                _pend_rows = _ct3.execute("""
                    SELECT co.id, co.provider_name, co.provider_email,
                           co.project_name, co.client_email,
                           CASE WHEN co.includes_materials=1 THEN co.price_with_mat ELSE co.price_no_mat END as precio,
                           co.created_at
                    FROM construction_offers co
                    WHERE co.estado='aceptada' AND COALESCE(co.comision_pagada,0)=0
                    ORDER BY co.created_at DESC
                """).fetchall()
                _ct3.close()
                for _pr in _pend_rows:
                    _oid_p, _prov_n, _prov_e, _pname_p, _cemail_p, _precio_p, _cat_p = _pr
                    _com_p = float(_precio_p or 0) * 0.03
                    st.warning(
                        f"💳 Constructor: **{_prov_n}** ({_prov_e}) · "
                        f"Proyecto: {_pname_p} · Precio oferta: €{float(_precio_p or 0):,.0f} · "
                        f"Comisión pendiente: **€{_com_p:,.0f}**"
                    )
        except Exception as _eit:
            st.error(f"Error cargando tablón/comisiones: {_eit}")

    elif _admin_seccion == "⚙️ Admin":
        st.header("⚙️ Herramientas de Administración")
        st.warning("Estas acciones afectan a datos reales. Úsalas solo si sabes lo que haces.")

        st.subheader("🔄 Resincronización Total")
        st.write("Elimina todas las reservas bloqueadas, resetea fincas a 'disponible' y limpia la caché de Streamlit.")
        if st.button("🚨 FORZAR RESINCRONIZACIÓN TOTAL", type="primary"):
            try:
                import sqlite3
                from modules.marketplace.utils import DB_PATH
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()
                cur.execute("DELETE FROM reservations")
                cur.execute("UPDATE plots SET status = 'disponible'")
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("✅ Resincronización completada. Todas las fincas disponibles y caché limpia.")
                st.rerun()
            except Exception as e:
                st.error(f"Error en resincronización: {e}")

        st.markdown("---")
        st.subheader("🧹 Limpiar Clientes de Prueba")
        st.write("Elimina **todas las reservas** y **todos los usuarios cliente** (role='client'). Las fincas y el resto de datos NO se tocan.")
        st.error("⚠️ IRREVERSIBLE — solo para pruebas. No ejecutar en producción real.")
        _confirm_clean = st.checkbox("Confirmo que quiero borrar todos los clientes y reservas de prueba", key="confirm_clean_clients")
        if _confirm_clean:
            if st.button("🗑️ LIMPIAR CLIENTES Y RESERVAS DE PRUEBA", type="primary", key="btn_clean_clients"):
                try:
                    from modules.marketplace.utils import db_conn as _db_conn_clean
                    _cc = _db_conn_clean()
                    # Contar antes
                    _n_res = _cc.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
                    _n_cli = _cc.execute("SELECT COUNT(*) FROM users WHERE role='client'").fetchone()[0]
                    # Borrar
                    _cc.execute("DELETE FROM reservations")
                    _cc.execute("DELETE FROM users WHERE role='client'")
                    _cc.commit()
                    _cc.close()
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success(f"✅ Limpieza completada: {_n_res} reservas y {_n_cli} clientes borrados.")
                    st.rerun()
                except Exception as _e:
                    st.error(f"Error en limpieza: {_e}")

        st.markdown("---")
        st.info("🏠 **Gestión del Catálogo de Prefabricadas** → Usa la pestaña **🏠 Prefabricadas** del menú principal.")

    elif _admin_seccion == "🎯 Waitlist":
        st.header("Lista de Espera (Waitlist)")
        try:
            import sqlite3 as _sq3w, pandas as _pdw
            _cw = db_conn()
            _cur_wl = _cw.execute("SELECT name, email, profile, created_at, approved FROM waitlist ORDER BY created_at DESC")
            _rows_wl = _cur_wl.fetchall()
            _cols_wl = [d[0] for d in (_cur_wl.description or [])]
            _data_wl = []
            for _r_wl in _rows_wl:
                try:
                    _data_wl.append([_r_wl[i] for i in range(len(_cols_wl))])
                except Exception:
                    _data_wl.append([_r_wl[c] for c in _cols_wl])
            _dfw = _pdw.DataFrame(_data_wl, columns=_cols_wl)
            _cw.close()
            _total = len(_dfw)
            _approved = int(_dfw['approved'].sum()) if _total > 0 else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Total solicitudes", _total)
            c2.metric("Aprobados", _approved)
            c3.metric("Pendientes", _total - _approved)
            st.markdown("---")
            if _total > 0:
                # Pendientes — con botones de acción
                _cw2 = db_conn()
                _cur_wl2 = _cw2.execute("SELECT id, name, email, profile, created_at, approved FROM waitlist ORDER BY approved ASC, created_at DESC")
                _rows_wl2 = _cur_wl2.fetchall()
                _cols_wl2 = [d[0] for d in (_cur_wl2.description or [])]
                _data_wl2 = []
                for _r2 in _rows_wl2:
                    try:
                        _data_wl2.append([_r2[i] for i in range(len(_cols_wl2))])
                    except Exception:
                        _data_wl2.append([_r2[c] for c in _cols_wl2])
                _cw2.close()
                for _wrow in _data_wl2:
                    _wid, _wname, _wemail, _wprofile, _wdate, _wapproved = _wrow
                    _wstatus_col = "wl_status"
                    # Leer estado extendido si existe (tramite/suspendido)
                    _wext_status = st.session_state.get(f"wl_ext_{_wid}", None)
                    if _wapproved:
                        _badge = "✅ Aprobado"
                    elif _wext_status == "tramite":
                        _badge = "🟡 En trámite"
                    elif _wext_status == "suspendido":
                        _badge = "🔴 Suspendido"
                    else:
                        _badge = "⏳ Pendiente"
                    with st.expander(f"{_badge} · {_wname} ({_wemail})"):
                        st.markdown(f"**Perfil:** {_wprofile or '—'}  \n**Fecha:** {_wdate}")
                        _wa1, _wa2, _wa3, _wa4 = st.columns(4)
                        with _wa1:
                            if st.button("✅ Aprobar 🟢", key=f"wl_apr_{_wid}",
                                         type="primary" if _wapproved else "secondary",
                                         use_container_width=True):
                                _cwa = db_conn()
                                try:
                                    _cwa.execute("UPDATE waitlist SET approved=1 WHERE id=?", (_wid,))
                                    _cwa.commit()
                                finally:
                                    _cwa.close()
                                st.session_state.pop(f"wl_ext_{_wid}", None)
                                st.success(f"✅ {_wname} aprobado.")
                                st.rerun()
                        with _wa2:
                            if st.button("⏳ Trámite 🟡", key=f"wl_tram_{_wid}",
                                         type="primary" if _wext_status == "tramite" else "secondary",
                                         use_container_width=True):
                                _cwt = db_conn()
                                try:
                                    _cwt.execute("UPDATE waitlist SET approved=0 WHERE id=?", (_wid,))
                                    _cwt.commit()
                                finally:
                                    _cwt.close()
                                st.session_state[f"wl_ext_{_wid}"] = "tramite"
                                st.rerun()
                        with _wa3:
                            if st.button("🔴 Suspender", key=f"wl_sus_{_wid}",
                                         type="primary" if _wext_status == "suspendido" else "secondary",
                                         use_container_width=True):
                                _cws = db_conn()
                                try:
                                    _cws.execute("UPDATE waitlist SET approved=0 WHERE id=?", (_wid,))
                                    _cws.commit()
                                finally:
                                    _cws.close()
                                st.session_state[f"wl_ext_{_wid}"] = "suspendido"
                                st.rerun()
                        with _wa4:
                            with st.popover("🗑️ Eliminar", use_container_width=True):
                                st.error(f"⚠️ ¿Eliminar a {_wname}?")
                                st.caption("Irreversible.")
                                if st.button("❌ Sí, eliminar", key=f"wl_del_yes_{_wid}",
                                             type="primary", use_container_width=True):
                                    _cwd = db_conn()
                                    try:
                                        _cwd.execute("DELETE FROM waitlist WHERE id=?", (_wid,))
                                        _cwd.commit()
                                    finally:
                                        _cwd.close()
                                    st.rerun()
                st.markdown("---")
                # Exportar CSV
                _csv = _dfw.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Descargar CSV",
                    data=_csv,
                    file_name="waitlist_archirapid.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Aun no hay solicitudes en la lista de espera.")
        except Exception as _ew:
            import traceback as _tb7
            st.error(f"Error cargando waitlist: {_ew}")
            st.code(_tb7.format_exc())

    elif _admin_seccion == "📬 Actividad":
        st.header("📬 Actividad Reciente")

        # Estado configuración Telegram
        try:
            from modules.marketplace.email_notify import _get_telegram_creds
            _tok, _cid = _get_telegram_creds()
            if _tok and _cid:
                st.success("✅ Telegram configurado — notificaciones activas (@archirapid_mvp_bot)")
            else:
                st.warning("⚠️ **Notificaciones Telegram inactivas** — añade las credenciales en Streamlit Cloud Secrets.")
                with st.expander("¿Cómo configurar?"):
                    st.markdown("""
En Streamlit Cloud → Settings → Secrets, añade:
```
TELEGRAM_BOT_TOKEN = "tu_token_del_bot"
TELEGRAM_CHAT_ID   = "tu_chat_id"
```
Obtén el token creando un bot con @BotFather en Telegram.
""")
        except Exception:
            pass

        st.markdown("---")
        import sqlite3 as _sq3a
        import pandas as _pda

        _ca = db_conn()

        def _read_tab8(conn, sql):
            cur = conn.execute(sql)
            rows = cur.fetchall()
            if not rows:
                return _pda.DataFrame()
            cols = [d[0] for d in (cur.description or [])]
            data = []
            for r in rows:
                try:
                    data.append([r[i] for i in range(len(cols))])
                except Exception:
                    data.append([r[c] for c in cols])
            return _pda.DataFrame(data, columns=cols)

        # Últimos registros
        st.subheader("👤 Últimos registros de usuarios")
        try:
            _df_users = _read_tab8(
                _ca,
                "SELECT name, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 20"
            )
            if not _df_users.empty:
                _df_users["✉️"] = _df_users["email"].apply(
                    lambda e: f"[Escribir](mailto:{e})"
                )
                st.dataframe(
                    _df_users.rename(columns={"name": "Nombre", "email": "Email", "role": "Rol", "created_at": "Fecha"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin registros todavía.")
        except Exception as _eu:
            st.error(f"Error: {_eu}")

        st.markdown("---")

        # Últimas reservas/compras
        st.subheader("💰 Últimas reservas y compras de fincas")
        try:
            _df_res = _read_tab8(
                _ca,
                """SELECT r.buyer_name, r.buyer_email, p.title as finca, r.amount, r.kind, r.created_at
                   FROM reservations r LEFT JOIN plots p ON r.plot_id=p.id
                   ORDER BY r.created_at DESC LIMIT 20"""
            )
            if not _df_res.empty:
                _df_res["kind"] = _df_res["kind"].map({"purchase": "Compra", "reservation": "Reserva"}).fillna(_df_res["kind"])
                st.dataframe(
                    _df_res.rename(columns={
                        "buyer_name": "Comprador", "buyer_email": "Email",
                        "finca": "Finca", "amount": "Importe (€)",
                        "kind": "Tipo", "created_at": "Fecha"
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin transacciones todavía.")
        except Exception as _er:
            st.error(f"Error: {_er}")

        st.markdown("---")

        # Waitlist reciente
        st.subheader("🎯 Waitlist reciente")
        try:
            _df_wl = _read_tab8(
                _ca,
                "SELECT name, email, profile, created_at FROM waitlist ORDER BY created_at DESC LIMIT 10"
            )
            if not _df_wl.empty:
                st.dataframe(
                    _df_wl.rename(columns={"name": "Nombre", "email": "Email", "profile": "Perfil", "created_at": "Fecha"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Sin solicitudes todavía.")
        except Exception as _ew2:
            st.error(f"Error: {_ew2}")

        _ca.close()

    # ── ANALYTICS ─────────────────────────────────────────────────────────────
    elif _admin_seccion == "📊 Analytics":
        st.header("📊 Dashboard de Analytics — ArchiRapid")
        import sqlite3 as _sq9
        import pandas as _pd9
        import datetime as _dt9

        def _read_sql9(conn, sql):
            """pd.read_sql_query compatible con SQLite y psycopg2 wrapper."""
            try:
                cur = conn.execute(sql)
                rows = cur.fetchall()
                if not rows:
                    return _pd9.DataFrame()
                cols = [d[0].title() if d[0].islower() else d[0] for d in (cur.description or [])]
                data = []
                for r in rows:
                    try:
                        data.append([r[i] for i in range(len(cols))])
                    except Exception:
                        data.append([r[c] for c in cols])
                return _pd9.DataFrame(data, columns=cols)
            except Exception as _re:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise _re

        try:
            _db9 = db_conn()

            # ══ 🚨 ALERTAS Y PENDIENTES ══════════════════════════════════════
            st.subheader("🚨 Alertas y pendientes — Acción requerida")
            _alerts_list = []
            try:
                _n_inmo_pend = _db9.execute(
                    "SELECT COUNT(*) FROM inmobiliarias WHERE activa=0"
                ).fetchone()[0]
                if _n_inmo_pend > 0:
                    _alerts_list.append(f"🏢 **{_n_inmo_pend} inmobiliaria(s)** pendiente(s) de aprobación → pestaña MLS")
            except Exception:
                pass
            try:
                _n_finca_pend = _db9.execute(
                    "SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'"
                ).fetchone()[0]
                if _n_finca_pend > 0:
                    _alerts_list.append(f"🏠 **{_n_finca_pend} finca(s) MLS** pendiente(s) de publicación → pestaña MLS")
            except Exception:
                pass
            try:
                _n_colab_pend = _db9.execute(
                    "SELECT COUNT(*) FROM notificaciones_mls WHERE tipo_evento='solicitud_colaboracion_72h' AND destinatario_id='admin' AND leida=0"
                ).fetchone()[0]
                if _n_colab_pend > 0:
                    _alerts_list.append(f"🤝 **{_n_colab_pend} solicitud(es) de colaboración 72h** sin gestionar → pestaña MLS")
            except Exception:
                pass
            try:
                _n_res_48h = _db9.execute(
                    "SELECT COUNT(*) FROM reservas_mls WHERE estado='pendiente_confirmacion_48h'"
                ).fetchone()[0]
                if _n_res_48h > 0:
                    _alerts_list.append(f"⏰ **{_n_res_48h} reserva(s)** cliente pendientes confirmación 48h → pestaña MLS")
            except Exception:
                pass
            try:
                _n_waitlist_pend = _db9.execute(
                    "SELECT COUNT(*) FROM waitlist WHERE approved=0"
                ).fetchone()[0]
                if _n_waitlist_pend > 0:
                    _alerts_list.append(f"🎯 **{_n_waitlist_pend} persona(s)** en waitlist sin aprobar → pestaña Waitlist")
            except Exception:
                pass

            if _alerts_list:
                for _al in _alerts_list:
                    st.warning(_al)
            else:
                st.success("✅ Sin alertas activas. Todo al día.")

            st.markdown("---")

            # ── KPIs principales ──────────────────────────────────────────────
            st.subheader("Métricas globales")

            _n_users    = _db9.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            _n_plots    = _db9.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
            _n_avail    = _db9.execute("SELECT COUNT(*) FROM plots WHERE status='disponible'").fetchone()[0]
            _n_projects = _db9.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            _n_res      = _db9.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            _n_purchase = _db9.execute("SELECT COUNT(*) FROM reservations WHERE kind='purchase'").fetchone()[0]
            _rev_row    = _db9.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()
            _revenue    = float(_rev_row[0]) if _rev_row else 0.0
            _n_waitlist = _db9.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0]
            _n_approved = _db9.execute("SELECT COUNT(*) FROM waitlist WHERE approved=1").fetchone()[0]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("👤 Usuarios registrados", _n_users)
            k2.metric("🗺️ Fincas publicadas", _n_plots, delta=f"{_n_avail} disponibles")
            k3.metric("🏗️ Proyectos activos", _n_projects)
            k4.metric("💶 Ingresos acumulados", f"€{_revenue:,.0f}", delta=f"{_n_res} transacciones")

            _n_alerts = 0
            try:
                _n_alerts = _db9.execute("SELECT COUNT(*) FROM plot_alerts WHERE active=1").fetchone()[0]
            except Exception:
                pass

            k5, k6, k7, k8 = st.columns(4)
            k5.metric("🛒 Reservas totales", _n_res)
            k6.metric("✅ Compras efectivas", _n_purchase)
            k7.metric("🎯 Waitlist total", _n_waitlist, delta=f"{_n_approved} aprobados")
            k8.metric("📐 Conversión reserva→compra",
                      f"{(_n_purchase/_n_res*100):.1f}%" if _n_res else "—")

            _n_subs9, _mrr9, _n_estudio9 = 0, 0.0, 0
            try:
                _sr9 = _db9.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM subscriptions WHERE status='active'").fetchone()
                _n_subs9, _mrr9 = int(_sr9[0]), float(_sr9[1])
            except Exception:
                pass
            try:
                _n_estudio9 = _db9.execute("SELECT COUNT(*) FROM estudio_projects").fetchone()[0]
            except Exception:
                pass

            k9, k10, k11, k12 = st.columns(4)
            k9.metric("🔔 Alertas activas", _n_alerts)
            k10.metric("💎 Suscripciones activas", _n_subs9, delta=f"MRR €{_mrr9:,.0f}")
            k11.metric("🎨 Proyectos Modo Estudio", _n_estudio9)
            _n_ai9 = 0
            try:
                _n_ai9 = _db9.execute("SELECT COUNT(*) FROM ai_projects").fetchone()[0]
            except Exception:
                pass
            k12.metric("🏠 Proyectos AI pagados", _n_ai9)

            st.markdown("---")

            # ── 💳 Stripe Revenue Dashboard ───────────────────────────────────
            st.subheader("💳 Stripe — Revenue en tiempo real (modo test)")
            try:
                from modules.stripe_utils import list_recent_sessions as _lrs
                import pandas as _pd_stripe
                _stripe_sessions = _lrs(limit=50)
                _stripe_rows = []
                _stripe_data = getattr(_stripe_sessions, "data", None) or list(_stripe_sessions)
                for _ss in _stripe_data:
                    if getattr(_ss, "payment_status", None) == "paid":
                        try:
                            _meta = dict(getattr(_ss, "metadata", None) or {})
                        except Exception:
                            _meta = {}
                        _stripe_rows.append({
                            "Fecha": _pd_stripe.to_datetime(getattr(_ss, "created", 0), unit="s").strftime("%d/%m/%Y %H:%M"),
                            "Email": getattr(_ss, "customer_email", None) or _meta.get("client_email", "—"),
                            "Productos": _meta.get("products", "—"),
                            "Proyecto ID": _meta.get("project_id", "—"),
                            "Importe (€)": (getattr(_ss, "amount_total", 0) or 0) / 100,
                            "Estado": "✅ Pagado",
                        })
                if _stripe_rows:
                    _df_stripe = _pd_stripe.DataFrame(_stripe_rows)
                    _total_stripe = _df_stripe["Importe (€)"].sum()
                    _sc1, _sc2, _sc3 = st.columns(3)
                    _sc1.metric("💶 Revenue Stripe (test)", f"€{_total_stripe:,.0f}")
                    _sc2.metric("🧾 Pagos completados", len(_stripe_rows))
                    _sc3.metric("📊 Ticket medio", f"€{_total_stripe/len(_stripe_rows):,.0f}" if _stripe_rows else "—")
                    st.dataframe(_df_stripe, use_container_width=True, hide_index=True)
                else:
                    st.info("Aún no hay pagos completados en Stripe (modo test). Realiza una compra de prueba con la tarjeta 4242 4242 4242 4242.")
            except Exception as _stripe_err:
                st.warning(f"Stripe error: {type(_stripe_err).__name__}: {_stripe_err}")

            st.markdown("---")

            # ── Funnel de conversión ──────────────────────────────────────────
            st.subheader("🔽 Funnel de conversión")
            _funnel_data = {
                "Etapa": ["Fincas publicadas", "Usuarios registrados", "Reservas realizadas", "Compras efectivas", "Waitlist aprobados"],
                "Total": [_n_plots, _n_users, _n_res, _n_purchase, _n_approved]
            }
            _df_funnel = _pd9.DataFrame(_funnel_data).set_index("Etapa")
            st.bar_chart(_df_funnel)

            st.markdown("---")

            # ── Usuarios por rol ──────────────────────────────────────────────
            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("👥 Usuarios por rol")
                try:
                    _df_roles = _read_sql9(
                        _db9,
                        "SELECT role as Rol, COUNT(*) as Total FROM users GROUP BY role ORDER BY Total DESC"
                    )
                    if not _df_roles.empty:
                        st.dataframe(_df_roles, use_container_width=True, hide_index=True)
                        st.bar_chart(_df_roles.set_index("Rol"))
                    else:
                        st.info("Sin datos de roles todavía.")
                except Exception as _er:
                    st.warning(f"Roles: {_er}")

            with col_b:
                st.subheader("🗺️ Fincas por provincia")
                try:
                    _df_prov = _read_sql9(
                        _db9,
                        "SELECT province as Provincia, COUNT(*) as Fincas FROM plots GROUP BY province ORDER BY Fincas DESC"
                    )
                    if not _df_prov.empty:
                        st.dataframe(_df_prov, use_container_width=True, hide_index=True)
                        st.bar_chart(_df_prov.set_index("Provincia"))
                    else:
                        st.info("Sin datos de provincias todavía.")
                except Exception as _ep:
                    st.warning(f"Provincias: {_ep}")

            st.markdown("---")

            # ── Ingresos por tipo de operación ────────────────────────────────
            st.subheader("💰 Ingresos por tipo de operación")
            try:
                _df_kind = _read_sql9(
                    _db9,
                    "SELECT kind as Tipo, COUNT(*) as Operaciones, COALESCE(SUM(amount),0) as Importe FROM reservations GROUP BY kind"
                )
                if not _df_kind.empty:
                    _df_kind["Tipo"] = _df_kind["Tipo"].map(
                        {"purchase": "Compra", "reservation": "Reserva", "pdf": "Docs PDF",
                         "cad": "Docs CAD", "full": "Paquete completo"}
                    ).fillna(_df_kind["Tipo"])
                    st.dataframe(_df_kind, use_container_width=True, hide_index=True)
                    st.bar_chart(_df_kind.set_index("Tipo")["Importe"])
                else:
                    st.info("Sin transacciones todavía.")
            except Exception as _ek:
                st.warning(f"Tipos: {_ek}")

            st.markdown("---")

            # ── Actividad diaria (últimos 30 días) ────────────────────────────
            st.subheader("📅 Registros de usuarios — últimos 30 días")
            try:
                _df_daily = _read_sql9(
                    _db9,
                    """SELECT DATE(created_at) as Fecha, COUNT(*) as Registros
                       FROM users
                       WHERE DATE(created_at) >= DATE('now', '-30 days')
                       GROUP BY DATE(created_at)
                       ORDER BY Fecha"""
                )
                if not _df_daily.empty:
                    st.line_chart(_df_daily.set_index("Fecha"))
                else:
                    st.info("Sin registros en los últimos 30 días.")
            except Exception as _ed:
                st.warning(f"Actividad diaria: {_ed}")

            st.markdown("---")

            # ── Top fincas por precio ─────────────────────────────────────────
            st.subheader("🏆 Top 10 fincas por precio")
            try:
                _df_top = _read_sql9(
                    _db9,
                    "SELECT title as Finca, province as Provincia, m2 as Superficie_m2, price as Precio_EUR, status as Estado FROM plots ORDER BY price DESC LIMIT 10"
                )
                if not _df_top.empty:
                    st.dataframe(_df_top, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin fincas en el catálogo.")
            except Exception as _et:
                st.warning(f"Top fincas: {_et}")

            # ── TRACKING DEEP LINKS Y DEMOS ────────────────────────────────
            st.markdown("---")
            st.subheader("🔗 Tracking de Deep Links y Demos")
            try:
                from datetime import datetime as _dtnow, timedelta as _td
                import pandas as _pd_trk

                # Filtro de periodo
                _periodo_opts = {"Hoy": 1, "Últimos 7 días": 7, "Último mes": 30, "Últimos 3 meses": 90, "Todo el histórico": 99999, "Personalizado": 0}
                _periodo_sel = st.selectbox("Periodo", list(_periodo_opts.keys()), index=1, key="trk_periodo")
                if _periodo_sel == "Personalizado":
                    _pc1, _pc2 = st.columns(2)
                    _fecha_desde = _pc1.date_input("Desde", value=_dtnow.utcnow().date() - _td(days=30), key="trk_desde")
                    _fecha_hasta = _pc2.date_input("Hasta", value=_dtnow.utcnow().date(), key="trk_hasta")
                    _desde_iso = _fecha_desde.isoformat()
                    _hasta_iso = (_fecha_hasta + _td(days=1)).isoformat()
                else:
                    _dias = _periodo_opts[_periodo_sel]
                    _desde_iso = (_dtnow.utcnow() - _td(days=_dias)).isoformat() if _dias < 99999 else "2000-01-01"
                    _hasta_iso = "2099-12-31"

                _df_vis = _read_sql9(
                    _db9,
                    f"""SELECT origen as Origen,
                              COUNT(*) as Visitas,
                              SUM(convirtio_a_registro) as Registros,
                              ROUND(SUM(convirtio_a_registro)*100.0/COUNT(*),1) as ConvPct
                       FROM visitas_demo
                       WHERE timestamp >= '{_desde_iso}' AND timestamp < '{_hasta_iso}'
                       GROUP BY origen ORDER BY Visitas DESC"""
                )
                if not _df_vis.empty:
                    _kv1, _kv2, _kv3 = st.columns(3)
                    _total_vis = int(_df_vis["Visitas"].sum())
                    _total_reg = int(_df_vis["Registros"].sum())
                    _conv_global = round(_total_reg * 100.0 / _total_vis, 1) if _total_vis > 0 else 0
                    _kv1.metric("Total visitas demo", _total_vis)
                    _kv2.metric("Registros generados", _total_reg)
                    _kv3.metric("Conversión global", f"{_conv_global}%")
                    st.dataframe(_df_vis, use_container_width=True, hide_index=True)

                    # Gráfica visitas por día
                    _df_dia = _read_sql9(
                        _db9,
                        f"""SELECT SUBSTR(timestamp,1,10) as Dia, COUNT(*) as Visitas
                            FROM visitas_demo
                            WHERE timestamp >= '{_desde_iso}' AND timestamp < '{_hasta_iso}'
                            GROUP BY Dia ORDER BY Dia ASC"""
                    )
                    if not _df_dia.empty and len(_df_dia) > 1:
                        st.caption("Evolución de visitas por día:")
                        st.bar_chart(_df_dia.set_index("Dia")["Visitas"])

                    # Detalle histórico completo con scroll
                    with st.expander(f"📋 Detalle de visitas ({_total_vis} registros)", expanded=False):
                        _df_det = _read_sql9(
                            _db9,
                            f"""SELECT timestamp as Fecha, origen as Origen, nombre_usuario as Usuario,
                                      accion_realizada as Accion,
                                      CASE convirtio_a_registro WHEN 1 THEN 'Si' ELSE 'No' END as Registro
                               FROM visitas_demo
                               WHERE timestamp >= '{_desde_iso}' AND timestamp < '{_hasta_iso}'
                               ORDER BY timestamp DESC"""
                        )
                        st.dataframe(_df_det, use_container_width=True, hide_index=True, height=400)
                else:
                    st.info("Sin visitas registradas en este periodo. Comparte el enlace demo para empezar a trackear.")
                    st.code("https://archirapid.streamlit.app/?seccion=arquitecto&demo=true&from=linkedin&user=nombre")
            except Exception as _ev:
                st.error(f"Error tracking: {_ev}")

            # ── MLS Analytics ─────────────────────────────────────────────────
            st.markdown("---")
            st.subheader("🏢 MLS — Estadísticas consolidadas")
            _mls_a_conn = db_conn()
            try:

                # KPIs MLS en una fila
                _mls_total_inmos   = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias").fetchone()[0]
                _mls_act_inmos     = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=1").fetchone()[0]
                _mls_pend_inmos    = _mls_a_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=0").fetchone()[0]
                _mls_fincas_pub    = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='publicada'").fetchone()[0]
                _mls_fincas_res    = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='reservada'").fetchone()[0]
                _mls_fincas_pend   = _mls_a_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'").fetchone()[0]
                _mls_reservas_act  = _mls_a_conn.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='activa'").fetchone()[0]

                _ma1, _ma2, _ma3, _ma4 = st.columns(4)
                _ma1.metric("🏢 Inmos totales", _mls_total_inmos,
                            delta=f"{_mls_act_inmos} activas / {_mls_pend_inmos} pend.")
                _ma2.metric("🏠 Fincas publicadas", _mls_fincas_pub)
                _ma3.metric("🔒 Fincas reservadas", _mls_fincas_res)
                _ma4.metric("📋 Reservas activas", _mls_reservas_act)

                _col_mls1, _col_mls2 = st.columns(2)

                with _col_mls1:
                    # Fincas MLS por estado
                    try:
                        _df_mls_estado = _read_sql9(
                            _mls_a_conn,
                            "SELECT estado as Estado, COUNT(*) as Total FROM fincas_mls GROUP BY estado ORDER BY Total DESC"
                        )
                        if not _df_mls_estado.empty:
                            st.caption("Fincas MLS por estado")
                            st.bar_chart(_df_mls_estado.set_index("Estado"))
                    except Exception as _em1:
                        st.warning(f"Fincas MLS estado: {_em1}")

                with _col_mls2:
                    # Inmos por provincia
                    try:
                        _df_mls_prov = _read_sql9(
                            _mls_a_conn,
                            "SELECT provincia as Provincia, COUNT(*) as Inmos FROM inmobiliarias GROUP BY provincia ORDER BY Inmos DESC LIMIT 10"
                        )
                        if not _df_mls_prov.empty:
                            st.caption("Inmos MLS por provincia (top 10)")
                            st.bar_chart(_df_mls_prov.set_index("Provincia"))
                    except Exception as _em2:
                        st.warning(f"Inmos provincia: {_em2}")

                # Actividad MLS últimos 30 días (registros de inmos + fincas subidas)
                try:
                    _df_mls_act = _read_sql9(
                        _mls_a_conn,
                        """
                        SELECT DATE(created_at) as Fecha, 'Inmobiliarias' as Tipo, COUNT(*) as N
                        FROM inmobiliarias
                        WHERE created_at >= DATE('now', '-30 days')
                        GROUP BY DATE(created_at)
                        UNION ALL
                        SELECT DATE(created_at) as Fecha, 'Fincas MLS' as Tipo, COUNT(*) as N
                        FROM fincas_mls
                        WHERE created_at >= DATE('now', '-30 days')
                        GROUP BY DATE(created_at)
                        ORDER BY Fecha
                        """
                    )
                    if not _df_mls_act.empty:
                        _df_mls_pivot = _df_mls_act.pivot_table(
                            index="Fecha", columns="Tipo", values="N", aggfunc="sum"
                        ).fillna(0)
                        st.caption("Actividad MLS — últimos 30 días")
                        st.bar_chart(_df_mls_pivot)
                except Exception as _em3:
                    pass  # tabla puede estar vacía — no mostrar error

                # Notificaciones MLS pendientes por tipo
                try:
                    _df_notifs = _read_sql9(
                        _mls_a_conn,
                        """SELECT tipo_evento as Tipo, COUNT(*) as Total
                           FROM notificaciones_mls
                           WHERE leida=0
                           GROUP BY tipo_evento ORDER BY Total DESC"""
                    )
                    if not _df_notifs.empty:
                        st.caption("Notificaciones MLS sin leer por tipo")
                        st.dataframe(_df_notifs, use_container_width=True, hide_index=True)
                except Exception:
                    pass

                # ── Leads MLS (solicitudes demo/contacto desde la home) ──────
                st.markdown("---")
                st.subheader("📋 Leads MLS — Solicitudes de demo")
                try:
                    _leads_conn = db_conn()
                    _df_leads = _read_sql9(
                        _leads_conn,
                        """SELECT id, nombre as Nombre, empresa as Empresa, email as Email,
                                  telefono as Telefono, num_fincas as Fincas,
                                  mensaje as Mensaje, origen as Origen,
                                  estado as Estado, created_at as Fecha
                           FROM leads_mls
                           ORDER BY id DESC
                           LIMIT 100"""
                    )
                    _leads_conn.close()
                    if not _df_leads.empty:
                        _ltotal = len(_df_leads)
                        _lnuevos = len(_df_leads[_df_leads["Estado"] == "nuevo"]) if "Estado" in _df_leads.columns else 0
                        _ll1, _ll2 = st.columns(2)
                        _ll1.metric("Total leads MLS", _ltotal)
                        _ll2.metric("Sin contactar", _lnuevos)
                        st.caption("URL demo para compartir:")
                        st.code("https://archirapid.streamlit.app/?seccion=mls&demo=true&from=linkedin")
                        st.dataframe(_df_leads, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sin leads MLS todavía. Comparte la URL demo para empezar a recibir solicitudes.")
                        st.code("https://archirapid.streamlit.app/?seccion=mls&demo=true&from=linkedin")
                except Exception as _el:
                    st.warning(f"Error leads MLS: {_el}")

            except Exception as _emls:
                st.warning(f"Error estadísticas MLS: {_emls}")
            finally:
                _mls_a_conn.close()

            _db9.close()

        except Exception as _e9:
            st.error(f"Error en Analytics: {_e9}")

    # ── MLS — INMOBILIARIAS ───────────────────────────────────────────────────
    elif _admin_seccion == "🏢 MLS — Inmobiliarias":
        st.header("🏢 ArchiRapid MLS — Panel de Administración")

        # Imports locales — sin afectar el resto de la Intranet
        try:
            from modules.mls import mls_db as _mls
            from modules.mls import mls_notificaciones as _mls_notif
        except Exception as _imp_err:
            st.error(f"No se pudo cargar el módulo MLS: {_imp_err}")
            return

        def _mask_iban(iban: str) -> str:
            """Muestra solo los últimos 4 dígitos del IBAN en listados."""
            if not iban or len(iban) < 4:
                return iban or "—"
            return "****…****" + iban[-4:]

        # ══ SECCIÓN F: KPIs MLS ══════════════════════════════════════════════
        st.subheader("📊 KPIs MLS")
        try:
            _mls_conn = db_conn()
            _n_inmo_total  = _mls_conn.execute("SELECT COUNT(*) FROM inmobiliarias").fetchone()[0]
            _n_inmo_act    = _mls_conn.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=1").fetchone()[0]
            _n_fincas_pub  = _mls_conn.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='publicada'").fetchone()[0]
            _n_reservas_a  = _mls_conn.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='activa'").fetchone()[0]
            _mls_conn.close()

            _mls_conn2 = db_conn()
            _n_pend_inmo   = _mls_conn2.execute("SELECT COUNT(*) FROM inmobiliarias WHERE activa=0").fetchone()[0]
            _n_pend_finca  = _mls_conn2.execute("SELECT COUNT(*) FROM fincas_mls WHERE estado='validada_pendiente_aprobacion'").fetchone()[0]
            _n_res_cli     = _mls_conn2.execute("SELECT COUNT(*) FROM reservas_mls WHERE estado='pendiente_confirmacion_48h'").fetchone()[0]
            # Ingresos estimados: sum de pagos Stripe con mls en productos
            _ingresos_mls  = 0.0
            try:
                from modules.stripe_utils import list_recent_sessions as _lrs_mls
                _sess_mls = _lrs_mls(limit=100)
                import datetime as _dt_mls
                _this_month = _dt_mls.datetime.now().replace(day=1, hour=0, minute=0, second=0)
                _sess_mls_data = getattr(_sess_mls, "data", None) or list(_sess_mls)
                for _sm in _sess_mls_data:
                    if getattr(_sm, "payment_status", None) == "paid":
                        try:
                            _meta_m = dict(getattr(_sm, "metadata", None) or {})
                        except Exception:
                            _meta_m = {}
                        _prods = _meta_m.get("products", "")
                        if "mls" in _prods.lower():
                            _ts = _dt_mls.datetime.fromtimestamp(getattr(_sm, "created", 0))
                            if _ts >= _this_month:
                                _ingresos_mls += (getattr(_sm, "amount_total", 0) or 0) / 100
            except Exception:
                pass
            _mls_conn2.close()

            _fk1, _fk2, _fk3, _fk4 = st.columns(4)
            _fk1.metric("🏢 Inmos registradas", _n_inmo_total)
            _fk2.metric("✅ Inmos activas", _n_inmo_act)
            _fk3.metric("🏠 Fincas publicadas", _n_fincas_pub)
            _fk4.metric("🔒 Reservas activas", _n_reservas_a)

            _fk5, _fk6, _fk7, _fk8 = st.columns(4)
            _fk5.metric("⏳ Pendientes aprobación", _n_pend_inmo,
                        delta="⚠️ Acción requerida" if _n_pend_inmo > 0 else None,
                        delta_color="inverse")
            _fk6.metric("📋 Fincas pend. aprobación", _n_pend_finca,
                        delta="⚠️ Acción requerida" if _n_pend_finca > 0 else None,
                        delta_color="inverse")
            _fk7.metric("⏰ Reservas cliente 48h", _n_res_cli)
            _fk8.metric("💶 Ingresos MLS (este mes)", f"€{_ingresos_mls:,.0f}")
        except Exception as _ef:
            st.warning(f"Error KPIs MLS: {_ef}")

        st.markdown("---")

        # ══ SECCIÓN A: Inmobiliarias pendientes de aprobación ════════════════
        st.subheader("⏳ A. Inmobiliarias pendientes de aprobación")
        try:
            _pendientes = _mls.get_inmos_pendientes()
            if not _pendientes:
                st.success("✅ Sin registros pendientes de aprobación.")
            else:
                st.warning(f"**{len(_pendientes)} inmobiliaria(s) esperando aprobación.**")
                for _p in _pendientes:
                    _pnombre = _p.get("nombre_comercial") or _p.get("nombre", "Sin nombre")
                    with st.expander(f"📋 {_pnombre} — {_p.get('cif','?')} | {_p.get('email','?')} | {(_p.get('created_at',''))[:10]}"):
                        _ca, _cb = st.columns([3, 1])
                        with _ca:
                            st.markdown("**📊 Datos de empresa**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre legal | {_p.get('nombre_sociedad') or '—'} |
| Nombre comercial | {_p.get('nombre_comercial') or '—'} |
| CIF | `{_p.get('cif','—')}` |
| Email corporativo | {_p.get('email','—')} |
| Email login | {_p.get('email_login') or '—'} |
| Teléfono principal | {_p.get('telefono') or '—'} |
| Teléfono secundario | {_p.get('telefono_secundario') or '—'} |
| Telegram | {_p.get('telegram_contacto') or '—'} |
| Web | {_p.get('web') or '—'} |
| IP registro | `{_p.get('ip_registro','—')}` |
| Fecha registro | {(_p.get('created_at',''))[:19]} |
""")
                            st.markdown("**📍 Dirección**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Dirección | {_p.get('direccion') or '—'} |
| Localidad | {_p.get('localidad') or '—'} |
| Provincia | {_p.get('provincia') or '—'} |
| CP | {_p.get('codigo_postal') or '—'} |
| País | {_p.get('pais') or '—'} |
""")
                            st.markdown("**👤 Persona de contacto**")
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre | {_p.get('contacto_nombre') or '—'} |
| Cargo | {_p.get('contacto_cargo') or '—'} |
| Email directo | {_p.get('contacto_email') or '—'} |
| Teléfono | {_p.get('contacto_telefono') or '—'} |
| Telegram | {_p.get('contacto_telegram') or '—'} |
""")
                            st.markdown("**🧾 Facturación**")
                            _iban_m = _mask_iban(_p.get('iban') or '')
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Razón social | {_p.get('factura_razon_social') or '—'} |
| CIF factura | {_p.get('factura_cif') or '—'} |
| Dirección fiscal | {_p.get('factura_direccion') or '—'} |
| Email facturas | {_p.get('factura_email') or '—'} |
| IBAN | `{_iban_m}` |
| Banco | {_p.get('banco_nombre') or '—'} |
| Titular | {_p.get('banco_titular') or '—'} |
""")
                        with _cb:
                            st.markdown("**Acciones**")
                            if st.button("✅ Aprobar", key=f"mls_apro_{_p['id']}", type="primary",
                                         use_container_width=True):
                                _mls.update_inmo_activa(_p["id"], 1)
                                # Activar trial 30 días automáticamente al aprobar
                                try:
                                    _mls.activate_trial(_p["id"])
                                except Exception:
                                    pass
                                try:
                                    _mls_notif.notif_aprobacion(
                                        nombre=_pnombre,
                                        email=_p.get("email", ""),
                                        aprobada=True,
                                    )
                                except Exception:
                                    pass
                                # Email bienvenida trial
                                try:
                                    from modules.mls.mls_trial_emails import send_trial_email
                                    send_trial_email(
                                        inmo_email=_p.get("email", ""),
                                        inmo_nombre=_pnombre,
                                        tipo="bienvenida",
                                    )
                                except Exception:
                                    pass
                                st.success(f"✅ {_pnombre} aprobada. Trial de 30 días activado.")
                                st.rerun()

                            st.markdown("")
                            with st.popover("❌ Rechazar y eliminar", use_container_width=True):
                                st.error(f"⚠️ ¿Eliminar {_pnombre}?")
                                st.caption("Esta acción no se puede deshacer.")
                                if st.button("❌ Sí, eliminar", key=f"mls_del_yes_{_p['id']}",
                                             type="primary", use_container_width=True):
                                    try:
                                        _dc = db_conn()
                                        _dc.execute("DELETE FROM inmobiliarias WHERE id=?", (_p["id"],))
                                        _dc.commit()
                                        _dc.close()
                                        _mls_notif.notif_aprobacion(
                                            nombre=_pnombre,
                                            email=_p.get("email", ""),
                                            aprobada=False,
                                        )
                                    except Exception:
                                        pass
                                    st.success("Inmobiliaria eliminada")
                                    st.rerun()
        except Exception as _ea:
            st.warning(f"Error sección A: {_ea}")

        st.markdown("---")

        # ══ SECCIÓN B: Inmobiliarias activas ═════════════════════════════════
        st.subheader("✅ B. Inmobiliarias activas")
        try:
            # Agregar columnas si no existen
            for _col, _def in [("status","TEXT DEFAULT 'aprobada'"),
                                ("is_active","INTEGER DEFAULT 1")]:
                try:
                    _mls_altb = db_conn()
                    _mls_altb.execute(f"ALTER TABLE inmobiliarias ADD COLUMN {_col} {_def}")
                    _mls_altb.commit()
                    _mls_altb.close()
                except Exception:
                    try:
                        _mls_altb.close()
                    except Exception:
                        pass

            # Inicializar status vacíos (solo si es NULL o ''), NO resetea estados ya asignados
            if not st.session_state.get("_init_inmos_status_done", False):
                try:
                    _mls_reset = db_conn()
                    try:
                        _mls_reset.execute("UPDATE inmobiliarias SET status='aprobada' WHERE (status IS NULL OR status='') AND firma_hash IS NOT NULL")
                        _mls_reset.execute("UPDATE inmobiliarias SET status='pendiente_firma' WHERE (status IS NULL OR status='') AND (firma_hash IS NULL OR firma_hash='')")
                        _mls_reset.commit()
                    finally:
                        _mls_reset.close()
                    st.session_state["_init_inmos_status_done"] = True
                except Exception:
                    pass

            # Consulta directa: mostrar TODAS (activas + suspendidas + en trámite)
            # get_inmos_activas() filtra activa=1 y pierde las suspendidas
            _inmo_all_conn = db_conn()
            try:
                _activas_raw = _inmo_all_conn.execute(
                    "SELECT * FROM inmobiliarias WHERE activa=1 OR (status IS NOT NULL AND status != '') ORDER BY created_at DESC"
                ).fetchall()
                _inmo_cols = [d[0] for d in _inmo_all_conn.execute("SELECT * FROM inmobiliarias LIMIT 0").description or []]
            finally:
                _inmo_all_conn.close()
            _activas = [dict(zip(_inmo_cols, r)) for r in _activas_raw] if _inmo_cols and _activas_raw else []

            if not _activas:
                st.info("No hay inmobiliarias activas todavía.")
            else:
                for _a in _activas:
                    if _a is None:
                        continue
                    _anombre = _a.get("nombre_comercial") or _a.get("nombre", "?")
                    _plan_a  = (_a.get("plan") or "ninguno").upper()
                    _tiene_firma = bool(_a.get("firma_hash"))
                    _firma_a = "✅ Firmado" if _tiene_firma else "🔴 Sin firma"
                    # Contar fincas activas
                    _n_fincas_a = 0
                    try:
                        _fc = db_conn()
                        _n_fincas_a = _fc.execute(
                            "SELECT COUNT(*) FROM fincas_mls WHERE inmo_id=? AND estado NOT IN ('eliminada','cerrada')",
                            (_a["id"],)
                        ).fetchone()[0]
                        _fc.close()
                    except Exception:
                        pass

                    # GET status actual
                    _imo_status = "aprobada"
                    try:
                        _fcs = db_conn()
                        _sts = _fcs.execute("SELECT status FROM inmobiliarias WHERE id=?", (_a["id"],)).fetchone()
                        if _sts:
                            _imo_status = _sts[0] or "aprobada"
                        _fcs.close()
                    except Exception:
                        pass

                    _inmo_icon = "🟢" if _tiene_firma else "🔴"
                    with st.expander(
                        f"{_inmo_icon} {_anombre} — Plan {_plan_a} | Firma: {_firma_a} | "
                        f"Fincas: {_n_fincas_a} | {_a.get('email','')}"
                    ):
                        _ba, _bb = st.columns([3, 1])
                        with _ba:
                            # Tabla resumida
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| Nombre comercial | {_anombre} |
| CIF | `{_a.get('cif','—')}` |
| Email | {_a.get('email','—')} |
| Plan | **{_plan_a}** |
| Plan activo | {'✅' if _a.get('plan_activo') else '❌'} |
| Firma acuerdo | {_firma_a} |
| Fecha firma | {((_a.get('firma_timestamp') or ''))[:10] or '—'} |
| Fincas activas | {_n_fincas_a} |
| Estado | {_imo_status} |
""")
                            # Detalle completo en sub-expander
                            with st.expander("📋 Ver detalle completo"):
                                _iban_full = _a.get("iban") or "—"
                                st.markdown(f"""
**Empresa**
- Nombre legal: {_a.get('nombre_sociedad') or '—'}
- Teléfono: {_a.get('telefono') or '—'} / {_a.get('telefono_secundario') or '—'}
- Web: {_a.get('web') or '—'}
- Dirección: {_a.get('direccion') or '—'}, {_a.get('localidad') or '—'}, {_a.get('provincia') or '—'} {_a.get('codigo_postal') or ''}, {_a.get('pais') or '—'}

**Contacto responsable**
- {_a.get('contacto_nombre') or '—'} ({_a.get('contacto_cargo') or 'sin cargo'})
- Email: {_a.get('contacto_email') or '—'}
- Tel: {_a.get('contacto_telefono') or '—'}

**Facturación**
- Razón social: {_a.get('factura_razon_social') or '—'}
- CIF: {_a.get('factura_cif') or '—'}
- Dirección fiscal: {_a.get('factura_direccion') or '—'}
- Email facturas: {_a.get('factura_email') or '—'}
- IBAN completo: `{_iban_full}`
- Banco: {_a.get('banco_nombre') or '—'} — Titular: {_a.get('banco_titular') or '—'}
""")
                        with _bb:
                            st.markdown("**Acciones**")
                            st.caption(f"🔧 Status: `{_imo_status or 'aprobada'}` | Firma: {_firma_a}")

                            if not _tiene_firma:
                                st.warning("🔴 Sin acuerdo firmado — solo se puede suspender hasta que firme.")

                            _mls_c1, _mls_c2, _mls_c3, _mls_c4 = st.columns(4)

                            with _mls_c1:
                                _is_prim_apr_mls = (_imo_status == 'aprobada')
                                if st.button("✅ APROBAR 🟢", key=f"mls_apro_{_a['id']}",
                                           use_container_width=True,
                                           disabled=not _tiene_firma,
                                           help="Requiere firma del acuerdo MLS" if not _tiene_firma else "",
                                           type="primary" if _is_prim_apr_mls else "secondary"):
                                    try:
                                        _mls_ap = db_conn()
                                        try:
                                            _mls_ap.execute("UPDATE inmobiliarias SET status=?, activa=1 WHERE id=?", ("aprobada", _a["id"]))
                                            _mls_ap.commit()
                                        finally:
                                            _mls_ap.close()
                                        st.cache_data.clear()
                                        st.success("✅ Aprobada")
                                        st.rerun()
                                    except Exception as _e:
                                        st.error(f"Error: {_e}")

                            with _mls_c2:
                                _is_prim_tram_mls = (_imo_status == 'tramite')
                                if st.button("⏳ EN TRÁMITE 🟡", key=f"mls_tramite_{_a['id']}",
                                             use_container_width=True,
                                             type="primary" if _is_prim_tram_mls else "secondary"):
                                    try:
                                        _mls_tr = db_conn()
                                        try:
                                            _mls_tr.execute("UPDATE inmobiliarias SET status=? WHERE id=?", ("tramite", _a["id"]))
                                            _mls_tr.commit()
                                        finally:
                                            _mls_tr.close()
                                        st.cache_data.clear()
                                        st.info("En trámite")
                                        st.rerun()
                                    except Exception as _e:
                                        st.error(f"Error: {_e}")

                            with _mls_c3:
                                _is_prim_susp_mls = (_imo_status in ('suspendida', 'suspended'))
                                if st.button("🔴 SUSPENDER", key=f"mls_susp_{_a['id']}",
                                             use_container_width=True,
                                             type="primary" if _is_prim_susp_mls else "secondary"):
                                    try:
                                        _mls_su = db_conn()
                                        try:
                                            # Solo suspende — NO elimina el registro
                                            _mls_su.execute("UPDATE inmobiliarias SET status=?, activa=0 WHERE id=?", ("suspendida", _a["id"]))
                                            _mls_su.commit()
                                        finally:
                                            _mls_su.close()
                                        st.cache_data.clear()
                                        st.warning("🔴 Suspendida (registro conservado)")
                                        st.rerun()
                                    except Exception as _e:
                                        st.error(f"Error: {_e}")

                            with _mls_c4:
                                with st.popover("🗑️ Eliminar", use_container_width=True):
                                    _inmo_nom_del = _a.get("nombre_comercial") or _a.get("nombre", "?")
                                    st.error(f"⚠️ ¿Eliminar '{_inmo_nom_del}'?")
                                    st.caption("Irreversible. El registro se borra de la BBDD.")
                                    if st.button("❌ Sí, eliminar", key=f"mls_b_del_yes_{_a['id']}",
                                                 type="primary", use_container_width=True):
                                        try:
                                            _mls_del = db_conn()
                                            try:
                                                _mls_del.execute("DELETE FROM inmobiliarias WHERE id=?", (_a["id"],))
                                                _mls_del.commit()
                                            finally:
                                                _mls_del.close()
                                            st.cache_data.clear()
                                            st.success("Eliminada")
                                            st.rerun()
                                        except Exception as _e:
                                            st.error(f"Error: {_e}")

        except Exception as _eb:
            st.warning(f"Error sección B: {_eb}")

        st.markdown("---")

        # ══ SECCIÓN C: Fincas MLS ════════════════════════════════════════════
        st.subheader("🏠 C. Fincas MLS en el sistema")
        try:
            # Filtro por estado
            _estados_filtro = ["Todos", "pendiente_validacion", "validada_pendiente_aprobacion",
                               "publicada", "reservada", "reserva_pendiente_confirmacion",
                               "cerrada", "pausada", "eliminada"]
            _filtro_estado = st.selectbox(
                "Filtrar por estado", _estados_filtro,
                key="mls_filtro_estado_fincas"
            )

            _fq = db_conn()
            _sql_fincas = """
                SELECT f.id, f.ref_codigo, f.titulo, f.precio, f.superficie_m2,
                       f.estado, f.created_at, f.catastro_validada,
                       f.dias_en_mercado_inicio,
                       COALESCE(i.nombre_comercial, i.nombre, '—') as listante,
                       i.email as listante_email
                FROM fincas_mls f
                LEFT JOIN inmobiliarias i ON f.inmo_id = i.id
            """
            if _filtro_estado != "Todos":
                _sql_fincas += " WHERE f.estado = ?"
                _fincas_list = _fq.execute(_sql_fincas, (_filtro_estado,)).fetchall()
            else:
                _fincas_list = _fq.execute(_sql_fincas).fetchall()
            _fq.close()

            if not _fincas_list:
                st.info("No hay fincas que coincidan con el filtro.")
            else:
                import pandas as _pd_mls
                _cols_f = ["id","ref_codigo","titulo","precio","superficie_m2","estado",
                           "created_at","catastro_validada","dias_en_mercado_inicio",
                           "listante","listante_email"]
                _df_fincas = _pd_mls.DataFrame([dict(zip(_cols_f, r)) for r in _fincas_list])

                # Calcular días en mercado
                import datetime as _dt_mls2
                def _dias(ts):
                    try:
                        d = _dt_mls2.datetime.fromisoformat(ts)
                        return (_dt_mls2.datetime.now(_dt_mls2.timezone.utc) - d).days
                    except Exception:
                        return "—"
                _df_fincas["días"] = _df_fincas["dias_en_mercado_inicio"].apply(_dias)
                _df_fincas["catastro"] = _df_fincas["catastro_validada"].map({1: "✅", 0: "⚠️"}).fillna("⚠️")

                st.dataframe(
                    _df_fincas[["ref_codigo","titulo","precio","estado","días","listante","catastro"]].rename(columns={
                        "ref_codigo": "REF", "titulo": "Título",
                        "precio": "Precio (€)", "estado": "Estado",
                        "días": "Días", "listante": "Listante", "catastro": "Catastro"
                    }),
                    use_container_width=True, hide_index=True
                )

                st.markdown("**Acciones por finca:**")
                for _, _frow in _df_fincas.iterrows():
                    _fid    = _frow["id"]
                    _fref   = _frow["ref_codigo"] or "sin ref"
                    _ftit   = _frow["titulo"] or "Sin título"
                    _festado = _frow["estado"]
                    _femail = _frow["listante_email"]
                    _flis   = _frow["listante"]

                    with st.expander(f"[{_fref}] {_ftit} — {_festado}"):
                        _fc1, _fc2 = st.columns([2, 1])
                        with _fc1:
                            st.markdown(f"**Listante:** {_flis} | **Estado:** `{_festado}` | "
                                        f"**Precio:** €{_frow['precio']:,.0f} | "
                                        f"**Superficie:** {_frow['superficie_m2']} m²")
                        with _fc2:
                            # Aprobar publicación — solo si está validada_pendiente_aprobacion
                            if _festado == "validada_pendiente_aprobacion":
                                if st.button("✅ Aprobar publicación", key=f"mls_apro_f_{_fid}",
                                             type="primary", use_container_width=True):
                                    try:
                                        _mls.update_finca_estado(_fid, "publicada")
                                        _mls_notif.notif_finca_publicada(
                                            ref_codigo=_fref,
                                            titulo=_ftit,
                                            precio=_frow["precio"],
                                            inmo_email=_femail or "",
                                        )
                                    except Exception:
                                        pass
                                    st.rerun()

                            # Confirmación reserva cliente directo
                            if _festado == "reserva_pendiente_confirmacion":
                                # Buscar datos del cliente en reservas
                                try:
                                    _rc = db_conn()
                                    _res_cli_row = _rc.execute(
                                        """SELECT notas FROM reservas_mls
                                           WHERE finca_id=? AND inmo_colaboradora_id='CLIENTE_DIRECTO'
                                           ORDER BY timestamp_reserva DESC LIMIT 1""",
                                        (_fid,)
                                    ).fetchone()
                                    _rc.close()
                                    _notas_cli = (_res_cli_row[0] or "") if _res_cli_row else ""
                                    # notas = "Cliente: {nombre} | {email}"
                                    _nom_cli, _email_cli = "—", "—"
                                    if "Cliente:" in _notas_cli and "|" in _notas_cli:
                                        _parts = _notas_cli.split("|")
                                        _nom_cli  = _parts[0].replace("Cliente:", "").strip()
                                        _email_cli = _parts[1].strip() if len(_parts) > 1 else "—"
                                except Exception:
                                    _nom_cli, _email_cli = "—", "—"

                                st.caption(f"Cliente: {_nom_cli} | {_email_cli}")
                                _rc1, _rc2 = st.columns(2)
                                with _rc1:
                                    if st.button("✅ Confirmar disponible", key=f"mls_conf_{_fid}",
                                                 type="primary", use_container_width=True):
                                        _mls.update_finca_estado(_fid, "reservada")
                                        try:
                                            _mls_notif.notif_confirmacion_reserva_cliente(
                                                email_cliente=_email_cli,
                                                nombre_cliente=_nom_cli,
                                                ref_codigo=_fref,
                                                confirmada=True,
                                            )
                                        except Exception:
                                            pass
                                        st.rerun()
                                with _rc2:
                                    if st.button("❌ No disponible", key=f"mls_nodisp_{_fid}",
                                                 use_container_width=True):
                                        _mls.update_finca_estado(_fid, "publicada")
                                        try:
                                            _mls_notif.notif_confirmacion_reserva_cliente(
                                                email_cliente=_email_cli,
                                                nombre_cliente=_nom_cli,
                                                ref_codigo=_fref,
                                                confirmada=False,
                                            )
                                        except Exception:
                                            pass
                                        st.rerun()

                            # Botones de gestión general
                            _gb1, _gb2 = st.columns(2)
                            with _gb1:
                                if _festado not in ("pausada", "cerrada", "eliminada"):
                                    if st.button("⏸ Pausar", key=f"mls_pau_{_fid}",
                                                 use_container_width=True):
                                        _mls.update_finca_estado(_fid, "pausada")
                                        st.rerun()
                                elif _festado == "pausada":
                                    if st.button("▶️ Reactivar", key=f"mls_react_{_fid}",
                                                 type="primary", use_container_width=True):
                                        _mls.update_finca_estado(_fid, "publicada")
                                        st.rerun()
                            with _gb2:
                                if _festado != "eliminada":
                                    _elim_key = f"mls_elim_confirm_{_fid}"
                                    if st.session_state.get(_elim_key):
                                        if st.button("⚠️ Confirmar borrado lógico",
                                                     key=f"mls_elim_yes_{_fid}",
                                                     use_container_width=True):
                                            _mls.update_finca_estado(_fid, "eliminada")
                                            st.session_state.pop(_elim_key, None)
                                            st.rerun()
                                    else:
                                        if st.button("🗑️ Eliminar", key=f"mls_elim_{_fid}",
                                                     use_container_width=True):
                                            st.session_state[_elim_key] = True
                                            st.rerun()
        except Exception as _ec:
            st.warning(f"Error sección C: {_ec}")

        st.markdown("---")

        # ══ SECCIÓN D: Reservas activas ══════════════════════════════════════
        st.subheader("🔒 D. Reservas activas")
        try:
            import datetime as _dt_res
            _rq = db_conn()
            _reservas_admin = _rq.execute("""
                SELECT r.id, r.finca_id, r.inmo_colaboradora_id, r.estado,
                       r.importe_reserva, r.timestamp_reserva, r.timestamp_expira_72h, r.notas,
                       f.ref_codigo, f.titulo,
                       COALESCE(il.nombre_comercial, il.nombre, '—') as listante,
                       COALESCE(ic.nombre_comercial, ic.nombre, r.inmo_colaboradora_id) as colaboradora
                FROM reservas_mls r
                LEFT JOIN fincas_mls f ON r.finca_id = f.id
                LEFT JOIN inmobiliarias il ON f.inmo_id = il.id
                LEFT JOIN inmobiliarias ic ON r.inmo_colaboradora_id = ic.id
                WHERE r.estado IN ('activa','pendiente_confirmacion_48h')
                ORDER BY r.timestamp_reserva DESC
            """).fetchall()
            _rq.close()

            if not _reservas_admin:
                st.info("No hay reservas activas en este momento.")
            else:
                _cols_r = ["id","finca_id","inmo_colaboradora_id","estado","importe_reserva",
                           "timestamp_reserva","timestamp_expira_72h","notas",
                           "ref_codigo","titulo","listante","colaboradora"]
                for _rv in _reservas_admin:
                    _rd = dict(zip(_cols_r, _rv))
                    # Calcular horas restantes
                    _hrs_rest = "—"
                    try:
                        _exp_dt = _dt_res.datetime.fromisoformat(_rd["timestamp_expira_72h"])
                        _now_dt = _dt_res.datetime.now(_dt_res.timezone.utc)
                        if _exp_dt.tzinfo is None:
                            _exp_dt = _exp_dt.replace(tzinfo=_dt_res.timezone.utc)
                        _diff   = _exp_dt - _now_dt
                        _hrs_rest = f"{max(0, int(_diff.total_seconds() // 3600))}h"
                    except Exception:
                        pass

                    _tipo_r = "👤 Cliente directo" if _rd["inmo_colaboradora_id"] == "CLIENTE_DIRECTO" \
                              else "🤝 Colaboradora"
                    with st.expander(
                        f"[{_rd['ref_codigo'] or '?'}] {_rd['titulo'] or '?'} — "
                        f"{_tipo_r} | {_hrs_rest} restantes | €{_rd['importe_reserva']:,.0f}"
                    ):
                        _ra, _rb = st.columns([3, 1])
                        with _ra:
                            st.markdown(f"""
| Campo | Valor |
|---|---|
| REF finca | `{_rd['ref_codigo'] or '—'}` |
| Tipo | {_tipo_r} |
| Colaboradora/Cliente | {_rd['colaboradora']} |
| Listante | {_rd['listante']} |
| Importe reserva | €{_rd['importe_reserva']:,.0f} |
| Reservado el | {(_rd['timestamp_reserva'] or '')[:16]} |
| Expira | {(_rd['timestamp_expira_72h'] or '')[:16]} |
| Horas restantes | **{_hrs_rest}** |
| Notas | {_rd['notas'] or '—'} |
""")
                        with _rb:
                            if st.button("⏰ Forzar expiración", key=f"mls_fexp_{_rd['id']}",
                                         use_container_width=True):
                                try:
                                    _ec2 = db_conn()
                                    _ec2.execute(
                                        "UPDATE reservas_mls SET estado='expirada' WHERE id=?",
                                        (_rd["id"],)
                                    )
                                    _ec2.execute(
                                        "UPDATE fincas_mls SET estado='publicada', updated_at=? WHERE id=?",
                                        (_dt_res.datetime.now(_dt_res.timezone.utc).isoformat(timespec="seconds"),
                                         _rd["finca_id"])
                                    )
                                    _ec2.commit()
                                    _ec2.close()
                                    st.success("Reserva expirada. Finca liberada.")
                                    st.rerun()
                                except Exception as _ef2:
                                    st.error(f"Error: {_ef2}")
        except Exception as _ed:
            st.warning(f"Error sección D: {_ed}")

        st.markdown("---")

        # ══ SECCIÓN E: Firmas del acuerdo ════════════════════════════════════
        st.subheader("✍️ E. Firmas del Acuerdo de Colaboración MLS")
        try:
            _fq2 = db_conn()
            _firmas_admin = _fq2.execute("""
                SELECT fc.id, COALESCE(i.nombre_comercial, i.nombre, '—') as inmo,
                       fc.cif, fc.timestamp, fc.ip,
                       fc.documento_hash, fc.firma_hash, fc.documento_version
                FROM firmas_colaboracion fc
                LEFT JOIN inmobiliarias i ON fc.inmo_id = i.id
                ORDER BY fc.timestamp DESC
            """).fetchall()
            _fq2.close()

            if not _firmas_admin:
                st.info("No hay firmas registradas todavía.")
            else:
                import pandas as _pd_f
                _cols_fi = ["id","inmo","cif","timestamp","ip","doc_hash","firma_hash","version"]
                _df_fi   = _pd_f.DataFrame([dict(zip(_cols_fi, r)) for r in _firmas_admin])
                # Truncar hashes para listado
                _df_fi["doc_hash_s"]   = _df_fi["doc_hash"].str[:16]  + "…"
                _df_fi["firma_hash_s"] = _df_fi["firma_hash"].str[:16] + "…"
                st.dataframe(
                    _df_fi[["inmo","cif","timestamp","ip","doc_hash_s","firma_hash_s","version"]].rename(columns={
                        "inmo": "Inmobiliaria", "cif": "CIF",
                        "timestamp": "Fecha firma", "ip": "IP",
                        "doc_hash_s": "Doc hash (16)", "firma_hash_s": "Firma hash (16)",
                        "version": "Versión"
                    }),
                    use_container_width=True, hide_index=True
                )
                st.caption("Firmas digitales eIDAS art.25 — SHA-256 sobre TEXTO_ACUERDO + timestamp + CIF + IP")

                for _, _fir in _df_fi.iterrows():
                    with st.expander(f"📄 Certificado completo — {_fir['inmo']} ({_fir['timestamp'][:10]})"):
                        st.markdown(f"""
**Inmobiliaria:** {_fir['inmo']}
**CIF:** `{_fir['cif']}`
**Timestamp:** `{_fir['timestamp']}`
**IP firmante:** `{_fir['ip']}`
**Versión documento:** `{_fir['version']}`

**Documento hash (SHA-256 completo):**
```
{_fir['doc_hash']}
```
**Firma hash (SHA-256 completo):**
```
{_fir['firma_hash']}
```
*Referencia legal: eIDAS art.25 — Firma electrónica avanzada.*
*SHA-256(TEXTO_ACUERDO_MLS + timestamp + CIF + IP)*
""")
        except Exception as _ee2:
            st.warning(f"Error sección E: {_ee2}")

        st.markdown("---")

        # ══ SECCIÓN F: Solicitudes de Colaboración 72h ═══════════════════════
        st.subheader("🤝 F. Solicitudes de Colaboración 72h")
        try:
            import json as _json_f
            _sq_f = db_conn()
            _sols_admin = _sq_f.execute("""
                SELECT id, payload, timestamp, leida
                FROM notificaciones_mls
                WHERE tipo_evento = 'solicitud_colaboracion_72h'
                  AND destinatario_id = 'admin'
                ORDER BY timestamp DESC
                LIMIT 50
            """).fetchall()
            _sq_f.close()

            _sols_pend = [s for s in _sols_admin if not s[3]]
            if _sols_pend:
                st.warning(f"**{len(_sols_pend)} solicitud(es) pendiente(s) de gestión.**")
            elif not _sols_admin:
                st.info("No hay solicitudes de colaboración todavía.")

            for _s in _sols_admin:
                _sid   = _s[0]
                _ts    = (_s[2] or "")[:16].replace("T", " ")
                _leida = bool(_s[3])
                try:
                    _pl = _json_f.loads(_s[1] or "{}")
                except Exception:
                    _pl = {}

                _ref_s    = _pl.get("ref_codigo") or "—"
                _inm_nom  = _pl.get("inmo_nombre") or "—"
                _inm_em   = _pl.get("inmo_email")  or ""
                _finca_id = _pl.get("finca_id")    or ""
                _inmo_id  = _pl.get("inmo_id")     or ""
                _notas_s  = _pl.get("notas")       or ""

                _label = f"{'✅' if _leida else '🆕'} [{_ref_s}] {_inm_nom} — {_ts}"
                with st.expander(_label, expanded=not _leida):
                    st.markdown(
                        f"**Inmo:** {_inm_nom}  \n"
                        f"**Email:** {_inm_em}  \n"
                        f"**REF finca:** `{_ref_s}`  \n"
                        f"**Notas:** {_notas_s or '—'}"
                    )
                    if not _leida and _finca_id and _inmo_id:
                        _bf1, _bf2 = st.columns(2)
                        with _bf1:
                            if st.button(
                                "✅ Confirmar reserva 72h",
                                key=f"mls_sol_ok_{_sid}",
                                type="primary",
                                use_container_width=True,
                            ):
                                try:
                                    _mls.update_finca_estado(_finca_id, "reservada")
                                    _mls.create_reserva(
                                        finca_id=_finca_id,
                                        inmo_colaboradora_id=_inmo_id,
                                        stripe_session_id=None,
                                        importe=0.0,
                                    )
                                    _mls.create_notificacion(
                                        destinatario_tipo="inmo",
                                        destinatario_id=_inmo_id,
                                        tipo_evento="solicitud_colaboracion_confirmada",
                                        payload=_json_f.dumps({
                                            "finca_id": _finca_id,
                                            "ref_codigo": _ref_s,
                                            "mensaje": "Tu solicitud de colaboración ha sido confirmada. "
                                                       "ArchiRapid se pondrá en contacto para coordinar el pago.",
                                        }),
                                    )
                                    _mls.marcar_leida(_sid)
                                    st.rerun()
                                except Exception as _ef2:
                                    st.error(f"Error al confirmar: {_ef2}")
                        with _bf2:
                            if st.button(
                                "❌ Rechazar",
                                key=f"mls_sol_no_{_sid}",
                                use_container_width=True,
                            ):
                                try:
                                    _mls.create_notificacion(
                                        destinatario_tipo="inmo",
                                        destinatario_id=_inmo_id,
                                        tipo_evento="solicitud_colaboracion_rechazada",
                                        payload=_json_f.dumps({
                                            "finca_id": _finca_id,
                                            "ref_codigo": _ref_s,
                                            "mensaje": "Tu solicitud de colaboración no pudo ser confirmada "
                                                       "en este momento. Contacta con ArchiRapid para más información.",
                                        }),
                                    )
                                    _mls.marcar_leida(_sid)
                                    st.rerun()
                                except Exception as _ef3:
                                    st.error(f"Error al rechazar: {_ef3}")
                    elif _leida:
                        st.caption("✅ Gestionada")
        except Exception as _ef_sec:
            st.warning(f"Error sección F: {_ef_sec}")

        st.markdown("---")

        # ══ SECCIÓN G: Trial 30 días ══════════════════════════════════════════
        st.subheader("🎁 G. Emails de ciclo trial (día 7 y día 25)")
        st.caption(
            "Envía emails de check-in (día 7) y urgencia (día 25) a todas las "
            "inmobiliarias con trial activo que cumplan el criterio. "
            "Los emails no se duplican si el criterio ya no aplica."
        )
        try:
            if st.button("📧 Ejecutar envío de emails de trial ahora",
                         key="mls_trial_emails_run", type="primary"):
                from modules.mls.mls_trial_emails import check_and_send_trial_emails
                _sent = check_and_send_trial_emails()
                if _sent:
                    st.success(f"✅ Emails enviados: {_sent}")
                else:
                    st.info("Ninguna inmobiliaria cumple el criterio de envío ahora mismo.")

            # Tabla resumen de trials activos
            from modules.mls import mls_db as _mls_db_g
            _trials = _mls_db_g.get_inmos_con_trial_activo()
            if _trials:
                import datetime as _dt_g
                _trial_rows = []
                for _t in _trials:
                    _ts = _mls_db_g.check_trial_status(_t["id"])
                    _trial_rows.append({
                        "Nombre": _t.get("nombre_comercial") or _t.get("nombre", "?"),
                        "Email": _t.get("email", "—"),
                        "Inicio trial": (_t.get("trial_start_date") or "")[:10],
                        "Días restantes": _ts["days_remaining"],
                        "Día trial": _ts["trial_day"],
                    })
                import pandas as _pd_g
                st.dataframe(_pd_g.DataFrame(_trial_rows),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No hay inmobiliarias con trial activo.")
        except Exception as _eg:
            st.warning(f"Error sección G: {_eg}")

    elif _admin_seccion == "⚖️ Disclaimers Legales":
        try:
            import pandas as pd
            from modules.marketplace.utils import db_conn as _dc11

            st.subheader("⚖️ Registro de Disclaimers Aceptados")

            _conn11 = _dc11()
            try:
                _rows11 = _conn11.execute("""
                    SELECT email, nombre_completo, tipo_disclaimer,
                           timestamp_utc, hash_sha256, pdf_url, version_texto
                    FROM disclaimers_aceptados
                    ORDER BY timestamp_utc DESC
                    LIMIT 200
                """).fetchall()
            finally:
                _conn11.close()

            if _rows11:
                _df11 = pd.DataFrame(
                    [tuple(r) for r in _rows11],
                    columns=["Email", "Nombre", "Tipo", "Fecha UTC", "Hash SHA-256", "PDF", "Versión"]
                )
                _df11_display = _df11.copy()
                _df11_display["Hash SHA-256"] = _df11_display["Hash SHA-256"].str[:20] + "..."

                st.metric("Total aceptaciones registradas", len(_df11))

                _col_a, _col_b = st.columns(2)
                _col_a.metric("Diseño IA", int((_df11["Tipo"] == "diseno_ia").sum()))
                _col_b.metric("Documentación/Pago", int((_df11["Tipo"] == "documentacion_pago").sum()))

                st.dataframe(_df11_display, use_container_width=True)

                _csv11 = _df11.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Exportar CSV completo",
                    _csv11,
                    "disclaimers_archirapid.csv",
                    "text/csv",
                    key="dl_disclaimers_csv"
                )

                st.markdown("---")
                st.markdown("**📄 Certificados individuales con SHA-256:**")
                for _idx11, _row11 in _df11.iterrows():
                    with st.expander(f"📄 {_row11['Email']} — {_row11['Tipo']} ({str(_row11['Fecha UTC'])[:10]})"):
                        _cert_txt = f"""ARCHIRAPID — REGISTRO DE ACEPTACIÓN DE DISCLAIMER
=================================================
Email:       {_row11['Email']}
Nombre:      {_row11['Nombre']}
Tipo:        {_row11['Tipo']}
Versión:     {_row11['Versión']}
Fecha UTC:   {_row11['Fecha UTC']}
Hash SHA-256 (completo):
{_row11['Hash SHA-256']}

Nota: Este registro cumple con el RGPD y eIDAS art.25.
Conservar durante 5 años como evidencia legal.
"""
                        _cert_col1, _cert_col2 = st.columns([3, 1])
                        with _cert_col1:
                            st.code(_cert_txt, language=None)
                        with _cert_col2:
                            st.download_button(
                                "⬇️ Descargar certificado",
                                _cert_txt.encode("utf-8"),
                                file_name=f"disclaimer_{_row11['Email'].replace('@','_')}_{str(_row11['Fecha UTC'])[:10]}.txt",
                                mime="text/plain",
                                key=f"dl_disc_{_idx11}",
                                use_container_width=True,
                            )
                            if _row11.get("PDF") and str(_row11["PDF"]).startswith("http"):
                                st.link_button("📥 PDF original", _row11["PDF"], use_container_width=True)
            else:
                st.info("No hay disclaimers registrados aún.")

        except Exception as _eh:
            st.warning(f"Error sección Disclaimers: {_eh}")

    elif _admin_seccion == "🎓 Estudiantes":
        try:
            _admin_estudiantes_tab()
        except Exception as _eh12:
            st.warning(f"Error sección Estudiantes: {_eh12}")

    elif _admin_seccion == "🏠 Prefabricadas":
        try:
            from modules.prefabricadas.admin import render_admin_prefabricadas
            render_admin_prefabricadas()
        except Exception as _eh_pref:
            st.warning(f"Error sección Prefabricadas: {_eh_pref}")

# ─── ADMIN ESTUDIANTES ────────────────────────────────────────────────────────

def _admin_estudiantes_tab():
    st.header("🎓 Gestión de Estudiantes")

    tab_reg, tab_proy = st.tabs(["Solicitudes de registro", "Proyectos pendientes"])

    with tab_reg:
        _admin_solicitudes_estudiantes()

    with tab_proy:
        _admin_proyectos_tfg()


def _admin_solicitudes_estudiantes():
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, nombre_completo, universidad, año_tfg,
                   ciudad, estado, hash_autorizacion, pdf_autorizacion_url, created_at
            FROM estudiantes
            ORDER BY
                CASE estado WHEN 'pendiente' THEN 0 WHEN 'aprobado' THEN 1 ELSE 2 END,
                created_at DESC
        """)
        rows = cur.fetchall()
    finally:
        conn.close()

    pendientes = [r for r in rows if r[6] == "pendiente"]
    st.metric("Pendientes de revisión", len(pendientes))

    for r in rows:
        id_, email, nombre, uni, año, ciudad, estado, hash_val, pdf_url, fecha = (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]
        )
        _est_icon = {"pendiente": "⏳", "aprobado": "🟢", "rechazado": "🔴", "suspendido": "🔴"}.get(estado, "⚪")
        with st.expander(f"{_est_icon} {nombre} — {uni} ({estado})"):
            st.write(f"**Email:** {email}")
            st.write(f"**Universidad:** {uni} | **Año TFG:** {año} | **Ciudad:** {ciudad}")
            st.write(f"**Registrado:** {str(fecha)[:10]}")
            if hash_val:
                st.caption(f"SHA-256: {str(hash_val)[:32]}...")
            if pdf_url:
                st.markdown(f"[📄 Ver autorización firmada]({pdf_url})")

            # Patrón unificado 4 botones para TODOS los estados
            _ec1, _ec2, _ec3, _ec4 = st.columns(4)
            with _ec1:
                if st.button("✅ Aprobar 🟢", key=f"est_apr_{id_}",
                             type="primary" if estado == "aprobado" else "secondary",
                             use_container_width=True):
                    _cambiar_estado_estudiante(id_, "aprobado")
                    st.rerun()
            with _ec2:
                if st.button("⏳ Pendiente 🟡", key=f"est_pend_{id_}",
                             type="primary" if estado == "pendiente" else "secondary",
                             use_container_width=True):
                    _cambiar_estado_estudiante(id_, "pendiente")
                    st.rerun()
            with _ec3:
                if st.button("🔴 Suspender", key=f"est_susp_{id_}",
                             type="primary" if estado in ("suspendido", "rechazado") else "secondary",
                             use_container_width=True):
                    _cambiar_estado_estudiante(id_, "suspendido")
                    st.rerun()
            with _ec4:
                with st.popover("🗑️ Eliminar", use_container_width=True):
                    st.error(f"⚠️ ¿Eliminar a {nombre}?")
                    st.caption("Irreversible.")
                    if st.button("❌ Sí, eliminar", key=f"est_del_{id_}",
                                 type="primary", use_container_width=True):
                        _c = db_conn()
                        try:
                            _c.execute("DELETE FROM estudiantes WHERE id=?", (id_,))
                            _c.commit()
                        finally:
                            _c.close()
                        st.success("Estudiante eliminado")
                        st.rerun()


def _admin_proyectos_tfg():
    # Mostrar estudiantes aprobados sin proyectos subidos
    try:
        _conn_no_proj = db_conn()
        try:
            _est_sin_proj = _conn_no_proj.execute("""
                SELECT e.email, e.nombre_completo, e.universidad, e.año_tfg, e.estado
                FROM estudiantes e
                WHERE e.estado = 'aprobado'
                  AND NOT EXISTS (
                      SELECT 1 FROM proyectos_tfg p WHERE p.email_estudiante = e.email
                  )
            """).fetchall()
        finally:
            _conn_no_proj.close()
        if _est_sin_proj:
            st.info(f"ℹ️ {len(_est_sin_proj)} estudiante(s) aprobado(s) sin proyectos subidos aún:")
            for _es in _est_sin_proj:
                st.caption(f"• {_es[1]} ({_es[0]}) — {_es[2]}, año {_es[3]}")
    except Exception:
        pass

    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.titulo, p.email_estudiante, p.precio_venta,
                   p.modalidad_venta, p.tipologia, p.provincia,
                   p.estado, p.archivo_planos_url, p.imagen_portada_url,
                   p.hash_documento, p.created_at,
                   COALESCE(e.nombre_completo, p.email_estudiante) as nombre_est,
                   COALESCE(e.universidad, '—') as universidad
            FROM proyectos_tfg p
            LEFT JOIN estudiantes e ON p.email_estudiante = e.email
            ORDER BY
                CASE p.estado WHEN 'pendiente' THEN 0 WHEN 'aprobado' THEN 1 ELSE 2 END,
                p.created_at DESC
        """)
        rows = cur.fetchall()
    finally:
        conn.close()

    pendientes = [r for r in rows if r[7] == "pendiente"]
    st.metric("Proyectos pendientes", len(pendientes))

    for r in rows:
        id_, titulo, email, precio, modalidad, tipologia, provincia, estado, \
            url_planos, url_portada, hash_doc, fecha, nombre_est, universidad = (
                r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                r[7], r[8], r[9], r[10], r[11], r[12], r[13]
            )
        icono = "⏳" if estado == "pendiente" else ("✅" if estado == "aprobado" else "❌")
        with st.expander(f"{icono} {titulo} — {precio}€ ({estado}) | {nombre_est}"):
            st.write(f"**Estudiante:** {nombre_est} ({email}) — {universidad}")
            st.write(f"**Tipología:** {tipologia} | **Provincia:** {provincia}")
            st.write(f"**Modalidad:** {modalidad} | **Precio:** {precio}€")
            st.write(f"**Subido:** {str(fecha)[:10]}")
            if hash_doc:
                st.caption(f"SHA-256: {str(hash_doc)[:32]}...")
            if url_planos:
                st.markdown(f"[📐 Ver planos]({url_planos})")

            if estado == "pendiente":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Aprobar y publicar", key=f"apr_proy_{id_}"):
                        _cambiar_estado_proyecto(id_, "aprobado")
                        st.rerun()
                with col2:
                    if st.button("❌ Rechazar", key=f"rec_proy_{id_}"):
                        _cambiar_estado_proyecto(id_, "rechazado")
                        st.rerun()
            else:
                # Para proyectos aprobados o rechazados, ofrecer opciones de cambio de estado
                _proj_col1, _proj_col2, _proj_col3, _proj_col4 = st.columns(4)
                with _proj_col1:
                    if estado != "aprobado":
                        if st.button("✅ Restaurar", key=f"btn_tfg_restore_{id_}", type="primary", use_container_width=True):
                            _cambiar_estado_proyecto(id_, "aprobado")
                            st.rerun()
                with _proj_col2:
                    if st.button("⏸ Pausar", key=f"btn_tfg_pause_{id_}", use_container_width=True):
                        _cambiar_estado_proyecto(id_, "pausado")
                        st.rerun()
                with _proj_col3:
                    if st.button("🔴 Suspender", key=f"btn_tfg_suspend_{id_}", use_container_width=True):
                        _cambiar_estado_proyecto(id_, "suspendido")
                        st.rerun()
                with _proj_col4:
                    with st.popover("🗑️ Eliminar", use_container_width=True):
                        st.error(f"⚠️ ¿Eliminar '{titulo}'?")
                        st.caption("Irreversible.")
                        if st.button("❌ Sí, eliminar", key=f"btn_tfg_delete_{id_}", type="primary", use_container_width=True):
                            _cp = db_conn()
                            _cp.execute("DELETE FROM proyectos_tfg WHERE id=?", (id_,))
                            _cp.commit()
                            _cp.close()
                            st.success("Proyecto eliminado")
                            st.rerun()


def _cambiar_estado_estudiante(id_: int, nuevo_estado: str):
    _is_active = 1 if nuevo_estado == "aprobado" else 0
    conn = db_conn()
    try:
        conn.execute("""
            UPDATE estudiantes
            SET estado = ?, status = ?, is_active = ?, approved_at = datetime('now')
            WHERE id = ?
        """, (nuevo_estado, nuevo_estado, _is_active, id_))
        conn.commit()
    finally:
        conn.close()


def _cambiar_estado_proyecto(id_: int, nuevo_estado: str):
    _is_active = 1 if nuevo_estado == "aprobado" else 0
    conn = db_conn()
    try:
        conn.execute("""
            UPDATE proyectos_tfg
            SET estado = ?, status = ?, is_active = ?, activo = ?, approved_at = datetime('now')
            WHERE id = ?
        """, (nuevo_estado, nuevo_estado, _is_active, _is_active, id_))
        conn.commit()
    finally:
        conn.close()
