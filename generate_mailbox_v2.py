"""
Parametrische Briefkasten-Generierung als IFC:
- Außenprofil mit 4 Bögen (12 Punkte) skalierbar über width/height
- Extrusionstiefe (depth) für den Rahmen
- Feste Öffnungen (Keine Werbung, Beschriftung, Einwurfklappe) mit Einlagen
- Raster-Kopien in global X/Z über rows/columns
- Zwei Furnishing-Elemente: Bierkasten (mit Rahmen + Platten) und Bierkasten_RahmenKopie (nur Rahmen)
"""

import tempfile
from pathlib import Path
from typing import Optional

import ifcopenshell

# Basis-Profil: 12 Punkte mit 4 Bögen , in Metern
BASE_OUTER_POINTS = [
    (0.0, 0.3110),
    (0.0, 0.0005),
    (0.0, 0.0),       # arc start 1
    (0.0005, 0.0),
    (0.4085, 0.0),
    (0.4090, 0.0),    # arc start 2
    (0.4090, 0.0005),
    (0.4090, 0.3110),
    (0.4090, 0.3115), # arc start 3
    (0.4085, 0.3115),
    (0.0005, 0.3115),
    (0.0, 0.3115),    # arc start 4
]
ARC_INDICES = [2, 5, 8, 11]  # 1-based middle points for IfcArcIndex
BASE_WIDTH = max(p[0] for p in BASE_OUTER_POINTS) - min(p[0] for p in BASE_OUTER_POINTS)  # 0.409
BASE_HEIGHT = max(p[1] for p in BASE_OUTER_POINTS) - min(p[1] for p in BASE_OUTER_POINTS)  # 0.3115

HOLES = [
    {
        "name": "Schild Keine Werbung",
        "points": [(0.017, 0.1809), (0.017, 0.1957), (0.0973, 0.1957), (0.0973, 0.1809)],
    },
    {
        "name": "Schild Beschriftung",
        "points": [(0.017, 0.2057), (0.017, 0.231), (0.0973, 0.231), (0.0973, 0.2057)],
    },
    {
        "name": "Einwurfklappe",
        "points": [(0.017, 0.261), (0.017, 0.2915), (0.373, 0.2915), (0.373, 0.261)],
    },
]

GAP = 0.003  # 3 mm Abstand zwischen Briefkästen
PLATE_THICKNESS = 0.002  # 2 mm Plattenstärke
FRAME_OUTER_OFFSET = 0.018  # 18 mm nach außen
FRAME_INNER_OFFSET = 0.003  # 3 mm nach außen
FRAME_DEPTH_DEFAULT = 0.35  # 35 cm Extrusion

# Hersteller-Informationen (Standardwerte)
MANUFACTURER_INFO = {
    "Manufacturer": "Briefkasten Profi GmbH",
    "ArticleNumber": "BK-ALU-005",
    "ModelLabel": "Premium Alu Plate",
    "ProductionYear": 2025
}

# Farb-Mapping für Property-Sets (Hex -> Name)
RAL_COLORS_MAP = {
    "#C0C0C0": "Farblos eloxiert",
    "#000000": "RAL 9011 - Graphitschwarz",
    "#F7FBF5": "RAL 9016 - Verkehrsweiss",
    "#383E42": "RAL 7016 - Anthrazitgrau",
    "#7A7B7A": "RAL 7037 - Staubgrau",
    "#005387": "RAL 5005 - Signalblau",
    "#A72920": "RAL 3000 - Feuerrot",
    "#E2B007": "RAL 1004 - Goldgelb",
    "#4D6F39": "RAL 6010 - Grasgrün",
}

# ------------------ Geometrie-Helfer ------------------

def _listf(vals):
    return [float(x) for x in vals]


def create_direction(f, xyz):
    return f.create_entity("IfcDirection", _listf(xyz))


def create_point(f, xyz):
    return f.create_entity("IfcCartesianPoint", _listf(xyz))


def axis2placement2d(f, origin=(0.0, 0.0), xdir=(1.0, 0.0)):
    p = create_point(f, origin)
    d = create_direction(f, xdir)
    return f.create_entity("IfcAxis2Placement2D", p, d)


def axis2placement3d(f, origin=(0.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0), xdir=(1.0, 0.0, 0.0)):
    p = create_point(f, origin)
    z = create_direction(f, zdir)
    x = create_direction(f, xdir)
    return f.create_entity("IfcAxis2Placement3D", p, z, x)


def create_indexed_polycurve(f, points, arc_points=None, closed=True):
    if arc_points is None:
        arc_points = []
    plist = f.create_entity("IfcCartesianPointList2D", CoordList=[_listf(p) for p in points])
    segments = []
    n = len(points)
    for i in range(n if closed else n - 1):
        start = i + 1
        nxt = (i + 1) % n + 1
        mid = (i + 2) % n + 1
        if (i + 1) in arc_points:
            segments.append(f.create_entity("IfcArcIndex", [start, nxt, mid]))
        else:
            segments.append(f.create_entity("IfcLineIndex", [start, nxt]))
    return f.create_entity("IfcIndexedPolyCurve", plist, Segments=segments)


def scale_profile(points, sx, sy):
    return [(p[0] * sx, p[1] * sy) for p in points]


def bounding_rectangle(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def inset_rectangle(points, offset):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    return [
        (xmin + offset, ymin + offset),
        (xmin + offset, ymax - offset),
        (xmax - offset, ymax - offset),
        (xmax - offset, ymin + offset),
    ]


# ------------------ Styling & Properties Helfer ------------------

def hex_to_rgb(hex_str):
    """Wandelt Hex-String (z.B. '#4D6F39') in RGB-Tupel (0.0-1.0) um."""
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def get_color_name(hex_str):
    """Gibt den Farbnamen zurück oder den Hex-Code, falls nicht gefunden."""
    # Normalisierung für Lookup (Großschreibung)
    return RAL_COLORS_MAP.get(hex_str.upper(), hex_str)

def create_surface_style(f, name, rgb):
    """Erstellt einen IfcSurfaceStyle für Rendering."""
    colour_rgb = f.create_entity("IfcColourRgb", None, *rgb)
    # Einfaches Rendering ohne Texturen
    surface_style_rendering = f.create_entity(
        "IfcSurfaceStyleRendering",
        SurfaceColour=colour_rgb,
        Transparency=0.0,
        ReflectanceMethod="NOTDEFINED"
    )
    return f.create_entity(
        "IfcSurfaceStyle",
        Name=name,
        Side="BOTH",
        Styles=[surface_style_rendering]
    )

def assign_style_to_shape(f, shape_rep, style):
    """Weist den Style dem ersten Item der ShapeRepresentation zu."""
    if shape_rep and shape_rep.Items:
        item = shape_rep.Items[0]
        f.create_entity("IfcStyledItem", Item=item, Styles=[style], Name="StyleAssignment")

def add_property_set(f, product, pset_name, properties_dict):
    """Fügt einem Produkt ein PropertySet hinzu."""
    props = []
    for k, v in properties_dict.items():
        val = f.create_entity("IfcLabel", str(v))
        props.append(f.create_entity("IfcPropertySingleValue", Name=k, NominalValue=val))
    
    pset = f.create_entity("IfcPropertySet", ifcopenshell.guid.new(), None, pset_name, None, props)
    f.create_entity("IfcRelDefinesByProperties", ifcopenshell.guid.new(), None, None, None, [product], pset)


# ------------------ IFC-Struktur ------------------

def create_project_hierarchy():
    f = ifcopenshell.file(schema="IFC4")
    project = f.create_entity("IfcProject", ifcopenshell.guid.new(), None, "Mailbox Project")
    si_length = f.create_entity("IfcSIUnit", None, "LENGTHUNIT", None, "METRE")
    units = f.create_entity("IfcUnitAssignment", [si_length])
    project.UnitsInContext = units

    wcs = axis2placement3d(f, (0, 0, 0))
    model_ctx = f.create_entity("IfcGeometricRepresentationContext", None, "Model", 3, 1e-5, wcs, None)
    body_ctx = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=model_ctx,
        TargetScale=None,
        TargetView="MODEL_VIEW",
        UserDefinedTargetView=None,
    )

    site_lp = f.create_entity("IfcLocalPlacement", None, axis2placement3d(f))
    site = f.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Default Site",
        ObjectPlacement=site_lp,
        CompositionType="ELEMENT",
    )

    bldg_lp = f.create_entity("IfcLocalPlacement", site_lp, axis2placement3d(f))
    building = f.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Building",
        ObjectPlacement=bldg_lp,
        CompositionType="ELEMENT",
    )

    storey_lp = f.create_entity("IfcLocalPlacement", bldg_lp, axis2placement3d(f))
    storey = f.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="Groundfloor",
        ObjectPlacement=storey_lp,
        Elevation=0.0,
        CompositionType="ELEMENT",
    )

    f.create_entity("IfcRelAggregates", ifcopenshell.guid.new(), None, None, None, project, [site])
    f.create_entity("IfcRelAggregates", ifcopenshell.guid.new(), None, None, None, site, [building])
    f.create_entity("IfcRelAggregates", ifcopenshell.guid.new(), None, None, None, building, [storey])

    return f, body_ctx, storey


# ------------------ Produkt-Erzeugung ------------------

def create_extruded_shape(f, body_ctx, outer_points, inner_curves, thickness, arc_indices=None):
    """Erstellt nur die geometrische Repräsentation (IfcShapeRepresentation)."""
    if arc_indices is None:
        arc_indices = []
        
    outer_curve = create_indexed_polycurve(f, outer_points, arc_indices, closed=True)
    if inner_curves:
        profile = f.create_entity(
            "IfcArbitraryProfileDefWithVoids",
            ProfileType="AREA",
            ProfileName=None,
            OuterCurve=outer_curve,
            InnerCurves=inner_curves,
        )
    else:
        profile = f.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            ProfileName=None,
            OuterCurve=outer_curve,
        )

    solid = f.create_entity(
        "IfcExtrudedAreaSolid",
        profile,
        axis2placement3d(f, zdir=(0.0, 1.0, 0.0), xdir=(1.0, 0.0, 0.0)),
        create_direction(f, (0.0, 0.0, -1.0)),
        float(thickness),
    )

    return f.create_entity("IfcShapeRepresentation", body_ctx, "Body", "SweptSolid", [solid])


def create_plate(
    f,
    body_ctx,
    name,
    outer_points,
    inner_curves,
    thickness,
    placement_rel_to,
    spatial_container=None,
    aggregate_parent=None,
    representation=None,  # Neu: Optionale fertige Geometrie
    arc_indices=None,     # Neu: Spezifische Bogen-Indizes
):
    if representation:
        shape_rep = representation
    else:
        # Fallback: Geometrie neu erstellen (Standardverhalten mit globalen ARC_INDICES wenn nichts übergeben)
        use_arcs = arc_indices if arc_indices is not None else ARC_INDICES
        shape_rep = create_extruded_shape(f, body_ctx, outer_points, inner_curves, thickness, use_arcs)

    prod_shape = f.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])

    loc = f.create_entity(
        "IfcLocalPlacement",
        placement_rel_to,
        axis2placement3d(f, (0.0, 0.0, 0.0), zdir=(0.0, 0.0, -1.0), xdir=(-1.0, 0.0, 0.0)),
    )

    plate = f.create_entity(
        "IfcPlate",
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        ObjectPlacement=loc,
        Representation=prod_shape,
    )

    if spatial_container:
        f.create_entity(
            "IfcRelContainedInSpatialStructure",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            [plate],
            spatial_container,
        )
    if aggregate_parent:
        f.create_entity(
            "IfcRelAggregates",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            aggregate_parent,
            [plate],
        )

    return plate


def create_frame(
    f,
    body_ctx,
    name,
    outer_points,
    inner_points,
    depth,
    placement_rel_to,
    spatial_container=None,
    aggregate_parent=None,
):
    outer_curve = create_indexed_polycurve(f, outer_points, arc_points=[], closed=True)
    inner_curve = create_indexed_polycurve(f, inner_points, arc_points=[], closed=True)
    profile = f.create_entity(
        "IfcArbitraryProfileDefWithVoids",
        ProfileType="AREA",
        ProfileName=None,
        OuterCurve=outer_curve,
        InnerCurves=[inner_curve],
    )
    solid = f.create_entity(
        "IfcExtrudedAreaSolid",
        profile,
        axis2placement3d(f, zdir=(0.0, 1.0, 0.0), xdir=(1.0, 0.0, 0.0)),
        create_direction(f, (0.0, 0.0, -1.0)),
        float(depth),
    )
    shape_rep = f.create_entity("IfcShapeRepresentation", body_ctx, "Body", "SweptSolid", [solid])
    prod_shape = f.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])

    loc = f.create_entity(
        "IfcLocalPlacement",
        placement_rel_to,
        axis2placement3d(f, (0.0, 0.0, 0.0), zdir=(0.0, 0.0, -1.0), xdir=(-1.0, 0.0, 0.0)),
    )

    frame = f.create_entity(
        "IfcPlate",
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        ObjectPlacement=loc,
        Representation=prod_shape,
    )

    if spatial_container:
        f.create_entity(
            "IfcRelContainedInSpatialStructure",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            [frame],
            spatial_container,
        )
    if aggregate_parent:
        f.create_entity(
            "IfcRelAggregates",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            aggregate_parent,
            [frame],
        )

    return frame


# ------------------ Hauptgenerator ------------------

def generate_mailbox_ifc(
    width: float = BASE_WIDTH,
    height: float = BASE_HEIGHT,
    depth: float = FRAME_DEPTH_DEFAULT,
    rows: int = 1,
    columns: int = 1,
    output_path: Optional[Path] = None,
    color: str = "#C72727",  # Default: Farblos eloxiert / Grau
) -> Optional[Path]:
    rows = max(1, min(rows, 5))
    columns = max(1, min(columns, 3))

    try:
        f, body_ctx, storey = create_project_hierarchy()

        # Haupt-Furnishing "Bierkasten"
        bierkasten_lp = f.create_entity("IfcLocalPlacement", storey.ObjectPlacement, axis2placement3d(f))
        bierkasten = f.create_entity(
            "IfcFurnishingElement",
            GlobalId=ifcopenshell.guid.new(),
            Name="Bierkasten",
            ObjectPlacement=bierkasten_lp,
        )
        f.create_entity(
            "IfcRelContainedInSpatialStructure",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            [bierkasten],
            storey,
        )

        # Zweites Furnishing nur für den Rahmen
        bierkasten_frame_lp = f.create_entity("IfcLocalPlacement", storey.ObjectPlacement, axis2placement3d(f))
        bierkasten_frame = f.create_entity(
            "IfcFurnishingElement",
            GlobalId=ifcopenshell.guid.new(),
            Name="Bierkasten_RahmenKopie",
            ObjectPlacement=bierkasten_frame_lp,
        )
        f.create_entity(
            "IfcRelContainedInSpatialStructure",
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            [bierkasten_frame],
            storey,
        )

        # --- Styling vorbereiten ---
        rgb_color = hex_to_rgb(color)
        main_style = create_surface_style(f, f"Style_{color}", rgb_color)

        # --- Property Set Daten vorbereiten ---
        color_name = get_color_name(color)
        pset_data = MANUFACTURER_INFO.copy()
        pset_data["Color"] = color_name

        # Skalierungsfaktoren für ein einzelnes Profil
        sx_single = width / BASE_WIDTH
        sy_single = height / BASE_HEIGHT
        scaled_outer_single = scale_profile(BASE_OUTER_POINTS, sx_single, sy_single)

        # Frame über das gesamte Raster
        total_width = rows * width + (rows - 1) * GAP
        total_height = columns * height + (columns - 1) * GAP
        sx_total = total_width / BASE_WIDTH
        sy_total = total_height / BASE_HEIGHT
        frame_outer = scale_profile(BASE_OUTER_POINTS, sx_total, sy_total)
        xmin, xmax, ymin, ymax = bounding_rectangle(frame_outer)
        frame_outer = [
            (xmin - FRAME_OUTER_OFFSET, ymin - FRAME_OUTER_OFFSET),
            (xmin - FRAME_OUTER_OFFSET, ymax + FRAME_OUTER_OFFSET),
            (xmax + FRAME_OUTER_OFFSET, ymax + FRAME_OUTER_OFFSET),
            (xmax + FRAME_OUTER_OFFSET, ymin - FRAME_OUTER_OFFSET),
        ]
        frame_inner = [
            (xmin - FRAME_INNER_OFFSET, ymin - FRAME_INNER_OFFSET),
            (xmin - FRAME_INNER_OFFSET, ymax + FRAME_INNER_OFFSET),
            (xmax + FRAME_INNER_OFFSET, ymax + FRAME_INNER_OFFSET),
            (xmax + FRAME_INNER_OFFSET, ymin - FRAME_INNER_OFFSET),
        ]

        # Rahmen erzeugen (nur im zweiten Furnishing, nicht mehr doppelt)
        frame_element = create_frame(
            f,
            body_ctx,
            "Briefkastenrahmen",
            frame_outer,
            frame_inner,
            depth,
            bierkasten_frame_lp,
            aggregate_parent=bierkasten_frame,
        )
        
        # Style und Pset auf Rahmen anwenden
        assign_style_to_shape(f, frame_element.Representation.Representations[0], main_style)
        add_property_set(f, frame_element, "Pset_ManufacturerTypeInformation", pset_data)

        # --- VORBEREITUNG: Geometrien einmalig erstellen (Performance & Dateigröße) ---
        
        # 1. Deckblatt-Geometrie
        hole_curves = []
        for h in HOLES:
            hole_curves.append(
                create_indexed_polycurve(
                    f,
                    h["points"],
                    arc_points=[],
                    closed=True,
                )
            )
        
        shape_deckblatt = create_extruded_shape(
            f, body_ctx, scaled_outer_single, hole_curves, PLATE_THICKNESS, arc_indices=ARC_INDICES
        )
        # Deckblatt bekommt die Farbe
        assign_style_to_shape(f, shape_deckblatt, main_style)

        # 2. Einlagen-Geometrien
        # Wir speichern die Shapes in einem Dictionary für späteren Zugriff
        shapes_inserts = {}
        inset_offset = 0.001
        insert_names = {
            1: "Schild Keine Werbung",
            2: "Schild Beschriftung",
            3: "Einwurfklappe",
        }
        
        for idx, hole in enumerate(HOLES, start=1):
            shrunk_hole = inset_rectangle(hole["points"], inset_offset)
            # Wichtig: arc_indices=[] übergeben, da Einlagen rechteckig sind (keine Bögen)
            shape = create_extruded_shape(f, body_ctx, shrunk_hole, [], PLATE_THICKNESS, arc_indices=[])
            shapes_inserts[idx] = shape
            
            if idx == 3: # Einwurfklappe bekommt auch die Farbe
                assign_style_to_shape(f, shape, main_style)

        # Raster an Platten (Deckblatt + Einlagen) erzeugen
        for r in range(rows):
            for c in range(columns):
                offset_x = -(r * (width + GAP))
                offset_z = c * (height + GAP)
                cell_lp = f.create_entity(
                    "IfcLocalPlacement",
                    bierkasten_lp,
                    axis2placement3d(f, (offset_x, 0.0, offset_z)),
                )

                # Deckblatt platzieren (Wiederverwendung der Geometrie)
                plate_deck = create_plate(
                    f,
                    body_ctx,
                    "Deckblatt Briefkasten",
                    None, None, None, # Keine Geometrie-Daten nötig
                    cell_lp,
                    aggregate_parent=bierkasten,
                    representation=shape_deckblatt # Hier übergeben wir die fertige Form
                )
                add_property_set(f, plate_deck, "Pset_ManufacturerTypeInformation", pset_data)

                # Einlagen platzieren
                for idx, hole in enumerate(HOLES, start=1):
                    plate_insert = create_plate(
                        f,
                        body_ctx,
                        insert_names.get(idx, hole["name"]),
                        None, None, None,
                        cell_lp,
                        aggregate_parent=bierkasten,
                        representation=shapes_inserts[idx] # Wiederverwendung
                    )
                    add_property_set(f, plate_insert, "Pset_ManufacturerTypeInformation", pset_data)

        # Datei schreiben
        if output_path is None:
            out_path = Path(tempfile.gettempdir()) / f"{ifcopenshell.guid.new()}.ifc"
        else:
            out_path = Path(output_path)
        f.write(str(out_path))
        return out_path

    except Exception as e:
        print(f"Fehler bei der IFC-Generierung: {e}")
        return None


if __name__ == "__main__":
    # 1x1
    out1 = generate_mailbox_ifc(color="#4D6F39", output_path=Path("test_generate_mailbox_1x1.ifc"))
    if out1:
        print(f"IFC erstellt: {out1}")
    # 3x5 (max rows/cols), entspricht Name 5x3 in der Benennung
    # Test mit Farbe Grasgrün (#4D6F39)
    out2 = generate_mailbox_ifc(rows=5, columns=3, color="#4D6F39", output_path=Path("test_generate_mailbox_5x3.ifc"))
    if out2:
        print(f"IFC erstellt: {out2}")
