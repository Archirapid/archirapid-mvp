import streamlit as st
import json
import os
from dotenv import load_dotenv
from groq import Groq

from .data_model import create_example_design, HouseDesign, Plot, RoomType, RoomInstance

# ================================================
# GENERADOR ZIP COMPLETO DEL PROYECTO
# ================================================
def generar_zip_proyecto(req, design_data, plot_data, partidas, subsidy_total, energy_label):
    import io, zipfile, json
    from datetime import datetime
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    zip_buffer = io.BytesIO()
    fecha = datetime.now().strftime("%Y-%m-%d")
    proyecto_nombre = f"ArchiRapid_{plot_data.get('title','Proyecto').replace(' ','_')}_{fecha}"
    total_cost = design_data.get('total_cost', 0)
    total_area = design_data.get('total_area', 0)
    style = req.get('style', 'Moderno')
    rooms = design_data.get('rooms', [])

    # ----------------------------------------
    # GENERAR MEMORIA COMPLETA CON GROQ
    # ----------------------------------------
    memoria_ia = ""
    try:
        from groq import Groq as _Groq
        from pathlib import Path as _Path
        from dotenv import load_dotenv as _load_dotenv
        import os as _os
        _load_dotenv(dotenv_path=_Path(__file__).parent.parent.parent / '.env')
        _client = _Groq(api_key=_os.getenv("GROQ_API_KEY"))

        habitaciones_list = "\n".join([f"- {r['name']}: {r['area_m2']:.1f} m²" for r in rooms])
        extras_list = [k for k, v in req.get('extras', {}).items() if v]
        energy_list = [k for k, v in req.get('energy', {}).items() if v]

        prompt_memoria = f"""Eres un arquitecto técnico español experto en redacción de proyectos básicos de vivienda unifamiliar.
Redacta una MEMORIA DESCRIPTIVA Y CONSTRUCTIVA profesional y detallada para el siguiente proyecto.
Usa terminología técnica arquitectónica española. Sé específico y profesional.
Al final de cada sección importante añade esta nota: "[MVP ArchiRapid: sección orientativa, requiere desarrollo completo por arquitecto colegiado]"

DATOS DEL PROYECTO:
- Parcela: {plot_data.get('title','N/A')} | Ref. catastral: {plot_data.get('catastral_ref','N/A')}
- Superficie parcela: {plot_data.get('total_m2',0):.0f} m² | Edificable: {plot_data.get('buildable_m2',0):.0f} m²
- Ubicación: Lat {plot_data.get('lat','N/A')}, Lon {plot_data.get('lon','N/A')}
- Superficie construida: {total_area:.1f} m²
- Estilo arquitectónico: {style}
- Tipo cimentación: {req.get('foundation_type','zapatas corridas')}
- Tipo cubierta: {req.get('roof_type','a dos aguas')}
- Calificación energética: {energy_label}
- Dormitorios: {req.get('bedrooms',3)} | Baños: {req.get('bathrooms',2)}
- Extras: {', '.join(extras_list) if extras_list else 'ninguno'}
- Sistemas sostenibles: {', '.join(energy_list) if energy_list else 'ninguno'}

DISTRIBUCIÓN DE ESPACIOS:
{habitaciones_list}
TOTAL: {total_area:.1f} m²

Redacta EXACTAMENTE estas secciones con el nivel de detalle de un proyecto básico real:

1. MEMORIA DESCRIPTIVA
1.1. AGENTES (promotor: datos del cliente ArchiRapid, proyectista: ArchiRapid IA + arquitecto colegiado pendiente de visado)
1.2. INFORMACIÓN PREVIA Y EMPLAZAMIENTO (describe la parcela, entorno, accesos, orientación sur)
1.3. DESCRIPCIÓN DEL PROYECTO (objeto, programa de necesidades, solución adoptada, descripción general)
1.4. CUADRO DE SUPERFICIES (tabla con todas las estancias y sus m²)
1.5. PRESTACIONES CTE (HE ahorro energía, HS salubridad, SE seguridad estructural, SI incendio, SUA accesibilidad)

2. MEMORIA CONSTRUCTIVA
2.1. SUSTENTACIÓN Y CIMENTACIÓN (describe el tipo elegido: {req.get('foundation_type','zapatas')})
2.2. SISTEMA ESTRUCTURAL (hormigón armado, muros de carga según estilo {style})
2.3. SISTEMA ENVOLVENTE (cubierta {req.get('roof_type','dos aguas')}, fachadas estilo {style}, carpintería exterior)
2.4. PARTICIONES INTERIORES Y ACABADOS
2.5. INSTALACIONES PREVISTAS (fontanería, electricidad, climatización, {'paneles solares, ' if req.get('energy',{}).get('solar') else ''}{'aerotermia, ' if req.get('energy',{}).get('aerotermia') else ''}saneamiento)

3. CUMPLIMIENTO NORMATIVA
3.1. CTE DB-HE AHORRO DE ENERGÍA (calificación {energy_label})
3.2. CTE DB-HS SALUBRIDAD
3.3. CTE DB-SE SEGURIDAD ESTRUCTURAL  
3.4. NORMATIVA URBANÍSTICA (edificabilidad 33%, retranqueos, alturas)

Máximo 1800 palabras. Profesional, técnico, directo."""

        _resp = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_memoria}],
            temperature=0.2,
            max_tokens=2500
        )
        memoria_ia = _resp.choices[0].message.content.strip()
    except Exception as _e:
        memoria_ia = f"[Memoria IA no disponible: {_e}. Ver datos en 03_Datos_Proyecto.json]"

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

        # ── 1. MEMORIA COMPLETA PDF ───────────────────────────
        solar_si    = 'Sí' if req.get('energy', {}).get('solar') else 'No'
        aero_si     = 'Sí' if req.get('energy', {}).get('aerotermia') else 'No'
        geo_si      = 'Sí' if req.get('energy', {}).get('geotermia') else 'No'
        insul_si    = 'Sí' if req.get('energy', {}).get('insulation') else 'No'
        rain_si     = 'Sí' if req.get('energy', {}).get('rainwater') else 'No'
        domo_si     = 'Sí' if req.get('energy', {}).get('domotic') else 'No'

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.colors import HexColor, white
            from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                            Table, TableStyle, PageBreak)
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

            pdf_buf = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buf, pagesize=A4,
                rightMargin=2*cm, leftMargin=2*cm,
                topMargin=2.5*cm, bottomMargin=2*cm)

            C_DARK  = HexColor('#1A252F')
            C_BLUE  = HexColor('#2C3E50')
            C_GREEN = HexColor('#27AE60')
            C_ORA   = HexColor('#E67E22')
            C_LIGHT = HexColor('#ECF0F1')
            C_MVP   = HexColor('#9B59B6')
            C_GREY  = HexColor('#7F8C8D')
            C_ROW   = HexColor('#F8F9FA')

            SS = getSampleStyleSheet()
            def sty(name, **kw):
                return ParagraphStyle(name, parent=SS['Normal'], **kw)

            s_body  = sty('body',  fontSize=9.5, leading=14,  spaceAfter=5,  alignment=TA_JUSTIFY, textColor=C_BLUE)
            s_h1    = sty('h1',    fontSize=13,  fontName='Helvetica-Bold', spaceBefore=12, spaceAfter=5, textColor=white)
            s_h2    = sty('h2',    fontSize=10.5,fontName='Helvetica-Bold', spaceBefore=8,  spaceAfter=3, textColor=C_BLUE)
            s_mvp   = sty('mvp',   fontSize=8,   fontName='Helvetica-Oblique', textColor=C_MVP, leftIndent=8, spaceAfter=8)
            s_aviso = sty('aviso', fontSize=9,   fontName='Helvetica-Bold',    textColor=C_ORA, alignment=TA_CENTER)
            s_small = sty('small', fontSize=8,   textColor=C_GREY, alignment=TA_CENTER)
            s_ctr   = sty('ctr',   fontSize=14,  fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=C_DARK, spaceAfter=6)
            s_sub   = sty('sub',   fontSize=11,  alignment=TA_CENTER, textColor=C_BLUE, spaceAfter=4)

            story = []

            # ── PORTADA
            story.append(Spacer(1, 1*cm))
            hdr = Table([[Paragraph('<font color="white"><b>ArchiRapid</b> — Proyecto de Vivienda</font>',
                          sty('ph', fontSize=18, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=white))]],
                        colWidths=[17*cm])
            hdr.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C_DARK),('ROWPADDING',(0,0),(-1,-1),18)]))
            story.append(hdr)
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph('PROYECTO BÁSICO DE VIVIENDA UNIFAMILIAR', s_ctr))
            story.append(Paragraph(plot_data.get('title','Parcela').upper(), s_sub))
            story.append(Paragraph(f"Ref. Catastral: {plot_data.get('catastral_ref','N/A')}", s_small))
            story.append(Spacer(1, 0.5*cm))

            kpis = [
                ['SUPERFICIE', 'PRESUPUESTO', 'CALIF. ENERGÉTICA', 'ESTILO'],
                [f"{total_area:.0f} m²", f"€{total_cost:,}", energy_label, style],
            ]
            tk = Table(kpis, colWidths=[4.25*cm]*4)
            tk.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),C_BLUE),('TEXTCOLOR',(0,0),(-1,0),white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
                ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,1),(-1,1),13),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ROWPADDING',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.4,C_LIGHT),
            ]))
            story.append(tk)
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph(f"Generado por ArchiRapid MVP | {fecha} | www.archirapid.es", s_small))
            story.append(Paragraph("⚠️ DOCUMENTO ORIENTATIVO — Requiere visado por arquitecto colegiado", s_aviso))
            story.append(PageBreak())

            # ── ÍNDICE
            def sec_header(txt):
                t = Table([[Paragraph(f'<font color="white"><b>{txt}</b></font>',
                    sty('sh', fontSize=11, fontName='Helvetica-Bold', textColor=white))]],
                    colWidths=[17*cm])
                t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C_BLUE),('ROWPADDING',(0,0),(-1,-1),8)]))
                return t

            idx_rows = [
                ['ÍNDICE',''],
                ['I.   Memoria Descriptiva','3'],
                ['II.  Memoria Constructiva','4'],
                ['III. Cumplimiento CTE','5'],
                ['IV.  Cuadro de Superficies','6'],
                ['V.   Presupuesto por Partidas','7'],
                ['VI.  Eficiencia Energética','8'],
                ['VII. Sistemas Sostenibles','9'],
                ['VIII.Vistas 3D (archivos adjuntos)','—'],
                ['IX.  Aviso Legal MVP','—'],
            ]
            ti = Table(idx_rows, colWidths=[14*cm, 3*cm])
            ti.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),C_DARK),('TEXTCOLOR',(0,0),(-1,0),white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),
                ('ROWPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.3,C_LIGHT),
                ('ALIGN',(1,0),(1,-1),'CENTER'),
            ]))
            story.append(ti)
            story.append(PageBreak())

            # ── CUERPO IA
            if memoria_ia:
                for linea in memoria_ia.split('\n'):
                    l = linea.strip()
                    if not l:
                        story.append(Spacer(1,0.15*cm))
                    elif l.startswith('[MVP'):
                        story.append(Paragraph(l, s_mvp))
                    elif (l[:2] in ('1.','2.','3.') and len(l)>3):
                        story.append(Spacer(1,0.2*cm))
                        story.append(sec_header(l))
                        story.append(Spacer(1,0.1*cm))
                    elif l[:4].replace('.','').isdigit() and '.' in l[:5]:
                        story.append(Paragraph(f'<b>{l}</b>', s_h2))
                    else:
                        story.append(Paragraph(l, s_body))
            story.append(PageBreak())

            # ── CUADRO SUPERFICIES
            story.append(sec_header('IV. CUADRO DE SUPERFICIES'))
            story.append(Spacer(1,0.2*cm))
            sup_h = [['ESTANCIA','USO','m²']]
            for r in rooms:
                c = r.get('code','').lower()
                uso = ('Húmedo' if any(x in c for x in ['bano','aseo'])
                  else 'Noche'   if 'dorm' in c
                  else 'Día'     if any(x in c for x in ['salon','cocina','comedor'])
                  else 'Servicio' if any(x in c for x in ['garaje','garage'])
                  else 'Exterior' if any(x in c for x in ['porche','terraza'])
                  else 'Auxiliar')
                sup_h.append([r['name'], uso, f"{r['area_m2']:.1f}"])
            sup_h += [['','',''],
                      ['TOTAL CONSTRUIDO','',f'{total_area:.1f} m²'],
                      ['Máx. edificable','' ,f"{plot_data.get('buildable_m2',0):.0f} m²"],
                      ['Ocupación edificable','',
                       f"{(total_area/max(plot_data.get('buildable_m2',1),1)*100):.1f}%"]]
            ts = Table(sup_h, colWidths=[9*cm,4.5*cm,3.5*cm])
            ts.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),C_DARK),('TEXTCOLOR',(0,0),(-1,0),white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
                ('ROWPADDING',(0,0),(-1,-1),5),('GRID',(0,0),(-1,-1),0.3,C_LIGHT),
                ('BACKGROUND',(0,-3),(-1,-1),C_LIGHT),('FONTNAME',(0,-3),(-1,-1),'Helvetica-Bold'),
                ('ROWBACKGROUNDS',(0,1),(-1,-4),[white,C_ROW]),
            ]))
            story.append(ts)
            story.append(Paragraph('[MVP: superficies orientativas. El proyecto definitivo incluirá superficies útiles, construidas y computables según normativa municipal aplicable]', s_mvp))
            story.append(PageBreak())

            # ── PRESUPUESTO
            story.append(sec_header('V. PRESUPUESTO POR PARTIDAS'))
            story.append(Spacer(1,0.2*cm))
            pr_h = [['PARTIDA','COSTE','%','DESCRIPCIÓN']]
            for p in partidas:
                pr_h.append([p[0],p[1],p[2],p[3]])
            pr_h += [['','','',''],
                     ['TOTAL EJECUCIÓN MATERIAL',f'€{total_cost:,}','100%',''],
                     ['Subvenciones estimadas',f'-€{subsidy_total:,}','','IDAE + CCAA'],
                     ['COSTE NETO',f'€{total_cost-subsidy_total:,}','','']]
            tp = Table(pr_h, colWidths=[6*cm,3*cm,2*cm,6*cm])
            tp.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),C_DARK),('TEXTCOLOR',(0,0),(-1,0),white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),
                ('ROWPADDING',(0,0),(-1,-1),5),('GRID',(0,0),(-1,-1),0.3,C_LIGHT),
                ('BACKGROUND',(0,-3),(-1,-1),C_LIGHT),('FONTNAME',(0,-3),(-1,-1),'Helvetica-Bold'),
                ('ROWBACKGROUNDS',(0,1),(-1,-4),[white,C_ROW]),
            ]))
            story.append(tp)
            story.append(Paragraph('[MVP: presupuesto estimativo a €1.500/m². El definitivo requiere mediciones detalladas por aparejador colegiado]', s_mvp))
            story.append(PageBreak())

            # ── EFICIENCIA ENERGÉTICA
            story.append(sec_header('VI. EFICIENCIA ENERGÉTICA'))
            story.append(Spacer(1,0.3*cm))
            letra = energy_label if energy_label else 'B'
            colores_ee = {'A':'#2ECC71','B':'#27AE60','C':'#F39C12','D':'#E74C3C','E':'#C0392B'}
            col_ee = HexColor(colores_ee.get(letra,'#27AE60'))
            ee_rows = [
                ['Calificación Energética', letra],
                ['Zona Climática (estimada)','D3 — Clima mediterráneo interior'],
                ['Demanda calefacción (est.)','≤ 30 kWh/m²·año'],
                ['Demanda refrigeración (est.)','≤ 15 kWh/m²·año'],
                ['Emisiones CO₂ (est.)','< 10 kg CO₂/m²·año'],
                ['Aislamiento fachada','≥ 8 cm poliestireno expandido'],
                ['Carpintería exterior','Aluminio RPT + doble acristalamiento bajo emisivo'],
                ['Paneles solares',solar_si],
                ['Aerotermia',aero_si],
                ['Geotermia',geo_si],
                ['Aislamiento reforzado',insul_si],
                ['Recogida agua de lluvia',rain_si],
                ['Domótica / gestión energética',domo_si],
            ]
            tee = Table(ee_rows, colWidths=[10*cm,7*cm])
            tee.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(0,-1),C_LIGHT),
                ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
                ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,-1),9),
                ('ROWPADDING',(0,0),(-1,-1),6),
                ('GRID',(0,0),(-1,-1),0.3,C_LIGHT),
                ('BACKGROUND',(1,0),(1,0),col_ee),
                ('TEXTCOLOR',(1,0),(1,0),white),
                ('FONTNAME',(1,0),(1,0),'Helvetica-Bold'),
                ('FONTSIZE',(1,0),(1,0),22),
                ('ALIGN',(1,0),(1,0),'CENTER'),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,C_ROW]),
            ]))
            story.append(tee)
            story.append(Spacer(1,0.3*cm))
            story.append(Paragraph('[MVP: certificación energética orientativa calculada por IA. La CEE oficial requiere software reconocido (HULC/CE3X) y técnico competente habilitado]', s_mvp))
            story.append(PageBreak())

            # ── SISTEMAS SOSTENIBLES
            story.append(sec_header('VII. SISTEMAS SOSTENIBLES Y EXTRAS'))
            story.append(Spacer(1,0.3*cm))
            extras_list2 = [k for k, v in req.get('extras', {}).items() if v]
            sos_rows = [['SISTEMA','INCLUIDO','DESCRIPCIÓN']]
            sos_items = [
                ('Paneles Solares Fotovoltaicos', solar_si,
                 f"Orientación Sur 30°. Potencia estimada: {int(total_area*0.05):.0f} kWp"),
                ('Aerotermia', aero_si,
                 'Bomba de calor aire-agua. COP estimado 3.5. Calefacción + ACS'),
                ('Geotermia', geo_si,
                 'Captación geotérmica horizontal. Altísima eficiencia estacional'),
                ('Aislamiento Reforzado', insul_si,
                 'Fachada ventilada + SATE. U ≤ 0.25 W/m²K'),
                ('Recogida Agua de Lluvia', rain_si,
                 f"Depósito estimado {int(plot_data.get('total_m2',200)*0.1):.0f} litros. Riego y usos no potables"),
                ('Domótica', domo_si,
                 'Control inteligente climatización, iluminación y seguridad'),
            ]
            for nom, inc, desc in sos_items:
                color_inc = C_GREEN if inc == 'Sí' else C_GREY
                sos_rows.append([nom, inc, desc])
            tsos = Table(sos_rows, colWidths=[5*cm,2.5*cm,9.5*cm])
            tsos.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),C_DARK),('TEXTCOLOR',(0,0),(-1,0),white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),
                ('ROWPADDING',(0,0),(-1,-1),6),('GRID',(0,0),(-1,-1),0.3,C_LIGHT),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,C_ROW]),
                ('ALIGN',(1,0),(1,-1),'CENTER'),
            ]))
            story.append(tsos)
            if extras_list2:
                story.append(Spacer(1,0.3*cm))
                story.append(Paragraph(f'<b>Extras incluidos:</b> {", ".join(extras_list2)}', s_body))
            story.append(Paragraph('[MVP: sistemas orientativos. Dimensionado definitivo requiere proyecto de instalaciones por ingeniero especialista]', s_mvp))
            story.append(PageBreak())

            # ── PLANO 2D EMBEBIDO
            import streamlit as _st2
            plano_bytes = (_st2.session_state.get('final_floor_plan')
                        or _st2.session_state.get('current_floor_plan'))
            if plano_bytes:
                try:
                    from reportlab.platypus import Image as RLImage
                    from reportlab.lib.units import cm
                    import io as _io2
                    story.append(sec_header('VIII. PLANO DE DISTRIBUCIÓN EN PLANTA'))
                    story.append(Spacer(1, 0.3*cm))
                    story.append(Paragraph(
                        'Plano de distribución generado automáticamente. '
                        'El proyecto de ejecución incluirá planta acotada, '
                        'alzados N/S/E/O, secciones y detalles constructivos a escala.',
                        s_body))
                    story.append(Spacer(1, 0.2*cm))
                    img_buf = _io2.BytesIO(plano_bytes)
                    rl_img = RLImage(img_buf, width=16*cm, height=12*cm,
                                     kind='proportional')
                    story.append(rl_img)
                    story.append(Spacer(1, 0.2*cm))
                    story.append(Paragraph(
                        '[MVP ArchiRapid: plano orientativo generado por IA. '
                        'El proyecto definitivo incluirá planos técnicos visados '
                        'a escala 1:50 / 1:100 con cotas, superficies y referencias]',
                        s_mvp))
                    story.append(PageBreak())
                except Exception as _img_e:
                    story.append(Paragraph(
                        f'[Plano no disponible en PDF: {_img_e}. Ver 04_Plano_2D.png adjunto]',
                        s_mvp))

            # ── AVISO LEGAL
            story.append(sec_header('IX. AVISO LEGAL — DOCUMENTO MVP'))
            story.append(Spacer(1,0.3*cm))
            aviso_txt = """
<b>Este documento ha sido generado automáticamente por ArchiRapid (MVP v2.1)</b>
mediante inteligencia artificial a partir de los datos del usuario.<br/><br/>
<b>NO tiene validez legal</b> para presentación ante el Ayuntamiento, Colegio de
Arquitectos ni para inicio de obra sin revisión y <b>visado por arquitecto colegiado</b>.<br/><br/>
Tiene carácter <b>orientativo y comercial</b>, destinado a mostrar las capacidades del
sistema y servir de base de trabajo para el arquitecto que desarrolle el proyecto definitivo.<br/><br/>
<b>Cuando el sistema esté completamente operativo incluirá:</b><br/>
- Planos técnicos a escala: planta acotada, alzados N/S/E/O, secciones, detalles constructivos<br/>
- Pliego de condiciones técnicas completo<br/>
- Estado de mediciones por unidades de obra (m³ hormigón, m² enfoscado, ml cerrajería...)<br/>
- Estudio geotécnico y levantamiento topográfico<br/>
- Estudio básico de seguridad y salud<br/>
- Proyectos de instalaciones: electricidad BT, fontanería, climatización, telecomunicaciones<br/>
- Certificado de eficiencia energética oficial (HULC/CE3X)<br/>
- Libro del edificio y plan de mantenimiento<br/><br/>
<b>ArchiRapid | www.archirapid.es | info@archirrapid.es</b>
"""
            av_t = Table([[Paragraph(aviso_txt, sty('avb', fontSize=9, textColor=C_DARK,
                           leading=13))]],colWidths=[17*cm])
            av_t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),HexColor('#FEF9E7')),
                ('BOX',(0,0),(-1,-1),1.5,C_ORA),
                ('ROWPADDING',(0,0),(-1,-1),16),
            ]))
            story.append(av_t)

            doc.build(story)
            zf.writestr(f"{proyecto_nombre}/01_MEMORIA_PROYECTO.pdf", pdf_buf.getvalue())

        except ImportError:
            hab_txt = "\n".join([f"  - {r['name']}: {r['area_m2']:.1f} m²" for r in rooms])
            zf.writestr(f"{proyecto_nombre}/01_Memoria_Descriptiva.txt",
                f"MEMORIA DESCRIPTIVA\nArchiRapid MVP | {fecha}\n\n{memoria_ia}\n\nSUPERFICIES:\n{hab_txt}\nTOTAL: {total_area:.1f} m²\n\nINSTALAR: pip install reportlab")
        except Exception as _pdf_e:
            zf.writestr(f"{proyecto_nombre}/01_Memoria_Error.txt",
                f"Error PDF: {_pdf_e}\n\n{memoria_ia}")


        # 2. ESTADO DE MEDICIONES — Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Mediciones y Presupuesto"
        hf = Font(bold=True, color="FFFFFF", size=11)
        hfill = PatternFill("solid", fgColor="1A252F")
        tfill = PatternFill("solid", fgColor="27AE60")

        ws.merge_cells("A1:F1")
        ws["A1"] = f"ESTADO DE MEDICIONES — {plot_data.get('title','Proyecto').upper()} | ArchiRapid MVP"
        ws["A1"].font = Font(bold=True, size=13, color="FFFFFF")
        ws["A1"].fill = hfill
        ws["A1"].alignment = Alignment(horizontal="center")
        ws.merge_cells("A2:F2")
        ws["A2"] = f"Ref: {plot_data.get('catastral_ref','N/A')} | {total_area:.0f} m² | {style} | {fecha}"
        ws["A2"].alignment = Alignment(horizontal="center")

        ws.merge_cells("A4:F4")
        ws["A4"] = "DISTRIBUCIÓN DE ESPACIOS"
        ws["A4"].font = Font(bold=True, color="FFFFFF")
        ws["A4"].fill = PatternFill("solid", fgColor="2C3E50")

        for col, h in enumerate(["Espacio","Código","Área (m²)","Ancho (m)","Fondo (m)","€/m²"], 1):
            c = ws.cell(row=5, column=col, value=h)
            c.font = hf; c.fill = hfill

        for ri, r in enumerate(rooms, 6):
            ws.cell(row=ri, column=1, value=r['name'])
            ws.cell(row=ri, column=2, value=r.get('code',''))
            ws.cell(row=ri, column=3, value=round(r['area_m2'],1))
            ws.cell(row=ri, column=4, value=round(r.get('width',0),2))
            ws.cell(row=ri, column=5, value=round(r.get('depth',0),2))
            ws.cell(row=ri, column=6, value=1500)

        rt = len(rooms)+6
        ws.cell(row=rt, column=1, value="TOTAL").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rt, column=1).fill = tfill
        ws.cell(row=rt, column=3, value=round(total_area,1)).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rt, column=3).fill = tfill

        rp = rt+3
        ws.merge_cells(f"A{rp}:F{rp}")
        ws.cell(row=rp, column=1, value="PARTIDAS PRESUPUESTARIAS").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rp, column=1).fill = PatternFill("solid", fgColor="2C3E50")
        for col, h in enumerate(["Partida","Coste","% Total","Descripción","",""], 1):
            c = ws.cell(row=rp+1, column=col, value=h)
            c.font = hf; c.fill = hfill
        for ri2, (partida, coste, pct, desc) in enumerate(partidas, rp+2):
            ws.cell(row=ri2, column=1, value=partida)
            ws.cell(row=ri2, column=2, value=coste)
            ws.cell(row=ri2, column=3, value=pct)
            ws.cell(row=ri2, column=4, value=desc)
        rf = rp+2+len(partidas)
        ws.cell(row=rf, column=1, value="TOTAL").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rf, column=1).fill = tfill
        ws.cell(row=rf, column=2, value=f"€{total_cost:,}").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rf, column=2).fill = tfill
        ws.cell(row=rf+1, column=1, value="Subvenciones")
        ws.cell(row=rf+1, column=2, value=f"-€{subsidy_total:,}")
        ws.cell(row=rf+2, column=1, value="COSTE NETO").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rf+2, column=1).fill = tfill
        ws.cell(row=rf+2, column=2, value=f"€{total_cost-subsidy_total:,}").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=rf+2, column=2).fill = tfill
        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['D'].width = 40

        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        zf.writestr(f"{proyecto_nombre}/02_Mediciones_Presupuesto.xlsx", excel_buffer.getvalue())

        # 3. DATOS COMPLETOS JSON
        catastro_data = {
            "proyecto": proyecto_nombre, "fecha": fecha,
            "parcela": {
                "ref_catastral": plot_data.get('catastral_ref','N/A'),
                "descripcion": plot_data.get('title','N/A'),
                "superficie_total_m2": plot_data.get('total_m2',0),
                "edificable_m2": plot_data.get('buildable_m2',0),
                "lat": plot_data.get('lat','N/A'), "lon": plot_data.get('lon','N/A')
            },
            "vivienda": {
                "superficie_m2": total_area, "estilo": style,
                "dormitorios": req.get('bedrooms',0), "banos": req.get('bathrooms',0),
                "calificacion_energetica": energy_label,
                "cimientos": req.get('foundation_type','N/A'),
                "tejado": req.get('roof_type','N/A')
            },
            "presupuesto": {
                "total": total_cost, "subvenciones": subsidy_total,
                "neto": total_cost-subsidy_total, "coste_m2": 1500
            },
            "habitaciones": [{"nombre": r['name'], "codigo": r.get('code',''), "area_m2": r['area_m2']} for r in rooms],
            "sostenibilidad": req.get('energy', {}),
            "aviso": "MVP ArchiRapid. Requiere validacion arquitecto colegiado."
        }
        zf.writestr(f"{proyecto_nombre}/03_Datos_Proyecto.json", json.dumps(catastro_data, ensure_ascii=False, indent=2))

        # 4. PLANO PNG
        import streamlit as _st
        plano = _st.session_state.get('current_floor_plan') or _st.session_state.get('final_floor_plan')
        if plano:
            zf.writestr(f"{proyecto_nombre}/04_Plano_2D.png", plano)

        # 5. VISTAS 3D BABYLON — capturas de perspectivas
        vistas_3d = _st.session_state.get('babylon_captures', {})
        if vistas_3d:
            nombres_legibles = {
                'sur_fachada_principal': '05a_Vista_Sur_Fachada_Principal.png',
                'norte':                 '05b_Vista_Norte.png',
                'este':                  '05c_Vista_Este.png',
                'oeste':                 '05d_Vista_Oeste.png',
                'planta_cenital':        '05e_Vista_Planta_Cenital.png',
            }
            for key, filename in nombres_legibles.items():
                if key in vistas_3d:
                    # Las capturas llegan como data:image/png;base64,...
                    img_data = vistas_3d[key]
                    if ',' in img_data:
                        img_data = img_data.split(',')[1]
                    import base64 as _b64
                    try:
                        zf.writestr(
                            f"{proyecto_nombre}/Vistas_3D/{filename}",
                            _b64.b64decode(img_data)
                        )
                    except Exception:
                        pass
        else:
            # Nota explicativa si no hay capturas
            zf.writestr(
                f"{proyecto_nombre}/Vistas_3D/INSTRUCCIONES.txt",
                "Para incluir las vistas 3D en el ZIP:\n"
                "1. Abre el Editor 3D (Paso 3)\n"
                "2. Pulsa el boton '📸 Capturar Vistas' en la barra de herramientas\n"
                "3. Espera el mensaje de confirmacion\n"
                "4. Vuelve a Documentacion y descarga el ZIP\n"
            )

        # 6. LAYOUT BABYLON JSON
        babylon_layout = _st.session_state.get('babylon_modified_layout')
        if babylon_layout:
            zf.writestr(f"{proyecto_nombre}/06_Layout_3D_Editable.json",
                json.dumps(babylon_layout, ensure_ascii=False, indent=2))

        # 6. README
        zf.writestr(f"{proyecto_nombre}/LEEME.txt", f"""PAQUETE DOCUMENTAL — {proyecto_nombre}
ArchiRapid MVP | {fecha}

CONTENIDO:
  01_Memoria_Descriptiva.txt       — Memoria proyecto básico
  02_Mediciones_Presupuesto.xlsx   — Mediciones y partidas presupuestarias
  03_Datos_Proyecto.json           — Datos completos (catastro, vivienda, costes)
  04_Plano_2D.png                  — Plano distribución en planta
  05_Layout_3D.json                — Modelo 3D editable (si fue modificado)

PRÓXIMOS PASOS:
  1. Arquitecto colegiado para visado
  2. Estudio geotécnico del terreno
  3. Proyecto Básico al Ayuntamiento
  4. Proyecto de Ejecución completo
  5. Contrato constructor

AVISO LEGAL: MVP orientativo. Sin validez legal sin firma de arquitecto colegiado.
www.archirapid.es | info@archirapid.es
""" )

    zip_buffer.seek(0)
    return zip_buffer.getvalue(), f"{proyecto_nombre}.zip"

# ---------------------------------------------------------------------------
# CONSTANTES REUTILIZABLES
# ---------------------------------------------------------------------------
PANEL_MIN_M2 = 3



# ============================================================
# FUENTE ÚNICA DE VERDAD - ARQUITECTURA CENTRALIZADA
# ============================================================

def get_current_design_data():
    """
    Retorna los datos del diseño actual desde la fuente correcta.
    ORDEN DE PRIORIDAD:
    1. babylon_modified_layout (si existe) - diseño editado en 3D
    2. ai_room_proposal - diseño inicial de la IA
    """
    COST_PER_M2 = 1500
    
    # 1. Intentar cargar desde Babylon (prioridad)
    babylon_data = st.session_state.get("babylon_modified_layout")
    
    if babylon_data:
        rooms = []
        total_area = 0
        for room in babylon_data:
            try:
                area = float(room.get('new_area', room.get('original_area', 10)))
                total_area += area
                rooms.append({
                    'name': room.get('name', 'Espacio'),
                    'code': room.get('code', room.get('name', 'generic')),
                    'area_m2': area,
                    'x': room.get('x', 0),
                    'z': room.get('z', 0),
                    'width': room.get('width', 0),
                    'depth': room.get('depth', 0)
                })
            except (ValueError, TypeError):
                continue
        return {
            'rooms': rooms,
            'total_area': round(total_area, 1),
            'total_cost': int(total_area * COST_PER_M2),
            'cost_per_m2': COST_PER_M2,
            'source': 'babylon',
            'modified': True
        }
    
    # 2. Si no hay Babylon, usar propuesta IA
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if proposal:
        rooms = []
        total_area = 0
        for code, area in proposal.items():
            try:
                area_float = float(area) if isinstance(area, (str, int, float)) else 10
                total_area += area_float
                rooms.append({
                    'name': code,
                    'code': code,
                    'area_m2': area_float
                })
            except (ValueError, TypeError):
                continue
        return {
            'rooms': rooms,
            'total_area': round(total_area, 1),
            'total_cost': int(total_area * COST_PER_M2),
            'cost_per_m2': COST_PER_M2,
            'source': 'ai_proposal',
            'modified': False
        }
    
    # 3. Fallback
    return {
        'rooms': [],
        'total_area': 0,
        'total_cost': 0,
        'cost_per_m2': COST_PER_M2,
        'source': 'none',
        'modified': False
    }


def main():
    # ============================================
    # 🔗 CONEXIÓN CON DATOS DE LA FINCA COMPRADA
    # ============================================
    
    # Obtener ID de la finca si viene del panel de cliente
    design_plot_id = st.session_state.get("design_plot_id")
    
    if design_plot_id:
        # Consultar datos de la finca en la BD
        try:
            from modules.marketplace.utils import db_conn
            conn = db_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, catastral_ref, m2, superficie_edificable, 
                       lat, lon, owner_email
                FROM plots 
                WHERE id = ?
            """, (design_plot_id,))
            
            plot_row = cursor.fetchone()
            conn.close()
            
            if plot_row:
                # Guardar datos de la parcela en session_state
                st.session_state["design_plot_data"] = {
                    'id': plot_row[0],
                    'title': plot_row[1],
                    'catastral_ref': plot_row[2],
                    'total_m2': plot_row[3] or 0,
                    'buildable_m2': (plot_row[3] * 0.33) if plot_row[3] else 0,
                    'lat': plot_row[5],
                    'lon': plot_row[6],
                    'owner_email': plot_row[7]
                }
                
                # Pre-configurar superficie objetivo según edificabilidad
                if "ai_house_requirements" not in st.session_state:
                    max_buildable = st.session_state["design_plot_data"]['buildable_m2']
                    st.session_state["ai_house_requirements"] = {
                        "target_area_m2": min(120.0, max_buildable),  # 120m² o el máximo edificable
                        "max_buildable_m2": max_buildable,  # NUEVO: límite máximo
                        "budget_limit": None,
                        "bedrooms": 3,
                        "bathrooms": 2,
                        "wants_pool": False,
                        "wants_porch": True,
                        "wants_garage": False,
                        "wants_outhouse": False,
                        "max_floors": 1,
                        "style": "moderna",
                        "materials": ["hormigón"],
                        "notes": "",
                        "orientation": "Sur",
                        "roof_type": "A dos aguas",
                        "energy_rating": "B",
                        "accessibility": False,
                        "sustainable_materials": []
                    }
            else:
                st.warning("⚠️ No se encontraron datos de la finca. Usando valores por defecto.")
        
        except Exception as e:
            st.error(f"❌ Error cargando datos de la finca: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # ============================================
    
    # Si hay una finca nueva seleccionada, resetear el diseñador desde cero
    # Esto evita que quede atrapado en un paso anterior de otra sesión
    if design_plot_id and st.session_state.get("_last_design_plot_id") != design_plot_id:
        st.session_state["ai_house_step"] = 1
        st.session_state["_last_design_plot_id"] = design_plot_id
        # Limpiar diseño anterior para que no contamine el nuevo
        st.session_state.pop("ai_room_proposal", None)
        st.session_state.pop("babylon_modified_layout", None)
        st.session_state.pop("current_floor_plan", None)
        st.session_state.pop("babylon_editor_used", None)
    
    # Inicializar el paso si no existe
    if "ai_house_step" not in st.session_state:
        st.session_state["ai_house_step"] = 1
    
    ai_house_step = st.session_state["ai_house_step"]
    
    # Título principal
    st.title("🏠 Diseñador de Vivienda con IA (MVP) v2.1 🔧")
    
    # Mostrar paso actual
    st.subheader(f"Paso {ai_house_step} de 4")
    
    # Llamar a la función correspondiente según el paso
    if ai_house_step == 1:
        render_step1()
    elif ai_house_step == 2:
        render_step2()
    elif ai_house_step == 3:
        render_step3_editor()
    elif ai_house_step == 4:
        render_step3()  # Documentación ahora es paso 4
    
    # CRÍTICO: Salir para no ejecutar código del marketplace
    return


def recalculate_layout(modified_rooms: list, house_shape: str = "Rectangular") -> dict:
    """
    Recibe habitaciones con áreas modificadas desde Babylon.
    Redistribuye el layout completo usando generate_layout().
    
    Args:
        modified_rooms: [{'code': str, 'name': str, 'area_m2': float}, ...]
        house_shape: Forma de la planta
    
    Returns:
        dict: {
            'success': bool,
            'layout': [{'x', 'z', 'width', 'depth', 'name', 'code', 'area_m2'}, ...],
            'total_width': float,
            'total_depth': float,
            'error': str (solo si success=False)
        }
    """
    try:
        from .architect_layout import generate_layout
        
        # Validar y limpiar datos de entrada
        rooms_clean = []
        for r in modified_rooms:
            try:
                area = float(r.get('area_m2', r.get('new_area', 10)))
                area = max(2.0, area)  # mínimo 2m²
                rooms_clean.append({
                    'code': str(r.get('code', r.get('name', 'espacio'))),
                    'name': str(r.get('name', 'Espacio')),
                    'area_m2': area
                })
            except (ValueError, TypeError):
                continue
        
        if not rooms_clean:
            return {'success': False, 'error': 'No hay habitaciones válidas'}
        
        # Redistribuir layout completo
        layout = generate_layout(rooms_clean, house_shape)
        
        if not layout:
            return {'success': False, 'error': 'generate_layout devolvió vacío'}
        
        # Calcular dimensiones totales
        total_width = max(item['x'] + item['width'] for item in layout)
        total_depth = max(item['z'] + item['depth'] for item in layout)
        
        return {
            'success': True,
            'layout': layout,
            'total_width': round(total_width, 2),
            'total_depth': round(total_depth, 2)
        }
    
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def get_final_design():
    """
    Retorna el diseño FINAL del usuario.
    ORDEN DE PRIORIDAD:
    1. babylon_modified_layout (si modificó en 3D)
    2. Sliders Paso 2 (desde session_state)
    3. ai_room_proposal original
    
    Returns:
        dict: {
            'rooms': [{'name': str, 'area_m2': float, ...}],
            'total_area': float,
            'total_cost': float,
            'source': 'babylon' | 'step2_sliders' | 'ai_original'
        }
    """
    import streamlit as st
    
    COST_PER_M2 = 1500
    
    # PRIORIDAD 1: Babylon (diseño modificado en 3D)
    babylon_data = st.session_state.get("babylon_modified_layout")
    if babylon_data:
        rooms = []
        total_area = 0
        for room in babylon_data:
            try:
                area = float(room.get('new_area', room.get('original_area', 10)))
                total_area += area
                rooms.append({
                    'name': room.get('name', 'Espacio'),
                    'code': room.get('name', 'generic'),
                    'area_m2': area,
                    'index': room.get('index', 0)
                })
            except (ValueError, TypeError):
                continue
        
        return {
            'rooms': rooms,
            'total_area': round(total_area, 1),
            'total_cost': int(total_area * COST_PER_M2),
            'source': 'babylon'
        }
    
    # PRIORIDAD 2: Sliders Paso 2 (valores ajustados por usuario)
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if proposal:
        rooms = []
        total_area = 0
        
        for i, (code, original_area) in enumerate(proposal.items()):
            # Leer del slider si existe
            slider_key = f"step2_slider_{i}"
            area = st.session_state.get(slider_key)
            
            if area is None:
                # Si no hay slider, usar área original
                try:
                    area = float(original_area)
                except (ValueError, TypeError):
                    area = 10
            
            total_area += area
            rooms.append({
                'name': code,
                'code': code,
                'area_m2': area,
                'index': i
            })
        
        # Determinar si es modificado o original
        source = 'step2_sliders' if any(
            st.session_state.get(f"step2_slider_{i}") is not None 
            for i in range(len(proposal))
        ) else 'ai_original'
        
        return {
            'rooms': rooms,
            'total_area': round(total_area, 1),
            'total_cost': int(total_area * COST_PER_M2),
            'source': source
        }
    
    # FALLBACK: Vacío
    return {
        'rooms': [],
        'total_area': 0,
        'total_cost': 0,
        'source': 'none'
    }

def render_step1():
    """Paso 1: Configurador de vivienda - Estilo Mercedes Benz"""
    
    # Obtener datos de la finca
    plot_data = st.session_state.get("design_plot_data", {})
    max_buildable = plot_data.get('buildable_m2', 0)

    # ============================================
    # HERO BANNER PROFESIONAL
    # ============================================
    st.markdown("""
    <div style='
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 40px 30px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 24px;
        border: 1px solid rgba(52,152,219,0.3);
    '>
        <h1 style='
            color: white;
            font-size: 2.4em;
            margin: 0 0 10px 0;
            font-weight: 700;
            letter-spacing: -0.5px;
        '>🏡 Diseña Tu Vivienda Sostenible</h1>
        <p style='
            color: rgba(255,255,255,0.75);
            font-size: 1.1em;
            margin: 0 0 20px 0;
        '>Inteligencia Artificial + Editor 3D + Normativa CTE · Todo en un solo flujo</p>
        <div style='display: flex; justify-content: center; gap: 30px; flex-wrap: wrap;'>
            <div style='color: #2ECC71; font-size: 0.95em;'>✅ Distribución automática</div>
            <div style='color: #3498DB; font-size: 0.95em;'>🏗️ Editor 3D profesional</div>
            <div style='color: #E67E22; font-size: 0.95em;'>📐 Planos constructivos</div>
            <div style='color: #9B59B6; font-size: 0.95em;'>💰 Presupuesto en tiempo real</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # BANNER FINCA (si existe)
    if plot_data:
        col1, col2, col3 = st.columns(3)
        col1.metric("📍 Tu Finca", plot_data.get('title', 'Tu parcela'))
        col2.metric("📏 Superficie total", f"{plot_data.get('total_m2', 0):.0f} m²")
        col3.metric("🏗️ Máx. edificable (33%)", f"{max_buildable:.0f} m²")
        st.markdown("---")
    
    # ============================================
    # PASO A: PRESUPUESTO
    # ============================================
    st.subheader("💰 ¿Cuál es tu presupuesto?")
    
    budget = st.select_slider(
        "Selecciona tu rango de inversión",
        options=[50000, 75000, 100000, 125000, 150000, 175000, 200000, 
                 250000, 300000, 400000, 500000],
        value=150000,
        format_func=lambda x: f"€{x:,.0f}"
    )
    
    # Mensaje orientativo según presupuesto
    if budget < 100000:
        st.info("🏠 Casa básica sostenible: 60-80 m² · 2 dormitorios · Eficiente")
    elif budget < 150000:
        st.info("🏡 Casa confortable: 80-120 m² · 3 dormitorios · Muy eficiente")
    elif budget < 250000:
        st.success("🏘️ Casa amplia premium: 120-180 m² · 4 dormitorios · Alta eficiencia")
    else:
        st.success("🏰 Casa de lujo sostenible: 180m²+ · 5+ dormitorios · Máxima eficiencia")
    
    st.markdown("---")
    
    # ============================================
    # PASO B: ESTILO DE VIVIENDA - CARDS CON FOTOS
    # ============================================
    st.subheader("🎨 ¿Qué estilo te gusta?")

    styles_data = {
        "Ecológico": {
            "desc": "Materiales naturales, mínimo impacto ambiental",
            "img": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=250&fit=crop"
        },
        "Rural": {
            "desc": "Piedra, madera, integrado en el paisaje",
            "img": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=400&h=250&fit=crop"
        },
        "Moderno": {
            "desc": "Líneas limpias, grandes ventanales, minimalista",
            "img": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=400&h=250&fit=crop"
        },
        "Montaña": {
            "desc": "Refugio alpino, tejados inclinados, madera y piedra",
            "img": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=400&h=250&fit=crop"
        },
        "Playa": {
            "desc": "Abierto, ventilado, colores claros, terrazas",
            "img": "https://images.unsplash.com/photo-1499793983690-e29da59ef1c2?w=400&h=250&fit=crop"
        },
        "Clásico": {
            "desc": "Elegante, simétrico, materiales nobles",
            "img": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=400&h=250&fit=crop"
        },
        "Andaluz": {
            "desc": "Patio central, cerámica, cal, frescor natural",
            "img": "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=400&h=250&fit=crop"
        },
        "Contemporáneo": {
            "desc": "Vanguardista, tecnológico, sostenible",
            "img": "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=400&h=250&fit=crop"
        },
    }

    # Inicializar selección
    if 'selected_style_key' not in st.session_state:
        st.session_state['selected_style_key'] = 'Moderno'

    # Render cards en filas de 4
    style_keys = list(styles_data.keys())
    for row_start in range(0, len(style_keys), 4):
        cols = st.columns(4)
        for col, style_key in zip(cols, style_keys[row_start:row_start+4]):
            data = styles_data[style_key]
            is_selected = st.session_state['selected_style_key'] == style_key
            border_color = "#3498DB" if is_selected else "rgba(255,255,255,0.1)"
            bg_color = "rgba(52,152,219,0.15)" if is_selected else "rgba(255,255,255,0.03)"
            check = "✅ " if is_selected else ""

            with col:
                st.markdown(f"""
                <div style='\
                    border: 2px solid {border_color};\
                    border-radius: 12px;\
                    overflow: hidden;\
                    background: rgba(20,30,48,0.95);\
                    margin-bottom: 8px;\
                    cursor: pointer;\
                '>
                    <img src='{data["img"]}' style='width:100%; height:130px; object-fit:cover;'>
                    <div style='padding: 8px 10px;'>
                        <p style='margin:0; font-weight:700; font-size:0.9em; color:white; text-shadow: 1px 1px 3px rgba(0,0,0,0.9);'>{check}{style_key}</p>
                        <p style='margin:2px 0 0 0; font-size:0.75em; color:rgba(255,255,255,0.85); text-shadow: 1px 1px 2px rgba(0,0,0,0.9);'>{data["desc"]}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    "✓ Seleccionar" if is_selected else "Elegir",
                    key=f"style_btn_{style_key}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary"
                ):
                    st.session_state['selected_style_key'] = style_key
                    st.rerun()

    selected_style = st.session_state['selected_style_key']
    st.caption(f"✨ Seleccionado: **{selected_style}** — {styles_data[selected_style]['desc']}")
    st.markdown("---")
    
    # ============================================
    # PASO C: HABITACIONES Y BAÑOS
    # ============================================
    st.subheader("🛏️ Habitaciones y Baños")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        bedrooms = st.number_input(
            "🛏️ Dormitorios",
            min_value=1, max_value=6,
            value=3, step=1
        )
    
    with col2:
        bathrooms = st.number_input(
            "🚿 Baños",
            min_value=1, max_value=4,
            value=2, step=1
        )
    
    with col3:
        floors = st.selectbox(
            "Plantas",
            ["1 Planta", "2 Plantas", "Planta Baja + Semisótano", "2 Plantas + Semisótano"],
            index=0,
            help="Cada planta genera su propio plano de distribución"
        )
        
        # Avisos según selección
        if floors == "2 Plantas":
            st.caption("⚠️ Se diseñarán 2 planos: Planta Baja y Planta Alta")
        elif "Semisótano" in floors:
            st.caption("⚠️ Incluye plano de semisótano (garage/bodega/zona técnica)")
    
    st.markdown("---")
    
    # ============================================
    # PASO C2: FORMA Y TEJADO
    # ============================================
    st.subheader("🏗️ Forma y Tejado")
    
    col1, col2 = st.columns(2)
    
    with col1:
        house_shape = st.selectbox(
            "Forma de la planta",
            [
                "Cuadrada (más económica)",
                "Rectangular (más común)",
                "En L (para parcelas irregulares)",
                "Irregular / Personalizada"
            ],
            index=1,
            help="La forma afecta al coste de cimentación y construcción"
        )
        
        # Info de coste según forma
        shape_costs = {
            "Cuadrada (más económica)": ("Mínimo perímetro = mínimo coste", "✅"),
            "Rectangular (más común)": ("Equilibrio perfecto coste/funcionalidad", "✅"),
            "En L (para parcelas irregulares)": ("15-20% más cara que rectangular", "⚠️"),
            "Irregular / Personalizada": ("20-30% más cara, requiere arquitecto", "⚠️")
        }
        
        msg, icon = shape_costs[house_shape]
        st.caption(f"{icon} {msg}")
    
    with col2:
        roof_type = st.selectbox(
            "Tipo de tejado",
            [
                "Dos aguas (clásico, eficiente)",
                "Cuatro aguas (para zonas con mucha lluvia)",
                "Plana/Transitable (zona seca, terraza)",
                "A un agua (moderno, minimalista)",
                "Invertida (colecta agua lluvia)"
            ],
            index=0,
            help="El tejado afecta al coste, aislamiento y recogida de agua"
        )
    
    # Guardar selecciones
    if 'request' not in st.session_state:
        st.session_state['request'] = {}
    
    st.session_state['request']['house_shape'] = house_shape
    st.session_state['request']['roof_type'] = roof_type
    
    st.markdown("---")
    
    # ============================================
    # PASO D: EXTRAS - CARDS VISUALES
    # ============================================
    st.subheader("🌟 Extras")
    st.caption("Selecciona los elementos adicionales que quieres incluir")

    extras_data = [
        {"key": "garage",     "label": "Garaje",         "desc": "2 plazas cubiertas",     "color": "#1a3a5c", "accent": "#3498DB", "default": True},
        {"key": "pool",       "label": "Piscina",        "desc": "8×4m con depuradora",    "color": "#0d3d56", "accent": "#00BCD4", "default": False},
        {"key": "porch",      "label": "Porche/Terraza", "desc": "Cubierto, suelo ext.",   "color": "#1a3d2b", "accent": "#2ECC71", "default": True},
        {"key": "bodega",     "label": "Bodega",         "desc": "9m² climatizada",         "color": "#3d1a2b", "accent": "#9B59B6", "default": False},
        {"key": "huerto",     "label": "Huerto",         "desc": "30m² con riego",          "color": "#1e3d1a", "accent": "#27AE60", "default": False},
        {"key": "caseta",     "label": "Casa de Aperos", "desc": "15m² exterior",           "color": "#3d2e1a", "accent": "#E67E22", "default": False},
        {"key": "accessible", "label": "Accesible",      "desc": "Rampas y baño adaptado", "color": "#1a2d3d", "accent": "#5DADE2", "default": False},
        {"key": "office",     "label": "Despacho",       "desc": "10m² insonorizado",       "color": "#2d1a3d", "accent": "#8E44AD", "default": False},
    ]

    # Inicializar estado
    for extra in extras_data:
        if f"extra_{extra['key']}" not in st.session_state:
            st.session_state[f"extra_{extra['key']}"] = extra['default']

    # Render en 2 filas de 4
    for row_start in range(0, len(extras_data), 4):
        cols = st.columns(4)
        for col, extra in zip(cols, extras_data[row_start:row_start+4]):
            key = f"extra_{extra['key']}"
            is_on = st.session_state[key]
            bg = extra['color'] if not is_on else extra['color']
            border = extra['accent'] if is_on else "rgba(255,255,255,0.1)"
            opacity = "1" if is_on else "0.55"
            indicator = f"<span style='color:{extra['accent']}; font-weight:900;'>●</span>" if is_on else "<span style='color:rgba(255,255,255,0.3); font-weight:900;'>○</span>"

            with col:
                st.markdown(f"""
                <div style='\
                    border: 2px solid {border};\
                    border-radius: 10px;\
                    padding: 10px 12px;\
                    background: {bg};\
                    margin-bottom: 6px;\
                    opacity: {opacity};\
                '>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <p style='margin:0; font-weight:700; font-size:0.88em; color:white;'>{extra['label']}</p>
                        {indicator}
                    </div>
                    <p style='margin:3px 0 0 0; font-size:0.72em; color:rgba(255,255,255,0.75);'>{extra['desc']}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    "✓ Incluido" if is_on else "Añadir",
                    key=f"btn_extra_{extra['key']}",
                    use_container_width=True,
                    type="primary" if is_on else "secondary"
                ):
                    st.session_state[key] = not is_on
                    st.rerun()

    # Extraer valores para uso posterior
    has_garage     = st.session_state["extra_garage"]
    has_pool       = st.session_state["extra_pool"]
    has_porch      = st.session_state["extra_porch"]
    has_bodega     = st.session_state["extra_bodega"]
    has_huerto     = st.session_state["extra_huerto"]
    has_caseta     = st.session_state["extra_caseta"]
    has_accessible = st.session_state["extra_accessible"]
    has_office     = st.session_state["extra_office"]

    st.markdown("---")
    
    # ============================================
    # PASO E: ENERGÍA Y SOSTENIBILIDAD
    # ============================================
    st.subheader("⚡ Energía y Sostenibilidad")
    st.caption("Reduce tu factura energética hasta un 90%")
    
    col1, col2 = st.columns(2)
    
    with col1:
        solar = st.checkbox("☀️ Paneles Solares", value=True,
            help="Autoconsumo eléctrico. Ahorro: €1,200/año")
        aerotermia = st.checkbox("🌡️ Aerotermia",
            help="Calefacción/frío eficiente. Ahorro: €800/año")
        geotermia = st.checkbox("🌍 Geotermia",
            help="Temperatura constante del suelo")
    
    with col2:
        rainwater = st.checkbox("💧 Recuperación Agua Lluvia", value=True,
            help="Ahorro hasta 40% en agua")
        insulation = st.checkbox("🌿 Aislamiento Natural",
            help="Lana de roca, corcho, cáñamo")
        domotic = st.checkbox("🏠 Domótica",
            help="Control inteligente del hogar")
    
    # Calcular ahorro estimado
    ahorro_anual = 0
    if solar: ahorro_anual += 1200
    if aerotermia: ahorro_anual += 800
    if rainwater: ahorro_anual += 300
    if insulation: ahorro_anual += 400
    if geotermia: ahorro_anual += 1000
    
    if ahorro_anual > 0:
        st.success(f"💰 Ahorro energético estimado: **€{ahorro_anual:,}/año** · Retorno inversión: {int(15000/ahorro_anual)} años")
    
    st.markdown("---")
    
    # ============================================
    # PASO F: NOTAS ESPECIALES
    # ============================================
    st.subheader("📝 Algo más que quieras añadir")
    
    special_notes = st.text_area(
        "Cuéntanos más detalles",
        placeholder="Ej: Quiero una bodega grande para eventos, necesito espacio para animales, me gusta mucho la luz natural...",
        height=80,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # ============================================
    # PASO G: CIMIENTOS E INSTALACIONES
    # ============================================
    st.subheader("🏗️ Cimientos e Instalaciones Básicas")
    st.caption("Calculamos automáticamente lo mínimo necesario para abaratar costes")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        foundation_type = st.selectbox(
            "Tipo de cimentación",
            [
                "Zapatas aisladas (mínimo, más barato)",
                "Losa de hormigón (suelos blandos)",
                "Pilotes (terrenos difíciles)",
                "Recomendación automática IA"
            ],
            index=3
        )
    
    with col2:
        st.markdown("**Suministro de agua**")
        water_municipal = st.checkbox("🏘️ Red municipal (si disponible)", value=False)
        water_rain = st.checkbox("🌧️ Depósito agua lluvia", value=True, 
            help="Depósito 5,000-10,000L. Ahorro 40% en agua")
        water_well = st.checkbox("⛏️ Pozo propio", value=False)
        water_solar = st.checkbox("☀️ Calentador solar ACS", value=True,
            help="Agua caliente sanitaria solar. Ahorro €400/año")
        
        # Calcular combinación
        water_systems = []
        if water_municipal: water_systems.append("red municipal")
        if water_rain: water_systems.append("depósito lluvia")
        if water_well: water_systems.append("pozo")
        if water_solar: water_systems.append("solar ACS")
        
        if not water_systems:
            st.warning("⚠️ Selecciona al menos un sistema de agua")
        else:
            st.caption(f"✅ Combinación: {' + '.join(water_systems)}")
    
    with col3:
        st.markdown("**Saneamiento**")
        sew_municipal = st.checkbox("🏘️ Red municipal (si disponible)", value=False,
            key="sew_municipal")
        sew_septic = st.checkbox("♻️ Fosa séptica ecológica", value=True,
            help="Autónomo, sin conexión a red")
        sew_phyto = st.checkbox("🌿 Fitodepuración", value=False,
            help="Máxima sostenibilidad. Filtra con plantas naturales")
        sew_biodigestor = st.checkbox("⚗️ Biodigestor", value=False,
            help="Genera biogás aprovechable para cocina")
        
        sewage_systems = []
        if sew_municipal: sewage_systems.append("red municipal")
        if sew_septic: sewage_systems.append("fosa séptica")
        if sew_phyto: sewage_systems.append("fitodepuración")
        if sew_biodigestor: sewage_systems.append("biodigestor")
        
        if not sewage_systems:
            st.warning("⚠️ Selecciona al menos un sistema de saneamiento")
        else:
            st.caption(f"✅ Combinación: {' + '.join(sewage_systems)}")
    
    st.markdown("---")
    
    # ============================================
    # BOTÓN DISEÑAR
    # ============================================
    
    # Calcular m² recomendados según presupuesto
    cost_per_m2 = 1100  # €/m² promedio sostenible
    max_m2_budget = int(budget * 0.85 / cost_per_m2)  # 85% para construcción
    
    if max_buildable > 0:
        recommended_m2 = min(max_m2_budget, int(max_buildable * 0.9))
    else:
        recommended_m2 = max_m2_budget
    
    # Calcular presupuesto cimentación automáticamente
    foundation_cost = int(recommended_m2 * 180)  # €180/m² cimentación
    
    st.info(f"💰 Presupuesto estimado de cimentación: **€{foundation_cost:,}** ({int(foundation_cost/budget*100)}% del presupuesto total) · Incluido en el presupuesto global")
    
    # Resumen antes del botón - diseño profesional
    extras_activos = []
    if has_garage: extras_activos.append("Garaje")
    if has_pool: extras_activos.append("Piscina")
    if has_porch: extras_activos.append("Porche")
    if has_bodega: extras_activos.append("Bodega")
    if has_huerto: extras_activos.append("Huerto")
    if has_caseta: extras_activos.append("Casa Aperos")
    if has_office: extras_activos.append("Despacho")

    extras_html = "".join([
        f"<span style='background:rgba(255,255,255,0.15); padding:3px 10px; "
        f"border-radius:20px; margin:3px; display:inline-block; font-size:12px;'>"
        f"{e}</span>"
        for e in extras_activos
    ]) if extras_activos else "<span style='opacity:0.6; font-size:12px;'>Sin extras seleccionados</span>"

    ahorro_html = (
        f"<div style='margin-top:12px; padding:8px 16px; background:rgba(46,204,113,0.2); "
        f"border-radius:8px; border:1px solid rgba(46,204,113,0.4); font-size:13px;'>"
        f"⚡ Ahorro energético estimado: <b>€{ahorro_anual:,}/año</b></div>"
    ) if ahorro_anual > 0 else ""

    resumen_html = (
        "<div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);"
        "padding: 24px; border-radius: 16px; color: white;"
        "border: 1px solid rgba(255,255,255,0.1);"
        "box-shadow: 0 8px 32px rgba(0,0,0,0.3);'>"
        "<p style='margin:0 0 16px 0; font-size:13px; opacity:0.6;"
        "letter-spacing:2px; text-transform:uppercase;'>Resumen de tu proyecto</p>"
        "<div style='display:grid; grid-template-columns: repeat(4,1fr); gap:12px; margin-bottom:16px;'>"
        "<div style='background:rgba(255,255,255,0.07); padding:14px; border-radius:10px;"
        "text-align:center; border:1px solid rgba(255,255,255,0.1);'>"
        "<div style='font-size:11px; opacity:0.6; margin-bottom:4px;'>PRESUPUESTO</div>"
        f"<div style='font-size:20px; font-weight:700; color:#2ECC71;'>€{budget:,}</div></div>"
        "<div style='background:rgba(255,255,255,0.07); padding:14px; border-radius:10px;"
        "text-align:center; border:1px solid rgba(255,255,255,0.1);'>"
        "<div style='font-size:11px; opacity:0.6; margin-bottom:4px;'>SUPERFICIE</div>"
        f"<div style='font-size:20px; font-weight:700; color:#3498DB;'>{recommended_m2} m²</div></div>"
        "<div style='background:rgba(255,255,255,0.07); padding:14px; border-radius:10px;"
        "text-align:center; border:1px solid rgba(255,255,255,0.1);'>"
        "<div style='font-size:11px; opacity:0.6; margin-bottom:4px;'>HABITACIONES</div>"
        f"<div style='font-size:20px; font-weight:700; color:#E67E22;'>{bedrooms} dorm · {bathrooms} baños</div></div>"
        "<div style='background:rgba(255,255,255,0.07); padding:14px; border-radius:10px;"
        "text-align:center; border:1px solid rgba(255,255,255,0.1);'>"
        "<div style='font-size:11px; opacity:0.6; margin-bottom:4px;'>ESTILO</div>"
        f"<div style='font-size:14px; font-weight:700; color:#9B59B6;'>{selected_style.split(' ')[-1]}</div>"
        "</div></div>"
        "<div style='margin-bottom:8px; font-size:12px; opacity:0.6;'>EXTRAS INCLUIDOS</div>"
        f"<div style='margin-bottom:4px;'>{extras_html}</div>"
        f"{ahorro_html}"
        "</div>"
    )

    st.markdown(resumen_html, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        design_button = st.button(
            "🤖 DISEÑAR MI CASA CON IA",
            type="primary",
            use_container_width=True
        )
    
    if design_button:
        # Recopilar todos los datos
        req = {
            "budget": budget,
            "style": selected_style,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "floors": floors,
            "target_area_m2": recommended_m2,
            "max_buildable_m2": max_buildable,
            "house_shape": house_shape,
            "roof_type": roof_type,
            "foundation_type": foundation_type,
            "water_systems": water_systems,
            "sewage_systems": sewage_systems,
            "water_details": {
                "municipal": water_municipal,
                "rain_tank": water_rain,
                "well": water_well,
                "solar_acs": water_solar
            },
            "sewage_details": {
                "municipal": sew_municipal,
                "septic": sew_septic,
                "phyto": sew_phyto,
                "biodigestor": sew_biodigestor
            },
            "extras": {
                "garage": has_garage,
                "pool": has_pool,
                "porch": has_porch,
                "bodega": has_bodega,
                "huerto": has_huerto,
                "caseta": has_caseta,
                "accessible": has_accessible,
                "office": has_office
            },
            "energy": {
                "solar": solar,
                "aerotermia": aerotermia,
                "geotermia": geotermia,
                "rainwater": rainwater,
                "insulation": insulation,
                "domotic": domotic
            },
            "special_notes": special_notes,
            "estimated_savings": ahorro_anual
        }
        
        st.session_state["ai_house_requirements"] = req
        
        # Llamar a IA
        _generate_ai_proposal(req)

def _normalize_ai_proposal(proposal: dict, energy_list: list) -> dict:
    """Normaliza los nombres y entradas del JSON generado por la IA.

    - Agrega o agrupa cualquier clave que mencione paneles o solar en una sola
      entrada con código **paneles_solares**.
    - Si el cliente pidió energía solar y no aparece ningún panel, inserta una
      entrada mínima con {PANEL_MIN_M2} m² para garantizar su visualización.
    - Devuelve el diccionario modificado (la operación se realiza in‑place).
    """
    panel_area = 0.0
    keys_to_remove = []

    for k, v in list(proposal.items()):
        if 'panel' in k.lower() or 'solar' in k.lower():
            try:
                panel_area += float(v)
            except Exception:
                # valores no numéricos se ignoran
                pass
            keys_to_remove.append(k)

    # quitar también claves de sistemas energéticos no espaciales
    # si el usuario marcó cualquier energía distinta de solar, eliminamos
    # posibles entradas generadas por la IA que mencionen el término.
    for en in energy_list:
        if en != 'solar':
            for k in list(proposal.keys()):
                if en.lower() in k.lower():
                    proposal.pop(k, None)

    # eliminar las claves antiguas asociadas a paneles
    for k in keys_to_remove:
        proposal.pop(k, None)

    if panel_area > 0:
        proposal['paneles_solares'] = panel_area
    elif 'solar' in energy_list:
        # el usuario quería paneles pero la IA no generó ninguno
        proposal['paneles_solares'] = PANEL_MIN_M2

    return proposal


def _generate_ai_proposal(req):
    """Genera propuesta de distribución con IA"""
    with st.spinner("🤖 La IA está diseñando tu casa..."):
        try:
            from dotenv import load_dotenv
            from groq import Groq
            from pathlib import Path
            import os
            import json
            
            # Cargar API key
            project_root = Path(__file__).parent.parent.parent
            load_dotenv(dotenv_path=project_root / '.env')
            groq_api_key = os.getenv("GROQ_API_KEY")
            
            if not groq_api_key:
                st.error("❌ GROQ_API_KEY no encontrada")
                return
            
            client = Groq(api_key=groq_api_key)
            
            # Construir prompt simplificado
            extras_list = [k for k, v in req['extras'].items() if v]
            energy_list = [k for k, v in req['energy'].items() if v]
            
            prompt = f"""Diseña una vivienda '{req['style']}'de {req['target_area_m2']}m² con:
- {req['bedrooms']} dormitorios (1 principal + {req['bedrooms']-1} secundarios)
- {req['bathrooms']} baños
- Extras: {', '.join(extras_list) if extras_list else 'ninguno'}
- Energía/Sostenibilidad: {', '.join(energy_list) if energy_list else 'ninguno'}
- **IMPORTANTE**: No transformes ninguna energía/sostenibilidad salvo los paneles en habitaciones. Es decir, no crees espacios llamados "aerotermia", "geotermia", "domótica", "rainwater", "insulation" ni similares. Esas tecnologías sólo deben aparecer en el análisis escrito, nunca en el plano ni como habitaciones.
- REGLA ESTRICTA: Si en la lista aparece "solar" (paneles solares), incluye EXACTAMENTE UNO con code "paneles_solares" en el JSON. NUNCA dos entradas de paneles.
- RESTRICCIÓN ECONÓMICA ABSOLUTA: La suma de TODOS los m² del JSON NO puede superar {req['target_area_m2']} m². El cliente tiene €{req['budget']:,} de presupuesto. Si no caben todos los extras, reduce sus m² proporcionalmente hasta que la suma total sea <= {req['target_area_m2']} m². Esto es innegociable.

PETICIONES ESPECIALES DEL CLIENTE (OBLIGATORIO INCLUIR):
{req.get('special_notes', 'ninguna')}

IMPORTANTE - Si el cliente menciona:
- "chimenea" → añadir coste €3,000-5,000 en descripción
- "suelo radiante" → añadir €80/m² extra al presupuesto
- "domótica" → añadir €5,000-15,000 en sistemas inteligentes
- Cualquier extra especial → incluirlo en el análisis y presupuesto
NUNCA ignorar las peticiones especiales del cliente.

Responde SOLO con un JSON válido (sin markdown) con habitaciones y m². Ejemplo:
{{
  "salon": 22,
  "cocina": 14,
  "dormitorio_principal": 16,
  "dormitorio": 11,
  "bano": 6,
  "bano_2": 5,
  "porche": 18,
  "garaje": 20
}}
"""
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # Parsear respuesta
            response_text = response.choices[0].message.content.strip()
            
            # Limpiar markdown si existe
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            ai_proposal = json.loads(response_text)

            # Normalizar resultados y asegurar paneles solares
            ai_proposal = _normalize_ai_proposal(ai_proposal, energy_list)
            
            # Guardar propuesta
            req["ai_room_proposal"] = ai_proposal
            st.session_state["ai_house_requirements"] = req
            
            st.success("✅ ¡Casa diseñada! Pasando al Paso 2...")
            st.session_state["ai_house_step"] = 2
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error generando diseño: {e}")
            import traceback
            st.code(traceback.format_exc())

def render_step2():
    """Paso 2: Editor visual unificado - Layout 2 columnas profesional"""
    
    # Leer datos del proyecto para el banner (lectura segura, sin modificar)
    _req_header = st.session_state.get("ai_house_requirements", {})
    _budget_h = _req_header.get("budget", 0)
    _style_h = _req_header.get("style", "")
    _style_h_short = _style_h.split(" ")[-1] if _style_h else "—"
    _area_h = _req_header.get("target_area_m2", 0)
    _beds_h = _req_header.get("bedrooms", 0)
    _baths_h = _req_header.get("bathrooms", 0)

    _banner_html = (
        "<div style='background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);"
        "padding: 16px 24px; border-radius: 12px; color: white; margin-bottom: 16px;"
        "border: 1px solid rgba(255,255,255,0.1);'>"
        "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;'>"
        "<div>"
        "<div style='font-size:11px; opacity:0.5; letter-spacing:2px; text-transform:uppercase;'>Tu proyecto</div>"
        "<div style='font-size:20px; font-weight:700; margin-top:2px;'>Ajusta tu diseño</div>"
        "<div style='font-size:12px; opacity:0.6; margin-top:2px;'>El plano se actualiza automáticamente</div>"
        "</div>"
        "<div style='display:flex; gap:16px; flex-wrap:wrap;'>"
        f"<div style='text-align:center;'><div style='font-size:10px; opacity:0.5;'>PRESUPUESTO</div>"
        f"<div style='font-size:16px; font-weight:700; color:#2ECC71;'>€{_budget_h:,}</div></div>"
        f"<div style='text-align:center;'><div style='font-size:10px; opacity:0.5;'>SUPERFICIE</div>"
        f"<div style='font-size:16px; font-weight:700; color:#3498DB;'>{_area_h} m²</div></div>"
        f"<div style='text-align:center;'><div style='font-size:10px; opacity:0.5;'>HABITACIONES</div>"
        f"<div style='font-size:16px; font-weight:700; color:#E67E22;'>{_beds_h}d · {_baths_h}b</div></div>"
        f"<div style='text-align:center;'><div style='font-size:10px; opacity:0.5;'>ESTILO</div>"
        f"<div style='font-size:16px; font-weight:700; color:#9B59B6;'>{_style_h_short}</div></div>"
        "</div></div></div>"
    )
    st.markdown(_banner_html, unsafe_allow_html=True)
    
    # Botones navegación
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("← Paso 1", key="back_to_1", use_container_width=True):
            st.session_state["ai_house_step"] = 1
            st.rerun()
    with col2:
        if st.button("Paso 3: Editor 3D →", key="go_to_3", type="primary", use_container_width=True):
            st.session_state["ai_house_step"] = 3
            st.rerun()
    
    st.markdown("---")
    
    # ============================================
    # VALIDAR DATOS
    # ============================================
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if not proposal:
        st.warning("Primero completa el Paso 1")
        if st.button("← Volver al Paso 1"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # ================================================
    # USAR DATOS CENTRALIZADOS (referencia)
    # ================================================
    design_data = get_current_design_data()
    base_total_cost = design_data['total_cost']
    
    # Si hay diseño de Babylon, usar esas áreas en los sliders
    # El cable #076 ya sincronizó ai_room_proposal con new_area de Babylon
    if design_data['modified']:
        st.info(f"📐 **Diseño editado en Babylon activo**: {design_data['total_area']}m² · "
                f"€{base_total_cost:,} · Los sliders reflejan tu diseño 3D")
    
    # proposal ya tiene los valores de Babylon gracias al cable #076
    # No necesitamos sobreescribir nada más aquí

    # Datos de parcela
    plot_data = st.session_state.get("design_plot_data", {})
    max_buildable = plot_data.get('buildable_m2', 400.0)
    
    # ============================================
    # TIPOS DE HABITACIÓN CON PRECIOS REALES
    # ============================================
    from .data_model import HouseDesign, Plot, RoomType, RoomInstance
    
    room_types = {
        "salon_cocina": RoomType(code="salon_cocina", name="Salón-Cocina", min_m2=20, max_m2=50, base_cost_per_m2=1200),
        "salon": RoomType(code="salon", name="Salón", min_m2=15, max_m2=40, base_cost_per_m2=1100),
        "cocina": RoomType(code="cocina", name="Cocina", min_m2=8, max_m2=20, base_cost_per_m2=1300),
        "dormitorio_principal": RoomType(code="dormitorio_principal", name="Dormitorio Principal", min_m2=12, max_m2=25, base_cost_per_m2=1400),
        "dormitorio": RoomType(code="dormitorio", name="Dormitorio", min_m2=8, max_m2=15, base_cost_per_m2=1100),
        "bano": RoomType(code="bano", name="Baño", min_m2=4, max_m2=8, base_cost_per_m2=900),
        "bodega": RoomType(code="bodega", name="Bodega", min_m2=6, max_m2=20, base_cost_per_m2=600),
        "piscina": RoomType(code="piscina", name="Piscina", min_m2=20, max_m2=60, base_cost_per_m2=2500),
        "paneles_solares": RoomType(code="paneles_solares", name="Paneles Solares", min_m2=3, max_m2=15, base_cost_per_m2=3000),
        "garaje": RoomType(code="garaje", name="Garaje", min_m2=15, max_m2=40, base_cost_per_m2=900),
        "porche": RoomType(code="porche", name="Porche/Terraza", min_m2=8, max_m2=40, base_cost_per_m2=700),
        "bomba_agua": RoomType(code="bomba_agua", name="Instalaciones", min_m2=2, max_m2=8, base_cost_per_m2=2000),
        "accesibilidad": RoomType(code="accesibilidad", name="Zona Accesible", min_m2=0, max_m2=10, base_cost_per_m2=2000),
        "pasillo": RoomType(code="pasillo", name="Pasillo/Distribuidor", min_m2=5, max_m2=20, base_cost_per_m2=800),
        "huerto": RoomType(code="huerto", name="Huerto", min_m2=10, max_m2=100, base_cost_per_m2=150),
        "despacho": RoomType(code="despacho", name="Despacho", min_m2=8, max_m2=20, base_cost_per_m2=1100),
    }
    
    # ============================================
    # CREAR DISEÑO CON MAPEO INTELIGENTE
    # ============================================
    plot = Plot(
        id=plot_data.get('id', 'temp'),
        area_m2=plot_data.get('total_m2', 400.0),
        buildable_ratio=0.33
    )
    design = HouseDesign(plot)
    
    for code, area in proposal.items():
        if not isinstance(area, (int, float)):
            continue
        
        room_type = None
        code_lower = code.lower()
        
        if code in room_types:
            room_type = room_types[code]
        elif 'salon' in code_lower and 'cocina' not in code_lower:
            room_type = room_types['salon']
        elif 'cocina' in code_lower and 'salon' not in code_lower:
            room_type = room_types['cocina']
        elif 'salon' in code_lower and 'cocina' in code_lower:
            room_type = room_types['salon_cocina']
        elif 'dormitorio' in code_lower and 'principal' in code_lower:
            room_type = room_types['dormitorio_principal']
        elif 'dormitorio' in code_lower:
            room_type = room_types['dormitorio']
        elif 'bano' in code_lower or 'baño' in code_lower:
            room_type = room_types['bano']
        elif 'bodega' in code_lower:
            room_type = room_types['bodega']
        elif 'piscina' in code_lower:
            room_type = room_types['piscina']
        elif 'paneles' in code_lower or 'solar' in code_lower:
            room_type = room_types['paneles_solares']
        elif 'garaje' in code_lower or 'garage' in code_lower:
            room_type = room_types['garaje']
        elif 'porche' in code_lower or 'terraza' in code_lower:
            room_type = room_types['porche']
        elif 'bomba' in code_lower or 'instalac' in code_lower:
            room_type = room_types['bomba_agua']
        elif 'accesib' in code_lower:
            room_type = room_types['accesibilidad']
        elif 'pasillo' in code_lower or 'distrib' in code_lower:
            room_type = room_types['pasillo']
        elif 'huerto' in code_lower:
            room_type = room_types['huerto']
        elif 'despacho' in code_lower or 'oficina' in code_lower:
            room_type = room_types['despacho']
        else:
            room_type = RoomType(
                code=code,
                name=code.replace("_", " ").title(),
                min_m2=5, max_m2=50,
                base_cost_per_m2=1000
            )
        
        design.rooms.append(RoomInstance(
            room_type=room_type,
            area_m2=float(area)
        ))
    
    # ============================================
    # LAYOUT 2 COLUMNAS PRINCIPALES
    # ============================================
    col_left, col_right = st.columns([4, 6])
    
    # ============================================
    # COLUMNA IZQUIERDA: CONTROLES
    # ============================================
    with col_left:
        
        budget = req.get('budget', 150000)
        
        # Placeholder para métricas (se calculan después de sliders y checkboxes)
        metrics_placeholder = st.empty()
        
        st.markdown("---")
        
        # AJUSTAR HABITACIONES
        st.markdown("#### Ajustar Habitaciones")
        
        # Primero identificar qué extras están marcados para eliminar
        optional_codes = ['piscina', 'garaje', 'porche', 'bodega', 
                         'huerto', 'paneles', 'bomba', 'accesib']
        
        # Pre-calcular qué rooms se van a eliminar
        preview_remove = []
        for i, room in enumerate(design.rooms):
            code = room.room_type.code.lower()
            if any(x in code for x in optional_codes):
                keep = st.session_state.get(f"keep_{i}", True)
                if not keep:
                    preview_remove.append(i)
        
        # Diccionario de costes por m² según tipo
        ROOM_COSTS = {
            'salon': 1200, 'cocina': 1200, 'dormitorio': 1400,
            'bano': 900, 'garaje': 900, 'porche': 700,
            'bodega': 600, 'pasillo': 800, 'paneles': 3000,
            'piscina': 2500, 'huerto': 150, 'despacho': 1100,
            'caseta': 800, 'office': 1100, 'lavadero': 700,
        }
        
        def get_cost_per_m2(room_code: str) -> int:
            code_lower = room_code.lower()
            for key, cost in ROOM_COSTS.items():
                if key in code_lower:
                    return cost
            return 1000  # coste por defecto
        
        # Aviso antes de los sliders
        st.warning("""
        ⚠️ **DISEÑO PRELIMINAR**

        Los sliders te permiten ajustar áreas para estimar presupuesto.

        El diseño arquitectónico FINAL se crea en el **Editor 3D (Paso 3)**.

        Las medidas aquí son aproximadas y pueden variar en el editor 3D 
        debido a las dimensiones reales de construcción.
        """)
        
        # Mostrar sliders SOLO para rooms que NO se van a eliminar
        for i, room in enumerate(design.rooms):
            if room.area_m2 < 2:
                continue
            if i in preview_remove:
                continue  # No mostrar slider si va a ser eliminado
            
            cost_per_m2 = get_cost_per_m2(room.room_type.code)
            
            # Leer valor previo desde session_state si existe
            slider_key = f"step2_slider_{i}"
            saved_area = st.session_state.get(slider_key, float(room.area_m2))
            saved_area = max(float(room.room_type.min_m2), 
                       min(float(room.room_type.max_m2), saved_area))

            # Mostrar PRIMERO: nombre y precio
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{room.room_type.name}**")
            with col2:
                current_cost = saved_area * cost_per_m2
                st.markdown(f"<span style='color:#2ECC71; font-weight:bold;'>€{current_cost:,.0f}</span>", unsafe_allow_html=True)

            # Luego el slider
            new_area = st.slider(
                f"{saved_area:.1f} m²",
                min_value=float(room.room_type.min_m2),
                max_value=float(room.room_type.max_m2),
                value=saved_area,
                step=0.5,
                key=slider_key,
                label_visibility="collapsed"
            )

            # Calcular coste con valor ACTUAL del slider
            new_cost = new_area * cost_per_m2
            old_cost = float(room.area_m2) * cost_per_m2
            diff = new_cost - old_cost

            if abs(diff) > 10:
                if diff > 0:
                    st.caption(f"💰 +€{diff:,.0f}")
                else:
                    st.caption(f"💰 {diff:,.0f}")

            design.rooms[i].area_m2 = new_area
            
            # CABLE SLIDER → SESSION_STATE: persistir valor del slider
            req = st.session_state.get("ai_house_requirements", {})
            if "ai_room_proposal" in req:
                req["ai_room_proposal"][room.room_type.code] = new_area
                st.session_state["ai_house_requirements"] = req
        
        st.markdown("---")
        
        # ELIMINAR EXTRAS
        st.markdown("#### Eliminar Extras (Ahorrar)")
        
        optional_codes = ['piscina', 'garaje', 'porche', 'bodega', 
                         'huerto', 'paneles', 'bomba', 'accesib']
        
        rooms_to_remove = []
        # Construir lista unificada: habitaciones opcionales + sistemas energéticos
        ENERGY_COSTS = {
            'aerotermia': ('🌡️ Aerotermia · €8,000',    8000),
            'geotermia':  ('🌍 Geotermia · €12,000',    12000),
            'rainwater':  ('💧 Agua Lluvia · €3,500',    3500),
            'insulation': ('🌿 Aislamiento · €2,000',    2000),
            'domotic':    ('🏠 Domótica · €5,000',       5000),
        }
        energy_selected = req.get('energy', {})
        energy_cost_total = 0
        energy_keep = {}

        # Grid 3 columnas — todos los extras juntos
        optional_rooms = [(i, room) for i, room in enumerate(design.rooms)
                          if any(x in room.room_type.code.lower() for x in optional_codes)]
        energy_items = [(k, label, cost) for k, (label, cost) in ENERGY_COSTS.items()
                        if energy_selected.get(k)]
        total_items = len(optional_rooms) + len(energy_items)
        cols = st.columns(3)
        col_idx = 0
        for i, room in optional_rooms:
            cost = room.area_m2 * room.room_type.base_cost_per_m2
            with cols[col_idx % 3]:
                keep = st.checkbox(
                    f"{room.room_type.name} · €{cost:,.0f}",
                    value=True,
                    key=f"keep_{i}"
                )
                if not keep:
                    rooms_to_remove.append(i)
            col_idx += 1
        for key, label, cost in energy_items:
            with cols[col_idx % 3]:
                keep_e = st.checkbox(label, value=True, key=f"keep_energy_{key}")
                energy_keep[key] = keep_e
                if keep_e:
                    energy_cost_total += cost
            col_idx += 1
        st.session_state['energy_cost_total'] = energy_cost_total
        st.session_state['energy_keep'] = energy_keep

        # Eliminar desmarcados
        for idx in sorted(rooms_to_remove, reverse=True):
            design.rooms.pop(idx)
        
        # RECALCULAR MÉTRICAS FINALES (después de sliders y checkboxes)
        total_area_final = sum([r.area_m2 for r in design.rooms])
        total_cost_final = sum([r.area_m2 * r.room_type.base_cost_per_m2 for r in design.rooms])
        foundation_cost = int(total_area_final * 180)
        installation_cost = int(total_area_final * 150)
        energy_cost_total = st.session_state.get('energy_cost_total', 0)
        total_with_extras = total_cost_final + foundation_cost + installation_cost + energy_cost_total
        budget_pct = total_with_extras / budget * 100
        
        if budget_pct <= 90:
            b_icon = "✅"
            b_color = "normal"
        elif budget_pct <= 100:
            b_icon = "⚠️"
            b_color = "normal"
        else:
            b_icon = "❌"
            b_color = "inverse"
        
        # Rellenar placeholder con métricas actualizadas
        with metrics_placeholder.container():
            m1, m2 = st.columns(2)
            m1.metric(
                "Presupuesto",
                f"€{total_with_extras:,.0f}",
                delta=f"{b_icon} {budget_pct:.0f}% de €{budget:,.0f}",
                delta_color=b_color
            )
            m2.metric(
                "Superficie",
                f"{total_area_final:.0f} m²",
                delta=f"Máx: {max_buildable:.0f} m²"
            )
            savings = req.get('estimated_savings', 0)
            if savings > 0:
                st.success(f"Ahorro energético: €{savings:,}/año")
        
        # WARNING presupuesto superado
        if budget_pct > 110:
            exceso = int(total_with_extras - budget)
            st.error(
                f"🚨 **Presupuesto superado**: El diseño actual cuesta **€{total_with_extras:,}** "                f"pero tu presupuesto es **€{budget:,}**. "                f"Exceso: **€{exceso:,}**. "                f"Reduce habitaciones con los sliders o vuelve al Paso 1 para ajustar tu presupuesto."
            )
            if st.button("← Volver al Paso 1 y ajustar presupuesto", key="btn_back_budget"):
                st.session_state["ai_house_step"] = 1
                st.rerun()
        elif budget_pct > 100:
            exceso = int(total_with_extras - budget)
            st.warning(
                f"⚠️ El diseño actual supera ligeramente tu presupuesto en **€{exceso:,}**. "                f"Ajusta alguna habitación con los sliders."
            )
        
        st.markdown("---")
        
        if 'current_floor_plan' in st.session_state:
            st.download_button(
                label="Descargar Plano PNG",
                data=st.session_state['current_floor_plan'],
                file_name="plano_distribucion.png",
                mime="image/png",
                use_container_width=True
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Paso 1", use_container_width=True):
                st.session_state["ai_house_step"] = 1
                st.rerun()
        with col2:
            if st.button("Paso 3 →", type="primary", use_container_width=True):
                st.session_state["ai_house_step"] = 3
                st.rerun()
    
    # ============================================
    # COLUMNA DERECHA: PLANO + IA
    # ============================================
    with col_right:
        
        # TABLA RESUMEN
        st.markdown("#### Tu Distribución")
        
        import pandas as pd
        table_data = []
        for room in design.rooms:
            price = room.room_type.base_cost_per_m2
            cost = room.area_m2 * price
            table_data.append({
                "Espacio": room.room_type.name,
                "m²": f"{room.area_m2:.0f}",
                "€/m²": f"€{price:,}",
                "Total": f"€{cost:,.0f}"
            })
        
        # Añadir cimentación e instalaciones
        table_data.append({
            "Espacio": "Cimentación",
            "m²": f"{total_area_final:.0f}",
            "€/m²": "€180",
            "Total": f"€{foundation_cost:,}"
        })
        table_data.append({
            "Espacio": "Instalaciones",
            "m²": f"{total_area_final:.0f}",
            "€/m²": "€150",
            "Total": f"€{installation_cost:,}"
        })
        if energy_cost_total > 0:
            table_data.append({
                "Espacio": "Sistemas sostenibles",
                "m²": "-",
                "€/m²": "-",
                "Total": f"€{energy_cost_total:,}"
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Plano 2D preliminar (sin pestañas)
        st.subheader("📐 Plano 2D Preliminar")

        if st.button("Generar Plano 2D", type="primary", use_container_width=True):
            try:
                from .floor_plan_svg import FloorPlanSVG
                planner = FloorPlanSVG(design)
                img_bytes = planner.generate()
                st.session_state['current_floor_plan'] = img_bytes
                st.session_state['current_design'] = design
                st.success("Plano generado correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"Error generando plano: {e}")
                import traceback
                st.code(traceback.format_exc())

        if 'current_floor_plan' in st.session_state:
            st.image(
                st.session_state['current_floor_plan'],
                caption="Plano profesional con medidas reales",
                use_container_width=True
            )
        else:
            st.info("Pulsa 'Generar Plano 2D' para ver tu distribución")
        
        st.markdown("---")
        
        # ANÁLISIS IA
        if 'current_floor_plan' in st.session_state:
            st.markdown("#### Análisis del Arquitecto IA")
            
            with st.spinner("Analizando..."):
                try:
                    from groq import Groq
                    import os
                    from dotenv import load_dotenv
                    from pathlib import Path
                    
                    project_root = Path(__file__).parent.parent.parent
                    load_dotenv(dotenv_path=project_root / '.env')
                    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                    
                    rooms_summary = "\n".join([
                        f"- {r.room_type.name}: {r.area_m2:.0f} m² ({r.area_m2:.1f}m × {r.area_m2/max(r.area_m2**0.5,1):.1f}m aprox)"
                        for r in design.rooms
                    ])
                    ENERGY_LABELS = {
                        'aerotermia': 'Aerotermia', 'geotermia': 'Geotermia',
                        'rainwater': 'Recuperación agua lluvia',
                        'insulation': 'Aislamiento natural', 'domotic': 'Domótica',
                        'solar': 'Paneles solares',
                    }
                    energy_sel = req.get('energy', {})
                    systems_summary = ", ".join([
                        ENERGY_LABELS[k] for k in ENERGY_LABELS if energy_sel.get(k)
                    ]) or "ninguno"
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": f"""Eres arquitecto experto en vivienda sostenible española.

Analiza esta distribución:
{rooms_summary}
TOTAL: {total_area_final:.0f} m²
PRESUPUESTO: €{budget:,}
ESTILO: {req.get('style', 'No especificado')}
SISTEMAS SOSTENIBLES SELECCIONADOS: {systems_summary}

Evalúa brevemente:
1. ¿Las medidas son correctas para una vivienda real? (mínimos CTE)
2. ¿Algún espacio demasiado grande o pequeño?
3. ¿El presupuesto es realista?
4. Una sugerencia de mejora concreta
5. En 1 frase por sistema: comenta profesionalmente cada sistema sostenible seleccionado indicando que se instalará en obra (no en el plano)

Máximo 200 palabras. Usa: ✅ para correcto, ⚠️ para mejorable, ❌ para problema."""}],
                        temperature=0.3,
                        max_tokens=300
                    )
                    
                    st.markdown(response.choices[0].message.content)
                
                except Exception as e:
                    st.warning(f"Análisis IA no disponible: {e}")

def render_step3_editor():
    """Paso 3: Editor 3D con Babylon.js"""
    
    st.header("Paso 3 – Editor 3D Avanzado")
    st.caption("Diseña tu casa con herramientas profesionales")
    
    # Validar datos
    req = st.session_state.get("ai_house_requirements", {})
    if not req or not req.get("ai_room_proposal"):
        st.warning("⚠️ Completa primero el Paso 1 y 2")
        if st.button("← Volver al Paso 2"):
            st.session_state["ai_house_step"] = 2
            st.rerun()
        return
    
    # Botón volver arriba
    if st.button("← Volver al Paso 2", key="back_to_2_top", use_container_width=True):
        st.session_state["ai_house_step"] = 2
        st.rerun()
    
    st.markdown("---")
    
    # Información del editor
    st.info("""
    🎯 **Editor 3D Profesional con Babylon.js**
    
    **Herramientas disponibles:**
    - 🖱️ Seleccionar y mover elementos
    - ⤢ Escalar habitaciones (ancho/fondo)
    - 🔝 Vista cenital (planta)
    - 💾 Guardar cambios (exportar JSON)
    
    **El asistente IA te ayudará a:**
    - ✅ Validar que tu diseño cumple normativa
    - ⚠️ Alertar sobre problemas técnicos
    """)
    
    # Botón abrir editor - DESTACADO
    st.markdown("### 🏗️ Diseña tu casa")
    
    if st.button("🏗️ Abrir Editor Babylon.js", type="primary", use_container_width=True, key="open_babylon"):
        
        # Obtener forma de casa
        house_shape = st.session_state.get('request', {}).get('house_shape', 'Rectangular (más común)')
        
        from .babylon_editor import generate_babylon_html
        
        # Obtener layout
        from .architect_layout import generate_layout
        
        rooms_data = []
        for room_data in req.get("ai_room_proposal", {}).items():
            rooms_data.append({
                'code': room_data[0],
                'name': room_data[0],
                'area_m2': room_data[1]
            })
        
        layout_result = generate_layout(rooms_data, house_shape)
        
        # Calcular dimensiones
        if layout_result:
            all_x = [item['x'] + item['width'] for item in layout_result]
            all_z = [item['z'] + item['depth'] for item in layout_result]
            total_width = max(all_x)
            total_depth = max(all_z)
        else:
            total_width = 10
            total_depth = 10
        
        roof_type = st.session_state.get('request', {}).get('roof_type', 'Dos aguas (clásico, eficiente)')
        plot_data = st.session_state.get("design_plot_data", {})
        plot_area_m2 = float(plot_data.get('total_m2', 0) or 0)
        req_data = st.session_state.get("ai_house_requirements", {})
        foundation_type = req_data.get("foundation_type", "Losa de hormigón (suelos blandos)")
        house_style = req_data.get("style", "Moderno")
        html_editor = generate_babylon_html(layout_result, total_width, total_depth, roof_type, plot_area_m2, foundation_type, house_style)
        
        # Guardar HTML en session_state para renderizar embebido
        st.session_state["babylon_html"] = html_editor
        st.session_state["babylon_editor_used"] = True
        st.rerun()

    # Receptor de capturas desde Babylon via componente HTML
    st.markdown("---")
    st.markdown("#### 📸 Capturas del Editor 3D")
    st.caption("Pulsa '📸 Capturar Vistas' en el editor 3D para guardar las perspectivas del proyecto")

    capture_receiver = """
    <script>
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'archirapid_captures') {
            const views = event.data.views;
            // Guardar en localStorage temporal para que Streamlit lo lea
            localStorage.setItem('archirapid_captures', JSON.stringify(views));
            document.getElementById('capture-msg').innerHTML = 
                '<b style="color:#27AE60">✅ ' + Object.keys(views).length + ' vistas capturadas y listas para el ZIP</b>';
            // también avisar al componente para que Python reciba los datos
            Streamlit.setComponentValue(JSON.stringify(views));
        }
    });
    </script>
    <div id="capture-msg" style="padding:8px; background:rgba(39,174,96,0.1); 
         border-radius:6px; color:#7F8C8D; font-size:13px;">
        📷 Esperando capturas del editor...
    </div>
    """
    captures = st.components.v1.html(capture_receiver, height=50)
    if captures:
        try:
            captures_dict = json.loads(captures)
            st.session_state['babylon_captures'] = captures_dict
            # generar miniaturas en segundo plano
            try:
                from PIL import Image
                import io, base64
                thumbs = {}
                for name, dataurl in captures_dict.items():
                    # dataurl = 'data:image/png;base64,...'
                    parts = dataurl.split(',', 1)
                    if len(parts) != 2:
                        continue
                    imgdata = base64.b64decode(parts[1])
                    img = Image.open(io.BytesIO(imgdata))
                    img.thumbnail((300, 300))
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    thumbs[name] = base64.b64encode(buf.getvalue()).decode('ascii')
                st.session_state['babylon_captures_thumb'] = thumbs
            except Exception:
                # si falla, simplemente ignorar
                pass
        except Exception:
            pass
    # Renderizar editor embebido si existe
    if st.session_state.get("babylon_html"):
        import streamlit.components.v1 as components

        st.info("💡 Usa las herramientas del editor 3D. Cuando termines, pulsa **💾 Guardar Cambios** dentro del editor para descargar el JSON.")

        components.html(
            st.session_state["babylon_html"],
            height=700,
            scrolling=False
        )
    
    # Botón continuar DESPUÉS del editor
    st.markdown("### ✅ Ya terminé de diseñar")
    
    col1, col2 = st.columns([1, 2])
    with col2:
        if st.button("Continuar a Documentación (Paso 4) →", type="primary", use_container_width=True, key="go_to_4_bottom"):
            st.session_state["ai_house_step"] = 4
            st.rerun()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _zip_images_dict(images_dict, thumb=False):
    """Return ZIP bytes containing png images taken from data‑URLs.

    If *thumb* is True the filenames get a ``_thumb`` suffix.
    """
    import io, zipfile, base64
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, dataurl in images_dict.items():
            parts = dataurl.split(',', 1)
            if len(parts) != 2:
                continue
            data = base64.b64decode(parts[1])
            fname = name + ("_thumb.png" if thumb else ".png")
            zf.writestr(fname, data)
    buf.seek(0)
    return buf.read()


def render_step3():
    """Paso 3: Documentación completa y monetización"""
    
    st.header("Paso 3 – Tu Proyecto Completo")
    st.caption("Documentación técnica, eficiencia energética y siguiente paso.")
    
    # Verificar si se usó el editor 3D



    st.markdown("---")

    # Verificar si se usó el editor 3D
    if st.session_state.get("babylon_editor_used", False):
        st.warning("""
        ⚠️ **DISEÑO MODIFICADO MANUALMENTE**
        
        Este proyecto ha sido editado con el editor 3D. Los cambios realizados:
        - Requieren validación por arquitecto colegiado
        - NO garantizan cumplimiento de normativa CTE
        - Pueden afectar presupuesto y plazos
        
        Nuestro equipo revisará el diseño antes de visar si contrata este servicio con nosotros.
        """)

    # Sincronización Babylon → Paso 4
    st.markdown("---")
    babylon_json = st.file_uploader(
        "📐 Si modificaste el diseño en Editor 3D, sube el JSON aquí:",
        type=['json'],
        key="babylon_sync_step4",
        help="El JSON se descarga al hacer 'Guardar Cambios' en Babylon"
    )

    if babylon_json:
        import json as _json
        try:
            babylon_data = _json.load(babylon_json)
            # Guardar en session_state
            st.session_state["babylon_modified_layout"] = babylon_data
            
            # CABLE BABYLON → ai_room_proposal
            # Actualizar propuesta con new_area de Babylon
            # para que los sliders del Paso 2 reflejen el diseño editado
            _req_sync = st.session_state.get("ai_house_requirements", {})
            if "ai_room_proposal" in _req_sync:
                for _room in babylon_data:
                    try:
                        _name = _room.get('name', '')
                        _new_area = float(_room.get('new_area', _room.get('original_area', 0)))
                        if _name and _new_area > 0:
                            _req_sync["ai_room_proposal"][ _name ] = round(_new_area, 1)
                    except (ValueError, TypeError):
                        continue
                st.session_state["ai_house_requirements"] = _req_sync
            
            # Recalcular con conversión segura
            total_area = 0
            original_area = 0

            _area_loaded = sum(float(r.get('new_area', r.get('original_area', 0))) for r in babylon_data)
            st.success(f"✅ Diseño cargado: {len(babylon_data)} habitaciones | {_area_loaded:.1f}m²")
            # NO hacer st.rerun() aquí
        except Exception as e:
            st.error(f"❌ Error: {e}")

    # Validar datos
    req = st.session_state.get("ai_house_requirements", {})
    proposal = req.get("ai_room_proposal", {})
    
    if not proposal:
        st.warning("Primero completa el Paso 1 y 2")
        if st.button("← Volver al inicio"):
            st.session_state["ai_house_step"] = 1
            st.rerun()
        return
    
    # Calcular datos del diseño
    budget = req.get('budget', 150000)
    style = req.get('style', 'No especificado')
    energy = req.get('energy', {})
    water_systems = req.get('water_systems', [])
    sewage_systems = req.get('sewage_systems', [])
    
    # Usar diseño FINAL via get_current_design_data (fuente única de verdad)
    design_data = get_current_design_data()
    total_area = design_data['total_area']
    rooms = design_data['rooms']
    # Mostrar miniaturas si ya tenemos capturas 3D
    if st.session_state.get('babylon_captures'):
        st.markdown("#### 📷 Vistas 3D capturadas")
        try:
            st.image(list(st.session_state['babylon_captures'].values()), width=200)
        except Exception:
            pass
        # archivo zip con vistas grandes
        zip_bytes = _zip_images_dict(st.session_state['babylon_captures'], thumb=False)
        st.download_button(
            label="📁 Descargar vistas 3D (ZIP)",
            data=zip_bytes,
            file_name="vistas_3d.zip",
            mime="application/zip"
        )
        # si tenemos miniaturas, mostrarlas y ofrecer descarga
        if st.session_state.get('babylon_captures_thumb'):
            st.markdown("#### 🔎 Miniaturas")
            try:
                thumb_urls = [f"data:image/png;base64,{b64}" for b64 in st.session_state['babylon_captures_thumb'].values()]
                st.image(thumb_urls, width=100)
            except Exception:
                pass
            zip_thumb = _zip_images_dict({k: f"data:image/png;base64,{b64}" for k,b64 in st.session_state['babylon_captures_thumb'].items()}, thumb=True)
            st.download_button(
                label="📁 Descargar miniaturas (ZIP)",
                data=zip_thumb,
                file_name="miniaturas_3d.zip",
                mime="application/zip"
            )
    # Indicador visual de origen
    if design_data['modified']:
        st.success("🏗️ **Diseño desde Editor 3D** - Versión personalizada")
    else:
        st.info("🤖 **Diseño generado por IA** - Propuesta original")
    # Costes por partidas
    construction_cost = int(total_area * 1100)
    foundation_cost = int(total_area * 180)
    installation_cost = int(total_area * 150)
    architecture_cost = int((construction_cost + foundation_cost) * 0.08)
    total_cost = construction_cost + foundation_cost + installation_cost + architecture_cost
    
    # Calcular subvenciones
    subsidy = 0
    if energy.get('solar'): subsidy += 3000
    if energy.get('aerotermia'): subsidy += 5000
    if energy.get('geotermia'): subsidy += 8000
    if energy.get('insulation'): subsidy += 2000
    if energy.get('rainwater'): subsidy += 1000
    if energy.get('domotic'): subsidy += 500
    subsidy_total = min(subsidy, int(total_cost * 0.40))
    
    # ============================================
    # RESUMEN EJECUTIVO - ARRIBA
    # ============================================
    st.markdown("### Tu Proyecto en Números")
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Coste Total Estimado",
        f"€{total_cost:,}",
        delta=f"vs €{int(total_area * 3500):,} piso ciudad",
        delta_color="normal"
    )
    col2.metric(
        "Subvenciones Estimadas",
        f"€{subsidy_total:,}",
        delta=f"Coste neto: €{total_cost - subsidy_total:,}",
        delta_color="normal"
    )
    col3.metric(
        "Superficie Total",
        f"{total_area:.0f} m²",
        delta=f"Estilo: {style.split(' ')[-1]}"
    )
    col4.metric(
        "Ahorro vs Piso Ciudad",
        f"€{int(total_area * 3500) - (total_cost - subsidy_total):,}",
        delta="Ahorro real con subvenciones"
    )
    
    st.markdown("---")
    
    # ============================================
    # DOS COLUMNAS: ENERGÍA + PRESUPUESTO
    # ============================================
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        
        # EFICIENCIA ENERGÉTICA
        st.markdown("### Eficiencia Energética")
        
        # Calcular calificación
        energy_score = 0
        if energy.get('solar'): energy_score += 25
        if energy.get('aerotermia'): energy_score += 20
        if energy.get('geotermia'): energy_score += 20
        if energy.get('insulation'): energy_score += 15
        if energy.get('rainwater'): energy_score += 10
        if energy.get('domotic'): energy_score += 10
        
        if energy_score >= 60:
            rating = "A"
            rating_color = "#2ECC71"
            rating_text = "Máxima eficiencia energética"
        elif energy_score >= 40:
            rating = "B"
            rating_color = "#27AE60"
            rating_text = "Alta eficiencia energética"
        elif energy_score >= 20:
            rating = "C"
            rating_color = "#F39C12"
            rating_text = "Eficiencia media"
        else:
            rating = "D"
            rating_color = "#E74C3C"
            rating_text = "Eficiencia básica"
        
        # Badge de calificación
        st.markdown(f"""
        <div style='background: {rating_color}; padding: 20px; border-radius: 10px; 
                    text-align: center; color: white; margin-bottom: 15px;'>
            <h1 style='margin:0; font-size: 60px;'>{rating}</h1>
            <p style='margin:0; font-size: 16px;'>{rating_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Detalles energéticos
        consumo_base = total_area * 120  # kWh/año casa normal
        ahorro_pct = energy_score * 0.9
        consumo_real = int(consumo_base * (1 - ahorro_pct/100))
        ahorro_euros = int((consumo_base - consumo_real) * 0.18)
        co2_evitado = int((consumo_base - consumo_real) * 0.25 / 1000 * 10) / 10
        
        e1, e2 = st.columns(2)
        e1.metric("Consumo estimado", f"{consumo_real:,} kWh/año",
                 delta=f"-{ahorro_pct:.0f}% vs media")
        e2.metric("Ahorro energético", f"€{ahorro_euros:,}/año",
                 delta="vs casa convencional")
        
        st.metric("CO₂ evitado", f"{co2_evitado} ton/año",
                 delta="Contribución al medioambiente")
        
        # Sistemas instalados
        st.markdown("**Sistemas sostenibles incluidos:**")
        systems = []
        if energy.get('solar'): systems.append("☀️ Paneles solares fotovoltaicos")
        if energy.get('aerotermia'): systems.append("🌡️ Aerotermia (calefacción/frío)")
        if energy.get('geotermia'): systems.append("🌍 Geotermia")
        if energy.get('insulation'): systems.append("🌿 Aislamiento natural")
        if energy.get('rainwater'): systems.append("💧 Recuperación agua lluvia")
        if energy.get('domotic'): systems.append("🏠 Domótica inteligente")
        if water_systems: systems.append(f"💧 Agua: {' + '.join(water_systems)}")
        if sewage_systems: systems.append(f"♻️ Saneamiento: {' + '.join(sewage_systems)}")
        
        for s in systems:
            st.markdown(f"- {s}")
        
        st.markdown("---")
        
        # SUBVENCIONES
        st.markdown("### Subvenciones Disponibles")
        
        subsidy_data = []
        if energy.get('solar'):
            subsidy_data.append(("☀️ Paneles solares (IDAE)", "€3,000"))
        if energy.get('aerotermia'):
            subsidy_data.append(("🌡️ Aerotermia (NextGen EU)", "€5,000"))
        if energy.get('geotermia'):
            subsidy_data.append(("🌍 Geotermia (NextGen EU)", "€8,000"))
        if energy.get('insulation'):
            subsidy_data.append(("🌿 Aislamiento (IDAE)", "€2,000"))
        if energy.get('rainwater'):
            subsidy_data.append(("💧 Agua lluvia (CC.AA.)", "€1,000"))
        
        if subsidy_data:
            for name, amount in subsidy_data:
                col_s1, col_s2 = st.columns([3, 1])
                col_s1.markdown(f"- {name}")
                col_s2.markdown(f"**{amount}**")
            
            st.success(f"Total estimado: **€{subsidy_total:,}** (hasta 40% del coste)")
            st.caption("Sujeto a convocatorias vigentes. Consulta con nuestro equipo.")
        else:
            st.info("Activa sistemas sostenibles en el Paso 1 para acceder a subvenciones")
    
    with col_right:
        
        # PRESUPUESTO DETALLADO
        st.markdown("### Presupuesto por Partidas")
        
        import pandas as pd
        
        partidas = [
            ("1. Cimentación", f"€{foundation_cost:,}", 
             f"{int(foundation_cost/total_cost*100)}%",
             "Zapatas/losa según estudio geotécnico"),
            ("2. Estructura y cubierta", f"€{int(construction_cost*0.35):,}",
             "32%", "Estructura + tejado + cerramientos ext."),
            ("3. Cerramientos y tabiquería", f"€{int(construction_cost*0.20):,}",
             "18%", "Fachada, ventanas, puertas, tabiques int."),
            ("4. Instalaciones", f"€{installation_cost:,}",
             f"{int(installation_cost/total_cost*100)}%",
             "Elec., fontanería, climatización, domótica"),
            ("5. Acabados", f"€{int(construction_cost*0.25):,}",
             "23%", "Pavimentos, pintura, cocina, baños"),
            ("6. Sistemas sostenibles", f"€{st.session_state.get('energy_cost_total', int(construction_cost*0.10)):,}",
             f"{int(st.session_state.get('energy_cost_total', construction_cost*0.10)/max(total_cost,1)*100)}%",
             "Paneles, aerotermia, geotermia, domótica, agua lluvia"),
            ("7. Honorarios técnicos", f"€{architecture_cost:,}",
             "8%", "Arquitecto, aparejador, licencias"),
        ]
        
        df = pd.DataFrame(partidas, 
                         columns=["Partida", "Coste", "%", "Descripción"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Total
        st.markdown(f"""
        <div style='background: #2C3E50; padding: 15px; border-radius: 8px; 
                    color: white; text-align: center;'>
            <h3 style='margin:0;'>TOTAL: €{total_cost:,}</h3>
            <p style='margin:5px 0 0 0; font-size:14px;'>
                Neto con subvenciones: €{total_cost - subsidy_total:,}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # PLANO FINAL (siempre desde get_final_design)
        st.markdown("### Tu Plano")

        final_rooms_for_plan = get_final_design()
        plan_source = final_rooms_for_plan.get('source', 'ai_original')
        plan_label = {
            'babylon': '🏗️ Plano desde Editor 3D',
            'step2_sliders': '📊 Plano con ajustes del Paso 2',
            'ai_original': '🤖 Plano propuesta IA'
        }.get(plan_source, 'Plano de distribución')

        if st.button("🗺️ Generar Plano Final", type="primary", use_container_width=True, key="gen_plan_paso4"):
            try:
                from .architect_layout import generate_layout
                from .floor_plan_svg import FloorPlanSVG
                from .data_model import HouseDesign, Plot, RoomType, RoomInstance

                house_shape = st.session_state.get('request', {}).get('house_shape', 'Rectangular')
                rooms_for_layout = []
                for r in final_rooms_for_plan['rooms']:
                    rooms_for_layout.append({
                        'code': r.get('code', r.get('name', 'espacio')),
                        'name': r.get('name', 'Espacio'),
                        'area_m2': float(r.get('area_m2', 10))
                    })

                layout = generate_layout(rooms_for_layout, house_shape)

                plot = Plot(id='final', area_m2=500, buildable_ratio=0.33)
                design_for_plan = HouseDesign(plot)
                for r in final_rooms_for_plan['rooms']:
                    rt = RoomType(
                        code=r.get('code', 'espacio'),
                        name=r.get('name', 'Espacio'),
                        min_m2=2, max_m2=200,
                        base_cost_per_m2=1000
                    )
                    design_for_plan.rooms.append(RoomInstance(room_type=rt, area_m2=float(r.get('area_m2', 10))))

                planner = FloorPlanSVG(design_for_plan)
                img_bytes = planner.generate()
                st.session_state['final_floor_plan'] = img_bytes
                st.success(f"✅ Plano generado desde: {plan_label}")

            except Exception as e:
                st.error(f"❌ Error generando plano: {e}")
                import traceback
                st.code(traceback.format_exc())

        if 'final_floor_plan' in st.session_state:
            st.image(
                st.session_state['final_floor_plan'],
                caption=plan_label,
                use_container_width=True
            )
        elif 'current_floor_plan' in st.session_state:
            st.image(
                st.session_state['current_floor_plan'],
                caption="Plano del Paso 2 (genera el plano final arriba)",
                use_container_width=True
            )
        else:
            st.info("Pulsa 'Generar Plano Final' para ver el plano correcto")

        st.markdown("---")
        
        # DESCARGAS
        st.markdown("### Descargas")
        
        dl1, dl2 = st.columns(2)
        
        with dl1:
            plan_to_download = st.session_state.get('final_floor_plan') or st.session_state.get('current_floor_plan')
            if plan_to_download:
                st.download_button(
                    label="Descargar Plano PNG",
                    data=plan_to_download,
                    file_name="plano_archirapid_final.png",
                    mime="image/png",
                    use_container_width=True
                )
        
        with dl2:
            # Excel presupuesto
            try:
                import io
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
                
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Presupuesto"
                
                # Cabecera
                ws['A1'] = "PRESUPUESTO ARCHIRAPID"
                ws['A1'].font = Font(bold=True, size=14)
                ws['A2'] = f"Superficie: {total_area:.0f} m² | Estilo: {style}"
                
                # Headers
                headers = ["Partida", "Coste (€)", "% Total", "Descripción"]
                for col, h in enumerate(headers, 1):
                    cell = ws.cell(row=4, column=col, value=h)
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="2C3E50")
                
                # Datos
                for row, (partida, coste, pct, desc) in enumerate(partidas, 5):
                    ws.cell(row=row, column=1, value=partida)
                    ws.cell(row=row, column=2, value=coste)
                    ws.cell(row=row, column=3, value=pct)
                    ws.cell(row=row, column=4, value=desc)
                
                # Total
                ws.cell(row=len(partidas)+6, column=1, value="TOTAL").font = Font(bold=True)
                ws.cell(row=len(partidas)+6, column=2, value=f"€{total_cost:,}").font = Font(bold=True)
                ws.cell(row=len(partidas)+7, column=1, value="Con subvenciones").font = Font(bold=True)
                ws.cell(row=len(partidas)+7, column=2, value=f"€{total_cost-subsidy_total:,}").font = Font(bold=True, color="2ECC71")
                
                # Ajustar columnas
                ws.column_dimensions['A'].width = 30
                ws.column_dimensions['B'].width = 15
                ws.column_dimensions['C'].width = 10
                ws.column_dimensions['D'].width = 45
                
                excel_buffer = io.BytesIO()
                wb.save(excel_buffer)
                excel_buffer.seek(0)
                
                st.download_button(
                    label="Descargar Excel",
                    data=excel_buffer.getvalue(),
                    file_name="presupuesto_archirapid.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.warning(f"Excel no disponible: {e}")
    
    st.markdown("---")
    
    # ============================================
    # CONSTRUCTORES ASOCIADOS - MONETIZACIÓN
    # ============================================
    st.markdown("### Constructores Asociados")
    st.caption("Solicita presupuesto real a constructores verificados de tu zona")
    
    constructors = [
        {
            "name": "Construcciones EcoVerde",
            "specialty": "Vivienda sostenible y bioconstrucción",
            "rating": "⭐⭐⭐⭐⭐",
            "projects": "127 proyectos",
            "zone": "Andalucía, Extremadura"
        },
        {
            "name": "BuildGreen España",
            "specialty": "Casas pasivas y certificación energética",
            "rating": "⭐⭐⭐⭐⭐",
            "projects": "89 proyectos",
            "zone": "Nacional"
        },
        {
            "name": "Construye Rural",
            "specialty": "Vivienda rural, piedra natural y madera",
            "rating": "⭐⭐⭐⭐",
            "projects": "203 proyectos",
            "zone": "Todo el territorio"
        }
    ]
    
    cols = st.columns(3)
    for col, constructor in zip(cols, constructors):
        with col:
            st.markdown(f"""
            <div style='border: 1px solid #ddd; border-radius: 10px; 
                        padding: 15px; height: 200px;'>
                <h4 style='color: #2C3E50; margin-top:0;'>{constructor["name"]}</h4>
                <p style='font-size:12px; color:#666;'>{constructor["specialty"]}</p>
                <p>{constructor["rating"]}</p>
                <p style='font-size:11px;'>📁 {constructor["projects"]}</p>
                <p style='font-size:11px;'>📍 {constructor["zone"]}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.button(
                f"Solicitar Presupuesto",
                key=f"constructor_{constructor['name']}",
                use_container_width=True,
                type="primary"
            )
    
    st.info("ArchiRapid cobra una comisión del 3% al constructor cuando se formaliza el contrato. Sin coste para el cliente.")
    
    st.markdown("---")
    
    # NAVEGACIÓN
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Volver al Paso 2", use_container_width=True):
            st.session_state["ai_house_step"] = 2
            st.rerun()
    with col2:
        if st.button("✅ He terminado el diseño — Ver opciones de proyecto", type="primary", use_container_width=True):
            st.session_state["mostrar_monetizacion"] = True
            st.rerun()

    # ================================================
    # BLOQUE MONETIZACIÓN — solo visible tras aprobar
    # ================================================
    if st.session_state.get("mostrar_monetizacion", False):

        st.markdown("---")
        st.markdown("## 📋 Tu Proyecto Está Listo")
        st.success("✅ Diseño aprobado. Selecciona los servicios que necesitas.")

        # Leer presupuesto real del proyecto
        req = st.session_state.get("ai_house_requirements", {})
        design_data = get_current_design_data()
        presupuesto_obra = design_data.get('total_cost', 200000)

        # ------------------------------------------
        # DOCUMENTACIÓN BASE
        # ------------------------------------------
        st.markdown("### 📄 Documentación del Proyecto")
        col_doc1, col_doc2 = st.columns(2)

        with col_doc1:
            st.markdown("""
            **📦 Paquete PDF Completo** *(1ª copia gratis)*
            - Memoria descriptiva
            - Plano 2D
            - Presupuesto por partidas
            - Calificación energética
            - Datos cimientos y extras
            """)
            pdf_copias = st.number_input("Copias adicionales PDF (150€/copia)", min_value=0, max_value=10, value=0, key="pdf_copias")

        with col_doc2:
            st.markdown("""
            **📐 Paquete CAD/BIM Profesional**
            - Todo lo del PDF
            - Archivos editables CAD
            - Modelo 3D exportable (.glb)
            - Apto para constructor y arquitecto
            """)
            cad_copias = st.number_input("Copias CAD (250€/copia)", min_value=0, max_value=10, value=0, key="cad_copias")

        coste_doc = int(presupuesto_obra * 0.01) + (pdf_copias * 150) + (cad_copias * 250)

        st.info(f"💰 **Proyecto completo (1% presupuesto): €{int(presupuesto_obra * 0.01):,}** + copias adicionales: €{(pdf_copias*150)+(cad_copias*250):,}")

        # ------------------------------------------
        # SERVICIOS TÉCNICOS
        # ------------------------------------------
        st.markdown("### 🔧 Servicios Técnicos Profesionales")
        st.caption("Todos gestionados por ArchiRapid con profesionales colegiados")

        servicios = {
            "visado": {"label": "📋 Visado del Proyecto (Colegio Arquitectos)", "precio": int(presupuesto_obra * 0.015), "desc": "Obligatorio para licencia de obra. ~1.5% presupuesto"},
            "revision": {"label": "🔍 Revisión y Validación Técnica", "precio": 450, "desc": "Arquitecto revisa y firma el diseño ArchiRapid"},
            "licencia": {"label": "🏛️ Gestión Licencia Municipal", "precio": 800, "desc": "Tramitación completa ante el Ayuntamiento"},
            "constructor": {"label": "👷 Búsqueda y Contrato Constructor", "precio": int(presupuesto_obra * 0.005), "desc": f"0.5% del presupuesto. Selección, negociación y contrato"},
            "fontaneria": {"label": "🚿 Proyecto Fontanería e Instalaciones", "precio": 650, "desc": "Planos de agua, saneamiento y climatización"},
            "electricidad": {"label": "⚡ Proyecto Eléctrico BT", "precio": 550, "desc": "Esquema unifilar, cuadro eléctrico, domótica"},
            "energia": {"label": "☀️ Auditoría Energética + CEE", "precio": 380, "desc": "Certificado Eficiencia Energética oficial"},
            "geotecnico": {"label": "🔬 Estudio Geotécnico del Terreno", "precio": 1200, "desc": "Obligatorio para cálculo de cimientos"},
            "topografia": {"label": "📏 Levantamiento Topográfico", "precio": 900, "desc": "Medición precisa de la parcela"},
            "seguridad": {"label": "🦺 Estudio Seguridad y Salud", "precio": 350, "desc": "Obligatorio para obras con proyecto"},
            "vr": {"label": "🥽 Tour Virtual 360° / Realidad Virtual", "precio": 290, "desc": "Recorrido inmersivo de tu vivienda antes de construir"},
        }

        seleccionados = {}
        coste_servicios = 0

        cols_svc = st.columns(2)
        for i, (key, svc) in enumerate(servicios.items()):
            col = cols_svc[i % 2]
            with col:
                checked = st.checkbox(
                    f"{svc['label']} — **€{svc['precio']:,}**",
                    key=f"svc_{key}",
                    help=svc['desc']
                )
                if checked:
                    seleccionados[key] = svc['precio']
                    coste_servicios += svc['precio']

        # ------------------------------------------
        # RESUMEN TOTAL
        # ------------------------------------------
        st.markdown("---")
        total_monetizacion = coste_doc + coste_servicios

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e, #2C3E50);
                    padding: 20px; border-radius: 12px; color: white; text-align: center;
                    border: 2px solid #27AE60;'>
            <h3 style='margin:0; color:#27AE60;'>TOTAL SERVICIOS SELECCIONADOS</h3>
            <h1 style='margin:10px 0; color:white;'>€{total_monetizacion:,}</h1>
            <p style='margin:0; font-size:13px; color:#aaa;'>
                Documentación: €{coste_doc:,} | Servicios técnicos: €{coste_servicios:,}
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_pay1, col_pay2 = st.columns(2)
        with col_pay1:
            if st.button("💳 Pagar con Tarjeta (Simulado)", type="primary", use_container_width=True):
                st.session_state["pago_completado"] = True
                st.session_state["servicios_contratados"] = seleccionados
                st.session_state["total_pagado"] = total_monetizacion
                st.rerun()
        with col_pay2:
            if st.button("📞 Hablar con un Arquitecto", use_container_width=True):
                st.info("📧 Contacto: info@archirapid.es | ☎️ 900 XXX XXX")

        # ------------------------------------------
        # POST-PAGO — desbloquear descargas
        # ------------------------------------------
        if st.session_state.get("pago_completado", False):
            st.balloons()
            st.success(f"✅ Pago simulado de €{st.session_state.get('total_pagado',0):,} procesado. ¡Tu proyecto está listo!")

            st.markdown("### 📥 Descarga Tu Proyecto Completo")

            try:
                zip_bytes, zip_filename = generar_zip_proyecto(
                    req=st.session_state.get("ai_house_requirements", {}),
                    design_data=get_current_design_data(),
                    plot_data=st.session_state.get("design_plot_data", {}),
                    partidas=partidas,
                    subsidy_total=subsidy_total,
                    energy_label=rating if 'rating' in dir() else "B"
                )

                st.download_button(
                    label="📦 DESCARGAR TODO EL PROYECTO (ZIP)",
                    data=zip_bytes,
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
                st.caption("Incluye: Memoria descriptiva · Mediciones y presupuesto Excel · Plano 2D · Datos catastro · Layout 3D · Guía de próximos pasos")

            except Exception as e:
                st.error(f"Error generando ZIP: {e}")
                import traceback
                st.code(traceback.format_exc())

            st.markdown("---")
            st.info("📬 Proyecto guardado en tu **Panel de Cliente**. El equipo ArchiRapid recibirá notificación inmediata.")