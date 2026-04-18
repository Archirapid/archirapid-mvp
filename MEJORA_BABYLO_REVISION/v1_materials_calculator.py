"""
Calculadora de PEM (Presupuesto de Ejecución Material) por materiales.
Cruza el layout de Babylon (width*depth por room) con prices en materials_db.json.
NO modifica total_cost existente — genera detailed_pem_breakdown como capa paralela.
"""
from __future__ import annotations
import json
import os
from typing import List, Dict, Any

_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'materials_db.json')


def _load_db() -> Dict[str, Any]:
    try:
        with open(_DB_PATH, encoding='utf-8') as f:
            return {m['id']: m for m in json.load(f)['materials']}
    except Exception:
        return {}


def calculate_pem_breakdown(babylon_layout: List[Dict]) -> Dict[str, Any]:
    """
    Itera sobre los rooms de Babylon, recupera area real (width*depth),
    cruza con materials_db y devuelve detailed_pem_breakdown.

    Args:
        babylon_layout: lista de dicts {name, code, zone, x, z, width, depth,
                                         area_m2, material_id (opcional)}
    Returns:
        {
          "by_material": {material_id: {name, total_m2, price_m2, subtotal_eur}},
          "by_room":     [{room_name, material_name, area_m2, subtotal_eur}],
          "total_pem":   float,
          "rooms_without_material": [name, ...]
        }
    """
    db = _load_db()
    by_material: Dict[str, Dict] = {}
    by_room: List[Dict] = []
    without_material: List[str] = []

    for room in babylon_layout:
        width = float(room.get('width') or 0)
        depth = float(room.get('depth') or 0)
        area  = round(width * depth, 2)
        mat_id = room.get('material_id') or ''
        mat    = db.get(mat_id)
        name   = room.get('name', 'Habitación')

        if not mat or area <= 0:
            if area > 0:
                without_material.append(name)
            continue

        subtotal = round(area * mat['price_m2'], 2)

        if mat_id not in by_material:
            by_material[mat_id] = {
                'name':        mat['name'],
                'price_m2':    mat['price_m2'],
                'total_m2':    0.0,
                'subtotal_eur': 0.0,
                'normativa':   mat.get('normativa_cte_ref', ''),
            }
        by_material[mat_id]['total_m2']     = round(by_material[mat_id]['total_m2'] + area, 2)
        by_material[mat_id]['subtotal_eur'] = round(by_material[mat_id]['subtotal_eur'] + subtotal, 2)

        by_room.append({
            'room_name':     name,
            'zone':          room.get('zone', ''),
            'material_id':   mat_id,
            'material_name': mat['name'],
            'area_m2':       area,
            'price_m2':      mat['price_m2'],
            'subtotal_eur':  subtotal,
        })

    total_pem = round(sum(v['subtotal_eur'] for v in by_material.values()), 2)

    return {
        'by_material': by_material,
        'by_room':     by_room,
        'total_pem':   total_pem,
        'rooms_without_material': without_material,
    }
