import multiprocessing
import os
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom


def convert_ifc_to_glb(ifc_path: Path, glb_path: Path):
    # IFC-Datei laden
    ifc_file = ifcopenshell.open(str(ifc_path))

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

    serialiser = ifcopenshell.geom.serializers.gltf(str(glb_path), settings, serialiser_settings)

    serialiser.setFile(ifc_file)
    serialiser.setUnitNameAndMagnitude("METER", 1.0)
    serialiser.writeHeader()

    # Iterator initialisieren (mehrkernig)
    iterator = ifcopenshell.geom.iterator(settings, ifc_file, 1)
    if iterator.initialize():
        while True:
            shape = iterator.get()
            serialiser.write(shape)
            if not iterator.next():
                break
    serialiser.finalize()


if __name__ == "__main__":
    # Dieser Block dient zum direkten Testen des Skripts
    # Erstelle eine Dummy-IFC-Datei zum Testen
    from generate_mailbox_ifc import generate_mailbox_ifc
    print("Teste Konvertierung...")
    test_ifc_path = generate_mailbox_ifc(width=0.4, depth=0.2, height=0.5, color="#004E8A")
    if test_ifc_path:
        test_glb_path = test_ifc_path.with_suffix(".glb")
        convert_ifc_to_glb(test_ifc_path, test_glb_path)
        print(f"✅ Konvertierung erfolgreich: {test_glb_path}")
        # Aufräumen
        test_ifc_path.unlink()
        test_glb_path.unlink()