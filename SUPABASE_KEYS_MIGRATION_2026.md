# Migración Claves Supabase — 2026-04-13

## Problema
**Fecha**: 2026-03-27 (hace una semana)
- Supabase deshabilitó las legacy API keys (anon, service_role)
- Error: `Legacy API keys are disabled`
- **Causa**: Cambio global de seguridad de Supabase

## Solución
Migrar a nuevas claves: **Publishable** y **Secret**

### Claves Utilizadas (actual)
- **SUPABASE_KEY** (Publishable): `sb_publishable_[REDACTED_IN_GIT]`
  - Uso: Cliente/Frontend (seguro con RLS)
  - Almacenadas: `.env`, `secrets.toml`, Streamlit Cloud secrets
- **SUPABASE_SERVICE_KEY** (Secret): `sb_secret_[REDACTED_IN_GIT]`
  - Uso: Backend/Servidor (acceso completo)
  - Almacenadas: `.env`, `secrets.toml`, Streamlit Cloud secrets

### Archivos Modificados
1. **`.env`** (local):
   ```
   SUPABASE_URL=https://ifmtsaoboxrlucnxxmhw.supabase.co
   SUPABASE_KEY=sb_publishable_[REDACTED_IN_GIT]
   SUPABASE_SERVICE_KEY=sb_secret_[REDACTED_IN_GIT]
   SUPABASE_DB_URL=postgresql://[REDACTED_IN_GIT]@aws-1-eu-central-1.pooler.supabase.com:6543/postgres
   ```

2. **`.streamlit/secrets.toml`** (local):
   ```toml
   SUPABASE_URL = "https://ifmtsaoboxrlucnxxmhw.supabase.co"
   SUPABASE_KEY = "sb_publishable_[REDACTED_IN_GIT]"
   SUPABASE_SERVICE_KEY = "sb_secret_[REDACTED_IN_GIT]"
   SUPABASE_DB_URL = "postgresql://[REDACTED_IN_GIT]@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"
   ```

3. **Streamlit Cloud Secrets** (share.streamlit.io):
   - Settings → Secrets
   - Añadidas las 3 variables arriba
   - Estado: ✅ Activas

### Código Afectado
**Donde se usan las claves:**
- `modules/mls/mls_db.py`: `create_inmo()`, `update_inmo_firma()`
- `modules/mls/mls_portal.py`: bloque post-registro (firma inline)
- `modules/marketplace/intranet.py`: operaciones admin
- Patrón: 
  ```python
  _sb_key = (os.environ.get("SUPABASE_SERVICE_KEY", "") or
             _st.secrets.get("SUPABASE_SERVICE_KEY", ""))
  ```

### Verificación
**Test exitoso (2026-04-13 14:30 UTC):**
```
UPDATE exitoso!
Filas actualizadas: 1
Nueva firma: test_nuevas_claves_2026
```

## ¿Las claves vuelven a cambiar?

**Probabilidad: Baja**
- Supabase cambió una sola vez (2026-03-27) tras años de legacy keys
- Las nuevas claves son estándar (Publishable/Secret)
- No hay indicios de cambios próximos

**Si vuelven a cambiar:**
1. Ir a Supabase dashboard → Settings → API
2. Copiar nuevas claves (Publishable + Secret)
3. Actualizar: `.env`, `secrets.toml`, Streamlit Cloud
4. Test: `python -c "...update..."`

**Escenarios de cambio:**
- Supabase anuncia EOL de keys actuales (publicado en blog)
- Usuario revoca manualmente las keys (precaución de seguridad)
- Fallo de seguridad descubierto (imperativo)

## Seguridad
- ✅ `.env` en `.gitignore` — no sube a GitHub
- ✅ `secrets.toml` en `.gitignore` — no sube a GitHub
- ✅ Streamlit Cloud encripta secrets en tránsito y reposo
- ✅ RLS activo en tablas (cliente no puede leer/escribir sin policies)
- ⚠️ Si secret_key es comprometida: revocar en Supabase (regenera en 5s)

## Referencias
- Supabase Docs: https://supabase.com/docs/guides/api/rest/authentication
- Dashboard: https://supabase.com → [proyecto] → Settings → API
