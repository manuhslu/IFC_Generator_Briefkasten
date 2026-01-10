import streamlit as st
import base64
from typing import Optional, Tuple, List

from datetime import datetime
from pathlib import Path
from generate_mailbox_v2 import generate_mailbox_ifc, BASE_WIDTH, BASE_HEIGHT, FRAME_DEPTH_DEFAULT
from ifc_to_glb import convert_ifc_to_glb
from ui_components import color_selector

st.set_page_config(page_title="Briefkasten-Konfigurator", layout="wide")
st.title("📬 Parametrischer Briefkasten-Konfigurator")

# --- Konstanten für Standardwerte (aus generate_mailbox_v2) ---
DEFAULT_BREITE = BASE_WIDTH
DEFAULT_HOEHE = BASE_HEIGHT
DEFAULT_TIEFE = FRAME_DEPTH_DEFAULT
DEFAULT_FARBE = "#C0C0C0"  # Farblos eloxiert / Grau

@st.cache_data(show_spinner=False)
def generate_and_convert_model(
    width: float, height: float, depth: float, color: str, rows: int, columns: int, mounting_type: str, sonerie_positions: List[Tuple[int, int]], has_intercom: bool, has_camera: bool, cache_buster: str
) -> Optional[Tuple[bytes, bytes]]:
    """
    Generiert ein IFC-Modell, konvertiert es nach GLB und gibt die GLB- und IFC-Daten als Bytes zurück.
    Streamlit's Caching verhindert die Neugenerierung bei gleichen Parametern.
    """
    ifc_path = generate_mailbox_ifc(
        width=width, height=height, depth=depth, color=color, rows=rows, columns=columns, mounting_type=mounting_type, sonerie_positions=sonerie_positions, has_intercom=has_intercom, has_camera=has_camera
    )
    if not ifc_path:
        st.error("IFC-Datei konnte nicht erstellt werden.")
        return None

    glb_path = ifc_path.with_suffix(".glb")
    
    try:
        # Konvertierung aufrufen
        convert_ifc_to_glb(ifc_path, glb_path)

        ifc_bytes = None
        glb_bytes = None

        if ifc_path.exists():
            ifc_bytes = ifc_path.read_bytes()
        else:
            st.error("Temporäre IFC-Datei konnte nicht gelesen werden.")
            return None

        if glb_path.exists():
            glb_bytes = glb_path.read_bytes()
        else:
            st.error("Modell konnte nicht konvertiert werden (GLB-Datei nicht gefunden).")
            return None
            
        return glb_bytes, ifc_bytes

    except Exception as e:
        st.error(f"Ein Fehler ist bei der Konvertierung aufgetreten: {e}")
        return None
    finally:
        # Stelle sicher, dass die temporären Dateien nach der Verwendung gelöscht werden.
        for p in [ifc_path, glb_path]:
            if p and p.exists():
                p.unlink()

def get_model_viewer_html(
    data_url: str,
    exposure: float = 1.0,
    shadow_intensity: float = 1.5,
    shadow_softness: float = 1.0,
    tone_mapping: str = "neutral",
    light_rotation: int = 0,
    metallic_factor: float = 0.4,
    roughness_factor: float = 0.3,
    environment_image: str = "legacy",
) -> str:
    """Erzeugt den HTML-Code für die <model-viewer>-Komponente."""
    return f"""
        <model-viewer
            src="{data_url}"
            camera-controls
            auto-rotate
            camera-orbit="180deg 75deg 105%"
            min-camera-orbit="auto auto 5%"
            shadow-intensity="{shadow_intensity}"
            shadow-softness="{shadow_softness}"
            environment-image="{environment_image}"
            environment-rotation="0deg {light_rotation}deg 0deg"
            exposure="{exposure}"
            tone-mapping="{tone_mapping}"
            background-color="#eeeeee"
            style="width:100%; height:600px;">
            <effect-composer render-mode="quality">
                <outline-effect color="black" strength="1.0"></outline-effect>
                <ssao-effect intensity="2.0" radius="0.1"></ssao-effect>
            </effect-composer>
            <style>
              model-viewer {{
                --poster-color: transparent;
              }}
            </style>
        </model-viewer>
        <script type="module" 
                src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js">
        </script>
        <script type="module" 
                src="https://ajax.googleapis.com/ajax/libs/model-viewer-effects/1.5.0/model-viewer-effects.min.js">
        </script>
        <script>
            const viewer = document.querySelector('model-viewer');
            viewer.addEventListener('load', () => {{
                for (const material of viewer.model.materials) {{
                    material.pbrMetallicRoughness.setMetallicFactor({metallic_factor});
                    material.pbrMetallicRoughness.setRoughnessFactor({roughness_factor});
                }}
            }});
        </script>
    """


# --- Session State Initialisierung ---
if 'breite' not in st.session_state:
    st.session_state.breite = 0.409 # Default Querformat
if 'hoehe' not in st.session_state:
    st.session_state.hoehe = 0.312 # Default Querformat
if 'tiefe' not in st.session_state:
    st.session_state.tiefe = 0.355 # Default Querformat
if 'farbe' not in st.session_state:
    st.session_state.farbe = DEFAULT_FARBE
if 'rows' not in st.session_state:
    st.session_state.rows = 1
if 'columns' not in st.session_state:
    st.session_state.columns = 1
if 'mounting_type' not in st.session_state:
    st.session_state.mounting_type = "Wandmontage"
if 'sonerie_mode' not in st.session_state:
    st.session_state.sonerie_mode = "Nein"
if 'sonerie_selection' not in st.session_state:
    st.session_state.sonerie_selection = set([(0, 0)]) # Default unten links
if 'format_selection' not in st.session_state:
    st.session_state.format_selection = "Querformat"
if 'has_intercom' not in st.session_state:
    st.session_state.has_intercom = False
if 'has_camera' not in st.session_state:
    st.session_state.has_camera = False

# --- Validierung gegen veraltete Session-State-Werte ---
# Verhindert Fehler, wenn noch alte Werte (z.B. "Wand" oder False) im Cache liegen
valid_mounting = ["Wandmontage", "Freistehend"]
if st.session_state.mounting_type not in valid_mounting:
    st.session_state.mounting_type = valid_mounting[0]

valid_sonerie = ["Nein", "Ja"]
if st.session_state.sonerie_mode not in valid_sonerie:
    st.session_state.sonerie_mode = valid_sonerie[0]

# Vorbereitung der Sonerie-Positionen für den Generator
current_sonerie_positions = []
if st.session_state.sonerie_mode == "Ja":
    current_sonerie_positions = sorted(list(st.session_state.sonerie_selection))

# --- Zentrale Modellgenerierung ---
# Das Modell wird immer basierend auf dem aktuellen session_state generiert.
# @st.cache_data verhindert die Neugenerierung, wenn sich die Parameter nicht ändern.
# Der Spinner wird dank Caching nur bei echten Neuberechnungen länger sichtbar sein.
glb_bytes, ifc_bytes = None, None
with st.spinner("Aktualisiere Modell..."):
    model_data = generate_and_convert_model(
        st.session_state.breite,
        st.session_state.hoehe,
        st.session_state.tiefe,
        st.session_state.farbe,
        st.session_state.rows,
        st.session_state.columns,
        st.session_state.mounting_type,
        current_sonerie_positions,
        st.session_state.has_intercom,
        st.session_state.has_camera,
        "v2.3", # Cache Buster: Zwingt Streamlit zur Neugenerierung bei Code-Änderungen
    )
    if model_data:
        glb_bytes, ifc_bytes = model_data

# --- UI Rendering ---
# --- Layout & CSS ---
st.markdown("""
    <style>
    /* Fixiert die linke Spalte (Viewer) */
    div[data-testid="column"]:nth-of-type(1) > div {
        position: sticky;
        top: 2rem;
        z-index: 100;
    }
    /* Sticky Footer für Download-Buttons in der rechten Spalte */
    .download-container {
        position: sticky;
        bottom: 0;
        background-color: white;
        padding: 1rem 0;
        border-top: 1px solid #f0f2f6;
        z-index: 99;
    }
    </style>
""", unsafe_allow_html=True)

# --- Layout: Links Viewer, rechts Eingabe ---
col1, col2 = st.columns([2, 1])

# ---------- RECHTS: Eingaben ----------
with col2:
    st.subheader("Konfiguration")

    # Callback für Format-Änderung
    def update_dims():
        fmt = st.session_state.format_selection
        if fmt == "Querformat":
            st.session_state.breite = 0.409
            st.session_state.hoehe = 0.312
            st.session_state.tiefe = 0.355
        elif fmt == "Hochformat":
            st.session_state.breite = 0.300
            st.session_state.hoehe = 0.312
            st.session_state.tiefe = 0.455

    # Section 1: Format & Grösse
    st.markdown("### Format & Grösse")
    
    st.radio(
        "Format wählen", 
        ["Querformat", "Hochformat", "Benutzerdefiniert"], 
        key="format_selection", 
        on_change=update_dims,
        horizontal=False
    )

    if st.session_state.format_selection == "Benutzerdefiniert":
        st.slider("Breite [m]", 0.2, 1.0, key="breite", step=0.05)
        st.slider("Höhe [m]", 0.2, 1.0, key="hoehe", step=0.05)
        st.slider("Tiefe [m]", 0.1, 0.5, key="tiefe", step=0.05)
    else:
        st.info(f"Masse: {st.session_state.breite:.2f}m x {st.session_state.hoehe:.2f}m x {st.session_state.tiefe:.2f}m")

    # Section 2: Anordnung
    st.markdown("### Anordnung")
    st.caption("Wählen Sie die Grösse durch Klicken auf das Raster:")

    # Grid-Selector: 5 breit (rows), 4 hoch (columns)
    # Wir rendern von oben (4) nach unten (1), damit es wie ein physischer Aufbau aussieht.
    for h in range(4, 0, -1):
        cols_ui = st.columns(5)
        for w in range(1, 6):
            # Ist dieser Slot Teil der aktuellen Auswahl?
            is_selected = (w <= st.session_state.rows) and (h <= st.session_state.columns)
            btn_type = "primary" if is_selected else "secondary"
            
            def update_grid(width=w, height=h):
                st.session_state.rows = width
                st.session_state.columns = height

            cols_ui[w-1].button(
                "■", 
                key=f"btn_grid_{w}_{h}", 
                type=btn_type, 
                on_click=update_grid,
                use_container_width=True,
                help=f"{w} Breit x {h} Hoch"
            )
    
    st.write(f"**Auswahl:** {st.session_state.rows} Breit x {st.session_state.columns} Hoch")

    # Section 3: Farbauswahl
    color_selector(key="farbe")

    # Section 4: Montage & Technik
    st.markdown("### Montage & Technik")
    st.radio("Montageart", ["Wandmontage", "Freistehend"], key="mounting_type")
    st.radio("Sonerie", ["Nein", "Ja"], key="sonerie_mode")

    if st.session_state.sonerie_mode == "Ja":
        st.checkbox("Freisprechanlage", key="has_intercom")
        st.checkbox("Kamera", key="has_camera")
        st.caption("Position der Sonerie wählen:")
        
        # Check double height condition (Max 10 Namensschilder pro Feld)
        # Wenn (Total - 1) > 10, dann doppelte Höhe nötig.
        total_boxes = st.session_state.rows * st.session_state.columns
        is_double_height = ((total_boxes - 1) > 10) and (st.session_state.columns >= 2)

        # Grid Selector für Sonerie-Positionen
        # Wir iterieren von oben (columns-1) nach unten (0)
        for c in range(st.session_state.columns - 1, -1, -1):
            cols_son = st.columns(st.session_state.rows)
            for r in range(st.session_state.rows):
                # Determine selection state
                is_start = (r, c) in st.session_state.sonerie_selection
                is_extension = False
                # If double height, check if this slot is the "top" part of a selected start
                if is_double_height and c > 0 and (r, c - 1) in st.session_state.sonerie_selection:
                    is_extension = True
                
                is_selected = is_start or is_extension
                
                # Determine interactivity
                is_disabled = False
                click_target = (r, c)
                
                # "nur die oberste reihe ist gespert" (als Startposition)
                if is_double_height and c == st.session_state.columns - 1:
                    if is_extension:
                        # Wenn es eine Erweiterung ist, soll es leuchten (nicht disabled)
                        # Klick darauf entfernt die Auswahl (target = start position)
                        click_target = (r, c - 1)
                    else:
                        is_disabled = True
                elif is_extension:
                    # Klick auf Erweiterung toggelt die Basis
                    click_target = (r, c - 1)
                
                def toggle_sonerie(pos=click_target):
                    # Max 1 Logic: Clear others
                    if pos in st.session_state.sonerie_selection:
                        st.session_state.sonerie_selection.remove(pos)
                    else:
                        st.session_state.sonerie_selection.clear()
                        st.session_state.sonerie_selection.add(pos)
                
                btn_type = "primary" if is_selected else "secondary"
                
                cols_son[r].button(
                    " ",
                    key=f"son_pos_{r}_{c}",
                    on_click=toggle_sonerie,
                    use_container_width=True,
                    type=btn_type,
                    disabled=is_disabled,
                    help=f"Sonerie an Position {r+1}/{c+1}"
                )

    st.markdown("---")

    # Sticky Bottom Container for Downloads
    st.markdown('<div class="download-container">', unsafe_allow_html=True)
    if ifc_bytes:
        file_name_ifc = f"{datetime.now().strftime('%Y-%m-%d')}_Briefkasten.ifc"
        st.download_button(
            label="Download IFC",
            data=ifc_bytes,
            file_name=file_name_ifc,
            mime="application/x-step",
            use_container_width=True
        )
    
    if glb_bytes:
        file_name_glb = f"{datetime.now().strftime('%Y-%m-%d')}_Briefkasten.glb"
        st.download_button(
            label="Download GLB",
            data=glb_bytes,
            file_name=file_name_glb,
            mime="model/gltf-binary",
            use_container_width=True
        )
    st.markdown('</div>', unsafe_allow_html=True)


# ---------- LINKS: Viewer ----------
with col1:
    st.subheader("3D-Ansicht")

    with st.expander("🛠️ Viewer-Optionen (Experte)"):
        exposure = st.slider("Belichtung (Exposure)", 0.0, 3.0, 1.0, 0.1)
        shadow_intensity = st.slider("Schattenintensität", 0.0, 3.0, 1.5, 0.1)
        shadow_softness = st.slider("Schattenweichheit", 0.0, 1.0, 1.0, 0.1)
        light_rotation = st.slider("Lichtrichtung (Rotation)", 0, 360, 0, 15)
        tone_mapping = st.selectbox("Tone Mapping", ["neutral", "aces", "agx"], index=0)
        environment_image = st.selectbox("Environment Image", ["legacy", "neutral"], index=0)
        metallic_factor = st.slider("Metallic Factor", 0.0, 1.0, 0.4, 0.05)
        roughness_factor = st.slider("Roughness Factor", 0.0, 1.0, 0.3, 0.05)

    # Zeigt das Modell nur an, wenn es im Session State vorhanden ist
    if glb_bytes:
        b64 = base64.b64encode(glb_bytes).decode("ascii")
        data_url = f"data:model/gltf-binary;base64,{b64}"

        viewer_html = get_model_viewer_html(data_url, exposure, shadow_intensity, shadow_softness, tone_mapping, light_rotation, metallic_factor, roughness_factor, environment_image)
        st.components.v1.html(viewer_html, height=620)
        
        if st.button("🔄 Ansicht aktualisieren", use_container_width=True):
            st.rerun()
    else:
        # Fallback, falls die Generierung fehlschlägt
        st.warning("Modell konnte nicht geladen werden.")
