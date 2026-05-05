import streamlit as st

st.set_page_config(page_title="Hakili Lab AI Correction", layout="wide")
st.title("Hakili Lab — Correction assistée par IA")
st.warning("Prototype : validation humaine obligatoire avant restitution officielle.")

copy_files = st.file_uploader("Copie de l'élève — PDF/JPG/PNG", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)
subject_file = st.file_uploader("Énoncé", type=["pdf", "txt", "md", "jpg", "jpeg", "png"])
rubric_file = st.file_uploader("Barème", type=["pdf", "txt", "md", "jpg", "jpeg", "png"])

if st.button("Lancer l'analyse"):
    if not copy_files or subject_file is None or rubric_file is None:
        st.error("Ajoute la copie, l'énoncé et le barème.")
    else:
        st.info("Pipeline à connecter : ingestion → qualité image → transcription → correction → diagnostic → PDF/JSON.")
