import streamlit as st
import base64
from typing import Optional, Tuple

from datetime import datetime
from pathlib import Path
from generate_mailbox_ifc import generate_mailbox_ifc
from ifc_to_glb import convert_ifc_to_glb
from ui_components import color_selector

st.set_page_config(page_title="Briefkasten-Konfigurator", layout="wide")
st.title("📬 Parametrischer Briefkasten-Konfigurator")

# --- Konstanten für Standardwerte ---
DEFAULT_BREITE = 0.4
DEFAULT_HOEHE = 0.3
DEFAULT_TIEFE = 0.15
DEFAULT_FARBE = "#A1A1A0" # RAL 9006 - Weissaluminium

@st.cache_data
def generate_and_convert_model(
    width: float, height: float, depth: float, color: str, rows: int, cols: int
) -> Optional[Tuple[bytes, bytes]]:
    """
    Generiert ein IFC-Modell, konvertiert es nach GLB und gibt die GLB- und IFC-Daten als Bytes zurück.
    Streamlit's Caching verhindert die Neugenerierung bei gleichen Parametern.
    """
    ifc_path = generate_mailbox_ifc(
        width=width, height=height, depth=depth, color=color, rows=rows, cols=cols
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

def get_model_viewer_html(data_url: str) -> str:
    """Erzeugt den HTML-Code für die <model-viewer>-Komponente."""
    return f"""
        <model-viewer
            src="{data_url}"
            camera-controls
            auto-rotate
            camera-orbit="180deg 75deg 105%"
            shadow-intensity="2"
            shadow-softness="0"
            environment-image="neutral"
            exposure="1.2"
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


# --- Session State Initialisierung ---
if 'step' not in st.session_state:
    st.session_state.step = "initial" # Zustand 1: Initialisierung
    st.session_state.breite = DEFAULT_BREITE
    st.session_state.hoehe = DEFAULT_HOEHE
    st.session_state.tiefe = DEFAULT_TIEFE
    st.session_state.farbe = DEFAULT_FARBE
    st.session_state.rows = 1
    st.session_state.cols = 1

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
        st.session_state.cols,
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
        st.session_state.cols = st.number_input("Anzahl Spalten", min_value=1, max_value=5, value=st.session_state.cols, step=1)
        st.session_state.rows = st.number_input("Anzahl Zeilen", min_value=1, max_value=5, value=st.session_state.rows, step=1)
        
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
            - **Anordnung:** `{st.session_state.rows}` Zeile(n), `{st.session_state.cols}` Spalte(n)
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

    # Zeigt das Modell nur an, wenn es im Session State vorhanden ist
    if glb_bytes:
        b64 = base64.b64encode(glb_bytes).decode("ascii")
        data_url = f"data:model/gltf-binary;base64,{b64}"

        viewer_html = get_model_viewer_html(data_url)
        st.components.v1.html(viewer_html, height=620)
    else:
        # Fallback, falls die Generierung fehlschlägt
        st.warning("Modell konnte nicht geladen werden.")
