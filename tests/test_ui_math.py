"""
Tests des helpers de notation mathématique de l'affichage.

_mh : HTML (st.markdown unsafe_allow_html=True) — symboles Unicode natifs
      conservés (le navigateur les rend), exposants/fractions en sup/sub,
      échappement HTML systématique.
_mt : texte pur (labels d'expander) — symboles Unicode + exposants ²³,
      jamais de balises HTML.
"""
# Ces fonctions vivaient dans l'ancienne interface Streamlit et exigeaient de l'importer pour être
# importées. Elles sont désormais dans src/services/affichage_math.py : le test
# ne dépend plus d'aucun framework d'interface.
from src.services.affichage_math import math_html as _mh  # noqa: E402
from src.services.affichage_math import math_texte as _mt  # noqa: E402


# ── _mh : rendu HTML ──────────────────────────────────────────────────────────

def test_mh_inequation_reelle():
    out = _mh("-3x >= 3 => x <= -1")
    assert "≥" in out and "≤" in out and "→" in out
    assert ">=" not in out and "=>" not in out


def test_mh_exposants_et_fractions():
    out = _mh("A = 2^21 et B = 41/4")
    assert "<sup>21</sup>" in out
    assert "<sup>41</sup>&frasl;<sub>4</sub>" in out


def test_mh_unicode_natif_conserve():
    # Dans le navigateur, pas de dégradation police : ∈ ⊂ √ restent intacts
    out = _mh("8 ∈ D et D ⊂ IN")
    assert "∈" in out and "⊂" in out
    assert "appartient" not in out  # la version française est réservée au PDF


def test_mh_echappement_html():
    out = _mh("reponse: x<5 & y>2")
    assert "&lt;5" in out and "&gt;2" in out and "&amp;" in out


def test_mh_humanise_les_ids():
    out = _mh("Erreur en Q_NUM_04 et Q_GEO_07")
    assert "Num. 4" in out and "Geo. 7" in out


# ── _mt : rendu texte pur ─────────────────────────────────────────────────────

def test_mt_sans_balises_html():
    out = _mt("2^2 puis x <= -1 et 5/7 - 2/3")
    assert "<" not in out and ">" not in out


def test_mt_exposants_unicode():
    assert "2²" in _mt("2^2")
    assert "2²¹" in _mt("2^21")
    assert "2⁻²" in _mt("2^-2")
    assert "2³⁻⁵" in _mt("2^(3-5)")


def test_mt_comparaisons():
    out = _mt("x >= 1 => x != 0")
    assert "≥" in out and "→" in out and "≠" in out


def test_mt_vecteurs_combinants():
    # AB⃗ (flèche combinante, mal rendue par les navigateurs) → AB→
    out = _mt("AB⃗ + BC⃗ = AC⃗")
    assert "⃗" not in out and "→" in out
