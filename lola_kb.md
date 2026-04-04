# ArchiRapid - Base de Conocimientos

INSTRUCCION CRITICA: Lola nunca debe decir que ArchiRapid genera proyectos ejecutables, proyectos listos para construir, ni que sustituye al arquitecto. Si el usuario pregunta si puede construir directamente con el diseno de ArchiRapid, Lola debe responder que el diseno es orientativo y que necesita visado de arquitecto colegiado conforme a la LOE. Siempre mencionar que ArchiRapid ofrece arquitectos y profesionales colaboradores para este paso.

Plataforma PropTech espanola. Conecta propietarios de terrenos, compradores, arquitectos, constructores e inmobiliarias. IA + Catastro + 3D.
URL: https://archirapid.streamlit.app
Contacto: hola@archirapid.com | +34 623 172 704
Direccion: Avda. de Europa 15, 28224 Pozuelo de Alarcon, Madrid.
Soporte: soporte@archirapid.com | Proyectos: proyectos@archirapid.com

## Roles de usuario

- Comprador: navega mapa, ve fincas (sin login), registra para comprar. Compra proyectos arquitectonicos.
- Propietario: sube fincas, recibe propuestas de arquitectos. Comision ArchiRapid 7-10% sobre venta.
- Arquitecto: publica proyectos, usa Modo Estudio IA. Suscripcion mensual.
- Constructor/Profesional: recibe obras compatibles, hace ofertas. Plan gratuito o Destacado.
- Inmobiliaria MLS: red colaborativa de compraventa entre agencias. Trial 30 dias gratis.
- Admin: gestiona aprobaciones, usuarios, datos.

## Funciones principales

MAPA: Mapa interactivo con pins azules (fincas propietarios) y pins naranjas (fincas MLS inmobiliarias). Filtros: min/max m2, provincia, texto.

FINCAS: Click en pin = ficha completa: m2, precio, provincia, tipo suelo (Urbana/Rustica), ref catastral, fotos. Auto-clasificacion suelo via API Catastro.

DISENADOR 3D IA: Introduce datos de finca y presupuesto. IA genera prefiguracion orientativa: plano 2D (SVG), modelo 3D (Babylon.js), presupuesto estimado, memoria descriptiva orientativa PDF. Los documentos generados NO sustituyen al proyecto tecnico visado por arquitecto colegiado.

CASAS PREFABRICADAS: Catalogo desde 45 m2. Materiales: Madera, Acero modular, Hormigon prefab, Mixto.

CALCULADORA HIPOTECA: Amortizacion francesa. Inputs: precio terreno, coste construccion, entrada %, interes, plazo. Resultado: cuota mensual estimada (orientativa, no vinculante).

CONTRATOS: PDF generado con SHA-256 para verificacion de integridad.

## Planes Arquitectos

BASIC: 29 EUR/mes. 1 proyecto activo, Modo Estudio 19 EUR/proyecto, 10% comision.
PRO: 99 EUR/mes. 5 proyectos, Modo Estudio ilimitado, 8% comision, verificado.
PRO ANUAL: 890 EUR/ano (74 EUR/mes, ahorro 298 EUR). Igual que PRO.
ENTERPRISE: 299 EUR/mes. Proyectos ilimitados, 5% comision, soporte prioritario.
Comision: solo si vendes. Si no vendes, no pagas comision.

## Planes Constructores/Profesionales

GRATUITO: 0 EUR. Perfil, tablon de obras, 3 ofertas/mes, proyectos con 24h retraso.
DESTACADO: 99 EUR/30 dias. Ofertas ilimitadas, verificado, primera posicion, notificacion inmediata.
Comision ArchiRapid: 3% sobre contratos adjudicados.
16 especialidades: Constructor general, Estructura, Cimentacion, Cerramientos, Electricas, Fontaneria, Climatizacion, Acabados, Tejados, Sostenibilidad, Direccion obra, Aparejador, Reformas, Prefabricadas, Topografia, BIM.

## Sistema MLS Inmobiliarias

Red colaborativa entre inmobiliarias. Listante = quien pone la finca. Colaboradora = quien trae comprador.
Comision: ArchiRapid cobra 1% fijo. Resto se reparte entre listante y colaboradora.

TRIAL: 30 dias gratis, sin tarjeta, activado al aprobar admin (24-48h habiles).
STARTER: 39 EUR/mes, 15 fincas activas.
AGENCY: 99 EUR/mes, 75 fincas, reservas Stripe (200 EUR).
PRO: 199 EUR/mes, fincas ilimitadas, reservas, soporte prioritario.

Reserva: 200 EUR via Stripe, 72h exclusividad. Se descuenta de comision final.

Flujo 5 pasos: 1) Buscar finca en mercado. 2) Ver ficha profesional (REF, comision %, importe). 3) Reservar para cliente (200 EUR, 72h). 4) Coordinar visita via ArchiRapid (identidad protegida). 5) Cerrar operacion (contrato, deposito, notaria).

Fichas publicas: visibles sin login. Datos del listante NUNCA se exponen publicamente.

## Portal Estudiantes TFG/TFM

Acceso: banner "🎓 Estudiantes" en la home, o URL /?page=estudiantes.
Registro propio con email y contraseña (no necesita cuenta general de ArchiRapid).

FICHA DEL ESTUDIANTE: nombre, teléfono, edad, universidad, curso (1º Grado - Doctorado), año presentación TFG/TFM, ciudad, bio, portfolio/LinkedIn.

SUBIDA DE PROYECTO: título, descripción, tipología (unifamiliar, plurifamiliar, mixto, equipamiento, rehabilitación, urbanismo, etc.), superficie m2, provincia, ciudad, ejecutable (Sí/No/En estudio), precio de venta.

PRECIO RECOMENDADO: 1.900 EUR para TFG estándar. Proyectos con CAD, memoria completa, renders y realidad virtual pueden valorarse más.

ARCHIVOS ACEPTADOS: fotos JPG/PNG (múltiples), planos PDF (obligatorio), memoria PDF, CAD/DWG/DXF/IFC, tour virtual MP4/GLB/GLTF, paquete ZIP.

INGRESOS: 60% para el estudiante, 40% para ArchiRapid. Modalidad exclusiva (una venta) o múltiple (varios compradores).

REVISIÓN: El equipo de ArchiRapid aprueba en 24-48h tras el registro. El proyecto aparece en la plataforma tras aprobación.

AVISO LEGAL: Los proyectos son trabajos académicos orientativos. Cualquier uso constructivo requiere visado de arquitecto colegiado (LOE Ley 38/1999).

## Precios productos (compra proyecto)

Memoria PDF: 1.800 EUR. Planos CAD: 2.500 EUR. Proyecto Completo: 4.000 EUR.
Modelo BIM/IFC: 149 EUR. Certificado Blockchain: 99 EUR. Visado: 500 EUR.
Direccion Obra: 800 EUR. Construccion Completa: 1.500 EUR. Supervision: 300 EUR.
Modo Estudio (descarga): 19 EUR.

## Subida de finca (propietarios)

1. Subir PDF Nota Catastral. 2. IA extrae: ref catastral, m2, municipio. 3. Auto-clasifica Urbana/Rustica via API Catastro. 4. Finca aparece como pin azul en mapa.

## Informacion legal

RGPD: Reglamento UE 2016/679 + LOPDGDD Ley 3/2018. Politica privacidad en la web.
ArchiRapid S.L. (en constitucion).
