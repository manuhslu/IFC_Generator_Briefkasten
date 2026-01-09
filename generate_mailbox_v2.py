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
import ifcopenshell.guid

# Basis-Profil: 4 Punkte (Rechteck), keine Bögen mehr
BASE_OUTER_POINTS = [
    (0.0, 0.0),
    (0.4090, 0.0),
    (0.4090, 0.3115),
    (0.0, 0.3115),
]
ARC_INDICES = []  # Keine Bögen mehr
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

def create_curve_style(f, name, rgb):
    """Erstellt einen IfcCurveStyle für Linien/Kanten."""
    colour_rgb = f.create_entity("IfcColourRgb", None, *rgb)
    return f.create_entity("IfcCurveStyle", Name=name, CurveColour=colour_rgb)

def assign_style_to_shape(f, shape_rep, style):
    """Weist den Style allen Items der ShapeRepresentation zu."""
    if shape_rep and shape_rep.Items:
        for item in shape_rep.Items:
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


def create_representation_map(f, representation):
    """Erstellt eine IfcRepresentationMap für eine gegebene Representation."""
    origin = axis2placement3d(f)
    return f.create_entity("IfcRepresentationMap", MappingOrigin=origin, MappedRepresentation=representation)


def create_mapped_item_shape(f, body_ctx, rep_maps):
    """Erstellt ein ProductDefinitionShape, das ein IfcMappedItem enthält."""
    # Falls nur eine Map übergeben wurde, in Liste packen
    if not isinstance(rep_maps, list):
        rep_maps = [rep_maps]
    
    reps = []
    for rm in rep_maps:
        op_origin = create_point(f, (0.0, 0.0, 0.0))
        operator = f.create_entity("IfcCartesianTransformationOperator3D", LocalOrigin=op_origin)
        mapped_item = f.create_entity("IfcMappedItem", MappingSource=rm, MappingTarget=operator)
        
        # Jedes MappedItem bekommt eine eigene ShapeRepresentation
        shape_rep = f.create_entity("IfcShapeRepresentation", ContextOfItems=body_ctx, RepresentationIdentifier="Body", RepresentationType="MappedRepresentation", Items=[mapped_item])
        reps.append(shape_rep)
    
    return f.create_entity("IfcProductDefinitionShape", Representations=reps)


def create_3d_wireframe(f, body_ctx, outer_points, thickness, inner_points_list=None):
    """Erstellt eine Drahtgitter-Repräsentation (Kanten) für Extrusionen."""
    items = []
    
    # Mapping: Profile(x,y) -> Object(x, -z), Extrusion -> Object(-y)
    # Dies entspricht der Rotation im IfcExtrudedAreaSolid (Z=(0,1,0), X=(1,0,0))
    def map_point(p, y):
        return _listf((p[0], y, -p[1]))

    def make_loop(points, y):
        pts_3d = [f.create_entity("IfcCartesianPoint", map_point(p, y)) for p in points]
        pts_3d.append(pts_3d[0]) # Loop schließen
        return f.create_entity("IfcPolyline", Points=pts_3d)

    def make_verticals(points, y_start, y_end):
        lines = []
        for p in points:
            p1 = f.create_entity("IfcCartesianPoint", map_point(p, y_start))
            p2 = f.create_entity("IfcCartesianPoint", map_point(p, y_end))
            lines.append(f.create_entity("IfcPolyline", Points=[p1, p2]))
        return lines

    # Extrusion geht in negative Y-Richtung (im Objekt-System)
    y_front = 0.0
    y_back = -float(thickness)

    # Außenkontur
    items.append(make_loop(outer_points, y_front))
    items.append(make_loop(outer_points, y_back))
    items.extend(make_verticals(outer_points, y_front, y_back))

    # Innenkonturen (Löcher)
    if inner_points_list:
        for ip in inner_points_list:
            items.append(make_loop(ip, y_front))
            items.append(make_loop(ip, y_back))
            items.extend(make_verticals(ip, y_front, y_back))

    return f.create_entity("IfcShapeRepresentation", body_ctx, "Body", "GeometricCurveSet", Items=items)


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
    representation=None,
    product_def_shape=None, # Neu: Für Instancing
    representation_maps=None, # Neu: Liste von Maps (Solid + Wireframe)
    arc_indices=None,
    pos_offset=(0.0, 0.0, 0.0) # Neu: Offset zur Vermeidung von Z-Fighting
):
    # Geometrie-Handling: Entweder existierende Shape nutzen (Instancing) oder neu erstellen
    if representation_maps:
        prod_shape = create_mapped_item_shape(f, body_ctx, representation_maps)
    elif product_def_shape:
        prod_shape = product_def_shape
    elif representation:
        prod_shape = f.create_entity("IfcProductDefinitionShape", Representations=[representation])
    else:
        # Fallback: Geometrie neu erstellen
        use_arcs = arc_indices if arc_indices is not None else ARC_INDICES
        shape_rep = create_extruded_shape(f, body_ctx, outer_points, inner_curves, thickness, use_arcs)
        
        # Wireframe dazu generieren (wenn Punkte vorhanden)
        wireframe_rep = create_3d_wireframe(f, body_ctx, outer_points, thickness, []) # Keine inner_points hier verfügbar/geparst
        prod_shape = f.create_entity("IfcProductDefinitionShape", Representations=[shape_rep, wireframe_rep])

    # Placement mit Offset
    loc = f.create_entity(
        "IfcLocalPlacement",
        placement_rel_to,
        axis2placement3d(f, pos_offset, zdir=(0.0, 0.0, -1.0), xdir=(-1.0, 0.0, 0.0)),
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
    
    # Wireframe hinzufügen
    wireframe_rep = create_3d_wireframe(f, body_ctx, outer_points, depth, [inner_points])
    prod_shape = f.create_entity("IfcProductDefinitionShape", None, None, [shape_rep, wireframe_rep])

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
    edge_color: str = "#000000", # Default: Schwarz
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

        # Stil für Kanten: Dynamisch aus Parameter
        edge_rgb = hex_to_rgb(edge_color)
        edge_style = create_curve_style(f, "Style_Edges", edge_rgb)

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
        if len(frame_element.Representation.Representations) > 1:
            assign_style_to_shape(f, frame_element.Representation.Representations[1], edge_style)
        add_property_set(f, frame_element, "Pset_ManufacturerTypeInformation", pset_data)

        # --- Rückwand erzeugen ---
        # 2mm Blech, 1mm kleiner als innerer Rahmen, Position bei depth - 0.01m
        back_panel_points = inset_rectangle(frame_inner, 0.001)
        back_panel_pos = (0.0, -depth + 0.01, 0.0)
        
        back_panel = create_plate(
            f,
            body_ctx,
            "Rueckwand",
            back_panel_points,
            [], # Keine Löcher
            0.002, # 2mm Dicke
            bierkasten_frame_lp,
            aggregate_parent=bierkasten_frame,
            pos_offset=back_panel_pos
        )
        # create_plate erstellt jetzt automatisch Wireframe, wenn keine Map übergeben wird
        assign_style_to_shape(f, back_panel.Representation.Representations[0], main_style)
        if len(back_panel.Representation.Representations) > 1:
            assign_style_to_shape(f, back_panel.Representation.Representations[1], edge_style)
        add_property_set(f, back_panel, "Pset_ManufacturerTypeInformation", pset_data)

        # --- VORBEREITUNG: Geometrien einmalig erstellen (Instancing) ---
        
        # Anpassung der Löcher/Einlagen an die neue Höhe (Abstand von oben fixieren)
        dy = height - BASE_HEIGHT
        adjusted_holes = []
        for h in HOLES:
            if h["name"] == "Einwurfklappe":
                xs = [p[0] for p in h["points"]]
                min_x = min(xs)
                new_points = []
                for p in h["points"]:
                    # Startpunkt (links) bleibt fix, Endpunkt (rechts) wandert mit der Breite
                    if abs(p[0] - min_x) < 1e-5:
                        nx = p[0]
                    else:
                        nx = width - (BASE_WIDTH - p[0])
                    new_points.append((nx, p[1] + dy))
            else:
                # Andere Einlagen bleiben in der Breite/Position fix
                new_points = [(p[0], p[1] + dy) for p in h["points"]]
            adjusted_holes.append({"name": h["name"], "points": new_points})

        # 1. Deckblatt-Geometrie (Shared ProductDefinitionShape)
        hole_curves = []
        for h in adjusted_holes:
            hole_curves.append(
                create_indexed_polycurve(
                    f,
                    h["points"],
                    arc_points=[],
                    closed=True,
                )
            )
        
        shape_deckblatt_rep = create_extruded_shape(
            f, body_ctx, scaled_outer_single, hole_curves, PLATE_THICKNESS, arc_indices=ARC_INDICES
        )
        assign_style_to_shape(f, shape_deckblatt_rep, main_style)
        
        # Wireframe für Deckblatt erstellen (inkl. Löcher)
        deck_holes_points = [h["points"] for h in adjusted_holes]
        shape_deckblatt_wireframe = create_3d_wireframe(f, body_ctx, scaled_outer_single, PLATE_THICKNESS, deck_holes_points)
        assign_style_to_shape(f, shape_deckblatt_wireframe, edge_style)
        
        # Maps erstellen (Solid und Wireframe separat)
        deck_map = create_representation_map(f, shape_deckblatt_rep)
        deck_wireframe_map = create_representation_map(f, shape_deckblatt_wireframe)

        # 2. Einlagen-Geometrien (Maps)
        insert_maps = {}
        inset_offset = 0.001
        insert_names = {
            1: "Schild Keine Werbung",
            2: "Schild Beschriftung",
            3: "Einwurfklappe",
        }
        
        for idx, hole in enumerate(adjusted_holes, start=1):
            shrunk_hole = inset_rectangle(hole["points"], inset_offset)
            # Wichtig: arc_indices=[] übergeben, da Einlagen rechteckig sind
            shape_rep = create_extruded_shape(f, body_ctx, shrunk_hole, [], PLATE_THICKNESS, arc_indices=[])
            
            # Wireframe für Einlage
            shape_wireframe = create_3d_wireframe(f, body_ctx, shrunk_hole, PLATE_THICKNESS)
            assign_style_to_shape(f, shape_wireframe, edge_style)
            
            if idx == 3: # Einwurfklappe bekommt auch die Farbe
                assign_style_to_shape(f, shape_rep, main_style)
            
            # Maps speichern (Liste: [Solid, Wireframe])
            insert_maps[idx] = [create_representation_map(f, shape_rep), create_representation_map(f, shape_wireframe)]

        # Raster an Platten (Deckblatt + Einlagen) erzeugen
        for r in range(rows):
            for c in range(columns):
                offset_x = -(r * (width + GAP))
                offset_z = c * (height + GAP)

                # Deckblatt platzieren (Direkt an Bierkasten, flache Hierarchie für besseren Export)
                deck_pos = (offset_x, 0.0, offset_z)
                plate_deck = create_plate(
                    f,
                    body_ctx,
                    "Deckblatt Briefkasten",
                    None, None, None, # Keine Geometrie-Daten nötig
                    bierkasten_lp,
                    aggregate_parent=bierkasten,
                    representation_maps=[deck_map, deck_wireframe_map], # MappedItem Instancing (Solid + Wireframe)
                    pos_offset=deck_pos
                )
                add_property_set(f, plate_deck, "Pset_ManufacturerTypeInformation", pset_data)
                # WICHTIG: Stil auch auf die Instanz (MappedItem) des Wireframes anwenden
                if len(plate_deck.Representation.Representations) > 1:
                    assign_style_to_shape(f, plate_deck.Representation.Representations[1], edge_style)

                # Einlagen platzieren
                for idx, hole in enumerate(adjusted_holes, start=1):
                    # Offset hinzufügen (Z-Fighting) + Grid Position
                    insert_pos = (offset_x, 0.0, offset_z + 0.0005)

                    plate_insert = create_plate(
                        f,
                        body_ctx,
                        insert_names.get(idx, hole["name"]),
                        None, None, None,
                        bierkasten_lp,
                        aggregate_parent=bierkasten,
                        representation_maps=insert_maps[idx], # Ist bereits eine Liste [Solid, Wireframe]
                        pos_offset=insert_pos
                    )
                    add_property_set(f, plate_insert, "Pset_ManufacturerTypeInformation", pset_data)
                    # WICHTIG: Stil auch auf die Instanz (MappedItem) des Wireframes anwenden
                    if len(plate_insert.Representation.Representations) > 1:
                        assign_style_to_shape(f, plate_insert.Representation.Representations[1], edge_style)

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
