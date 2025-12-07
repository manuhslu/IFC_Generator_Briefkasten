import streamlit as st
import base64

from generate_mailbox_ifc import generate_mailbox_ifc
from ifc_to_glb import convert_ifc_to_glb
from ui_components import color_selector

st.set_page_config(page_title="Briefkasten-Konfigurator", layout="wide")
st.title("📬 Parametrischer Briefkasten-Konfigurator")

# --- Layout: Links Viewer, rechts Eingabe ---
col1, col2 = st.columns([2, 1])

@st.cache_data
def generate_and_convert_model(width, height, depth, color):
    """
    Generiert ein IFC-Modell, konvertiert es nach GLB und gibt die GLB-Daten als Bytes zurück.
    Streamlit's Caching verhindert die Neugenerierung bei gleichen Parametern.
    """
    st.info("Generiere neues Modell...")
    ifc_path = generate_mailbox_ifc(width=width, height=height, depth=depth, color_hex=color)
    if ifc_path:
        glb_path = convert_ifc_to_glb(ifc_path)
        if glb_path and glb_path.exists():
            with open(glb_path, "rb") as f:
                return f.read()
    st.error("Modell konnte nicht generiert oder konvertiert werden.")
    return None


# ---------- RECHTS: Eingaben ----------
with col2:
    st.subheader("⚙️ Eingabeparameter")

    breite = st.slider("Breite [m]", 0.2, 1.0, 0.4, 0.05)
    hoehe = st.slider("Höhe [m]", 0.2, 1.0, 0.3, 0.05)
    tiefe = st.slider("Tiefe [m]", 0.1, 0.5, 0.15, 0.05)
    st.markdown("---") # Visuelle Trennlinie

    # Verwende den neuen, benutzerdefinierten Farbwähler
    farbe = color_selector()

# ---------- LINKS: Viewer ----------
with col1:
    st.subheader("3D-Ansicht")

    # Generiere das Modell basierend auf den Eingaben
    glb_bytes = generate_and_convert_model(breite, hoehe, tiefe, farbe)

    if glb_bytes:
        b64 = base64.b64encode(glb_bytes).decode("ascii")
        data_url = f"data:model/gltf-binary;base64,{b64}"

        viewer_html = f"""
            <model-viewer
                src="{data_url}"
                camera-controls
                auto-rotate
                shadow-intensity="1"
                exposure="1.1"
                background-color="#ffffff"
                style="width:100%; height:600px;">
                <style>
                  model-viewer {{
                    --poster-color: transparent;
                  }}
                </style>
            </model-viewer>
            <script type="module" 
                    src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js">
            </script>
        """

        st.components.v1.html(viewer_html, height=620)
    else:
        st.warning("Kein Modell zum Anzeigen vorhanden. Bitte Parameter prüfen.")
