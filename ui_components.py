import streamlit as st

# Definition der verfügbaren RAL-Farben mit ihren Hex-Codes
RAL_COLORS = {
    "Farblos eloxiert": "#C0C0C0",
    "RAL 9005 - Tiefschwarz": "#0E0E10",
    "RAL 9016 - Verkehrsweiss": "#F7FBF5",
    "RAL 7016 - Anthrazitgrau": "#383E42",
    "RAL 7037 - Nussbraun": "#5A3A29",
    "RAL 5005 - Signalblau": "#005387",
    "RAL 3000 - Feuerrot": "#A72920",
    "RAL 1004 - Goldgelb": "#E2B007",
    "RAL 6010 - Grasgrün": "#4D6F39",
}

# Zuordnung von Farbnamen zu Emojis für eine visuelle Darstellung
COLOR_EMOJIS = {
    "Farblos eloxiert": "⬜",
    "RAL 9005 - Tiefschwarz": "⬛",
    "RAL 9016 - Verkehrsweiss": "⬜",
    "RAL 7016 - Anthrazitgrau": "⬛",
    "RAL 7037 - Nussbraun": "🟫",
    "RAL 5005 - Signalblau": "🟦",
    "RAL 3000 - Feuerrot": "🟥",
    "RAL 1004 - Goldgelb": "🟨",
    "RAL 6010 - Grasgrün": "🟩",
}

def color_selector(key: str) -> str:
    """
    Zeigt eine Auswahl von RAL-Farben mit st.radio an und aktualisiert den Session-State-Key.
    Die Optionen enthalten jetzt ein farbiges Emoji-Quadrat zur besseren Visualisierung.
    Nutzt einen Callback, um den State sofort zu aktualisieren (verhindert "Double Click"-Problem).
    """
    st.subheader("Farbauswahl")
    
    # Aktuellen Wert aus Session State holen
    current_hex = st.session_state.get(key, "#C0C0C0")

    # Finde den Index der aktuell ausgewählten Farbe für die korrekte Vorauswahl.
    color_names = list(RAL_COLORS.keys())
    color_values = list(RAL_COLORS.values())
    try:
        default_index = color_values.index(current_hex)
    except ValueError:
        default_index = 0
    
    # Funktion zur Formatierung der Radio-Button-Beschriftungen mit Emojis
    def format_func(name):
        return f"{COLOR_EMOJIS.get(name, '■')} {name}"
        
    def on_change():
        # Widget-Key ist f"{key}_selection"
        selected_name = st.session_state[f"{key}_selection"]
        st.session_state[key] = RAL_COLORS[selected_name]
        
    st.radio(
        "Wähle eine Farbe",
        options=color_names,
        index=default_index,
        format_func=format_func,
        label_visibility="collapsed",
        key=f"{key}_selection",
        on_change=on_change
    )

    # Gib den Hex-Code von der ausgewählten Farbe zurück
    return st.session_state[key]