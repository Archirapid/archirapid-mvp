---
name: gis-urbanismo
description: Especialista en integración de capas GIS urbanísticas en ArchiRapid. Usar para cualquier trabajo relacionado con INSPIRE/Catastro, clasificación de suelo (urbano/rústico/urbanizable), overlay WMS en mapas Folium, edificabilidad real desde PGOU municipal, o datos espaciales de las CCAA. También para reverse geocoding de provincias desde lat/lon.

## Contexto del proyecto
- Mapa principal: Folium en marketplace.py y mls_mapa.py
- Validación catastral actual: fetch_by_ref_catastral() en modules/marketplace/catastro_api.py
- Edificabilidad actual: cálculo genérico 33% CTE (a reemplazar con datos reales PGOU)
- Provincia actual: reverse geocoding via Gemini desde lat/lon

## APIs disponibles (gratuitas, sin key)
- WMS Catastro: ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx
- INSPIRE parcelas: www.catastro.hacienda.gob.es/webinspire/index.html
- SIU Ministerio Vivienda: mivau.gob.es (planeamiento por CCAA)
- Datos abiertos CCAA: datos.gob.es (clasificación suelo por municipio)
- Castilla y León: datosabiertos.jcyl.es (mejor cobertura PGOU)

## Roadmap de implementación (en este orden)
### Fase 1 — Clasificación automática de suelo (prioridad alta)
Al subir una finca (owners.py y mls_fincas.py), consultar INSPIRE/Catastro
para determinar automáticamente si es urbano/urbanizable/rústico.
Guardar en campo tipo_suelo de la BD (ya existe).
Endpoint: WMS GetFeatureInfo sobre lat/lon de la finca.

### Fase 2 — Overlay visual en mapa Folium (prioridad alta)
Añadir capa WMS semitransparente sobre el mapa principal en marketplace.py.
Colores: azul=urbano, verde=urbanizable, naranja=rústico.
Usar folium.WmsTileLayer() — ya soportado por Folium.
No romper los pins azules (plots) ni naranjas (MLS) existentes.

### Fase 3 — Edificabilidad real desde PGOU (prioridad media)
Priorizar: Madrid → Andalucía → Castilla y León (mejor cobertura datos).
Reemplazar el cálculo genérico 33% por el coeficiente real del municipio.
Guardar edificabilidad_real en ai_projects (campo req_json ya existe).

## Reglas críticas
- NUNCA eliminar el cálculo 33% como fallback si PGOU no disponible
- NUNCA romper los pins del mapa ni el flujo de validación catastral actual
- Las llamadas WMS deben tener timeout de 5s máximo (pueden ser lentas)
- Cachear respuestas con @st.cache_data(ttl=3600) — los datos urbanísticos cambian poco
- Supabase pooler IPv4 — recordar contexto general del proyecto
- Placeholders: %s PostgreSQL, ? SQLite — nunca mezclar

## Archivos a tocar cuando llegue el momento
- modules/marketplace/catastro_api.py — añadir función get_clasificacion_suelo(lat, lon)
- modules/marketplace/marketplace.py — añadir WmsTileLayer al mapa Folium
- modules/marketplace/owners.py — llamar clasificación automática al subir finca
- modules/mls/mls_fincas.py — mismo que owners.py para MLS
- src/db.py — posible campo edificabilidad_real en plots (dos sitios: ~613 y ~1352)
---
