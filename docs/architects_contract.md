# Contrato de la Sección Arquitectos

## Propósito
La sección Arquitectos es el núcleo del marketplace para profesionales de la arquitectura. Permite a los arquitectos registrados subir, gestionar y publicar proyectos arquitectónicos completos en el catálogo de ARCHIRAPID, facilitando la conexión con propietarios y clientes potenciales.

## Funcionalidades Principales
- **Subida de Proyectos**: Los arquitectos pueden cargar proyectos completos incluyendo planos, renders 3D, memorias constructivas, presupuestos y archivos CAD.
- **Gestión de Catálogo**: Visualización y edición de proyectos publicados.
- **Suscripciones**: Control de acceso basado en planes de suscripción activos.
- **Marketplace Integration**: Exposición de proyectos en el marketplace principal para que propietarios y clientes puedan explorarlos y contactar.

## Datos de Entrada (Contexto Requerido)
La sección requiere un contexto (`ctx`) que debe contener exactamente estas claves:

- `architect_id`: Identificador único del arquitecto (string, obligatorio)
- `architect_email`: Correo electrónico del arquitecto (string, obligatorio)
- `subscription_active`: Estado de la suscripción (boolean, indica si el arquitecto tiene acceso premium)
- `db`: Módulo de base de datos (objeto `src.db`, obligatorio)

El contexto debe ser validado antes de acceder a la sección. Si falta alguna clave o `architect_id`/`architect_email` están vacíos, se debe denegar el acceso.

## Datos de Salida (Proyectos en Base de Datos)
Los proyectos se almacenan en la tabla `projects` de la base de datos con la siguiente estructura principal:

- `id`: Identificador único del proyecto
- `architect_id`: ID del arquitecto creador
- `title`: Título del proyecto
- `description`: Descripción detallada
- `price`: Precio del proyecto
- `m2_construidos`: Metros cuadrados construidos
- `style`: Estilo arquitectónico
- `location`: Ubicación
- `images`: Lista de URLs de imágenes
- `plans`: Archivos de planos (PDF, CAD)
- `renders_3d`: Renders 3D (OBJ, GLTF, etc.)
- `memoria_constructiva`: Memoria constructiva (PDF)
- `presupuesto`: Presupuesto estimado
- `status`: Estado del proyecto (draft, published, sold)
- `created_at`: Fecha de creación
- `updated_at`: Fecha de última modificación

## Restricciones y Prohibiciones
La sección Arquitectos tiene restricciones estrictas para mantener la integridad del sistema:

### NO debe hacer nunca:
- **Importar lógica de clientes**: No acceder a funciones o datos relacionados con paneles de cliente, compras o reservas.
- **Importar lógica de IA**: No integrar funcionalidades de generación automática de planos o análisis IA.
- **Acceder a session_state global**: No leer o escribir `st.session_state` fuera del flujo controlado de la sección.
- **Cambiar contratos de datos**: No modificar la estructura de datos de proyectos sin una nueva versión documentada.
- **Acceder a otras secciones**: No importar o llamar funciones de módulos de propietarios, intranet o servicios.
- **Almacenar datos sensibles**: No guardar información personal de clientes o datos financieros sin encriptación.

### Solo cambios permitidos:
- Añadir campos opcionales a proyectos (con migración de DB)
- Ajustes menores de UI interna
- Optimizaciones de rendimiento
- Corrección de bugs sin cambiar contratos

## Punto de Entrada
El acceso a la sección debe hacerse exclusivamente a través de:
```python
from modules.marketplace.architects_entry import render_architects_panel
render_architects_panel(ctx)
```

No se permite importar `marketplace_upload.py` directamente desde otras partes del sistema.

## Responsabilidades
- **CORE MARKETPLACE**: Mantenimiento y evolución de la sección Arquitectos
- **Validación de Contexto**: El punto de entrada debe validar el `ctx` antes de proceder
- **Integridad de Datos**: Asegurar que todos los proyectos cumplan con estándares de calidad y formato