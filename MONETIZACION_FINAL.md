# MONETIZACIÓN FINAL — ArchiRapid
## Documento maestro — Todos los canales, precios y comisiones
_Última actualización: 2026-03-30_

---

## VISIÓN GLOBAL — 6 CANALES DE INGRESOS

```
ArchiRapid
├── 1. DISEÑO CON IA          → Pago por uso + suscripción arquitectos
├── 2. DOCUMENTACIÓN          → PDF · CAD · BIM · Blockchain
├── 3. SERVICIOS TÉCNICOS     → Visado · D.Obra · Geotécnico · Licencia
├── 4. CONSTRUCTORES          → Plan Destacado €99 + Comisión 3% obra
├── 5. MLS INMOBILIARIAS      → Suscripción €39-199 + Comisión 1% venta
└── 6. PREFABRICADAS          → Comisión 10% a proveedor (0,7% a inmo)
```

---

## 1. DISEÑO CON IA

### 1.1 Acceso por tipo de usuario

| Perfil | Precio | Qué obtiene | Stripe |
|--------|--------|-------------|--------|
| **Cliente particular (Plan Free)** | €19/proyecto | Descarga del proyecto diseñado | `estudio_download` · 1.900 cents |
| **Arquitecto BASIC** | €29/mes | 1 proyecto activo + modo estudio | `sub_basic` · 2.900 cents/mes |
| **Arquitecto PRO** | €99/mes | 5 proyectos + modo estudio ilimitado | `sub_pro` · 9.900 cents/mes |
| **Arquitecto PRO Anual** | €890/año | PRO con descuento anual (~26% ahorro) | `sub_pro_anual` · 89.000 cents/año |
| **Arquitecto ENTERPRISE** | €299/mes | Proyectos ilimitados + soporte prioritario | `sub_enterprise` · 29.900 cents/mes |

### 1.2 Coste estimado de construcción (motor IA — flow.py)

El motor genera presupuestos orientativos para el cliente basados en:

| Variable | Rango | Referencia |
|----------|-------|-----------|
| Coste/m² estilo Ecológico | €1.600/m² | Línea 636 flow.py |
| Coste/m² estilo Rural | €1.650/m² | |
| Coste/m² estilo Montaña | €1.750/m² | |
| Coste/m² estilo Clásico | €1.800/m² | |
| **Rango orientativo general** | **€1.200–1.800/m²** | Mostrado al usuario |

### 1.3 Extras de construcción incluidos en el presupuesto IA

| Extra | Precio | Notas |
|-------|--------|-------|
| Chimenea estándar | €4.500 | |
| Chimenea ecológica (bioetanol) | €3.500 | Solo estilo Ecológico |
| Piscina | €25.000 | |
| Paneles solares | €8.000 | Ahorro estimado €1.200/año |
| Aerotermia | €8.000 | Ahorro estimado €800/año |
| Geotermia | €12.000 | |
| Aislamiento premium | €2.000 | Ahorro estimado €300/año |

### 1.4 Desglose de presupuesto por partidas (service_providers.py)

| Partida | % sobre total | Ejemplo en €150.000 |
|---------|---------------|---------------------|
| Estructura y cubierta | 28% | €42.000 |
| Cerramientos / fachada | 16% | €24.000 |
| Acabados interiores | 20% | €30.000 |
| Instalaciones | 14% | €21.000 |
| Cimentación | 14% | €21.000 |
| Honorarios / gestión | 8% | €12.000 |
| **TOTAL** | **100%** | **€150.000** |

---

## 2. DOCUMENTACIÓN

Disponible tras el diseño IA. El cliente selecciona qué documentos necesita.

| Producto | Precio | Cents | Stripe key | Descripción |
|----------|--------|-------|------------|-------------|
| Memoria PDF del Proyecto | €1.800 | 180.000 | `pdf_proyecto` | Memoria técnica completa |
| Planos CAD editables | €2.500 | 250.000 | `planos_cad` | DWG/DXF editables |
| Proyecto Completo (PDF + CAD) | €4.000 | 400.000 | `proyecto_completo` | Pack combinado |
| Modelo BIM/IFC | €149 | 14.900 | `bim_ifc` | Archivo para Revit/ArchiCAD |
| Certificado Blockchain | €99 | 9.900 | `blockchain_cert` | Sellado inmutable + hash SHA-256 |
| Descarga Plan Free | €19 | 1.900 | `estudio_download` | Acceso básico al proyecto |

**Nota sobre copias:** El cliente puede pedir múltiples copias PDF (€1.800/copia) y CAD (€2.500/copia). El coste total = `(copias_pdf × 1.800) + (copias_cad × 2.500)`.

---

## 3. SERVICIOS TÉCNICOS

Servicios opcionales gestionados desde el flujo IA y el panel cliente.

| Servicio | Precio | Cents | Stripe key | Descripción |
|----------|--------|-------|------------|-------------|
| Visado del Proyecto | €500 | 50.000 | `visado_proyecto` | Visado en Colegio de Arquitectos |
| Dirección de Obra | €800 | 80.000 | `direccion_obra` | Seguimiento técnico en obra |
| Estudio Geotécnico | €1.200 | 120.000 | — | Análisis del terreno |
| Gestión Licencia Municipal | €800 | 80.000 | — | Tramitación licencia urbanística |
| Supervisión Técnica | €300 | 30.000 | `supervision` | Visita de supervisión |
| Construcción Completa | €1.500 | 150.000 | `construccion` | Coordinación construcción completa |
| Copia Adicional | €200 | 20.000 | `copia_adicional` | Copia extra de cualquier documento |

---

## 4. CONSTRUCTORES / PROFESIONALES

### 4.1 Planes de acceso al Tablón de Obras

| | Gratuito | Destacado |
|-|----------|-----------|
| **Precio** | €0/mes | **€99/mes** |
| **Stripe key** | — | `sp_destacado` · 9.900 cents |
| **Vigencia** | Permanente | 30 días renovables |
| **Ofertas/mes** | 3 | Ilimitadas |
| **Badge** | ❌ | ⭐ VERIFICADO |
| **Orden en listados** | Normal | **Primero** |
| **Visibilidad tablón** | 24h retraso | Tiempo real |
| **Notificación email** | ❌ | ✅ Inmediata |
| **Comisión por obra** | N/A | 3% del presupuesto |

### 4.2 Comisión por Obra Adjudicada — 3%

Solo aplica cuando el cliente ACEPTA la oferta de un constructor Destacado.

| Concepto | Valor |
|---------|-------|
| Comisión ArchiRapid | **3% del presupuesto de la obra** |
| Quién paga | **El constructor** (recibe la obra) |
| Cuándo se cobra | Al pulsar "Aceptar" en el panel del cliente |
| Mecanismo | Stripe Checkout generado automáticamente |
| Función | `create_comision_checkout()` en stripe_utils.py |

**Ejemplos reales:**
| Presupuesto obra | Comisión ArchiRapid |
|-----------------|---------------------|
| €80.000 | €2.400 |
| €150.000 | €4.500 |
| €250.000 | €7.500 |

**Referencia de mercado:**
- Habitissimo / Cronoshare: €8–50 por lead
- Domestika Obras: 8–12% comisión
- Gestores de obra independientes: 3–8%
- **ArchiRapid: 3% solo si hay adjudicación** — más justo para el constructor

### 4.3 Comisión según plan arquitecto

Los arquitectos en modo Estudio pagan comisión al vender proyectos en el marketplace:

| Plan | Comisión sobre venta |
|------|---------------------|
| BASIC (€29/mes) | 10% |
| PRO (€99/mes) | 8% |
| ENTERPRISE (€299/mes) | 5% |

### 4.4 Especialidades disponibles (16 categorías)

`constructor`, `estructura`, `cimentacion`, `cerramientos`, `instalaciones_electricas`, `instalaciones_fontaneria`, `climatizacion`, `acabados_interiores`, `tejados_cubiertas`, `sostenibilidad_energia`, `direccion_obra`, `aparejador`, `reformas_integrales`, `prefabricadas`, `topografia`, `bim`

---

## 5. MLS — INMOBILIARIAS

### 5.1 Planes de suscripción

| | STARTER | AGENCY | PRO |
|-|---------|--------|-----|
| **Precio** | **€39/mes** | **€99/mes** | **€199/mes** |
| **Stripe key** | `mls_starter` · 3.900 | `mls_agency` · 9.900 | `mls_enterprise` · 19.900 |
| **Fincas activas** | 5 | 20 | 50 |
| **Reservas de colaboración** | ❌ | ✅ | ✅ |
| **Mercado colaborativo** | ✅ | ✅ | ✅ |
| **Fichas públicas** | ✅ | ✅ | ✅ |
| **Soporte prioritario** | ❌ | ❌ | ✅ |
| **Trial gratuito** | 30 días | 30 días | 30 días |

### 5.2 Comisión ArchiRapid en operaciones MLS — 1% fijo

| Concepto | Valor |
|---------|-------|
| Comisión ArchiRapid | **1% FIJO sobre precio de venta** |
| Mínimo operacional | La comisión total debe ser > 1% |
| Función | `mls_comisiones.py` |

**Ejemplo de split en una operación:**

| Precio finca | €300.000 |
|-------------|----------|
| Comisión total acordada | 8% = €24.000 |
| **ArchiRapid (fijo)** | **1% = €3.000** |
| Canal disponible | 7% = €21.000 |
| Agencia listante | 3,5% = €10.500 |
| Agencia colaboradora | 3,5% = €10.500 |

### 5.3 Reserva de colaboración — €200

Señal para reservar una finca del mercado MLS durante 7 días.

| Concepto | Valor |
|---------|-------|
| Importe reserva | **€200** |
| Stripe key | `mls_reserva` · 20.000 cents |
| Vigencia | 7 días |
| Descuento en comisión final | Sí — descontado al cierre |
| Función | `create_reservation_checkout()` en stripe_utils.py |

### 5.4 Trial gratuito 30 días

- Se activa automáticamente al aprobar la inmobiliaria desde intranet
- Función `activate_trial()` en mls_db.py (idempotente)
- Emails automáticos: bienvenida (día 0), check-in (día 7), urgencia (día 25)
- Banner verde mientras activo (días restantes), banner rojo bloqueante al expirar

---

## 6. PREFABRICADAS

### 6.1 Modelo de comisión

| Concepto | Valor |
|---------|-------|
| ArchiRapid cobra al proveedor | **10%** del precio de venta |
| Parte que recibe la inmobiliaria | 7% de esa comisión = **0,7% del precio** |
| Archivo | `modules/mls/mls_prefabricadas.py` líneas 20-22 |

**Ejemplo:**
| Precio prefabricada | ArchiRapid | Inmobiliaria |
|--------------------|-----------|--------------|
| €80.000 | €8.000 (10%) | €560 (0,7%) |
| €120.000 | €12.000 | €840 |
| €200.000 | €20.000 | €1.400 |

---

## 7. CATÁLOGO STRIPE COMPLETO

Todos los `product_keys` definidos en `modules/stripe_utils.py` (líneas 9–35):

| Key | Nombre | Precio | Cents | Tipo |
|-----|--------|--------|-------|------|
| `pdf_proyecto` | Memoria PDF del Proyecto | €1.800 | 180.000 | Único |
| `planos_cad` | Planos CAD editables | €2.500 | 250.000 | Único |
| `proyecto_completo` | Proyecto Completo (PDF+CAD) | €4.000 | 400.000 | Único |
| `bim_ifc` | Modelo BIM/IFC | €149 | 14.900 | Único |
| `blockchain_cert` | Certificado Blockchain | €99 | 9.900 | Único |
| `estudio_download` | Descarga Plan Free | €19 | 1.900 | Único |
| `visado_proyecto` | Visado del Proyecto | €500 | 50.000 | Único |
| `direccion_obra` | Dirección de Obra | €800 | 80.000 | Único |
| `construccion` | Construcción Completa | €1.500 | 150.000 | Único |
| `supervision` | Supervisión Técnica | €300 | 30.000 | Único |
| `copia_adicional` | Copia Adicional | €200 | 20.000 | Único |
| `sub_basic` | Suscripción BASIC | €29/mes | 2.900 | Recurrente |
| `sub_pro` | Suscripción PRO | €99/mes | 9.900 | Recurrente |
| `sub_pro_anual` | Suscripción PRO Anual | €890/año | 89.000 | Recurrente |
| `sub_enterprise` | Suscripción ENTERPRISE | €299/mes | 29.900 | Recurrente |
| `mls_starter` | MLS STARTER | €39/mes | 3.900 | Único* |
| `mls_agency` | MLS AGENCY | €99/mes | 9.900 | Único* |
| `mls_enterprise` | MLS PRO | €199/mes | 19.900 | Único* |
| `mls_reserva` | Reserva MLS | €200 | 20.000 | Único |
| `sp_destacado` | Plan Destacado Constructor | €99/30d | 9.900 | Único* |

_* Pendiente migrar a mode="subscription" en el sprint Stripe Live_

---

## 8. THRESHOLDS DE DETECCIÓN DE PLAN

Función `_detectar_plan_desde_session()` — detecta qué plan pagó el usuario por el amount:

| Rango (cents) | Plan detectado |
|---------------|----------------|
| ≤ 5.000 | `mls_starter` |
| ≤ 15.000 | `mls_agency` |
| > 15.000 | `mls_enterprise` |

---

## 9. ESTADO ACTUAL DE IMPLEMENTACIÓN

| Canal | Estado | Notas |
|-------|--------|-------|
| Diseño con IA | ✅ Completo | Motor de presupuesto activo |
| Documentación (PDF/CAD/BIM) | ✅ Completo | Stripe integrado |
| Servicios técnicos | ✅ Parcial | Algunos sin Stripe aún |
| Plan Destacado constructor | ✅ Completo | Stripe + BD + email notificación |
| Comisión 3% obra | ✅ Completo | Stripe al aceptar oferta |
| Filtrado tablón por especialidad | ✅ Completo | `partidas_solicitadas` en BD |
| Delay 24h plan gratuito | ✅ Completo | |
| MLS planes STARTER/AGENCY/PRO | ✅ Completo | Stripe (test, pago único) |
| MLS trial 30 días + emails | ✅ Completo | |
| MLS reserva €200 | ✅ Completo | |
| Comisión 1% MLS | ✅ Lógica implementada | Pendiente verificar cobro real |
| Prefabricadas comisión | ✅ Lógica implementada | |
| Stripe LIVE (producción) | ⏳ Pendiente | Sprint agendado |
| MLS mode=subscription (recurrente) | ⏳ Pendiente | Junto con Stripe live |
| Cancelación suscripción MLS | ⏳ Pendiente | cancel_at_period_end |

---

## 10. PROYECCIÓN ECONÓMICA

### Escenario conservador (Año 1)

| Canal | Precio unitario | Volumen | Ingresos |
|-------|----------------|---------|---------|
| Plan Destacado constructores | €99/mes | 30 constructores | **€35.640/año** |
| Comisión 3% obras adjudicadas | €4.500 media | 20 obras | **€90.000/año** |
| MLS STARTER | €39/mes | 15 inmobiliarias | **€7.020/año** |
| MLS AGENCY | €99/mes | 10 inmobiliarias | **€11.880/año** |
| MLS PRO | €199/mes | 5 inmobiliarias | **€11.940/año** |
| Comisión 1% ventas MLS | €3.000 media | 5 operaciones | **€15.000/año** |
| Documentación (PDF/CAD) | €1.800–4.000 | 20 proyectos | **€50.000/año** |
| Suscripciones arquitectos | €29–299/mes | 20 arquitectos | **€18.000/año** |
| **TOTAL CONSERVADOR** | | | **~€229.480/año** |

### Escenario optimista (Año 2)

| Canal | Proyección |
|-------|-----------|
| 100 constructores Destacado + 50 obras | ~€350.000 |
| 50 inmobiliarias MLS + 20 operaciones | ~€120.000 |
| Documentación + servicios técnicos | ~€150.000 |
| **TOTAL OPTIMISTA** | **~€620.000/año** |

---

## 11. ARCHIVOS CLAVE

| Archivo | Contenido monetización |
|---------|----------------------|
| `modules/stripe_utils.py` | Catálogo PRODUCTS dict + 5 funciones checkout |
| `app.py` líneas ~1507–1660 | Handlers de pago exitoso (proyectos, destacado, comisión) |
| `modules/marketplace/service_providers.py` | UI planes constructor + comisión 3% |
| `modules/marketplace/client_panel.py` | Disparo comisión al aceptar oferta |
| `modules/marketplace/architects.py` | Planes arquitecto + comisiones por venta |
| `modules/mls/mls_portal.py` | Planes MLS STARTER/AGENCY/PRO + checkout |
| `modules/mls/mls_reservas.py` | Reserva €200 Stripe |
| `modules/mls/mls_comisiones.py` | Split 1% ArchiRapid + canal colaboración |
| `modules/mls/mls_prefabricadas.py` | Comisión 10% proveedor / 0,7% inmo |
| `modules/ai_house_designer/flow.py` | Coste/m² por estilo + presupuesto IA |

---

_Documento unificado desde MONETIZACION_SERVICIOS.md + análisis completo del código fuente_
_Reemplaza todos los documentos de monetización anteriores_
