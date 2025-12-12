import ifcopenshell
import ifcopenshell.api

def create_file(filename="model.ifc"):
    """
    Erstellt ein leeres IFC-Modell mit Projektstruktur (Site, Building, Storey).
    Gibt model, project, context, body, storey zurück.
    """
    model = ifcopenshell.file()
    
    # Projekt erstellen
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Briefkasten Projekt")
    
    # Einheiten definieren (Millimeter für Briefkasten-Details sinnvoll)
    ifcopenshell.api.run(
        "unit.assign_unit",
        model,
        length={"is_metric": True, "raw": "MILLIMETERS"},
    )
    
    # Geometrie-Kontext erstellen
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model, context_type="Model", 
                                context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    
    # Räumliche Struktur
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Grundstück")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Gebäude")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Erdgeschoss")
    
    # Hierarchie verknüpfen
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])
    
    return model, project, context, body, storey

def axis2placement_3d(model, point=(0.,0.,0.), axis=None, ref_direction=None):
    """Erstellt ein IfcAxis2Placement3D."""
    location = model.create_entity("IfcCartesianPoint", list(point))
    axis_ent = model.create_entity("IfcDirection", list(axis)) if axis else None
    ref_ent = model.create_entity("IfcDirection", list(ref_direction)) if ref_direction else None
    return model.create_entity("IfcAxis2Placement3D", location, axis_ent, ref_ent)

def local_placement(model, relative_to=None, relative_placement=None):
    """Erstellt ein IfcLocalPlacement."""
    if relative_placement is None:
        relative_placement = axis2placement_3d(model)
    return model.create_entity("IfcLocalPlacement", PlacementRelTo=relative_to, RelativePlacement=relative_placement)
