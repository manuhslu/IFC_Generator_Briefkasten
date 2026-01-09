import streamlit as st
import base64
from typing import Optional, Tuple

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
    width: float, height: float, depth: float, color: str, rows: int, columns: int, edge_color: str
) -> Optional[Tuple[bytes, bytes]]:
    """
    Generiert ein IFC-Modell, konvertiert es nach GLB und gibt die GLB- und IFC-Daten als Bytes zurück.
    Streamlit's Caching verhindert die Neugenerierung bei gleichen Parametern.
    """
    ifc_path = generate_mailbox_ifc(
        width=width, height=height, depth=depth, color=color, rows=rows, columns=columns, edge_color=edge_color
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
if 'step' not in st.session_state:
    st.session_state.step = "initial" # Zustand 1: Initialisierung
    st.session_state.breite = DEFAULT_BREITE
    st.session_state.hoehe = DEFAULT_HOEHE
    st.session_state.tiefe = DEFAULT_TIEFE
    st.session_state.farbe = DEFAULT_FARBE
    st.session_state.rows = 1
    st.session_state.columns = 1
    st.session_state.edge_color = "#000000" # Default Schwarz

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
        st.session_state.edge_color,
    )
    if model_data:
        glb_bytes, ifc_bytes = model_data

# --- UI Rendering ---
# --- Layout: Links Viewer, rechts Eingabe ---
col1, col2 = st.columns([2, 1])

# ---------- RECHTS: Eingaben ----------
with col2:
    # Zustand 1: Initialisierung (Startansicht)
    if st.session_state.step == "initial":
        st.subheader("Willkommen!")
        if st.button("Start Konfiguration", type="primary"):
            st.session_state.step = "size" # Wechsel zu Zustand 2
            st.rerun()

    # Zustand 2: Größenanpassung
    elif st.session_state.step == "size":
        st.subheader("1. Grösse anpassen")
        st.session_state.breite = st.slider("Breite [m]", 0.2, 1.0, st.session_state.breite, 0.05)
        st.session_state.hoehe = st.slider("Höhe [m]", 0.2, 1.0, st.session_state.hoehe, 0.05)
        st.session_state.tiefe = st.slider("Tiefe [m]", 0.1, 0.5, st.session_state.tiefe, 0.05)
        
        st.subheader("Anordnung")
        st.session_state.columns = st.number_input("Anzahl Spalten", min_value=1, max_value=5, value=st.session_state.columns, step=1)
        st.session_state.rows = st.number_input("Anzahl Zeilen", min_value=1, max_value=3, value=st.session_state.rows, step=1)
        
        st.markdown("---")

        # Callback zum Schliessen des Dialogs und Zurücksetzen der Checkbox
        def close_dialog():
            st.session_state.custom_size_check = False

        st.checkbox("Wunschgrösse nicht vorhanden?", key="custom_size_check")
        if st.session_state.get("custom_size_check"):
            # st.dialog erfordert Streamlit v1.33.0+. Dies ist eine kompatible Alternative.
            st.info("Wir machen ihre Wünsche möglich! max@mustermann.mustermail.ch")
            st.button("Ok", on_click=close_dialog)

        if st.button("Grösse bestätigen", type="primary"):
            st.session_state.step = "color" # Wechsel zu Zustand 3
            st.rerun()

    # Zustand 3: Farbanpassung
    elif st.session_state.step == "color":
        st.subheader("2. Farbe wählen")
        st.markdown(
            f"""
            **Ihre Konfiguration:**
            - **Grösse (B/H/T):** `{st.session_state.breite:.2f} m` / `{st.session_state.hoehe:.2f} m` / `{st.session_state.tiefe:.2f} m`
            - **Anordnung:** `{st.session_state.rows}` Zeile(n), `{st.session_state.columns}` Spalte(n)
            """
        )
        st.markdown("---")

        previous_color = st.session_state.farbe
        st.session_state.farbe = color_selector(default_color_hex=st.session_state.farbe)
        st.markdown("---")

        # st.rerun() wird durch die Interaktion mit dem Radio-Button automatisch ausgelöst
        if st.session_state.farbe != previous_color:
            st.rerun()

        if st.button("Konfiguration abschliessen", type="primary"):
            st.session_state.step = "finished" # Wechsel zu Zustand 4
            st.rerun()

    # Zustand 4: Abschluss
    elif st.session_state.step == "finished":
        st.subheader("✅ Konfiguration abgeschlossen")

        if ifc_bytes:
            file_name = f"{datetime.now().strftime('%Y-%m-%d')}_Briefkastenanlage.ifc"
            st.download_button(
                label="Download IFC",
                data=ifc_bytes,
                file_name=file_name,
                mime="application/x-step",
            )

        if st.button("Neue Konfiguration starten"):
            st.session_state.clear()
            st.rerun()


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
        st.session_state.edge_color = st.color_picker("Kantenfarbe (Wireframe)", st.session_state.edge_color)

    # Zeigt das Modell nur an, wenn es im Session State vorhanden ist
    if glb_bytes:
        b64 = base64.b64encode(glb_bytes).decode("ascii")
        data_url = f"data:model/gltf-binary;base64,{b64}"

        viewer_html = get_model_viewer_html(data_url, exposure, shadow_intensity, shadow_softness, tone_mapping, light_rotation, metallic_factor, roughness_factor, environment_image)
        st.components.v1.html(viewer_html, height=620)
    else:
        # Fallback, falls die Generierung fehlschlägt
        st.warning("Modell konnte nicht geladen werden.")
