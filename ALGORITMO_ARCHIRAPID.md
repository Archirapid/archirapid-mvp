# ALGORITMO ARCHIRAPID — Documento Interno Confidencial
**Para uso exclusivo del fundador. No distribuir.**
*Generado el 2026-03-31*

---

## 1. QUÉ ES EL ALGORITMO DE ARCHIRAPID

ArchiRapid es un sistema que permite a cualquier persona, sin conocimientos técnicos, diseñar su futura vivienda unifamiliar en minutos y obtener un presupuesto orientativo real.

**Qué entra:**
- La parcela del usuario (identificada por referencia catastral o seleccionada en el mapa)
- Sus preferencias: presupuesto, número de habitaciones y baños, estilo arquitectónico, extras como garaje o piscina, y sistemas de energía sostenible
- Sus necesidades de instalaciones: tipo de saneamiento (red municipal, fosa séptica, fitodepuración...) y suministro de agua

**Qué sale:**
- Una distribución de habitaciones con metros cuadrados propuesta automáticamente
- Un plano 2D de planta
- Un modelo 3D editable en el navegador
- Un presupuesto desglosado en 12 partidas (estructura, instalaciones, fachada, etc.)
- El cálculo de la instalación de saneamiento según normativa española CTE HS-5 (tuberías, diámetros, fosa séptica)
- Una calificación energética orientativa (letra A–D)
- Un paquete ZIP descargable con memoria descriptiva, mediciones en Excel y datos del proyecto en JSON

**Qué valor genera:**
- El proceso equivale a varias semanas de trabajo de un arquitecto: ArchiRapid lo hace en segundos
- El usuario llega a hablar con un arquitecto real con un briefing ya definido, ahorrando horas de consulta
- Le permite saber si su parcela "cabe" para el proyecto que tiene en mente, antes de gastar un euro
- Conecta automáticamente la parcela con proyectos arquitectónicos profesionales ya diseñados y disponibles para comprar

---

## 2. CÓMO FUNCIONA EL MOTOR DE DISEÑO (flow.py)

El flujo de diseño tiene 4 pasos encadenados.

### Paso 1 — Recogida de inputs del usuario

El usuario configura su proyecto respondiendo a una serie de preguntas:

- **Presupuesto:** rango entre €60.000 y €600.000
- **Superficie construible:** el sistema toma el dato de la finca. Si no existe, calcula automáticamente el **33% de la superficie total de la parcela** como límite máximo edificable (norma urbanística general en suelo rústico español). Los metros recomendados se calculan como el mínimo entre lo que cabe en el presupuesto (85% del presupuesto ÷ €1.100/m²) y el 90% de lo edificable
- **Estilo arquitectónico:** Moderno, Mediterráneo, Contemporáneo, Ecológico, Rural, Montaña, Clásico, Playa, Andaluz. Cada estilo tiene un coste base diferente por metro cuadrado (desde €1.500/m² para el Moderno hasta €1.800/m² para el Clásico)
- **Forma del edificio** (cuadrada, rectangular, en L, irregular) y **tipo de tejado**
- **Extras:** garaje, piscina, porche, bodega, huerto, casa de aperos, accesibilidad, despacho
- **Sistemas de energía:** paneles solares, aerotermia, geotermia, recuperación de agua de lluvia, aislamiento natural, domótica
- **Instalaciones base:** tipo de cimentación, suministro de agua, sistema de saneamiento
- **Notas especiales:** texto libre donde el usuario puede escribir cualquier petición (chimenea, animales, etc.)

### Qué hace la IA (Groq / Llama 3.3 70B) en el Paso 1

Cuando el usuario pulsa "DISEÑAR MI CASA CON IA", el sistema envía un prompt al modelo de lenguaje Llama 3.3 de 70 mil millones de parámetros, servido por Groq.

El prompt le da al modelo:
- El total de metros cuadrados disponibles
- El número de dormitorios y baños pedidos
- El estilo, los extras y los sistemas energéticos solicitados
- Una restricción absoluta: la suma de todos los metros del JSON no puede superar el total disponible
- Las notas especiales del cliente

El modelo responde con un JSON simple: nombre de cada habitación y sus metros cuadrados. Ejemplo: `{"salon": 22, "cocina": 14, "dormitorio_principal": 16, ...}`.

El sistema entonces:
- Normaliza los nombres (por si la IA usa variantes)
- Consolida paneles solares en una sola entrada si aparecen duplicados
- Garantiza que los sistemas energéticos no acaban convirtiéndose en habitaciones en el plano

**Todo lo demás es lógica nuestra, no IA.**

### Paso 2 — Ajuste manual del presupuesto

El usuario puede modificar los metros de cada habitación con sliders. Cada tipo de habitación tiene un precio por metro cuadrado definido por nosotros:
- Salón/Cocina/Dormitorio principal: €1.500–1.600/m²
- Dormitorios secundarios: €1.400/m²
- Porche/Terraza: €700/m²
- Garaje/Bodega: €1.000/m²
- Huerto: €40/m²

Además se suman:
- Cimentación: €180/m² sobre el total construido
- Instalaciones base: €150/m² sobre el total construido
- Sistemas energéticos: aerotermia €8.000, geotermia €12.000, agua lluvia €3.500, aislamiento €2.000, domótica €5.000 (costes fijos por sistema)

El sistema avisa en tiempo real si el presupuesto se supera.

Una segunda llamada a la IA (Groq) analiza la distribución y da feedback: si las medidas son realistas, si hay algo demasiado grande o pequeño, y un comentario sobre los sistemas sostenibles elegidos.

### Paso 3 — Editor 3D

El usuario puede visualizar y ajustar la casa en un editor tridimensional en el navegador (Babylon.js). Si modifica la casa en 3D, los cambios se exportan como JSON y se sincronizan con el presupuesto del Paso 2.

### Paso 4 — Documentación y presupuesto final

Aquí se calcula el presupuesto definitivo con lógica 100% determinista (sin IA):

**Fórmula de presupuesto:**
- PEM (Presupuesto de Ejecución Material) = metros² totales × precio base del estilo × factor de plantas (1,00 para 1 planta / 1,05 para 2 plantas / 1,18 con semisótano / 1,22 con 2 plantas y semisótano)
- Total = PEM × 1,13 + €1.200 (imprevistos) + coste de chimenea (€3.500–4.500 según estilo, si aplica)

**Partidas del presupuesto (% sobre PEM):**

| Partida | % PEM |
|---------|-------|
| Estructura y forjados | 20% |
| Instalaciones (eléctrica, fontanería, climatización) | 13% |
| Cerramientos y fachada | 12% |
| Acabados interiores | 12% |
| Cimentación | 10% |
| Cubierta | 7% |
| Carpintería exterior | 6% |
| Particiones interiores | 5% |
| Baños y cocina (sanitarios) | 5% |
| Urbanización parcela | 3% |
| Movimiento de tierras | 3% |

A esto se añaden: honorarios técnicos (9% PEM) y licencias municipales (4% PEM).

**Calificación energética (lógica de puntos, sin IA):**
- Solar: 25 puntos, aerotermia: 20, geotermia: 20, aislamiento: 15, agua lluvia: 10, domótica: 10
- Resultado: A (≥60 pts), B (≥40 pts), C (≥20 pts), D (<20 pts)

**Subvenciones estimadas:**
- Paneles solares: €3.000 (IDAE), aerotermia: €5.000 (NextGen EU), geotermia: €8.000, aislamiento: €2.000, agua lluvia: €1.000
- Tope: máximo 40% del coste total

**Memoria descriptiva:** generada por Groq (Llama 3.3 70B) con un prompt que pide el texto completo de un proyecto básico según CTE, incluyendo secciones de memoria descriptiva, constructiva y cumplimiento normativo. El resultado se maqueta en PDF con ReportLab.

---

## 3. CÓMO FUNCIONA EL MATCHING FINCA-PROYECTO

El módulo de compatibilidad (compatibilidad.py) conecta las parcelas del marketplace con los proyectos arquitectónicos del catálogo. Es **lógica de reglas pura, sin IA**.

### Criterios de compatibilidad (aplicados en orden):

1. **Superficie edificable:** el proyecto debe tener metros construidos ≤ a la superficie edificable de la finca. Si la finca no tiene ese dato registrado, se calcula como el 33% de sus metros totales
2. **Presupuesto del cliente:** el precio del proyecto debe ser ≤ al presupuesto indicado (filtro opcional)
3. **Área deseada:** si el cliente indicó un tamaño deseado, el proyecto debe estar dentro de ±20% de esa cifra
4. **Parcela mínima:** el proyecto no puede requerir una parcela mayor a la disponible
5. **Tipo de propiedad:** solo proyectos residenciales
6. **Activo:** solo proyectos publicados y activos
7. **Ya comprado:** se excluyen proyectos que el cliente ya haya adquirido

Los resultados se ordenan de menor a mayor precio.

### Por qué no es IA

Esta lógica es deliberadamente determinista: un proyecto o cabe en una finca o no cabe. No hay margen de interpretación. La IA no añade valor aquí porque las reglas son objetivas (metros, precio, tipo).

---

## 4. CÓMO FUNCIONA LA CLASIFICACIÓN DE SUELO INSPIRE

La función `get_tipo_suelo_desde_coordenadas` en catastro_api.py determina si una parcela es Urbana o Rústica consultando la **Sede Electrónica del Catastro español**.

### Proceso:

1. El sistema envía una petición HTTPS al servicio OVC del Catastro con las coordenadas GPS de la parcela (latitud y longitud en formato WGS84)
2. El Catastro devuelve un XML con la descripción textual de la ubicación (`ldt`) y la referencia catastral de la parcela (`pc2`)
3. El sistema analiza ese texto:
   - Si contiene palabras como "RUSTIC" o "POLIGONO" → clasifica como **Rústica**
   - Si contiene "CALLE", "AVENIDA", "PLAZA", "PASEO" o "VIA" → clasifica como **Urbana**
   - Si no hay texto suficiente: mira el código catastral → empieza por "R" = Rústica, por "U" = Urbana
4. Si la API falla (timeout, error de red, respuesta inesperada) → devuelve **"Desconocida"** sin lanzar ningún error

Esta clasificación se realiza automáticamente cuando un propietario sube una finca al sistema (tanto en el panel de propietario como en el portal MLS).

### Para obtener coordenadas desde referencia catastral

La función `fetch_by_ref_catastral` usa otro endpoint del mismo servicio (OVCCoordenadas) para convertir una referencia catastral en coordenadas GPS y obtener la dirección completa registrada. Esto permite geolocalizar una finca aunque el usuario solo proporcione su referencia catastral de 20 dígitos.

---

## 5. CÓMO FUNCIONA LA CERTIFICACIÓN SHA-256

### Qué se certifica

Cuando un constructor envía una oferta y el cliente la acepta, se genera un **precontrato de obra** en PDF. Este documento incluye: nombre del proyecto, constructor, cliente, precio, plazos, garantías, nota técnica y la comisión del 3% correspondiente a ArchiRapid.

### Cómo se genera el hash

Una vez generado el PDF completo con todos los datos:
1. Se calcula la función de hash SHA-256 sobre los bytes exactos del PDF
2. El resultado es una cadena de 64 caracteres hexadecimales única e irrepetible
3. Si se cambia un solo carácter del contrato, el hash cambia completamente

### Dónde se guarda

- El hash completo se guarda en la base de datos (tabla `construction_offers`, columna `contrato_sha256`)
- El PDF se guarda también en base64 en la misma tabla (`contrato_pdf_b64`)
- En el panel del constructor se muestran los primeros 32 caracteres del hash junto a cada oferta, como prueba de integridad

### Para qué sirve

Permite verificar que el contrato no ha sido modificado después de su generación. Si en el futuro hay una disputa, se puede recalcular el hash del documento guardado y compararlo con el registrado. Si coinciden, el documento es auténtico.

---

## 6. QUÉ ES NUESTRO Y QUÉ ES DE TERCEROS

### Lógica 100% propia de ArchiRapid (lo que nos diferencia)

| Componente | Descripción |
|-----------|-------------|
| Motor CTE HS-5 (mep_hs5.py) | Tablas completas de la normativa española, cálculo de UDs por aparato sanitario, diámetros de ramales y colector, dimensionado de fosa séptica — todo Python puro, sin dependencias |
| Fórmulas de presupuesto | Precio base por estilo, factores por plantas, 12 partidas como % del PEM, honorarios, licencias, chimeneas — calibradas con el mercado español 2025 |
| Motor de matching (compatibilidad.py) | Algoritmo de 7 filtros para conectar fincas con proyectos |
| Clasificación de suelo | Lógica de interpretación de la respuesta del Catastro (INSPIRE) |
| Generador de plano 2D (floor_plan_svg.py) | Dibuja el plano de distribución en planta automáticamente |
| Flujo completo de diseño (flow.py) | 4 pasos integrados con lógica propia de negocio |
| Sistema de certificación SHA-256 | Generación e inmutabilidad de precontratos de obra |
| Portal MLS completo | Registro de inmobiliarias, trial 30 días, mercado colaborativo, reservas, notificaciones |
| Portal de constructores | Filtrado por especialidad, delay 24h plan gratuito, comisión 3%, contrato PDF |

### Lo que viene de APIs externas

| Proveedor | Para qué lo usamos |
|-----------|-------------------|
| **Groq / Llama 3.3 70B** | Generación del JSON de habitaciones (Paso 1), memoria descriptiva del proyecto (PDF), análisis de la distribución (Paso 2) |
| **Google Gemini (REST)** | Análisis de imágenes y PDFs de notas catastrales escaneadas (visión artificial) |
| **Sede Electrónica del Catastro** | Clasificación Urbana/Rústica por coordenadas GPS, geolocalización por referencia catastral |
| **Stripe** | Pagos: suscripción plan Destacado constructores, comisión 3% sobre obras, reservas MLS |
| **Supabase** | Base de datos PostgreSQL en producción (en local es SQLite) |
| **Resend** | Envío de emails: notificaciones a constructores, ciclo de emails del trial MLS |

### Lo que viene de librerías open source

| Librería | Para qué |
|----------|---------|
| **Streamlit** | Marco de la aplicación web completa |
| **Babylon.js** | Editor 3D en el navegador |
| **Folium** | Mapas interactivos con pins y capas |
| **ReportLab** | Generación de PDFs (memorias, contratos) |
| **openpyxl** | Generación del Excel de mediciones |
| **pandas** | Tablas y gestión de datos |
| **requests** | Llamadas HTTP a APIs externas (Catastro, Gemini) |

---

## 7. CÓMO ESTÁ PROTEGIDO

### Dónde están las claves y secretos

Las claves nunca están hardcodeadas en el código. Se guardan en:
- **Local:** archivo `.env` y `.streamlit/secrets.toml` (ambos en `.gitignore`, nunca suben a GitHub)
- **Producción (Streamlit Cloud):** en la sección "Secrets" del dashboard de Streamlit, inyectadas como variables de entorno

Las claves existentes son: GROQ_API_KEY, GEMINI_API_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, credenciales de Supabase (URL + anon key + service role key), y RESEND_API_KEY.

### Cuáles son las partes más valiosas del código

El núcleo diferenciador de ArchiRapid son tres piezas que no existen en ningún producto similar:

1. **El motor CTE HS-5** (mep_hs5.py): implementación completa de la normativa española de saneamiento. Es el único motor de este tipo disponible en Python. Calcula automáticamente qué tuberías, qué diámetros, qué fosa séptica y qué presupuesto necesita una vivienda específica basándose en su distribución de habitaciones.

2. **Las fórmulas de presupuesto calibradas** (en flow.py): el sistema de precios por estilo, las 12 partidas como porcentajes del PEM y los factores de altura están ajustados a los precios reales del mercado español 2025. Esto es knowhow acumulado.

3. **El motor de matching finca-proyecto** (compatibilidad.py): la lógica que determina qué proyectos del catálogo encajan en qué parcelas, con todos sus criterios cruzados.

### Qué debería moverse a un microservicio privado antes de dar acceso a un programador externo

Si en el futuro se contrata a alguien para desarrollar partes del sistema, estas partes deberían estar detrás de una API privada antes de dar acceso al repositorio:

- **mep_hs5.py** (motor CTE HS-5) — es el activo más único
- **Las fórmulas de presupuesto** dentro de flow.py (la sección "Costes reales mercado 2025" y la función `get_current_design_data`) — contienen los precios calibrados
- **compatibilidad.py** (motor de matching) — define la lógica comercial del marketplace

El desarrollador externo debería ver estos módulos como cajas negras: les llama con unos parámetros y recibe un resultado, sin acceso al código interno.

---

*Documento confidencial — ArchiRapid 2026*
