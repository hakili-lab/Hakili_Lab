import base64
import logging
import re
import sys
import tempfile
from pathlib import Path

# Assure que la racine du projet est dans le path (nécessaire sur Windows)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _purge_stale_src_modules() -> None:
    """Streamlit ré-exécute app.py à chaud SANS redémarrer le processus Python
    (notamment lors d'un redéploiement Streamlit Cloud) : les modules src.*
    déjà importés restent alors en cache dans leur ANCIENNE version et lèvent
    des ImportError sur tout symbole ajouté depuis. Quand les sources ont
    changé depuis le dernier passage, purger sys.modules force la
    réimportation à neuf de tout le paquet src."""
    src_dir = Path(__file__).resolve().parent.parent
    mtimes = [p.stat().st_mtime for p in src_dir.rglob("*.py")]
    stamp = (len(mtimes), max(mtimes))
    if getattr(sys, "_hakili_src_stamp", None) != stamp:
        for name in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
            del sys.modules[name]
        sys._hakili_src_stamp = stamp  # type: ignore[attr-defined]


# Uniquement en exécution `streamlit run` (__name__ == "__main__") : importé
# comme module (tests), app.py est lui-même dans sys.modules sous "src.ui.app"
# et se purger en pleine importation casserait le chargement.
if __name__ == "__main__":
    _purge_stale_src_modules()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

import streamlit as st

from src.pipeline.math_format import (
    ascii_math_upgrade,
    humanize_ids_in_text,
    math_to_html,
)
from src.pipeline.text_structuring import series_title, split_question

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
[data-testid="stSidebar"] .stRadio > label,
[data-testid="stSidebar"] .stRadio > label p,
[data-testid="stSidebar"] .stRadio > label span {
    color: #ffffff !important;
    opacity: 1 !important;
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

/* ── Largeur sidebar réduite ────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    width: 200px !important;
    min-width: 200px !important;
    max-width: 200px !important;
}

/* ── Diagnostic forces / lacunes ────────────────────────────────────── */
.diag-section { margin: 8px 0 16px 0; }
.diag-section-header {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; padding: 7px 14px; border-radius: 4px 4px 0 0;
    margin-bottom: 0;
}
.forces-header { background: #eaf7ef; color: #1a7a42; border-left: 3px solid #27ae60; }
.lacunes-header { background: #fff3e8; color: #9a4500; border-left: 3px solid #e67e22; }
.diag-item {
    padding: 9px 14px 9px 16px;
    border-left: 3px solid;
    margin: 2px 0;
    font-size: 13px; line-height: 1.55; color: #2c3e50;
}
.forces-item { border-color: #27ae60; background: #f7fdf9; }
.lacunes-item { border-color: #e67e22; background: #fffaf5; }
.diag-item:last-child { border-radius: 0 0 4px 0; }
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
        format_func=lambda x: {
            "À PROPOS": "À propos",
            "TRAITEMENT UNIQUE": "Analyser une copie",
            "TRAITEMENT BATCH": "Session de classe",
        }.get(x, x),
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
        <div class="pheader-badge">Mathématiques · 6e à la Terminale</div>
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


def _show_failure(technical_detail: str = "") -> None:
    """Affiche un message d'échec clair, sans jargon technique visible."""
    st.markdown(
        """
        <div style="
            background:#fff0f0;
            border:2px solid #c0392b;
            border-radius:8px;
            padding:22px 24px;
            margin:16px 0;
            text-align:center;
        ">
            <div style="font-size:2rem; margin-bottom:8px;">&#9888;</div>
            <div style="font-size:1.1rem; font-weight:700; color:#c0392b; margin-bottom:6px;">
                Une erreur est survenue
            </div>
            <div style="font-size:0.95rem; color:#555;">
                Merci de réessayer. Si le problème persiste, vérifiez votre connexion
                ou contactez le support Hakili Lab.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if technical_detail:
        with st.expander("Détails techniques", expanded=False):
            st.code(technical_detail, language=None)


def _s(v) -> str:
    """Formate un float : entier si possible, sinon notation compacte."""
    try:
        return str(int(v)) if float(v) == int(float(v)) else f"{float(v):g}"
    except (TypeError, ValueError):
        return str(v)


# Substitutions pour les symboles mathématiques que Inter/les navigateurs ne rendent pas bien.
# ⃗ (U+20D7 COMBINING RIGHT ARROW ABOVE) → →  lisible et sémantique pour les vecteurs.
_UI_SYMBOL_SUBS: list[tuple[str, str]] = [
    ("⃗", "→"),   # ⃗ vecteur AB⃗ → AB→
    ("⃖", "←"),   # ⃖ flèche gauche combinante
    ("⃡", "↔"),   # ⃡ double flèche combinante
    ("⃑", "⇁"),   # ⃑ harpoon above
]


def _ui_clean(s: str) -> str:
    """Remplace les caractères combinants mathématiques invisibles/carrés."""
    for char, repl in _UI_SYMBOL_SUBS:
        s = s.replace(char, repl)
    return s


def _mh(s: str) -> str:
    """Notation math HTML : x^2 → <sup>2</sup>, 7/12 → fraction, <= → ≤,
    échappement HTML inclus. Pour les st.markdown(unsafe_allow_html=True).
    Contrairement au PDF, aucune dégradation de police : le navigateur rend
    nativement ∈, ⊂, ², √ — les symboles Unicode restent intacts."""
    return math_to_html(_ui_clean(humanize_ids_in_text(str(s))))


# Exposants Unicode pour les contextes texte pur (labels d'expander, captions)
_SUP_TRANS = str.maketrans("0123456789n+-", "⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻")


def _mt(s: str) -> str:
    """Notation math TEXTE PUR (sans balises HTML) pour les labels d'expander
    et captions Streamlit, où le HTML s'afficherait littéralement :
    <= → ≤, => → →, ^2 → ², ^(3-5) → ³⁻⁵."""
    t = _ui_clean(humanize_ids_in_text(ascii_math_upgrade(str(s))))
    return re.sub(
        r"\^\(?([0-9n+-]{1,3})\)?",
        lambda m: m.group(1).translate(_SUP_TRANS),
        t,
    )


# ── Relecture transcription — marqueurs de confiance (3 niveaux) ──────────────
# ⟦texte⟧ = incertain — [ILLISIBLE] = illisible — reste = confiant (pas de marquage).
# Convention posée dans prompts/transcription_prompt.md. Affichés en clair dans
# le champ éditable (pas de rendu coloré — voir render_transcription_review).

_UNCERTAIN_RE = re.compile(r"⟦([^⟧]*)⟧|(\[ILLISIBLE\])")


def _strip_transcription_markers(content: str) -> str:
    """Retire les marqueurs ⟦…⟧ (garde le texte contenu) pour obtenir le texte
    brut éditable par l'enseignant — [ILLISIBLE] reste tel quel."""
    return _UNCERTAIN_RE.sub(
        lambda m: m.group(1) if m.group(1) is not None else m.group(2), content
    )


# ── Prévisualisation PDF ──────────────────────────────────────────────────────
# Rendu des pages en PNG via PyMuPDF (déjà dépendance de l'ingestion) :
# 100 % fiable dans Streamlit, contrairement aux <iframe> data: que Chrome
# bloque selon les versions. Cache par (chemin, mtime) — un PDF régénéré
# (ex. après validation enseignant) invalide automatiquement son aperçu.

@st.cache_data(show_spinner=False, max_entries=24)
def _pdf_pages_png(pdf_path_str: str, mtime: float, zoom: float = 1.6) -> list[bytes]:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path_str)
    try:
        mat = fitz.Matrix(zoom, zoom)
        return [page.get_pixmap(matrix=mat).tobytes("png") for page in doc]
    finally:
        doc.close()


def _pdf_preview_pages(pdf_path) -> None:
    """Affiche chaque page du PDF en image (corps de l'aperçu)."""
    try:
        pages = _pdf_pages_png(str(pdf_path), pdf_path.stat().st_mtime)
    except Exception as exc:  # PDF corrompu / supprimé entre-temps
        st.warning(f"Aperçu indisponible : {exc}")
        return
    n = len(pages)
    for i, png in enumerate(pages, 1):
        st.image(png, caption=f"Page {i} / {n}", width="stretch")


def _pdf_preview_expander(pdf_path, key: str, nested: bool = False) -> None:
    """Aperçu du PDF avant téléchargement.

    nested=True : rendu via st.toggle (les expanders ne peuvent pas être
    imbriqués dans Streamlit — cas des résultats batch, déjà dans un
    expander par élève)."""
    if nested:
        if st.toggle("👁 Aperçu", key=f"toggle_{key}"):
            _pdf_preview_pages(pdf_path)
    else:
        with st.expander("👁 Aperçu avant téléchargement"):
            _pdf_preview_pages(pdf_path)


def _render_diag_overview(diag) -> str:
    """Retourne le HTML forces + lacunes pour affichage séquentiel élégant."""
    parts: list[str] = []
    if diag.strengths:
        parts.append('<div class="diag-section">')
        parts.append('<div class="diag-section-header forces-header">✦&nbsp; Forces identifiées</div>')
        for s in diag.strengths:
            parts.append(f'<div class="diag-item forces-item">{_mh(s)}</div>')
        parts.append('</div>')
    if diag.weaknesses:
        parts.append('<div class="diag-section">')
        parts.append('<div class="diag-section-header lacunes-header">▼&nbsp; Lacunes prioritaires</div>')
        for w in diag.weaknesses:
            parts.append(f'<div class="diag-item lacunes-item">{_mh(w)}</div>')
        parts.append('</div>')
    return "".join(parts)


def _text_area_height_for_image(img_path: Path, col_width_px: int = 600,
                                 min_h: int = 480, max_h: int = 1100) -> int:
    """Estime la hauteur (px) du champ éditable pour qu'elle se rapproche de la
    hauteur affichée de l'image de la page (même ratio hauteur/largeur), afin
    d'éviter le scroll interne du text_area à côté d'une copie pleine page."""
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
        if w <= 0:
            return col_width_px
        height = int(col_width_px * h / w)
        return max(min_h, min(max_h, height))
    except Exception:
        return col_width_px


def render_transcription_review(transcription, ingestion, key_prefix: str = "") -> None:
    """
    Écran de relecture transcription — étape 1 de la Phase A.
    Pour chaque page : image de la copie à gauche, transcription éditable à
    droite — un champ unique, marqueurs de confiance visibles en clair
    (⟦texte⟧ = incertain, [ILLISIBLE] = illisible) que l'enseignant corrige
    directement dans le texte. Stocke les éditions dans
    st.session_state["transcription_edits"] ({page_number: texte_enseignant}).
    """
    if "transcription_edits" not in st.session_state:
        st.session_state["transcription_edits"] = {}

    st.caption(
        "⟦texte⟧ = lecture incertaine  ·  [ILLISIBLE] = passage illisible — "
        "corrigez directement dans le texte ci-dessous."
    )

    edits = st.session_state["transcription_edits"]
    page_images = {i + 1: p for i, p in enumerate(ingestion.pages)} if ingestion else {}

    for page in transcription.pages:
        idx = page.page_number
        st.markdown(f"##### Page {idx}")
        col_img, col_txt = st.columns([1, 1], gap="large")

        img_path = page_images.get(idx)
        img_exists = bool(img_path) and Path(img_path).exists()

        with col_img:
            if img_exists:
                st.image(str(img_path), width="stretch")
            else:
                st.caption("Image indisponible")

        with col_txt:
            text_height = _text_area_height_for_image(img_path) if img_exists else 600
            default_text = edits.get(idx, page.content)
            edited = st.text_area(
                f"Transcription page {idx}",
                value=default_text,
                height=text_height,
                key=f"{key_prefix}trans_edit_{idx}",
                label_visibility="collapsed",
                help="Corrigez directement le texte si la transcription IA s'est trompée.",
            )
            edits[idx] = edited

        if page.uncertainties:
            with st.expander(f"⚠ {len(page.uncertainties)} zone(s) signalée(s) — page {idx}"):
                for u in page.uncertainties:
                    st.markdown(f"- {_mh(u)}")

        st.divider()

    st.session_state["transcription_edits"] = edits


def _apply_transcription_edits(transcription, edits: dict) -> None:
    """Réécrit transcription.pages[i].content avec le texte validé par l'enseignant
    (marqueurs ⟦…⟧ résiduels retirés — seuls [ILLISIBLE] sont conservés tels quels)."""
    for page in transcription.pages:
        e = edits.get(page.page_number)
        if e is not None:
            page.content = _strip_transcription_markers(e)


def render_validation_table(grade, rubric=None) -> None:
    """
    Affiche le tableau de validation enseignant et stocke les décisions dans
    st.session_state["teacher_decisions"] = { rubric_item_id: {"decision": str, "score": float} }.
    """
    from src.models.domain import TeacherDecision

    if "teacher_decisions" not in st.session_state:
        st.session_state["teacher_decisions"] = {}

    # index max_score par question
    max_scores: dict[str, float] = {}
    if rubric:
        for item in rubric.items:
            max_scores[item.id] = item.max_score

    st.markdown("""
    <style>
    .val-table-header {
        display:grid; grid-template-columns:70px 1fr 1fr 90px 180px;
        gap:0; background:#001e4a; color:#fff; font-size:11px;
        font-weight:700; letter-spacing:0.5px; text-transform:uppercase;
        padding:9px 12px; border-radius:6px 6px 0 0;
    }
    .val-row {
        display:grid; grid-template-columns:70px 1fr 1fr 90px 180px;
        gap:0; padding:7px 12px; font-size:12.5px; border-bottom:1px solid #e8eef8;
        align-items:center;
    }
    .val-row:hover { background:#f5f8fd; }
    .val-row-accepted { background:#f0fbf2; }
    .val-row-refused  { background:#fff8f0; }
    .val-tag-ok  { color:#2d7a2d; font-weight:600; }
    .val-tag-err { color:#c0392b; font-weight:600; }
    .val-tag-rev { color:#e67e22; font-size:10px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="val-table-header">'
        '<span>N° Q</span><span>Bonne réponse</span><span>Réponse élève</span>'
        '<span>Note IA</span><span>Décision enseignant</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    decisions = st.session_state["teacher_decisions"]
    n_decided = 0

    for q in grade.questions:
        max_s = max_scores.get(q.rubric_item_id, 1.0)
        ia_note = f"{_s(q.score)} / {_s(max_s)}"

        prev = decisions.get(q.rubric_item_id, {})
        prev_decision = prev.get("decision", "Accepter")

        review_tag = " ⚠" if q.requires_review else ""
        illisible = "[ILLISIBLE]" in q.observed_answer.upper() or q.observed_answer == "—"
        ans_color = "color:#c0392b;" if illisible else ""
        correct_display = q.correct_answer if q.correct_answer else "—"

        row_class = ""
        if prev_decision == "Accepter":
            row_class = "val-row-accepted"
            n_decided += 1
        elif prev_decision == "Refuser":
            row_class = "val-row-refused"
            n_decided += 1

        st.markdown(
            f'<div class="val-row {row_class}">'
            f'<span style="font-weight:600;color:#001e4a;">{q.rubric_item_id}</span>'
            f'<span style="color:#2c5f2e;">{_mh(correct_display)}</span>'
            f'<span style="{ans_color}">{_mh(q.observed_answer)}{review_tag}</span>'
            f'<span style="font-weight:600;">{"🟢" if q.score > 0 else "🔴"} {ia_note}</span>'
            f'<span></span>'
            '</div>',
            unsafe_allow_html=True,
        )

        col_dec, col_score = st.columns([1, 1])
        with col_dec:
            choice = st.radio(
                f"_{q.rubric_item_id}",
                options=["Accepter", "Refuser"],
                index=0 if prev_decision == "Accepter" else 1,
                horizontal=True,
                label_visibility="collapsed",
                key=f"val_radio_{q.rubric_item_id}",
            )
        with col_score:
            if choice == "Refuser":
                new_score = st.number_input(
                    f"Note {q.rubric_item_id}",
                    min_value=0.0,
                    max_value=float(max_s),
                    value=float(prev.get("score", 0.0)),
                    step=0.25,
                    label_visibility="collapsed",
                    key=f"val_score_{q.rubric_item_id}",
                )
                decisions[q.rubric_item_id] = {"decision": "Refuser", "score": new_score}
            else:
                decisions[q.rubric_item_id] = {"decision": "Accepter", "score": q.score}

    st.session_state["teacher_decisions"] = decisions

    # Compteur et score en temps réel — même formule que compute_final_score() (arrondi au 0.25)
    n_total = len(grade.questions)
    _denom_20 = grade.total_possible
    _raw_sum = sum(d["score"] for d in decisions.values())
    current_score_20 = (
        round(round(_raw_sum / _denom_20 * 20 * 4) / 4, 2) if _denom_20 else 0
    )

    st.markdown(f"""
    <div style="background:#f0f5fc;border:1px solid #c8d8ee;border-radius:0 0 6px 6px;
                padding:10px 14px;display:flex;justify-content:space-between;align-items:center;
                font-size:13px;">
        <span style="color:#6b87a8;">
            <strong>{n_decided} / {n_total}</strong> questions validées
        </span>
        <span>
            Score après validation :
            <strong style="color:#001e4a;font-size:15px;">{current_score_20} / 20</strong>
        </span>
    </div>
    """, unsafe_allow_html=True)


def _apply_teacher_decisions(grade, decisions: dict) -> None:
    """Applique les décisions du tableau au CopyGrade et calcule le score final."""
    from src.models.domain import TeacherDecision
    for q in grade.questions:
        d = decisions.get(q.rubric_item_id, {})
        if d.get("decision") == "Refuser":
            q.teacher_decision = TeacherDecision.refused
            q.teacher_score = d.get("score", 0.0)
        else:
            q.teacher_decision = TeacherDecision.accepted
    grade.compute_final_score()


def _display_results(result, key_prefix: str = "") -> None:
    if not result.success:
        _show_failure("; ".join(result.errors))
        return

    grade = result.grade
    student_label = result.student_name or result.copy_id

    # Score final (validé) ou score IA si pas encore validé
    score_20   = grade.final_score_on_20
    score_disp = f"{score_20}/20" if score_20 is not None else f"{_s(grade.final_score or grade.total_score)} / {_s(grade.total_possible)}"
    st.success(f"Rapport généré — **{student_label}** : **{score_disp}**")

    # Alertes orchestrateur
    auto_fixes = [i for i in result.validation_issues if i.auto_fixed]
    warnings_  = [i for i in result.validation_issues if not i.auto_fixed and i.severity == "warning"]
    if auto_fixes:
        with st.expander(f"Orchestrateur — {len(auto_fixes)} correction(s) automatique(s)"):
            for issue in auto_fixes:
                st.caption(f"✓ [{issue.code}] {issue.message}")
    if warnings_:
        with st.expander(f"Orchestrateur — {len(warnings_)} avertissement(s) à vérifier"):
            for issue in warnings_:
                st.warning(f"[{issue.code}] {issue.message}")

    avg_conf = (
        sum(q.confidence for q in grade.questions) / len(grade.questions)
        if grade.questions else 0.0
    )
    col1, col2 = st.columns(2)
    col1.metric("Note finale", score_disp)
    col2.metric("Fiabilité de lecture", f"{avg_conf:.0%}")

    # ── Tableaux synthèse ─────────────────────────────────────────────────────
    st.markdown("#### Résultats par question")
    good_qs = [q for q in grade.questions if (q.teacher_score if q.teacher_score is not None and q.teacher_decision.value == "refused" else q.score) > 0]
    bad_qs  = [q for q in grade.questions if (q.teacher_score if q.teacher_score is not None and q.teacher_decision.value == "refused" else q.score) == 0]

    col_g, col_b = st.columns(2, gap="large")
    with col_g:
        st.markdown(f"**Bonnes réponses ({len(good_qs)})**")
        for q in good_qs:
            eff = q.teacher_score if (q.teacher_score is not None and q.teacher_decision.value == "refused") else q.score
            st.markdown(f"&nbsp;&nbsp;✅ `{q.rubric_item_id}` — {_s(eff)} pt(s)")
    with col_b:
        st.markdown(f"**Réponses incorrectes ({len(bad_qs)})**")
        for q in bad_qs:
            max_s = q.score  # score IA = 0 → on affiche 0/max_score
            st.markdown(f"&nbsp;&nbsp;❌ `{q.rubric_item_id}` — 0 pt")

    if result.diagnostic:
        diag = result.diagnostic
        st.markdown("#### Diagnostic pédagogique approfondi")
        if diag.strengths or diag.weaknesses:
            st.markdown(_render_diag_overview(diag), unsafe_allow_html=True)

        if diag.root_causes:
            st.markdown("#### Où se situent les vraies difficultés")
            st.caption(
                "Ces points expliquent la majorité des erreurs. "
                "Les corriger aura le plus grand impact sur les résultats de votre enfant."
            )
            for rc in diag.root_causes:
                qs = ", ".join(rc.linked_questions) if rc.linked_questions else "—"
                with st.expander(f"Questions {qs} — {_mt(rc.visible_error)}"):
                    st.markdown(f"**Cause cachée :** {_mh(rc.hidden_cause)}", unsafe_allow_html=True)

        if diag.skills:
            st.markdown("#### Ce que maîtrise l'élève — ce qu'il doit retravailler")
            _level_icon = {
                "acquis":      "🟢 Acquis",
                "part_acquis": "🟡 Part. acquis",
                "non_acquis":  "🔴 Non acquis",
                "unknown":     "⚪ Inconnu",
            }
            _gap_index = {g.chunk_id: g for g in (diag.competency_gaps or [])}
            for sk in diag.skills:
                lbl = _level_icon.get(sk.level, sk.level)
                # Programme RAG : classe + chapitre si non/part acquis
                prog_info = ""
                if sk.level in ("non_acquis", "part_acquis") and sk.chunk_ids:
                    refs = []
                    for cid in sk.chunk_ids:
                        g = _gap_index.get(cid)
                        refs.append(f"{g.classe} — {g.chapitre}" if g else cid)
                    prog_info = "  ·  " + " / ".join(refs)
                with st.expander(f"{lbl}  —  {_mt(sk.name)}{prog_info}"):
                    st.markdown(_mh(sk.evidence), unsafe_allow_html=True)
                    if sk.level in ("non_acquis", "part_acquis") and sk.chunk_ids:
                        for cid in sk.chunk_ids:
                            g = _gap_index.get(cid)
                            if g:
                                st.markdown(f"**Programme :** {g.classe} · {g.chapitre} — *{g.lecon}*")
                                if g.savoir_faire:
                                    for sf in g.savoir_faire:
                                        st.markdown(f"  - {_mh(sf)}", unsafe_allow_html=True)

        if diag.competency_gaps:
            st.markdown("#### Notions à consolider — Programme officiel MEN Burkina Faso")
            st.caption(
                "Ces notions figurent dans le programme officiel du Ministère de l'Éducation. "
                "Elles correspondent aux réponses incorrectes sur ce test."
            )
            for gap in diag.competency_gaps:
                badge = f"{gap.classe} · {gap.domaine.capitalize()}"
                with st.expander(f"[{gap.chunk_id}]  {gap.chapitre} — {gap.lecon}"):
                    st.markdown(f"**Niveau :** {badge}")
                    if gap.savoir_faire:
                        st.markdown("**Savoir-faire à retravailler :**")
                        for sf in gap.savoir_faire:
                            st.markdown(f"- {_mh(sf)}", unsafe_allow_html=True)
                    if gap.erreurs_frequentes:
                        st.markdown("**Erreurs fréquentes associées :**")
                        for ef in gap.erreurs_frequentes:
                            st.caption(f"⚠ {_mt(ef)}")

        if diag.remediation_plan:
            st.markdown("#### Comment aider votre enfant à progresser")
            for item in sorted(diag.remediation_plan, key=lambda x: x.priority):
                st.markdown(f"{item.priority}. **{_mh(item.topic)}** — {_mh(item.action)}", unsafe_allow_html=True)

    if result.remediation_subject and result.remediation_subject.exercises:
        st.markdown("#### Exercices personnalisés pour progresser")
        st.caption("Des exercices ciblés, du plus simple au plus exigeant, pour combler chaque lacune identifiée.")
        current_topic = None
        for ex in result.remediation_subject.exercises:
            if ex.topic != current_topic:
                current_topic = ex.topic
                st.markdown(f"**Série : {_mh(series_title(ex.topic))}**", unsafe_allow_html=True)
            with st.expander(f"Exercice {ex.number}"):
                # Même découpage positionnel que le PDF : une seule numérotation,
                # jamais les marqueurs bruts du LLM ("(1)…" mêlé à "1.…")
                _enonce, _tasks = split_question(str(ex.question))
                _q_html = f"<p>{_mh(_enonce)}</p>" if _enonce else ""
                if _tasks:
                    _q_html += "<ol>" + "".join(f"<li>{_mh(t)}</li>" for t in _tasks) + "</ol>"
                st.markdown(_q_html or _mh(ex.question), unsafe_allow_html=True)
                if ex.hint:
                    st.markdown(f'<span style="font-size:11px;color:#7090b8;">Aide : {_mh(ex.hint)}</span>', unsafe_allow_html=True)

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
                "Rapport complet — Enseignant",
                data=result.pdf_path.read_bytes(),
                file_name=f"rapport_correction_{name_slug}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{kid}",
                use_container_width=True,
            )
            _pdf_preview_expander(result.pdf_path, key=f"prev_pdf_{kid}")
    with col_dl2:
        if result.remediation_pdf_path and result.remediation_pdf_path.exists():
            st.download_button(
                "Exercices de progression — Élève",
                data=result.remediation_pdf_path.read_bytes(),
                file_name=f"sujet_remediation_{name_slug}.pdf",
                mime="application/pdf",
                key=f"dl_rem_{kid}",
                use_container_width=True,
            )
            _pdf_preview_expander(result.remediation_pdf_path, key=f"prev_rem_{kid}")
        elif not (result.remediation_subject and result.remediation_subject.exercises):
            st.caption("Exercices de progression non disponibles pour cette copie")


# ── PAGE : À PROPOS ───────────────────────────────────────────────────────────

if page == "À PROPOS":
    _page_header("Hakili Lab — Diagnostic mathématiques", "Connaître le niveau réel de votre enfant en quelques minutes")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("## Pourquoi le test diagnostic ?")
        st.markdown(
            "Votre enfant a passé un test de mathématiques Hakili Lab. "
            "Cette plateforme vous permet de **connaître précisément ses forces et ses lacunes**, "
            "question par question — et de recevoir un **plan d'exercices personnalisés** "
            "pour l'aider à progresser."
        )

        st.divider()
        st.markdown("## Ce que fait la plateforme")

        items = [
            ("Lecture de la copie manuscrite", "L'IA lit et comprend l'écriture à la main, les calculs et les schémas géométriques — même les copies peu soignées."),
            ("Correction question par question", "Chaque réponse est évaluée selon le barème officiel du test. Vous voyez ce qui est juste et ce qui ne l'est pas."),
            ("Diagnostic pédagogique approfondi", "L'IA identifie les causes profondes des erreurs et les notions du programme officiel qui ne sont pas maîtrisées."),
            ("Exercices de progression personnalisés", "Un sujet d'exercices ciblés est généré automatiquement pour chaque lacune identifiée — du plus simple au plus exigeant."),
            ("Rapport complet téléchargeable", "Un document PDF prêt à imprimer : diagnostic, exercices et conseils pour l'enseignant et l'élève."),
        ]
        for title, desc in items:
            st.markdown(f"**{title}**")
            st.caption(desc)
            st.markdown("")

    with col_right:
        st.markdown("## Comment ça marche ?")
        st.markdown(
            "**1. Scannez ou photographiez** la copie de l'élève.\n\n"
            "**2. Choisissez le test** passé (Hakili 3e, 6e…) — tout est prêt automatiquement.\n\n"
            "**3. Lancez l'analyse** — résultats en moins de 2 minutes.\n\n"
            "**4. L'enseignant valide** les notes proposées et génère le rapport final.\n\n"
            "**5. Téléchargez** le rapport et les exercices personnalisés."
        )

        st.divider()
        st.markdown("## Pour qui ?")
        st.markdown(
            "**Parents d'élèves** — Comprendre où en est votre enfant et comment l'aider.\n\n"
            "**Enseignants** — Corriger une classe entière rapidement, avec un diagnostic précis par élève.\n\n"
            "**Élèves** — Recevoir des exercices ciblés sur leurs vraies difficultés."
        )

        st.divider()
        st.caption(
            "Les corrections proposées par l'IA sont toujours vérifiées et validées "
            "par l'enseignant avant de générer le rapport final."
        )


# ── PAGE : TRAITEMENT UNIQUE ──────────────────────────────────────────────────

elif page == "TRAITEMENT UNIQUE":
    _page_header("Analyser une copie", "Diagnostic complet en quelques minutes")

    if "single_result" not in st.session_state:
        st.session_state.single_result = None

    from src.knowledge.test_registry import get_registry as _get_registry

    # ── Sélection du mode ─────────────────────────────────────────────────────
    _registry = _get_registry()
    _available = _registry.available_tests()

    _MODE_OPTIONS = ["Test personnalisé"] + [
        t.label for t in _available.values()
    ]
    _MODE_IDS = [""] + list(_available.keys())

    selected_mode_label = st.selectbox(
        "Quel test a passé l'élève ?",
        options=_MODE_OPTIONS,
        help=(
            "Sélectionnez le test Hakili correspondant — l'énoncé et le barème se chargent automatiquement. "
            "Si vous utilisez votre propre test, choisissez « Test personnalisé »."
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
        _enonce_status = (
            "✓ Énoncé chargé automatiquement"
            if hakili_test.subject_text
            else "⚠ Énoncé non disponible (PDF uniquement)"
        )
        st.markdown(
            f"""<div style="background:#eef6ff;border:1px solid #b8d4f5;border-radius:6px;
                padding:12px 16px;margin-bottom:16px;font-size:13px;color:#1a3a5c;">
            <strong>{hakili_test.label}</strong><br>
            <span style="color:#5a7aa8;font-size:12px;">
                {hakili_test.description} · Niveaux : {hakili_test.niveaux} ·
                <strong>{hakili_test.total_questions} questions</strong>
            </span><br>
            <span style="color:#2d7a2d;font-size:11.5px;margin-top:4px;display:block;">
                {_enonce_status} &nbsp;·&nbsp;
                ✓ Barème {hakili_test.total_questions} questions prêt &nbsp;·&nbsp;
                ✓ Diagnostic pédagogique activé
            </span>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    col_input, col_config = st.columns(2, gap="large")

    with col_input:
        st.markdown("#### Copie de l'élève")
        copy_files = st.file_uploader(
            "Copie de l'élève (PDF ou photo)",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="single_copy",
            help="Déposez 1 PDF ou plusieurs photos dans l'ordre des pages. Jusqu'à 20 photos.",
        )
        if copy_files:
            n = len(copy_files)
            if n == 1:
                st.caption(f"1 fichier chargé — {copy_files[0].name}")
            else:
                st.caption(f"{n} photos chargées — vérifiez qu'elles sont dans le bon ordre (page 1, 2…)")

        # Énoncé : affiché seulement en mode personnalisé
        if not hakili_test:
            st.markdown("#### Documents du test (optionnel)")
            subject_file = st.file_uploader(
                "Sujet du test (optionnel)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="single_subject",
                help="PDF ou photo du sujet donné à l'élève.",
            )
        else:
            subject_file = None

    with col_config:
        st.markdown("#### Consignes spéciales (optionnel)")
        expert_instructions = st.text_area(
            "Précisions pour la correction (optionnel)",
            height=130,
            placeholder=(
                "Ex : Pour la question 2b, accepter x = 0 même sans justification. "
                "Ne pas pénaliser les fautes d'orthographe."
            ),
            help="Ces précisions seront prises en compte lors de la correction de la copie.",
        )
        if not hakili_test:
            st.caption(
                "Sans barème fourni, la plateforme identifie automatiquement les questions et applique une notation 0/1 par défaut."
            )

    st.divider()

    # ── Session state Étape 1 (transcription) / Étape 2 (correction) / Phase B ─
    if "single_transcription" not in st.session_state:
        st.session_state.single_transcription = None  # PipelineResult après run_transcription
    if "single_phase_a" not in st.session_state:
        st.session_state.single_phase_a = None   # PipelineResult après run_grading
    if "single_result" not in st.session_state:
        st.session_state.single_result = None    # PipelineResult Phase B (final)

    # ── Bouton Étape 1 — Transcription ────────────────────────────────────────
    if st.button("Lancer la transcription", use_container_width=False):
        if not copy_files:
            st.error("Veuillez charger la copie de l'élève (PDF ou photo(s)).")
        elif len(copy_files) > 1 and any(f.name.lower().endswith(".pdf") for f in copy_files):
            st.error("Impossible de mélanger un PDF avec des images. Chargez soit 1 PDF, soit plusieurs images.")
        else:
            st.session_state.single_transcription = None
            st.session_state.single_phase_a = None
            st.session_state.single_result  = None
            st.session_state["teacher_decisions"] = {}
            st.session_state["transcription_edits"] = {}
            try:
                from src.core.anonymizer import make_copy_id
                from src.core.config import settings
                from src.pipeline.pipeline import run_transcription
                from src.ui.progress import PipelineProgressUI

                runs_dir = Path(settings.runs_dir)
                student_name = (
                    Path(copy_files[0].name).stem.replace("_", " ").replace("-", " ").title()
                )
                copy_id = make_copy_id(student_name)

                if hakili_test:
                    rubric = hakili_test.rubric
                    subject_text_val = hakili_test.subject_text
                    subject_file_path = None
                else:
                    from src.models.domain import Rubric as _Rubric
                    rubric = _Rubric(subject="mathematics", total_points=0, items=[])
                    subject_text_val = ""
                    subject_file_path = None

                _logo_path = Path(__file__).parent / "hakili_logo.png"
                _logo_b64 = (
                    base64.b64encode(_logo_path.read_bytes()).decode("utf-8")
                    if _logo_path.exists() else ""
                )

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

                    if not hakili_test and subject_file:
                        sp = Path(tmp) / f"subject_{subject_file.name}"
                        _save_upload(subject_file, sp)
                        subject_file_path = sp

                    transcription_result = run_transcription(
                        copy_id=copy_id,
                        student_name=student_name,
                        file_paths=saved_paths,
                        rubric=rubric,
                        rubric_file_path=None,
                        subject_text=subject_text_val,
                        subject_file_path=subject_file_path,
                        expert_instructions=expert_instructions,
                        bareme_id=bareme_id_single,
                        official_answers=hakili_test.official_answers if hakili_test else "",
                        runs_dir=runs_dir,
                        on_progress=progress_ui.update,
                    )

                progress_ui.clear()
                st.session_state.single_transcription = transcription_result
                st.rerun()

            except Exception as e:
                if "progress_ui" in dir():
                    progress_ui.clear()
                _show_failure(str(e))

    # ── Écran de relecture transcription (après Étape 1) ──────────────────────
    if (
        st.session_state.single_transcription is not None
        and st.session_state.single_phase_a is None
        and st.session_state.single_result is None
    ):
        trans_result = st.session_state.single_transcription

        if trans_result.errors:
            _show_failure("; ".join(trans_result.errors))
        elif trans_result.transcription is not None:
            st.divider()
            st.markdown("""
            <div style="background:#001e4a;color:#fff;padding:12px 16px;border-radius:6px;
                        margin-bottom:16px;font-size:13px;font-weight:600;">
                Étape 1 — Relecture de la transcription
                <span style="font-size:11px;font-weight:400;margin-left:10px;color:#a0c0e8;">
                    Corrigez les zones incertaines ou illisibles avant la correction IA
                </span>
            </div>
            """, unsafe_allow_html=True)

            render_transcription_review(
                trans_result.transcription,
                trans_result.ingestion,
            )

            st.markdown("")
            if st.button(
                "Valider la transcription et lancer la correction →",
                use_container_width=False,
                type="primary",
            ):
                from src.pipeline.pipeline import run_grading
                from src.ui.progress import PipelineProgressUI

                edits = st.session_state.get("transcription_edits", {})
                _apply_transcription_edits(trans_result.transcription, edits)

                _logo_path = Path(__file__).parent / "hakili_logo.png"
                _logo_b64 = (
                    base64.b64encode(_logo_path.read_bytes()).decode("utf-8")
                    if _logo_path.exists() else ""
                )
                progress_ui = PipelineProgressUI(
                    logo_b64=_logo_b64,
                    test_label=hakili_test.label if hakili_test else "Correction libre",
                    student_name=trans_result.student_name,
                )

                try:
                    grading_result = run_grading(
                        result=trans_result,
                        on_progress=progress_ui.update,
                    )
                except Exception as _e_g:
                    progress_ui.clear()
                    _show_failure(str(_e_g))
                    st.stop()

                progress_ui.clear()
                if grading_result.errors:
                    _show_failure("; ".join(grading_result.errors))
                    st.stop()
                st.session_state.single_phase_a = grading_result
                st.session_state.single_transcription = None
                st.rerun()

    # ── Tableau de validation (après Étape 2 — correction) ────────────────────
    if st.session_state.single_phase_a is not None and st.session_state.single_result is None:
        phase_a = st.session_state.single_phase_a

        if phase_a.errors:
            _show_failure("; ".join(phase_a.errors))
        elif phase_a.grade is not None:
            st.divider()
            st.markdown("""
            <div style="background:#001e4a;color:#fff;padding:12px 16px;border-radius:6px;
                        margin-bottom:16px;font-size:13px;font-weight:600;">
                Étape 2 — Validation enseignant
                <span style="font-size:11px;font-weight:400;margin-left:10px;color:#a0c0e8;">
                    Acceptez ou corrigez chaque note proposée par l'IA
                </span>
            </div>
            """, unsafe_allow_html=True)

            render_validation_table(
                phase_a.grade,
                rubric=phase_a.rubric,
            )

            st.markdown("")
            if st.button(
                "Valider et générer le diagnostic →",
                use_container_width=False,
                type="primary",
            ):
                from src.pipeline.pipeline import run_phase_b
                from src.ui.progress import PipelineProgressUI

                decisions = st.session_state.get("teacher_decisions", {})
                _apply_teacher_decisions(phase_a.grade, decisions)

                _logo_path = Path(__file__).parent / "hakili_logo.png"
                _logo_b64 = (
                    base64.b64encode(_logo_path.read_bytes()).decode("utf-8")
                    if _logo_path.exists() else ""
                )
                progress_ui = PipelineProgressUI(
                    logo_b64=_logo_b64,
                    test_label=hakili_test.label if hakili_test else "Correction libre",
                    student_name=phase_a.student_name,
                )

                try:
                    final_result = run_phase_b(
                        result=phase_a,
                        on_progress=progress_ui.update,
                    )
                except Exception as _e_b:
                    progress_ui.clear()
                    _show_failure(str(_e_b))
                    st.stop()

                progress_ui.clear()
                if final_result.errors:
                    _show_failure("; ".join(final_result.errors))
                    st.stop()
                st.session_state.single_result  = final_result
                st.session_state.single_phase_a = None
                st.rerun()

    # ── Résultats finaux (après Phase B) ─────────────────────────────────────
    if st.session_state.single_result is not None:
        st.divider()
        _display_results(st.session_state.single_result)


# ── PAGE : TRAITEMENT BATCH ───────────────────────────────────────────────────

elif page == "TRAITEMENT BATCH":
    _page_header("Session de classe", "Analyser toute une classe d'un coup")

    if "batch_results" not in st.session_state:
        st.session_state.batch_results = None
    if "batch_errors" not in st.session_state:
        st.session_state.batch_errors = []

    from src.knowledge.test_registry import get_registry as _get_registry_batch
    _registry_batch = _get_registry_batch()
    _available_batch = _registry_batch.available_tests()

    # ── Sélection du mode batch ───────────────────────────────────────────────
    _MODE_OPTIONS_BATCH = ["Test personnalisé"] + [
        t.label for t in _available_batch.values()
    ]
    _MODE_IDS_BATCH = [""] + list(_available_batch.keys())

    selected_mode_label_batch = st.selectbox(
        "Quel test a passé la classe ?",
        options=_MODE_OPTIONS_BATCH,
        key="batch_mode_select",
        help="Sélectionnez le test Hakili correspondant — énoncé et barème chargés automatiquement pour toutes les copies.",
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
                ✓ Énoncé prêt &nbsp;·&nbsp; ✓ Barème prêt &nbsp;·&nbsp;
                ✓ Diagnostic pédagogique activé pour chaque copie
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
        st.markdown("#### Documents du test")
        col_x, col_y = st.columns(2, gap="large")
        with col_x:
            subject_file_batch = st.file_uploader(
                "Sujet du test (optionnel)",
                type=["pdf", "jpg", "jpeg", "png"],
                key="batch_subject",
                help="PDF ou photo du sujet commun à toutes les copies.",
            )
        with col_y:
            expert_instructions_batch = st.text_area(
                "Consignes spéciales (optionnel)",
                height=120,
                placeholder="Précisions pour la correction de ce devoir…",
            )
        st.divider()
    else:
        subject_file_batch = None
        expert_instructions_batch = st.text_area(
            "Consignes spéciales (optionnel)",
            height=80,
            placeholder="Précisions pour la correction de ce devoir…",
        )
        st.divider()

    st.markdown("#### Copies des élèves")
    st.caption("Un fichier PDF ou photo par élève, nommé avec le prénom et nom de l'élève (ex : `sawadogo_aminata.pdf`).")
    copies_folder = st.file_uploader(
        "PDFs ou images",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="batch_copies",
    )
    st.caption(f"{len(copies_folder) if copies_folder else 0} fichier(s) chargé(s)")

    st.divider()

    if st.button("Analyser toutes les copies", use_container_width=False):
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
                from src.models.domain import Rubric as _RubricB
                rubric_batch = _RubricB(subject="mathematics", total_points=0, items=[])
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

                if not hakili_test_batch and subject_file_batch:
                    subject_tmp_batch = Path(tmp) / f"subject_{subject_file_batch.name}"
                    _save_upload(subject_file_batch, subject_tmp_batch)
                    subject_file_path_batch = subject_tmp_batch

                for i, uploaded in enumerate(copies_folder):
                    student_name_raw = (
                        Path(uploaded.name).stem.replace("_", " ").replace("-", " ").title()
                    )
                    copy_id = make_copy_id(student_name_raw, str(i + 1))

                    batch_header.markdown(
                        f"**Traitement en cours** — Copie {i + 1} / {total} : **{student_name_raw}**"
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
                            rubric_file_path=None,
                            subject_text=subject_text_batch,
                            subject_file_path=subject_file_path_batch,
                            expert_instructions=expert_instructions_batch,
                            bareme_id=bareme_id_batch,
                            official_answers=hakili_test_batch.official_answers if hakili_test_batch else "",
                            runs_dir=runs_dir,
                            on_progress=copy_ui.update,
                        )
                        copy_ui.clear()
                        results.append(result)
                    except Exception as e:
                        copy_ui.clear()
                        errors.append(f"{student_name_raw} : {e}")

            global_bar.progress(1.0)
            batch_header.markdown(f"**Session terminée** — {len(results)}/{total} copies analysées")
            copy_progress_slot.empty()

            st.session_state.batch_results = results
            st.session_state.batch_errors = errors

    # ── Affichage persistant des résultats batch ───────────────────────────────
    if st.session_state.batch_results is not None:
        results = st.session_state.batch_results
        errors = st.session_state.batch_errors

        for err in errors:
            _show_failure(err)

        if results:
            total = len(results) + len(errors)
            success_results = [r for r in results if r.success]
            st.success(f"{len(success_results)}/{total} copies traitées avec succès.")

            # ── Synthèse de classe ───────────────────────────────────────
            st.markdown("#### Vue d'ensemble de la classe")
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
                _sf = lambda v: str(int(v)) if float(v) == int(float(v)) else f"{float(v):g}"
                label = (
                    f"{flag}  {display_name} — "
                    f"{_sf(r.grade.total_score)}/{_sf(r.grade.total_possible)} pt(s)"
                    + ("  · À vérifier" if has_review else "")
                )
                with st.expander(label):
                    for q in r.grade.questions:
                        q_icon = "✓" if q.score > 0 else "✗"
                        rtag = " · à vérifier" if q.requires_review else ""
                        st.markdown(f"{q_icon} **{q.rubric_item_id}** — {q.score}/1{rtag}")
                        st.caption(f"Réponse : {q.observed_answer}")

                    if r.diagnostic:
                        if r.diagnostic.strengths:
                            st.markdown("**Points forts :** " + " · ".join(r.diagnostic.strengths))
                        if r.diagnostic.weaknesses:
                            st.markdown("**À retravailler :** " + " · ".join(r.diagnostic.weaknesses))
                        if r.diagnostic.competency_gaps:
                            gap_labels = [g.lecon for g in r.diagnostic.competency_gaps]
                            st.caption("Notions à consolider : " + " · ".join(gap_labels))

                    bc1, bc2 = st.columns(2)
                    r_slug = (
                        r.student_name.lower().replace(" ", "_").replace("'", "").replace("/", "")
                        if r.student_name else r.copy_id
                    )
                    with bc1:
                        if r.pdf_path and r.pdf_path.exists():
                            st.download_button(
                                "Rapport — Enseignant",
                                data=r.pdf_path.read_bytes(),
                                file_name=f"rapport_correction_{r_slug}.pdf",
                                mime="application/pdf",
                                key=f"batch_pdf_{r.copy_id}",
                                use_container_width=True,
                            )
                            _pdf_preview_expander(r.pdf_path, key=f"batch_prev_pdf_{r.copy_id}", nested=True)
                    with bc2:
                        if r.remediation_pdf_path and r.remediation_pdf_path.exists():
                            st.download_button(
                                "Exercices — Élève",
                                data=r.remediation_pdf_path.read_bytes(),
                                file_name=f"sujet_remediation_{r_slug}.pdf",
                                mime="application/pdf",
                                key=f"batch_rem_{r.copy_id}",
                                use_container_width=True,
                            )
                            _pdf_preview_expander(r.remediation_pdf_path, key=f"batch_prev_rem_{r.copy_id}", nested=True)
