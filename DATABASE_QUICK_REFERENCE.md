# 🎯 ARCHIRAPID DATABASE - GUÍA RÁPIDA

## 📊 TABLA DE REFERENCIA RÁPIDA

| Tabla | Registros | Estado | Propósito | Archivos principales |
|-------|-----------|--------|-----------|---------------------|
| **plots** | 111 | 🟢 Activa | Fincas publicadas en marketplace | owners.py, client_panel.py, flow.py |
| **users** | 397 | 🟢 Activa | Todos los usuarios (roles múltiples) | app.py, utils.py, auth.py |
| **reservations** | 118 | 🟢 Activa | Reservas de fincas por clientes | client_panel.py, utils.py, plot_detail.py |
| **client_interests** | 77 | 🟢 Activa | Proyectos guardados como favoritos | project_search.py, client_panel.py |
| **projects** | 2 | 🟢 Activa | Proyectos arquitectónicos publicados | architects.py, utils.py |
| **architects** | 1 | 🟢 Activa | Info de arquitectos (duplica users) | utils.py, architects.py |
| **owners** | 13 | 🟢 Activa | Info de propietarios (duplica users) | utils.py, owners.py |
| **proposals** | 0 | 🟡 Preparada | Propuestas de arquitectos a fincas | src/db.py (preparado) |
| **subscriptions** | 0 | 🟡 Preparada | Planes de arquitectos (Basic/Pro) | architects.py (preparado) |
| **payments** | 0 | 🟡 Preparada | Historial de pagos | payment_flow.py (futuro) |
| **project_purchases** | 0 | 🟡 Preparada | Compras de proyectos (CAD/memoria) | project_search.py (futuro) |
| **service_providers** | 0 | 🟡 Preparada | Constructores y topógrafos | (futuro) |
| **service_assignments** | 0 | 🟡 Preparada | Asignación de servicios post-venta | (futuro) |
| **additional_services** | 0 | 🟡 Preparada | Servicios adicionales cotizados | (futuro) |

---

## 🔑 COLUMNAS CLAVE POR TABLA

### plots (parcelas/fincas)
```python
COLUMNAS_IMPORTANTES = {
    'id': 'INTEGER PRIMARY KEY',
    'catastral_ref': 'Referencia catastral oficial',  # NO cadastral_ref ⚠️
    'm2': 'Superficie total',                         # NO surface_m2 ⚠️
    'superficie_edificable': 'Metros edificables',    # NO buildable_m2 ⚠️
    'lat', 'lon': 'Coordenadas GPS',
    'price': 'Precio en €',
    'status': "'disponible' | 'reserved' | 'sold'",
    'owner_email': 'FK a users.email',
    'photo_paths': 'JSON array de rutas',
    'vector_geojson': 'GeoJSON de geometría'
}
```

### users (usuarios)
```python
COLUMNAS_IMPORTANTES = {
    'id': 'TEXT PRIMARY KEY (UUID)',
    'email': 'UNIQUE - usado como FK en otras tablas',
    'role': "'client' | 'architect' | 'owner' | 'provider'",
    'is_professional': '1 si es profesional',
    'password_hash': 'Hash de contraseña'
}
```

### projects (proyectos arquitectónicos)
```python
COLUMNAS_IMPORTANTES = {
    'id': 'INTEGER PRIMARY KEY',
    'architect_id': 'FK a users.id',
    'm2_parcela_minima': 'Parcela mínima requerida',
    'habitaciones', 'banos', 'plantas': 'Características',
    'memoria_pdf': 'Ruta a memoria técnica',
    'cad_file': 'Ruta a archivo CAD',
    'modelo_3d_glb': 'Modelo 3D para VR',
    'characteristics_json': 'JSON con todas las características'
}
```

---

## 🔄 FLUJOS DE DATOS PRINCIPALES

### 1️⃣ PROPIETARIO PUBLICA FINCA
```
owners.py (formulario) 
  → AI extrae datos (Gemini) 
  → utils.insert_plot() 
  → tabla plots 
  → app.py (marketplace)
```

### 2️⃣ CLIENTE COMPRA FINCA Y DISEÑA CASA
```
plot_detail.py (clic "Reservar") 
  → utils.insert_reservation() 
  → tabla reservations
  
client_panel.py (clic "DISEÑAR CON IA") 
  → session_state["design_plot_id"] 
  → flow.py lee tabla plots 
  → Groq API genera propuestas 
  → step2_planner.py (plano 2D)
```

### 3️⃣ ARQUITECTO PUBLICA PROYECTO
```
architects.py (subir PDF/CAD/fotos) 
  → utils.insert_project() 
  → tabla projects 
  → app.py (marketplace de proyectos)
```

---

## ⚠️ PROBLEMAS CRÍTICOS IDENTIFICADOS

### 🚨 1. Columna inexistente: `is_urban`
**Error:** `modules/ai_house_designer/flow.py` línea ~26  
**Problema:** SQL query pide `is_urban` pero NO existe en DB  
**Solución:** 
```python
# ❌ MAL
query = "SELECT catastral_ref, m2, superficie_edificable, is_urban FROM plots"

# ✅ BIEN
query = "SELECT catastral_ref, m2, superficie_edificable, plot_type FROM plots"
# O simplemente eliminar la columna del query
```

### ⚠️ 2. Duplicación de datos (users/architects/owners)
**Problema:** Misma información en 3 tablas diferentes  
**Impacto:** Posibles inconsistencias, duplicación de inserts  
**Solución recomendada:** Consolidar todo en `users` usando campo `role`

### ⚠️ 3. Tabla `clients` no existe
**Archivos afectados:** `app.py` (línea 441, 450), `app_clean.py`  
**Problema:** Código busca tabla `clients` que fue consolidada en `users`  
**Solución:**
```python
# ❌ MAL
cursor.execute("SELECT id FROM clients WHERE email = ?", (email,))

# ✅ BIEN
cursor.execute("SELECT id FROM users WHERE email = ? AND role = 'client'", (email,))
```

---

## 📂 ARCHIVOS DE ACCESO A BASE DE DATOS

### 🎯 Principal:
- **`src/db.py`** - CRUD completo, conexiones, funciones core

### 🛍️ Marketplace:
- **`modules/marketplace/utils.py`** - CRUD simplificado, helpers
- **`modules/marketplace/owners.py`** - Publicación de fincas
- **`modules/marketplace/client_panel.py`** - Panel de cliente, reservas
- **`modules/marketplace/architects.py`** - Gestión de arquitectos, proyectos
- **`modules/marketplace/plot_detail.py`** - Detalles de finca
- **`modules/marketplace/project_detail.py`** - Detalles de proyecto

### 🏠 AI Designer:
- **`modules/ai_house_designer/flow.py`** - Lee datos de parcela, genera propuestas

### 🔐 Autenticación:
- **`app.py`** - Sistema de login unificado
- **`modules/marketplace/auth.py`** - Funciones de autenticación

---

## 🔍 QUERIES ÚTILES

### Ver fincas disponibles en una provincia
```sql
SELECT id, title, m2, price, locality 
FROM plots 
WHERE province = 'Alicante' AND status = 'disponible'
ORDER BY price ASC;
```

### Ver reservas de un cliente
```sql
SELECT r.id, r.created_at, p.title, p.price, r.kind
FROM reservations r
JOIN plots p ON r.plot_id = p.id
WHERE r.buyer_email = 'cliente@example.com'
ORDER BY r.created_at DESC;
```

### Ver proyectos de un arquitecto
```sql
SELECT id, title, m2_parcela_minima, precio, habitaciones, banos
FROM projects
WHERE architect_id = 'UUID_ARQUITECTO'
ORDER BY created_at DESC;
```

### Ver usuarios por rol
```sql
SELECT role, COUNT(*) as total
FROM users
GROUP BY role;
```

---

## 🎨 FORMATO DE CAMPOS JSON

### photo_paths (en plots y projects)
```json
["uploads/foto1.jpg", "uploads/foto2.jpg", "uploads/foto3.jpg"]
```

### vector_geojson (en plots)
```json
{
  "type": "Polygon",
  "coordinates": [[[x1, y1], [x2, y2], [x3, y3], [x1, y1]]]
}
```

### characteristics_json (en projects)
```json
{
  "habitaciones": 3,
  "banos": 2,
  "plantas": 2,
  "garaje": true,
  "piscina": false,
  "jardin": true,
  "orientacion": "sur",
  "ventanas_pvc": true
}
```

---

## 🛠️ COMANDOS ÚTILES

### Verificar esquema de una tabla
```python
import sqlite3
conn = sqlite3.connect('database.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(plots);")
print(cur.fetchall())
```

### Contar registros
```python
cur.execute("SELECT COUNT(*) FROM plots;")
print(f"Total plots: {cur.fetchone()[0]}")
```

### Verificar foreign keys
```python
cur.execute("PRAGMA foreign_key_list(reservations);")
print(cur.fetchall())
```

### Habilitar foreign keys (SQLite)
```python
cur.execute("PRAGMA foreign_keys = ON;")
```

---

## 📋 CHECKLIST DE INTEGRACIÓN

Cuando agregues código que usa la base de datos:

- [ ] ✅ Usa nombres de columnas correctos (catastral_ref, m2, superficie_edificable)
- [ ] ✅ No uses `is_urban` (no existe)
- [ ] ✅ No busques tabla `clients` (usa users con role='client')
- [ ] ✅ Usa `utils.db_conn()` para obtener conexión
- [ ] ✅ Cierra conexiones con `conn.close()`
- [ ] ✅ Usa prepared statements con `?` para evitar SQL injection
- [ ] ✅ Valida que el usuario tiene permisos (owner_email, buyer_email, etc.)
- [ ] ✅ Maneja excepciones de SQLite
- [ ] ✅ Usa transacciones para operaciones múltiples

---

## 🚀 PRÓXIMOS PASOS

1. **⚠️ CRÍTICO:** Eliminar `is_urban` de flow.py
2. **Consolidar:** Eliminar tablas `architects` y `owners` duplicadas
3. **Agregar:** Foreign keys constraints en próxima migración
4. **Testear:** Flujo marketplace → AI designer con datos reales
5. **Documentar:** Agregar índices para optimizar queries frecuentes

---

**Archivo completo:** [DATABASE_DOCUMENTATION.md](DATABASE_DOCUMENTATION.md)  
**Diagrama ER:** [DATABASE_DIAGRAM.md](DATABASE_DIAGRAM.md)  
**Última actualización:** 2026-02-15
