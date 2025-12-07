from math import isfinite
import tempfile
from pathlib import Path
from typing import Optional

import ifcopenshell

# --- IFC Geometrie- und Struktur-Hilfsfunktionen ---

def _listf(vals):
    return [float(x) for x in vals]


def create_direction(f, xyz):
    return f.create_entity("IfcDirection", _listf(xyz))


def create_point(f, xyz):
    return f.create_entity("IfcCartesianPoint", _listf(xyz))


def axis2placement2d(f, origin=(0.0, 0.0), xdir=(1.0, 0.0)):
    p = f.create_entity("IfcCartesianPoint", _listf(origin))
    d = f.create_entity("IfcDirection", _listf(xdir))
    return f.create_entity("IfcAxis2Placement2D", p, d)


def axis2placement3d(f, origin=(0.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0), xdir=(1.0, 0.0, 0.0)):
    p = create_point(f, origin)
    z = create_direction(f, zdir)
    x = create_direction(f, xdir)
    return f.create_entity("IfcAxis2Placement3D", p, z, x)


def create_project_hierarchy(f):
    project = f.create_entity("IfcProject", ifcopenshell.guid.new(), None, "Mailbox Project")

    # Units (meters)
    si_length = f.create_entity("IfcSIUnit", None, "LENGTHUNIT", None, "METRE")
    units = f.create_entity("IfcUnitAssignment", [si_length])
    project.UnitsInContext = units

    # Contexts
    wcs = axis2placement3d(f, (0, 0, 0))
    model_ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        None,
        "Model",
        3,
        1e-5,
        wcs,
        None,
    )
    body_subctx = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=model_ctx,
        TargetScale=None,
        TargetView="MODEL_VIEW",
        UserDefinedTargetView=None,
    )

    site_placement = f.create_entity("IfcLocalPlacement", None, axis2placement3d(f))
    site = f.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Default Site",
        ObjectPlacement=site_placement,
        CompositionType="ELEMENT",
    )

    bldg_placement = f.create_entity("IfcLocalPlacement", site_placement, axis2placement3d(f))
    building = f.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Building",
        ObjectPlacement=bldg_placement,
        CompositionType="ELEMENT",
    )

    storey_placement = f.create_entity("IfcLocalPlacement", bldg_placement, axis2placement3d(f))
    storey = f.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="Storey 0",
        ObjectPlacement=storey_placement,
        CompositionType="ELEMENT",
        Elevation=0.0,
    )

    # Aggregations
    f.create_entity(
        "IfcRelAggregates",
        ifcopenshell.guid.new(),
        None,
        None,
        None,
        project,
        [site],
    )
    f.create_entity(
        "IfcRelAggregates",
        ifcopenshell.guid.new(),
        None,
        None,
        None,
        site,
        [building],
    )
    f.create_entity(
        "IfcRelAggregates",
        ifcopenshell.guid.new(),
        None,
        None,
        None,
        building,
        [storey],
    )

    return project, body_subctx, storey


def rectangle_solid(
    f,
    x_size,
    y_size,
    z_extrusion,
    origin3d=(0.0, 0.0, 0.0),
):
    # Profile centered at origin in XY; extruded along +Z
    prof_pos = axis2placement2d(f)
    profile = f.create_entity(
        "IfcRectangleProfileDef",
        "AREA",
        None,
        prof_pos,
        float(x_size),
        float(y_size),
    )

    placement3d = axis2placement3d(f, origin3d)
    dir_z = create_direction(f, (0.0, 0.0, 1.0))
    solid = f.create_entity(
        "IfcExtrudedAreaSolid",
        profile,
        placement3d,
        dir_z,
        float(z_extrusion),
    )
    return solid


def make_mailbox_csg(f, dims):
    W = float(dims["width"])          # X size
    D = float(dims["depth"])          # Y size
    H = float(dims["height"])         # Z height
    t = float(dims["door_thickness"]) # door thickness along Y
    SW = float(dims["slot_width"])    # X
    SH = float(dims["slot_height"])   # Z
    SD = float(dims["slot_depth"])    # Y

    # Body box: centered in XY, base at z=0
    body = rectangle_solid(f, W, D, H, origin3d=(0.0, 0.0, 0.0))

    # Door: thin plate at front face (positive Y)
    door_w = min(W * 0.9, W)
    door_h = H * 0.6
    door_bottom = H * 0.10
    # Center of door area in XY
    door_center_x = 0.0
    # Slightly outside the front face so it's visible as addition
    door_center_y = (D / 2.0) + (t / 2.0)
    door = rectangle_solid(
        f,
        door_w,
        t,
        door_h,
        origin3d=(door_center_x, door_center_y, door_bottom),
    )

    # Optional slot: near top, subtracting from the body+door (only if all slot dims > 0)
    union = f.create_entity("IfcBooleanResult", "UNION", body, door)
    if SW > 0.0 and SH > 0.0 and SD > 0.0:
        slot_bottom = H * 0.70
        slot_center = (0.0, (D / 2.0) - (SD / 2.0) - 0.002, slot_bottom)
        slot = rectangle_solid(f, SW, SD, SH, origin3d=slot_center)
        final_csg = f.create_entity("IfcBooleanResult", "DIFFERENCE", union, slot)
    else:
        final_csg = union
    return final_csg


def create_mailbox_product(f, context, storey, dims):
    csg = make_mailbox_csg(f, dims)

    body_repr = f.create_entity(
        "IfcShapeRepresentation",
        context,
        "Body",
        "CSG",
        [csg],
    )
    prod_shape = f.create_entity("IfcProductDefinitionShape", None, None, [body_repr])

    local_placement = f.create_entity(
        "IfcLocalPlacement",
        storey.ObjectPlacement,
        axis2placement3d(f, (0.0, 0.0, 0.0)),
    )


    proxy = f.create_entity(
    "IfcBuildingElementProxy",
    GlobalId=ifcopenshell.guid.new(),
    Name="Mailbox",
    ObjectType="Briefkasten",
    ObjectPlacement=local_placement,
    Representation=prod_shape,
)


    # Place element into the storey via containment
    f.create_entity(
        "IfcRelContainedInSpatialStructure",
        ifcopenshell.guid.new(),
        None,
        None,
        None,
        [proxy],
        storey,
    )
    return proxy


def validate_dims(d):
    # Enforce strictly positive for main body and door thickness
    must_be_pos = ["width", "depth", "height", "door_thickness"]
    for k in must_be_pos:
        v = d[k]
        if not (isfinite(v) and v > 0):
            raise ValueError(f"Ungültiges Maß für {k}: {v}")
    # Slot dimensions can be zero to disable the slot subtraction
    slot_keys = ["slot_width", "slot_height", "slot_depth"]
    for k in slot_keys:
        v = d[k]
        if not (isfinite(v) and v >= 0):
            raise ValueError(f"Ungültiges Maß für {k}: {v}")


def generate_mailbox_ifc(
    width: float, depth: float, height: float, color: str
) -> Optional[Path]:
    """
    Erzeugt eine temporäre IFC-Datei für einen Briefkasten und gibt den Pfad zurück.
    Die Farbe wird direkt der Geometrie zugewiesen.
    """
    dims = {
        "width": width,
        "depth": depth,
        "height": height,
        "door_thickness": 0.005,
        "slot_width": 0.30,
        "slot_height": 0.03,
        "slot_depth": 0.02,
    }
    try:
        validate_dims(dims)

        # 1. IFC-Datei im Speicher erstellen und Hierarchie aufbauen
        f = ifcopenshell.file(schema="IFC4")
        _, context, storey = create_project_hierarchy(f)

        # 2. Produkt (Briefkasten-Geometrie) erstellen
        element = create_mailbox_product(f, context, storey, dims)

        # 3. Sichtbare Farbe für die 3D-Darstellung zuweisen (vereinfachter Weg)
        def hex_to_rgb_floats(hex_color):
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

        r, g, b = hex_to_rgb_floats(color)
        rgb_color = f.create_entity("IfcColourRgb", None, r, g, b)
        surface_style_rendering = f.create_entity("IfcSurfaceStyleRendering", SurfaceColour=rgb_color)
        surface_style = f.create_entity("IfcSurfaceStyle", Name="MailboxColor", Side="BOTH", Styles=[surface_style_rendering])
        
        # Zuweisung des Stils zur Geometrie
        shape_representation = element.Representation.Representations[0]
        styled_item = f.create_entity("IfcStyledItem", Item=shape_representation.Items[0], Styles=[surface_style])
        
        # Ersetze das 'Item' in der Shape Representation durch das 'StyledItem'
        shape_representation.Items = [styled_item]

        # 4. IFC-Datei in ein temporäres Verzeichnis schreiben
        temp_dir = Path(tempfile.gettempdir())
        out_path = temp_dir / f"{ifcopenshell.guid.new()}.ifc"
        f.write(str(out_path))
        
        return out_path
    except Exception as e:
        print(f"Fehler bei der IFC-Generierung: {e}")
        return None


if __name__ == "__main__":
    # Dieser Block dient zum direkten Testen des Skripts
    print("Generiere Test-Briefkasten...")
    test_path = generate_mailbox_ifc(width=0.4, depth=0.25, height=0.5, color="#BF242A")
    if test_path:
        print(f"Test-Briefkasten erfolgreich erstellt: {test_path}")
