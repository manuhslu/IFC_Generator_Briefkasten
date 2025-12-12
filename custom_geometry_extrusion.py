# ifc_setup.py muss die Funktionen aus dem GitHub-Link enthalten
from ifc_setup import create_file, local_placement
import ifcopenshell
import ifcopenshell.guid

def axis2placement_2d(model, point, direction=None):
    location = model.create_entity("IfcCartesianPoint", list(point))
    if direction:
        ref_direction = model.create_entity("IfcDirection", list(direction))
        return model.create_entity("IfcAxis2Placement2D", location, ref_direction)
    return model.create_entity("IfcAxis2Placement2D", location)

def indexed_polycurve(model, points, arc_points=None, closed=False):
    if arc_points is None:
        arc_points = []
    
    pt_list = model.create_entity("IfcCartesianPointList2D", CoordList=[list(p) for p in points])
    
    segments = []
    arc_mids = set(arc_points)
    current_line = [1]
    num_points = len(points)
    limit = num_points if closed else num_points - 1
    
    i = 0
    while i < limit:
        next_idx = (i + 1) % num_points
        if next_idx in arc_mids:
            next_next_idx = (next_idx + 1) % num_points
            if len(current_line) > 1:
                segments.append(model.create_entity("IfcLineIndex", current_line))
            segments.append(model.create_entity("IfcArcIndex", [i + 1, next_idx + 1, next_next_idx + 1]))
            current_line = [next_next_idx + 1]
            i += 2
        else:
            current_line.append(next_idx + 1)
            i += 1
            
    if len(current_line) > 1:
        segments.append(model.create_entity("IfcLineIndex", current_line))
        
    return model.create_entity("IfcIndexedPolyCurve", Points=pt_list, Segments=segments, SelfIntersect=False)

# Anpassung Ihrer Hilfsfunktionen für Konsistenz
def circle_curve(model, center, radius):
    # IfcCircle benötigt einen IfcAxis2Placement2D, nicht den 3D-Placement
    placement = model.create_entity(
        "IfcAxis2Placement2D",
        Location=model.create_entity("IfcCartesianPoint", list(center)),
    )
    return model.create_entity("IfcCircle", placement, radius)


def erstelle_geometrie_mit_freiprofil(dateiname="custom_geometry_extrusion.ifc"):
    """
    Erstellt ein IFC-Modell mit der komplexen Geometrie.
    """

    # VEREINFACHUNG HIER: GESAMTES SETUP IN EINEM SCHRITT!
    # model, project, context, body, storey werden direkt erstellt und zurückgegeben
    model, project, context, body, storey = create_file(dateiname)
    
    # -----------------------------------------------------------
    # AB HIER NUR NOCH GEOMETRIE-LOGIK (WIE VORHER)
    # -----------------------------------------------------------

    # 1. Profil definieren (Aussenkurve mit Kreisbogen + innerer Kreis)
    outer_curve = indexed_polycurve(
        model,
        points=[(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (51.2, 98.7), (18.5, 105.3), (0.0, 77.5)],
        arc_points=[4],
        closed=True,
    )

    profile = model.create_entity(
        "IfcArbitraryProfileDefWithVoids",
        ProfileType="AREA",
        OuterCurve=outer_curve,
        InnerCurves=[circle_curve(model, (50.0, 50.0), radius=10.0)],
    )

    # 2. Extrusion
    extrusion_depth = 200.0
    # Die Funktion axis2placement_3d muss noch in den scope oder aus ifc_setup importiert werden
    from ifc_setup import axis2placement_3d 
    solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=axis2placement_3d(model),
        ExtrudedDirection=model.create_entity("IfcDirection", (0.0, 0.0, 1.0)),
        Depth=extrusion_depth,
    )

    # 3. Shape und Repräsentation
    shape_representation = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    representation = model.create_entity("IfcProductDefinitionShape", Representations=[shape_representation])

    # 4. Produkt erzeugen und platzieren
    product = model.create_entity(
        "IfcBuildingElementProxy",
        ifcopenshell.guid.new(),
        Name="Element_mit_Freiprofil",
    )
    
    # local_placement wird aus ifc_setup importiert
    product.ObjectPlacement = local_placement(model, relative_to=storey.ObjectPlacement) 
    product.Representation = representation

    # 5. Produkt dem Geschoss zuordnen
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        products=[product],
        relating_structure=storey,
    )

    # 6. Modell speichern
    model.write(dateiname)
    print(f"IFC-Datei erfolgreich erstellt: {dateiname}")


if __name__ == "__main__":
    # Achtung: Stellen Sie sicher, dass die Hilfsfunktionen (indexed_polycurve etc.)
    # und die importierten Funktionen aus ifc_setup.py verfügbar sind.
    erstelle_geometrie_mit_freiprofil()
