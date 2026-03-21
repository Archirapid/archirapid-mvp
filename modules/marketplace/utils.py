# modules/marketplace/utils.py
import os, uuid, json
from pathlib import Path
import sqlite3
from datetime import datetime

BASE = Path.cwd()
UPLOADS = BASE / "uploads"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database.db")
UPLOADS.mkdir(parents=True, exist_ok=True)

def save_upload(uploaded_file, prefix="file"):
    # uploaded_file: Streamlit UploadedFile or werkzeug FileStorage (for API)
    ext = Path(uploaded_file.name).suffix if hasattr(uploaded_file, "name") else ".bin"
    fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
    dest = UPLOADS / fname
    # if streamlit file-like
    try:
        with open(dest, "wb") as f:
            f.write(uploaded_file.getbuffer())
    except Exception:
        # werkzeug or other
        uploaded_file.save(str(dest))
    return str(Path("uploads") / fname)  # ruta relativa para uso en st.image y DB

def db_conn():
    """Devuelve conexión a BD. En producción (Supabase) usa get_conn() de src.db."""
    try:
        from src.db import get_conn, DB_MODE
        if DB_MODE == 'postgres':
            return get_conn()
    except Exception:
        pass
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def insert_user(user):
    conn = db_conn(); c=conn.cursor()
    # Support for architects table
    if user.get("role") == "architect":
        c.execute("SELECT id FROM architects WHERE email=?", (user['email'],))
        if not c.fetchone():
            c.execute("""INSERT INTO architects
                         (id,name,email,company,phone,nif,specialty,address,city,province,
                          avg_project_price,origen_registro,password_hash,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (user["id"], user["name"], user["email"],
                       user.get("company", user.get("name", "")),
                       user.get("phone", ""),
                       user.get("nif", ""),
                       user.get("specialty", ""),
                       user.get("address", ""),
                       user.get("city", ""),
                       user.get("province", ""),
                       user.get("avg_project_price", None),
                       user.get("origen_registro", None),
                       user.get("password_hash", None),
                       datetime.utcnow().isoformat()))
        else:
            # Actualizar campos si el arquitecto ya existe
            update_fields = [
                "phone=COALESCE(NULLIF(?,''),phone)",
                "specialty=COALESCE(NULLIF(?,''),specialty)",
                "address=COALESCE(NULLIF(?,''),address)",
                "city=COALESCE(NULLIF(?,''),city)",
                "province=COALESCE(NULLIF(?,''),province)",
                "avg_project_price=COALESCE(?,avg_project_price)",
            ]
            params = [user.get("phone",""), user.get("specialty",""),
                      user.get("address",""), user.get("city",""),
                      user.get("province",""), user.get("avg_project_price")]
            # Solo actualizar password si se proporciona uno nuevo
            if user.get("password_hash"):
                update_fields.append("password_hash=?")
                params.append(user["password_hash"])
            params.append(user["email"])
            c.execute(f"UPDATE architects SET {', '.join(update_fields)} WHERE email=?", params)
    elif user.get("role") == "owner":
        c.execute("SELECT id FROM owners WHERE email=?", (user['email'],))
        if not c.fetchone():
            c.execute("INSERT INTO owners (id,name,email,phone,address,created_at) VALUES (?,?,?,?,?,?)",
                      (user["id"], user["name"], user["email"], user.get("phone",""), user.get("address",""), datetime.utcnow().isoformat()))
    elif user.get("role") == "services":
        c.execute("SELECT id FROM service_providers WHERE email=?", (user['email'],))
        if not c.fetchone():
            c.execute("INSERT INTO service_providers (id,name,email,company,phone,address,created_at) VALUES (?,?,?,?,?,?,?)",
                      (user["id"], user["name"], user["email"], user.get("company",""), user.get("phone",""), user.get("address",""), datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def get_user_by_email(email):
    conn = db_conn(); c=conn.cursor()
    # Check users table first (new unified table)
    c.execute("SELECT id, name, email, role FROM users WHERE email=?", (email,))
    row = c.fetchone()
    if row:
        conn.close()
        return {"id": row[0], "name": row[1], "email": row[2], "role": row[3]}
    # Check architects table
    c.execute("SELECT id, name, email, company FROM architects WHERE email=?", (email,))
    row = c.fetchone()
    if row:
        conn.close()
        return {"id": row[0], "name": row[1], "email": row[2], "company": row[3], "role": "architect"}
    # Check owners table with phone and address
    c.execute("SELECT id, name, email, phone, address FROM owners WHERE email=?", (email,))
    row = c.fetchone()
    if row:
        conn.close()
        return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "address": row[4], "role": "owner"}
    # Check service_providers table
    c.execute("SELECT id, name, email, company, specialty FROM service_providers WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "email": row[2], "company": row[3], "specialty": row[4], "role": "services"}
    return None

def list_projects():
    conn = db_conn(); c=conn.cursor()
    # Join with architects table instead of users
    c.execute("""
        SELECT p.id, p.title, p.description, p.area_m2, p.price, p.foto_principal, p.galeria_fotos, p.created_at,
               a.name as architect_name, a.company
        FROM projects p
        LEFT JOIN architects a ON p.architect_id = a.id
        ORDER BY p.created_at DESC
    """)
    rows = c.fetchall(); conn.close()
    cols = ["id","title","description","area_m2","price","foto_principal","galeria_fotos","created_at","architect_name","company"]
    projects = [dict(zip(cols,r)) for r in rows]
    # galeria_fotos puede ser None o JSON
    for proj in projects:
        if proj['galeria_fotos']:
            try:
                proj['galeria_fotos'] = json.loads(proj['galeria_fotos'])
            except Exception:
                proj['galeria_fotos'] = []
        else:
            proj['galeria_fotos'] = []
    return projects

def create_plot_record(plot):
    from datetime import datetime
    from src import db

    data = {
        "id": plot.get("id"),
        "title": plot.get("title"),
        "description": plot.get("description", "") or plot.get("title", ""),
        "lat": plot.get("lat"),  # CRÍTICO: debe estar presente
        "lon": plot.get("lon"),  # CRÍTICO: debe estar presente
        "m2": plot.get("surface_m2") or plot.get("m2") or 0,
        "height": plot.get("height") or plot.get("max_height") or None,
        "price": plot.get("price") or 0.0,
        "type": plot.get("finca_type") or plot.get("type") or "Urbano",
        "province": plot.get("province") or "",
        "locality": plot.get("locality") or "",
        "owner_name": plot.get("owner_name") or plot.get("owner") or "",
        "owner_email": plot.get("owner_email") or "",
        "owner_phone": plot.get("owner_phone") or "",
        "image_path": None,
        "registry_note_path": plot.get("registry_note_path") or None,
        "address": plot.get("owner_address") or plot.get("address") or plot.get("plot_address") or "",
        "created_at": plot.get("created_at") or datetime.utcnow().isoformat(),
        "photo_paths": None,
        "catastral_ref": plot.get("catastral_ref") or None,
        "services": plot.get("services") or None,
        "status": plot.get("status") or "published",
        "plano_catastral_path": plot.get("plano_catastral_path") or None,
        "vertices_coordenadas": plot.get("vertices_coordenadas") or None,
        "numero_parcela_principal": plot.get("numero_parcela_principal") or None,
    }

    # Normalize photo_paths and set image_path to first photo if available
    photo_paths = plot.get("photo_paths")
    if isinstance(photo_paths, list):
        data["photo_paths"] = json.dumps(photo_paths) if photo_paths else None
        data["image_path"] = photo_paths[0] if len(photo_paths) > 0 else None
    elif isinstance(photo_paths, str):
        # Si es JSON string, dejarlo como está; si es delimitado por ;, convertirlo a JSON
        try:
            json.loads(photo_paths)  # Verificar si ya es JSON válido
            data["photo_paths"] = photo_paths
        except (json.JSONDecodeError, TypeError):
            # Si no es JSON, asumir que es delimitado por ;
            parts = [p.strip() for p in photo_paths.split(";") if p.strip()]
            data["photo_paths"] = json.dumps(parts) if parts else None
            data["image_path"] = parts[0] if parts else (plot.get("image_path") or None)
    else:
        # fallback to any single image field present
        data["photo_paths"] = None
        data["image_path"] = plot.get("image_path") or plot.get("photo")

    # Ensure owner_email/name fallback from top-level plot fields if needed
    if not data["owner_email"]:
        data["owner_email"] = plot.get("email") or plot.get("owner_email_address")
    
    # Validar que lat y lon estén presentes (crítico para el mapa)
    if data["lat"] is None or data["lon"] is None:
        raise ValueError(f"Las coordenadas (lat, lon) son obligatorias. lat={data['lat']}, lon={data['lon']}")

    db.insert_plot(data)

def list_published_plots():
    conn = db_conn(); c=conn.cursor()
    # Traer todas las filas de plots con coordenadas (lat/lon son críticos para el mapa)
    # Usar m2 como alias de surface_m2 para compatibilidad
    c.execute("SELECT id,title,m2 as surface_m2,price,lat,lon,registry_note_path,status,tour_360_b64 FROM plots WHERE lat IS NOT NULL AND lon IS NOT NULL")
    rows = c.fetchall(); conn.close()
    cols = ["id","title","surface_m2","price","lat","lon","registry_note_path","status","tour_360_b64"]
    result = []
    for r in rows:
        plot_dict = dict(zip(cols, r))
        # Asegurar que surface_m2 tenga un valor (usar m2 como fallback)
        if not plot_dict.get('surface_m2') and plot_dict.get('m2'):
            plot_dict['surface_m2'] = plot_dict['m2']
        result.append(plot_dict)
    return result

def reserve_plot(plot_id, buyer_name, buyer_email, amount, kind="reservation"):
    conn = db_conn(); c=conn.cursor()
    rid = uuid.uuid4().hex
    c.execute("INSERT INTO reservations (id,plot_id,buyer_name,buyer_email,amount,kind,created_at) VALUES (?,?,?,?,?,?,?)",
              (rid, plot_id, buyer_name, buyer_email, amount, kind, datetime.utcnow().isoformat()))
    # set plot status
    if kind=="reservation":
        c.execute("UPDATE plots SET status='reserved' WHERE id=?", (plot_id,))
    elif kind=="purchase":
        c.execute("UPDATE plots SET status='sold' WHERE id=?", (plot_id,))
    conn.commit(); conn.close()
    try:
        from modules.marketplace.email_notify import notify_new_reservation
        notify_new_reservation(plot_id, buyer_name, buyer_email, amount, kind)
    except Exception:
        pass
    return rid

def create_client_user_if_not_exists(email, name, transaction_id=None):
    """
    Crea un usuario cliente automáticamente si no existe.
    Retorna True si se creó el usuario, False si ya existía.
    """
    conn = db_conn(); c = conn.cursor()

    # Verificar si el usuario ya existe
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing_user = c.fetchone()

    if existing_user:
        conn.close()
        return False, None  # Usuario ya existe — consistente con (True, pwd)

    # Crear usuario nuevo
    import uuid
    from datetime import datetime
    import hashlib

    user_id = uuid.uuid4().hex

    # Generar contraseña temporal (usando el transaction_id o un hash del email)
    temp_password = transaction_id or hashlib.md5(email.encode()).hexdigest()[:8]
    password_hash = hashlib.sha256(temp_password.encode()).hexdigest()

    c.execute("""
        INSERT INTO users (id, email, name, role, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, email, name, 'client', password_hash, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    return True, temp_password  # Retorna True y la contraseña temporal

def get_client_proposals(client_email):
    """Obtener propuestas recibidas por un cliente (owner) usando owner_email en plots"""
    conn = db_conn(); c = conn.cursor()
    # Fix: Join architects table, use owner_email from plots
    c.execute("""
        SELECT 
            pr.id, pr.proposal_text, pr.estimated_budget, pr.deadline_days, pr.sketch_image_path, 
            pr.status, pr.created_at, pr.responded_at, pr.delivery_format, pr.delivery_price, 
            pr.supervision_fee, pr.visa_fee, pr.total_cliente, pr.commission, pr.project_id,
            pl.title as plot_title, pl.surface_m2 as plot_surface, pl.price as plot_price,
            a.id as architect_user_id,
            a.name as architect_name, a.company as architect_company,
            pj.title as project_title, pj.description as project_description, pj.area_m2 as project_area, pj.price as project_price
        FROM proposals pr
        JOIN plots pl ON pr.plot_id = pl.id
        JOIN architects a ON pr.architect_id = a.id
        LEFT JOIN projects pj ON pr.project_id = pj.id
        WHERE pl.owner_email = ?
        ORDER BY pr.created_at DESC
    """, (client_email,))
    rows = c.fetchall(); conn.close()
    cols = ["id", "proposal_text", "estimated_budget", "deadline_days", "sketch_image_path", 
            "status", "created_at", "responded_at", "delivery_format", "delivery_price", 
            "supervision_fee", "visa_fee", "total_cliente", "commission", "project_id",
            "plot_title", "plot_surface", "plot_price",
            "architect_user_id", "architect_name", "architect_company",
            "project_title", "project_description", "project_area", "project_price"]
    return [dict(zip(cols, r)) for r in rows]

def calculate_edificability(plot_surface_m2, percentage=0.33):
    """Calcular área edificable máxima basada en superficie de la finca y porcentaje (default 33%)"""
    return plot_surface_m2 * percentage

def update_proposal_status(proposal_id, status):
    """Actualizar status y responded_at de una propuesta"""
    from datetime import datetime
    conn = db_conn(); c = conn.cursor()
    c.execute("UPDATE proposals SET status = ?, responded_at = ? WHERE id = ?", 
              (status, datetime.utcnow().isoformat(), proposal_id))
    conn.commit(); conn.close()

def init_db():
    """Crear tablas necesarias si no existen"""
    conn = db_conn()
    c = conn.cursor()
    
    # Tabla service_providers
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_providers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            nif TEXT,
            specialty TEXT,
            company TEXT,
            phone TEXT,
            address TEXT,
            certifications TEXT,
            experience_years INTEGER,
            service_area TEXT,
            created_at TEXT
        )
    """)
    
    # Tabla service_assignments
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_assignments (
            id TEXT PRIMARY KEY,
            venta_id TEXT,
            proveedor_id TEXT,
            servicio_tipo TEXT,
            cliente_email TEXT,
            proyecto_id TEXT,
            precio_servicio REAL,
            estado TEXT DEFAULT 'pendiente',
            fecha_asignacion TEXT,
            fecha_completado TEXT,
            notas TEXT,
            FOREIGN KEY (venta_id) REFERENCES ventas_proyectos (id),
            FOREIGN KEY (proveedor_id) REFERENCES service_providers (id)
        )
    """)
    
    # Asegurar que la tabla users tenga el rol 'services' soportado
    # (Ya debería existir de db_setup.py, pero por si acaso)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            role TEXT,
            is_professional INTEGER DEFAULT 0,
            password_hash TEXT,
            phone TEXT,
            address TEXT,
            company TEXT,
            specialty TEXT,
            created_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def create_or_update_client_user(email, name, password=None):
    """
    Crea o actualiza un usuario cliente automáticamente.
    Siempre asegura que el usuario existe con rol 'client'.
    Si se proporciona password, se actualiza.
    """
    from werkzeug.security import generate_password_hash
    import uuid
    from datetime import datetime

    conn = db_conn()
    c = conn.cursor()

    # Verificar si el usuario ya existe
    c.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
    existing_user = c.fetchone()

    if existing_user:
        # Usuario existe - actualizar rol y nombre
        c.execute("UPDATE users SET role = 'client', name = ? WHERE email = ?", (name, email))

        # Si se proporciona nueva password, actualizarla
        if password:
            password_hash = generate_password_hash(password)
            c.execute("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))
    else:
        # Crear usuario nuevo - password es obligatoria para nuevos usuarios
        if not password:
            raise ValueError("Se requiere contraseña para crear un nuevo usuario cliente")

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)

        c.execute("""
            INSERT INTO users (id, email, name, role, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email, name, 'client', password_hash, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()