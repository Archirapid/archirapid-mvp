# CLAUDE.md - ArchiRapid (Minimal 2026)

Proyecto: SaaS PropTech Marketplace español para diseño arquitectónico con IA.
Stack principal: Streamlit + Babylon.js 7.x + Supabase (prod) / SQLite (local) + Groq/Gemini.

Archivos clave (solo referencia):
- app.py → router principal + navegación URL ↔ session_state
- src/db.py y src/db_compat.py → capa DB (schema en ~613 y ~1352)
- modules/ai_house_designer/ → todo el diseñador IA (floor_plan_svg.py, babylon_editor.py, constraint_solver.py, cte_checker.py, mep_hs5.py)
- modules/mls/ → módulo inmobiliarias, trials, reservas Stripe
- modules/marketplace/ → mapa, catastro, constructores, contratos PDF + SHA-256

Reglas críticas (NUNCA ignorar):
- Rutas exactas siempre en prompts. No explores automáticamente.
- Archivos pesados (PDF, SVG grandes, GLB si hay): solo path/URL, nunca leer completo.
- DB: usa helpers _read_sql9/_read3 etc. Nunca pd.read_sql_query directo. Placeholders %s (PG) o ? (SQLite) vía wrapper.
- Babylon.js: dispose() para memoria, async donde corresponda, trackea _currentStyle y _basePosData.
- Stripe: usa _get_base_url() de stripe_utils.py. Nunca hardcodear URLs.
- st.stop() nunca dentro de try/except.
- Folium: siempre m.get_root().render() — NO _repr_html_().
- Navegación: sync URL↔session_state en cada rerun.

Delegación recomendada (usa @agent-xxx si disponible):
- @agent-babylon-editor → cambios 3D, meshes, MEP
- @agent-db-migrations → schema, ALTER TABLE en db.py
- @agent-mls-specialist → todo modules/mls/
- @agent-stripe-specialist → Stripe, webhooks, success_url

Convenciones:
- Commits en inglés: fix:, feat:, refactor:
- Type hints + try/except en utils.
- Probar local antes de push.
- Schema BD actualizado en DOS sitios (db.py líneas ~613 y ~1352).

Estado actual y pendientes → consulta archivos específicos o estados en código.
