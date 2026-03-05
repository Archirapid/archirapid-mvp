# BLINDAJE FINAL

Este documento recoge la estrategia de protección que hemos diseñado para
la sección de *Arquitectos* y que puede servir de plantilla para otras partes
de la aplicación.

## 1. Contrato único y módulo aislado

- La funcionalidad de arquitectos debe residir en un paquete dedicado:
  `modules/architects`.
- Exportar una única función pública `run_architects_portal(state)` que reciba
  y devuelva un objeto de estado (`ArchitectState`).
- `ArchitectState` es una dataclass inmutable con los campos mínimos
  necesarios: `logged_in`, `role`, `architect_id`, `architect_plan`, etc.
- El resto de la aplicación (ruteador, otros módulos) sólo conoce este
  contrato; no manipulan directamente `st.session_state`.

## 2. Validaciones y decoradores de guardia

- Definir un decorador `@require_architect` para envolver la entrada del
  portal. Verifica que el estado cumple con las condiciones mínimas y, si no
  es así, muestra un error y termina la ejecución.
- Añadir aserciones internas y mensajes claros sobre invariantes rotas.

## 3. API de acceso a sesión

- Encapsular todas las lecturas/escrituras de `st.session_state` mediante
  funciones (`get_architect_id()`, `set_architect_plan()`, etc.).
- Esto facilita futuros refactorings (p.ej. cambiar la clave usada).

## 4. Cobertura automática de pruebas

- Crear tests unitarios para `run_architects_portal` con estados válidos y
  erróneos.
- Añadir tests de integración que recorran los flujos clave de Streamlit.
- Integrar estos tests en CI; el pipeline debe ejecutarlos cada vez que cualquier
  archivo del repositorio cambie.

## 5. Aislamiento físico y documentación

- Mantener la carpeta `modules/architects` autoconclusiva (con sus propios
  tests y documentación).
- Documentar el flujo en un diagrama (Mermaid o similar) en `docs/`.
- Registrar en el README las reglas de importación y las zonas prohibidas.

## 6. Feature flags y despliegue progresivo

- Introducir banderas en la sesión o en configuración para activar cambios de
  riesgo sólo para determinados usuarios o entornos.
- Permitir volver atrás rápidamente si algo se rompe en producción.

## 7. Monitoreo y alertas

- Instrumentar eventos importantes con logs estructurados.
- Crear un simple health‑check automatizado que ejecute periódicamente el flujo
  de arquitectos y notifique fallos.

## 8. Enfoque general

Aunque el ejemplo está centrado en arquitectos, **la misma arquitectura se puede
aplicar a cualquier otra sección (propietarios, clientes, proveedores, etc.)**.
El objetivo es tener módulos encapsulados con su propio contrato, validaciones,
pruebas y documentación. De este modo, tocar un módulo no rompe los cables de
otro.

---

Este archivo puede descargarse o consultarse siempre que necesites recordar la
estrategia de blindaje.

> **Nota:** la primera vez decíamos ‘blindar arquitectos’ porque era la sección
> problemática, pero la plantilla es universal: se puede duplicar y adaptar para
> cada sub‑sistema de la aplicación.
