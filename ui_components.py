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

def color_selector():
    """
    Zeigt eine klickbare Auswahl von RAL-Farben an und gibt den gewählten Hex-Code zurück.
    
    Verwendet HTML und CSS in st.markdown, um farbige Quadrate als Buttons darzustellen.
    Die Auswahl wird über st.radio im Hintergrund gesteuert.
    """
    st.subheader("🎨 Farbauswahl")

    # Erstelle eine visuelle Darstellung mit HTML/CSS
    color_html = ""
    for name, hex_code in RAL_COLORS.items():
        color_html += f"""
        <div style="display: inline-block; margin: 5px; text-align: center;">
            <div style="width: 50px; height: 50px; background-color: {hex_code}; border: 1px solid #ccc; border-radius: 5px;"></div>
            <small style="display: block; margin-top: 5px;">{name.split(' - ')[0]}</small>
        </div>
        """
    
    # Unsichtbares Radio-Button-Set zur Steuerung der Auswahl
    selected_color_name = st.radio(
        "Wähle eine Farbe",
        options=list(RAL_COLORS.keys()),
        index=1,  # Standardauswahl ist Weissaluminium
        label_visibility="collapsed", # Versteckt das Label "Wähle eine Farbe"
        format_func=lambda name: name.split(' - ')[1] # Zeigt nur den Farbnamen an
    )

    # Zeige die visuellen Farb-Boxen an
    st.markdown(f"<div style='display: flex; flex-wrap: wrap;'>{color_html}</div>", unsafe_allow_html=True)
    st.markdown("---") # Trennlinie

    # Gib den Hex-Code der ausgewählten Farbe zurück
    return RAL_COLORS[selected_color_name]