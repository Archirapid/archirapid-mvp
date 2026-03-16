"""Base de datos centralizada para ArchiRapid (SQLite)."""
from __future__ import annotations
import os
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Iterator

BASE_PATH = Path.cwd()
# Use a fixed absolute database path to ensure all modules use the same DB file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.db")

def get_conn():
    """Devuelve conexión SQLite con row_factory habilitado para acceder por nombre de columna.

    Usa `DB_PATH` absoluto para evitar confusión entre rutas relativas.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

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

def ensure_tables():
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
            plot_id TEXT, buyer_name TEXT, buyer_email TEXT, amount REAL, kind TEXT, created_at TEXT
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
            "ALTER TABLE plots ADD COLUMN tour_360_b64 TEXT",
            "ALTER TABLE plots ADD COLUMN buildable_m2 REAL",
            "ALTER TABLE plots ADD COLUMN ai_verification_cache TEXT",
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
            status TEXT
        )""")

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
