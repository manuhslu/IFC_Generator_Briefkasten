# IFC Mailbox Generator (Minimal)

Dieses minimale Python-Projekt generiert ein funktionsfähiges IFC‑Modell eines Briefkastens (Korpus, Tür, Einwurfschlitz) auf Basis von ifcopenshell. Die Geometrie wird als CSG (Vereinigung und Subtraktion) aus einfachen Quadern aufgebaut, orientiert an der offiziellen ifcopenshell-Dokumentation zu Geometrieerstellung.

## Voraussetzungen
- Python 3.9+
- Pakete: `ifcopenshell`

Installation (lokal):

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Nutzung
Erzeuge eine IFC-Datei mit Standardabmessungen:

```bash
python generate_mailbox_ifc.py --out mailbox.ifc
```

Optionale Parameter (Meter):
- `--width` Breite Korpus (X) [0.40]
- `--depth` Tiefe Korpus (Y) [0.25]
- `--height` Höhe Korpus (Z) [0.50]
- `--door-thickness` Türstärke (Y) [0.005]
- `--slot-width` Schlitzbreite (X) [0.30]
- `--slot-height` Schlitzhöhe (Z) [0.03]
- `--slot-depth` Schlitztiefe (Y) [0.02]

Beispiel mit angepassten Maßen:

```bash
python generate_mailbox_ifc.py --out mailbox.ifc \
  --width 0.45 --depth 0.28 --height 0.55 \
  --door-thickness 0.006 --slot-width 0.32 --slot-height 0.03 --slot-depth 0.02
```

## Was erzeugt wird
- IFC4-Datei mit Projekt, Standort, Gebäude, Geschoss und einem `IfcBuildingElementProxy` namens "Mailbox".
- Geometrie:
  - Korpus: Quader (Extrusion eines Rechtecks)
  - Tür: dünner Quader an der Front, per Vereinigung mit Korpus
  - Einwurfschlitz: Quader, per Differenz vom Korpus+Tür abgezogen
- Repräsentationstyp: `Body` als `CSG`

## Hinweise
- Viele Viewer unterstützen Öffnungen/Booleans in Proxies, die CSG-Darstellung ist daher bewusst gewählt. Falls Ihr Viewer Booleans in Proxies ignoriert, kann man alternativ eine reine Volumenrepräsentation ohne Subtraktion erzeugen.
- Einheiten: Meter.

## Referenz
- Offizielle Doku: https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html
