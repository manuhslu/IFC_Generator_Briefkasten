import streamlit as st

# Definition der verfügbaren RAL-Farben mit ihren Hex-Codes
RAL_COLORS = {
    "RAL 9011 - Graphitschwarz": "#1C1C1E",
    "RAL 9006 - Weissaluminium": "#A1A1A0",
    "RAL 9016 - Verkehrsweiss": "#F1F1F1",
    "RAL 5005 - Signalblau": "#004E8A",
    "RAL 3000 - Feuerrot": "#BF242A",
    "RAL 1004 - Goldgelb": "#E2B007",
    "RAL 6010 - Grasgrün": "#49733F",
}

# Zuordnung von Farbnamen zu Emojis für eine visuelle Darstellung
COLOR_EMOJIS = {
    "RAL 9011 - Graphitschwarz": "⬛",
    "RAL 9006 - Weissaluminium": "⬜",
    "RAL 9016 - Verkehrsweiss": "⬜",
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