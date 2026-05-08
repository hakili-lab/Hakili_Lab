import base64
import streamlit as st
from pathlib import Path

# Configuration page
st.set_page_config(
    page_title="Hakili Lab — Correction IA",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_hakili_logo() -> str:
    logo_path = Path(__file__).parent / "hakili_logo.png"
    if logo_path.exists():
        encoded = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return f'<img src="data:image/png;base64,{encoded}" alt="Hakili Lab logo" style="width: 90px; height: auto; object-fit: contain; display: block; margin: 0 auto;" />'
    return '<div style="font-size: 38px; line-height: 1;">🎓</div>'

# CSS personnalisé pour reproduire le design (couleurs bleu foncé + blanc)
st.markdown("""
<style>
    /* Import Google Fonts pour un look professionnel */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Variables CSS pour cohérence */
    :root {
        --primary-blue: #001F5C;
        --secondary-blue: #0F3A7D;
        --light-blue: #4A90E2;
        --accent-blue: #B0BED9;
        --white: #FFFFFF;
        --light-gray: #F8F9FA;
        --border-color: #E1E5E9;
        --shadow: 0 2px 10px rgba(0, 31, 92, 0.1);
        --border-radius: 8px;
    }
    
    /* Police globale */
    body, * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Animations fluides */
    * {
        transition: all 0.3s ease;
    }
    
    /* Sidebar markdown cleanup */
    [data-testid="stSidebar"] .stMarkdown {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Scroll fluide */
    html {
        scroll-behavior: smooth;
    }
    
    /* Sidebar couleur bleu foncé avec bordures */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        border-right: 3px solid var(--light-blue);
        box-shadow: var(--shadow);
    }
    
    /* Texte sidebar blanc */
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] p {
        color: var(--white) !important;
    }
    
    /* Navigation items avec bordures et hover */
    [data-testid="stSidebar"] [data-baseweb="radio"],
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        display: block;
        padding: 16px 18px;
        margin-bottom: 12px;
        border-radius: var(--border-radius);
        border: 1px solid rgba(255, 255, 255, 0.15);
        background: rgba(255, 255, 255, 0.08);
        color: var(--white) !important;
        transition: all 0.25s ease;
        cursor: pointer;
        min-height: 54px;
    }
    
    [data-testid="stSidebar"] [data-baseweb="radio"]:hover,
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255, 255, 255, 0.16);
        border-color: rgba(255, 255, 255, 0.35);
        transform: translateX(4px);
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label[aria-checked="true"],
    [data-testid="stSidebar"] div[role="radiogroup"] > label.st-bd {
        background: rgba(255, 255, 255, 0.2) !important;
        border-color: rgba(255, 255, 255, 0.45) !important;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.2);
    }
    
    [data-testid="stSidebar"] [data-baseweb="radio"] label,
    [data-testid="stSidebar"] div[role="radiogroup"] > label span {
        cursor: pointer;
        font-weight: 600;
        color: var(--white) !important;
    }
    
    /* Boutons avec bordures et animations */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        color: var(--white);
        border: 2px solid var(--light-blue);
        border-radius: var(--border-radius);
        padding: 12px 24px;
        font-weight: 600;
        font-size: 14px;
        box-shadow: var(--shadow);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--secondary-blue) 0%, var(--primary-blue) 100%);
        border-color: var(--accent-blue);
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0, 31, 92, 0.3);
    }
    
    .stButton > button:active {
        transform: translateY(0px);
    }
    
    /* Titres avec bordures élégantes */
    h1 {
        color: var(--primary-blue);
        border-bottom: 3px solid var(--light-blue);
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-weight: 700;
    }
    
    h2 {
        color: var(--primary-blue);
        border-left: 4px solid var(--light-blue);
        padding-left: 15px;
        margin: 30px 0 15px 0;
        font-weight: 600;
    }
    
    h3 {
        color: var(--secondary-blue);
        border-bottom: 2px solid var(--accent-blue);
        padding-bottom: 5px;
        margin-bottom: 15px;
        font-weight: 500;
    }
    
    /* Cartes avec bordures (désactivé pour supprimer les boîtes inutiles) */
    .stMarkdown {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* File uploaders avec bordures simplifiées */
    [data-testid="stFileUploader"] {
        border: 2px dashed rgba(0, 31, 92, 0.12);
        border-radius: var(--border-radius);
        padding: 18px;
        background: rgba(255, 255, 255, 0.95);
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: var(--light-blue);
        background: rgba(74, 144, 226, 0.05);
    }
    
    /* Text inputs avec bordures */
    [data-testid="stTextInput"] input {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 10px 15px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stTextInput"] input:focus {
        border-color: var(--light-blue);
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
    }
    
    /* Selectbox avec bordures */
    [data-testid="stSelectbox"] select {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 10px 15px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stSelectbox"] select:focus {
        border-color: var(--light-blue);
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
    }
    
    /* Date input avec bordures */
    [data-testid="stDateInput"] input {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 10px 15px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stDateInput"] input:focus {
        border-color: var(--light-blue);
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
    }
    
    /* Number input avec bordures */
    [data-testid="stNumberInput"] input {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 10px 15px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stNumberInput"] input:focus {
        border-color: var(--light-blue);
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
    }
    
    /* Messages d'info/erreur avec bordures */
    .stAlert {
        border-radius: var(--border-radius);
        border: 1px solid;
        box-shadow: var(--shadow);
    }
    
    /* Dividers élégants */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, var(--light-blue), var(--accent-blue), var(--light-blue));
        margin: 30px 0;
    }
    
    /* Animations d'entrée pour les éléments */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeInUp 0.6s ease-out;
    }
    
    /* Colonnes avec espacement */
    .stColumn {
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    # Logo HAKILI professionnel
    st.markdown(f"""
    <div style="text-align: center; padding: 20px 16px 12px 16px; margin-bottom: 18px; background: transparent; border-radius: var(--border-radius);">
        <div style="width: 80px; height: 80px; margin: 0 auto 10px auto; display: flex; align-items: center; justify-content: center; background: var(--white); border-radius: 18px; box-shadow: 0 10px 20px rgba(0,0,0,0.08);">
            {_render_hakili_logo()}
        </div>
        <h2 style="color: var(--white); margin: 0; font-weight: 700; font-size: 20px; letter-spacing: 0.04em;">HAKILI</h2>
        <p style="color: var(--accent-blue); font-size: 12px; margin: 8px 0 0 0; font-weight: 500;">Plateforme d'évaluation IA</p>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.radio(
        "**MENU**",
        options=["À PROPOS", "TRAITEMENT UNIQUE", "TRAITEMENT BATCH"],
        label_visibility="collapsed",
    )
    
    st.markdown("""
    <style>
        [data-testid="stSidebar"] > div:nth-child(3) {
            padding: 0;
            margin-top: 0;
            background: transparent;
            border: none;
        }
        [data-testid="stSidebar"] [data-baseweb="radio"],
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 14px 0 !important;
            margin: 0 0 10px 0 !important;
        }
        [data-testid="stSidebar"] .stRadio button {
            color: var(--white) !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ── PAGE 1 : À PROPOS ────────────────────────────────────────────────────────

if page == "À PROPOS":
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("À propos de la plateforme")
    
    st.markdown("""
    ## 🎯 Objectif
    **Hakili Lab** est une plateforme d'évaluation et de remédiation assistée par IA pour copies manuscrites
    de **mathématiques**.
    
    Notre mission : fournir aux enseignants du lycée une correction fiable, rapide et pédagogique.
    
    ---
    
    ## 🚀 Fonctionnalités principales
    
    ### 1️⃣ Transcription multimodale
    - Reconnaissance optique (OCR) des textes et formules manuscrites
    - Détection automatique de schémas et diagrammes
    - Signalement des zones illisibles ou ambiguës
    
    ### 2️⃣ Correction intelligent
    - Évaluation **0/1 (binaire)** selon le barème fourni
    - Calcul des scores question par question
    - Identification des réponses nécessitant une revue manuelle
    
    ### 3️⃣ Diagnostic pédagogique
    - Analyse des forces et lacunes de l'élève
    - Diagnostic par compétence (conceptuelle, méthodologique, calcul, rédaction)
    - Plan de remédiation personnalisé avec ressources recommandées
    
    ---
    
    ## 📋 Guide d'utilisation
    
    ### ✅ Avant de commencer
    1. **Préparez votre session** : rassemblez toutes les copies
    2. **Scannez ou photographiez** : une image par page, ou un PDF multi-pages
    3. **Préparez le barème** : énoncé + barème de notation
    4. **Vérifiez la qualité** : images nettes, bien alignées, bonne luminosité
    
    ### 🔄 Traitement Unique
    - Pour **1 copie** : téléchargez le PDF ou les images
    - Le système transcrit, corrige et produit un rapport PDF + JSON
    
    ### 📦 Traitement Batch
    - Pour **plusieurs copies** : organisez-les par élève
    - Traitez tout en une seule session
    - Export récapitulatif + correspondance anonyme
    
    ### ⚠️ Points importants
    - ✋ **Validation obligatoire** : l'IA n'est pas infaillible, un enseignant doit valider avant restitution
    - 🔒 **Confidentialité** : anonymisation par défaut, correspondance stockée séparément
    - 📊 **Confiance** : chaque score indique le niveau de confiance (0-100%)
    - 🏁 **Révision** : les items "low confidence" sont marqués pour révision manuelle
    
    ---
    
    ## 📊 Barème système
    Le système utilise un **barème binaire** :
    - **1 point** : réponse correcte complète selon les critères du barème
    - **0 point** : réponse absente, incomplète ou incorrecte
    
    Aucun demi-point, aucune pénalité double — respect strict du barème fourni.
    
    ---
    
    ## 🛠️ Support
    Pour toute question ou signalement d'erreur, contactez l'équipe Hakili Lab.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# ── PAGE 2 : TRAITEMENT UNIQUE ───────────────────────────────────────────────

elif page == "TRAITEMENT UNIQUE":
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("Traitement d'une copie unique")
    
    st.markdown("""
    Chargez une copie, l'énoncé et le barème. 
    Le système analysera, corrigera et générera un rapport complet.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📤 Fichiers d'entrée")
        
        copy_file = st.file_uploader(
            "Copie de l'élève",
            type=["pdf", "jpg", "jpeg", "png"],
            key="single_copy",
            help="PDF multi-pages ou image"
        )
        
        subject_file = st.file_uploader(
            "Énoncé",
            type=["pdf", "txt", "md", "jpg", "jpeg", "png"],
            key="single_subject",
            help="Texte ou image de l'énoncé"
        )
        
        rubric_file = st.file_uploader(
            "Barème de notation",
            type=["pdf", "txt", "md", "jpg", "jpeg", "png"],
            key="single_rubric",
            help="Points par question"
        )
    
    with col2:
        st.subheader("👤 Identité de l'élève")
        
        student_name = st.text_input(
            "Nom de l'élève",
            placeholder="Ex: Alice Dupont",
            help="Sera anonymisé avant traitement"
        )
        
        class_name = st.text_input(
            "Classe / Groupe",
            placeholder="Ex: 1A",
            help="Optionnel"
        )
        
        exam_date = st.date_input(
            "Date de l'examen",
            help="Optionnel"
        )
    
    st.divider()
    
    col_a, col_b, col_c = st.columns([1, 1, 2])
    
    with col_a:
        if st.button("🚀 Lancer l'analyse", use_container_width=True):
            if not copy_file or not subject_file or not rubric_file:
                st.error("⚠️ Veuillez charger : copie, énoncé et barème")
            elif not student_name:
                st.error("⚠️ Veuillez entrer le nom de l'élève")
            else:
                st.info("✅ Vérification des fichiers en cours...")
                st.success("📊 **Pipeline de traitement** :")
                st.markdown("""
                1. Ingestion et découpage des pages
                2. Contrôle qualité des images
                3. Transcription (OCR + formules)
                4. Correction selon barème
                5. Diagnostic pédagogique
                6. Génération PDF + JSON
                """)
    
    with col_c:
        st.info("""
        **État du système :** ⏳ Pipeline en développement
        
        Les résultats s'afficheront ici une fois l'analyse terminée.
        """)
    st.markdown('</div>', unsafe_allow_html=True)

# ── PAGE 3 : TRAITEMENT BATCH ────────────────────────────────────────────────

elif page == "TRAITEMENT BATCH":
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("Traitement batch — Plusieurs copies")
    
    st.markdown("""
    Traitez plusieurs copies en une seule session.
    Tous les résultats seront organisés et téléchargeables.
    """)
    
    st.subheader("📋 Configuration de la session")
    
    col1, col2 = st.columns(2)
    
    with col1:
        exam_name = st.text_input(
            "Nom du devoir / Examen",
            placeholder="Ex: Contrôle 1 - Algèbre",
            help="Utilisé pour organiser les fichiers de sortie"
        )
        
        st.markdown("**Matière :** Mathématiques")
        
        class_select = st.text_input(
            "Classe / Groupe",
            placeholder="Ex: 1A",
        )
    
    with col2:
        exam_date = st.date_input("Date de l'examen")
        
        num_students = st.number_input(
            "Nombre d'élèves attendus",
            min_value=1,
            max_value=500,
            value=30,
        )
    
    st.divider()
    
    st.subheader("📦 Fichiers d'entrée")
    
    col_x, col_y = st.columns(2)
    
    with col_x:
        st.markdown("**Fichiers de copies**")
        copies_folder = st.file_uploader(
            "Téléchargez les PDFs ou images",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="batch_copies",
            help="Une image par page ou un PDF par élève"
        )
        st.caption(f"📁 {len(copies_folder) if copies_folder else 0} fichier(s) chargé(s)")
    
    with col_y:
        st.markdown("**Fichiers d'énoncé et barème**")
        subject_file = st.file_uploader(
            "Énoncé",
            type=["pdf", "txt", "md", "jpg", "jpeg", "png"],
            key="batch_subject",
        )
        rubric_file = st.file_uploader(
            "Barème",
            type=["pdf", "txt", "md", "jpg", "jpeg", "png"],
            key="batch_rubric",
        )
    
    st.divider()
    
    col_p, col_q, col_r = st.columns([1, 1, 2])
    
    with col_p:
        if st.button("🚀 Lancer le traitement batch", use_container_width=True):
            if not copies_folder or not subject_file or not rubric_file:
                st.error("⚠️ Veuillez charger : copies, énoncé et barème")
            elif not exam_name:
                st.error("⚠️ Veuillez entrer le nom du devoir")
            else:
                st.info("✅ Vérification des fichiers en cours...")
                st.success(f"📊 **Session batch configurée** :")
                st.markdown(f"""
                - **Exam :** {exam_name}
                - **Matière :** Mathématiques
                - **Classe :** {class_select}
                - **Copies à traiter :** {len(copies_folder)} fichier(s)
                - **Élèves attendus :** {num_students}
                """)
    
    with col_r:
        st.info("""
        **État du système :** ⏳ Pipeline en développement
        
        Une fois terminé, vous recevrez :
        - 📊 Fichier récapitulatif (JSON)
        - 📄 Rapports individuels (PDF)
        - 🔐 Correspondance anonyme (CSV)
        """)
    st.markdown('</div>', unsafe_allow_html=True)
