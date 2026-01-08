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
    settings.set("use-world-coords", False)

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
    # Erstelle Dummy-IFC-Dateien analog zu den Tests in generate_mailbox_v2 (__main__)
    from generate_mailbox_v2 import generate_mailbox_ifc
    tests = [
        {"rows": 1, "columns": 1, "color": "#4D6F39", "name": "test_generate_mailbox_1x1"},
        # Maximal: rows=3 (X), columns=5 (Z)
        {"rows": 5, "columns": 3, "color": "#4D6F39", "name": "test_generate_mailbox_5x3"},
    ]

    for t in tests:
        print(f"Teste Konvertierung für {t['name']}...")
        ifc_path = generate_mailbox_ifc(
            rows=t["rows"],
            columns=t["columns"],
            color=t["color"],
            output_path=Path(f"{t['name']}.ifc"),
        )
        if ifc_path:
            glb_path = Path(f"{t['name']}.glb")
            convert_ifc_to_glb(ifc_path, glb_path)
            print(f"✅ Konvertierung erfolgreich: {glb_path}")