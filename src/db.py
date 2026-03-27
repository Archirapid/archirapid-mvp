"""Base de datos centralizada para ArchiRapid (SQLite/PostgreSQL)."""
from __future__ import annotations
import os
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Iterator

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

import streamlit as st
from src.db_compat import adapt_sql, adapt_params

BASE_PATH = Path.cwd()
# Use a fixed absolute database path to ensure all modules use the same DB file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.db")


def _get_db_mode() -> str:
    """
    Detecta si usar PostgreSQL o SQLite.
    Retorna 'postgres' o 'sqlite'.
    """
    try:
        import streamlit as st
        url = st.secrets.get(
            "SUPABASE_DB_URL",
            os.getenv("SUPABASE_DB_URL", "")
        )
        if url and _PSYCOPG2_AVAILABLE:
            return 'postgres'
    except Exception:
        url = os.getenv("SUPABASE_DB_URL", "")
        if url and _PSYCOPG2_AVAILABLE:
            return 'postgres'
    return 'sqlite'


# Variable global del modo actual
DB_MODE = _get_db_mode()


class _CompatRow:
    """
    Fila compatible con sqlite3.Row: soporta row[0] (índice) Y row['col'] (nombre).
    Devuelta por fetchone()/fetchall() en modo Postgres para que el código existente
    que usa row[N] no rompa al cambiar de SQLite a PostgreSQL.
    """
    __slots__ = ('_data', '_cols')

    def __init__(self, row_dict: dict, cols: list):
        self._data = row_dict
        self._cols = cols  # orden de columnas tal como devuelve description

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._cols[key]]
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def __iter__(self):
        return iter(self._data.values())

    def __bool__(self):
        return True  # nunca None; None se devuelve explícitamente

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        return f'_CompatRow({self._data!r})'


def _make_compat_row(raw_row, description) -> '_CompatRow':
    """Construye un _CompatRow a partir de un RealDictRow y el description del cursor."""
    cols = [d[0] for d in description] if description else []
    return _CompatRow(dict(raw_row), cols)


class _PgAdaptingCursor:
    """
    Cursor que adapta SQL antes de ejecutar.
    Devuelto por _PostgresConnWrapper.cursor() para que
    conn.cursor().execute() también pase por adapt_sql().
    """
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = adapt_sql(sql, is_postgres=True)
        params = adapt_params(params, True)
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql, params_list):
        sql = adapt_sql(sql, is_postgres=True)
        self._cur.executemany(sql, params_list)

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _make_compat_row(row, self._cur.description)

    def fetchall(self):
        desc = self._cur.description
        return [_make_compat_row(r, desc) for r in self._cur.fetchall()]

    def __iter__(self):
        desc = self._cur.description
        for row in self._cur:
            yield _make_compat_row(row, desc)

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        try:
            row = self._cur.fetchone()
            return row.get('id') if row else None
        except Exception:
            return None

    @property
    def connection(self):
        return self._cur.connection

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class _PgCursorWrapper:
    """Wrapper del cursor PostgreSQL (devuelto por _PostgresConnWrapper.execute())."""
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _make_compat_row(row, self._cur.description)

    def fetchall(self):
        desc = self._cur.description
        return [_make_compat_row(r, desc) for r in self._cur.fetchall()]

    def __iter__(self):
        desc = self._cur.description
        for row in self._cur:
            yield _make_compat_row(row, desc)

    @property
    def lastrowid(self):
        # PostgreSQL no tiene lastrowid
        # Se obtiene con RETURNING id
        try:
            row = self._cur.fetchone()
            return row.get('id') if row else None
        except Exception:
            return None

    @property
    def description(self):
        return self._cur.description

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class _PostgresConnWrapper:
    """
    Hace que psycopg2 se comporte como sqlite3
    para que los 28 archivos no noten diferencia.
    - execute() adapta SQL automáticamente
    - fetchone/fetchall devuelven Row-like dicts
    - commit/close funcionan igual
    """
    def __init__(self, conn):
        self._conn = conn
        self._cursor = None

    def execute(self, sql, params=None):
        sql = adapt_sql(sql, is_postgres=True)
        params = adapt_params(params, True)
        cur = self._conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        cur.execute(sql, params)
        self._cursor = cur
        return _PgCursorWrapper(cur)

    def executemany(self, sql, params_list):
        sql = adapt_sql(sql, is_postgres=True)
        cur = self._conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        cur.executemany(sql, params_list)
        self._cursor = cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self, **kwargs):
        raw = self._conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return _PgAdaptingCursor(raw)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.commit()
        self._conn.close()


def _get_sqlite_conn():
    """Conexión SQLite — igual que antes."""
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_pg_url() -> str:
    """Obtiene y normaliza la URL de PostgreSQL desde secrets o env."""
    try:
        import streamlit as st
        url = st.secrets.get("SUPABASE_DB_URL", os.getenv("SUPABASE_DB_URL", ""))
    except Exception:
        url = os.getenv("SUPABASE_DB_URL", "")
    if url and 'sslmode' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=require'
    return url


# ── Connection pool (module-level singleton) ───────────────────────────────────
import threading as _threading

_pg_pool_lock = _threading.Lock()
_pg_pool_ref: list = [None]  # list so inner scope can mutate it


def _get_or_create_pool():
    """Crea el pool de conexiones PostgreSQL una sola vez (thread-safe)."""
    with _pg_pool_lock:
        if _pg_pool_ref[0] is None:
            try:
                from psycopg2 import pool as _pgpool
                url = _resolve_pg_url()
                if url:
                    _pg_pool_ref[0] = _pgpool.ThreadedConnectionPool(
                        minconn=1, maxconn=5, dsn=url, connect_timeout=15,
                    )
            except Exception as e:
                print(f"[DB pool] No se pudo crear el pool: {e}")
        return _pg_pool_ref[0]


class _PooledPostgresConn(_PostgresConnWrapper):
    """Conexión prestada de un pool. close() devuelve al pool en lugar de desconectar."""
    def __init__(self, conn, pool):
        super().__init__(conn)
        self._pool = pool

    def close(self):
        try:
            if not self._conn.autocommit:
                self._conn.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass

    def __exit__(self, *args):
        self._conn.commit()
        self.close()


def _get_postgres_conn():
    """Conexión PostgreSQL — del pool si disponible, directa como fallback."""
    pool = _get_or_create_pool()
    if pool is not None:
        try:
            raw = pool.getconn()
            raw.autocommit = False
            # Garantizar estado limpio: si la conexión vuelve al pool sin rollback,
            # la siguiente llamada la encontraría en "transaction aborted".
            try:
                raw.rollback()
            except Exception:
                pass
            return _PooledPostgresConn(raw, pool)
        except Exception:
            pass  # Pool agotado o error, usar conexión directa

    # Fallback: conexión directa (igual que antes)
    url = _resolve_pg_url()
    if not url:
        raise RuntimeError("SUPABASE_DB_URL no está configurada en secrets/.env")
    try:
        conn = psycopg2.connect(url, connect_timeout=15, sslmode='require')
    except psycopg2.OperationalError as e:
        host = url.split('@')[-1].split('/')[0] if '@' in url else 'desconocido'
        raise RuntimeError(
            f"psycopg2 no pudo conectar a {host} — "
            f"verifica SUPABASE_DB_URL, puerto y SSL. "
            f"Error original: {type(e).__name__}"
        ) from None
    conn.autocommit = False
    return _PostgresConnWrapper(conn)


def get_conn():
    """
    Devuelve conexión a BD.
    PostgreSQL si SUPABASE_DB_URL está en secrets.
    SQLite si no — comportamiento idéntico al actual.
    """
    if DB_MODE == 'postgres':
        return _get_postgres_conn()
    return _get_sqlite_conn()

@contextmanager
def transaction() -> Iterator[sqlite3.Cursor]:
    """Context manager para operaciones atómicas.

    Uso:
        with transaction() as cur:
            cur.execute(...)
            cur.execute(...)
    Hace commit automático si no hay excepción; rollback si falla.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ── PostgreSQL DDL ─────────────────────────────────────────────────────────────
# CREATE TABLE statements con TODAS las columnas consolidadas (sin ALTER TABLE).
# Ordenadas respetando dependencias de FK.
# adapt_sql() se aplica automáticamente en _PostgresConnWrapper.execute().

_PG_DDL = [
    """CREATE TABLE IF NOT EXISTS plots (
        id TEXT PRIMARY KEY,
        title TEXT, description TEXT, lat REAL, lon REAL,
        m2 INTEGER, height REAL, price REAL, type TEXT, province TEXT,
        locality TEXT, owner_name TEXT, owner_email TEXT,
        image_path TEXT, registry_note_path TEXT, created_at TEXT,
        address TEXT, owner_phone TEXT, photo_paths TEXT,
        catastral_ref TEXT, services TEXT, status TEXT DEFAULT 'published',
        plano_catastral_path TEXT, vertices_coordenadas TEXT,
        numero_parcela_principal TEXT, superficie_parcela REAL,
        superficie_edificable REAL, solar_virtual TEXT,
        featured INTEGER DEFAULT 0, tour_360_b64 TEXT,
        buildable_m2 REAL, ai_verification_cache TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        title TEXT, description TEXT,
        m2_construidos REAL, area_m2 REAL, price REAL,
        estimated_cost REAL, architect_name TEXT, max_height REAL,
        style TEXT, file_path TEXT, ocr_text TEXT,
        parsed_data_json TEXT, characteristics_json TEXT,
        architect_id TEXT,
        m2_parcela_minima INTEGER, m2_parcela_maxima INTEGER,
        habitaciones INTEGER, banos INTEGER, garaje INTEGER,
        plantas INTEGER, certificacion_energetica TEXT,
        tipo_proyecto TEXT, foto_principal TEXT, galeria_fotos TEXT,
        modelo_3d_glb TEXT, planos_pdf TEXT, planos_dwg TEXT,
        memoria_pdf TEXT, price_memoria REAL DEFAULT 1800,
        price_cad REAL DEFAULT 2500,
        property_type TEXT DEFAULT 'residencial',
        energy_rating TEXT, vr_tour TEXT, is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        amount REAL, concept TEXT, buyer_name TEXT, buyer_email TEXT,
        buyer_phone TEXT, buyer_nif TEXT, method TEXT, status TEXT,
        timestamp TEXT, card_last4 TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY,
        name TEXT, email TEXT, phone TEXT, address TEXT,
        preferences TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS reservations (
        id TEXT PRIMARY KEY,
        plot_id TEXT, buyer_name TEXT, buyer_email TEXT,
        amount REAL, kind TEXT, created_at TEXT,
        buyer_dni TEXT, buyer_domicilio TEXT, buyer_province TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS architects (
        id TEXT PRIMARY KEY,
        name TEXT, email TEXT UNIQUE, phone TEXT, company TEXT, nif TEXT,
        created_at TEXT,
        proyectos_estudio_count INTEGER DEFAULT 0,
        specialty TEXT, address TEXT, city TEXT, province TEXT,
        avg_project_price REAL, origen_registro TEXT, password_hash TEXT,
        fee_pct REAL DEFAULT 8.0,
        expenses_pct REAL DEFAULT 5.0,
        iva_pct REAL DEFAULT 10.0
    )""",
    """CREATE TABLE IF NOT EXISTS ai_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_email TEXT, project_name TEXT,
        total_area REAL, total_cost REAL, services_json TEXT,
        style TEXT, energy_label TEXT, created_at TEXT, status TEXT,
        req_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS estudio_projects (
        id TEXT PRIMARY KEY,
        architect_id TEXT NOT NULL, catastral_ref TEXT,
        address TEXT, surface_m2 REAL, style TEXT,
        rooms INTEGER, budget REAL, total_cost REAL,
        zip_filename TEXT, stripe_session_id TEXT,
        paid INTEGER DEFAULT 0, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        architect_id TEXT, plan_type TEXT, price REAL,
        monthly_proposals_limit INTEGER, commission_rate REAL,
        status TEXT, start_date TEXT, end_date TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS visitas_demo (
        id TEXT PRIMARY KEY,
        timestamp TEXT, origen TEXT, nombre_usuario TEXT,
        accion_realizada TEXT,
        convirtio_a_registro INTEGER DEFAULT 0, session_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS proposals (
        id TEXT PRIMARY KEY,
        architect_id TEXT, plot_id TEXT, proposal_text TEXT,
        estimated_budget REAL, deadline_days INTEGER,
        sketch_image_path TEXT, status TEXT, created_at TEXT,
        responded_at TEXT,
        delivery_format TEXT DEFAULT 'PDF',
        delivery_price REAL DEFAULT 1200,
        supervision_fee REAL DEFAULT 0,
        visa_fee REAL DEFAULT 0,
        total_cliente REAL DEFAULT 0,
        commission REAL DEFAULT 0,
        project_id TEXT, message TEXT, price REAL
    )""",
    """CREATE TABLE IF NOT EXISTS additional_services (
        id TEXT PRIMARY KEY,
        proposal_id TEXT, client_id TEXT, architect_id TEXT,
        service_type TEXT, description TEXT, price REAL,
        commission REAL, total_cliente REAL, status TEXT,
        created_at TEXT, quoted_at TEXT, accepted_at TEXT,
        paid INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS arquitectos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT, email TEXT UNIQUE, telefono TEXT,
        especialidad TEXT, plan_id INTEGER, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS proyectos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arquitecto_id INTEGER, titulo TEXT, estilo TEXT,
        m2_construidos REAL, presupuesto_ejecucion REAL,
        m2_parcela_minima REAL, alturas INTEGER,
        pdf_path TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS prefab_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, m2 REAL NOT NULL,
        rooms INTEGER NOT NULL, bathrooms INTEGER NOT NULL,
        floors INTEGER NOT NULL, material TEXT NOT NULL,
        price REAL NOT NULL, description TEXT, image_path TEXT,
        active INTEGER DEFAULT 1,
        modulos TEXT, price_label TEXT, image_paths TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS owners (
        id TEXT PRIMARY KEY,
        name TEXT, email TEXT UNIQUE,
        phone TEXT, address TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        profile TEXT, created_at TEXT DEFAULT (datetime('now')),
        approved INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS stripe_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL, product_key TEXT,
        project_id TEXT, user_email TEXT, amount_eur REAL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS project_purchases (
        id TEXT PRIMARY KEY,
        project_id TEXT, buyer_email TEXT, product_type TEXT,
        price REAL, status TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ventas_proyectos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER NOT NULL, cliente_email TEXT NOT NULL,
        nombre_cliente TEXT NOT NULL, telefono TEXT, direccion TEXT,
        nif TEXT, productos_comprados TEXT,
        total_pagado REAL NOT NULL, metodo_pago TEXT,
        fecha_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        stripe_session_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS service_providers (
        id TEXT PRIMARY KEY, name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, nif TEXT, specialty TEXT,
        company TEXT, phone TEXT, address TEXT,
        certifications TEXT, experience_years INTEGER,
        service_area TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE,
        password_hash TEXT, full_name TEXT,
        role TEXT DEFAULT 'client',
        is_professional INTEGER DEFAULT 0,
        address TEXT, professional_id TEXT, plan_id TEXT,
        bio TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        name TEXT, company TEXT, phone TEXT, specialty TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS project_tablon (
        id TEXT PRIMARY KEY, client_email TEXT, client_name TEXT,
        project_name TEXT, province TEXT, style TEXT,
        total_area REAL, total_cost REAL, coste_m2 REAL,
        budget_json TEXT, created_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS construction_offers (
        id TEXT PRIMARY KEY, tablon_id TEXT, provider_id TEXT,
        provider_name TEXT, provider_email TEXT, client_email TEXT,
        project_name TEXT, total_area REAL, price_no_mat REAL,
        price_with_mat REAL, includes_materials INTEGER DEFAULT 0,
        plazo_semanas INTEGER, garantia_anos INTEGER DEFAULT 5,
        nota_tecnica TEXT, breakdown_json TEXT,
        estado TEXT DEFAULT 'enviada', created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS service_assignments (
        id TEXT PRIMARY KEY, venta_id TEXT, proveedor_id TEXT,
        servicio_tipo TEXT, cliente_email TEXT, proyecto_id TEXT,
        precio_servicio REAL, estado TEXT DEFAULT 'pendiente',
        fecha_asignacion TEXT, fecha_completado TEXT, notas TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS plot_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL, name TEXT, province TEXT,
        max_price REAL DEFAULT 0, created_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS document_certs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_hash TEXT NOT NULL, doc_name TEXT,
        user_email TEXT, plot_id TEXT,
        certified_at TEXT NOT NULL,
        polygon_tx TEXT DEFAULT NULL,
        polygon_net TEXT DEFAULT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS planes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_plan TEXT, precio_mensual REAL,
        limite_proyectos INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS client_interests (
        id TEXT PRIMARY KEY, email TEXT, project_id TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS inmobiliarias (
        id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL, cif TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        telefono TEXT, web TEXT, plan TEXT DEFAULT 'starter',
        plan_activo INTEGER DEFAULT 0, stripe_session_id TEXT,
        firma_hash TEXT, firma_timestamp TEXT,
        activa INTEGER DEFAULT 0, ip_registro TEXT, created_at TEXT,
        nombre_sociedad TEXT, nombre_comercial TEXT,
        telefono_secundario TEXT, telegram_contacto TEXT,
        direccion TEXT, localidad TEXT, provincia TEXT,
        codigo_postal TEXT, pais TEXT DEFAULT 'España',
        contacto_nombre TEXT, contacto_cargo TEXT,
        contacto_email TEXT, contacto_telefono TEXT,
        contacto_telegram TEXT, factura_razon_social TEXT,
        factura_cif TEXT, factura_direccion TEXT, factura_email TEXT,
        iban TEXT, banco_nombre TEXT, banco_titular TEXT,
        email_login TEXT,
        trial_start_date TEXT DEFAULT NULL,
        trial_active INTEGER DEFAULT 0,
        trial_expired INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS fincas_mls (
        id TEXT PRIMARY KEY,
        inmo_id TEXT NOT NULL, secuencial INTEGER,
        ref_codigo TEXT UNIQUE, catastro_ref TEXT NOT NULL,
        catastro_validada INTEGER DEFAULT 0,
        catastro_lat REAL, catastro_lon REAL,
        catastro_direccion TEXT, catastro_municipio TEXT,
        titulo TEXT, descripcion_publica TEXT,
        notas_privadas TEXT, precio REAL, superficie_m2 REAL,
        tipo_suelo TEXT, servicios TEXT, forma_solar TEXT, orientacion TEXT,
        comision_total_pct REAL,
        comision_archirapid_pct REAL DEFAULT 1.0,
        comision_colaboradora_pct REAL, comision_listante_pct REAL,
        split_aceptado INTEGER DEFAULT 0,
        estado TEXT DEFAULT 'pendiente_validacion',
        image_paths TEXT, precio_historial TEXT,
        dias_en_mercado_inicio TEXT, periodo_privado_expira TEXT,
        created_at TEXT, updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS reservas_mls (
        id TEXT PRIMARY KEY,
        finca_id TEXT NOT NULL,
        inmo_colaboradora_id TEXT NOT NULL,
        stripe_session_id TEXT,
        importe_reserva REAL DEFAULT 200.0,
        estado TEXT DEFAULT 'activa',
        timestamp_reserva TEXT, timestamp_expira_72h TEXT, notas TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS firmas_colaboracion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inmo_id TEXT NOT NULL,
        documento_version TEXT DEFAULT '1.0',
        documento_hash TEXT NOT NULL, firma_hash TEXT NOT NULL,
        timestamp TEXT NOT NULL, ip TEXT, cif TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS notificaciones_mls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destinatario_tipo TEXT, destinatario_id TEXT,
        tipo_evento TEXT, payload TEXT, timestamp TEXT,
        leida INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS leads_mls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        empresa TEXT,
        email TEXT NOT NULL,
        telefono TEXT,
        num_fincas TEXT,
        mensaje TEXT,
        origen TEXT DEFAULT 'web',
        estado TEXT DEFAULT 'nuevo',
        created_at TEXT
    )""",
]

_PG_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_plots_province ON plots(province)",
    "CREATE INDEX IF NOT EXISTS idx_projects_style ON projects(style)",
    "CREATE INDEX IF NOT EXISTS idx_projects_architect ON projects(architect_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)",
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_architect ON subscriptions(architect_id)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_plot ON proposals(plot_id)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_architect ON proposals(architect_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_email ON clients(email)",
    "CREATE INDEX IF NOT EXISTS idx_reservations_plot ON reservations(plot_id)",
    "CREATE INDEX IF NOT EXISTS idx_reservations_kind ON reservations(kind)",
    "CREATE INDEX IF NOT EXISTS idx_additional_services_client ON additional_services(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_additional_services_architect ON additional_services(architect_id)",
    "CREATE INDEX IF NOT EXISTS idx_additional_services_proposal ON additional_services(proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_additional_services_status ON additional_services(status)",
    "CREATE INDEX IF NOT EXISTS idx_inmobiliarias_email ON inmobiliarias(email)",
    "CREATE INDEX IF NOT EXISTS idx_inmobiliarias_cif ON inmobiliarias(cif)",
    "CREATE INDEX IF NOT EXISTS idx_fincas_mls_estado ON fincas_mls(estado)",
    "CREATE INDEX IF NOT EXISTS idx_fincas_mls_inmo ON fincas_mls(inmo_id)",
    "CREATE INDEX IF NOT EXISTS idx_reservas_mls_finca ON reservas_mls(finca_id)",
    "CREATE INDEX IF NOT EXISTS idx_reservas_mls_estado ON reservas_mls(estado)",
    "CREATE INDEX IF NOT EXISTS idx_firmas_inmo ON firmas_colaboracion(inmo_id)",
]

_PG_PREFAB_SEED = [
    ("Studio Modular 45",  45,  1, 1, 1, "Modular acero",     44900,  "Vivienda compacta de acero modular, ideal para parcelas pequeñas. Certificación energética A.",   "assets/branding/logo.png"),
    ("Eco Timber 65",      65,  2, 1, 1, "Madera",            67500,  "Casa de madera laminada con aislamiento superior. Diseño nórdico, bajo mantenimiento.",            "assets/branding/logo.png"),
    ("Nordic Home 80",     80,  3, 1, 1, "Madera",            88000,  "3 dormitorios, salón abierto, porche cubierto. Clase energética A+.",                              "assets/branding/logo.png"),
    ("Smart Compact 55",   55,  2, 1, 1, "Modular acero",     57500,  "Módulo doble con cocina integrada. Entrega en 90 días desde firma.",                               "assets/branding/logo.png"),
    ("Green Container 60", 60,  2, 1, 1, "Contenedor",        51000,  "Dos contenedores HC interconectados, acabados premium, azotea transitable.",                       "assets/branding/logo.png"),
    ("Bioclimática 95",    95,  3, 2, 1, "Mixto",            112000,  "Orientación sur, voladizos pasivos, ventilación cruzada. Sin necesidad de A/C.",                   "assets/branding/logo.png"),
    ("Timber XL 120",     120,  4, 2, 2, "Madera",           144000,  "4 dormitorios en dos plantas, terraza superior, estructura CLT certificada.",                      "assets/branding/logo.png"),
    ("Modular Familiar 110",110, 4, 3, 2, "Modular acero",   128000,  "4 dormitorios, 3 baños, garaje integrado. Instalación en 2 semanas.",                              "assets/branding/logo.png"),
    ("Premium Hormigón 130",130, 4, 3, 2, "Hormigón prefab", 154000,  "Paneles de hormigón arquitectónico. Máxima durabilidad y aislamiento acústico.",                  "assets/branding/logo.png"),
    ("Villa Modular 160",  160,  5, 3, 2, "Mixto",           194000,  "5 dormitorios, piscina opcional, domótica integrada. Villa de lujo prefabricada.",                 "assets/branding/logo.png"),
]


_PG_ALTER_MIGRATIONS = [
    # fincas_mls: columnas añadidas post-creación inicial
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS tipo_suelo TEXT DEFAULT 'Urbana'",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS servicios TEXT",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS forma_solar TEXT",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS orientacion TEXT",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS featured INTEGER DEFAULT 0",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS catastro_direccion TEXT",
    "ALTER TABLE fincas_mls ADD COLUMN IF NOT EXISTS catastro_municipio TEXT",
    "ALTER TABLE ai_projects ADD COLUMN IF NOT EXISTS req_json TEXT",
    # inmobiliarias: columnas trial 30 días
    "ALTER TABLE inmobiliarias ADD COLUMN IF NOT EXISTS trial_start_date TEXT DEFAULT NULL",
    "ALTER TABLE inmobiliarias ADD COLUMN IF NOT EXISTS trial_active INTEGER DEFAULT 0",
    "ALTER TABLE inmobiliarias ADD COLUMN IF NOT EXISTS trial_expired INTEGER DEFAULT 0",
]


def _run_postgres_migrations(conn) -> None:
    """Ejecuta todos los CREATE TABLE, índices y ALTER TABLE en PostgreSQL."""
    errors = []
    for sql in _PG_DDL:
        try:
            conn.execute(sql)
        except Exception as e:
            errors.append(f"DDL error: {e} | SQL: {sql[:60]}")
    for sql in _PG_INDEXES:
        try:
            conn.execute(sql)
        except Exception as e:
            errors.append(f"INDEX error: {e}")
    for sql in _PG_ALTER_MIGRATIONS:
        try:
            conn.execute(sql)
        except Exception as e:
            errors.append(f"ALTER error: {e} | SQL: {sql[:80]}")
    if errors:
        for err in errors:
            print(f"[PG migration] {err}")


def _ensure_tables_postgres():
    """
    Crea todas las tablas en PostgreSQL si no existen.
    Reutiliza _PG_DDL con adapt_sql() via _PostgresConnWrapper.
    """
    conn = get_conn()
    _run_postgres_migrations(conn)
    # Seed prefab_catalog si está vacía
    try:
        cur = conn.execute("SELECT COUNT(*) as n FROM prefab_catalog")
        row = cur.fetchone()
        count = row['n'] if row else 0
        if count == 0:
            conn.execute(
                "INSERT INTO prefab_catalog (name,m2,rooms,bathrooms,floors,material,price,description,image_path) VALUES (?,?,?,?,?,?,?,?,?)",
                _PG_PREFAB_SEED[0]
            )
            for seed_row in _PG_PREFAB_SEED[1:]:
                conn.execute(
                    "INSERT INTO prefab_catalog (name,m2,rooms,bathrooms,floors,material,price,description,image_path) VALUES (?,?,?,?,?,?,?,?,?)",
                    seed_row
                )
    except Exception as e:
        print(f"[PG seed] prefab_catalog: {e}")
    conn.commit()
    conn.close()


_tables_initialized = False


def ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    if DB_MODE == 'postgres':
        _ensure_tables_postgres()
        _tables_initialized = True
        return
    with transaction() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS plots (
            id TEXT PRIMARY KEY,
            title TEXT, description TEXT, lat REAL, lon REAL,
            m2 INTEGER, height REAL, price REAL, type TEXT, province TEXT,
            locality TEXT, owner_name TEXT, owner_email TEXT,
            image_path TEXT, registry_note_path TEXT, created_at TEXT
        )""")
        # Asegurar columna `province` en instalaciones antiguas y hacer COMMIT inmediato
        try:
            c.execute("ALTER TABLE plots ADD COLUMN province TEXT DEFAULT 'Madrid'")
            try:
                # Forzar commit inmediato para que índices posteriores no fallen
                conn_obj = c.connection
                conn_obj.commit()
            except Exception:
                pass
        except sqlite3.OperationalError:
            # Probablemente la columna ya existe
            pass
        except Exception:
            pass

        # Migración segura: agregar columnas nuevas si no existen
        try:
            c.execute("ALTER TABLE plots ADD COLUMN address TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN owner_phone TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN photo_paths TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN catastral_ref TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN services TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN status TEXT DEFAULT 'published'")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN plano_catastral_path TEXT")
        except Exception:
            pass  # Columna ya existe
        # CRÍTICO: Agregar columnas lat y lon si no existen
        try:
            c.execute("ALTER TABLE plots ADD COLUMN lat REAL")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN lon REAL")
        except Exception:
            pass  # Columna ya existe
        # Agregar otras columnas que puedan faltar
        try:
            c.execute("ALTER TABLE plots ADD COLUMN height REAL")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN locality TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN owner_name TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN image_path TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN registry_note_path TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN vertices_coordenadas TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN numero_parcela_principal TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN superficie_parcela REAL")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN superficie_edificable REAL")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN solar_virtual TEXT")
        except Exception:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE plots ADD COLUMN featured INTEGER DEFAULT 0")
        except Exception:
            pass  # ya existe
        c.execute("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            m2_construidos REAL,
            area_m2 REAL,
            price REAL,
            estimated_cost REAL,
            architect_name TEXT,
            max_height REAL,
            style TEXT,
            file_path TEXT,
            ocr_text TEXT,
            parsed_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Asegurar columna `characteristics_json` en la tabla projects (migración segura)
        try:
            c.execute("ALTER TABLE projects ADD COLUMN characteristics_json TEXT")
            try:
                conn_obj = c.connection
                conn_obj.commit()
            except Exception:
                pass
        except sqlite3.OperationalError:
            # La columna probablemente ya existe
            pass
        except Exception:
            pass
        # Asegurar columna `ocr_text` en la tabla projects (migración segura)
        try:
            c.execute("ALTER TABLE projects ADD COLUMN ocr_text TEXT")
        except Exception:
            pass  # Columna ya existe
        # Asegurar columna `parsed_data_json` en la tabla projects (migración segura)
        try:
            c.execute("ALTER TABLE projects ADD COLUMN parsed_data_json TEXT")
        except Exception:
            pass  # Columna ya existe
        c.execute("""CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            amount REAL, concept TEXT, buyer_name TEXT, buyer_email TEXT,
            buyer_phone TEXT, buyer_nif TEXT, method TEXT, status TEXT, timestamp TEXT,
            card_last4 TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT, email TEXT, phone TEXT, address TEXT, preferences TEXT, created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY,
            plot_id TEXT, buyer_name TEXT, buyer_email TEXT, amount REAL, kind TEXT, created_at TEXT,
            buyer_dni TEXT, buyer_domicilio TEXT, buyer_province TEXT
        )""")
        
        # Tablón de obras y ofertas de construcción
        c.execute("""CREATE TABLE IF NOT EXISTS project_tablon (
            id           TEXT PRIMARY KEY,
            client_email TEXT, client_name TEXT, project_name TEXT,
            province TEXT, style TEXT, total_area REAL, total_cost REAL,
            coste_m2 REAL, budget_json TEXT, created_at TEXT,
            active INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS construction_offers (
            id                TEXT PRIMARY KEY,
            tablon_id         TEXT, provider_id TEXT, provider_name TEXT,
            provider_email    TEXT, client_email TEXT, project_name TEXT,
            total_area        REAL, price_no_mat REAL, price_with_mat REAL,
            includes_materials INTEGER DEFAULT 0, plazo_semanas INTEGER,
            garantia_anos     INTEGER DEFAULT 5, nota_tecnica TEXT,
            breakdown_json    TEXT, estado TEXT DEFAULT 'enviada', created_at TEXT
        )""")

        # Tabla architects (arquitectos registrados)
        c.execute("""CREATE TABLE IF NOT EXISTS architects (
            id TEXT PRIMARY KEY,
            name TEXT, email TEXT UNIQUE, phone TEXT, company TEXT, nif TEXT,
            created_at TEXT
        )""")
        # Migraciones seguras: añadir columnas nuevas sin romper instalaciones previas
        for _mig_sql in [
            "ALTER TABLE architects ADD COLUMN proyectos_estudio_count INTEGER DEFAULT 0",
            "ALTER TABLE architects ADD COLUMN specialty TEXT",
            "ALTER TABLE architects ADD COLUMN address TEXT",
            "ALTER TABLE architects ADD COLUMN city TEXT",
            "ALTER TABLE architects ADD COLUMN province TEXT",
            "ALTER TABLE architects ADD COLUMN avg_project_price REAL",
            "ALTER TABLE architects ADD COLUMN origen_registro TEXT",
            "ALTER TABLE architects ADD COLUMN password_hash TEXT",
            "ALTER TABLE architects ADD COLUMN fee_pct REAL DEFAULT 8.0",
            "ALTER TABLE architects ADD COLUMN expenses_pct REAL DEFAULT 5.0",
            "ALTER TABLE architects ADD COLUMN iva_pct REAL DEFAULT 10.0",
            "ALTER TABLE plots ADD COLUMN tour_360_b64 TEXT",
            "ALTER TABLE plots ADD COLUMN buildable_m2 REAL",
            "ALTER TABLE plots ADD COLUMN ai_verification_cache TEXT",
            "ALTER TABLE reservations ADD COLUMN buyer_dni TEXT",
            "ALTER TABLE reservations ADD COLUMN buyer_domicilio TEXT",
            "ALTER TABLE reservations ADD COLUMN buyer_province TEXT",
        ]:
            try:
                c.execute(_mig_sql)
            except Exception:
                pass  # columna ya existe

        # Tabla ai_projects (proyectos del AI Designer pagados por clientes)
        c.execute("""CREATE TABLE IF NOT EXISTS ai_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_email TEXT,
            project_name TEXT,
            total_area REAL,
            total_cost REAL,
            services_json TEXT,
            style TEXT,
            energy_label TEXT,
            created_at TEXT,
            status TEXT,
            req_json TEXT
        )""")
        try:
            c.execute("ALTER TABLE ai_projects ADD COLUMN req_json TEXT")
        except Exception:
            pass  # columna ya existe

        # Tabla estudio_projects (proyectos generados en Modo Estudio por arquitectos)
        c.execute("""CREATE TABLE IF NOT EXISTS estudio_projects (
            id TEXT PRIMARY KEY,
            architect_id TEXT NOT NULL,
            catastral_ref TEXT,
            address TEXT,
            surface_m2 REAL,
            style TEXT,
            rooms INTEGER,
            budget REAL,
            total_cost REAL,
            zip_filename TEXT,
            stripe_session_id TEXT,
            paid INTEGER DEFAULT 0,
            created_at TEXT
        )""")

        # Tabla subscriptions (suscripciones de arquitectos)
        c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            architect_id TEXT,
            plan_type TEXT,
            price REAL,
            monthly_proposals_limit INTEGER,
            commission_rate REAL,
            status TEXT,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT
        )""")
        
        # Tabla visitas_demo (tracking de deep links y demos)
        c.execute("""CREATE TABLE IF NOT EXISTS visitas_demo (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            origen TEXT,
            nombre_usuario TEXT,
            accion_realizada TEXT,
            convirtio_a_registro INTEGER DEFAULT 0,
            session_id TEXT
        )""")

        # Tabla proposals (propuestas de arquitectos a propietarios)
        # Versión nueva simplificada (mantener compatibilidad con esquema anterior extenso)
        c.execute("""CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            architect_id TEXT,
            plot_id TEXT,
            proposal_text TEXT,
            estimated_budget REAL,
            deadline_days INTEGER,
            sketch_image_path TEXT,
            status TEXT,
            created_at TEXT,
            responded_at TEXT,
            delivery_format TEXT DEFAULT 'PDF',
            delivery_price REAL DEFAULT 1200,
            supervision_fee REAL DEFAULT 0,
            visa_fee REAL DEFAULT 0,
            total_cliente REAL DEFAULT 0,
            commission REAL DEFAULT 0,
            project_id TEXT
        )""")
        # Migraciones seguras para columnas nuevas usadas por nueva API insert_proposal
        try:
            c.execute("ALTER TABLE proposals ADD COLUMN message TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE proposals ADD COLUMN price REAL")
        except Exception:
            pass
        
        # Migración segura: agregar columnas nuevas a projects si no existen
        try:
            c.execute("ALTER TABLE projects ADD COLUMN architect_name TEXT")
        except Exception:
            pass

        try:
            c.execute("ALTER TABLE projects ADD COLUMN architect_id TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN m2_construidos INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN m2_parcela_minima INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN m2_parcela_maxima INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN habitaciones INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN banos INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN garaje INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN plantas INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN certificacion_energetica TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN tipo_proyecto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN foto_principal TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN galeria_fotos TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN modelo_3d_glb TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN planos_pdf TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN planos_dwg TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE projects ADD COLUMN memoria_pdf TEXT")
        except Exception:
            pass
        
        # Campos para matching y monetización
        try:
            c.execute("ALTER TABLE projects ADD COLUMN estimated_cost REAL")
        except sqlite3.OperationalError:
            pass  # Ya existe

        try:
            c.execute("ALTER TABLE projects ADD COLUMN price_memoria REAL DEFAULT 1800")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE projects ADD COLUMN price_cad REAL DEFAULT 2500")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE projects ADD COLUMN property_type TEXT DEFAULT 'residencial'")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE projects ADD COLUMN energy_rating TEXT")
        except sqlite3.OperationalError:
            pass

        try: 
            c.execute("ALTER TABLE projects ADD COLUMN vr_tour TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE projects ADD COLUMN is_active INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        # Índices para mejorar filtrado futuro (creación defensiva)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_plots_province ON plots(province)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_projects_style ON projects(style)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_projects_architect ON projects(architect_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_architect ON subscriptions(architect_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_proposals_plot ON proposals(plot_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_proposals_architect ON proposals(architect_id)")
        except Exception:
            pass
        # Índice único para email de clientes (si hay duplicados previos fallará, lo capturamos)
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_email ON clients(email)")
        except Exception:
            pass
        # Índices adicionales para acelerar búsquedas de reservas
        c.execute("CREATE INDEX IF NOT EXISTS idx_reservations_plot ON reservations(plot_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reservations_kind ON reservations(kind)")
        
        # Tabla additional_services (servicios post-proyecto: dirección obra, visados, modificaciones)
        c.execute("""CREATE TABLE IF NOT EXISTS additional_services (
            id TEXT PRIMARY KEY,
            proposal_id TEXT,
            client_id TEXT,
            architect_id TEXT,
            service_type TEXT,
            description TEXT,
            price REAL,
            commission REAL,
            total_cliente REAL,
            status TEXT,
            created_at TEXT,
            quoted_at TEXT,
            accepted_at TEXT,
            paid BOOLEAN DEFAULT 0
        )""")
        
        # Índices para servicios adicionales
        c.execute("CREATE INDEX IF NOT EXISTS idx_additional_services_client ON additional_services(client_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_additional_services_architect ON additional_services(architect_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_additional_services_proposal ON additional_services(proposal_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_additional_services_status ON additional_services(status)")

        # Compatibilidad con vistas y código legacy en español: crear tablas `proyectos` y `arquitectos`
        # usadas por las vistas del portal de arquitectos (migración segura).
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS arquitectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                email TEXT UNIQUE,
                telefono TEXT,
                especialidad TEXT,
                plan_id INTEGER,
                created_at TEXT
            )""")
        except Exception:
            pass

        try:
            c.execute("""CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arquitecto_id INTEGER,
                titulo TEXT,
                estilo TEXT,
                m2_construidos REAL,
                presupuesto_ejecucion REAL,
                m2_parcela_minima REAL,
                alturas INTEGER,
                pdf_path TEXT,
                created_at TEXT
            )""")
        except Exception:
            pass

        # Tabla client_interests (intereses de clientes en proyectos)
        c.execute("""CREATE TABLE IF NOT EXISTS client_interests (
            id TEXT PRIMARY KEY,
            email TEXT,
            project_id TEXT,
            created_at TEXT,
            FOREIGN KEY (email) REFERENCES clients(email),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )""")

        # Catálogo de casas prefabricadas
        c.execute("""CREATE TABLE IF NOT EXISTS prefab_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            m2 REAL NOT NULL,
            rooms INTEGER NOT NULL,
            bathrooms INTEGER NOT NULL,
            floors INTEGER NOT NULL,
            material TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image_path TEXT,
            active INTEGER DEFAULT 1
        )""")

        # Migraciones seguras: añadir columnas nuevas si no existen
        for _col, _typedef in [("modulos", "TEXT"), ("price_label", "TEXT"), ("image_paths", "TEXT")]:
            try:
                c.execute(f"ALTER TABLE prefab_catalog ADD COLUMN {_col} {_typedef}")
            except Exception:
                pass  # columna ya existe

        # Seed: insertar modelos de muestra solo si la tabla está vacía
        c.execute("SELECT COUNT(*) FROM prefab_catalog")
        if c.fetchone()[0] == 0:
            prefab_samples = [
                ("Studio Modular 45",  45,  1, 1, 1, "Modular acero",     44900,  "Vivienda compacta de acero modular, ideal para parcelas pequeñas. Certificación energética A.",          "assets/branding/logo.png"),
                ("Eco Timber 65",      65,  2, 1, 1, "Madera",            67500,  "Casa de madera laminada con aislamiento superior. Diseño nórdico, bajo mantenimiento.",                "assets/branding/logo.png"),
                ("Nordic Home 80",     80,  3, 1, 1, "Madera",            88000,  "3 dormitorios, salón abierto, porche cubierto. Clase energética A+.",                                  "assets/branding/logo.png"),
                ("Smart Compact 55",   55,  2, 1, 1, "Modular acero",     57500,  "Módulo doble con cocina integrada. Entrega en 90 días desde firma.",                                   "assets/branding/logo.png"),
                ("Green Container 60", 60,  2, 1, 1, "Contenedor",        51000,  "Dos contenedores HC interconectados, acabados premium, azotea transitable.",                           "assets/branding/logo.png"),
                ("Bioclimática 95",    95,  3, 2, 1, "Mixto",            112000,  "Orientación sur, voladizos pasivos, ventilación cruzada. Sin necesidad de A/C.",                      "assets/branding/logo.png"),
                ("Timber XL 120",     120,  4, 2, 2, "Madera",           144000,  "4 dormitorios en dos plantas, terraza superior, estructura CLT certificada.",                          "assets/branding/logo.png"),
                ("Modular Familiar 110",110, 4, 3, 2, "Modular acero",   128000,  "4 dormitorios, 3 baños, garaje integrado. Instalación en 2 semanas.",                                  "assets/branding/logo.png"),
                ("Premium Hormigón 130",130, 4, 3, 2, "Hormigón prefab", 154000,  "Paneles de hormigón arquitectónico. Máxima durabilidad y aislamiento acústico.",                      "assets/branding/logo.png"),
                ("Villa Modular 160",  160,  5, 3, 2, "Mixto",           194000,  "5 dormitorios, piscina opcional, domótica integrada. Villa de lujo prefabricada.",                    "assets/branding/logo.png"),
            ]
            c.executemany(
                "INSERT INTO prefab_catalog (name, m2, rooms, bathrooms, floors, material, price, description, image_path) VALUES (?,?,?,?,?,?,?,?,?)",
                prefab_samples
            )

        # ══════════════════════════════════════════════════════════════════════
        # ARCHIRAPID MLS — Tablas nuevas (nunca tocan tablas existentes)
        # Todas usan CREATE TABLE IF NOT EXISTS: idempotentes y seguras.
        # ══════════════════════════════════════════════════════════════════════

        # Tabla inmobiliarias (registro de agencias MLS)
        c.execute("""CREATE TABLE IF NOT EXISTS inmobiliarias (
            id               TEXT PRIMARY KEY,
            nombre           TEXT NOT NULL,
            cif              TEXT UNIQUE NOT NULL,
            email            TEXT UNIQUE NOT NULL,
            password_hash    TEXT NOT NULL,
            telefono         TEXT,
            web              TEXT,
            plan             TEXT DEFAULT 'starter',
            plan_activo      INTEGER DEFAULT 0,
            stripe_session_id TEXT,
            firma_hash       TEXT,
            firma_timestamp  TEXT,
            activa           INTEGER DEFAULT 0,
            ip_registro      TEXT,
            created_at       TEXT,
            trial_start_date TEXT DEFAULT NULL,
            trial_active     INTEGER DEFAULT 0,
            trial_expired    INTEGER DEFAULT 0
        )""")

        # Migraciones MLS: columnas extendidas de inmobiliarias (add-only, idempotentes)
        for _mls_col in [
            "ALTER TABLE inmobiliarias ADD COLUMN nombre_sociedad TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN nombre_comercial TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN telefono_secundario TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN telegram_contacto TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN direccion TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN localidad TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN provincia TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN codigo_postal TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN pais TEXT DEFAULT 'España'",
            "ALTER TABLE inmobiliarias ADD COLUMN contacto_nombre TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN contacto_cargo TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN contacto_email TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN contacto_telefono TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN contacto_telegram TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN factura_razon_social TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN factura_cif TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN factura_direccion TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN factura_email TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN iban TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN banco_nombre TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN banco_titular TEXT",
            "ALTER TABLE inmobiliarias ADD COLUMN email_login TEXT",
            # Trial 30 días
            "ALTER TABLE inmobiliarias ADD COLUMN trial_start_date TEXT DEFAULT NULL",
            "ALTER TABLE inmobiliarias ADD COLUMN trial_active INTEGER DEFAULT 0",
            "ALTER TABLE inmobiliarias ADD COLUMN trial_expired INTEGER DEFAULT 0",
        ]:
            try:
                c.execute(_mls_col)
            except Exception:
                pass  # columna ya existe — SQLite ignora silenciosamente

        # Tabla fincas_mls (fincas aportadas por inmobiliarias listantes)
        c.execute("""CREATE TABLE IF NOT EXISTS fincas_mls (
            id                        TEXT PRIMARY KEY,
            inmo_id                   TEXT NOT NULL,
            secuencial                INTEGER,
            ref_codigo                TEXT UNIQUE,
            catastro_ref              TEXT NOT NULL,
            catastro_validada         INTEGER DEFAULT 0,
            catastro_lat              REAL,
            catastro_lon              REAL,
            catastro_direccion        TEXT,
            catastro_municipio        TEXT,
            titulo                    TEXT,
            descripcion_publica       TEXT,
            notas_privadas            TEXT,
            precio                    REAL,
            superficie_m2             REAL,
            tipo_suelo                TEXT,
            servicios                 TEXT,
            forma_solar               TEXT,
            orientacion               TEXT,
            comision_total_pct        REAL,
            comision_archirapid_pct   REAL DEFAULT 1.0,
            comision_colaboradora_pct REAL,
            comision_listante_pct     REAL,
            split_aceptado            INTEGER DEFAULT 0,
            estado                    TEXT DEFAULT 'pendiente_validacion',
            image_paths               TEXT,
            precio_historial          TEXT,
            dias_en_mercado_inicio    TEXT,
            periodo_privado_expira    TEXT,
            created_at                TEXT,
            updated_at                TEXT
        )""")

        # Tabla reservas_mls (reservas 72h de colaboradoras sobre fincas MLS)
        c.execute("""CREATE TABLE IF NOT EXISTS reservas_mls (
            id                   TEXT PRIMARY KEY,
            finca_id             TEXT NOT NULL,
            inmo_colaboradora_id TEXT NOT NULL,
            stripe_session_id    TEXT,
            importe_reserva      REAL DEFAULT 200.0,
            estado               TEXT DEFAULT 'activa',
            timestamp_reserva    TEXT,
            timestamp_expira_72h TEXT,
            notas                TEXT
        )""")

        # Tabla firmas_colaboracion (firma digital eIDAS del acuerdo MLS)
        c.execute("""CREATE TABLE IF NOT EXISTS firmas_colaboracion (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            inmo_id           TEXT NOT NULL,
            documento_version TEXT DEFAULT '1.0',
            documento_hash    TEXT NOT NULL,
            firma_hash        TEXT NOT NULL,
            timestamp         TEXT NOT NULL,
            ip                TEXT,
            cif               TEXT
        )""")

        # Tabla notificaciones_mls (log de eventos para admin y portales)
        c.execute("""CREATE TABLE IF NOT EXISTS notificaciones_mls (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            destinatario_tipo TEXT,
            destinatario_id   TEXT,
            tipo_evento       TEXT,
            payload           TEXT,
            timestamp         TEXT,
            leida             INTEGER DEFAULT 0
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS leads_mls (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT NOT NULL,
            empresa    TEXT,
            email      TEXT NOT NULL,
            telefono   TEXT,
            num_fincas TEXT,
            mensaje    TEXT,
            origen     TEXT DEFAULT 'web',
            estado     TEXT DEFAULT 'nuevo',
            created_at TEXT
        )""")

        # Índices MLS (mejoran rendimiento sin afectar tablas existentes)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_inmobiliarias_email ON inmobiliarias(email)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_inmobiliarias_cif ON inmobiliarias(cif)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_fincas_mls_estado ON fincas_mls(estado)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_fincas_mls_inmo ON fincas_mls(inmo_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_reservas_mls_finca ON reservas_mls(finca_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_reservas_mls_estado ON reservas_mls(estado)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_firmas_inmo ON firmas_colaboracion(inmo_id)")
        except Exception:
            pass

        # ── Migraciones aditivas fincas_mls (safe ALTER TABLE) ───────────────
        _mls_migrations = [
            "ALTER TABLE fincas_mls ADD COLUMN tipo_suelo         TEXT DEFAULT 'Urbana'",
            "ALTER TABLE fincas_mls ADD COLUMN servicios          TEXT",
            "ALTER TABLE fincas_mls ADD COLUMN forma_solar        TEXT",
            "ALTER TABLE fincas_mls ADD COLUMN orientacion        TEXT",
            "ALTER TABLE fincas_mls ADD COLUMN featured           INTEGER DEFAULT 0",
            "ALTER TABLE fincas_mls ADD COLUMN catastro_direccion TEXT",
            "ALTER TABLE fincas_mls ADD COLUMN catastro_municipio TEXT",
        ]
        for _sql in _mls_migrations:
            try:
                c.execute(_sql)
            except Exception:
                pass  # columna ya existe → ignorar
    _tables_initialized = True


def insert_plot(data: Dict):
    ensure_tables()
    from datetime import datetime
    with transaction() as c:
        photo_paths = data.get("photo_paths")
        photo_paths_json = None
        image_path = data.get("image_path")

        # Normalizar photo_paths: lista -> JSON, string -> mantener
        if isinstance(photo_paths, list):
            import json as _json
            photo_paths_json = _json.dumps(photo_paths) if photo_paths else None
            # Si no hay image_path explícito, usar la primera foto
            if photo_paths and not image_path:
                image_path = photo_paths[0]
        elif isinstance(photo_paths, str):
            photo_paths_json = photo_paths

        # Si image_path sigue vacío pero viene en data, respetarlo
        if not image_path:
            image_path = data.get("image_path")

        # Aceptar tanto claves en español (FincaMVP) como en inglés (create_plot_record)
        _title    = data.get("titulo")    or data.get("title")
        _address  = data.get("direccion") or data.get("address")
        _province = data.get("provincia") or data.get("province")
        _price    = data.get("precio")    or data.get("price")
        _m2       = data.get("superficie_parcela") or data.get("m2")
        _cat_ref  = data.get("referencia_catastral") or data.get("catastral_ref")

        c.execute("""
            INSERT OR REPLACE INTO plots (
                id,
                title,
                address,
                province,
                locality,
                price,
                m2,
                superficie_parcela,
                superficie_edificable,
                lat,
                lon,
                solar_virtual,
                catastral_ref,
                plano_catastral_path,
                owner_name,
                owner_email,
                photo_paths,
                image_path,
                created_at,
                status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("id"),
            _title,
            _address,
            _province,
            _province,
            _price,
            _m2,
            _m2,
            data.get("superficie_edificable"),
            data.get("lat"),
            data.get("lon"),
            json.dumps(data.get("solar_virtual")) if data.get("solar_virtual") else None,
            _cat_ref,
            data.get("plano_catastral_path"),
            (data.get("propietario_nombre") or data.get("owner_name")),
            (data.get("propietario_email") or data.get("owner_email")),
            photo_paths_json,
            image_path,
            datetime.utcnow().isoformat(),
            "published"
        ))

def insert_project(data: Dict):
    """Inserta o reemplaza un proyecto en la tabla `projects` de forma flexible.

    La función detecta las columnas reales existentes en la tabla `projects`
    mediante `PRAGMA table_info(projects)`, filtra el diccionario `data`
    para quedarse solo con las claves que coinciden con columnas reales,
    y construye dinámicamente la sentencia `INSERT OR REPLACE`.

    Esto evita errores cuando el diccionario contiene claves que no existen
    en esquemas antiguos o reducidos.
    """
    ensure_tables()
    with transaction() as c:
        # Obtener columnas reales de la tabla projects
        c.execute("PRAGMA table_info(projects)")
        info = c.fetchall()
        real_cols = [row[1] for row in info] if info else []

        # Filtrar solo claves que existen como columnas
        filtered = {k: v for k, v in data.items() if k in real_cols}

        # Asegurar campos útiles por defecto si existen en la tabla
        from datetime import datetime
        if 'created_at' in real_cols and 'created_at' not in filtered:
            filtered['created_at'] = datetime.utcnow().isoformat()

        if 'id' in real_cols and 'id' not in filtered:
            import uuid
            filtered['id'] = f"p_{uuid.uuid4().hex}"

        if not filtered:
            # No hay columnas coincidentes; lanzar para que el llamador lo controle
            raise ValueError('No hay columnas válidas para insertar en projects')

        cols_sql = ','.join(filtered.keys())
        placeholders = ','.join(['?'] * len(filtered))
        values = tuple(filtered[k] for k in filtered.keys())

        c.execute(f"INSERT OR REPLACE INTO projects ({cols_sql}) VALUES ({placeholders})", values)

        # Registro observable
        try:
            from src.logger import log
            log('project_created', project_id=filtered.get('id'), architect_id=filtered.get('architect_id'), title=filtered.get('title'))
        except Exception:
            pass

def insert_payment(data: Dict):
    ensure_tables()
    with transaction() as c:
        c.execute("""INSERT OR REPLACE INTO payments (
            payment_id,amount,concept,buyer_name,buyer_email,buyer_phone,buyer_nif,method,status,timestamp,card_last4
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (data['payment_id'], data['amount'], data['concept'], data['buyer_name'], data['buyer_email'],
         data['buyer_phone'], data['buyer_nif'], data['method'], data['status'], data['timestamp'], data.get('card_last4')))

@st.cache_data(ttl=60)
def get_all_plots():
    ensure_tables(); conn = get_conn(); import pandas as pd
    try:
        df = pd.read_sql_query('SELECT * FROM plots', conn)
    finally:
        conn.close()
    return df

def get_plots_by_owner(email: str):
    ensure_tables()
    conn = get_conn()
    import pandas as pd
    try:
        # Usamos parameter binding para seguridad
        df = pd.read_sql_query('SELECT * FROM plots WHERE owner_email = ?', conn, params=(email,))
    finally:
        conn.close()
    return df


def list_fincas_filtradas(provincia: Optional[str], min_surface: float, max_surface: Optional[float]) -> list:
    """
    Devuelve fincas filtradas por superficie y provincia.
    Usa las columnas reales del esquema actual:
    - superficie_parcela
    - m2
    - province
    """

    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Usar superficie_parcela como columna principal
        area_col = "superficie_parcela"

        sql = f"SELECT * FROM plots WHERE COALESCE({area_col}, 0) >= ?"
        params = [min_surface]

        # Filtro por superficie máxima
        if max_surface is not None and float(max_surface) > 0:
            sql += f" AND COALESCE({area_col}, 0) <= ?"
            params.append(float(max_surface))

        # Filtro por provincia real
        if provincia and provincia not in ("", "Todas"):
            sql += " AND province = ?"
            params.append(provincia)

        sql += f" ORDER BY COALESCE({area_col}, 0) ASC"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []

        return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]

    finally:
        conn.close()

@st.cache_data(ttl=60)
def get_all_projects():
    ensure_tables(); conn = get_conn(); import pandas as pd
    try:
        df = pd.read_sql_query('SELECT * FROM projects', conn)
    finally:
        conn.close()
    return df

def list_proyectos(filtros: dict | None = None):
    """
    Devuelve una lista de proyectos como lista de diccionarios,
    aplicando filtros simples sobre el DataFrame de get_all_projects().
    """
    df = get_all_projects()
    if filtros:
        for campo, valor in filtros.items():
            if campo in df.columns:
                df = df[df[campo] == valor]
    # devolver como lista de dicts
    return df.to_dict(orient="records")

def insert_architect(data: Dict):
    """Inserta o reemplaza un arquitecto."""
    ensure_tables()
    with transaction() as c:
        c.execute("""INSERT OR REPLACE INTO architects (
            id,name,email,phone,company,nif,created_at
        ) VALUES (?,?,?,?,?,?,?)""", (
            data['id'], data['name'], data['email'], data.get('phone'), data.get('company'), data.get('nif'), data['created_at']
        ))


def guardar_nuevo_arquitecto(nombre: str, email: str, telefono: str, especialidad: str, plan_id: int) -> bool:
    """Guarda un nuevo arquitecto en la tabla `arquitectos`.

    Devuelve True si la inserción fue exitosa, False en caso contrario (por ejemplo, email duplicado).
    """
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Asegurar existencia de la tabla `arquitectos` compatible con db_setup
        cur.execute("""
        CREATE TABLE IF NOT EXISTS arquitectos (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            email TEXT UNIQUE,
            telefono TEXT,
            especialidad TEXT,
            plan_id INTEGER
        )
        """)
        cur.execute("INSERT INTO arquitectos (nombre,email,telefono,especialidad,plan_id) VALUES (?,?,?,?,?)",
                    (nombre, email, telefono, especialidad, plan_id))
        conn.commit()
        return True
    except Exception as e:
        # No propagamos error, devolvemos False para que la UI lo gestione
        try:
            print('guardar_nuevo_arquitecto error:', e)
        except Exception:
            pass
        return False
    finally:
        conn.close()


def obtener_todos_los_planes() -> list:
    """Recupera todos los planes desde la tabla `planes`.

    Retorna una lista de dicts con keys: `id`, `nombre_plan`, `precio_mensual`, `limite_proyectos`.
    """
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Asegurar existencia de la tabla `planes` (compatibilidad)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS planes (
            id INTEGER PRIMARY KEY,
            nombre_plan TEXT,
            precio_mensual REAL,
            limite_proyectos INTEGER
        )
        """)
        conn.commit()
        cur.execute("SELECT id,nombre_plan,precio_mensual,limite_proyectos FROM planes ORDER BY id")
        rows = cur.fetchall()
        # sqlite3.Row es mapeable a dict
        return [dict(r) for r in rows]
    finally:
        conn.close()


def obtener_datos_arquitecto(email: str):
    """Recupera datos básicos de un arquitecto por su email.

    Retorna un diccionario con keys: `id`, `nombre`, `plan_id` si se encuentra.
    Si no existe, devuelve `None`.
    """
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Asegurar existencia de la tabla `arquitectos` (compatibilidad con otras partes del código)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS arquitectos (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            email TEXT UNIQUE,
            telefono TEXT,
            especialidad TEXT,
            plan_id INTEGER
        )
        """)
        conn.commit()

        cur.execute("SELECT id, nombre, plan_id FROM arquitectos WHERE LOWER(email)=LOWER(?) LIMIT 1", (email.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        # row puede ser sqlite3.Row o tupla
        try:
            return {"id": row[0], "nombre": row[1], "plan_id": row[2]}
        except Exception:
            # Si es sqlite3.Row con keys
            return {"id": row['id'], "nombre": row['nombre'], "plan_id": row.get('plan_id')}
    except Exception as e:
        try:
            print('obtener_datos_arquitecto error:', e)
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

def update_project_architect_id(project_id: str, architect_id: str):
    """Actualiza el arquitecto asociado a un proyecto."""
    ensure_tables()
    with transaction() as c:
        c.execute("UPDATE projects SET architect_id=? WHERE id=?", (architect_id, project_id))


def update_project_fields(project_id: str, fields: Dict):
    """Actualizar campos concretos de un proyecto.

    Sólo actualiza las columnas proporcionadas en `fields`.
    """
    if not fields:
        return
    ensure_tables()
    allowed = {
        'title','architect_name','architect_id','area_m2','max_height','style','price','file_path','description',
        'm2_construidos','m2_parcela_minima','m2_parcela_maxima','habitaciones','banos','garaje','plantas','certificacion_energetica',
        'tipo_proyecto','foto_principal','galeria_fotos','modelo_3d_glb','render_vr','planos_pdf','planos_dwg','memoria_pdf'
    }
    set_pairs = []
    values = []
    for k, v in fields.items():
        if k in allowed:
            set_pairs.append(f"{k}=?")
            values.append(v)
    if not set_pairs:
        return
    values.append(project_id)
    sql = f"UPDATE projects SET {', '.join(set_pairs)} WHERE id=?"
    with transaction() as c:
        c.execute(sql, tuple(values))


def guardar_nuevo_proyecto(arquitecto_id: int, titulo: str, estilo: str, m2_construidos: float,
                          presupuesto_ejecucion: float, m2_parcela_minima: float, alturas: int, pdf_path: str) -> bool:
    """Inserta un nuevo proyecto en la tabla `proyectos`.

    Devuelve True si la inserción fue exitosa, False en caso de error.
    """
    ensure_tables()
    try:
        with transaction() as c:
            c.execute("""INSERT INTO proyectos (
                arquitecto_id, titulo, estilo, m2_construidos, presupuesto_ejecucion,
                m2_parcela_minima, alturas, pdf_path
            ) VALUES (?,?,?,?,?,?,?,?)""",
                      (arquitecto_id, titulo, estilo, m2_construidos, presupuesto_ejecucion,
                       m2_parcela_minima, alturas, pdf_path))
        return True
    except Exception as e:
        try:
            print('guardar_nuevo_proyecto error:', e)
        except Exception:
            pass
        return False


def verificar_limite_proyectos(arquitecto_id: int) -> bool:
    """Verifica si el arquitecto con id `arquitecto_id` aún puede crear nuevos proyectos.

    Lógica:
      - Obtener `plan_id` desde la tabla `arquitectos`.
      - Obtener `limite_proyectos` desde la tabla `planes` para ese plan.
      - Contar proyectos en la tabla `proyectos` asociados a `arquitecto_id`.
    Devuelve True si contador < limite, False si alcanzó o superó el límite.
    """
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Obtener plan del arquitecto
        cur.execute("SELECT plan_id FROM arquitectos WHERE id = ?", (arquitecto_id,))
        row = cur.fetchone()
        if not row:
            # Si no existe el arquitecto asumimos permitido (o gestionar upstream)
            return True
        plan_id = row['plan_id'] if isinstance(row, sqlite3.Row) and 'plan_id' in row.keys() else row[0]

        # Obtener límite del plan
        cur.execute("SELECT limite_proyectos FROM planes WHERE id = ?", (plan_id,))
        p = cur.fetchone()
        if not p:
            # Si no existe el plan, no imponemos límite
            return True
        limite = p['limite_proyectos'] if isinstance(p, sqlite3.Row) and 'limite_proyectos' in p.keys() else p[0]

        # Contar proyectos existentes para el arquitecto
        cur.execute("SELECT COUNT(1) as cnt FROM proyectos WHERE arquitecto_id = ?", (arquitecto_id,))
        cnt_row = cur.fetchone()
        cnt = cnt_row['cnt'] if isinstance(cnt_row, sqlite3.Row) and 'cnt' in cnt_row.keys() else cnt_row[0]

        try:
            return int(cnt) < int(limite)
        except Exception:
            return True
    finally:
        conn.close()

def get_plot_by_id(pid: str) -> Optional[Dict]:
    ensure_tables(); conn = get_conn(); c = conn.cursor(); c.execute('SELECT * FROM plots WHERE id=?', (pid,))
    row = c.fetchone(); conn.close()
    if not row:
        return None
    # Gracias a row_factory podemos acceder por nombre
    return {k: row[k] for k in row.keys()}

    """Devuelve proyectos destacados (por defecto los últimos `limit` publicados).
    Cada proyecto es un dict con campos: id,title,area_m2,price,foto_principal,description
    """
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Return all available columns so the UI can access mirrored fields
        cur.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        out = []
        for r in rows:
            out.append({cols[i]: r[i] for i in range(len(cols))})
        return out
    finally:
        conn.close()

def counts() -> Dict[str,int]:
    ensure_tables(); conn = get_conn(); c = conn.cursor()
    out = {}
    for table in ['plots','projects','payments']:
        c.execute(f'SELECT COUNT(*) FROM {table}'); out[table] = c.fetchone()[0]
    conn.close(); return out

def insert_proposal(data: Dict):
    """Inserta propuesta en la tabla proposals."""
    ensure_tables()
    with transaction() as c:
        # Detectar si columnas message/price existen (compatibilidad con esquema anterior)
        has_message = True
        has_price = True
        try:
            c.execute("SELECT message FROM proposals LIMIT 1")
        except Exception:
            has_message = False
        try:
            c.execute("SELECT price FROM proposals LIMIT 1")
        except Exception:
            has_price = False
        if has_message and has_price:
            c.execute("""INSERT OR REPLACE INTO proposals (
                id,plot_id,architect_id,project_id,message,price,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?)""", (
                data['id'], data['plot_id'], data['architect_id'], data.get('project_id'), data.get('message'),
                data.get('price'), data.get('status','pending'), data['created_at']
            ))
        else:
            # Insert en columnas legacy (proposal_text, estimated_budget) mapeando valores
            c.execute("""INSERT OR REPLACE INTO proposals (
                id,architect_id,plot_id,proposal_text,estimated_budget,deadline_days,sketch_image_path,status,created_at,project_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                data['id'], data['architect_id'], data['plot_id'], data.get('message'), data.get('price'),
                data.get('deadline_days', 30), None, data.get('status','pending'), data['created_at'], data.get('project_id')
            ))

def get_proposals_for_plot(plot_id: str):
    ensure_tables(); conn = get_conn(); import pandas as pd
    try:
        df = pd.read_sql_query('SELECT * FROM proposals WHERE plot_id = ?', conn, params=(plot_id,))
    finally:
        conn.close()
    return df

def update_proposal_status(proposal_id: str, new_status: str):
    """Actualiza el estado de una propuesta (pending->accepted/rejected)."""
    ensure_tables()
    with transaction() as c:
        # Asegurar columna responded_at (legacy ya la tiene, pero migración defensiva)
        try:
            c.execute("ALTER TABLE proposals ADD COLUMN responded_at TEXT")
        except Exception:
            pass
        from datetime import datetime
        responded_at = datetime.utcnow().isoformat()
        try:
            c.execute("UPDATE proposals SET status=?, responded_at=? WHERE id=?", (new_status, responded_at, proposal_id))
        except Exception:
            # Si no existe responded_at, degradar sin timestamp
            c.execute("UPDATE proposals SET status=? WHERE id=?", (new_status, proposal_id))

def get_proposals_for_owner(owner_email: str):
    """Obtiene todas las propuestas recibidas por un propietario."""
    ensure_tables()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                pr.id, pr.message, pr.price, pr.status, pr.created_at,
                pl.id as plot_id, pl.title as plot_title,
                a.id as architect_id, a.name as architect_name, a.company as architect_company,
                pj.id as project_id, pj.title as project_title
            FROM proposals pr
            JOIN plots pl ON pr.plot_id = pl.id
            JOIN architects a ON pr.architect_id = a.id
            LEFT JOIN projects pj ON pr.project_id = pj.id
            WHERE pl.owner_email = ?
            ORDER BY pr.created_at DESC
        """, (owner_email,))
        rows = cur.fetchall()
        # Convert to list of dicts
        cols = [d[0] for d in cur.description]
        return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]
    finally:
        conn.close()


# Cache ligera en memoria para counts (TTL segundos)
_COUNTS_CACHE: Dict[str,int] | None = None
_COUNTS_TS: float | None = None
_COUNTS_TTL = 5  # segundos

def cached_counts() -> Dict[str,int]:
    import time
    global _COUNTS_CACHE, _COUNTS_TS
    now = time.time()
    if _COUNTS_CACHE is None or _COUNTS_TS is None or (now - _COUNTS_TS) > _COUNTS_TTL:
        _COUNTS_CACHE = counts()
        _COUNTS_TS = now
    return _COUNTS_CACHE.copy()


# =====================================================
# SERVICIOS ADICIONALES (Post-Proyecto)
# =====================================================

def insert_additional_service(data: Dict):
    """Inserta un nuevo servicio adicional solicitado por cliente."""
    ensure_tables()
    with transaction() as c:
        c.execute("""INSERT INTO additional_services (
            id, proposal_id, client_id, architect_id, service_type, 
            description, price, commission, total_cliente, status, created_at, paid
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            data['id'], data.get('proposal_id'), data['client_id'], data['architect_id'],
            data['service_type'], data.get('description', ''), 
            data.get('price', 0), data.get('commission', 0), data.get('total_cliente', 0),
            data.get('status', 'solicitado'), data['created_at'], data.get('paid', 0)
        ))

def get_additional_services_by_client(client_id: str):
    """Obtiene todos los servicios adicionales de un cliente."""
    ensure_tables()
    conn = get_conn()
    import pandas as pd
    try:
        df = pd.read_sql_query("""
            SELECT s.*, a.name as architect_name, a.email as architect_email
            FROM additional_services s
            LEFT JOIN architects a ON s.architect_id = a.id
            WHERE s.client_id = ?
            ORDER BY s.created_at DESC
        """, conn, params=(client_id,))
    finally:
        conn.close()
    return df

def get_additional_services_by_architect(architect_id: str):
    """Obtiene todos los servicios adicionales para un arquitecto."""
    ensure_tables()
    conn = get_conn()
    import pandas as pd
    try:
        df = pd.read_sql_query("""
            SELECT s.*, c.name as client_name, c.email as client_email
            FROM additional_services s
            LEFT JOIN clients c ON s.client_id = c.id
            WHERE s.architect_id = ?
            ORDER BY s.created_at DESC
        """, conn, params=(architect_id,))
    finally:
        conn.close()
    return df

def update_additional_service_quote(service_id: str, price: float, commission_rate: float):
    """Arquitecto cotiza un servicio adicional (estado: solicitado -> cotizado)."""
    ensure_tables()
    commission = price * commission_rate
    total_cliente = price + commission
    
    with transaction() as c:
        from datetime import datetime
        quoted_at = datetime.utcnow().isoformat()
        c.execute("""UPDATE additional_services 
                     SET price=?, commission=?, total_cliente=?, status='cotizado', quoted_at=?
                     WHERE id=?""", 
                  (price, commission, total_cliente, quoted_at, service_id))

def update_additional_service_status(service_id: str, new_status: str):
    """Actualiza estado de servicio adicional (cotizado -> aceptado/rechazado)."""
    ensure_tables()
    with transaction() as c:
        from datetime import datetime
        if new_status == 'aceptado':
            accepted_at = datetime.utcnow().isoformat()
            c.execute("UPDATE additional_services SET status=?, accepted_at=? WHERE id=?", 
                      (new_status, accepted_at, service_id))
        else:
            c.execute("UPDATE additional_services SET status=? WHERE id=?", (new_status, service_id))

def mark_additional_service_paid(service_id: str):
    """Marca servicio adicional como pagado."""
    ensure_tables()
    with transaction() as c:
        c.execute("UPDATE additional_services SET paid=1 WHERE id=?", (service_id,))


def registrar_venta_proyecto(proyecto_id: int, cliente_email: str, tipo_compra: str, precio_base: float) -> float:
    """Registra la venta de un proyecto, calcula la comisión (10%) y guarda la transacción.

    Retorna la comision_archirapid calculada.
    """
    ensure_tables()
    comision = float(precio_base) * 0.10
    from datetime import datetime
    fecha = datetime.utcnow().isoformat()
    try:
        with transaction() as c:
            # Insertar transacción
            c.execute("""INSERT INTO ventas_proyectos (
                proyecto_id, cliente_email, tipo_compra, precio_venta, comision_archirapid, fecha
            ) VALUES (?,?,?,?,?,?)""",
                      (proyecto_id, cliente_email, tipo_compra, precio_base, comision, fecha))
        return comision
    except Exception as e:
        try:
            print('registrar_venta_proyecto error:', e)
        except Exception:
            pass
        return 0.0


def list_proyectos_compatibles(finca_surface_m2: float) -> list:
    """Devuelve proyectos cuya área construida (`m2_construidos`) es <= 33% de la superficie de la finca.

    Parámetros:
      - finca_surface_m2: superficie total de la parcela en m²

    Retorna una lista de dicts con los campos de la tabla `proyectos`.
    """
    ensure_tables()
    max_built_area = (finca_surface_m2 or 0) * 0.33
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM proyectos WHERE m2_construidos <= ? ORDER BY m2_construidos ASC", (max_built_area,))
        rows = cur.fetchall()
        out = []
        if rows:
            cols = [d[0] for d in cur.description]
            for r in rows:
                out.append({cols[i]: r[i] for i in range(len(cols))})
        return out
    finally:
        conn.close()


def get_featured_projects(limit=6):
    """
    Obtiene proyectos arquitectónicos destacados de la base de datos. 
    
    Args:
        limit (int): Número máximo de proyectos a retornar
        
    Returns:
        list: Lista de diccionarios con datos de proyectos
    """
    ensure_tables()
    conn = get_conn()
    try:
        cursor = conn.cursor()
        
        # Consulta SQL para obtener proyectos
        query = """
        SELECT 
            id,
            title,
            description,
            area_m2,
            price,
            foto_principal,
            galeria_fotos,
            created_at
        FROM projects
        ORDER BY created_at DESC
        LIMIT ?
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        projects = []
        for row in rows:
            # Procesar galeria_fotos si es JSON
            galeria = []
            if row['galeria_fotos']:
                try:
                    galeria = json.loads(row['galeria_fotos']) if isinstance(row['galeria_fotos'], str) else []
                except:
                    galeria = [row['galeria_fotos']] if row['galeria_fotos'] else []
            
            # Construir lista de fotos: principal + galería
            fotos = []
            if row['foto_principal']:
                fotos.append(row['foto_principal'])
            fotos.extend(galeria)
            
            project = {
                'id': row['id'],
                'title': row['title'],
                'description': row['description'],
                'architect_name': '',  # No existe en la tabla actual
                'company': '',  # No existe en la tabla
                'price': row['price'],
                'area_m2': row['area_m2'],
                'files': {'fotos': fotos},
                'characteristics': {},  # No existe en la tabla actual
                'created_at': row['created_at']
            }
            projects.append(project)
        
        print(f"DEBUG: get_featured_projects returning {len(projects)} projects")
        for p in projects:
            print(f"  Project {p['id']}: files = {p.get('files', 'NO FILES')}")
        return projects
        
    except Exception as e:
        print(f"Error obteniendo proyectos destacados: {e}")
        return []
    finally:
        conn.close()


def get_project_by_id(project_id: str):
    """
    Obtiene un proyecto específico por su ID.
    
    Args:
        project_id (str): ID del proyecto a buscar
        
    Returns:
        dict: Diccionario con datos del proyecto o None si no existe
    """
    ensure_tables()
    conn = get_conn()
    try:
        cursor = conn.cursor()
        
        # Consulta SQL para obtener el proyecto
        query = """
        SELECT 
            id,
            title,
            description,
            area_m2,
            price,
            foto_principal,
            galeria_fotos,
            created_at
        FROM projects
        WHERE id = ?
        """
        
        cursor.execute(query, (project_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Procesar galeria_fotos si es JSON
        galeria = []
        if row['galeria_fotos']:
            try:
                galeria = json.loads(row['galeria_fotos']) if isinstance(row['galeria_fotos'], str) else []
            except:
                galeria = [row['galeria_fotos']] if row['galeria_fotos'] else []
        
        # Construir lista de fotos: principal + galería
        fotos = []
        if row['foto_principal']:
            fotos.append(row['foto_principal'])
        fotos.extend(galeria)
        
        project = {
            'id': row['id'],
            'title': row['title'],
            'description': row['description'],
            'architect_name': '',  # No existe en la tabla actual
            'company': '',  # No existe en la tabla
            'price': row['price'],
            'area_m2': row['area_m2'],
            'files': {'fotos': fotos},
            'characteristics': {},  # No existe en la tabla actual
            'created_at': row['created_at']
        }
        
        return project
        
    except Exception as e:
        print(f"Error obteniendo proyecto {project_id}: {e}")
        return None
    finally:
        conn.close()
