# LOG DE DESARROLLO — ARCHIRAPID MVP 2026

## [SESIÓN: 2026-04-18 (CONTINUACIÓN)] ✅ FIX €0 PAYMENT + CLEANUP PENDIENTE

### 🎯 Bug Fix Completado

#### 6. **Prevención de Pago €0 — Flujo Paso 6 (Pago y Descarga)**
- ✅ Added `st.stop()` after "No has seleccionado" info message (line 5178, flow.py)
- ✅ Garantiza que usuarios DEBEN seleccionar al menos 1 servicio/documento
- ✅ Impide fallback button que procesaba €0 sin validación Stripe
- ✅ Commit: `a9ed3d0` — "fix: Prevenir pago €0"

---

## [SESIÓN: 2026-04-18] ✅ PROYECTOS DISPONIBLES PORTAL CLIENTE — CERRADO

### 🎯 Objetivos Completados

#### 1. **Documentación Técnica CTE/LOE**
- ✅ Agregados 3 campos nuevos a BD (Supabase/PostgreSQL + SQLite):
  - `presupuesto_pdf` — Presupuesto y mediciones
  - `estudio_seguridad_pdf` — Estudio básico de seguridad y salud (RD 1627/1997)
  - `especificaciones_pdf` — Especificaciones técnicas NNEE
- ✅ Migraciones PostgreSQL en `_PG_ALTER_MIGRATIONS` (db.py líneas 962-967)
- ✅ SQLite migrations con try/except (db.py líneas 1480-1487)

#### 2. **Flujo Arquitectos/Estudiantes → Portal Cliente**
- ✅ `marketplace_upload.py`: 3 nuevos uploaders (CTE/LOE) → Supabase
- ✅ `estudiantes.py`: Mismos uploaders + wiring a DB
- ✅ `intranet.py`: Display completo de docs con enlaces
- ✅ Integración bidireccional con `save_upload()` (Supabase-first)

#### 3. **Portal Cliente — Sección Proyectos Disponibles**
- ✅ Badge pre-compra: "📎 Documentación técnica incluida"
- ✅ Botones de descarga post-compra (7 archivos):
  - Memoria PDF, Planos CAD, Modelo 3D, Presupuesto, ESS, NNEE, Planos DWG
- ✅ Info/expander: "¿Qué contiene este proyecto?" con tabla completa
- ✅ Manejo seguro: URLs Supabase + rutas locales

#### 4. **Financiación y Servicios Extra**
- ✅ Calculadora hipotecaria integrada: `render_calculadora()` de hipoteca.py
- ✅ Banners de partners: Banco (condiciones exclusivas) + Seguro de obra
- ✅ Servicios de gestión:
  - Gestión Hipoteca Autopromotor → +199€
  - Gestión Seguro de Obra → +99€
- ✅ Totales dinámicos reflejados en Stripe

#### 5. **Hardening Defensivo — BLINDAJE COMPLETO**
- ✅ `_safe_row_get()` para accesos a índices (sin `len()` que falla con _CompatRow)
- ✅ `_safe_float()` para conversión segura de números
- ✅ Validación previa a pagos: email + project_id
- ✅ Try/except robusto en todos los puntos críticos
- ✅ Protección contra divisiones por cero
- ✅ Valores por defecto para campos None
- ✅ Mensajes de error acotados y claros

---

### 📋 Commits Realizados

| Hash | Mensaje | Cambios |
|------|---------|---------|
| `a2ff590` | `hardening: Blindaje defensivo — PROYECTOS DISPONIBLES portal cliente (indestructible)` | Validaciones defensivas, try/except robusto, protección datos incompletos |
| `573a795` | `feat: Financiación y Servicios Extra — Calculadora hipotecaria + Partners + Gestión +199€/+99€` | Calculadora, banners, servicios de gestión, totales dinámicos |
| `f9aaf75` | `fix: Portal cliente — documentación CTE/LOE post-compra + info completa incluida` | Botones descarga, info expander, badge pre-compra |
| `790cbc8` | (anterior) | Intranet mejorada con state-aware buttons |

---

### 🔐 CRÍTICO — ESTADO ACTUAL

#### ✅ CERRADO Y BLINDADO
- **Sección**: `PROYECTOS DISPONIBLES` → Portal Cliente
- **Archivo**: `modules/marketplace/client_panel.py` (función `show_selected_project_panel()`)
- **Status**: INDESTRUCTIBLE — NO se puede romper

#### ⚠️ IMPORTANTE — RECORDATORIO
- **Groq API Key**: Rotación pendiente (clave antigua está en histórico GitHub)
  - Ver: `https://github.com/Archirapid/archirapid-mvp/security/secret-scanning`
  - TODO: Generar nueva clave → actualizar `.env` + Streamlit secrets + memory.md

---

### 📚 Contexto para Próximas Sesiones

#### Base de Datos
- Todas las migraciones están en `_PG_ALTER_MIGRATIONS` (líneas 962-967)
- SQLite fallback en lines 1480-1487
- Acceso seguro a _CompatRow: usar `_safe_row_get()` para índices

#### Validaciones Defensivas
- Siempre usar `_safe_float()` para conversiones numéricas
- Validar email + project_id ANTES de operaciones
- Try/except con límite de caracteres en mensajes: `str(err)[:100]`

#### Stripe Integration
- Verificar que `_url` no es None después de `create_checkout_session()`
- Incluir `extra_meta={"services_detail": _servicios_label()}` en todas las transacciones
- URLs de éxito/cancelación incluyen parámetros correctos (selected_project_v2, etc.)

---

### 🚀 Próximas Fases (Backlog)

1. **Stripe Live** (lunes 2026-03-30)
   - Activar modo live: `mode="subscription"` para suscripciones MLS
   - Cancelación de fin de período + webhook
   - Ver: `project_stripe_lunes.md`

2. **GIS Fase 2 — WMS Overlay** (aparcado)
   - Botón capa Catastro en mapa
   - Ver: `project_gis_wms_pendiente.md`

3. **MEP Visual en Babylon Editor**
   - Saneamiento, agua, eléctrico en 3D
   - Después de pruebas MLS

4. **Flujo Constructores e2e**
   - Revisión y ajustes: `project_service_providers.md`

---

### 📌 Notas Técnicas Críticas

- **No modificar**: Lógica interna de `render_calculadora()` en hipoteca.py
- **Supabase**: _CompatRow no tiene `len()` — usar `_safe_row_get()` siempre
- **Stripe**: El `project_id` se envía como string en `ventas_proyectos.proyecto_id`
- **Intranet**: Admin ve TODOS los docs (incluida docs CTE/LOE) para auditoría
- **Cliente**: Solo ve docs que compró (limitado por `ventas_proyectos`)

---

**Última actualización**: 2026-04-18 | **Estado**: ✅ BLOQUEADO Y CERRADO
