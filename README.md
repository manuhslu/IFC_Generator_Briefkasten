# IFC Mailbox Generator (aktuell: `generate_mailbox_v2.py`)

Parametrische Briefkasten-Anlage auf Basis von IfcOpenShell:
- Furnishing „Bierkasten“ mit Deckblatt + Einlagen („Keine Werbung“, „Beschriftung“, „Einwurfklappe“)
- Separates Furnishing mit Rahmenkopie
- Raster in X (rows, max 3) und Z (columns, max 5) mit 3 mm Abstand
- Außenprofil (12 Punkte, 4 Bögen) skalierbar über Breite/Höhe; Öffnungen top-ausgerichtet und mit 1 mm Inset
- Rahmen: Außenoffset 18 mm, Innenoffset 3 mm, Extrusion `depth` (Standard 0.35 m)
- Farben via IfcSurfaceStyle; PropertySet „Pset_ManufacturerTypeInformation“ pro Element

## Voraussetzungen
- Python 3.9+
- Pakete laut `requirements.txt` (u.a. `ifcopenshell`, `streamlit`)

Installation:
```bash
python -m venv .venv
. .venv/Scripts/activate  # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## CLI-Nutzung
```bash
python generate_mailbox_v2.py
```
Erzeugt u.a. `test_generate_mailbox_1x1.ifc` und `test_generate_mailbox_5x3.ifc` im Arbeitsordner.

Wichtige Defaults (Meter):
- Breite `BASE_WIDTH` ≈ 0.409
- Höhe `BASE_HEIGHT` ≈ 0.3115
- Tiefe/Extrusion Rahmen `FRAME_DEPTH_DEFAULT` = 0.35
- Raster: rows (X) max 3, columns (Z) max 5, Abstand 3 mm

## Streamlit UI
Start:
```bash
. .venv/Scripts/activate
python -m streamlit run main.py
```
Im UI lassen sich Breite/Höhe/Tiefe, Farbe, rows/columns einstellen; das Modell wird je Änderung neu als IFC generiert und anschließend nach GLB konvertiert.

## IFC → GLB
`ifc_to_glb.py` konvertiert IFC nach GLB. Der Testlauf erzeugt die gleichen Test-IFCs wie `generate_mailbox_v2` (1x1, 5x3) und konvertiert sie:
```bash
python ifc_to_glb.py
```

## Dateien
- `generate_mailbox_v2.py` – Generator (Platten, Rahmen, Raster, Styles, Psets)
- `main.py` – Streamlit-Frontend, nutzt `generate_mailbox_v2`
- `ifc_to_glb.py` – IFC→GLB Konverter (mit apply-default-materials)
- `test_generate_mailbox_1x1.ifc`, `test_generate_mailbox_5x3.ifc` – Beispielausgaben

## Referenz
- Offizielle Doku: https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html
