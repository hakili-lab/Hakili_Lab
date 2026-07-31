"""
Tests de la lecture des copies par zones (src/pipeline/zones.py, module 2).

Deux niveaux :

1. Sur un **sujet fabriqué** dans le test lui-même, qui reproduit la signature
   graphique des vrais sujets (mêmes gris, mêmes largeurs, code dans le coin du
   cadre). C'est ce qui rend ces tests exécutables partout : les 7 vrais sujets
   sont des PDF non versionnés (`.gitignore`), la CI ne les a pas.

2. Sur les **7 vrais sujets**, quand ils sont présents sur la machine. C'est le
   test qui compte vraiment — il vérifie les 280 cadres contre les barèmes — mais
   il est ignoré faute de fichiers plutôt que d'échouer.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
import pytest
import yaml
from PIL import Image

from src.pipeline.zones import (
    GabaritIncoherent,
    decouper_zones,
    extraire_gabarit,
    verifier_gabarit,
)

_RACINE = Path(__file__).parent.parent
_SUJETS = _RACINE / "data" / "Documents"
_KB = _RACINE / "data" / "knowledge"
_NIVEAUX = ("6eme", "5eme", "4eme", "3eme", "2ndeC", "1ereD", "tleD")

_GRIS_CADRE = (0.478431, 0.478431, 0.478431)
_GRIS_TRACE = (0.600000, 0.600000, 0.600000)
_GRIS_LIGNE = (0.749020, 0.749020, 0.749020)
_BLANC = (1.0, 1.0, 1.0)


def _dessiner_cadre(page, code: str, y: float, lignes: int, gris=_GRIS_CADRE) -> fitz.Rect:
    """Reproduit un cadre de réponse : aplat gris, intérieur blanc, code en haut à gauche."""
    hauteur = 16 + max(lignes, 1) * 21
    cadre = fitz.Rect(45.7, y, 45.7 + 503.9, y + hauteur)
    page.draw_rect(cadre, color=None, fill=gris)
    page.draw_rect(cadre + (1, 1, -1, -1), color=None, fill=_BLANC)
    page.insert_text(fitz.Point(cadre.x0 + 6, cadre.y0 + 10), code, fontsize=8)
    for i in range(lignes):
        ligne = fitz.Rect(cadre.x0 + 9, cadre.y0 + 14 + i * 21, cadre.x1 - 9, cadre.y0 + 35 + i * 21)
        page.draw_rect(ligne, color=None, fill=_GRIS_LIGNE)
    return cadre


def _sujet_factice(chemin: Path, cadres: list[tuple[str, int]], gris=_GRIS_CADRE) -> Path:
    """Un sujet d'une page portant les cadres demandés — `(code, nombre de lignes)`."""
    doc = fitz.open()
    page = doc.new_page(width=595.3, height=841.9)
    y = 60.0
    for code, lignes in cadres:
        rect = _dessiner_cadre(page, code, y, lignes, gris)
        # le même code figure aussi en marge, à côté de l'énoncé : c'est le cas
        # que l'association par inclusion doit départager
        page.insert_text(fitz.Point(20, y + 10), code, fontsize=8)
        y = rect.y1 + 12
    doc.save(chemin)
    doc.close()
    return chemin


@pytest.fixture
def sujet(tmp_path: Path) -> Path:
    return _sujet_factice(
        tmp_path / "sujet.pdf",
        [("N1", 1), ("N2", 2), ("G1", 8)],
    )


# ── Gabarit ───────────────────────────────────────────────────────────────────

def test_un_cadre_par_question_avec_son_code(sujet: Path) -> None:
    gabarit = extraire_gabarit(sujet)
    assert [c.code for c in gabarit.cadres] == ["N1", "N2", "G1"]
    assert all(c.page == 1 for c in gabarit.cadres)


def test_le_format_se_deduit_du_nombre_de_lignes(sujet: Path) -> None:
    formats = {c.code: c.format for c in extraire_gabarit(sujet).cadres}
    assert formats == {"N1": "qcm", "N2": "court", "G1": "redige"}


def test_un_cadre_sans_ligne_est_une_question_de_construction(tmp_path: Path) -> None:
    chemin = _sujet_factice(tmp_path / "trace.pdf", [("G8", 0)], gris=_GRIS_TRACE)
    cadre = extraire_gabarit(chemin).cadres[0]
    assert (cadre.format, cadre.lignes) == ("construction", 0)


def test_le_code_en_marge_ne_cree_pas_de_cadre(sujet: Path) -> None:
    # trois codes en marge + trois dans les cadres : six occurrences, trois cadres
    assert len(extraire_gabarit(sujet).cadres) == 3


def test_un_code_en_double_est_refuse(tmp_path: Path) -> None:
    chemin = _sujet_factice(tmp_path / "double.pdf", [("N1", 1), ("N1", 2)])
    with pytest.raises(GabaritIncoherent, match="N1"):
        extraire_gabarit(chemin)


def test_un_cadre_sans_code_est_refuse(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595.3, height=841.9)
    cadre = fitz.Rect(45.7, 60, 45.7 + 503.9, 120)
    page.draw_rect(cadre, color=None, fill=_GRIS_CADRE)
    page.draw_rect(cadre + (1, 1, -1, -1), color=None, fill=_BLANC)
    chemin = tmp_path / "muet.pdf"
    doc.save(chemin)
    doc.close()
    with pytest.raises(GabaritIncoherent, match="aucun code"):
        extraire_gabarit(chemin)


def test_un_pdf_quelconque_est_refuse(tmp_path: Path) -> None:
    doc = fitz.open()
    doc.new_page().insert_text(fitz.Point(72, 72), "Une note de service.")
    chemin = tmp_path / "autre.pdf"
    doc.save(chemin)
    doc.close()
    with pytest.raises(GabaritIncoherent, match="aucun cadre"):
        extraire_gabarit(chemin)


# ── Confrontation au barème ───────────────────────────────────────────────────

def test_gabarit_conforme_au_bareme(sujet: Path) -> None:
    attendu = {"N1": "qcm", "N2": "court", "G1": "redige"}
    assert verifier_gabarit(extraire_gabarit(sujet), attendu) == []


def test_les_ecarts_avec_le_bareme_sont_nommes(sujet: Path) -> None:
    gabarit = extraire_gabarit(sujet)
    anomalies = verifier_gabarit(gabarit, {"N1": "qcm", "N2": "redige", "N9": "court"})
    joint = " | ".join(anomalies)
    assert "N9" in joint and "absent du sujet" in joint       # attendue, pas imprimée
    assert "G1" in joint and "inconnu du barème" in joint     # imprimée, pas attendue
    assert "N2" in joint and "'redige'" in joint              # format divergent


# ── Découpe ───────────────────────────────────────────────────────────────────

def _rendre(chemin_pdf: Path, dossier: Path, dpi: int = 150) -> list[Path]:
    doc = fitz.open(chemin_pdf)
    pages = []
    for i, page in enumerate(doc):
        chemin = dossier / f"page_{i + 1:02d}.png"
        page.get_pixmap(dpi=dpi).save(str(chemin))
        pages.append(chemin)
    doc.close()
    return pages


def test_une_zone_par_cadre_nommee_par_son_code(sujet: Path, tmp_path: Path) -> None:
    gabarit = extraire_gabarit(sujet)
    zones = decouper_zones(gabarit, _rendre(sujet, tmp_path), tmp_path / "zones")
    assert {z.code for z in zones} == {"N1", "N2", "G1"}
    assert all(z.chemin.exists() and z.chemin.name == f"{z.code}.png" for z in zones)


def test_les_lignes_de_guidage_disparaissent(sujet: Path, tmp_path: Path) -> None:
    """Un cadre vierge doit ressortir entièrement blanc, lignes comprises."""
    gabarit = extraire_gabarit(sujet)
    zones = decouper_zones(gabarit, _rendre(sujet, tmp_path), tmp_path / "zones")
    for zone in zones:
        pixels = np.asarray(Image.open(zone.chemin))
        assert pixels.min() == 255, f"{zone.code} garde des pixels de guidage"
        assert zone.vide


def test_l_ecriture_de_l_eleve_est_conservee(tmp_path: Path) -> None:
    """La même page, avec un trait sombre dans un seul cadre."""
    chemin = _sujet_factice(tmp_path / "s.pdf", [("N1", 1), ("N2", 2)])
    doc = fitz.open(chemin)
    page = doc.load_page(0)
    cadre = next(c for c in extraire_gabarit(chemin).cadres if c.code == "N2")
    page.draw_line(
        fitz.Point(cadre.x0 + 40, cadre.y0 + 25),
        fitz.Point(cadre.x0 + 300, cadre.y0 + 25),
        color=(0, 0, 0), width=2,
    )
    rempli = tmp_path / "rempli.pdf"
    doc.save(rempli)
    doc.close()

    gabarit = extraire_gabarit(chemin)
    zones = {z.code: z for z in decouper_zones(gabarit, _rendre(rempli, tmp_path), tmp_path / "z")}
    assert not zones["N2"].vide, "le trait de l'élève a été effacé avec les lignes"
    assert zones["N1"].vide, "un cadre resté vierge est signalé comme rempli"
    assert np.asarray(Image.open(zones["N2"].chemin)).min() < 140


def test_une_page_manquante_fait_echouer_la_decoupe(sujet: Path, tmp_path: Path) -> None:
    gabarit = extraire_gabarit(sujet)
    with pytest.raises(GabaritIncoherent, match="page"):
        decouper_zones(gabarit, [], tmp_path / "zones")


def test_un_scan_brut_est_refuse_avant_decoupe(sujet: Path, tmp_path: Path) -> None:
    """
    Les proportions d'un scan ne sont pas celles du sujet.

    Mesuré sur un scan réel (HP Scan, 200 DPI) : largeur 612 pt au lieu de
    595,3 et hauteur variant de 835 à 851 pt d'une feuille à l'autre du même
    fichier. Découpé tel quel, le décalage atteint plusieurs millimètres en bas
    de page — assez pour attraper la ligne de la question voisine, pas assez
    pour que le résultat ait l'air faux.
    """
    gabarit = extraire_gabarit(sujet)
    scan = tmp_path / "scan_p1.png"
    Image.new("L", (1700, 2320), color=255).save(scan)  # 612 × 835 pt à 200 DPI
    with pytest.raises(GabaritIncoherent, match="recalée"):
        decouper_zones(gabarit, [scan], tmp_path / "zones")


def test_resolution_native_d_un_scan(tmp_path: Path) -> None:
    """Un PDF de scan annonce sa définition ; un PDF vectoriel n'en a pas."""
    from src.pipeline.zones import resolution_scan

    page_image = tmp_path / "page.png"
    Image.new("L", (1700, 2200), color=255).save(page_image)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)      # 1700 px / (612/72) po = 200 DPI
    page.insert_image(page.rect, filename=str(page_image))
    scanne = tmp_path / "scanne.pdf"
    doc.save(scanne)
    doc.close()

    assert resolution_scan(scanne) == 200
    assert resolution_scan(_sujet_factice(tmp_path / "vectoriel.pdf", [("N1", 1)])) is None


# ── Les 7 vrais sujets ────────────────────────────────────────────────────────

def _bareme(niveau: str) -> dict[str, str]:
    chemin = _KB / f"bareme_urie_{niveau}.yaml"
    data = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    return {q["code"]: q["format"] for q in data["questions"]}


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_les_40_cadres_de_chaque_sujet_reel(niveau: str) -> None:
    """280 cadres sur les 7 sujets, chacun conforme au barème du référentiel."""
    chemin = _SUJETS / f"Test_diagnostique_entree_{niveau}.pdf"
    if not chemin.exists():
        pytest.skip(f"{chemin.name} absent — sujets non versionnés (.gitignore)")

    gabarit = extraire_gabarit(chemin)
    assert len(gabarit.cadres) == 40
    assert verifier_gabarit(gabarit, _bareme(niveau)) == []
