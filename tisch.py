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


def create_project_hierarchy(f):
    project = f.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Table Project")
    # Units (meters)
    si_length = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    units = f.create_entity("IfcUnitAssignment", Units=[si_length])
    project.UnitsInContext = units

    # Root placement
    wcs = axis2placement3d(f, (0, 0, 0))
    model_ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=wcs,
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

    # Aggregations
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=project, RelatedObjects=[site])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=site, RelatedObjects=[building])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=building, RelatedObjects=[storey])

    return project, storey, model_ctx


def ensure_body_context(f, model_ctx):
    subs = [s for s in f.by_type("IfcGeometricRepresentationSubContext") if s.ParentContext == model_ctx and s.ContextIdentifier == "Body"]
    if subs:
        return subs[0]
    return f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=model_ctx,
        TargetView="MODEL_VIEW",
        UserDefinedTargetView=None,
    )


def build_table_items(f, width=4000.0, depth=700.0, height=750.0, leg_size=50.0, thickness=50.0):
    builder = shape_builder.ShapeBuilder(f)

    # Tabletop
    rectangle = builder.rectangle(size=(width, depth))
    tabletop = builder.extrude(builder.profile(rectangle), thickness, (0.0, 0.0, height - thickness))

    # Legs: one rectangle, mirrored about X, Y, and XY around table center
    leg_curve = builder.rectangle(size=(leg_size, leg_size))
    legs_curves = [leg_curve] + builder.mirror(
        leg_curve,
        mirror_axes=[(1.0, 0.0), (0.0, 1.0), (1.0, 1.0)],
        mirror_point=(width / 2.0, depth / 2.0),
        create_copy=True,
    )
    legs_profiles = [builder.profile(leg) for leg in legs_curves]
    legs = [builder.extrude(leg, height - thickness) for leg in legs_profiles]

    # Center at origin
    items = [tabletop] + legs
    builder.translate(items, (-width / 2.0, -depth / 2.0, 0.0))
    return items


def create_table_product(f, storey, model_ctx, items):
    body_ctx = ensure_body_context(f, model_ctx)
    shape = shape_builder.ShapeBuilder(f).get_representation(context=body_ctx, items=items)
    pds = f.create_entity("IfcProductDefinitionShape", Representations=[shape])

    placement = f.create_entity("IfcLocalPlacement", PlacementRelTo=storey.ObjectPlacement, RelativePlacement=axis2placement3d(f))
    table = f.create_entity(
        "IfcFurnishingElement",
        GlobalId=ifcopenshell.guid.new(),
        Name="Table",
        ObjectPlacement=placement,
        Representation=pds,
    )
    f.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[table],
    )
    return table


def main():
    ap = argparse.ArgumentParser(description="Generate a simple IFC table using ShapeBuilder")
    ap.add_argument("--out", default=str(Path("models") / "tisch.ifc"), help="Output IFC path")
    ap.add_argument("--width", type=float, default=1200.0)
    ap.add_argument("--depth", type=float, default=700.0)
    ap.add_argument("--height", type=float, default=750.0)
    ap.add_argument("--leg-size", type=float, default=50.0)
    ap.add_argument("--thickness", type=float, default=50.0, help="Tabletop thickness")
    args = ap.parse_args()

    f = ifcopenshell.file(schema="IFC4")
    _, storey, model_ctx = create_project_hierarchy(f)
    items = build_table_items(f, args.width, args.depth, args.height, args.leg_size, args.thickness)

    # Ensure output directory exists
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    create_table_product(f, storey, model_ctx, items)
    f.write(str(out_path))
    print(f"Wrote IFC table to {out_path}")


if __name__ == "__main__":
    main()
