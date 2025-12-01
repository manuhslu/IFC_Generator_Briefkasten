import streamlit as st
import base64
from pathlib import Path
import time

from generate_mailbox_ifc import generate_mailbox_ifc
from ifc_to_glb import convert_ifc_to_glb

st.set_page_config(page_title="Briefkasten-Konfigurator", layout="wide")
st.title("📬 Parametrischer Briefkasten-Konfigurator")

# --- Layout: Links Viewer, rechts Eingabe ---
col1, col2 = st.columns([2, 1])

# ---------- RECHTS: Eingaben ----------
with col2:
    st.subheader("⚙️ Eingabeparameter")

    breite = st.slider("Breite [m]", 0.2, 1.0, 0.4, 0.05)
    hoehe = st.slider("Höhe [m]", 0.2, 1.0, 0.3, 0.05)
    tiefe = st.slider("Tiefe [m]", 0.1, 0.5, 0.15, 0.05)
    farbe = st.color_picker("Farbe wählen", "#aaaaaa")

    # 👉 Hier könnte dein IFC/GLB-Generator aufgerufen werden:
    # generate_mailbox_ifc(width=breite, height=hoehe, depth=tiefe, color=farbe)
    #
    # In dieser Testversion simulieren wir nur eine kurze Pause:
    time.sleep(0.3)

# ---------- LINKS: Viewer ----------
with col1:
    st.subheader("3D-Ansicht")

    model_path = Path("models/briefkasten.glb")

    if not model_path.exists():
        st.error(f"⚠️ Datei nicht gefunden: {model_path.resolve()}")
    else:
        with open(model_path, "rb") as f:
            glb_bytes = f.read()
        b64 = base64.b64encode(glb_bytes).decode("ascii")
        data_url = f"data:model/gltf-binary;base64,{b64}"

        # 🔁 Cache-Buster mit Parametern – zwingt Streamlit zum Neuladen
        key = f"{breite}-{hoehe}-{tiefe}-{farbe}"

        viewer_html = f"""
            <model-viewer
                key="{key}"
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
