# 🗄️ ARCHIRAPID DATABASE DOCUMENTATION

**Archivo de base de datos:** `database.db`  
**Tamaño:** 4044 KB  
**Total de tablas:** 19  
**Generado:** 2026-02-15

---

## 📊 RESUMEN EJECUTIVO

### Tablas Activas (con datos)
- **plots**: 111 registros - Fincas publicadas en el marketplace
- **users**: 397 registros - Usuarios del sistema (arquitectos, clientes, propietarios)
- **reservations**: 118 registros - Reservas de fincas por clientes
- **client_interests**: 77 registros - Intereses de clientes en proyectos
- **architects**: 1 registro - Arquitectos registrados
- **owners**: 13 registros - Propietarios de fincas
- **projects**: 2 registros - Proyectos arquitectónicos publicados

### Tablas Vacías (preparadas para futuro uso)
- proposals, payments, project_purchases, subscriptions, additional_services
- service_providers, service_assignments, ventas_proyectos
- proyectos (legacy), arquitectos (legacy)

---

## 📋 TABLAS PRINCIPALES

### 1. **plots** (111 registros)
**Propósito:** Almacena fincas/parcelas publicadas en el marketplace por propietarios

**Columnas principales:**
```
id (INTEGER PRIMARY KEY)
title (TEXT)
catastral_ref (TEXT) - Referencia catastral oficial
m2 (REAL) - Superficie total en metros cuadrados
superficie_edificable (REAL) - Metros cuadrados edificables
lat, lon (REAL) - Coordenadas geográficas
price (REAL) - Precio en euros
status (TEXT) - disponible, reserved, sold
owner_email (TEXT)
owner_name (TEXT)
owner_phone (TEXT)
province (TEXT)
locality (TEXT)
address (TEXT)
registry_note_path (TEXT) - Ruta a nota simple registral
plano_catastral_path (TEXT) - Ruta a plano catastral
photo_paths (TEXT) - JSON con rutas de fotos
vector_geojson (TEXT) - Geometría vectorial de la parcela
solar_virtual (TEXT) - URL a Solar Virtual
sanitation_type (TEXT) - Tipo de saneamiento (urbano/fosa)
plot_type (TEXT) - Tipo de parcela
propietario_direccion (TEXT)
featured (INTEGER) - 1 si es destacada
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/owners.py` - Propietarios publican fincas
- `modules/marketplace/utils.py` - CRUD: `insert_plot()`, `list_published_plots()`
- `modules/marketplace/client_panel.py` - Clientes consultan fincas compradas/reservadas
- `modules/ai_house_designer/flow.py` - Carga datos de parcela para diseño
- `app.py` - Lista fincas en marketplace principal
- `modules/marketplace/plot_detail.py` - Muestra detalles de finca individual

**Datos de ejemplo:**
```sql
SELECT title, province, m2, price, owner_email FROM plots LIMIT 3;
-- Results: Fincas en Alicante, Málaga, Murcia con precios entre 120k-300k€
```

---

### 2. **users** (397 registros)
**Propósito:** Tabla unificada de usuarios del sistema (todos los roles)

**Columnas principales:**
```
id (TEXT PRIMARY KEY)
email (TEXT UNIQUE)
full_name / name (TEXT)
role (TEXT) - 'client', 'architect', 'owner', 'provider'
is_professional (INTEGER) - 1 si es profesional
password_hash (TEXT)
phone (TEXT)
address (TEXT)
company (TEXT)
specialty (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `app.py` - Sistema de autenticación unificado, registro de usuarios
- `modules/marketplace/utils.py` - `insert_user()`, `get_user_by_email()`
- `modules/marketplace/auth.py` - Login y registro
- `modules/marketplace/architects.py` - Registro de arquitectos
- `modules/marketplace/owners.py` - Registro de propietarios

**Roles activos:**
- **client**: Usuarios que compran fincas/proyectos
- **architect**: Arquitectos que publican proyectos y propuestas
- **owner**: Propietarios que publican fincas

---

### 3. **projects** (2 registros)
**Propósito:** Proyectos arquitectónicos publicados en el marketplace

**Columnas principales (36 columnas):**
```
id (INTEGER PRIMARY KEY)
title (TEXT)
architect_id (TEXT)
area_m2 / m2_construidos (REAL)
m2_parcela_minima (REAL) - Parcela mínima requerida
price (REAL) - Precio del proyecto
habitaciones (INTEGER)
banos (INTEGER)
plantas (INTEGER)
garaje (INTEGER) - 1 si tiene garaje
piscina (INTEGER) - 1 si tiene piscina
memoria_pdf (TEXT) - Ruta a memoria técnica
cad_file (TEXT) - Ruta a archivo CAD
foto_principal (TEXT)
modelo_3d_path (TEXT)
modelo_3d_glb (TEXT) - Modelo 3D para visor VR
characteristics_json (TEXT) - JSON con características completas
ocr_text (TEXT) - Texto extraído de memoria
files_json (TEXT) - JSON con todos los archivos
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/architects.py` - Arquitectos publican proyectos
- `modules/marketplace/utils.py` - `insert_project()`
- `modules/marketplace/marketplace_upload.py` - Subida de proyectos
- `modules/marketplace/project_detail.py` - Detalles de proyectos
- `app.py` - Marketplace de proyectos

---

### 4. **reservations** (118 registros)
**Propósito:** Reservas de fincas por clientes (antes de compra final)

**Columnas:**
```
id (TEXT PRIMARY KEY)
plot_id (INTEGER)
buyer_name (TEXT)
buyer_email (TEXT)
amount (REAL) - Monto de reserva
kind (TEXT) - 'reserve' o 'purchase'
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/client_panel.py` - Ver reservas del cliente
- `modules/marketplace/utils.py` - `insert_reservation()`
- `modules/marketplace/plot_detail.py` - Verificar si finca está reservada
- `app.py` - Panel de propietario (ver reservas recibidas)

---

### 5. **client_interests** (77 registros)
**Propósito:** Proyectos guardados como favoritos por clientes

**Columnas:**
```
id (INTEGER PRIMARY KEY AUTOINCREMENT)
client_email (TEXT)
project_id (INTEGER)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/project_search.py` - Guardar interés en proyecto
- `modules/marketplace/client_panel.py` - Ver proyectos guardados

---

### 6. **architects** (1 registro)
**Propósito:** Tabla específica de arquitectos (complementa users)

**Columnas:**
```
id (TEXT PRIMARY KEY)
name (TEXT)
email (TEXT)
company (TEXT)
specialty (TEXT)
bio (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/utils.py` - `insert_user()` crea entrada en architects
- `modules/marketplace/architects.py` - Perfil y gestión de arquitectos

**Nota:** Esta tabla duplica información de `users` con role='architect'. Considerar consolidación.

---

### 7. **owners** (13 registros)
**Propósito:** Tabla específica de propietarios (complementa users)

**Columnas:**
```
id (TEXT PRIMARY KEY)
name (TEXT)
email (TEXT)
phone (TEXT)
address (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/utils.py` - `insert_user()` crea entrada en owners
- `modules/marketplace/owners.py` - Gestión de propietarios

**Nota:** Esta tabla duplica información de `users` con role='owner'. Considerar consolidación.

---

### 8. **proposals** (0 registros - estructura preparada)
**Propósito:** Propuestas de arquitectos para diseñar fincas específicas

**Columnas:**
```
id (TEXT PRIMARY KEY)
plot_id (INTEGER)
architect_id (TEXT)
message (TEXT)
price (REAL)
status (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `src/db.py` - Funciones de lectura preparadas
- `modules/marketplace/client_panel.py` - Consulta propuestas (actualmente vacía)

---

### 9. **subscriptions** (0 registros - estructura preparada)
**Propósito:** Suscripciones de arquitectos (planes Basic/Pro/Premium)

**Columnas:**
```
id (TEXT PRIMARY KEY)
architect_id (TEXT)
plan_type (TEXT) - 'basic', 'pro', 'premium'
price (REAL)
monthly_proposals_limit (INTEGER)
commission_rate (REAL)
status (TEXT) - 'active', 'expired'
start_date (TEXT)
end_date (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/architects.py` - Verificar límites de plan, crear suscripción

---

### 10. **payments** (0 registros - estructura preparada)
**Propósito:** Historial de pagos de clientes

**Columnas:**
```
id (TEXT PRIMARY KEY)
user_email (TEXT)
amount (REAL)
type (TEXT) - 'plot', 'project', 'service'
reference_id (TEXT)
status (TEXT)
payment_method (TEXT)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/payment_flow.py` - Procesar pagos (próximamente)

---

### 11. **project_purchases** (0 registros - estructura preparada)
**Propósito:** Compras de proyectos (memoria técnica + CAD)

**Columnas:**
```
id (TEXT PRIMARY KEY)
project_id (INTEGER)
buyer_email (TEXT)
price (REAL)
includes_cad (INTEGER)
includes_memoria (INTEGER)
created_at (TEXT)
```

**Archivos que interactúan:**
- `modules/marketplace/project_search.py` - Comprar proyecto (próximamente)

---

### 12. **service_providers** (0 registros)
**Propósito:** Proveedores de servicios post-venta (constructores, topógrafos)

**Columnas:**
```
id (TEXT PRIMARY KEY)
name (TEXT)
email (TEXT)
service_type (TEXT) - 'constructor', 'surveyor'
phone (TEXT)
province (TEXT)
rating (REAL)
created_at (TEXT)
```

---

### 13. **service_assignments** (0 registros)
**Propósito:** Asignación de constructores/topógrafos a ventas

**Columnas:**
```
id (TEXT PRIMARY KEY)
reservation_id (TEXT)
provider_id (TEXT)
service_type (TEXT)
status (TEXT)
created_at (TEXT)
```

---

### 14. **additional_services** (0 registros)
**Propósito:** Servicios adicionales cotizados post-venta

**Columnas:**
```
id (TEXT PRIMARY KEY)
reservation_id (TEXT)
service_type (TEXT)
description (TEXT)
price (REAL)
status (TEXT)
created_at (TEXT)
```

---

### 15-17. **TABLAS LEGACY (español)**

Estas tablas parecen ser versiones antiguas en español que están siendo migradas:

- **proyectos** (0 registros) - Versión en español de `projects`
- **arquitectos** (0 registros) - Versión en español de `architects`
- **ventas_proyectos** (0 registros) - Versión en español de `project_purchases`

**Recomendación:** Eliminar tras confirmar que no se usan.

---

### 18. **clients** (tabla referenciada en código pero NO existe en DB actual)

**Archivos que intentan usarla:**
- `app.py` línea 441, 450
- `app_clean.py` línea 143, 526

**Estado:** Esta tabla parece haber sido consolidada en `users` con role='client'. El código debería actualizarse.

---

## 🔗 RELACIONES ENTRE TABLAS

### Diagrama de relaciones principales:

```
users (email, role)
  ├─> architects (email)
  ├─> owners (email)
  └─> clients (NO EXISTE - usar users.role='client')

owners (email)
  └─> plots (owner_email)

architects (id)
  ├─> projects (architect_id)
  ├─> proposals (architect_id)
  └─> subscriptions (architect_id)

plots (id)
  ├─> reservations (plot_id)
  ├─> proposals (plot_id)
  └─> design_plot_id (en session_state de Streamlit)

projects (id)
  ├─> client_interests (project_id)
  └─> project_purchases (project_id)

reservations (id)
  ├─> service_assignments (reservation_id)
  └─> additional_services (reservation_id)
```

---

## 🔄 FLUJO DE DATOS PRINCIPAL

### 1. Publicación de Finca por Propietario
```
1. owners.py: Propietario completa formulario
2. AI extrae datos de nota catastral (Gemini Vision API)
3. utils.py: insert_plot() → tabla plots
4. app.py: Finca aparece en marketplace
```

### 2. Cliente compra Finca y diseña casa
```
1. plot_detail.py: Cliente reserva finca → tabla reservations
2. client_panel.py: Clic en "DISEÑAR CON IA" → session_state["design_plot_id"]
3. flow.py: Lee plot data de tabla plots
4. flow.py: Genera propuestas con IA (Groq API)
5. step2_planner.py: Genera plano 2D (matplotlib)
```

### 3. Arquitecto publica Proyecto
```
1. architects.py: Subir memoria técnica (PDF) + CAD + fotos
2. utils.py: insert_project() → tabla projects
3. app.py: Proyecto aparece en marketplace
4. project_detail.py: Clientes pueden comprar memoria/CAD
```

---

## ⚠️ PROBLEMAS IDENTIFICADOS

### 1. Columna `is_urban` no existe en tabla plots
**Archivo afectado:** `modules/ai_house_designer/flow.py` línea ~26  
**Solución:** Eliminar de SQL query o usar columna `plot_type` en su lugar

### 2. Discrepancia en nombres de columnas
**Encontrado:**
- Código usa `cadastral_ref` pero DB tiene `catastral_ref` ✅ CORREGIDO
- Código usa `surface_m2` pero DB tiene `m2` ✅ CORREGIDO
- Código usa `buildable_m2` pero DB tiene `superficie_edificable` ✅ CORREGIDO

### 3. Duplicación de datos users/architects/owners
**Problema:** Mismos datos en 3 tablas diferentes  
**Recomendación:** Consolidar todo en `users` y usar campo `role`

### 4. Tabla `clients` referenciada pero no existe
**Solución:** Actualizar código para usar `users` con `WHERE role='client'`

---

## 📁 ARCHIVOS PRINCIPALES DE ACCESO A DB

### Core Database Module
- **`src/db.py`** (934 líneas)
  - Funciones: `insert_plot()`, `insert_project()`, `insert_user()`
  - Gestión de conexiones: `get_conn()`, `db_conn()`
  - CRUD completo para todas las tablas

### Marketplace Modules
- **`modules/marketplace/utils.py`**
  - CRUD simplificado: `insert_plot()`, `insert_user()`, `insert_reservation()`
  - Funciones de autenticación
  
- **`modules/marketplace/owners.py`**
  - Formulario de publicación de fincas (13 campos)
  - Integración con IA para extracción de datos catastrales

- **`modules/marketplace/client_panel.py`**
  - Panel de cliente: ver fincas compradas/reservadas
  - Botón "DISEÑAR CON IA" → connection con AI designer

- **`modules/marketplace/architects.py`**
  - Gestión de arquitectos: publicar proyectos, suscripciones
  - Dashboard de arquitecto

### AI Designer Module
- **`modules/ai_house_designer/flow.py`**
  - Lee datos de parcela desde `plots` vía `design_plot_id`
  - Genera propuestas con Groq API
  - Integración con planner 2D

---

## 📊 ESTADÍSTICAS DE DATOS

### Distribución de usuarios por rol
```sql
SELECT role, COUNT(*) FROM users GROUP BY role;
-- client: ~350+
-- architect: 1
-- owner: 13
-- (Resto sin especificar)
```

### Fincas por provincia
```sql
SELECT province, COUNT(*) FROM plots WHERE province IS NOT NULL GROUP BY province;
-- Alicante, Málaga, Murcia, Valencia (mayoría)
```

### Status de fincas
```sql
SELECT status, COUNT(*) FROM plots GROUP BY status;
-- disponible: ~90+
-- reserved: 20+
-- sold: 0
```

---

## 🔐 SEGURIDAD

### Passwords
- Almacenados como hash en `users.password_hash`
- No se expone en queries de lectura

### Validación de propietarios
- `plots.owner_email` debe coincidir con `users.email` donde `role='owner'`

### Acceso a datos
- Clients solo ven sus propias reservas: `WHERE buyer_email = ?`
- Propietarios solo ven sus fincas: `WHERE owner_email = ?`

---

## 📝 NOTAS ADICIONALES

### Formato de campos especiales

**photo_paths**: JSON array de rutas
```json
["uploads/foto1.jpg", "uploads/foto2.jpg"]
```

**vector_geojson**: GeoJSON de geometría de parcela
```json
{"type": "Polygon", "coordinates": [...]}
```

**characteristics_json**: Todas las características del proyecto
```json
{
  "habitaciones": 3,
  "banos": 2,
  "garaje": true,
  "piscina": false
}
```

### Convenciones de IDs
- `users.id`: UUID generado con `uuid4().hex`
- `plots.id`: INTEGER autoincremental
- `projects.id`: INTEGER autoincremental

### Timestamps
- Formato: ISO 8601 string `YYYY-MM-DD HH:MM:SS`
- Timezone: Local (España - UTC+1/+2)

---

## 🚀 PRÓXIMOS PASOS RECOMENDADOS

1. ✅ **CORREGIR:** Eliminar referencia a `is_urban` en flow.py
2. ⚠️ **CONSOLIDAR:** Eliminar tablas duplicadas (architects/owners → users)
3. 📝 **DOCUMENTAR:** Agregar constraints de FOREIGN KEY en próxima migración
4. 🧪 **TESTEAR:** Flujo completo marketplace → AI designer con datos reales
5. 🔐 **MIGRAR:** Passwords a bcrypt (actualmente usa hash simple)

---

**Última actualización:** 2026-02-15  
**Versión de DB:** database.db (4044 KB)  
**Commit Git:** d409bc9 (branch: diseñador-mvp-avanzado)
