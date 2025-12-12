import os
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

# ====================================================================
# HILFSFUNKTIONEN (Platzierung und Geometrie-Bausteine)
# Hinweis: Diese müssten in der finalen Datei verfügbar sein.
# ====================================================================

# [axis2placement_3d, local_placement, indexed_polycurve, create_circle_curve]
# Die Definitionen dieser Funktionen werden hier aus Platzgründen weggelassen,
# sie müssen aber aus dem Code der vorherigen Antwort übernommen werden.

def axis2placement_3d(model, location=(0.0, 0.0, 0.0), z_dir=(0.0, 0.0, 1.0), x_dir=(1.0, 0.0, 0.0)):
    """Erstellt eine IfcAxis2Placement3D für 3D-Platzierungen."""
    return model.create_entity(
        "IfcAxis2Placement3D",
        Location=model.create_entity("IfcCartesianPoint", list(location)),
        Axis=model.create_entity("IfcDirection", list(z_dir)),
        RefDirection=model.create_entity("IfcDirection", list(x_dir)),
    )

def local_placement(model, relative_to=None, location=(0.0, 0.0, 0.0), z_dir=(0.0, 0.0, 1.0), x_dir=(1.0, 0.0, 0.0)):
    """Erstellt eine IfcLocalPlacement."""
    return model.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=relative_to,
        RelativePlacement=axis2placement_3d(model, location, z_dir, x_dir),
    )

def indexed_polycurve(model, points, arc_points=(), closed=False):
    """
    Erstellt eine IfcIndexedPolyCurve (beliebige Polylinie) mit optionalen Kreisbogen-Segmenten.
    """
    dims = len(points[0])
    if dims == 2:
        point_list = model.create_entity("IfcCartesianPointList2D", CoordList=[list(p) for p in points])
    else:
        raise ValueError(f"Unerwartete Punktdimension: {dims}. Es werden nur 2D-Punkte im Profil unterstützt.")

    segments = []
    arc_starts = set(arc_points) if arc_points else set()
    n = len(points)
    limit = n if closed else n - 1
    
    i = 0
    while i < limit:
        current_idx = i + 1
        if current_idx in arc_starts:
            # Bogen: Start -> Mitte -> Ende (3 Punkte)
            idx_start = current_idx
            idx_mid = (i + 1) % n + 1
            idx_end = (i + 2) % n + 1
            segments.append(model.create_entity("IfcArcIndex", [idx_start, idx_mid, idx_end]))
            i += 2
        else:
            # Linie: Start -> Ende (2 Punkte)
            idx_start = current_idx
            idx_end = (i + 1) % n + 1
            segments.append(model.create_entity("IfcLineIndex", [idx_start, idx_end]))
            i += 1

    return model.create_entity("IfcIndexedPolyCurve", Points=point_list, Segments=segments)


def create_circle_curve(model, center, radius):
    """Erstellt eine IfcCircle-Kurve zur Verwendung als inneres Profil."""
    placement_2d = model.create_entity(
        "IfcAxis2Placement2D",
        Location=model.create_entity("IfcCartesianPoint", list(center)),
    )
    return model.create_entity("IfcCircle", placement_2d, radius)

def assign_material(model, product, name, color_rgb=None):
    """Weist einem Produkt ein Material und optional eine Farbe zu."""
    material = model.create_entity("IfcMaterial", Name=name)
    model.create_entity(
        "IfcRelAssociatesMaterial",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[product],
        RelatingMaterial=material,
    )
    # Farbe/Style bewusst weggelassen; kann später mit korrektem Kontext ergänzt werden.

def add_simple_property_set(model, product, pset_name, property_dict):
    """Fügt ein Property Set mit einfachen Werten (Text, Zahl, Bool) hinzu."""
    properties = []
    for name, value in property_dict.items():
        # Automatische Typ-Erkennung für den NominalValue
        if isinstance(value, bool):
            nominal_value = model.create_entity("IfcBoolean", value)
        elif isinstance(value, int):
            nominal_value = model.create_entity("IfcInteger", value)
        elif isinstance(value, float):
            nominal_value = model.create_entity("IfcReal", value)
        else:
            nominal_value = model.create_entity("IfcLabel", str(value))
            
        prop = model.create_entity("IfcPropertySingleValue", Name=name, NominalValue=nominal_value)
        properties.append(prop)

    pset = model.create_entity("IfcPropertySet", 
                               GlobalId=ifcopenshell.guid.new(),
                               Name=pset_name,
                               HasProperties=properties)

    model.create_entity("IfcRelDefinesByProperties",
                        GlobalId=ifcopenshell.guid.new(),
                        RelatedObjects=[product],
                        RelatingPropertyDefinition=pset)

# ====================================================================
# HAUPTFUNKTION FÜR DIE GEOMETRIE-ERSTELLUNG (Modulares Element)
# Diese Funktion wurde leicht angepasst, um IfcPlate zu unterstützen.
# ====================================================================

def create_extruded_element(
    model, 
    storey, 
    element_name, 
    outer_points, 
    extrusion_depth, 
    arc_points=None,
    inner_profiles_data=None, 
    product_class="IfcBuildingElementProxy" # Standardwert beibehalten
):
    """
    Erstellt einen extrudierten 3D-Körper basierend auf einer Punkteliste 
    mit optionalen inneren Profilen (Löchern) und fügt ihn einem Geschoss hinzu.
    """
    if arc_points is None: arc_points = []
    if inner_profiles_data is None: inner_profiles_data = []

    # 1. Äußere Kurve definieren
    outer_curve = indexed_polycurve(
        model,
        points=outer_points,
        arc_points=arc_points,
        closed=True,
    )
    
    # 2. Innere Kurven (Löcher) verarbeiten
    inner_curves = []
    for profile_data in inner_profiles_data:
        profile_type = profile_data.get('type')
        
        if profile_type == 'circle':
            inner_curves.append(
                create_circle_curve(model, profile_data['center'], profile_data['radius'])
            )
        elif profile_type == 'polyline':
            inner_curves.append(
                indexed_polycurve(
                    model, 
                    points=profile_data['points'], 
                    arc_points=profile_data.get('arc_points', []),
                    closed=profile_data.get('closed', True)
                )
            )

    # 3. Profil-Definition
    if inner_curves:
        profile = model.create_entity(
            "IfcArbitraryProfileDefWithVoids",
            ProfileType="AREA",
            OuterCurve=outer_curve,
            InnerCurves=inner_curves,
        )
    else:
        profile = model.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            OuterCurve=outer_curve,
        )

    # 4. Extrusion
    solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=axis2placement_3d(model),
        ExtrudedDirection=model.create_entity("IfcDirection", (0.0, 0.0, 1.0)),
        Depth=extrusion_depth,
    )

    # 5. Shape und Repräsentation (IfcPlate, IfcBuildingElementProxy, etc.)
    body = None
    for ctx in model.by_type("IfcGeometricRepresentationContext"):
        if ctx.ContextIdentifier == "Body":
            body = ctx
            break

    shape_representation = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    representation = model.create_entity("IfcProductDefinitionShape", Representations=[shape_representation])

    # 6. Produkt erzeugen und platzieren
    product = model.create_entity(
        product_class,
        ifcopenshell.guid.new(),
        Name=element_name,
    )
    product.ObjectPlacement = local_placement(model, relative_to=storey.ObjectPlacement)
    product.Representation = representation

    # 7. Produkt dem Geschoss zuordnen
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        products=[product],
        relating_structure=storey,
    )
    
    return product

# ====================================================================
# GENERATOR FÜR DAS METALLBLECH (Nutzung der strukturierten Daten)
# ====================================================================

def generate_metal_plate_ifc(dateiname="metal_plate.ifc", thickness=0.002):
    
    # -------------------------------------------------------------
    # SCHRITT 1: IFC GRUNDSTRUKTUR SETUP
    # -------------------------------------------------------------
    
    # Manuelles, minimales Setup (wie zuvor)
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Metal Plate Project")
    ifcopenshell.api.run("unit.assign_unit", model)
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="My Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="My Building")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="My Storey")
    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=building)
    site.ObjectPlacement = local_placement(model)
    building.ObjectPlacement = local_placement(model, relative_to=site.ObjectPlacement)
    storey.ObjectPlacement = local_placement(model, relative_to=building.ObjectPlacement)


    # -------------------------------------------------------------
    # SCHRITT 2: DATEN FÜR DIE GEOMETRIE-ERSTELLUNG DEFINIEREN
    # -------------------------------------------------------------
    
    # Äusseres Profil (12 Punkte mit 4 Bögen)
    outer_points = [
        (0.0, 0.311),      # 1
        (0.0, 0.0005),     # 2 (Start Bogen 1)
        (0.0, 0.0),        # 3 (Mitte Bogen 1)
        (0.0005, 0.0),     # 4 (Ende Bogen 1, Start Linie)
        (0.4085, 0.0),     # 5 (Ende Linie, Start Bogen 2)
        (0.409, 0.0),      # 6 (Mitte Bogen 2)
        (0.409, 0.0005),   # 7 (Ende Bogen 2, Start Linie)
        (0.409, 0.311),    # 8 (Ende Linie, Start Bogen 3)
        (0.409, 0.3115),   # 9 (Mitte Bogen 3)
        (0.4085, 0.3115),  # 10 (Ende Bogen 3, Start Linie)
        (0.0005, 0.3115),  # 11 (Ende Linie, Start Bogen 4)
        (0.0, 0.3115)      # 12 (Mitte Bogen 4, schliesst zu 1)
    ]
    # Index des Startpunkts für die IfcArcIndex-Segmente (1-basiert)
    arc_indices = [2, 5, 8, 11] 
    
    # Innere Profile (Löcher)
    inner_holes = [
        # Loch 1: (Segmente 0-3)
        {
            'type': 'polyline', 
            'points': [(0.017, 0.1809), (0.017, 0.1957), (0.0973, 0.1957), (0.0973, 0.1809)],
            'closed': True,
        },
        # Loch 2: (Segmente 4-7)
        {
            'type': 'polyline', 
            'points': [(0.017, 0.2057), (0.017, 0.231), (0.0973, 0.231), (0.0973, 0.2057)],
            'closed': True,
        },
        # Loch 3: (Segmente 8-11)
        {
            'type': 'polyline', 
            'points': [(0.017, 0.261), (0.017, 0.2915), (0.373, 0.2915), (0.373, 0.261)],
            'closed': True,
        },
    ]


    # -------------------------------------------------------------
    # SCHRITT 3: ERSTELLUNG DES IFC-ELEMENTS
    # -------------------------------------------------------------

    element_plate = create_extruded_element(
        model, 
        storey, 
        "Metallblech_mit_Loechern", 
        outer_points, 
        thickness, 
        arc_points=arc_indices,
        inner_profiles_data=inner_holes,
        product_class="IfcPlate" # Verwendung des spezifischen IFC-Typs für Platten/Bleche
    )
    
    # Material zuweisen (Aluminium, hellgrau)
    assign_material(model, element_plate, "Aluminium", color_rgb=(0.80, 0.80, 0.85))
    
    # Eigenschaften (Properties) hinzufügen
    add_simple_property_set(model, element_plate, "Pset_ManufacturerTypeInformation", {
        "Manufacturer": "Briefkasten Profi GmbH",
        "ArticleNumber": "BK-ALU-005",
        "ModelLabel": "Premium Alu Plate",
        "ProductionYear": 2025
    })
    
    print(f"IfcPlate '{element_plate.Name}' mit 3 Löchern erfolgreich erstellt.")

    # Speichern der IFC-Datei
    model.write(dateiname)
    print(f"\nIFC-Datei erfolgreich erstellt: {dateiname}")


if __name__ == "__main__":
    # Beispiel: Erstelle das Blech mit 5mm Dicke (statt Standard 2mm)
    generate_metal_plate_ifc(thickness=0.005)
