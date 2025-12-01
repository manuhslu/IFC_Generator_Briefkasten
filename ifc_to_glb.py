import multiprocessing
import ifcopenshell
import ifcopenshell.geom
import os

def convert_ifc_to_glb(ifc_path, glb_path):
    # IFC-Datei laden
    if not os.path.exists(ifc_path):
        raise FileNotFoundError(f"❌ IFC-Datei nicht gefunden: {ifc_path}")

    print(f"📂 Öffne IFC-Datei: {ifc_path}")
    ifc_file = ifcopenshell.open(ifc_path)

    # Geometrie- und Serialisierungs-Settings
    settings = ifcopenshell.geom.settings()

    # Wir wollen 3D-Modelle (Kurven, Flächen, Volumen)
    settings.set("dimensionality", ifcopenshell.ifcopenshell_wrapper.CURVES_SURFACES_AND_SOLIDS)

    # Farben/Materialien übernehmen (wichtig für GLB)
    settings.set("apply-default-materials", True)

    # Optional: Weltkoordinaten verwenden
    settings.set("use-world-coords", True)

    # Serialisierer konfigurieren
    serialiser_settings = ifcopenshell.geom.serializer_settings()
    serialiser_settings.set("use-element-guids", True)

    os.makedirs(os.path.dirname(glb_path), exist_ok=True)
    serialiser = ifcopenshell.geom.serializers.gltf(glb_path, settings, serialiser_settings)

    serialiser.setFile(ifc_file)
    serialiser.setUnitNameAndMagnitude("METER", 1.0)
    serialiser.writeHeader()

    # Iterator initialisieren (mehrkernig)
    iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count())

    print("🔄 Konvertiere Geometrie...")
    if iterator.initialize():
        while True:
            shape = iterator.get()
            serialiser.write(shape)
            if not iterator.next():
                break

    serialiser.finalize()
    print(f"✅ GLB-Datei erfolgreich erstellt: {glb_path}")


if __name__ == "__main__":
    # Eingabe: IFC-Datei und Ausgabepfad für GLB
    input_ifc = os.path.join("models", "tisch.ifc")
    output_glb = os.path.join("models", "tisch.glb")

    convert_ifc_to_glb(input_ifc, output_glb)

if __name__ == "__main__":
    # Eingabe: IFC-Datei und Ausgabepfad für GLB
    input_ifc = os.path.join("models", "briefkasten.ifc")
    output_glb = os.path.join("models", "briefkasten.glb")

    convert_ifc_to_glb(input_ifc, output_glb)