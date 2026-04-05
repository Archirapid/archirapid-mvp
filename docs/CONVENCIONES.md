# ArchiRapid — Convenciones de desarrollo

## Commits

- Idioma: **inglés**.
- Prefijos obligatorios:
  - `fix:` — corrección de bug
  - `feat:` — nueva funcionalidad
  - `refactor:` — refactorización sin cambio de comportamiento
  - `docs:` — solo documentación
  - `chore:` — tareas de mantenimiento (deps, config)
- Mensaje descriptivo: explica el *por qué*, no solo el *qué*.
- Co-authored: añadir `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` en commits asistidos por IA.

## Antes de tocar cualquier archivo

1. Leer el archivo completo (o la sección relevante) antes de editar.
2. Verificar que no hay otro archivo que ya haga lo mismo.
3. Si el cambio afecta DB: actualizar schema en **dos sitios** (`db.py` ~613 y ~1352).

## Pruebas

- Probar siempre en local antes de push.
- Para módulos Python puros: test funcional con `python -c "..."` antes de commit.
- Para Babylon.js: verificar sintaxis Python del archivo (template string) con `ast.parse()`.
- No hacer push hasta que Raul confirme que ha probado en local.

## Código

- Type hints en funciones de `utils/` y helpers públicos.
- `try/except` en todas las funciones que llamen a APIs externas o DB.
- No añadir docstrings, comentarios ni type annotations a código no modificado.
- No sobre-ingenierizar: la solución mínima que funciona es la correcta.
- No crear helpers/abstracciones para operaciones de un solo uso.

## Seguridad

- Nunca hardcodear claves API, tokens ni URLs de Stripe en el código.
- Usar `os.getenv()` o `st.secrets` para todos los valores sensibles.
- Rutas de archivos: siempre relativas en DB, nunca absolutas.

## Workflow con Claude

- Rutas exactas siempre en los prompts — no explorar automáticamente.
- Un commit por sprint/tarea atómica.
- Verificar sintaxis antes de cada commit.
- No push hasta orden explícita de Raul.
