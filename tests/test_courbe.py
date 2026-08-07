from datetime import date
from types import SimpleNamespace

from src.core.courbe import construire_courbe


def _copie(notes_finales, date_soumission):
    return SimpleNamespace(notes_finales=notes_finales, date_soumission=date_soumission)


def test_zero_copie_aucune_courbe():
    assert construire_courbe([]) is None


def test_une_seule_copie_aucune_courbe():
    assert construire_courbe([_copie(15.0, date(2026, 1, 1))]) is None


def test_notes_null_ignorees_dans_le_compte():
    copies = [_copie(None, date(2026, 1, 1)), _copie(15.0, date(2026, 2, 1))]
    assert construire_courbe(copies) is None


def test_deux_copies_tracent_une_courbe():
    copies = [_copie(10.0, date(2026, 1, 1)), _copie(14.0, date(2026, 2, 1))]
    courbe = construire_courbe(copies)
    assert courbe is not None
    assert len(courbe["points"]) == 2
    assert courbe["trace"].startswith("M ")
    assert courbe["dernier"]["note"] == 14.0


def test_ordre_entree_quelconque_trie_par_date():
    copies = [_copie(14.0, date(2026, 2, 1)), _copie(10.0, date(2026, 1, 1))]
    courbe = construire_courbe(copies)
    assert [p["note"] for p in courbe["points"]] == [10.0, 14.0]


def test_note_20_en_haut_note_0_en_bas():
    """En SVG, y croît vers le bas : la meilleure note doit avoir le plus
    petit y, la pire le plus grand -- sinon la courbe se lit à l'envers."""
    copies = [_copie(0.0, date(2026, 1, 1)), _copie(20.0, date(2026, 2, 1))]
    courbe = construire_courbe(copies)
    y_zero, y_vingt = courbe["points"][0]["y"], courbe["points"][1]["y"]
    assert y_vingt < y_zero


def test_reperes_y_couvrent_0_10_20():
    copies = [_copie(10.0, date(2026, 1, 1)), _copie(14.0, date(2026, 2, 1))]
    courbe = construire_courbe(copies)
    assert [r["valeur"] for r in courbe["reperes_y"]] == [0, 10, 20]


def test_points_espaces_regulierement_en_x():
    copies = [_copie(v, date(2026, i + 1, 1)) for i, v in enumerate([8.0, 12.0, 16.0, 10.0])]
    courbe = construire_courbe(copies)
    xs = [p["x"] for p in courbe["points"]]
    ecarts = [round(xs[i + 1] - xs[i], 3) for i in range(len(xs) - 1)]
    assert len(set(ecarts)) == 1
