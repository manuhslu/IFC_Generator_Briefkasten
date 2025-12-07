import streamlit as st

# Definition der verfügbaren RAL-Farben mit ihren Hex-Codes
RAL_COLORS = {
    "RAL 9004 - Signalschwarz": "#2A2B2D",
    "RAL 9006 - Weissaluminium": "#A1A1A0",
    "RAL 9011 - Graphitschwarz": "#1C1C1E",
    "RAL 9016 - Verkehrsweiß": "#F1F1F1",
    "RAL 5005 - Signalblau": "#004E8A",
    "RAL 3000 - Feuerrot": "#BF242A",
}

def color_selector(default_color_hex: str) -> str:
    """
    Zeigt eine Auswahl von RAL-Farben mit st.radio an und gibt den gewählten Hex-Code zurück.
    Der Zustand wird korrekt über den `default_color_hex` Parameter verwaltet.
    """
    st.subheader("🎨 Farbauswahl")

    # Finde den Index der aktuell ausgewählten Farbe für die korrekte Vorauswahl.
    # Falls die Farbe nicht gefunden wird, nimm den ersten Eintrag als Fallback.
    color_names = list(RAL_COLORS.keys())
    color_values = list(RAL_COLORS.values())
    try:
        default_index = color_values.index(default_color_hex)
    except ValueError:
        default_index = 0

    selected_color_name = st.radio(
        "Wähle eine Farbe",
        options=color_names,
        index=default_index,
        label_visibility="collapsed"
    )

    # Gib den Hex-Code der ausgewählten Farbe zurück
    return RAL_COLORS[selected_color_name]