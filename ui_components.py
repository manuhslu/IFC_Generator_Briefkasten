import streamlit as st

# Definition der verfügbaren RAL-Farben mit ihren Hex-Codes
RAL_COLORS = {
    "Farblos eloxiert": "#C0C0C0",
    "RAL 9011 - Graphitschwarz": "#292C2F",
    "RAL 9016 - Verkehrsweiss": "#F7FBF5",
    "RAL 7016 - Anthrazitgrau": "#383E42",
    "RAL 7037 - Staubgrau": "#7A7B7A",
    "RAL 5005 - Signalblau": "#005387",
    "RAL 3000 - Feuerrot": "#A72920",
    "RAL 1004 - Goldgelb": "#E2B007",
    "RAL 6010 - Grasgrün": "#4D6F39",
}

# Zuordnung von Farbnamen zu Emojis für eine visuelle Darstellung
COLOR_EMOJIS = {
    "Farblos eloxiert": "⬜",
    "RAL 9011 - Graphitschwarz": "⬛",
    "RAL 9016 - Verkehrsweiss": "⬜",
    "RAL 7016 - Anthrazitgrau": "⬛",
    "RAL 7037 - Staubgrau": "⬛",
    "RAL 5005 - Signalblau": "🟦",
    "RAL 3000 - Feuerrot": "🟥",
    "RAL 1004 - Goldgelb": "🟨",
    "RAL 6010 - Grasgrün": "🟩",
}

def color_selector(default_color_hex: str) -> str:
    """
    Zeigt eine Auswahl von RAL-Farben mit st.radio an und gibt den gewählten Hex-Code zurück.
    Die Optionen enthalten jetzt ein farbiges Emoji-Quadrat zur besseren Visualisierung.
    """
    st.subheader("🎨 Farbauswahl")

    # Finde den Index der aktuell ausgewählten Farbe für die korrekte Vorauswahl.
    color_names = list(RAL_COLORS.keys())
    color_values = list(RAL_COLORS.values())
    try:
        default_index = color_values.index(default_color_hex)
    except ValueError:
        default_index = 0
    
    # Funktion zur Formatierung der Radio-Button-Beschriftungen mit Emojis
    def format_func(name):
        return f"{COLOR_EMOJIS.get(name, '■')} {name}"
        
    selected_color_name = st.radio(
        "Wähle eine Farbe",
        options=color_names,
        index=default_index,
        format_func=format_func,
        label_visibility="collapsed"
    )

    # Gib den Hex-Code der ausgewählten Farbe zurück
    return RAL_COLORS[selected_color_name]