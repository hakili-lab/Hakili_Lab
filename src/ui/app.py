import base64
import sys
import tempfile
from pathlib import Path

# Assure que la racine du projet est dans le path (nécessaire sur Windows)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Hakili Lab — Correction IA",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _logo_html(size: int = 40) -> str:
    logo_path = Path(__file__).parent / "hakili_logo.png"
    if logo_path.exists():
        encoded = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return (
            f'<img src="data:image/png;base64,{encoded}" '
            f'style="width:{size}px;height:{size}px;object-fit:contain;display:block;" />'
        )
    return f'<span style="font-size:{size // 2}px;line-height:1;">🎓</span>'


# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body { font-family: 'Inter', sans-serif !important; }
* { font-family: inherit; }

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

.block-container {
    padding-top: 0 !important;
    padding-left: 32px !important;
    padding-right: 32px !important;
    max-width: 100% !important;
}

/* ── Sidebar ───────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: #001e4a !important;
}
[data-testid="stSidebarContent"] { background-color: #001e4a !important; }
[data-testid="stSidebar"] .stMarkdown {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

.stRadio > label {
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 1.6px !important;
    color: #ffffff !important;
    text-transform: uppercase !important;
    padding: 0 14px !important;
    margin-bottom: 4px !important;
}
.stRadio > div { gap: 1px !important; padding: 0 8px !important; }
.stRadio > div > label {
    padding: 9px 10px !important;
    border-radius: 4px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: #ffffff !important;
    cursor: pointer !important;
    border: none !important;
    transition: background 0.12s, color 0.12s !important;
    letter-spacing: 0.2px !important;
}
.stRadio > div > label:hover {
    background: rgba(255,255,255,0.07) !important;
    color: #ffffff !important;
}
.stRadio > div > label:has(input:checked) {
    background: rgba(255,255,255,0.11) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stRadio > div > label p,
[data-testid="stSidebar"] .stRadio > div > label span,
[data-testid="stSidebar"] .stRadio > div > label div {
    color: #ffffff !important;
}
.stRadio > div > label > div:first-child {
    border-color: #4d6d97 !important;
}
.stRadio > div > label:has(input:checked) > div:first-child {
    background-color: #4a90e2 !important;
    border-color: #4a90e2 !important;
}

/* ── En-tête de page ───────────────────────────────────────────────── */
.pheader {
    background: #ffffff;
    border-bottom: 1.5px solid #dde6f5;
    padding: 13px 0 13px 0;
    margin: 0 -32px 26px -32px;
    padding-left: 32px;
    padding-right: 32px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.pheader-title {
    font-size: 14px;
    font-weight: 700;
    color: #001e4a;
    line-height: 1.2;
}
.pheader-sub {
    font-size: 10px;
    color: #7090b8;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    margin-top: 2px;
}
.pheader-badge {
    margin-left: auto;
    font-size: 10.5px;
    color: #5a7aa8;
    background: #f2f6fc;
    border: 1px solid #d8e4f2;
    padding: 3px 11px;
    border-radius: 20px;
    font-weight: 500;
    white-space: nowrap;
}

/* ── Typographie ───────────────────────────────────────────────────── */
h1 {
    color: #001e4a !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    border-bottom: 1.5px solid #dde6f5;
    padding-bottom: 8px;
    margin-bottom: 14px !important;
}
h2 {
    color: #001e4a !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    margin-top: 20px !important;
    margin-bottom: 8px !important;
}
h3 {
    color: #2d5a8e !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}
h4 {
    color: #001e4a !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    margin-top: 16px !important;
    margin-bottom: 6px !important;
}
p, .stMarkdown p { font-size: 13px !important; color: #2c3e50 !important; line-height: 1.6 !important; }

/* ── Formulaires ───────────────────────────────────────────────────── */
.stTextInput label, .stTextArea label, .stFileUploader label,
.stDateInput label, .stNumberInput label, .stSelectbox label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #3d5a7a !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
}
.stTextInput input, .stTextArea textarea {
    border: 1px solid #d4dff0 !important;
    border-radius: 5px !important;
    font-size: 13px !important;
    background: #fafcff !important;
    color: #1a2a40 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #4a90e2 !important;
    box-shadow: 0 0 0 2px rgba(74,144,226,0.10) !important;
}

/* ── Boutons ───────────────────────────────────────────────────────── */
.stButton > button {
    background: #001e4a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 5px !important;
    padding: 9px 22px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.2px !important;
    transition: background 0.15s !important;
}
.stButton > button p,
.stButton > button span,
.stButton > button div { color: #ffffff !important; }
.stButton > button:hover { background: #003070 !important; }

.stDownloadButton > button {
    background: #f4f7fc !important;
    color: #001e4a !important;
    border: 1px solid #c8d8ee !important;
    border-radius: 5px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 7px 16px !important;
}
.stDownloadButton > button:hover {
    background: #e6edf8 !important;
    border-color: #4a90e2 !important;
}

/* ── Métriques ─────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #f7fafd !important;
    border: 1px solid #dde8f5 !important;
    border-radius: 6px !important;
    padding: 14px 18px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    font-weight: 700 !important;
    color: #6b87a8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #001e4a !important;
}

/* ── Expanders ─────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #f7fafd !important;
    border: 1px solid #dde8f5 !important;
    border-radius: 5px !important;
}

/* ── Uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: #f7fafd !important;
    border: 1.5px dashed #c0d2e8 !important;
    border-radius: 6px !important;
    padding: 12px !important;
}

/* ── Tableau ───────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #dde8f5 !important;
    border-radius: 6px !important;
    overflow: hidden !important;
}

/* ── Divider ───────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #dde8f5 !important;
    margin: 18px 0 !important;
}

/* ── Progress bar ──────────────────────────────────────────────────── */
.stProgress > div > div > div { background-color: #001e4a !important; }

/* ── Alertes ───────────────────────────────────────────────────────── */
.stAlert { border-radius: 5px !important; }

/* ── Caption / small ───────────────────────────────────────────────── */
.stCaption, caption { font-size: 11px !important; color: #7090b8 !important; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="padding:18px 14px 14px 14px;border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:14px;">
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:40px;height:40px;flex-shrink:0;background:rgba(255,255,255,0.08);
                        border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                {_logo_html(34)}
            </div>
            <div>
                <div style="font-size:14px;font-weight:700;color:#ffffff;letter-spacing:0.4px;">HAKILI LAB</div>
                <div style="font-size:10px;color:#7a9fc8;margin-top:2px;font-weight:400;">Évaluation IA · Maths 6e à la Tle</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "MENU",
        options=["À PROPOS", "TRAITEMENT UNIQUE", "TRAITEMENT BATCH"],
    )



# ── Helpers ───────────────────────────────────────────────────────────────────

def _page_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="pheader-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div class="pheader">
        <div style="width:38px;height:38px;flex-shrink:0;background:#f0f5fc;border-radius:6px;
                    display:flex;align-items:center;justify-content:center;overflow:hidden;">
            {_logo_html(30)}
        </div>
        <div>
            <div class="pheader-title">{title}</div>
            {sub}
        </div>
        <div class="pheader-badge">Maths · 6e → Tle · Barème 0/1</div>
    </div>
    """, unsafe_allow_html=True)


def _save_upload(uploaded_file, dest: Path) -> Path:
    dest.write_bytes(uploaded_file.read())
    return dest


def _parse_rubric_text(rubric_text: str):
    import json as _json
    from src.models.domain import Rubric, RubricItem
    rubric_text = rubric_text.strip()
    if not rubric_text:
        return Rubric(subject="mathematics", total_points=0, items=[])
    if rubric_text.startswith("{"):
        data = _json.loads(rubric_text)
        return Rubric(**data)
    items = []
    for i, line in enumerate(rubric_text.splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 1)
        qid = parts[0].strip() if len(parts) > 1 else f"Q{i+1}"
        label = parts[1].strip() if len(parts) > 1 else line
        items.append(RubricItem(id=qid, label=label))
    return Rubric(subject="mathematics", total_points=len(items), items=items)


def _display_results(result, key_prefix: str = "") -> None:
    if not result.success:
        st.error(f"Pipeline échoué : {'; '.join(result.errors)}")
        return

    grade = result.grade
    student_label = result.student_name or result.copy_id
    st.success(f"Correction terminée — **{student_label}** : **{grade.total_score}/{grade.total_possible}**")

    if result.quality.global_quality == "poor":
        st.warning("Qualité image insuffisante — vérifiez les pages signalées.")

    # Alertes orchestrateur
    auto_fixes = [i for i in result.validation_issues if i.auto_fixed]
    warnings = [i for i in result.validation_issues if not i.auto_fixed and i.severity == "warning"]
    if auto_fixes:
        with st.expander(f"Orchestrateur — {len(auto_fixes)} correction(s) automatique(s)"):
            for issue in auto_fixes:
                st.caption(f"✓ [{issue.code}] {issue.message}")
    if warnings:
        with st.expander(f"Orchestrateur — {len(warnings)} avertissement(s) à vérifier"):
            for issue in warnings:
                st.warning(f"[{issue.code}] {issue.message}")

    avg_conf = (
        sum(q.confidence for q in grade.questions) / len(grade.questions)
        if grade.questions else 0.0
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Note", f"{grade.total_score} / {grade.total_possible}")
    col2.metric("Confiance IA", f"{avg_conf:.0%}")
    col3.metric("Révisions requises", sum(1 for q in grade.questions if q.requires_review))

    st.markdown("#### Détail par question")
    for q in grade.questions:
        icon = "✓" if q.score == 1 else "✗"
        review_tag = " · Révision requise" if q.requires_review else ""
        with st.expander(f"{icon}  {q.rubric_item_id} — {q.score}/1  (confiance {q.confidence:.0%}){review_tag}"):
            st.markdown(f"**Réponse observée :** {q.observed_answer}")
            st.markdown(f"**Commentaire :** {q.comment}")

    if result.diagnostic:
        diag = result.diagnostic
        st.markdown("#### Diagnostic pédagogique")
        c1, c2 = st.columns(2)
        with c1:
            if diag.strengths:
                st.markdown("**Forces**")
                for s in diag.strengths:
                    st.markdown(f"- {s}")
        with c2:
            if diag.weaknesses:
                st.markdown("**Lacunes**")
                for w in diag.weaknesses:
                    st.markdown(f"- {w}")

        if diag.root_causes:
            st.markdown("#### Erreurs cachées identifiées")
            st.caption(
                "Ces causes profondes expliquent plusieurs points perdus — "
                "les corriger améliore la copie sur plusieurs questions à la fois."
            )
            for rc in diag.root_causes:
                qs = ", ".join(rc.linked_questions) if rc.linked_questions else "—"
                with st.expander(f"Questions {qs} — {rc.visible_error}"):
                    st.markdown(f"**Cause cachée :** {rc.hidden_cause}")

        if diag.competency_gaps:
            st.markdown("#### Compétences non maîtrisées (programme officiel)")
            st.caption(
                "Compétences extraites du programme du Ministère de l'Éducation du Burkina Faso, "
                "identifiées sur la base des questions échouées et du barème Hakili."
            )
            for gap in diag.competency_gaps:
                badge = f"{gap.classe} · {gap.domaine.capitalize()}"
                with st.expander(f"[{gap.chunk_id}]  {gap.chapitre} — {gap.lecon}"):
                    st.markdown(f"**Niveau :** {badge}")
                    if gap.savoir_faire:
                        st.markdown("**Savoir-faire à retravailler :**")
                        for sf in gap.savoir_faire:
                            st.markdown(f"- {sf}")
                    if gap.erreurs_frequentes:
                        st.markdown("**Erreurs fréquentes associées :**")
                        for ef in gap.erreurs_frequentes:
                            st.caption(f"⚠ {ef}")

        if diag.remediation_plan:
            st.markdown("#### Plan de remédiation")
            for item in sorted(diag.remediation_plan, key=lambda x: x.priority):
                st.markdown(f"{item.priority}. **{item.topic}** — {item.action}")

    if result.remediation_subject and result.remediation_subject.exercises:
        st.markdown("#### Sujet de remédiation (exercices)")
        st.caption("5 exercices progressifs par lacune identifiée — inclus dans le rapport PDF.")
        current_topic = None
        for ex in result.remediation_subject.exercises:
            if ex.topic != current_topic:
                current_topic = ex.topic
                st.markdown(f"**Série : {ex.topic}**")
            with st.expander(f"Exercice {ex.number}"):
                st.markdown(ex.question)
                if ex.hint:
                    st.caption(f"Aide : {ex.hint}")

    # ── Téléchargements ───────────────────────────────────────────────────────
    st.markdown("#### Téléchargements")
    kid = key_prefix or result.copy_id
    name_slug = (
        result.student_name.lower().replace(" ", "_").replace("'", "").replace("/", "")
        if result.student_name else result.copy_id
    )
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if result.pdf_path and result.pdf_path.exists():
            st.download_button(
                "Rapport de correction (enseignant)",
                data=result.pdf_path.read_bytes(),
                file_name=f"rapport_correction_{name_slug}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{kid}",
                use_container_width=True,
            )
    with col_dl2:
        if result.remediation_pdf_path and result.remediation_pdf_path.exists():
            st.download_button(
                "Sujet de remédiation (élève)",
                data=result.remediation_pdf_path.read_bytes(),
                file_name=f"sujet_remediation_{name_slug}.pdf",
                mime="application/pdf",
                key=f"dl_rem_{kid}",
                use_container_width=True,
            )
        elif not (result.remediation_subject and result.remediation_subject.exercises):
            st.caption("Sujet de remédiation non disponible (diagnostic insuffisant)")


# ── PAGE : À PROPOS ───────────────────────────────────────────────────────────

if page == "À PROPOS":
    _page_header("À propos de la plateforme", "Hakili Lab · Correction IA")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("## Objectif")
        st.markdown(
            "**Hakili Lab** est une plateforme d'évaluation et de remédiation assistée par IA "
            "pour copies manuscrites de **mathématiques**, conçue pour le programme "
            "du secondaire au Burkina Faso (**6e à la Terminale**). "
            "Elle fournit aux enseignants une correction fiable, rapide et pédagogique."
        )

        st.divider()
        st.markdown("## Fonctionnalités")

        items = [
            ("Transcription multimodale", "Reconnaissance des textes, formules et schémas manuscrits. Signalement des zones ambiguës."),
            ("Correction intelligente", "Évaluation binaire 0/1 par question et sous-question selon le barème fourni."),
            ("Barème flexible", "Saisie manuelle, JSON, ou import direct d'un PDF/image du barème — extraction automatique par IA."),
            ("Instructions expert", "Critères contextuels optionnels injectés dans le prompt pour affiner la précision."),
            ("Diagnostic pédagogique", "Analyse des forces et lacunes · Plan de remédiation personnalisé."),
        ]
        for title, desc in items:
            st.markdown(f"**{title}**")
            st.caption(desc)
            st.markdown("")

    with col_right:
        st.markdown("## Barème")
        st.markdown(
            "Le système applique un **barème binaire strict** :\n\n"
            "- **1 pt** — réponse correcte complète\n"
            "- **0 pt** — absente, incomplète ou incorrecte\n\n"
            "Chaque sous-question est un item indépendant. "
            "Aucun demi-point."
        )

        st.divider()
        st.markdown("## Modes disponibles")

        st.markdown(
            "**Copie Unique** — Traitement immédiat d'une seule copie, "
            "résultat affiché et téléchargeable.\n\n"
            "**Batch** — Session multi-élèves avec synthèse de classe "
            "et téléchargement individuel par copie."
        )

        st.divider()
        st.markdown("## Validation")
        st.caption(
            "La validation finale se fait hors plateforme, par l'enseignant "
            "directement sur le rapport PDF exporté."
        )


# ── PAGE : TRAITEMENT UNIQUE ──────────────────────────────────────────────────

elif page == "TRAITEMENT UNIQUE":
    _page_header("Traitement d'une copie unique", "Analyse · Correction · Rapport")

    if "single_result" not in st.session_state:
        st.session_state.single_result = None

    from src.knowledge.test_registry import get_registry as _get_registry

    # ── Sélection du mode ─────────────────────────────────────────────────────
    _registry = _get_registry()
    _available = _registry.available_tests()

    _MODE_OPTIONS = ["Mode libre (barème + énoncé manuels)"] + [
        f"Test Hakili : {t.label}" for t in _available.values()
    ]
    _MODE_IDS = [""] + list(_available.keys())

    selected_mode_label = st.selectbox(
        "Mode de correction",
        options=_MODE_OPTIONS,
        help=(
            "Mode Hakili : l'énoncé et le barème sont chargés automatiquement. "
            "Il suffit d'uploader la copie de l'élève. "
            "Mode libre : chargez votre propre énoncé et barème."
        ),
    )
    selected_mode_idx = _MODE_OPTIONS.index(selected_mode_label)
    bareme_id_single = _MODE_IDS[selected_mode_idx]
    hakili_test = _registry.get_test(bareme_id_single) if bareme_id_single else None

    # Pré-chargement du retriever RAG dès la sélection du test (singleton — ne charge qu'une fois)
    if hakili_test:
        from src.pipeline.pipeline import _get_retriever as _prewarm_retriever
        _prewarm_retriever()

    # Bandeau d'info quand un test Hakili est sélectionné
    if hakili_test:
        st.markdown(
            f"""<div style="background:#eef6ff;border:1px solid #b8d4f5;border-radius:6px;
                padding:12px 16px;margin-bottom:16px;font-size:13px;color:#1a3a5c;">
            <strong>{hakili_test.label}</strong><br>
            <span style="color:#5a7aa8;font-size:12px;">
                {hakili_test.description} · Niveaux : {hakili_test.niveaux} ·
                <strong>{hakili_test.total_questions} questions</strong>
            </span><br>
            <span style="color:#2d7a2d;font-size:11.5px;margin-top:4px;display:block;">
                ✓ Énoncé chargé automatiquement &nbsp;·&nbsp;
                ✓ Barème {hakili_test.total_questions} questions pré-chargé &nbsp;·&nbsp;
                ✓ Diagnostic RAG activé
            </span>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    col_input, col_config = st.columns(2, gap="large")

    with col_input:
        st.markdown("#### Copie de l'élève")
        copy_files = st.file_uploader(
            "Copie de l'élève",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="single_copy",
            help="1 PDF multi-pages OU plusieurs photos (JPG/PNG) dans l'ordre des pages — jusqu'à 20 images.",
        )
        if copy_files:
            n = len(copy_files)
            if n == 1:
                st.caption(f"1 fichier chargé — {copy_files[0].name}")
            else:
                st.caption(f"{n} photos chargées — vérifiez qu'elles sont dans le bon ordre (page 1, 2…)")

        # Énoncé et barème : affichés seulement en mode libre
        if not hakili_test:
            st.markdown("#### Fichiers optionnels")
            subject_file = st.file_uploader(
                "Énoncé (optionnel)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="single_subject",
                help="PDF ou image de l'énoncé.",
            )
            st.markdown("**Barème (optionnel)**")
            rubric_file = st.file_uploader(
                "Importer le barème (PDF ou image)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="single_rubric_file",
                help="Joignez le document barème — l'IA en extraira automatiquement les items.",
            )
        else:
            subject_file = None
            rubric_file = None

    with col_config:
        st.markdown("#### Instructions expert")
        expert_instructions = st.text_area(
            "Critères d'interprétation spécifiques (optionnel)",
            height=130,
            placeholder=(
                "Ex : Pour Q2b, accepter x = 0 même si la justification est absente. "
                "Ne pas pénaliser les fautes d'orthographe."
            ),
            help="Injectées dans le prompt de correction.",
        )
        if not hakili_test:
            st.caption(
                "En mode libre, vous pouvez aussi saisir le barème manuellement ci-dessous."
            )
            rubric_text = st.text_area(
                "Barème texte (optionnel — une question par ligne : ID: intitulé)",
                height=80,
                placeholder="Q1: Calculer l'expression\nQ2a: Résoudre l'équation\nQ2b: Vérifier la solution",
            )
        else:
            rubric_text = ""

    st.divider()

    if st.button("Lancer l'analyse", use_container_width=False):
        if not copy_files:
            st.error("Veuillez charger la copie de l'élève (PDF ou photo(s)).")
        elif len(copy_files) > 1 and any(f.name.lower().endswith(".pdf") for f in copy_files):
            st.error("Impossible de mélanger un PDF avec des images. Chargez soit 1 PDF, soit plusieurs images.")
        else:
            st.session_state.single_result = None
            try:
                from src.core.anonymizer import make_copy_id
                from src.core.config import settings
                from src.pipeline.pipeline import run_single_copy
                from src.ui.progress import PipelineProgressUI

                runs_dir = Path(settings.runs_dir)
                student_name = (
                    Path(copy_files[0].name).stem.replace("_", " ").replace("-", " ").title()
                )
                copy_id = make_copy_id(student_name)

                # Barème + énoncé : pré-chargés (test Hakili) ou manuels (mode libre)
                if hakili_test:
                    rubric = hakili_test.rubric
                    subject_text_val = hakili_test.subject_text
                    rubric_file_path = None
                    subject_file_path = None
                else:
                    rubric = _parse_rubric_text(rubric_text)
                    subject_text_val = ""
                    subject_file_path = None
                    rubric_file_path = None

                # Récupère le logo encodé pour l'affichage de la progression
                _logo_path = Path(__file__).parent / "hakili_logo.png"
                _logo_b64 = (
                    base64.b64encode(_logo_path.read_bytes()).decode("utf-8")
                    if _logo_path.exists() else ""
                )

                st.divider()
                progress_ui = PipelineProgressUI(
                    logo_b64=_logo_b64,
                    test_label=hakili_test.label if hakili_test else "Correction libre",
                    student_name=student_name,
                )

                with tempfile.TemporaryDirectory() as tmp:
                    saved_paths: list[Path] = []
                    for uf in copy_files:
                        p = Path(tmp) / uf.name
                        _save_upload(uf, p)
                        saved_paths.append(p)

                    if not hakili_test:
                        if subject_file:
                            subject_tmp = Path(tmp) / f"subject_{subject_file.name}"
                            _save_upload(subject_file, subject_tmp)
                            subject_file_path = subject_tmp
                        if rubric_file:
                            rubric_tmp = Path(tmp) / f"rubric_{rubric_file.name}"
                            _save_upload(rubric_file, rubric_tmp)
                            rubric_file_path = rubric_tmp

                    result = run_single_copy(
                        copy_id=copy_id,
                        student_name=student_name,
                        file_paths=saved_paths,
                        rubric=rubric,
                        rubric_file_path=rubric_file_path,
                        subject_text=subject_text_val,
                        subject_file_path=subject_file_path,
                        expert_instructions=expert_instructions,
                        bareme_id=bareme_id_single,
                        official_answers=hakili_test.official_answers if hakili_test else "",
                        runs_dir=runs_dir,
                        on_progress=progress_ui.update,
                    )

                progress_ui.finish()
                st.session_state.single_result = result

            except Exception as e:
                st.error(f"Erreur inattendue : {e}")

    if st.session_state.single_result is not None:
        st.divider()
        _display_results(st.session_state.single_result)


# ── PAGE : TRAITEMENT BATCH ───────────────────────────────────────────────────

elif page == "TRAITEMENT BATCH":
    _page_header("Traitement batch", "Session multi-élèves · Synthèse de classe")

    if "batch_results" not in st.session_state:
        st.session_state.batch_results = None
    if "batch_errors" not in st.session_state:
        st.session_state.batch_errors = []

    from src.knowledge.test_registry import get_registry as _get_registry_batch
    _registry_batch = _get_registry_batch()
    _available_batch = _registry_batch.available_tests()

    # ── Sélection du mode batch ───────────────────────────────────────────────
    _MODE_OPTIONS_BATCH = ["Mode libre (barème + énoncé manuels)"] + [
        f"Test Hakili : {t.label}" for t in _available_batch.values()
    ]
    _MODE_IDS_BATCH = [""] + list(_available_batch.keys())

    selected_mode_label_batch = st.selectbox(
        "Mode de correction",
        options=_MODE_OPTIONS_BATCH,
        key="batch_mode_select",
        help="Mode Hakili : énoncé et barème chargés automatiquement pour toutes les copies.",
    )
    selected_mode_idx_batch = _MODE_OPTIONS_BATCH.index(selected_mode_label_batch)
    bareme_id_batch = _MODE_IDS_BATCH[selected_mode_idx_batch]
    hakili_test_batch = _registry_batch.get_test(bareme_id_batch) if bareme_id_batch else None

    if hakili_test_batch:
        from src.pipeline.pipeline import _get_retriever as _prewarm_retriever_batch
        _prewarm_retriever_batch()

    if hakili_test_batch:
        st.markdown(
            f"""<div style="background:#eef6ff;border:1px solid #b8d4f5;border-radius:6px;
                padding:12px 16px;margin-bottom:12px;font-size:13px;color:#1a3a5c;">
            <strong>{hakili_test_batch.label}</strong> · {hakili_test_batch.niveaux}
            · <strong>{hakili_test_batch.total_questions} questions</strong><br>
            <span style="color:#2d7a2d;font-size:11.5px;">
                ✓ Énoncé pré-chargé &nbsp;·&nbsp; ✓ Barème pré-chargé &nbsp;·&nbsp;
                ✓ Diagnostic RAG activé pour toutes les copies
            </span>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        exam_name = st.text_input(
            "Nom du devoir / Examen",
            placeholder="Ex : Session recrutement Juin 2026",
        )
        class_select = st.text_input(
            "Classe / Groupe",
            placeholder="Ex : Groupe 1  |  Groupe A",
        )
    with col_b:
        exam_date = st.date_input("Date de l'examen")
        num_students = st.number_input("Nombre d'élèves attendus", min_value=1, max_value=500, value=30)

    st.divider()

    # Fichiers communs : seulement en mode libre
    if not hakili_test_batch:
        st.markdown("#### Fichiers communs (mode libre)")
        col_x, col_y = st.columns(2, gap="large")
        with col_x:
            subject_file_batch = st.file_uploader(
                "Énoncé (optionnel)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="batch_subject",
                help="PDF ou image de l'énoncé commun à toutes les copies.",
            )
            rubric_file_batch = st.file_uploader(
                "Barème (optionnel)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="batch_rubric_file",
                help="Joignez le document barème.",
            )
        with col_y:
            expert_instructions_batch = st.text_area(
                "Instructions expert (optionnel)",
                height=120,
                placeholder="Critères d'interprétation spécifiques à ce devoir…",
            )
        st.divider()
    else:
        subject_file_batch = None
        rubric_file_batch = None
        expert_instructions_batch = st.text_area(
            "Instructions expert (optionnel)",
            height=80,
            placeholder="Critères d'interprétation spécifiques à ce devoir…",
        )
        st.divider()

    st.markdown("#### Copies des élèves")
    st.caption("Un fichier par élève, nommé avec le nom de l'élève (ex : `sawadogo_aminata.pdf`).")
    copies_folder = st.file_uploader(
        "PDFs ou images",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="batch_copies",
    )
    st.caption(f"{len(copies_folder) if copies_folder else 0} fichier(s) chargé(s)")

    st.divider()

    if st.button("Lancer le traitement batch", use_container_width=False):
        if not copies_folder:
            st.error("Veuillez charger au moins une copie.")
        elif not exam_name:
            st.error("Veuillez entrer le nom du devoir.")
        else:
            st.session_state.batch_results = None
            st.session_state.batch_errors = []

            from src.core.anonymizer import make_copy_id
            from src.core.config import settings
            from src.pipeline.pipeline import run_single_copy

            runs_dir = Path(settings.runs_dir)
            results = []
            errors = []
            total = len(copies_folder)

            # Barème + énoncé communs
            if hakili_test_batch:
                rubric_batch = hakili_test_batch.rubric
                subject_text_batch = hakili_test_batch.subject_text
            else:
                rubric_batch = _parse_rubric_text("")
                subject_text_batch = ""

            # Logo pour la progression
            from src.ui.progress import PipelineProgressUI
            _logo_path_b = Path(__file__).parent / "hakili_logo.png"
            _logo_b64_b = (
                base64.b64encode(_logo_path_b.read_bytes()).decode("utf-8")
                if _logo_path_b.exists() else ""
            )

            # Barre globale batch
            batch_header = st.empty()
            global_bar = st.progress(0)
            st.divider()
            copy_progress_slot = st.empty()

            with tempfile.TemporaryDirectory() as tmp:
                subject_file_path_batch = None
                rubric_file_path_batch = None

                if not hakili_test_batch:
                    if subject_file_batch:
                        subject_tmp_batch = Path(tmp) / f"subject_{subject_file_batch.name}"
                        _save_upload(subject_file_batch, subject_tmp_batch)
                        subject_file_path_batch = subject_tmp_batch
                    if rubric_file_batch:
                        rubric_tmp_batch = Path(tmp) / f"rubric_{rubric_file_batch.name}"
                        _save_upload(rubric_file_batch, rubric_tmp_batch)
                        rubric_file_path_batch = rubric_tmp_batch

                for i, uploaded in enumerate(copies_folder):
                    student_name_raw = (
                        Path(uploaded.name).stem.replace("_", " ").replace("-", " ").title()
                    )
                    copy_id = make_copy_id(student_name_raw, str(i + 1))

                    batch_header.markdown(
                        f"**Session batch** — Copie {i + 1} / {total} : **{student_name_raw}**"
                    )
                    global_bar.progress((i) / total)

                    # Progression par copie
                    with copy_progress_slot.container():
                        copy_ui = PipelineProgressUI(
                            logo_b64=_logo_b64_b,
                            test_label=hakili_test_batch.label if hakili_test_batch else "Correction libre",
                            student_name=f"{student_name_raw}  ({i+1}/{total})",
                        )

                    tmp_path = Path(tmp) / uploaded.name
                    _save_upload(uploaded, tmp_path)
                    try:
                        result = run_single_copy(
                            copy_id=copy_id,
                            student_name=student_name_raw,
                            file_paths=[tmp_path],
                            rubric=rubric_batch,
                            rubric_file_path=rubric_file_path_batch,
                            subject_text=subject_text_batch,
                            subject_file_path=subject_file_path_batch,
                            expert_instructions=expert_instructions_batch,
                            bareme_id=bareme_id_batch,
                            official_answers=hakili_test_batch.official_answers if hakili_test_batch else "",
                            runs_dir=runs_dir,
                            on_progress=copy_ui.update,
                        )
                        copy_ui.finish()
                        results.append(result)
                    except Exception as e:
                        errors.append(f"{student_name_raw} : {e}")

            global_bar.progress(1.0)
            batch_header.markdown(f"**Session batch terminée** — {len(results)}/{total} copies traitées")
            copy_progress_slot.empty()

            progress.empty()
            st.session_state.batch_results = results
            st.session_state.batch_errors = errors

    # ── Affichage persistant des résultats batch ───────────────────────────────
    if st.session_state.batch_results is not None:
        results = st.session_state.batch_results
        errors = st.session_state.batch_errors

        for err in errors:
            st.error(err)

        if results:
            total = len(results) + len(errors)
            success_results = [r for r in results if r.success]
            st.success(f"{len(success_results)}/{total} copies traitées avec succès.")

            # ── Synthèse de classe ───────────────────────────────────────
            st.markdown("#### Synthèse de classe")
            if success_results:
                scores = [
                    (r.student_name or r.copy_id, r.grade.total_score, r.grade.total_possible)
                    for r in success_results if r.grade
                ]
                if scores:
                    avg_score = sum(s for _, s, _ in scores) / len(scores)
                    max_possible = scores[0][2]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Moyenne classe", f"{avg_score:.1f} / {max_possible}")
                    c2.metric("Copies traitées", len(success_results))
                    c3.metric("Copies en erreur", len(errors))

                    import pandas as pd
                    df = pd.DataFrame(scores, columns=["Élève", "Note", "Maximum"])
                    st.dataframe(df, use_container_width=True)

            # ── Résultats individuels ────────────────────────────────────
            st.markdown("#### Résultats individuels")
            for r in success_results:
                if not r.grade:
                    continue
                avg_conf = (
                    sum(q.confidence for q in r.grade.questions) / len(r.grade.questions)
                    if r.grade.questions else 0.0
                )
                has_review = any(q.requires_review for q in r.grade.questions)
                flag = "!" if has_review else "✓"
                display_name = r.student_name or r.copy_id
                label = (
                    f"{flag}  {display_name} — "
                    f"{r.grade.total_score}/{r.grade.total_possible} pt(s)  "
                    f"· confiance {avg_conf:.0%}"
                    + ("  · Révision requise" if has_review else "")
                )
                with st.expander(label):
                    for q in r.grade.questions:
                        q_icon = "✓" if q.score == 1 else "✗"
                        rtag = " · révision" if q.requires_review else ""
                        st.markdown(
                            f"{q_icon} **{q.rubric_item_id}** — {q.score}/1 "
                            f"(confiance {q.confidence:.0%}){rtag}"
                        )
                        st.caption(f"{q.observed_answer} — {q.comment}")

                    if r.diagnostic:
                        if r.diagnostic.strengths:
                            st.markdown("**Forces :** " + " · ".join(r.diagnostic.strengths))
                        if r.diagnostic.weaknesses:
                            st.markdown("**Lacunes :** " + " · ".join(r.diagnostic.weaknesses))
                        if r.diagnostic.competency_gaps:
                            gap_labels = [
                                f"[{g.chunk_id}] {g.lecon}"
                                for g in r.diagnostic.competency_gaps
                            ]
                            st.caption("Compétences non maîtrisées : " + " · ".join(gap_labels))

                    bc1, bc2 = st.columns(2)
                    r_slug = (
                        r.student_name.lower().replace(" ", "_").replace("'", "").replace("/", "")
                        if r.student_name else r.copy_id
                    )
                    with bc1:
                        if r.pdf_path and r.pdf_path.exists():
                            st.download_button(
                                "Rapport correction",
                                data=r.pdf_path.read_bytes(),
                                file_name=f"rapport_correction_{r_slug}.pdf",
                                mime="application/pdf",
                                key=f"batch_pdf_{r.copy_id}",
                                use_container_width=True,
                            )
                    with bc2:
                        if r.remediation_pdf_path and r.remediation_pdf_path.exists():
                            st.download_button(
                                "Sujet remédiation",
                                data=r.remediation_pdf_path.read_bytes(),
                                file_name=f"sujet_remediation_{r_slug}.pdf",
                                mime="application/pdf",
                                key=f"batch_rem_{r.copy_id}",
                                use_container_width=True,
                            )
