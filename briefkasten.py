import argparse
from pathlib import Path

import ifcopenshell
from ifcopenshell.util import representation as rep_util
from ifcopenshell.util import shape_builder


def create_point(f, xyz):
    return f.create_entity("IfcCartesianPoint", [float(x) for x in xyz])


def create_direction(f, xyz):
    return f.create_entity("IfcDirection", [float(x) for x in xyz])


def axis2placement3d(f, origin=(0.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0), xdir=(1.0, 0.0, 0.0)):
    p = create_point(f, origin)
    z = create_direction(f, zdir)
    x = create_direction(f, xdir)
    return f.create_entity("IfcAxis2Placement3D", p, z, x)


def axis2placement2d(f, origin=(0.0, 0.0), xdir=(1.0, 0.0)):
    p = f.create_entity("IfcCartesianPoint", [float(x) for x in origin])
    d = f.create_entity("IfcDirection", [float(x) for x in xdir])
    return f.create_entity("IfcAxis2Placement2D", p, d)


def rectangle_solid(f, x_size, y_size, z_extrusion, origin3d=(0.0, 0.0, 0.0)):
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
    return f.create_entity("IfcExtrudedAreaSolid", profile, placement3d, dir_z, float(z_extrusion))


def create_project_hierarchy(f):
    project = f.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Mailbox Project")
    si_length = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    units = f.create_entity("IfcUnitAssignment", Units=[si_length])
    project.UnitsInContext = units

    wcs = axis2placement3d(f, (0, 0, 0))
    model_ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=wcs,
    )
    # Ensure a Body subcontext
    body_ctx = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=model_ctx,
        TargetView="MODEL_VIEW",
        UserDefinedTargetView=None,
    )

    site_lp = f.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=axis2placement3d(f))
    site = f.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Default Site",
        ObjectPlacement=site_lp,
        CompositionType="ELEMENT",
    )

    bldg_lp = f.create_entity("IfcLocalPlacement", PlacementRelTo=site_lp, RelativePlacement=axis2placement3d(f))
    building = f.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Building",
        ObjectPlacement=bldg_lp,
        CompositionType="ELEMENT",
    )

    storey_lp = f.create_entity("IfcLocalPlacement", PlacementRelTo=bldg_lp, RelativePlacement=axis2placement3d(f))
    storey = f.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="Storey 0",
        ObjectPlacement=storey_lp,
        CompositionType="ELEMENT",
        Elevation=0.0,
    )

    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=project, RelatedObjects=[site])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=site, RelatedObjects=[building])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=building, RelatedObjects=[storey])

    return project, storey, body_ctx


def build_mailbox_items_swept(f, width=0.40, depth=0.25, height=0.50, door_thickness=0.005):
    b = shape_builder.ShapeBuilder(f)
    # Body as a box made from extruding rectangle
    body_rect = b.rectangle(size=(width, depth))
    body = b.extrude(b.profile(body_rect), height, (0.0, 0.0, 0.0))

    # Door as a thin plate on front
    door_w = min(width * 0.9, width)
    door_h = height * 0.6
    door_bottom = height * 0.10
    door_center_x = 0.0
    door_center_y = (depth / 2.0) + (door_thickness / 2.0)
    door = b.extrude(
        b.profile(b.rectangle(size=(door_w, door_thickness))),
        door_h,
        (door_center_x, door_center_y, door_bottom),
    )

    items = [body, door]
    return items


def build_mailbox_csg(f, width=0.40, depth=0.25, height=0.50, door_thickness=0.005,
                      slot_width=0.30, slot_height=0.03, slot_depth=0.02):
    body = rectangle_solid(f, width, depth, height, origin3d=(0.0, 0.0, 0.0))
    door_w = min(width * 0.9, width)
    door_h = height * 0.6
    door_bottom = height * 0.10
    door_center = (0.0, (depth / 2.0) + (door_thickness / 2.0), door_bottom)
    door = rectangle_solid(f, door_w, door_thickness, door_h, origin3d=door_center)

    union = f.create_entity("IfcBooleanResult", "UNION", body, door)

    if slot_width > 0 and slot_height > 0 and slot_depth > 0:
        slot_bottom = height * 0.70
        slot_center = (0.0, (depth / 2.0) - (slot_depth / 2.0) - 0.002, slot_bottom)
        slot = rectangle_solid(f, slot_width, slot_depth, slot_height, origin3d=slot_center)
        final_csg = f.create_entity("IfcBooleanResult", "DIFFERENCE", union, slot)
    else:
        final_csg = union
    return final_csg


def create_mailbox_product(f, storey, body_ctx, use_csg, dims, out_name="Mailbox"):
    placement = f.create_entity("IfcLocalPlacement", PlacementRelTo=storey.ObjectPlacement, RelativePlacement=axis2placement3d(f))
    proxy = f.create_entity(
        "IfcBuildingElementProxy",
        GlobalId=ifcopenshell.guid.new(),
        Name=out_name,
        ObjectPlacement=placement,
    )

    if use_csg:
        csg = build_mailbox_csg(f, dims["width"], dims["depth"], dims["height"], dims["door_thickness"],
                                dims["slot_width"], dims["slot_height"], dims["slot_depth"])
        shape = f.create_entity("IfcShapeRepresentation", body_ctx, "Body", "CSG", [csg])
        pds = f.create_entity("IfcProductDefinitionShape", Representations=[shape])
        proxy.Representation = pds
    else:
        items = build_mailbox_items_swept(f, dims["width"], dims["depth"], dims["height"], dims["door_thickness"])
        # Center at origin for nicer placement
        sb = shape_builder.ShapeBuilder(f)
        sb.translate(items, (-dims["width"] / 2.0, -dims["depth"] / 2.0, 0.0))
        shape = shape_builder.ShapeBuilder(f).get_representation(context=body_ctx, items=items)
        pds = f.create_entity("IfcProductDefinitionShape", Representations=[shape])
        proxy.Representation = pds

    f.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[proxy],
    )
    return proxy


def main():
    ap = argparse.ArgumentParser(description="Generate a mailbox IFC (derived from tisch.py structure)")
    ap.add_argument("--out", default=str(Path("models") / "briefkasten.ifc"), help="Output IFC path")
    ap.add_argument("--width", type=float, default=0.40)
    ap.add_argument("--depth", type=float, default=0.25)
    ap.add_argument("--height", type=float, default=0.50)
    ap.add_argument("--door-thickness", type=float, default=0.005)
    ap.add_argument("--slot-width", type=float, default=0.30)
    ap.add_argument("--slot-height", type=float, default=0.03)
    ap.add_argument("--slot-depth", type=float, default=0.02)
    ap.add_argument("--use-csg", action="store_true", help="Use CSG (enables slot subtraction if slot dims > 0)")
    args = ap.parse_args()

    f = ifcopenshell.file(schema="IFC4")
    _, storey, body_ctx = create_project_hierarchy(f)

    dims = {
        "width": args.width,
        "depth": args.depth,
        "height": args.height,
        "door_thickness": args["door-thickness"] if hasattr(args, "door-thickness") else args.door_thickness,
        "slot_width": args["slot-width"] if hasattr(args, "slot-width") else args.slot_width,
        "slot_height": args["slot-height"] if hasattr(args, "slot-height") else args.slot_height,
        "slot_depth": args["slot-depth"] if hasattr(args, "slot-depth") else args.slot_depth,
    }

    create_mailbox_product(f, storey, body_ctx, args.use_csg, dims)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out_path))
    print(f"Wrote IFC mailbox to {out_path}")


if __name__ == "__main__":
    main()

