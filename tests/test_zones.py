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
    SCORE_RECALAGE_MIN,
    GabaritIncoherent,
    decouper_zones,
    extraire_gabarit,
    recaler_page,
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


def test_le_gabarit_survit_a_un_changement_de_teinte(tmp_path: Path) -> None:
    """
    Le sujet est un document vivant : régénéré, il changera de teintes.

    Les règles sont exprimées en plages, pas en égalité aux valeurs relevées sur
    les sujets d'aujourd'hui. Une égalité stricte aurait fait échouer la lecture
    à la première retouche — et l'échec aurait été **total** (zéro cadre trouvé),
    pas partiel : le module 2 se serait arrêté net sans autre explication.
    """
    autre_teinte = _sujet_factice(
        tmp_path / "retouche.pdf", [("N1", 1), ("G1", 8)], gris=(0.35, 0.35, 0.35)
    )
    cadres = {c.code: c.format for c in extraire_gabarit(autre_teinte).cadres}
    assert cadres == {"N1": "qcm", "G1": "redige"}


def test_le_nombre_de_lignes_d_une_question_redigee_peut_changer(tmp_path: Path) -> None:
    """Au-delà de deux lignes, c'est une rédaction — que le sujet en offre 6, 8 ou 10."""
    chemin = _sujet_factice(tmp_path / "six_lignes.pdf", [("G13", 6)])
    cadre = extraire_gabarit(chemin).cadres[0]
    assert (cadre.format, cadre.lignes) == ("redige", 6)


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


def test_un_scan_brut_ne_se_decoupe_pas_sans_recalage(sujet: Path, tmp_path: Path) -> None:
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
        decouper_zones(gabarit, [scan], tmp_path / "zones", recaler=False)


def test_une_page_etrangere_au_sujet_est_refusee(sujet: Path, tmp_path: Path) -> None:
    """Rien à quoi se raccrocher : mieux vaut le dire que découper au hasard."""
    gabarit = extraire_gabarit(sujet)
    scan = tmp_path / "scan_p1.png"
    Image.new("L", (1700, 2320), color=255).save(scan)
    with pytest.raises(GabaritIncoherent, match="aucune page du scan"):
        decouper_zones(gabarit, [scan], tmp_path / "zones")


# ── Recalage ──────────────────────────────────────────────────────────────────

def _fausse_numerisation(
    chemin_pdf: Path, destination: Path, *, inclinaison: float,
    echelle: float = 1.0, marge: int = 30, page: int = 0,
) -> Path:
    """Imite ce que rend un scanner : page penchée, redimensionnée, avec du blanc autour."""
    doc = fitz.open(chemin_pdf)
    brut = destination.parent / f"_brut_{destination.name}"
    doc.load_page(page).get_pixmap(dpi=150).save(str(brut))
    doc.close()

    with Image.open(brut) as ouverte:
        image = ouverte.convert("L")
    image = image.rotate(inclinaison, resample=Image.BICUBIC, fillcolor=255)
    image = image.resize(
        (int(image.width * echelle), int(image.height * echelle)), Image.BICUBIC
    )
    toile = Image.new("L", (image.width + 2 * marge, image.height + 2 * marge), 255)
    toile.paste(image, (marge, marge))
    toile.save(destination)
    return destination


def _sujet_rempli(tmp_path: Path, code_rempli: str = "N2") -> tuple[Path, Path]:
    """Un sujet et le même sujet avec l'écriture d'un élève dans un seul cadre."""
    vierge = _sujet_factice(tmp_path / "sujet.pdf", [("N1", 1), ("N2", 2), ("G1", 8)])
    cadre = next(c for c in extraire_gabarit(vierge).cadres if c.code == code_rempli)
    doc = fitz.open(vierge)
    page = doc.load_page(0)
    page.insert_text(
        fitz.Point(cadre.x0 + 40, cadre.y0 + 30), "3x + 5 = 17 donc x = 4",
        fontsize=11, color=(0, 0, 0),
    )
    rempli = tmp_path / "rempli.pdf"
    doc.save(rempli)
    doc.close()
    return vierge, rempli


def test_l_inclinaison_est_mesuree_sans_faire_tourner_la_page(tmp_path: Path) -> None:
    """
    Le piège qui rendait le redressement décoratif.

    Estimer l'inclinaison en faisant tourner l'image pour comparer les résultats
    ne marche pas : la rotation ré-échantillonne, un trait fin s'étale sur deux
    pixels dont aucun n'atteint le seuil, et le trait disparaît. L'angle 0, seul
    à ne rien ré-échantillonner, gardait toute son encre et l'emportait donc
    **quelle que soit l'inclinaison réelle** — mesuré : 2 616 pixels d'encre à 0°
    contre moins de 600 partout ailleurs.

    Ce test échouerait sur cette version-là : il exige que l'angle soit retrouvé.
    """
    vierge, _ = _sujet_rempli(tmp_path)
    gabarit = extraire_gabarit(vierge)

    for inclinaison in (-1.25, 1.0, 2.5):
        scan = _fausse_numerisation(
            vierge, tmp_path / f"scan{inclinaison}.png", inclinaison=inclinaison
        )
        with Image.open(scan) as image:
            recalage = recaler_page(image, gabarit.cadres_de_page(1), gabarit)
        # le recalage annule l'inclinaison : les signes sont opposés
        assert recalage.angle == pytest.approx(-inclinaison, abs=0.15), (
            f"page penchée de {inclinaison}° : angle mesuré {recalage.angle}°"
        )


def test_une_page_scannee_est_recalee_avant_la_decoupe(tmp_path: Path) -> None:
    """La réponse doit atterrir dans la zone de sa question, pas dans la voisine."""
    vierge, rempli = _sujet_rempli(tmp_path)
    gabarit = extraire_gabarit(vierge)
    scan = _fausse_numerisation(
        rempli, tmp_path / "scan.png", inclinaison=-1.25, echelle=1.03
    )

    zones = {z.code: z for z in decouper_zones(gabarit, [scan], tmp_path / "zones")}
    assert not zones["N2"].vide, "la réponse de l'élève a été perdue au recalage"
    assert zones["N1"].vide and zones["G1"].vide, "une zone vierge a attrapé la voisine"


def test_le_recalage_rend_compte_de_ce_qu_il_a_retrouve(tmp_path: Path) -> None:
    """Le score est une part de bords de cadre, pas un indicateur décoratif."""
    vierge, _ = _sujet_rempli(tmp_path)
    gabarit = extraire_gabarit(vierge)
    scan = _fausse_numerisation(vierge, tmp_path / "scan.png", inclinaison=1.0)

    with Image.open(scan) as image:
        recalage = recaler_page(image, gabarit.cadres_de_page(1), gabarit)
    assert recalage.score >= SCORE_RECALAGE_MIN
    assert recalage.ajuste

    with Image.open(scan) as image:
        blanche = Image.new("L", image.size, 255)
    assert recaler_page(blanche, gabarit.cadres_de_page(1), gabarit).score == 0.0


# ── Appariement des pages ─────────────────────────────────────────────────────

def test_les_pages_en_trop_du_scan_sont_ecartees(tmp_path: Path) -> None:
    """
    Le scan ne suit pas la pagination du sujet.

    Mesuré sur un scan réel : **12 pages pour un sujet qui en compte 10**,
    l'enseignant ayant numérisé la page de garde et la page de renseignements
    avec le reste. Découpées dans l'ordre, toutes les zones auraient été prises
    sur la mauvaise page — et le résultat aurait eu l'air normal, chaque zone
    contenant bien de l'écriture.
    """
    doc = fitz.open()
    for cadres in ([("N1", 1), ("N2", 2)], [("G1", 8), ("G2", 2), ("G3", 1)]):
        page = doc.new_page(width=595.3, height=841.9)
        y = 60.0
        for code, lignes in cadres:
            rect = _dessiner_cadre(page, code, y, lignes)
            y = rect.y1 + 12
    sujet_2p = tmp_path / "sujet2p.pdf"
    doc.save(sujet_2p)
    doc.close()
    gabarit = extraire_gabarit(sujet_2p)

    # une page de garde et une page de renseignements s'intercalent
    intruse = tmp_path / "garde.png"
    garde = Image.new("L", (1290, 1810), 255)
    garde.paste(Image.new("L", (400, 30), 0), (200, 200))
    garde.save(intruse)

    pages = [
        intruse,
        _fausse_numerisation(sujet_2p, tmp_path / "s1.png", inclinaison=-1.0, page=0),
        intruse,
        _fausse_numerisation(sujet_2p, tmp_path / "s2.png", inclinaison=0.75, page=1),
    ]

    zones = decouper_zones(gabarit, pages, tmp_path / "zones")
    assert {z.code for z in zones} == {"N1", "N2", "G1", "G2", "G3"}
    # chaque code retrouve la page du sujet où il est imprimé
    par_code = {z.code: z.page for z in zones}
    assert par_code["N1"] == 1 and par_code["G3"] == 2


# ── Lignes de guidage imprimées ───────────────────────────────────────────────

def test_le_gabarit_releve_la_position_des_lignes(sujet: Path) -> None:
    """La position des lignes est lue dans le PDF, comme le reste du gabarit."""
    cadres = {c.code: c for c in extraire_gabarit(sujet).cadres}
    assert len(cadres["N2"].lignes_y) == 2 and len(cadres["G1"].lignes_y) == 8
    assert not cadres["N1"].lignes_y or len(cadres["N1"].lignes_y) == 1
    # les bandes sont dans le cadre et ordonnées
    for haut, bas in cadres["G1"].lignes_y:
        assert cadres["G1"].y0 <= haut < bas <= cadres["G1"].y1 + 1
    assert cadres["G1"].lignes_y == sorted(cadres["G1"].lignes_y)


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_les_lignes_de_guidage_pavent_la_zone_de_reponse(niveau: str) -> None:
    """
    Ce que les « lignes de guidage » sont réellement — et ce que ça interdit.

    Elles ne sont pas des traits : ce sont des bandes d'environ 21 pt,
    **jointives**, qui pavent toute la zone d'écriture du cadre. Ce que l'élève
    voit est un aplat gris, pas un lignage.

    Ce test est là pour empêcher de re-dériver un repli qui semble évident et qui
    ne marche pas : « si le tramage laser rend les lignes noires, on les effacera
    à leur position, le gabarit la connaît ». Leur position est la zone de
    réponse tout entière — l'effacement l'effacerait entière. Le retrait d'une
    trame est un problème de filtrage, pas de position.
    """
    chemin = _SUJETS / f"Test_diagnostique_entree_{niveau}.pdf"
    if not chemin.exists():
        pytest.skip(f"{chemin.name} absent — sujets non versionnés (.gitignore)")

    for cadre in extraire_gabarit(chemin).cadres:
        for (_, bas), (haut_suivant, _) in zip(cadre.lignes_y, cadre.lignes_y[1:]):
            assert haut_suivant - bas < 1.0, (
                f"{cadre.code} : les bandes ne sont pas jointives "
                f"({haut_suivant - bas:.2f} pt d'écart) — la géométrie a changé, "
                f"relire le commentaire de CadreReponse.lignes_y"
            )


# ── Orientation des zones ─────────────────────────────────────────────────────

def test_une_question_de_construction_n_est_pas_diagnosticable(tmp_path: Path) -> None:
    """
    Les 7 questions `construction` attendent un tracé, pas du texte.

    Elles se découpent comme les autres, mais le module 4 n'a rien à y
    reconnaître : juger une perpendiculaire demande de mesurer la figure. Elles
    partent vers la saisie humaine (module 8) plutôt que vers un diagnostic
    inventé.
    """
    chemin = _sujet_factice(tmp_path / "trace.pdf", [("G8", 0)], gris=_GRIS_TRACE)
    gabarit = extraire_gabarit(chemin)
    doc = fitz.open(chemin)
    cadre = gabarit.cadres[0]
    doc.load_page(0).draw_line(
        fitz.Point(cadre.x0 + 30, cadre.y0 + 20),
        fitz.Point(cadre.x0 + 200, cadre.y0 + 30),
        color=(0, 0, 0), width=2,
    )
    rempli = tmp_path / "rempli.pdf"
    doc.save(rempli)
    doc.close()

    zone = decouper_zones(gabarit, _rendre(rempli, tmp_path), tmp_path / "zones")[0]
    assert not zone.vide, "le tracé de l'élève doit être conservé"
    assert not zone.diagnosticable, "une construction ne part pas au diagnostic automatique"


def test_une_zone_vierge_n_est_pas_diagnosticable(sujet: Path, tmp_path: Path) -> None:
    """« Pas de réponse » se constate, il n'y a rien à faire lire à un modèle."""
    gabarit = extraire_gabarit(sujet)
    zones = decouper_zones(gabarit, _rendre(sujet, tmp_path), tmp_path / "zones")
    assert all(z.vide and not z.diagnosticable for z in zones)


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


# ── Branchement sur le pipeline ───────────────────────────────────────────────

def test_un_test_archive_ne_passe_pas_par_les_zones(tmp_path: Path) -> None:
    """
    Les tests archivés gardent la transcription pleine page.

    Ils n'ont pas de sujet à cadres ancrés — il n'y a pas de gabarit à lire, donc
    rien à découper. La condition porte sur `sujet_pdf`, pas sur une liste de
    tests à tenir à jour.
    """
    from src.pipeline.pipeline import _lire_zones

    zones, anomalies = _lire_zones(
        copy_id="copie-essai", bareme_id="hakili_3e_v1", pages=[], sortie=tmp_path
    )
    assert zones == [] and anomalies == []


def test_un_bareme_inconnu_ne_fait_pas_echouer_la_correction(tmp_path: Path) -> None:
    """Le mode libre n'a pas de `bareme_id` : l'étape se retire, elle ne casse pas."""
    from src.pipeline.pipeline import _lire_zones

    assert _lire_zones(
        copy_id="copie-essai", bareme_id="", pages=[], sortie=tmp_path
    ) == ([], [])


def test_une_copie_illisible_est_signalee_sans_arreter_la_correction(tmp_path: Path) -> None:
    """
    Rien de ce qui rate ici n'arrête la correction.

    Le module 4 n'existe pas encore : personne ne consomme les zones. Faire
    échouer une copie sur une étape dont plus rien ne dépend en aval casserait la
    correction pour un service qui n'est pas rendu. L'anomalie est signalée à
    l'enseignant — c'est ce qui compte, un sujet d'une autre version se voit là.
    """
    from src.pipeline.pipeline import _lire_zones

    chemin = _SUJETS / "Test_diagnostique_entree_6eme.pdf"
    if not chemin.exists():
        pytest.skip(f"{chemin.name} absent — sujets non versionnés (.gitignore)")

    blanche = tmp_path / "page_01.png"
    Image.new("L", (1700, 2320), color=255).save(blanche)

    zones, anomalies = _lire_zones(
        copy_id="copie-essai", bareme_id="urie_6eme",
        pages=[blanche] * 10, sortie=tmp_path,
    )
    assert zones == []
    assert [a.code for a in anomalies] == ["ZONES_ILLISIBLES"]
    assert all(a.severity == "warning" for a in anomalies)


def test_le_gabarit_des_7_sujets_concorde_avec_le_format_du_bareme(tmp_path: Path) -> None:
    """Le garde-fou d'exploitation, monté tel qu'il tournera : sujet contre barème."""
    from src.knowledge.test_registry import get_registry

    for niveau in _NIVEAUX:
        chemin = _SUJETS / f"Test_diagnostique_entree_{niveau}.pdf"
        if not chemin.exists():
            pytest.skip(f"{chemin.name} absent — sujets non versionnés (.gitignore)")
        test = get_registry().get_test(f"urie_{niveau}")
        assert test is not None and test.sujet_pdf is not None
        assert test.formats, f"urie_{niveau} : le barème ne porte aucun format"
        assert verifier_gabarit(extraire_gabarit(chemin), test.formats) == []


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
