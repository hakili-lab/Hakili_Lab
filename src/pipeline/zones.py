"""
Lecture des copies par zones — module 2 du chantier Urie v2.

Transforme un sujet rempli et scanné en une liste `(code_question, image)`.

**Écart assumé avec `guide-urie.md`.** Le guide prescrit de détecter les
rectangles sur le scan puis de lire au OCR le code typographié dans le coin de
chaque cadre. Ce n'est pas nécessaire : les 7 sujets sont produits par
WeasyPrint et leur PDF **porte déjà** la position exacte de chaque cadre et son
code, extractibles sans ambiguïté (vérifié : 280/280 cadres sur les 7 sujets).
Le gabarit est donc *lu à la source*, pas *deviné sur le scan* — ce qui
supprime l'étape la plus fragile de la chaîne. L'OCR d'un code de trois
caractères manuscrit-adjacent sur un scan à 150 DPI aurait été le premier point
de panne, et une confusion `G1`/`G7` aurait attribué une réponse à la mauvaise
question sans que rien ne le signale.

Ce qui reste à faire sur le scan lui-même est donc réduit à un seul problème :
**recaler** la page scannée sur le gabarit (translation, échelle, rotation).

Ce module est indépendant du framework : il ne connaît ni Django ni Streamlit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

FormatQuestion = Literal["qcm", "court", "redige", "construction"]

# ── Signature graphique des sujets ────────────────────────────────────────────
# Les cadres sont dessinés en aplats gris (type "f"), pas en traits : c'est le
# niveau de gris qui les distingue, et lui seul. Relevé sur les 7 sujets.
_GRIS_CADRE_LIGNE = 0.478431      # cadre des questions à lignes (qcm/court/redige)
_GRIS_CADRE_TRACE = 0.600000      # cadre vide des questions `construction`
_GRIS_LIGNE_GUIDAGE = 0.749020    # lignes de guidage à l'intérieur d'un cadre
_TOLERANCE_GRIS = 0.01

# Un cadre de réponse occupe toute la largeur du bloc de texte. Les seuls autres
# rectangles de cette largeur sont les bandeaux de section (« A1. Nombres »),
# écartés par leur hauteur et leur gris.
_LARGEUR_MIN_CADRE = 480.0
_HAUTEUR_MIN_CADRE = 25.0
_LARGEUR_MIN_LIGNE = 400.0

# Nombre de lignes de guidage → format de la question. Relevé sur les 7 sujets :
# qcm 71 × 1 ligne, court 139 × 2, redige 63 × 8, construction 7 × 0.
_FORMAT_PAR_LIGNES: dict[int, FormatQuestion] = {1: "qcm", 2: "court", 8: "redige"}

# Marge retirée de chaque côté à la découpe, en points PDF : le trait du cadre
# lui-même n'a pas à se retrouver dans l'image envoyée au diagnostic.
_MARGE_DECOUPE = 2.0

# Marge autour du code typographié à effacer de la zone découpée, en points.
_PAD_CODE = 1.5

# Écart toléré entre l'échelle horizontale et l'échelle verticale d'une page.
# 0,5 % laisse passer l'arrondi d'un rendu, pas les 2 à 3 % d'un scan brut.
_ECART_ECHELLE_MAX = 0.005

# Seuil de binarisation, sur 255. Les lignes de guidage sont imprimées à 191 et
# le trait du cadre à 122 ; l'encre descend nettement plus bas. Tout ce qui est
# plus clair que ce seuil est blanchi.
#
# Confronté à un scan réel (HP Scan, 200 DPI, copie 3e) : le papier ressort à
# 254 et la distribution est franchement bimodale — la proportion de pixels
# sombres ne bouge que de 1,85 % à 3,47 % quand le seuil passe de 120 à 200.
# 140 est donc au milieu d'un large plateau, et non sur une pente : le réglage
# n'est pas critique tant que le scan n'est pas sous-exposé.
SEUIL_ENCRE_DEFAUT = 140


class CadreReponse(BaseModel):
    """Un cadre de réponse du sujet, repéré dans le PDF source."""

    code: str                       # code de question du référentiel : "N4", "G13"…
    page: int = Field(ge=1)         # numéro de page, 1-indexé
    format: FormatQuestion
    lignes: int = Field(ge=0)       # lignes de guidage, 0 pour `construction`
    x0: float
    y0: float
    x1: float
    y1: float
    # Emprise du code typographié dans le coin du cadre. Il est imprimé en noir,
    # donc indiscernable de l'écriture au seuillage : sans sa position, chaque
    # zone contiendrait de l'encre et aucune ne serait jamais reconnue vierge.
    code_x0: float
    code_y0: float
    code_x1: float
    code_y1: float

    @property
    def largeur(self) -> float:
        return self.x1 - self.x0

    @property
    def hauteur(self) -> float:
        return self.y1 - self.y0


class GabaritSujet(BaseModel):
    """Position de tous les cadres de réponse d'un sujet."""

    source: Path
    pages: int = Field(ge=1)
    largeur_page: float
    hauteur_page: float
    cadres: list[CadreReponse]

    def par_code(self) -> dict[str, CadreReponse]:
        return {c.code: c for c in self.cadres}

    def cadres_de_page(self, page: int) -> list[CadreReponse]:
        return [c for c in self.cadres if c.page == page]


class ZoneDecoupee(BaseModel):
    """La production d'un élève sur une question, isolée du reste de la page."""

    code: str
    format: FormatQuestion
    page: int
    chemin: Path
    vide: bool          # aucune encre trouvée dans le cadre — l'élève n'a rien écrit
    taux_encre: float   # proportion de pixels sombres, pour régler le seuil de vide


class GabaritIncoherent(RuntimeError):
    """Le PDF ne présente pas la structure attendue d'un sujet Urie v2."""


def _est_gris(valeur: tuple[float, ...] | None, attendu: float) -> bool:
    return valeur is not None and abs(valeur[0] - attendu) < _TOLERANCE_GRIS


def _code_candidat(mot: str) -> bool:
    """Un code de question : une lettre de domaine puis un rang. « N4 », « G13 »."""
    return 2 <= len(mot) <= 4 and mot[0].isalpha() and any(c.isdigit() for c in mot)


def extraire_gabarit(chemin_pdf: Path) -> GabaritSujet:
    """
    Relève la position et le code de chaque cadre de réponse d'un sujet.

    Le code est cherché **à l'intérieur** du cadre, dans son coin supérieur
    gauche. C'est ce qui le distingue du même code imprimé en marge à côté de
    l'énoncé : les deux existent sur la page, seule l'inclusion les départage.
    """
    doc = fitz.open(chemin_pdf)
    try:
        if doc.page_count == 0:
            raise GabaritIncoherent(f"{chemin_pdf.name} ne contient aucune page.")

        cadres: list[CadreReponse] = []
        vus: dict[str, int] = {}
        premiere = doc.load_page(0).rect

        for index, page in enumerate(doc):
            numero = index + 1
            rects_cadres: list[fitz.Rect] = []
            rects_lignes: list[fitz.Rect] = []

            for dessin in page.get_drawings():
                rect, fill = dessin["rect"], dessin["fill"]
                largeur, hauteur = rect.width, rect.height
                if (
                    (_est_gris(fill, _GRIS_CADRE_LIGNE) or _est_gris(fill, _GRIS_CADRE_TRACE))
                    and largeur > _LARGEUR_MIN_CADRE
                    and hauteur > _HAUTEUR_MIN_CADRE
                ):
                    rects_cadres.append(rect)
                elif _est_gris(fill, _GRIS_LIGNE_GUIDAGE) and largeur > _LARGEUR_MIN_LIGNE:
                    rects_lignes.append(rect)

            mots = [m for m in page.get_text("words") if _code_candidat(m[4])]

            for rect in rects_cadres:
                interieur = sorted(
                    (
                        m for m in mots
                        if rect.x0 - 1 <= m[0] and m[2] <= rect.x1 + 1
                        and rect.y0 - 1 <= m[1] and m[3] <= rect.y1 + 1
                    ),
                    key=lambda m: (m[1], m[0]),
                )
                if not interieur:
                    raise GabaritIncoherent(
                        f"{chemin_pdf.name} page {numero} : un cadre de réponse "
                        f"(y={rect.y0:.0f}) ne porte aucun code. Le sujet ne suit pas "
                        f"le format à cadres ancrés attendu par le module 2."
                    )
                mot_code = interieur[0]
                code = mot_code[4]
                if code in vus:
                    raise GabaritIncoherent(
                        f"{chemin_pdf.name} : le code {code!r} apparaît dans deux cadres "
                        f"(pages {vus[code]} et {numero}). Un code doit désigner une "
                        f"seule zone de réponse."
                    )
                vus[code] = numero

                lignes = sum(
                    1 for lr in rects_lignes if rect.y0 <= lr.y0 and lr.y1 <= rect.y1 + 1
                )
                cadres.append(
                    CadreReponse(
                        code=code,
                        page=numero,
                        format=_FORMAT_PAR_LIGNES.get(lignes, "construction"),
                        lignes=lignes,
                        x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1,
                        code_x0=mot_code[0], code_y0=mot_code[1],
                        code_x1=mot_code[2], code_y1=mot_code[3],
                    )
                )

        if not cadres:
            raise GabaritIncoherent(
                f"{chemin_pdf.name} ne contient aucun cadre de réponse. Ce n'est "
                f"vraisemblablement pas un sujet au format Urie v2."
            )

        return GabaritSujet(
            source=chemin_pdf,
            pages=doc.page_count,
            largeur_page=premiere.width,
            hauteur_page=premiere.height,
            cadres=cadres,
        )
    finally:
        doc.close()


def resolution_scan(chemin_pdf: Path) -> int | None:
    """
    Résolution native d'un PDF de scan, en DPI — `None` si le PDF est vectoriel.

    Le scan se fait **hors plateforme** : ce qui arrive est un PDF multipage ou
    des images, produits par un scanner dont on ne contrôle pas les réglages.
    Rendre un scan à 200 DPI dans une image à 150 DPI perd de la définition sur
    une zone qui sera ensuite recadrée au dixième de la page — cette fonction
    permet à l'appelant de rendre à la résolution de la source plutôt qu'à une
    valeur fixe.

    La plus grande résolution rencontrée est retenue : un scanner peut mêler des
    pages de définitions différentes dans un même fichier.
    """
    doc = fitz.open(chemin_pdf)
    try:
        resolutions: list[float] = []
        for page in doc:
            largeur_pouces = page.rect.width / 72
            if largeur_pouces <= 0:
                continue
            for image in page.get_images(full=True):
                info = doc.extract_image(image[0])
                resolutions.append(info["width"] / largeur_pouces)
        return round(max(resolutions)) if resolutions else None
    finally:
        doc.close()


def decouper_zones(
    gabarit: GabaritSujet,
    pages: list[Path],
    dossier_sortie: Path,
    seuil_encre: int = SEUIL_ENCRE_DEFAUT,
    taux_vide: float = 0.0015,
) -> list[ZoneDecoupee]:
    """
    Découpe l'intérieur de chaque cadre dans les pages fournies.

    `pages` est la liste des images de la copie, dans l'ordre, telle que la
    produit `ingestion.ingest_pdf` (150 DPI, D-CEO-10). L'échelle est déduite de
    la largeur de l'image et de celle du gabarit : aucune hypothèse n'est faite
    sur la résolution du scan.

    Les lignes de guidage sont retirées par seuillage : elles sont pâles (191) et
    uniformes, l'écriture ne l'est pas. Le blanchiment garde les niveaux de gris
    de l'encre au lieu de binariser franchement — un trait de crayon clair reste
    lisible pour un modèle de vision, alors qu'un seuillage dur l'effacerait.

    ⚠ Cette fonction suppose la page **déjà recalée** sur le gabarit. Sur un scan
    réel il faut redresser avant d'appeler ici (voir le journal du module 2).
    """
    if len(pages) < gabarit.pages:
        raise GabaritIncoherent(
            f"La copie compte {len(pages)} page(s), le sujet en compte {gabarit.pages}. "
            f"Une page manquante décalerait toutes les zones : découpe refusée."
        )

    dossier_sortie.mkdir(parents=True, exist_ok=True)
    zones: list[ZoneDecoupee] = []

    for numero in range(1, gabarit.pages + 1):
        cadres = gabarit.cadres_de_page(numero)
        if not cadres:
            continue

        with Image.open(pages[numero - 1]) as image:
            grise = image.convert("L")
            echelle_x = grise.width / gabarit.largeur_page
            echelle_y = grise.height / gabarit.hauteur_page

            # Garde-fou contre l'erreur qui ne se verrait pas : passer ici un scan
            # brut. Un scanner ne rend pas la page du gabarit — mesuré sur un scan
            # réel (HP Scan) : largeur 612 pt au lieu de 595,3, et une hauteur qui
            # varie de 835 à 851 pt **d'une feuille à l'autre du même fichier**.
            # L'échelle déduite serait fausse de 2 à 3 %, soit un décalage de
            # plusieurs millimètres en bas de page : les découpes resteraient
            # plausibles tout en attrapant la ligne de la question voisine.
            ecart = abs(echelle_x - echelle_y) / max(echelle_x, echelle_y)
            if ecart > _ECART_ECHELLE_MAX:
                raise GabaritIncoherent(
                    f"Page {numero} : les proportions de l'image ({grise.width}×"
                    f"{grise.height}) ne sont pas celles du sujet "
                    f"({gabarit.largeur_page:.0f}×{gabarit.hauteur_page:.0f} pt) — "
                    f"{ecart:.1%} d'écart entre les échelles horizontale et "
                    f"verticale. La page doit être recalée sur le gabarit avant "
                    f"d'être découpée."
                )

            for cadre in cadres:
                boite = (
                    int(round((cadre.x0 + _MARGE_DECOUPE) * echelle_x)),
                    int(round((cadre.y0 + _MARGE_DECOUPE) * echelle_y)),
                    int(round((cadre.x1 - _MARGE_DECOUPE) * echelle_x)),
                    int(round((cadre.y1 - _MARGE_DECOUPE) * echelle_y)),
                )
                pixels = np.array(grise.crop(boite))

                # Le code typographié est effacé avant tout comptage : il est
                # imprimé en noir, le seuillage ne peut pas l'écarter, et le
                # laisser ferait passer pour remplie une zone restée vierge.
                cx0 = int(round((cadre.code_x0 - _PAD_CODE) * echelle_x)) - boite[0]
                cy0 = int(round((cadre.code_y0 - _PAD_CODE) * echelle_y)) - boite[1]
                cx1 = int(round((cadre.code_x1 + _PAD_CODE) * echelle_x)) - boite[0]
                cy1 = int(round((cadre.code_y1 + _PAD_CODE) * echelle_y)) - boite[1]
                pixels[max(cy0, 0):max(cy1, 0), max(cx0, 0):max(cx1, 0)] = 255

                encre = pixels < seuil_encre
                taux = float(encre.mean()) if pixels.size else 0.0

                nettoye = np.where(encre, pixels, np.uint8(255))
                chemin = dossier_sortie / f"{cadre.code}.png"
                Image.fromarray(nettoye).save(chemin)

                zones.append(
                    ZoneDecoupee(
                        code=cadre.code,
                        format=cadre.format,
                        page=numero,
                        chemin=chemin,
                        vide=taux < taux_vide,
                        taux_encre=taux,
                    )
                )

    return zones


def verifier_gabarit(gabarit: GabaritSujet, questions_bareme: dict[str, str]) -> list[str]:
    """
    Confronte le gabarit au barème du test — `{code: format}`.

    Sert de garde-fou à l'exploitation : si l'enseignant scanne un sujet d'une
    autre version que celle chargée en base, les codes ou les formats divergent
    et on le sait **avant** d'attribuer des réponses aux mauvaises questions.

    Retourne la liste des anomalies, vide si tout concorde.
    """
    anomalies: list[str] = []
    du_gabarit = gabarit.par_code()

    for code in sorted(set(questions_bareme) - set(du_gabarit)):
        anomalies.append(f"{code} : attendu par le barème, absent du sujet.")
    for code in sorted(set(du_gabarit) - set(questions_bareme)):
        anomalies.append(f"{code} : présent sur le sujet, inconnu du barème.")
    for code in sorted(set(du_gabarit) & set(questions_bareme)):
        attendu, trouve = questions_bareme[code], du_gabarit[code].format
        if attendu != trouve:
            anomalies.append(
                f"{code} : le barème annonce le format {attendu!r}, "
                f"le cadre du sujet est de format {trouve!r}."
            )
    return anomalies
