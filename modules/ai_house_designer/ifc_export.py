# modules/ai_house_designer/ifc_export.py
"""
Generador IFC2x3 — ArchiRapid
Puro Python (cero dependencias externas).
Convierte roomsData de Babylon.js o ai_room_proposal → gemelo digital BIM/IFC válido.
Compatible con: FreeCAD, BIMvision, Archicad, Revit, Navisworks, IfcOpenShell.
"""
import hashlib
import datetime
import math

# ── IFC GUID (128 bits → 22 chars, base-64 IFC alphabet) ──────────────────────

_IFC64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"


def _guid(seed: str) -> str:
    """Deterministic 22-char IFC GUID from seed string (2 + 21×6 = 128 bits)."""
    h = hashlib.md5(seed.encode()).digest()
    n = int.from_bytes(h, "big")
    result = []
    for _ in range(21):
        result.append(_IFC64[n & 63])
        n >>= 6
    result.append(_IFC64[n & 3])   # last 2 bits → index 0-3
    return "".join(reversed(result))


# ── Room normalizer ────────────────────────────────────────────────────────────

def _arrange_rooms(rooms_raw: list) -> list:
    """
    Accepts two input formats:
      A) Babylon saveChanges: [{name, x, z, width, depth, new_area, ...}]
      B) ai_room_proposal:    [{name, area}]  → auto grid layout
    Returns:  [{name, x, y, width, depth, area}]  in IFC XY floor coordinates.
    """
    if not rooms_raw:
        return []

    # Format A — Babylon data (has 'width' and 'x')
    if isinstance(rooms_raw[0], dict) and "width" in rooms_raw[0] and "x" in rooms_raw[0]:
        result = []
        for r in rooms_raw:
            if str(r.get("index", "")) == "custom_walls":
                continue
            w = float(r.get("width", 3.0))
            d = float(r.get("depth", 3.0))
            result.append({
                "name":  r.get("name", "Sala"),
                "x":     float(r.get("x", 0)),
                "y":     float(r.get("z", 0)),   # Babylon Z → IFC Y
                "width": w,
                "depth": d,
                "area":  float(r.get("new_area", w * d)),
            })
        return result

    # Format B — auto grid layout from name/area pairs
    result = []
    cursor_x, cursor_y = 0.0, 0.0
    max_row_depth, row_w = 0.0, 0.0

    for r in rooms_raw:
        if not isinstance(r, dict):
            continue
        name = r.get("name", "Sala")
        area = float(r.get("area", r.get("new_area", 12.0)))
        side = math.sqrt(max(area, 1))
        w = round(side * 1.2, 2)
        d = round(area / w, 2)

        if row_w > 0 and cursor_x + w > 22:  # new row after 22 m
            cursor_y += max_row_depth + 0.3
            cursor_x, max_row_depth = 0.0, 0.0

        result.append({"name": name, "x": cursor_x, "y": cursor_y,
                       "width": w, "depth": d, "area": area})
        cursor_x += w + 0.3
        row_w = cursor_x
        max_row_depth = max(max_row_depth, d)

    return result


# ── IFC2x3 generator ──────────────────────────────────────────────────────────

def generate_ifc(rooms_raw: list,
                 project_name: str = "ArchiRapid",
                 wall_height: float = 2.8) -> bytes:
    """
    Generate IFC2x3 bytes from rooms data.
    Returns UTF-8 bytes ready for st.download_button(mime='application/x-step').
    """
    rooms = _arrange_rooms(rooms_raw)
    now   = datetime.datetime.utcnow()
    ts_str = now.strftime("%Y-%m-%dT%H:%M:%S")
    ts_int = int(now.timestamp())
    pname  = project_name.replace("'", "")[:50]

    L = []   # lines list

    # ── HEADER ────────────────────────────────────────────────────────────────
    L.append("ISO-10303-21;")
    L.append("HEADER;")
    L.append("FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');")
    L.append(f"FILE_NAME('{pname}.ifc','{ts_str}',('ArchiRapid'),('ArchiRapid'),"
             f"'ArchiRapid IFC Export','ArchiRapid MVP','');")
    L.append("FILE_SCHEMA(('IFC2X3'));")
    L.append("ENDSEC;")
    L.append("DATA;")

    # ── SHARED INFRASTRUCTURE ─────────────────────────────────────────────────
    L.append("#1=IFCORGANIZATION($,'ArchiRapid',$,$,$);")
    L.append("#2=IFCPERSON($,'ArchiRapid',$,$,$,$,$,$);")
    L.append("#3=IFCPERSONANDORGANIZATION(#2,#1,$);")
    L.append("#4=IFCAPPLICATION(#1,'1.0','ArchiRapid MVP','ArchiRapid');")
    L.append(f"#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,{ts_int});")

    # Geometry context — origin, axes, context
    L.append("#6=IFCCARTESIANPOINT((0.,0.,0.));")
    L.append("#7=IFCDIRECTION((0.,0.,1.));")   # Z up
    L.append("#8=IFCDIRECTION((1.,0.,0.));")   # X right
    L.append("#9=IFCAXIS2PLACEMENT3D(#6,#7,#8);")
    L.append("#10=IFCLOCALPLACEMENT($,#9);")
    L.append("#11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#9,$);")
    L.append("#12=IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#11,$,.MODEL_VIEW.,$);")

    # Units
    L.append("#13=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);")
    L.append("#14=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);")
    L.append("#15=IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.);")
    L.append("#16=IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.);")
    L.append("#17=IFCUNITASSIGNMENT((#13,#14,#15,#16));")

    # Spatial hierarchy: Project → Site → Building → Storey
    L.append(f"#18=IFCPROJECT('{_guid('proj'+pname)}',#5,'{pname}',$,$,$,$,(#11),#17);")
    L.append(f"#19=IFCSITE('{_guid('site'+pname)}',#5,'Parcela',$,$,#10,$,$,.ELEMENT.,$,$,$,$,$);")
    L.append(f"#20=IFCBUILDING('{_guid('bldg'+pname)}',#5,'Vivienda',$,$,#10,$,$,.ELEMENT.,$,$,$);")
    L.append(f"#21=IFCBUILDINGSTOREY('{_guid('stry'+pname)}',#5,'Planta Baja',$,$,#10,$,$,.ELEMENT.,0.);")

    # Aggregation relations
    L.append(f"#22=IFCRELAGGREGATES('{_guid('ra1'+pname)}',#5,'ProjectSite',$,#18,(#19));")
    L.append(f"#23=IFCRELAGGREGATES('{_guid('ra2'+pname)}',#5,'SiteBuilding',$,#19,(#20));")
    L.append(f"#24=IFCRELAGGREGATES('{_guid('ra3'+pname)}',#5,'BuildingStorey',$,#20,(#21));")

    # ── PER-ROOM ENTITIES ──────────────────────────────────────────────────────
    # Each room uses 10 consecutive IDs starting at base + i*10
    BASE = 25
    space_refs = []

    for i, room in enumerate(rooms):
        b    = BASE + i * 10
        x    = room["x"]
        y    = room["y"]
        w    = room["width"]
        d    = room["depth"]
        area = room["area"]
        name = room["name"].replace("'", "")[:50]
        rg   = _guid(f"room{i}{name}{pname}")

        # Local placement for this room (placed relative to building storey)
        L.append(f"#{b+0}=IFCCARTESIANPOINT(({x:.4f},{y:.4f},0.));")
        L.append(f"#{b+1}=IFCAXIS2PLACEMENT3D(#{b+0},#7,#8);")
        L.append(f"#{b+2}=IFCLOCALPLACEMENT(#10,#{b+1});")

        # Rectangle profile (center at w/2, d/2 in local XY = from room corner)
        L.append(f"#{b+3}=IFCCARTESIANPOINT(({w/2:.4f},{d/2:.4f}));")
        L.append(f"#{b+4}=IFCAXIS2PLACEMENT2D(#{b+3},$);")
        L.append(f"#{b+5}=IFCRECTANGLEPROFILEDEF(.AREA.,'{name}',#{b+4},{w:.4f},{d:.4f});")

        # Extruded solid (extrusion in Z = up, from local origin)
        L.append(f"#{b+6}=IFCEXTRUDEDAREASOLID(#{b+5},#9,#7,{wall_height:.4f});")

        # Shape representation + product definition shape
        L.append(f"#{b+7}=IFCSHAPEREPRESENTATION(#12,'Body','SweptSolid',(#{b+6}));")
        L.append(f"#{b+8}=IFCPRODUCTDEFINITIONSHAPE($,$,(#{b+7}));")

        # IFC Space entity (11 attrs in IFC2x3)
        L.append(f"#{b+9}=IFCSPACE('{rg}',#5,'{name}','{name}',$,"
                 f"#{b+2},#{b+8},'{name}',.ELEMENT.,.INTERNAL.,{area:.4f});")

        space_refs.append(f"#{b+9}")

    # All spaces contained in building storey
    rc_id = BASE + len(rooms) * 10
    L.append(f"#{rc_id}=IFCRELCONTAINEDINSPATIALSTRUCTURE("
             f"'{_guid('rc'+pname)}',#5,'StoreySpaces',$,"
             f"({','.join(space_refs)}),#21);")

    L.append("ENDSEC;")
    L.append("END-ISO-10303-21;")

    return "\n".join(L).encode("utf-8")


# ── SVG 2D floor plan ──────────────────────────────────────────────────────────

_ROOM_COLORS = {
    "cocina": "#FFF3CD", "salon": "#D4EDDA", "dormitorio": "#D1ECF1",
    "bano": "#F8D7DA", "garaje": "#E2E3E5", "piscina": "#CCE5FF",
    "distribuidor": "#FFFFFF", "porche": "#FFEEBA", "terraza": "#FFEEBA",
    "default": "#F0F4F8",
}


def _room_color(name: str) -> str:
    nl = name.lower()
    for k, v in _ROOM_COLORS.items():
        if k in nl:
            return v
    return _ROOM_COLORS["default"]


def rooms_to_svg(rooms_raw: list, px: int = 540) -> str:
    """
    Generate crisp SVG 2D floor plan from rooms data.
    Returns SVG string — safe for st.markdown(unsafe_allow_html=True).
    """
    rooms = _arrange_rooms(rooms_raw)
    if not rooms:
        return ""

    # Bounding box
    xs = [r["x"] for r in rooms] + [r["x"] + r["width"] for r in rooms]
    ys = [r["y"] for r in rooms] + [r["y"] + r["depth"] for r in rooms]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    margin = 28
    scale  = (px - 2 * margin) / max(span_x, span_y)
    height = int(span_y * scale) + 2 * margin

    def tx(x): return margin + (x - min_x) * scale
    def ty(y): return margin + (y - min_y) * scale

    rects, labels = [], []
    for r in rooms:
        rx = tx(r["x"])
        ry = ty(r["y"])
        rw = r["width"]  * scale
        rd = r["depth"]  * scale
        cx = rx + rw / 2
        cy = ry + rd / 2
        fs = max(8, min(11, int(rw / 5.5)))

        rects.append(
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rd:.1f}" '
            f'fill="{_room_color(r["name"])}" stroke="#2C3E50" stroke-width="1.5" rx="2"/>'
        )
        name_short = r["name"].replace("_", " ")[:14]
        labels.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="system-ui,sans-serif" font-size="{fs}" fill="#1a1a2e" font-weight="600">'
            f'{name_short}</text>'
        )
        labels.append(
            f'<text x="{cx:.1f}" y="{cy + fs + 3:.1f}" text-anchor="middle" '
            f'font-family="system-ui,sans-serif" font-size="{max(7, fs-2)}" fill="#555">'
            f'{r["area"]:.1f}m²</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{height}" '
        f'style="background:#FAFAFA;border-radius:10px;border:1px solid #CBD5E1;display:block;">'
        f'{"".join(rects)}{"".join(labels)}'
        f'</svg>'
    )
