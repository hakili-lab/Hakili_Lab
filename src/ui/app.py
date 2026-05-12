import base64
import json
import tempfile
from pathlib import Path

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

*, body { font-family: 'Inter', sans-serif !important; }

/* Masquer la barre Streamlit par défaut */
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

/* Label "MENU" */
.stRadio > label {
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 1.6px !important;
    color: #4d6d97 !important;
    text-transform: uppercase !important;
    padding: 0 14px !important;
    margin-bottom: 4px !important;
}

/* Items du menu */
.stRadio > div { gap: 1px !important; padding: 0 8px !important; }
.stRadio > div > label {
    padding: 9px 10px !important;
    border-radius: 4px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: #95b5d9 !important;
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
/* Pastille radio */
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
details > summary {
    background: #f7fafd !important;
    border: 1px solid #dde8f5 !important;
    border-radius: 5px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: #001e4a !important;
    padding: 9px 14px !important;
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
                <div style="font-size:10px;color:#4d6d97;margin-top:2px;font-weight:400;">Évaluation IA · Mathématiques</div>
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
        <div class="pheader-badge">Mathématiques · Barème 0/1</div>
    </div>
    """, unsafe_allow_html=True)


def _save_upload(uploaded_file, dest: Path) -> Path:
    dest.write_bytes(uploaded_file.read())
    return dest


def _parse_rubric_text(rubric_text: str):
    from src.models.domain import Rubric, RubricItem
    rubric_text = rubric_text.strip()
    if rubric_text.startswith("{"):
        data = json.loads(rubric_text)
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


def _display_results(result, show_corr_download: bool = True) -> None:
    if not result.success:
        st.error(f"Pipeline échoué : {'; '.join(result.errors)}")
        return

    grade = result.grade
    st.success(f"Correction terminée — **{grade.total_score}/{grade.total_possible}**")

    if result.quality.global_quality == "poor":
        st.warning("Qualité image insuffisante — vérifiez les pages signalées.")

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
        icon = "✅" if q.score == 1 else "❌"
        review_tag = " · ⚠ Révision requise" if q.requires_review else ""
        with st.expander(f"{icon} {q.rubric_item_id} — {q.score}/1  (confiance {q.confidence:.0%}){review_tag}"):
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
        if diag.remediation_plan:
            st.markdown("**Plan de remédiation**")
            for item in sorted(diag.remediation_plan, key=lambda x: x.priority):
                st.markdown(f"{item.priority}. **{item.topic}** — {item.action}")

    st.markdown("#### Téléchargements")
    col_pdf, col_json, col_corr = st.columns(3)
    if result.pdf_path and result.pdf_path.exists():
        col_pdf.download_button(
            "📄 Rapport PDF",
            data=result.pdf_path.read_bytes(),
            file_name=f"rapport_{result.copy_id}.pdf",
            mime="application/pdf",
        )
    if result.json_path and result.json_path.exists():
        col_json.download_button(
            "📦 Export JSON",
            data=result.json_path.read_text(encoding="utf-8"),
            file_name=f"result_{result.copy_id}.json",
            mime="application/json",
        )
    if show_corr_download:
        from src.core.config import settings
        corr_path = Path(settings.runs_dir) / "sessions" / "correspondence.csv"
        if corr_path.exists():
            col_corr.download_button(
                "🔒 Fiche correspondance",
                data=corr_path.read_text(encoding="utf-8"),
                file_name="correspondance.csv",
                mime="text/csv",
            )


# ── PAGE : À PROPOS ───────────────────────────────────────────────────────────

if page == "À PROPOS":
    _page_header("À propos de la plateforme", "Hakili Lab · Correction IA")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("## Objectif")
        st.markdown(
            "**Hakili Lab** est une plateforme d'évaluation et de remédiation assistée par IA "
            "pour copies manuscrites de **mathématiques**. "
            "Elle fournit aux enseignants une correction fiable, rapide et pédagogique."
        )

        st.divider()
        st.markdown("## Fonctionnalités")

        items = [
            ("Transcription multimodale", "Reconnaissance des textes, formules et schémas manuscrits. Signalement des zones ambiguës."),
            ("Correction intelligente", "Évaluation binaire 0/1 par question et sous-question selon le barème fourni."),
            ("Instructions expert", "Critères contextuels optionnels injectés dans le prompt pour affiner la précision."),
            ("Diagnostic pédagogique", "Analyse des forces et lacunes · Plan de remédiation personnalisé."),
            ("Confidentialité", "Numérotation anonyme E-001, E-002… Le PDF exporté ne contient jamais le nom de l'élève."),
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

    col_input, col_config = st.columns(2, gap="large")

    with col_input:
        st.markdown("#### Fichiers d'entrée")
        copy_file = st.file_uploader(
            "Copie de l'élève",
            type=["pdf", "jpg", "jpeg", "png"],
            key="single_copy",
            help="PDF multi-pages ou image",
        )
        subject_text = st.text_area(
            "Énoncé",
            height=110,
            placeholder="Collez ici le texte de l'énoncé…",
        )
        rubric_text = st.text_area(
            "Barème",
            height=110,
            placeholder="Q1 : Calculer la dérivée\nQ2a : Montrer que f(0)=0\n\nOu JSON Rubric complet.",
            help="Une question par ligne au format 'ID : libellé', ou JSON Rubric.",
        )

    with col_config:
        st.markdown("#### Élève")
        student_name = st.text_input(
            "Nom de l'élève",
            placeholder="Ex : Alice Dupont",
            help="Sera anonymisé avant traitement",
        )
        class_name = st.text_input("Classe / Groupe", placeholder="Ex : 1A")
        exam_date = st.date_input("Date de l'examen")

        st.markdown("#### Instructions expert")
        expert_instructions = st.text_area(
            "Critères d'interprétation spécifiques (optionnel)",
            height=96,
            placeholder=(
                "Ex : Pour Q2b, accepter x = 0 même si la justification est absente. "
                "Ne pas pénaliser les fautes d'orthographe."
            ),
            help="Injectées dans le prompt de correction (D-CEO-04).",
        )

    st.divider()

    if st.button("Lancer l'analyse", use_container_width=False):
        if not copy_file:
            st.error("Veuillez charger la copie de l'élève.")
        elif not student_name:
            st.error("Veuillez entrer le nom de l'élève.")
        elif not rubric_text.strip():
            st.error("Veuillez saisir le barème.")
        else:
            with st.spinner("Pipeline en cours…"):
                try:
                    from src.core.anonymizer import Anonymizer
                    from src.core.config import settings
                    from src.pipeline.pipeline import run_single_copy

                    runs_dir = Path(settings.runs_dir)
                    anon = Anonymizer(runs_dir / "sessions")
                    copy_id = anon.register(student_name)
                    rubric = _parse_rubric_text(rubric_text)

                    with tempfile.TemporaryDirectory() as tmp:
                        tmp_path = Path(tmp) / copy_file.name
                        _save_upload(copy_file, tmp_path)
                        result = run_single_copy(
                            copy_id=copy_id,
                            file_path=tmp_path,
                            rubric=rubric,
                            subject_text=subject_text or "(énoncé non fourni)",
                            expert_instructions=expert_instructions,
                            runs_dir=runs_dir,
                        )

                    _display_results(result, show_corr_download=True)

                except Exception as e:
                    st.error(f"Erreur inattendue : {e}")


# ── PAGE : TRAITEMENT BATCH ───────────────────────────────────────────────────

elif page == "TRAITEMENT BATCH":
    _page_header("Traitement batch", "Session multi-élèves · Synthèse de classe")

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        exam_name = st.text_input("Nom du devoir / Examen", placeholder="Ex : Contrôle 1 — Algèbre")
        class_select = st.text_input("Classe / Groupe", placeholder="Ex : 1A")
    with col_b:
        exam_date = st.date_input("Date de l'examen")
        num_students = st.number_input("Nombre d'élèves attendus", min_value=1, max_value=500, value=30)

    st.divider()
    st.markdown("#### Fichiers communs")

    col_x, col_y = st.columns(2, gap="large")
    with col_x:
        subject_text_batch = st.text_area("Énoncé", height=96, placeholder="Texte de l'énoncé…")
        rubric_text_batch = st.text_area("Barème", height=96, placeholder="Q1 : …\nQ2a : …")
    with col_y:
        expert_instructions_batch = st.text_area(
            "Instructions expert (optionnel)",
            height=110,
            placeholder="Critères d'interprétation spécifiques à ce devoir…",
        )

    st.divider()
    st.markdown("#### Copies des élèves")
    st.caption("Un fichier par élève, nommé avec le nom de l'élève (ex : `alice_dupont.pdf`).")
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
        elif not rubric_text_batch.strip():
            st.error("Veuillez saisir le barème.")
        elif not exam_name:
            st.error("Veuillez entrer le nom du devoir.")
        else:
            from src.core.anonymizer import Anonymizer
            from src.core.config import settings
            from src.pipeline.pipeline import run_single_copy

            runs_dir = Path(settings.runs_dir)
            anon = Anonymizer(runs_dir / "sessions")
            rubric = _parse_rubric_text(rubric_text_batch)
            results = []
            errors = []
            total = len(copies_folder)
            progress = st.progress(0, text="Initialisation…")

            with tempfile.TemporaryDirectory() as tmp:
                for i, uploaded in enumerate(copies_folder):
                    student_name_raw = (
                        Path(uploaded.name).stem.replace("_", " ").replace("-", " ").title()
                    )
                    copy_id = anon.register(student_name_raw)
                    progress.progress((i + 1) / total, text=f"Traitement {copy_id} ({i+1}/{total})…")
                    tmp_path = Path(tmp) / uploaded.name
                    _save_upload(uploaded, tmp_path)
                    try:
                        result = run_single_copy(
                            copy_id=copy_id,
                            file_path=tmp_path,
                            rubric=rubric,
                            subject_text=subject_text_batch or "(énoncé non fourni)",
                            expert_instructions=expert_instructions_batch,
                            runs_dir=runs_dir,
                        )
                        results.append(result)
                    except Exception as e:
                        errors.append(f"{copy_id} : {e}")

            progress.empty()

            for err in errors:
                st.error(err)

            if results:
                success_results = [r for r in results if r.success]
                st.success(f"{len(success_results)}/{total} copies traitées avec succès.")

                # ── Synthèse de classe ───────────────────────────────────────
                st.markdown("#### Synthèse de classe")
                if success_results:
                    scores = [
                        (r.copy_id, r.grade.total_score, r.grade.total_possible)
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
                        df = pd.DataFrame(scores, columns=["Copie", "Note", "Maximum"])
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
                    flag = "⚠" if has_review else "✓"
                    label = (
                        f"{flag}  {r.copy_id} — "
                        f"{r.grade.total_score}/{r.grade.total_possible} pt(s)  "
                        f"· confiance {avg_conf:.0%}"
                        + ("  · Révision requise" if has_review else "")
                    )
                    with st.expander(label):
                        for q in r.grade.questions:
                            q_icon = "✅" if q.score == 1 else "❌"
                            rtag = " · ⚠ révision" if q.requires_review else ""
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

                        dcol1, dcol2 = st.columns(2)
                        if r.pdf_path and r.pdf_path.exists():
                            dcol1.download_button(
                                "📄 Rapport PDF",
                                data=r.pdf_path.read_bytes(),
                                file_name=f"rapport_{r.copy_id}.pdf",
                                mime="application/pdf",
                                key=f"pdf_{r.copy_id}",
                            )
                        if r.json_path and r.json_path.exists():
                            dcol2.download_button(
                                "📦 Export JSON",
                                data=r.json_path.read_text(encoding="utf-8"),
                                file_name=f"result_{r.copy_id}.json",
                                mime="application/json",
                                key=f"json_{r.copy_id}",
                            )

                # ── Fiche de correspondance ──────────────────────────────────
                corr_path = runs_dir / "sessions" / "correspondence.csv"
                if corr_path.exists():
                    st.divider()
                    st.download_button(
                        "🔒 Télécharger la fiche de correspondance (CSV)",
                        data=corr_path.read_text(encoding="utf-8"),
                        file_name="correspondance.csv",
                        mime="text/csv",
                    )
