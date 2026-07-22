import base64
import html
import logging
import logging.handlers
import re
import sys
import tempfile
import unicodedata
from datetime import datetime
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

def _configure_logging() -> None:
    """Configure le logger racine : sortie console (stdout) + fichier tournant
    par jour dans logs/. Streamlit ré-exécute ce script en entier à chaque
    interaction utilisateur, mais dans le MÊME processus Python — le logger
    racine garde donc d'un rerun à l'autre les handlers déjà ajoutés. On les
    marque et on vérifie leur présence avant d'en ajouter de nouveaux, sinon
    chaque rerun dupliquerait un handler et donc chaque ligne écrite."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    existing_ids = {getattr(h, "_hakili_handler_id", None) for h in root.handlers}
    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    if "console" not in existing_ids:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler._hakili_handler_id = "console"
        root.addHandler(console_handler)

    if "file" not in existing_ids:
        logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            logs_dir / "hakili.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._hakili_handler_id = "file"
        root.addHandler(file_handler)


_configure_logging()

import streamlit as st

from src.core.tendance import calculer_tendance
from src.db.database import SessionLocal
from src.db.models import Copie, UserRole
from src.integrations.google_sheets import get_eleve_by_identifiant
from src.pipeline.math_format import (
    ascii_math_upgrade,
    humanize_ids_in_text,
    math_to_html,
)
from src.pipeline.text_structuring import series_title, split_question
from src.services.auth_service import authentifier
from src.services.copie_service import (
    get_copies_pour_identifiants,
    get_documents_for_copie,
    get_historique_eleve,
)
from src.services.user_service import can_access_eleve, get_accessible_eleves

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

/* ── Dashboard Admin — cartes élève ─────────────────────────────────── */
.eleve-card {
    background: #f7fafd;
    border: 1px solid #dde8f5;
    border-left: 4px solid #001e4a;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 10px 0 6px 0;
}
.eleve-card h5 { margin: 0 0 4px 0; font-size: 14px; font-weight: 700; color: #001e4a; }
.eleve-card .eleve-id {
    font-size: 11px; color: #7090b8; font-family: monospace; margin-bottom: 8px;
}
.eleve-card .eleve-meta { font-size: 12.5px; color: #2c3e50; }
.eleve-tag {
    display: inline-block; background: #e6edf8; color: #2d5a8e;
    padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
    margin-right: 6px;
}
.eleve-card-header {
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
}
.eleve-card-header h5 { margin: 0; }
.tendance-badge {
    display: inline-block; padding: 3px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 700; white-space: nowrap;
}
.tendance-vert   { background: #eaf7ef; color: #1a7a42; }
.tendance-orange { background: #fff3e8; color: #9a4500; }
.tendance-rouge  { background: #fdecea; color: #c0392b; }
.tendance-gris   { background: #eef1f4; color: #5a6b7a; }

/* ── Suivi — copies & évolution ──────────────────────────────────────── */
.copie-card {
    background: #fafcff;
    border: 1px solid #e3ecf7;
    border-radius: 8px;
    padding: 12px 16px 8px 16px;
    margin: 12px 0 4px 0;
}
.copie-card .copie-title { font-weight: 700; color: #001e4a; font-size: 13px; margin: 0; }
.copie-card .copie-meta { font-size: 12px; color: #7090b8; margin: 3px 0 0 0; }
.note-good { color: #1a7a42; font-weight: 700; }
.note-pending { color: #9a4500; font-weight: 700; }
.evol-row { margin: 12px 0; font-size: 13px; }
.evol-row .evol-label { font-weight: 600; color: #001e4a; }
.evol-track {
    background: #e8eef7; border-radius: 4px; height: 18px;
    overflow: hidden; margin: 5px 0 3px 0;
}
.evol-fill { height: 100%; background: #27ae60; }
.evol-value { color: #1a7a42; font-weight: 700; font-size: 12.5px; }
.evol-empty { color: #9a4500; font-size: 12.5px; }
.admin-danger-zone {
    border-left: 3px solid #e67e22;
    background: #fffaf5;
    padding: 10px 14px;
    border-radius: 0 5px 5px 0;
    margin: 12px 0;
}

/* Un champ password Streamlit affiche déjà son propre bouton œil
   afficher/masquer ; certains navigateurs (Edge notamment) ajoutent EN PLUS
   leur propre icône native sur <input type="password">, d'où le doublon —
   on masque celle du navigateur pour ne garder que celle de Streamlit. */
input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear { display: none !important; }
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
        options=["À PROPOS", "TRAITEMENT UNIQUE", "TRAITEMENT BATCH", "GESTION"],
        format_func=lambda x: {
            "À PROPOS": "À propos",
            "TRAITEMENT UNIQUE": "Analyser une copie",
            "TRAITEMENT BATCH": "Session de classe",
            "GESTION": "Gestion",
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


def _display_results(result, key_prefix: str = "", eleve: dict | None = None) -> None:
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
    if eleve:
        def _stem(doc_type: str) -> str:
            return nom_fichier_document(
                nom=eleve.get("nom", ""), prenom=eleve.get("prenom", ""),
                doc_type=doc_type, date=datetime.now().date(),
            )
    else:
        _fallback_slug = (
            result.student_name.lower().replace(" ", "_").replace("'", "").replace("/", "")
            if result.student_name else result.copy_id
        )
        def _stem(doc_type: str) -> str:
            return f"{doc_type}_{_fallback_slug}"

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if result.pdf_path and result.pdf_path.exists():
            st.download_button(
                "Rapport complet — Enseignant",
                data=result.pdf_path.read_bytes(),
                file_name=f"{_stem('rapport')}.pdf",
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
                file_name=f"{_stem('remediation')}.pdf",
                mime="application/pdf",
                key=f"dl_rem_{kid}",
                use_container_width=True,
            )
            _pdf_preview_expander(result.remediation_pdf_path, key=f"prev_rem_{kid}")
        elif not (result.remediation_subject and result.remediation_subject.exercises):
            st.caption("Exercices de progression non disponibles pour cette copie")


_DOC_TYPES_ORDRE = ["scan", "rapport", "remediation"]
_DOC_TYPE_LABELS = {"scan": "Scan", "rapport": "Rapport", "remediation": "Remédiation"}


def _sniff_mime_and_ext(data: bytes) -> tuple[str, str]:
    """Détecte le type réel d'un document stocké en base à partir de ses premiers
    octets. Le scan peut être un PDF ou une photo JPG/PNG selon l'upload d'origine
    — contrairement au rapport et à la remédiation, toujours générés en PDF."""
    if data[:4] == b"%PDF":
        return "application/pdf", "pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    return "application/octet-stream", "bin"


@st.cache_data(show_spinner=False, max_entries=24)
def _doc_pdf_pages_png(data: bytes, zoom: float = 1.4) -> list[bytes]:
    """Rend chaque page d'un PDF (bytes) en PNG — variante bytes de _pdf_pages_png,
    nécessaire ici car les documents viennent de la base (BYTEA), pas d'un fichier."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        mat = fitz.Matrix(zoom, zoom)
        return [page.get_pixmap(matrix=mat).tobytes("png") for page in doc]
    finally:
        doc.close()


def _doc_preview(data: bytes, mime: str) -> None:
    """Aperçu d'un document : pages PDF rendues en image, ou image affichée telle
    quelle. Un aperçu qui échoue (lib de rendu absente/cassée, fichier corrompu)
    affiche un message et n'interrompt jamais le reste de la page — seul le
    téléchargement (déjà proposé à côté) reste garanti."""
    if mime == "application/pdf":
        try:
            pages = _doc_pdf_pages_png(data)
        except Exception as exc:
            st.warning(f"Aperçu indisponible : {exc}")
            return
        for i, png in enumerate(pages, 1):
            st.image(png, caption=f"Page {i} / {len(pages)}", width="stretch")
    elif mime.startswith("image/"):
        try:
            st.image(data, width="stretch")
        except Exception as exc:
            st.warning(f"Aperçu indisponible : {exc}")
    else:
        st.caption("Aperçu non disponible pour ce type de fichier.")


def _afficher_documents_copie(copie, db) -> None:
    """Affiche les documents (scan/rapport/remédiation) d'une copie avec boutons
    de téléchargement et d'aperçu — dans l'ordre scan → rapport → remédiation."""
    documents = get_documents_for_copie(db, copie.copy_id)
    docs_by_type = {doc.type: doc for doc in documents}

    # Identité lisible pour le nom de fichier (voir nom_fichier_document) —
    # élève introuvable OU Sheets injoignables (coupure réseau, cas rare
    # ici) : on retombe sur copy_id plutôt que de bloquer le téléchargement.
    from src.integrations.google_sheets import GoogleSheetsError
    try:
        eleve_pour_fichier = get_eleve_by_identifiant(copie.identifiant_hakili)
    except GoogleSheetsError:
        eleve_pour_fichier = None

    st.write("**Documents :**")
    for doc_type in _DOC_TYPES_ORDRE:
        label = _DOC_TYPE_LABELS[doc_type]
        doc = docs_by_type.get(doc_type)
        col_label, col_dl, col_prev = st.columns([1, 1.3, 1.3])
        with col_label:
            st.write(label)
        if doc is None:
            with col_dl:
                st.caption("Non disponible")
            continue

        mime, ext = _sniff_mime_and_ext(doc.fichier)
        if eleve_pour_fichier:
            stem = nom_fichier_document(
                nom=eleve_pour_fichier.get("nom", ""), prenom=eleve_pour_fichier.get("prenom", ""),
                doc_type=doc_type, date=copie.date_soumission,
            )
        else:
            stem = f"{copie.copy_id}_{doc_type}"
        with col_dl:
            st.download_button(
                label="Télécharger",
                data=doc.fichier,
                file_name=f"{stem}.{ext}",
                mime=mime,
                key=f"download_{copie.copy_id}_{doc_type}",
            )
        with col_prev:
            show_preview = st.toggle("Aperçu", key=f"preview_{copie.copy_id}_{doc_type}")
        if show_preview:
            _doc_preview(doc.fichier, mime)


def afficher_historique(eleve: dict, db) -> None:
    """Affiche l'historique complet d'un élève (copies soumises + notes + documents).

    eleve : dict issu des Google Sheets (voir src.integrations.google_sheets.
    get_eleve_by_identifiant) — identité (nom, prénom, centre, classe) vient
    du Sheet. contact_parents ET identifiant_hakili ne sont JAMAIS affichés
    ici (donnée personnelle / technique) — seule exception : le tableau
    élèves de l'admin (voir _admin_view_stats/dispatch GESTION)."""
    nom_complet = html.escape(f"{eleve['prenom']} {eleve['nom']}")
    st.markdown(f"""
    <div class="eleve-card">
        <h5>{nom_complet}</h5>
        <div class="eleve-meta">
            <span class="eleve-tag">{html.escape(eleve.get('centre') or '?')}</span>
            <span class="eleve-tag">{html.escape(eleve.get('classe') or '?')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    historique = get_historique_eleve(db, eleve["identifiant_hakili"])

    if historique:
        st.subheader("Copies soumises")
        for copie in historique:
            if copie.notes_finales is not None:
                note_html = f'<span class="note-good">{copie.notes_finales:.1f}/20</span>'
            else:
                note_html = '<span class="note-pending">Non notée</span>'

            st.markdown(f"""
            <div class="copie-card">
                <p class="copie-title">
                    {html.escape(copie.classe)} &middot; {html.escape(copie.annee_scolaire)}
                </p>
                <p class="copie-meta">{copie.date_soumission} &middot; {note_html}</p>
            </div>
            """, unsafe_allow_html=True)

            _afficher_documents_copie(copie, db)
    else:
        st.info("Aucune copie pour cet élève")


def _render_comparaison_view(db, user, eleves: list[dict]) -> None:
    """Affiche l'évolution chronologique des notes d'un élève, copie par copie
    triée par date_soumission croissante — pas de regroupement par année
    scolaire (centre à tests continus, le découpage en années n'a pas de sens).

    `eleves` : élèves ACCESSIBLES à l'utilisateur connecté (déjà filtrés par
    get_accessible_eleves selon son rôle/casquette) — la sélection par nom
    ne propose jamais un élève hors de ce périmètre. L'identifiant_hakili
    n'est jamais affiché, seulement utilisé en coulisse pour charger
    l'historique (voir _selectbox_recherchable)."""
    st.subheader("Comparaison évolution")

    eleve_comp = _selectbox_recherchable(
        "Élève", eleves,
        format_func=lambda e: f"{e.get('prenom', '')} {e.get('nom', '')}",
        key="comparaison_eleve_select",
        placeholder="Sélectionner un élève",
    )
    if eleve_comp is None:
        return

    if not can_access_eleve(db, user, eleve_comp):
        st.error("Vous n'avez pas accès à cet élève")
        return

    historique = get_historique_eleve(db, eleve_comp["identifiant_hakili"])

    if not historique:
        st.info("Aucune copie pour cet élève")
        return

    chronologie = sorted(historique, key=lambda c: c.date_soumission)

    nom_complet = html.escape(f"{eleve_comp['prenom']} {eleve_comp['nom']}")
    st.markdown(f"""
    <div class="eleve-card">
        <h5>{nom_complet} — Évolution</h5>
    """, unsafe_allow_html=True)

    classe_precedente: str | None = None
    for copie in chronologie:
        classe_label = html.escape(copie.classe)

        changement_html = ""
        if classe_precedente is not None and classe_precedente != copie.classe:
            changement_html = (
                f'<span class="eleve-tag">Changement de classe : '
                f'{html.escape(classe_precedente)} → {classe_label}</span>'
            )
        classe_precedente = copie.classe

        if copie.notes_finales is not None:
            pct = max(0, min(100, int((copie.notes_finales / 20) * 100)))
            note_html = (
                f'<div class="evol-track"><div class="evol-fill" style="width:{pct}%;"></div></div>'
                f'<span class="evol-value">{copie.notes_finales:.1f}/20</span>'
            )
        else:
            note_html = '<div class="evol-empty">Non notée</div>'

        row_html = (
            f'<div class="evol-row">'
            f'<span class="evol-label">{copie.date_soumission}</span> — {classe_label}'
            f'{changement_html}'
            f'{note_html}'
            f'</div>'
        )
        st.markdown(row_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# Libellé + classe CSS par tendance (voir src.core.tendance.calculer_tendance).
_TENDANCE_STYLE: dict[str, tuple[str, str]] = {
    "progresse": ("tendance-vert", "Progresse"),
    "stagne": ("tendance-orange", "Stagne"),
    "regresse": ("tendance-rouge", "Régresse"),
    "insuffisant": ("tendance-gris", "Pas assez de données"),
}

# Priorité d'affichage : un responsable doit voir en premier qui décroche.
_ORDRE_TENDANCE: dict[str, int] = {"regresse": 0, "stagne": 1, "progresse": 2, "insuffisant": 3}


def _render_tableau_responsable(db, eleves: list[dict]) -> None:
    """Tableau de suivi pour un responsable de centre : identité (Sheets) +
    pastille de tendance calculée sur les deux dernières copies notées de
    chaque élève (voir src.core.tendance.calculer_tendance).

    Performance : les copies de TOUS les élèves du centre sont chargées en
    UNE seule requête groupée (get_copies_pour_identifiants), pas une
    requête par élève — un centre à plusieurs dizaines d'élèves ferait
    sinon autant de requêtes que d'élèves.

    contact_parents n'est jamais lu ici : les dicts élèves de
    get_accessible_eleves() le portent, mais on ne prend que nom, prénom,
    classe, école, centre, identifiant_hakili."""
    identifiants = [e["identifiant_hakili"] for e in eleves]
    copies_par_identifiant = get_copies_pour_identifiants(db, identifiants)

    lignes: list[tuple[dict, str]] = []
    nb_en_baisse = 0
    for eleve in eleves:
        copies = copies_par_identifiant.get(eleve["identifiant_hakili"], [])
        tendance = calculer_tendance(copies)
        if tendance == "regresse":
            nb_en_baisse += 1
        lignes.append((eleve, tendance))

    if nb_en_baisse:
        st.warning(f"{nb_en_baisse} élève(s) en baisse — à regarder en priorité.")
    else:
        st.success("Aucun élève en baisse actuellement.")

    recherche = st.text_input(
        "Rechercher un élève",
        key="responsable_recherche",
        placeholder="Rechercher par nom ou prénom...",
    )
    if recherche.strip():
        lignes = [
            (eleve, tendance) for eleve, tendance in lignes
            if _correspond_recherche(recherche, f"{eleve.get('prenom', '')} {eleve.get('nom', '')}")
        ]

    st.write(f"**{len(lignes)} élève(s)** affiché(s) sur {len(eleves)} accessible(s)")

    # Élèves en baisse en premier, puis stagne, progresse, et enfin
    # insuffisant (rien à signaler) — ordre alphabétique à égalité.
    lignes.sort(key=lambda paire: (_ORDRE_TENDANCE[paire[1]], paire[0].get("nom") or ""))

    for eleve, tendance in lignes:
        css_class, libelle = _TENDANCE_STYLE[tendance]
        nom_complet = html.escape(f"{eleve.get('prenom', '')} {eleve.get('nom', '')}")
        classe = html.escape(eleve.get("classe") or "?")
        ecole = html.escape(eleve.get("ecole") or "?")
        centre = html.escape(eleve.get("centre") or "?")

        st.markdown(f"""
        <div class="eleve-card">
            <div class="eleve-card-header">
                <h5>{nom_complet}</h5>
                <span class="tendance-badge {css_class}">{libelle}</span>
            </div>
            <div class="eleve-meta">
                <span class="eleve-tag">{classe}</span>
                <span class="eleve-tag">{centre}</span>
                {ecole}
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_profil_enseignant(db, user: dict, eleves: list[dict]) -> None:
    """Vue individuelle enseignant : liste déroulante restreinte à ses
    élèves (get_accessible_eleves — déjà filtrée centre + classe), puis
    profil complet d'UN élève choisi : identité Sheets, pastille de
    tendance (même style que la vue responsable — calculer_tendance et
    _TENDANCE_STYLE réutilisés tels quels, aucune logique dupliquée),
    résumé chiffré, et copies/documents en ordre chronologique.

    Sécurité : la liste déroulante ne propose déjà que des élèves
    autorisés, mais on revérifie can_access_eleve() avant d'afficher quoi
    que ce soit — jamais confiance uniquement au filtrage côté UI."""
    eleve = _selectbox_recherchable(
        "Élève", eleves,
        format_func=lambda e: f"{e.get('prenom', '')} {e.get('nom', '')}",
        key="enseignant_eleve_select",
        placeholder="Sélectionner un élève",
    )
    if eleve is None:
        return

    if not can_access_eleve(db, user, eleve):
        st.error("Vous n'avez pas accès à cet élève.")
        return

    # Une seule requête : sert à la fois au calcul de tendance, au résumé
    # chiffré et à la liste chronologique ci-dessous.
    historique = get_historique_eleve(db, eleve["identifiant_hakili"])
    tendance = calculer_tendance(historique)
    css_class, libelle = _TENDANCE_STYLE[tendance]

    nom_complet = html.escape(f"{eleve.get('prenom', '')} {eleve.get('nom', '')}")
    classe = html.escape(eleve.get("classe") or "?")
    ecole = html.escape(eleve.get("ecole") or "?")
    centre = html.escape(eleve.get("centre") or "?")
    reprend = html.escape(str(eleve.get("reprend_la_classe") or "?"))
    boursier = html.escape(str(eleve.get("boursier") or "?"))

    st.markdown(f"""
    <div class="eleve-card">
        <div class="eleve-card-header">
            <h5>{nom_complet}</h5>
            <span class="tendance-badge {css_class}">{libelle}</span>
        </div>
        <div class="eleve-meta">
            <span class="eleve-tag">{classe}</span>
            <span class="eleve-tag">{centre}</span>
            {ecole}
        </div>
        <div class="eleve-meta" style="margin-top:6px;">
            Reprend la classe : {reprend} &middot; Boursier : {boursier}
        </div>
    </div>
    """, unsafe_allow_html=True)

    nb_copies = len(historique)
    derniere_copie = historique[0] if historique else None  # déjà trié desc
    date_derniere_copie_txt = str(derniere_copie.date_soumission) if derniere_copie else "—"
    derniere_notee = next((c for c in historique if c.notes_finales is not None), None)
    derniere_note_txt = f"{derniere_notee.notes_finales:.1f}/20" if derniere_notee else "Non notée"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Copies soumises", nb_copies)
    with col2:
        st.metric("Dernière note", derniere_note_txt)
    with col3:
        st.metric("Date dernière copie", date_derniere_copie_txt)

    st.divider()

    if not historique:
        st.info("Aucune copie pour cet élève.")
        return

    st.subheader("Copies soumises")
    # Ordre chronologique croissant — même convention que l'onglet
    # Comparaison (on suit le fil du temps, pas de regroupement par année).
    chronologie = sorted(historique, key=lambda c: c.date_soumission)
    for copie in chronologie:
        if copie.notes_finales is not None:
            note_html = f'<span class="note-good">{copie.notes_finales:.1f}/20</span>'
        else:
            note_html = '<span class="note-pending">Non notée</span>'

        st.markdown(f"""
        <div class="copie-card">
            <p class="copie-title">{html.escape(copie.classe)} &middot; {copie.date_soumission}</p>
            <p class="copie-meta">{note_html}</p>
        </div>
        """, unsafe_allow_html=True)

        _afficher_documents_copie(copie, db)


# ── Helpers — Dashboard Admin ───────────────────────────────────────────────

def _admin_view_stats(db) -> None:
    """Vue Statistiques — accessible uniquement depuis l'onglet Admin (is_admin),
    voir tab_admin plus bas. Affiche le personnel par centre (noms), TOUT le
    personnel y compris sans PIN (mention discrète) : ne jamais appeler
    cette fonction depuis l'onglet Suivi (responsables/enseignants).

    Élèves ET personnel viennent tous les deux des Google Sheets — plus
    aucune lecture Centre/Utilisateur/Credentials ici, ces tables n'existent
    plus. Les centres affichés sont DÉRIVÉS dynamiquement des Sheets (voir
    get_centres_derives) — plus de liste figée : un centre avec plusieurs
    personnes apparaît automatiquement, sans toucher au code."""
    st.markdown("**Statistiques**")

    from src.integrations.google_sheets import GoogleSheetsError, get_centres_derives, get_eleves, get_personnel

    eleves = _lire_sheets_avec_secours(
        get_eleves, cache_key="eleves", bouton_key="admin_eleves", label="Élèves",
    )
    if eleves is _SHEETS_ECHEC:
        eleves = []
    personnel = _lire_sheets_avec_secours(
        get_personnel, cache_key="personnel", bouton_key="admin_personnel", label="Personnel",
    )
    if personnel is _SHEETS_ECHEC:
        personnel = []

    centres_derives: dict[str, dict] = {}
    try:
        centres_derives = get_centres_derives()
    except GoogleSheetsError as exc:
        st.warning(f"Centres indisponibles (Google Sheets injoignable) : {exc}")

    # Centre vu très peu de fois : jamais bloqué ni corrigé, juste signalé
    # ici pour que le docteur vérifie s'il s'agit d'une faute de frappe.
    for info in centres_derives.values():
        if info["suspect"]:
            st.warning(
                f"Centre vu {info['count']} fois seulement : {info['canonique']!r} — "
                f"faute de frappe possible ?"
            )

    centres_a_afficher = sorted(info["canonique"] for info in centres_derives.values())
    nb_copies = db.query(Copie).count()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Élèves", len(eleves) if eleves else "?")
    with col2:
        st.metric("Centres", len(centres_a_afficher))
    with col3:
        st.metric("Copies", nb_copies)

    st.divider()
    st.markdown("**Personnel par centre**")

    def _classes_pour_centre(p: dict, centre_nom: str) -> list[str]:
        """Un enseignant peut avoir plusieurs affectations dans un même
        centre (ex : 6e ET 5e) — voir google_sheets._load_personnel."""
        return [classe for centre, classe in p.get("affectations", []) if centre == centre_nom]

    def _mention_pin(p: dict) -> str:
        return "" if p.get("pin") else "  ·  PIN manquant"

    _ROLES_CONNUS = {UserRole.admin.value, UserRole.responsable_centre.value, UserRole.enseignant.value}

    for centre_nom in centres_a_afficher:
        st.markdown(f"**{centre_nom}**")

        administrateurs = [
            p for p in personnel
            if p.get("role") == UserRole.admin.value and _classes_pour_centre(p, centre_nom)
        ]
        if administrateurs:
            st.write(f"Administrateurs ({len(administrateurs)}) :")
            for p in administrateurs:
                st.write(f"- {p.get('prenom', '')} {p.get('nom', '')}{_mention_pin(p)}")

        responsables = [
            p for p in personnel
            if p.get("role") == UserRole.responsable_centre.value and _classes_pour_centre(p, centre_nom)
        ]
        if responsables:
            st.write(f"Responsables ({len(responsables)}) :")
            for p in responsables:
                st.write(f"- {p.get('prenom', '')} {p.get('nom', '')}{_mention_pin(p)}")
        else:
            st.write("Responsables : aucun")

        enseignants = [
            p for p in personnel
            if p.get("role") == UserRole.enseignant.value and _classes_pour_centre(p, centre_nom)
        ]
        if enseignants:
            st.write(f"Enseignants ({len(enseignants)}) :")
            for p in enseignants:
                classes_txt = ", ".join(_classes_pour_centre(p, centre_nom)) or "classe non renseignée"
                st.write(f"- {p.get('prenom', '')} {p.get('nom', '')} — {classes_txt}{_mention_pin(p)}")
        else:
            st.write("Enseignants : aucun")

        autres = [
            p for p in personnel
            if p.get("role") not in _ROLES_CONNUS and _classes_pour_centre(p, centre_nom)
        ]
        if autres:
            st.write(f"Rôle non reconnu dans le Sheet ({len(autres)}) :")
            for p in autres:
                st.write(f"- {p.get('prenom', '')} {p.get('nom', '')} — rôle Sheet : {p.get('role') or 'vide'}")

        st.divider()

    # Personnel sans centre renseigné (ex. administrateur) — jamais masqué,
    # même s'il n'apparaît sous aucun centre ci-dessus.
    sans_centre = [
        p for p in personnel if not any(c for c, _cl in p.get("affectations", []))
    ]
    if sans_centre:
        st.markdown("**Personnel sans centre renseigné**")
        for p in sans_centre:
            role_txt = p.get("role") or "rôle non renseigné"
            st.write(f"- {p.get('prenom', '')} {p.get('nom', '')} ({role_txt}){_mention_pin(p)}")


def _nettoyer_pour_nom_fichier(text: str) -> str:
    """Retire accents/espaces/apostrophes/slashes et tout caractère non
    alphanumérique (remplacé par un underscore) — pour rester un nom de
    fichier valide à la fois sous Windows et sous Linux."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")


def nom_fichier_document(*, nom: str, prenom: str, doc_type: str, date) -> str:
    """Nom de fichier lisible pour un document téléchargé (scan/rapport/
    remédiation) : NOM_Prenom_type_date (sans extension — l'appelant ajoute
    .pdf/.jpg/...). Ne contient JAMAIS contact_parents (le numéro du parent
    ne doit pas voyager dans des fichiers qui circulent — WhatsApp, email)
    ni identifiant_hakili — seuls nom et prénom, comme affichés à l'écran.

    À appliquer PARTOUT où un document est proposé au téléchargement
    (traitement unique, traitement batch, vue Suivi)."""
    nom_c = _nettoyer_pour_nom_fichier(nom).upper()
    prenom_c = _nettoyer_pour_nom_fichier(prenom)
    parts = [p for p in (nom_c, prenom_c) if p]
    base = "_".join(parts) if parts else "eleve"
    return f"{base}_{doc_type}_{date}"


def _fold_token(text: str) -> str:
    """Minuscule, sans accents, lettres/chiffres uniquement — pour comparer
    un nom de fichier au nom/prénom d'un élève sans se soucier de la casse,
    des accents ou du séparateur utilisé."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]", "", ascii_text)


def _fold_texte(text: str) -> str:
    """Comme _fold_token mais CONSERVE un espace entre les mots — sert de
    base à une recherche insensible à l'ORDRE des mots (voir
    _correspond_recherche) : "Sanou Feryel" doit retrouver "Feryel SANOU"
    même si l'affichage montre le prénom avant le nom."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _correspond_recherche(requete: str, cible: str) -> bool:
    """Vrai si chaque mot de `requete` apparaît (comme sous-chaîne, ordre
    des mots ignoré) dans `cible` — insensible casse/accents. Une requête
    vide correspond toujours. Utilisé par toutes les recherches nom/prénom
    du projet (élèves, personnel) pour un comportement cohérent, qu'on
    tape "Sanou Feryel" ou "Feryel Sanou"."""
    mots_requete = _fold_texte(requete).split()
    cible_repliee = _fold_texte(cible)
    return all(mot in cible_repliee for mot in mots_requete)


def _selectbox_recherchable(
    label: str,
    items: list[dict],
    format_func,
    key: str,
    placeholder: str = "Sélectionner",
) -> dict | None:
    """Sélection dans une liste déroulante — st.selectbox est nativement
    recherchable (taper dedans filtre les options), donc aucune barre de
    recherche séparée n'est ajoutée ici (elle ferait doublon).

    Placeholder sobre, sans tirets cadratin autour (ex. "Sélectionner un
    élève", pas "— Sélectionner un élève —"). Retourne l'item sélectionné —
    le libellé affiché (format_func) peut changer sans jamais affecter la
    valeur technique retournée (ex. l'identifiant_hakili reste utilisé en
    coulisse par l'appelant) — ou None si le placeholder est resté choisi."""
    options = [placeholder] + [format_func(item) for item in items]
    selection = st.selectbox(label, options=options, key=key)
    if selection == placeholder:
        return None
    return items[options.index(selection) - 1]


def _match_eleve_par_nom_fichier(filename_stem: str, eleves: list[dict]) -> dict | None:
    """Mode batch : fait correspondre un fichier uploadé (nommé par convention
    avec le nom et prénom de l'élève) à un élève des Google Sheets, sans
    dépendre d'une sélection manuelle par fichier (peu pertinente pour 30
    copies d'un coup — voir chantier pipeline/Sheets).

    Retourne l'élève UNIQUEMENT si son nom ET son prénom (repliés, sans
    accents/casse) apparaissent tous les deux dans les tokens du nom de
    fichier, et qu'un seul élève correspond — sinon None (introuvable ou
    ambigu), auquel cas l'appelant doit bloquer cette copie plutôt que deviner.
    """
    tokens_fichier = {
        _fold_token(t) for t in re.split(r"[_\-\s]+", filename_stem) if t
    }
    matches = []
    for eleve in eleves:
        tokens_eleve = {_fold_token(eleve.get("nom", "")), _fold_token(eleve.get("prenom", ""))}
        if all(tokens_eleve) and tokens_eleve <= tokens_fichier:
            matches.append(eleve)
    return matches[0] if len(matches) == 1 else None


# ── Double rôle — sélecteur de casquette ─────────────────────────────────────

_ROLES_VALIDES = {r.value for r in UserRole}
_LABELS_CASQUETTE = {
    UserRole.responsable_centre.value: "Responsable",
    UserRole.enseignant.value: "Enseignant",
    UserRole.admin.value: "Administrateur",
}


def _roles_valides_de(personne: dict) -> list[str]:
    """Rôles reconnus (valeurs UserRole) d'une personne du Sheet personnel —
    à partir de personne["roles"] (double rôle possible, voir
    google_sheets._load_personnel) avec repli sur personne["role"] (rôle
    principal) si "roles" est absent. Un rôle du Sheet non reconnu par
    UserRole est simplement ignoré ici plutôt que de faire planter
    l'aiguillage — l'erreur claire est déjà montrée à la connexion."""
    roles = personne.get("roles") or ([personne["role"]] if personne.get("role") else [])
    return [r for r in roles if r in _ROLES_VALIDES]


def _vue_utilisateur_pour_casquette(personne: dict, casquette: str) -> dict:
    """Construit le dict "utilisateur" attendu par les fonctions de
    permission EXISTANTES (get_accessible_eleves/can_access_eleve) à partir
    de la personne connectée et de la casquette ACTIVE choisie — pertinent
    seulement en double rôle, voir chantier sélecteur de casquette.

    N'aiguille QUE role_enum et affectations vers le périmètre de la
    casquette choisie ; ne duplique aucune logique de permission ni aucune
    vue.

    Correction (audit) : la casquette Responsable donne accès à TOUT LE
    CENTRE où la personne porte le rôle responsable — voir
    personne["centres_responsable"] (google_sheets._load_personnel),
    construit à partir du RÔLE de chaque ligne du Sheet, jamais de la
    présence ou de l'absence d'une classe sur cette ligne. Dans les
    données réelles, une ligne responsable porte quasi toujours aussi une
    classe (ex. DIANE Abasse) : filtrer sur "classe is None" (ancienne
    logique) ne retenait alors AUCUNE affectation et vidait silencieusement
    l'accès du responsable à son propre centre. La casquette Enseignant,
    elle, reste basée sur les affectations précises (centre + classe),
    inchangée."""
    vue = dict(personne)
    vue["role_enum"] = UserRole(casquette)
    if casquette == UserRole.enseignant.value:
        vue["affectations"] = [a for a in personne.get("affectations", []) if a[1] is not None]
    elif casquette == UserRole.responsable_centre.value:
        vue["affectations"] = [
            (centre, None) for centre in personne.get("centres_responsable", [])
        ]
    return vue


# ── Échec doux sur coupure Google Sheets ─────────────────────────────────────

_SHEETS_ECHEC = object()  # sentinelle : "rien à afficher pour l'instant"


def _lire_sheets_avec_secours(action, *, cache_key: str, bouton_key: str, label: str):
    """Exécute `action` (callable sans argument qui lit les Sheets, ex.
    `lambda: get_accessible_eleves(user)`) en distinguant proprement une
    coupure réseau d'un problème de configuration (voir
    src.integrations.google_sheets.GoogleSheetsConnectiviteError /
    GoogleSheetsConfigError) :

    - CONFIGURATION (identifiant erroné, colonne manquante...) -> message
      technique précis conservé, JAMAIS de repli silencieux (un vrai
      problème à corriger ne doit jamais être masqué par d'anciennes
      données) ; retourne _SHEETS_ECHEC.
    - CONNECTIVITÉ (réseau/DNS/timeout) -> si aucune lecture n'a encore
      réussi, message doux + bouton Réessayer, retourne _SHEETS_ECHEC ; si
      une lecture a déjà réussi, `action()` a déjà servi ces données de
      repli en coulisse (voir google_sheets._cached_avec_repli) — on
      affiche alors juste un bandeau discret "hors ligne" avec l'heure de
      la dernière synchro et un bouton Réessayer, sans jamais de stack
      trace brute.

    L'appelant doit traiter un retour == _SHEETS_ECHEC comme "rien à
    afficher pour l'instant", jamais planter ni deviner."""
    from src.integrations.google_sheets import (
        GoogleSheetsConfigError, GoogleSheetsConnectiviteError, clear_cache, get_statut_lecture,
    )
    try:
        resultat = action()
    except GoogleSheetsConfigError as exc:
        st.error(f"{label} indisponible(s) : {exc}")
        return _SHEETS_ECHEC
    except GoogleSheetsConnectiviteError:
        st.warning(
            "Connexion à Internet indisponible pour le moment. Vérifiez votre "
            "connexion et réessayez."
        )
        if st.button("Réessayer", key=f"retry_{bouton_key}"):
            clear_cache()
            st.rerun()
        return _SHEETS_ECHEC

    statut = get_statut_lecture(cache_key)
    if statut["mode"] == "repli":
        heure = statut["derniere_synchro"].strftime("%H:%M") if statut["derniere_synchro"] else "?"
        col_msg, col_btn = st.columns([5, 1])
        with col_msg:
            st.info(
                f"Données affichées hors ligne (dernière synchro : {heure}). "
                f"Reconnectez-vous pour mettre à jour."
            )
        with col_btn:
            if st.button("Réessayer", key=f"retry_online_{bouton_key}"):
                clear_cache()
                st.rerun()
    return resultat


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

    # ── Sélection élève (gauche) / test (droite) sur une seule ligne ──────────
    from src.integrations.google_sheets import get_eleves

    col_eleve, col_test = st.columns(2, gap="large")

    with col_eleve:
        _eleves_disponibles = _lire_sheets_avec_secours(
            get_eleves, cache_key="eleves", bouton_key="single_eleves", label="Élèves",
        )
        if _eleves_disponibles is _SHEETS_ECHEC:
            _eleves_disponibles = []

        # Nom + prénom seulement — jamais classe/centre affichés ici, jamais
        # contact_parents ni identifiant_hakili (donnée interne uniquement,
        # utilisée en coulisse pour retrouver l'élève, jamais montrée).
        selected_eleve = _selectbox_recherchable(
            "Élève", _eleves_disponibles,
            format_func=lambda e: f"{e['prenom']} {e['nom']}",
            key="single_eleve_select",
            placeholder="Sélectionner un élève",
        )

    with col_test:
        # ── Sélection du mode ─────────────────────────────────────────────────
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

    # ── Session state Transcription / Phase A / B ─────────────────────────────
    if "single_transcription" not in st.session_state:
        st.session_state.single_transcription = None  # PipelineResult transcription (en attente de relecture)
    if "single_phase_a" not in st.session_state:
        st.session_state.single_phase_a = None   # PipelineResult Phase A (correction IA faite)
    if "single_result" not in st.session_state:
        st.session_state.single_result = None    # PipelineResult Phase B (final)

    # ── Bouton Transcription ──────────────────────────────────────────────────
    if st.button("Lancer la correction IA", use_container_width=False):
        if selected_eleve is None:
            st.error("Veuillez sélectionner l'élève dans la liste.")
        elif not copy_files:
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
                identifiant_hakili_single = selected_eleve["identifiant_hakili"]
                student_name = f"{selected_eleve['prenom']} {selected_eleve['nom']}"
                # Suffixe horodaté : un même élève peut soumettre plusieurs
                # copies au fil du temps (voir Suivi > Comparaison) —
                # identifiant_hakili seul ne suffit pas comme copy_id (clé
                # primaire de COPIE), il doit rester unique par soumission.
                copy_id = make_copy_id(identifiant_hakili_single, suffix=datetime.now().strftime("%Y%m%d%H%M%S"))

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
                        identifiant_hakili=identifiant_hakili_single,
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

    # ── Relecture transcription (après étape 1, avant notation) ──────────────
    if (
        st.session_state.single_transcription is not None
        and st.session_state.single_phase_a is None
        and st.session_state.single_result is None
    ):
        transcription_pending = st.session_state.single_transcription

        if transcription_pending.errors:
            _show_failure("; ".join(transcription_pending.errors))
        elif transcription_pending.transcription is not None:
            st.divider()
            st.markdown("""
            <div style="background:#001e4a;color:#fff;padding:12px 16px;border-radius:6px;
                        margin-bottom:16px;font-size:13px;font-weight:600;">
                Étape 1 — Relecture de la transcription
                <span style="font-size:11px;font-weight:400;margin-left:10px;color:#a0c0e8;">
                    Corrigez le texte avant de lancer la notation IA
                </span>
            </div>
            """, unsafe_allow_html=True)

            render_transcription_review(
                transcription_pending.transcription,
                transcription_pending.ingestion,
                key_prefix="single_",
            )

            st.markdown("")
            if st.button(
                "Valider et noter →",
                use_container_width=False,
                type="primary",
                key="single_validate_transcription",
            ):
                edits = st.session_state.get("transcription_edits", {})
                _apply_transcription_edits(transcription_pending.transcription, edits)

                from src.pipeline.pipeline import run_grading
                from src.ui.progress import PipelineProgressUI

                _logo_path = Path(__file__).parent / "hakili_logo.png"
                _logo_b64 = (
                    base64.b64encode(_logo_path.read_bytes()).decode("utf-8")
                    if _logo_path.exists() else ""
                )
                progress_ui = PipelineProgressUI(
                    logo_b64=_logo_b64,
                    test_label=hakili_test.label if hakili_test else "Correction libre",
                    student_name=transcription_pending.student_name,
                )

                try:
                    phase_a_result = run_grading(
                        result=transcription_pending,
                        on_progress=progress_ui.update,
                    )
                except Exception as _e_g:
                    progress_ui.clear()
                    _show_failure(str(_e_g))
                    st.stop()

                progress_ui.clear()
                st.session_state.single_phase_a = phase_a_result
                # Transcription consommée — relecture terminée, on ne revient
                # plus dessus (évite qu'un ancien texte édité ne réapparaisse
                # si l'enseignant relance une autre copie ensuite).
                st.session_state.single_transcription = None
                st.session_state["transcription_edits"] = {}
                st.rerun()

    # ── Tableau de validation (après Phase A) ─────────────────────────────────
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
        _display_results(st.session_state.single_result, eleve=selected_eleve)


# ── PAGE : TRAITEMENT BATCH ───────────────────────────────────────────────────

elif page == "TRAITEMENT BATCH":
    _page_header("Session de classe", "Analyser toute une classe d'un coup")

    if "batch_results" not in st.session_state:
        st.session_state.batch_results = None
    if "batch_errors" not in st.session_state:
        st.session_state.batch_errors = []
    if "batch_eleves_par_copy_id" not in st.session_state:
        st.session_state.batch_eleves_par_copy_id = {}

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
    st.caption(
        "Un fichier PDF ou photo par élève, nommé avec le prénom et nom de l'élève "
        "(ex : `sawadogo_aminata.pdf`) — le nom et le prénom doivent correspondre à un "
        "élève des Google Sheets, sinon cette copie sera bloquée avant tout traitement."
    )
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
            from src.integrations.google_sheets import get_eleves
            from src.pipeline.pipeline import run_single_copy

            runs_dir = Path(settings.runs_dir)
            results = []
            errors = []
            eleves_par_copy_id: dict[str, dict] = {}
            total = len(copies_folder)

            eleves_batch = _lire_sheets_avec_secours(
                get_eleves, cache_key="eleves", bouton_key="batch_eleves", label="Élèves",
            )
            if eleves_batch is _SHEETS_ECHEC:
                eleves_batch = []

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
                    filename_stem = Path(uploaded.name).stem
                    batch_header.markdown(
                        f"**Traitement en cours** — Copie {i + 1} / {total} : **{filename_stem}**"
                    )
                    global_bar.progress(i / total)

                    # Élève choisi implicitement par correspondance nom de fichier <->
                    # Sheet élèves (une sélection manuelle par fichier n'a pas de sens
                    # pour un lot de 30 copies) — mais toujours vérifié, jamais deviné :
                    # aucune correspondance unique -> copie bloquée avant tout appel IA.
                    matched_eleve = _match_eleve_par_nom_fichier(filename_stem, eleves_batch)
                    if matched_eleve is None:
                        errors.append(
                            f"{filename_stem} : élève introuvable ou ambigu dans les Google "
                            f"Sheets pour ce nom de fichier — copie non traitée."
                        )
                        continue

                    identifiant_hakili_batch = matched_eleve["identifiant_hakili"]
                    student_name_raw = f"{matched_eleve['prenom']} {matched_eleve['nom']}"
                    copy_id = make_copy_id(
                        identifiant_hakili_batch,
                        suffix=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i + 1}",
                    )
                    eleves_par_copy_id[copy_id] = matched_eleve

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
                            identifiant_hakili=identifiant_hakili_batch,
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
            st.session_state.batch_eleves_par_copy_id = eleves_par_copy_id

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
                    r_eleve = st.session_state.batch_eleves_par_copy_id.get(r.copy_id)
                    if r_eleve:
                        def _r_stem(doc_type: str, _eleve=r_eleve) -> str:
                            return nom_fichier_document(
                                nom=_eleve.get("nom", ""), prenom=_eleve.get("prenom", ""),
                                doc_type=doc_type, date=datetime.now().date(),
                            )
                    else:
                        r_slug = (
                            r.student_name.lower().replace(" ", "_").replace("'", "").replace("/", "")
                            if r.student_name else r.copy_id
                        )
                        def _r_stem(doc_type: str, _slug=r_slug) -> str:
                            return f"{doc_type}_{_slug}"
                    with bc1:
                        if r.pdf_path and r.pdf_path.exists():
                            st.download_button(
                                "Rapport — Enseignant",
                                data=r.pdf_path.read_bytes(),
                                file_name=f"{_r_stem('rapport')}.pdf",
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
                                file_name=f"{_r_stem('remediation')}.pdf",
                                mime="application/pdf",
                                key=f"batch_rem_{r.copy_id}",
                                use_container_width=True,
                            )
                            _pdf_preview_expander(r.remediation_pdf_path, key=f"batch_prev_rem_{r.copy_id}", nested=True)


# ── PAGE : GESTION ────────────────────────────────────────────────────────────

elif page == "GESTION":
    _page_header("Gestion — Suivi d'élèves", "Suivi pédagogique et administration")

    # État de connexion propre à cette section — indépendant des autres pages.
    if "gestion_authenticated" not in st.session_state:
        st.session_state.gestion_authenticated = False
        st.session_state.gestion_user = None
        st.session_state.gestion_casquette = None

    # ── PAS LOGUÉ → Formulaire de connexion ───────────────────────────────────
    if not st.session_state.gestion_authenticated:
        st.warning("Veuillez vous connecter pour accéder à la gestion")
        st.divider()

        col1, _ = st.columns([1, 2])
        with col1:
            st.subheader("Connexion")

            from src.integrations.google_sheets import get_personnel

            _personnel_disponible = _lire_sheets_avec_secours(
                get_personnel, cache_key="personnel", bouton_key="login_personnel", label="Personnel",
            )
            if _personnel_disponible is _SHEETS_ECHEC:
                _personnel_disponible = []

            personne_selectionnee = _selectbox_recherchable(
                "Nom", _personnel_disponible,
                format_func=lambda p: f"{p.get('prenom', '')} {p.get('nom', '')}",
                key="gestion_personne_select",
                placeholder="Sélectionner votre nom",
            )

            pin_saisi = st.text_input(
                "Code PIN (4 chiffres)", type="password", max_chars=4, key="gestion_pin",
            )

            if st.button("Se connecter"):
                resultat = authentifier(personne_selectionnee, pin_saisi)

                if resultat.status == "pin_absent":
                    if personne_selectionnee is None:
                        st.error("Veuillez sélectionner votre nom dans la liste.")
                    else:
                        st.error(
                            "Aucun code PIN n'a été configuré pour ce compte — "
                            "contactez le docteur."
                        )
                elif resultat.status == "pin_incorrect":
                    st.error("Code incorrect.")
                else:
                    personne = dict(resultat.personne)
                    if not _roles_valides_de(personne):
                        st.error(
                            f"Rôle non reconnu dans le Sheet ({personne.get('role', '')!r}) — "
                            f"contactez le docteur."
                        )
                    else:
                        st.session_state.gestion_authenticated = True
                        st.session_state.gestion_user = personne
                        st.session_state.gestion_casquette = None
                        st.success(f"Bienvenue {personne['prenom']} {personne['nom']}")
                        st.rerun()

    # ── LOGUÉ → Interface de gestion ──────────────────────────────────────────
    else:
        user_brut = st.session_state.gestion_user
        roles = _roles_valides_de(user_brut)

        if len(roles) > 1:
            # Double rôle (détecté génériquement, voir
            # google_sheets._load_personnel — jamais une liste de noms) :
            # la personne choisit sa casquette active, et peut en changer à
            # tout moment sans se déconnecter. Le choix n'aiguille que vers
            # les vues EXISTANTES ci-dessous (responsable/enseignant),
            # aucune nouvelle vue créée, aucun périmètre mélangé.
            if st.session_state.get("gestion_casquette") not in roles:
                # Défaut Responsable si disponible (documenté au rapport de
                # chantier) plutôt que de bloquer sur un choix forcé — vue
                # d'ensemble du centre, point d'entrée jugé le plus sûr.
                st.session_state.gestion_casquette = (
                    UserRole.responsable_centre.value
                    if UserRole.responsable_centre.value in roles else roles[0]
                )
            st.success(f"Connecté : {user_brut['prenom']} {user_brut['nom']}")
            casquette = st.radio(
                "Vous voulez travailler comme :",
                options=roles,
                format_func=lambda r: _LABELS_CASQUETTE.get(r, r),
                index=roles.index(st.session_state.gestion_casquette),
                key="gestion_casquette_radio",
                horizontal=True,
            )
            st.session_state.gestion_casquette = casquette
        else:
            casquette = roles[0]
            st.success(
                f"Connecté : {user_brut['prenom']} {user_brut['nom']} "
                f"({_LABELS_CASQUETTE.get(casquette, casquette)})"
            )

        user = _vue_utilisateur_pour_casquette(user_brut, casquette)
        is_admin = user["role_enum"] == UserRole.admin

        db = SessionLocal()
        try:
            main_tab_labels = ["Suivi", "Admin"] if is_admin else ["Suivi"]
            main_tabs = st.tabs(main_tab_labels)
            tab_suivi = main_tabs[0]
            tab_admin = main_tabs[1] if is_admin else None

            # ── Onglet Suivi ───────────────────────────────────────────────
            with tab_suivi:
                eleves = _lire_sheets_avec_secours(
                    lambda: get_accessible_eleves(user),
                    cache_key="eleves", bouton_key="suivi_eleves", label="Élèves",
                )

                if eleves is _SHEETS_ECHEC:
                    pass
                elif user["role_enum"] == UserRole.enseignant:
                    # Vue enseignant : UN seul écran (sélection d'UN élève
                    # parmi les siens -> profil + copies + documents, qui
                    # couvre déjà la chronologie) — pas d'onglets Historique/
                    # Comparaison séparés ici : sur un périmètre aussi
                    # restreint (ses seuls élèves), ils feraient double
                    # emploi avec ce même contenu (voir rapport de chantier).
                    st.subheader("Mes élèves")
                    if not eleves:
                        affectations_txt = ", ".join(
                            f"{centre or '?'} / {classe or '?'}"
                            for centre, classe in user.get("affectations", [])
                        ) or "aucune affectation renseignée"
                        st.info(f"Aucun élève trouvé pour vos affectations : {affectations_txt}.")
                    else:
                        _render_profil_enseignant(db, user, eleves)
                else:
                    sub_tab1, sub_tab2, sub_tab3 = st.tabs(
                        ["Historique", "Tableau des élèves", "Comparaison"]
                    )

                    with sub_tab1:
                        st.subheader("Historique d'un élève")
                        if not eleves:
                            st.info("Aucun élève accessible")
                        else:
                            eleve = _selectbox_recherchable(
                                "Élève", eleves,
                                format_func=lambda e: f"{e.get('prenom', '')} {e.get('nom', '')}",
                                key="historique_eleve_select",
                                placeholder="Sélectionner un élève",
                            )
                            if eleve is not None:
                                if not can_access_eleve(db, user, eleve):
                                    st.error("Vous n'avez pas accès à cet élève")
                                else:
                                    afficher_historique(eleve, db)

                    with sub_tab2:
                        st.subheader("Tableau des élèves")

                        if not eleves:
                            st.info("Aucun élève accessible")
                        elif user["role_enum"] == UserRole.responsable_centre:
                            # Vue dédiée responsable : pastille de tendance,
                            # tri avec les baisses en premier — voir chantier
                            # tendance. Couvre tout son centre (voir
                            # correction de la casquette Responsable).
                            _render_tableau_responsable(db, eleves)
                        elif is_admin:
                            # SEULE vue où contact_parents et identifiant_hakili
                            # sont affichés : l'admin gère les inscriptions et
                            # contacte les familles — exception validée, jamais
                            # étendue aux autres rôles (voir rapport de chantier).
                            import pandas as pd

                            recherche_admin = st.text_input(
                                "Rechercher un élève",
                                key="admin_eleves_recherche",
                                placeholder="Rechercher par nom ou prénom...",
                            )
                            eleves_affiches = eleves
                            if recherche_admin.strip():
                                eleves_affiches = [
                                    e for e in eleves
                                    if _correspond_recherche(
                                        recherche_admin, f"{e.get('prenom', '')} {e.get('nom', '')}"
                                    )
                                ]

                            st.write(
                                f"**{len(eleves_affiches)} élève(s)** affiché(s) sur "
                                f"{len(eleves)} accessible(s)"
                            )

                            df_eleves = pd.DataFrame([
                                {
                                    "Nom": eleve.get("nom"),
                                    "Prénom": eleve.get("prenom"),
                                    "Classe": eleve.get("classe"),
                                    "Centre": eleve.get("centre"),
                                    "École": eleve.get("ecole"),
                                    "Boursier": eleve.get("boursier"),
                                    "Redoublant": eleve.get("reprend_la_classe"),
                                    # str() : Google Sheets renvoie parfois un numéro de
                                    # téléphone en nombre (sans les espaces), parfois en
                                    # texte (avec) — coercion uniforme pour un affichage
                                    # cohérent et pour éviter une colonne pandas à types
                                    # mixtes (int/str).
                                    "Contact parents": str(eleve.get("contact_parents") or ""),
                                    "Identifiant": eleve.get("identifiant_hakili"),
                                }
                                for eleve in eleves_affiches
                            ])
                            st.dataframe(
                                df_eleves,
                                use_container_width=True,
                                hide_index=True,
                            )
                        else:
                            # Rôle reconnu mais sans vue dédiée ici (ne devrait
                            # pas arriver, le rôle est déjà validé à la
                            # connexion) — tableau minimal, JAMAIS de
                            # contact_parents ni d'identifiant par défaut.
                            import pandas as pd

                            st.write(f"**{len(eleves)} élève(s)** accessible(s)")
                            df_eleves = pd.DataFrame([
                                {
                                    "Nom": eleve.get("nom"),
                                    "Prénom": eleve.get("prenom"),
                                    "Classe": eleve.get("classe"),
                                    "Centre": eleve.get("centre"),
                                    "École": eleve.get("ecole"),
                                    "Boursier": eleve.get("boursier"),
                                    "Redoublant": eleve.get("reprend_la_classe"),
                                }
                                for eleve in eleves
                            ])
                            st.dataframe(
                                df_eleves,
                                use_container_width=True,
                                hide_index=True,
                            )

                    with sub_tab3:
                        if not eleves:
                            st.info("Aucun élève accessible")
                        else:
                            _render_comparaison_view(db, user, eleves)

            # ── Onglet Admin (visible admin uniquement) ───────────────────────
            if tab_admin is not None:
                with tab_admin:
                    st.header("Administration")
                    _admin_view_stats(db)

            st.divider()
            if st.button("Déconnexion"):
                st.session_state.gestion_authenticated = False
                st.session_state.gestion_user = None
                st.session_state.gestion_casquette = None
                st.rerun()
        finally:
            db.close()
