"""
Motor layout v4.0 - Filas horizontales reales
Basado en plano chalet español típico:

FILA 1 (norte/fondo): [SALON] [COCINA] [GARAJE]
FILA 2 (centro):      [PASILLO HORIZONTAL COMPLETO]
FILA 3 (sur/frente):  [BAÑO] [DORM1] [BAÑO] [DORM2] [DORM.PRINC+BAÑO]
EXTERIOR SUR:         [PORCHE ancho completo]
EXTERIOR NORTE:       [PISCINA]
EXTERIOR LATERAL:     [HUERTO] [CASETA]
"""
from dataclasses import dataclass
from typing import List, Dict
import math

ZONE_DAY = "day"
ZONE_NIGHT = "night"
ZONE_WET = "wet"
ZONE_CIRCULATION = "circ"
ZONE_SERVICE = "service"
ZONE_EXTERIOR = "exterior"
ZONE_GARDEN = "garden"

def classify(code: str, name: str) -> str:
    c = (code + name).lower()
    if any(x in c for x in ['piscin','pool','huerto','caseta','apero','panel','solar','bomba',
                             'tejavana','barbacoa','pozo','instalacion']):
        return ZONE_GARDEN
    if any(x in c for x in ['porche','terraza']):
        return ZONE_EXTERIOR
    if any(x in c for x in ['garaje','garage','bodega']):
        return ZONE_SERVICE
    if any(x in c for x in ['pasillo','distribuidor','hall','recibidor']):
        return ZONE_CIRCULATION
    if any(x in c for x in ['bano','baño','aseo','wc']):
        return ZONE_WET
    if any(x in c for x in ['dormitorio','habitacion','suite']):
        return ZONE_NIGHT
    return ZONE_DAY

@dataclass
class R:
    code: str
    name: str
    area: float
    zone: str
    x: float = 0.0
    z: float = 0.0
    w: float = 0.0
    d: float = 0.0

class ArchitectLayout:
    """
    Layout fijo tipo chalet español.
    
    PLANTA (vista desde arriba, norte arriba):
    
    ┌──────────────────────────────────────────┐ ← z_fila1_top
    │  SALON/COCINA    │  ESTUDIO/EXTRA  │GARAJE│
    ├──────────────────────────────────────────┤ ← z_pasillo_top  
    │  PASILLO DISTRIBUIDOR (ancho total casa) │
    ├──────────────────────────────────────────┤ ← z_pasillo_bot
    │BAÑO│DORMITORIO 1│BAÑO│DORM2│BAÑO+DORM.P.│
    └──────────────────────────────────────────┘ ← z_fila3_bot
    │  PORCHE (ancho total casa)               │
    └──────────────────────────────────────────┘
    
    Al norte (z negativo): PISCINA
    Al este (x positivo): HUERTO, CASETA
    """

    PASILLO_H = 1.2  # Altura (profundidad) del pasillo horizontal

    def __init__(self, rooms_data, house_shape: str = "Rectangular"):
        self.raw = rooms_data
        self.house_shape = house_shape  # Nuevo parámetro

    def _rooms_by_zone(self, rooms, *zones):
        return [r for r in rooms if r.zone in zones]

    def generate(self) -> List[Dict]:
        # Crear rooms
        all_rooms = []
        for rd in self.raw:
            zone = classify(rd['code'], rd['name'])
            # asegurar que el área sea un número para evitar comparaciones str/float
            try:
                area_val = float(rd.get('area_m2', 0))
            except (TypeError, ValueError):
                area_val = 0.0
            area_val = max(area_val, 2.0)
            r = R(rd['code'], rd['name'], area_val, zone)
            all_rooms.append(r)

        day   = self._rooms_by_zone(all_rooms, ZONE_DAY)
        night = self._rooms_by_zone(all_rooms, ZONE_NIGHT)
        wet   = self._rooms_by_zone(all_rooms, ZONE_WET)
        svc   = self._rooms_by_zone(all_rooms, ZONE_SERVICE)
        ext   = self._rooms_by_zone(all_rooms, ZONE_EXTERIOR)
        gdn   = self._rooms_by_zone(all_rooms, ZONE_GARDEN)

        # Dormitorios: principal primero
        night.sort(key=lambda r: r.area, reverse=True)

        # Separar garaje del resto de servicios
        garajes = [r for r in svc if 'garaje' in r.code.lower()
                   or 'garage' in r.code.lower()]
        otros_svc = [r for r in svc if r not in garajes]

        # Jardín
        piscinas = [r for r in gdn if 'piscin' in r.code.lower()
                    or 'pool' in r.code.lower()]
        laterales = [r for r in gdn if r not in piscinas]

        layout = []

        # ================================================
        # PASO 1: CALCULAR ANCHO TOTAL DE LA CASA
        # Basado en dormitorios (fila más ancha normalmente)
        # Cada dormitorio tiene un ancho proporcional a su área
        # ================================================
        
        # Profundidad fija para cada fila
        FILA1_D = 4.5   # Profundidad zona día (salón/cocina)
        FILA3_D = 3.5   # Profundidad zona noche (dormitorios)
        
        # Calcular ancho de cada dormitorio en fila 3
        # Todos tienen la misma profundidad (FILA3_D)
        # El ancho se calcula por área
        night_widths = []
        for r in night:
            w = round(r.area / FILA3_D, 1)
            w = max(w, 2.8)   # mínimo 2.8m de ancho
            night_widths.append(w)

        # Calcular ancho de cada baño en fila 3
        # Los baños van ANTES de cada dormitorio (entre pasillo y dorm)
        # 1 baño cortesía + 1 por dormitorio (excepto últimos sin baño)
        bano_widths = []
        for r in wet:
            w = round(r.area / FILA3_D, 1)
            w = max(w, 1.5)   # mínimo 1.5m
            w = min(w, 2.5)   # máximo 2.5m
            bano_widths.append(w)

        # Ancho fila 3: suma de dormitorios + baños
        # Agrupación suite: bano_principal/bano_suite → DESPUÉS de dormitorio_principal
        # Resto de baños → ANTES de su dormitorio
        fila3_rooms = []  # Lista ordenada: (room, width)

        def _is_suite_bano(r: R) -> bool:
            c = r.code.lower()
            return any(k in c for k in ('suite', 'principal', 'ensuite', 'en_suite', 'master'))

        # Separar baños de suite del resto
        suite_banos = [r for r in wet if _is_suite_bano(r)]
        regular_banos = [r for r in wet if r not in suite_banos]
        wet_regular_widths = [bano_widths[wet.index(r)] for r in regular_banos]
        wet_suite_widths   = [bano_widths[wet.index(r)] for r in suite_banos]

        # Distribuir baños normales ANTES de cada dormitorio; baños suite DESPUÉS del principal
        bano_idx = 0
        for i, (r, w) in enumerate(zip(night, night_widths)):
            is_principal = (i == 0)  # dormitorio principal = primero (ya ordenado por área desc)
            # Baño regular antes de cada dormitorio
            if bano_idx < len(regular_banos):
                bano = regular_banos[bano_idx]
                bw = wet_regular_widths[bano_idx]
                fila3_rooms.append((bano, bw, FILA3_D))
                bano_idx += 1
            fila3_rooms.append((r, w, FILA3_D))
            # Baño suite DESPUÉS del dormitorio principal (en-suite layout)
            if is_principal and suite_banos:
                for sb, sbw in zip(suite_banos, wet_suite_widths):
                    fila3_rooms.append((sb, sbw, FILA3_D))

        # Baños regulares sobrantes
        while bano_idx < len(regular_banos):
            bano = regular_banos[bano_idx]
            bw = wet_regular_widths[bano_idx]
            fila3_rooms.append((bano, bw, FILA3_D))
            bano_idx += 1

        house_w = sum(item[1] for item in fila3_rooms)
        house_w = max(house_w, 8.0)   # mínimo 8m
        house_w = min(house_w, 18.0)  # máximo 18m

        # Reescalar anchos de fila3 para que encajen EXACTAMENTE en house_w
        # Evita que la última habitación desborde cuando hay muchas dependencias
        raw_w = sum(item[1] for item in fila3_rooms)
        if raw_w > 0 and abs(raw_w - house_w) > 0.01:
            scale = house_w / raw_w
            fila3_rooms = [(r, round(w * scale, 2), d) for (r, w, d) in fila3_rooms]

        # ================================================
        # PASO 2: FILA 1 - ZONA DÍA
        # [SALON | COCINA | (otros día) | GARAJE]
        # Todos con la misma profundidad FILA1_D
        # ================================================
        
        # Zona día ocupa el ancho disponible sin garaje
        garaje_w = 0.0
        if garajes:
            for r in garajes:
                gw = round(r.area / FILA1_D, 1)
                gw = max(gw, 3.5)
                r.w = gw
                r.d = FILA1_D
                garaje_w += gw

        day_w_available = house_w  # garaje va lateral, no resta ancho día
        day_w_available = max(day_w_available, 5.0)

        # Zona día arranca en z=0. Porche va a z negativo (delante, sur)
        # → normalización lo lleva a z_MIN = fachada entrada visible
        z_dia = 0.0

        # Distribuir zona día en el espacio disponible
        if day:
            day_area_total = sum(r.area for r in day)
            x_day = 0.0
            for r in day:
                # Ancho proporcional al área
                r.w = round(day_w_available * (r.area / day_area_total), 1)
                r.w = max(r.w, 3.0)
                r.d = FILA1_D
                r.x = x_day
                r.z = z_dia
                layout.append(self._d(r))
                x_day += r.w

            # Ajustar último para cerrar exacto
            if day:
                day[-1].w = day_w_available - sum(
                    r.w for r in day[:-1])
                day[-1].w = max(day[-1].w, 3.0)
                layout[-1] = self._d(day[-1])
        
        # Otros servicios (bodega etc) en fila día
        x_otros = sum(r.w for r in day)
        for r in otros_svc:
            r.w = max(round(r.area / FILA1_D, 1), 2.0)
            r.d = FILA1_D
            r.x = x_otros
            r.z = z_dia
            layout.append(self._d(r))
            x_otros += r.w

        # Garaje lateral este (fuera de la huella de la casa, junto a zona día)
        x_garaje = house_w + 1.0
        for r in garajes:
            r.x = x_garaje
            r.z = z_dia
            layout.append(self._d(r))
            x_garaje += r.w

        # ================================================
        # PASO 3: PASILLO HORIZONTAL
        # Ocupa TODO el ancho de la casa
        # Es el distribuidor que conecta día con noche
        # ================================================
        
        z_pasillo = z_dia + FILA1_D
        
        # Crear pasillo si no existe
        pasillo_list = self._rooms_by_zone(all_rooms, ZONE_CIRCULATION)
        if not pasillo_list:
            p = R('pasillo', 'Distribuidor',
                  house_w * self.PASILLO_H, ZONE_CIRCULATION)
            pasillo_list = [p]
            all_rooms.append(p)
        
        for p in pasillo_list:
            p.w = house_w
            p.d = self.PASILLO_H
            p.x = 0.0
            p.z = z_pasillo
            layout.append(self._d(p))

        # ================================================
        # PASO 4: FILA 3 - ZONA NOCHE
        # [BAÑO][DORM1][BAÑO][DORM2][BAÑO][DORM.PRINC]
        # Todos con la misma profundidad FILA3_D
        # Posicionados de IZQUIERDA a DERECHA
        # ================================================
        
        z_fila3 = z_pasillo + self.PASILLO_H
        
        x_cursor = 0.0
        for (r, w, d) in fila3_rooms:
            r.w = w
            r.d = d
            r.x = x_cursor
            r.z = z_fila3
            layout.append(self._d(r))
            x_cursor += w

        z_casa_bottom = z_fila3 + FILA3_D

        # ================================================
        # PASO 5: PORCHE (fachada sur - ENTRADA)
        # z=0 — primer elemento, fachada de entrada
        # ================================================
        
        for r in ext:
            r.w = house_w
            r.d = max(round(r.area / house_w, 1), 2.0)
            r.x = 0.0
            r.z = -r.d  # delante de zona día (z negativo → normaliz. lo pone en z_MIN = entrada)
            layout.append(self._d(r))

        # ================================================
        # PASO 6: PISCINA (norte - detrás de la casa)
        # ================================================
        
        for r in piscinas:
            r.w = max(round(math.sqrt(r.area * 2.0), 1), 5.0)
            r.d = round(r.area / r.w, 1)
            r.x = (house_w - r.w) / 2  # centrada
            r.z = z_casa_bottom + 1.0    # NORTE: jardín privado trasero, 1m tras zona noche
            layout.append(self._d(r))

        # ================================================
        # PASO 7: JARDÍN LATERAL (este)
        # Huerto, caseta, otros
        # ================================================
        
        x_lat = house_w + 1.0
        z_lat = z_fila3  # junto a zona noche, sin solapamiento con garaje (z_dia)
        for r in laterales:
            r.w = round(math.sqrt(r.area * 1.3), 1)
            r.d = round(r.area / r.w, 1)
            r.x = x_lat
            r.z = z_lat
            layout.append(self._d(r))
            z_lat += r.d + 1.0

        # ================================================
        # NORMALIZAR a coordenadas positivas
        # ================================================
        if layout:
            min_x = min(i['x'] for i in layout)
            min_z = min(i['z'] for i in layout)
            ox = max(0.0, -min_x) + 2.0
            oz = max(0.0, -min_z) + 2.0
            for i in layout:
                i['x'] += ox
                i['z'] += oz

        # ================================================
        # POST-PASS 1: PACK ROWS — eliminar huecos en eje X por fila
        # ================================================
        _SNAP = 0.6
        rows: dict = {}
        for item in layout:
            z_key = None
            for k in rows:
                if abs(float(k) - item['z']) < _SNAP:
                    z_key = k
                    break
            if z_key is None:
                z_key = f"{item['z']:.2f}"
                rows[z_key] = []
            rows[z_key].append(item)

        for z_key, row in rows.items():
            row.sort(key=lambda i: i['x'])
            row_z = float(z_key)
            row_d = max(i['depth'] for i in row)
            cur_x = min(i['x'] for i in row)
            for item in row:
                item['x'] = round(cur_x, 3)
                item['z'] = row_z
                item['depth'] = row_d
                cur_x += item['width']

        # ================================================
        # POST-PASS 2: AABB EJECT — expulsar EXTERNAL si solapan INTERNAL
        # ================================================
        EXTERNAL_CODES = ('porche','terraza','piscin','pool','huerto','caseta','apero',
                          'panel','solar','bomba','tejavana','barbacoa','pozo','instalacion')
        INTERNAL_CODES = ('salon','cocina','dormitorio','bano','aseo','garaje',
                          'pasillo','distribuidor','hall','bodega','despensa','estudio')

        def _is_ext(code: str) -> bool:
            c = code.lower()
            return any(k in c for k in EXTERNAL_CODES)

        def _is_int(code: str) -> bool:
            c = code.lower()
            return any(k in c for k in INTERNAL_CODES)

        def _overlap_1d(a0, a1, b0, b1) -> float:
            """Penetración positiva en 1D; 0 si separados."""
            return max(0.0, min(a1, b1) - max(a0, b0))

        for ext_item in layout:
            if not _is_ext(ext_item['code']):
                continue
            # Solo GARDEN (caseta/tejavana/piscina) — NO exterior (porche/terraza)
            # Porche/terraza son intencionalmente adyacentes a la casa
            if ext_item.get('zone') == 'exterior':
                continue
            # Física OFF: usuario ha colocado este elemento manualmente
            if ext_item.get('is_user_placed') or ext_item.get('isEditable'):
                continue
            ex0, ex1 = ext_item['x'], ext_item['x'] + ext_item['width']
            ez0, ez1 = ext_item['z'], ext_item['z'] + ext_item['depth']
            for int_item in layout:
                if not _is_int(int_item['code']):
                    continue
                ix0, ix1 = int_item['x'], int_item['x'] + int_item['width']
                iz0, iz1 = int_item['z'], int_item['z'] + int_item['depth']
                pen_x = _overlap_1d(ex0, ex1, ix0, ix1)
                pen_z = _overlap_1d(ez0, ez1, iz0, iz1)
                if pen_x <= 0 or pen_z <= 0:
                    continue
                # Expulsar +2m en eje de menor penetración
                if pen_x <= pen_z:
                    # Empujar en X
                    if (ex0 + ex1) / 2 < (ix0 + ix1) / 2:
                        ext_item['x'] = ix0 - ext_item['width'] - 2.0
                    else:
                        ext_item['x'] = ix1 + 2.0
                else:
                    # Empujar en Z
                    if (ez0 + ez1) / 2 < (iz0 + iz1) / 2:
                        ext_item['z'] = iz0 - ext_item['depth'] - 2.0
                    else:
                        ext_item['z'] = iz1 + 2.0
                # Actualizar coordenadas locales tras eject
                ex0, ex1 = ext_item['x'], ext_item['x'] + ext_item['width']
                ez0, ez1 = ext_item['z'], ext_item['z'] + ext_item['depth']

        return layout

    def _d(self, r: R) -> Dict:
        return {
            'x': r.x, 'z': r.z,
            'width': r.w, 'depth': r.d,
            'name': r.name, 'code': r.code,
            'zone': r.zone, 'area_m2': r.area,
            'area_original': r.area,
        }


def generate_layout(rooms_data, house_shape: str = "Rectangular"):
    # Extraer solo el nombre de la forma (sin paréntesis)
    shape_clean = house_shape.split('(')[0].strip()
    return ArchitectLayout(rooms_data, shape_clean).generate()


if __name__ == '__main__':
    test = [
        {'code': 'salon',  'name': 'Salón',        'area_m2': 20},
        {'code': 'cocina', 'name': 'Cocina',        'area_m2': 12},
        {'code': 'dormitorio_principal', 'name': 'Dorm. Principal', 'area_m2': 16},
        {'code': 'dormitorio', 'name': 'Dormitorio 1', 'area_m2': 10},
        {'code': 'dormitorio', 'name': 'Dormitorio 2', 'area_m2': 10},
        {'code': 'bano',   'name': 'Baño',          'area_m2': 4},
        {'code': 'bano',   'name': 'Baño suite',    'area_m2': 5},
        {'code': 'garaje', 'name': 'Garaje',         'area_m2': 18},
        {'code': 'porche', 'name': 'Porche',         'area_m2': 10},
        {'code': 'piscina','name': 'Piscina',        'area_m2': 25},
        {'code': 'huerto', 'name': 'Huerto',         'area_m2': 30},
    ]
    layout = generate_layout(test)
    print(f"\nLayout v4.0: {len(layout)} espacios\n")
    print(f"{'Nombre':<22} {'Zona':<8} {'x':>6} {'z':>6} "
          f"{'w':>5} {'d':>5}")
    print("-" * 58)
    for i in layout:
        print(f"{i['name']:<22} {i['zone']:<8} "
              f"{i['x']:>6.1f} {i['z']:>6.1f} "
              f"{i['width']:>4.1f}m {i['depth']:>4.1f}m")
    print()
    print("ESQUEMA ESPERADO:")
    print("z pequeño = norte (jardín/piscina)")
    print("z grande  = sur   (porche/entrada)")
    print()
    print("FILA 1: Salón + Cocina + Garaje (misma z)")
    print("FILA 2: Pasillo horizontal completo")  
    print("FILA 3: Baños + Dormitorios alternados")
    print("PORCHE: Sur (z máximo de la casa)")