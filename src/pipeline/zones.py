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
# niveau de gris qui les distingue.
#
# Ces règles sont volontairement exprimées en **plages** et en **proportions de
# la page**, pas en valeurs relevées sur les 7 sujets actuels. Le sujet est un
# document vivant : régénéré, il changera de marges, de teintes et de nombre de
# lignes. Une égalité stricte à 0,478431 ou une largeur de 480 pt aurait fait
# échouer la lecture du gabarit à la première retouche du gabarit d'impression —
# et l'échec aurait été total (zéro cadre trouvé), pas partiel.
_GRIS_CADRE_MIN = 0.30            # plus sombre : du texte ou un bandeau plein
_GRIS_CADRE_MAX = 0.70            # plus clair : une ligne de guidage
_GRIS_LIGNE_MIN = 0.70            # les lignes de guidage sont plus pâles que les cadres
_GRIS_LIGNE_MAX = 0.95            # plus clair encore : une trame de fond

# Un cadre de réponse occupe toute la largeur du bloc de texte. Exprimé en
# fraction de la largeur de page, la règle survit à un changement de marges.
_PART_LARGEUR_CADRE = 0.75
_PART_LARGEUR_LIGNE = 0.60
_HAUTEUR_MIN_CADRE = 25.0

# Nombre de lignes de guidage → format de la question. Relevé sur les 7 sujets
# actuels : qcm 71 × 1 ligne, court 139 × 2, redige 63 × 8, construction 7 × 0.
# Au-delà de 2 lignes, c'est une question rédigée : la borne est ouverte pour
# qu'un sujet à 6 ou 10 lignes reste lu correctement.
_FORMAT_PAR_LIGNES: dict[int, FormatQuestion] = {0: "construction", 1: "qcm", 2: "court"}

# Marge retirée de chaque côté à la découpe, en points PDF : le trait du cadre
# lui-même n'a pas à se retrouver dans l'image envoyée au diagnostic.
_MARGE_DECOUPE = 2.0

# Marge autour du code typographié à effacer de la zone découpée, en points.
_PAD_CODE = 1.5

# Écart toléré entre l'échelle horizontale et l'échelle verticale d'une page.
# 0,5 % laisse passer l'arrondi d'un rendu, pas les 2 à 3 % d'un scan brut.
_ECART_ECHELLE_MAX = 0.005

# ── Recalage ──────────────────────────────────────────────────────────────────
# Bornes de la recherche d'inclinaison. Mesuré sur un scan réel (HP Scan) :
# −1,25°, −1,25°, +1,00° sur trois pages du même fichier. 3° laisse de la marge
# pour une feuille posée de travers ; au-delà, c'est un incident de numérisation
# qu'il vaut mieux signaler que rattraper.
_ANGLE_MAX = 3.0
_PAS_ANGLE = 0.1

# Au-delà, l'estimation d'inclinaison travaille sur un échantillon des pixels
# d'encre. La mesure est statistique : 200 000 points suffisent largement à
# situer un angle au dixième de degré, et le coût cesse de croître avec la
# résolution du scanner.
_ECHANTILLON_ENCRE_MAX = 200_000

# Bornes de la recherche d'échelle et de décalage, en fraction. L'estimation de
# départ — la taille de l'image rapportée à celle de la page du sujet — n'est
# qu'un ordre de grandeur : le scanner ne rend pas la page du gabarit, et ce
# qu'il ajoute autour (marges, bords de vitre) fausse le rapport sans toucher au
# contenu. 12 % couvre le cas qui coûterait le plus cher à diagnostiquer : une
# copie numérisée au format Letter au lieu de A4, soit 6 % d'écart en hauteur,
# plus les marges. Trop étroite, la recherche exclut la bonne échelle et se rabat
# sur la moins mauvaise — un calage faux mais confiant.
_TOLERANCE_ECHELLE = 0.12
_PAS_ECHELLE = 0.001
_TOLERANCE_DECALAGE = 0.06

# Tolérance de l'échelle horizontale **autour de l'échelle verticale**. Les
# cadres partagent tous les mêmes bords gauche et droit : l'axe horizontal n'offre
# que deux repères, contre une quinzaine à la verticale, et deux points suffisent
# tout juste à fixer deux inconnues — le moindre trait parasite en marge suffit
# alors à emporter l'ajustement. Or un scanner échantillonne à la même définition
# dans les deux sens : l'échelle du contenu est la même en x et en y. Chercher
# l'une autour de l'autre lève l'indétermination au lieu de la subir.
_TOLERANCE_ECHELLE_X = 0.015

# Tolérance, en pixels, de la rencontre entre un repère et l'encre. Le bord d'un
# cadre est un trait d'un point : à 150 DPI il ne fait que deux pixels de large,
# et un ajustement juste à un pixel près tomberait à côté — donc à zéro, comme
# s'il n'avait rien trouvé. Élargir les pics de deux pixels rend la mesure
# insensible à cet arrondi, sans dégrader le recalage au-delà de la marge que la
# découpe retire de toute façon sur le pourtour du cadre.
_TOLERANCE_REPERE_PX = 2

# Un bord de cadre est « retrouvé » si l'encre présente à sa position atteint
# cette part du maximum du profil. Sert à *rendre compte* du recalage, pas à le
# calculer : l'ajustement optimise une somme continue, plus stable à optimiser,
# et ce comptage traduit ensuite le résultat en une part interprétable.
_PART_REPERE_RETROUVE = 0.25

#: En deçà, la page ne ressemble pas au sujet : mieux vaut le dire que découper
#: au hasard. Un recalage réussi retrouve l'essentiel des bords de cadre.
SCORE_RECALAGE_MIN = 0.35


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
    # Bandes horizontales des « lignes de guidage », en points.
    #
    # ⚠ Elles ne sont pas des traits. Mesuré sur les 7 sujets : ce sont des
    # bandes de 21 pt **jointives** (853 relevées, hauteur 19,84 ou 20,98,
    # espacement égal à la hauteur) qui pavent toute la zone d'écriture du
    # cadre. Ce que l'élève voit est donc un **aplat gris**, pas un lignage ; le
    # nombre de bandes reste ce qui donne le format de la question.
    #
    # La conséquence porte sur le risque du tramage laser (voir `decouper_zones`)
    # et vaut d'être écrite ici, parce qu'elle contredit un repli qui semble
    # évident : effacer les lignes « à leur position connue » ne peut rien
    # donner, leur position est la zone de réponse tout entière.
    lignes_y: list[tuple[float, float]] = Field(default_factory=list)

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

    @property
    def diagnosticable(self) -> bool:
        """Le module 4 peut-il se prononcer sur cette zone ?

        Non pour les 7 questions de format `construction` : elles attendent un
        tracé à la règle et au compas, pas du texte. Juger une perpendiculaire
        ou un report de longueur demande de mesurer la figure, pas de lire une
        réponse — hors de portée du diagnostic contraint, qui reconnaît des
        signatures d'erreur écrites. Ces zones sont découpées comme les autres et
        **orientées vers la saisie humaine** (module 8) ; les laisser passer au
        module 4 produirait un diagnostic inventé sur une question sur quarante.
        """
        return self.format != "construction" and not self.vide


class GabaritIncoherent(RuntimeError):
    """Le PDF ne présente pas la structure attendue d'un sujet Urie v2."""


def _gris_dans(valeur: tuple[float, ...] | None, mini: float, maxi: float) -> bool:
    """Un aplat gris — donc non coloré — dont la clarté tombe dans la plage."""
    if valeur is None or len(valeur) < 3:
        return False
    if max(valeur[:3]) - min(valeur[:3]) > 0.05:   # une couleur, pas un gris
        return False
    return mini <= valeur[0] < maxi


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

            largeur_min_cadre = page.rect.width * _PART_LARGEUR_CADRE
            largeur_min_ligne = page.rect.width * _PART_LARGEUR_LIGNE

            for dessin in page.get_drawings():
                rect, fill = dessin["rect"], dessin["fill"]
                largeur, hauteur = rect.width, rect.height
                if (
                    _gris_dans(fill, _GRIS_CADRE_MIN, _GRIS_CADRE_MAX)
                    and largeur > largeur_min_cadre
                    and hauteur > _HAUTEUR_MIN_CADRE
                ):
                    rects_cadres.append(rect)
                elif _gris_dans(fill, _GRIS_LIGNE_MIN, _GRIS_LIGNE_MAX) and largeur > largeur_min_ligne:
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

                lignes_y = sorted(
                    (lr.y0, lr.y1)
                    for lr in rects_lignes
                    if rect.y0 <= lr.y0 and lr.y1 <= rect.y1 + 1
                )
                cadres.append(
                    CadreReponse(
                        code=code,
                        page=numero,
                        format=_FORMAT_PAR_LIGNES.get(len(lignes_y), "redige"),
                        lignes=len(lignes_y),
                        x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1,
                        code_x0=mot_code[0], code_y0=mot_code[1],
                        code_x1=mot_code[2], code_y1=mot_code[3],
                        lignes_y=lignes_y,
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


def _profil(binaire: np.ndarray, axe: int) -> np.ndarray:
    """Somme d'encre par ligne (axe=1) ou par colonne (axe=0)."""
    return binaire.sum(axis=axe).astype(np.float64)


def _projeter(le_long: np.ndarray, en_travers: np.ndarray, pente: float, taille: int) -> np.ndarray:
    """Profil d'encre le long d'un axe, l'inclinaison retirée.

    `le_long` est la coordonnée dont on fait l'histogramme, `en_travers` celle
    qui décale — une rangée de la page monte d'autant plus qu'on va vers la
    droite. Les deux axes s'y ramènent : les rangées avec `(y, x, −pente)`, les
    colonnes avec `(x, y, +pente)`.
    """
    marge = int(abs(pente) * (float(en_travers.max()) + 1)) + 1 if en_travers.size else 1
    rangs = np.rint(le_long + pente * en_travers).astype(np.int64) + marge
    profil = np.bincount(rangs, minlength=taille + 2 * marge).astype(np.float64)
    return profil[marge : marge + taille]


def _estimer_cisaillement(
    ys: np.ndarray, xs: np.ndarray, hauteur: int
) -> tuple[float, np.ndarray]:
    """Estime l'inclinaison de la page — retourne (pente, profil redressé).

    Le critère est la **concentration du profil horizontal** : sur une page bien
    droite, les bords de cadre et les lignes de texte rassemblent leur encre sur
    quelques rangées ; inclinée, cette encre s'étale et le profil s'aplatit.

    **L'estimation se fait sur les coordonnées des pixels d'encre, jamais en
    faisant tourner l'image** — et c'est le point qui décide de sa justesse. Une
    rotation ré-échantillonne : elle étale un trait fin d'un pixel sur deux, dont
    aucun n'est alors assez sombre pour franchir le seuil. Le trait disparaît
    purement et simplement. Mesuré sur une page d'essai inclinée de 1,25° : 2 616
    pixels d'encre à 0°, moins de 600 à tout autre angle — l'angle 0 l'emportait
    donc toujours, quelle que soit l'inclinaison réelle, et le redressement était
    un décor. Déplacer les coordonnées conserve exactement les mêmes pixels d'un
    angle à l'autre : les scores redeviennent comparables.

    L'inclinaison est modélisée par un **cisaillement** (`y − pente·x`) et non par
    une rotation. En deçà de 3°, les deux ne diffèrent pas d'un pixel sur une
    page A4, et le cisaillement s'applique ensuite exactement, sans seconde
    interpolation, au découpage de chaque zone.

    Mesuré sur un scan réel : −1,25°, −1,25° et +1,00° sur trois pages du **même
    fichier**. L'estimation est donc faite page par page, jamais globalement.
    """
    if ys.size == 0:
        return 0.0, np.zeros(hauteur, dtype=np.float64)

    if ys.size > _ECHANTILLON_ENCRE_MAX:
        pas = ys.size // _ECHANTILLON_ENCRE_MAX + 1
        ys_e, xs_e = ys[::pas], xs[::pas]
    else:
        ys_e, xs_e = ys, xs

    meilleure_pente, meilleur_score = 0.0, -1.0
    for angle in np.arange(-_ANGLE_MAX, _ANGLE_MAX + 1e-9, _PAS_ANGLE):
        pente = float(np.tan(np.radians(angle)))
        profil = _projeter(ys_e, xs_e, -pente, hauteur)
        # Somme des carrés : à quantité d'encre constante — c'est le cas ici,
        # les pixels sont les mêmes — elle est maximale quand l'encre est la
        # plus concentrée.
        score = float((profil**2).sum())
        if score > meilleur_score:
            meilleure_pente, meilleur_score = pente, score

    return meilleure_pente, _projeter(ys, xs, -meilleure_pente, hauteur)


def _ajuster_axe(
    profil: np.ndarray,
    reperes_pt: np.ndarray,
    echelle_initiale: float,
    tolerance: float = _TOLERANCE_ECHELLE,
) -> tuple[float, float, float]:
    """Cale les repères du gabarit sur le profil observé — retourne (échelle, décalage, score).

    Les repères sont les bords de cadre, dont on connaît la position exacte en
    points. On cherche l'échelle et le décalage qui font tomber le plus d'encre
    possible sur ces positions. C'est une recherche exhaustive sur une grille
    étroite : le problème est à deux paramètres et les repères sont peu nombreux
    (une quinzaine par page), donc l'exhaustif coûte moins cher qu'un ajustement
    itératif — et il ne peut pas converger vers un minimum local.

    **Pourquoi pas le rectangle de la page :** un scanner ne rend pas la page du
    gabarit. Mesuré sur un scan réel, la hauteur varie de 835 à 851 pt d'une
    feuille à l'autre du même fichier. L'ancrage se fait donc sur le contenu.
    """
    n = profil.size
    if n == 0 or reperes_pt.size == 0 or profil.max() <= 0:
        return echelle_initiale, 0.0, 0.0

    echelles = echelle_initiale * (1 + np.arange(-tolerance, tolerance + 1e-9, _PAS_ECHELLE))
    amplitude = int(n * _TOLERANCE_DECALAGE)
    decalages = np.arange(-amplitude, amplitude + 1, dtype=np.float64)

    profil = _elargir(profil, _TOLERANCE_REPERE_PX)
    normalise = profil / profil.max()
    meilleur = (echelle_initiale, 0.0, -1.0)
    for echelle in echelles:
        # (K repères, M décalages) → indice de pixel de chaque repère
        indices = np.rint(reperes_pt[:, None] * echelle + decalages[None, :]).astype(np.int64)
        valides = (indices >= 0) & (indices < n)
        scores = np.where(valides, normalise[np.clip(indices, 0, n - 1)], 0.0).sum(axis=0)
        k = int(scores.argmax())
        if scores[k] > meilleur[2]:
            meilleur = (float(echelle), float(decalages[k]), float(scores[k]))

    return meilleur[0], meilleur[1], _part_retrouvee(profil, reperes_pt, meilleur[0], meilleur[1])


def _elargir(profil: np.ndarray, rayon: int) -> np.ndarray:
    """Étale chaque pic sur `rayon` pixels de part et d'autre (dilatation)."""
    elargi = profil.copy()
    for pas in range(1, rayon + 1):
        elargi = np.maximum(elargi, np.roll(profil, pas))
        elargi = np.maximum(elargi, np.roll(profil, -pas))
    return elargi


def _part_retrouvee(
    profil: np.ndarray, reperes_pt: np.ndarray, echelle: float, decalage: float
) -> float:
    """Part des repères du gabarit qui tombent sur de l'encre — le score rendu.

    Distinct du critère d'ajustement, qui est une somme continue : celui-ci se
    lit (« 8 bords de cadre sur 10 retrouvés ») et c'est lui qu'on compare à
    `SCORE_RECALAGE_MIN` pour décider de refuser une page.
    """
    n = profil.size
    if n == 0 or reperes_pt.size == 0 or profil.max() <= 0:
        return 0.0
    profil = _elargir(profil, _TOLERANCE_REPERE_PX)
    indices = np.rint(reperes_pt * echelle + decalage).astype(np.int64)
    dedans = (indices >= 0) & (indices < n)
    valeurs = np.where(dedans, profil[np.clip(indices, 0, n - 1)], 0.0)
    return float((valeurs >= _PART_REPERE_RETROUVE * profil.max()).mean())


class Recalage(BaseModel):
    """Transformation d'une page scannée vers le repère du gabarit.

    Un point `(x, y)` du gabarit, en points PDF, tombe sur le pixel :

        X = x · echelle_x + decalage_x − pente · (y · echelle_y)
        Y = y · echelle_y + decalage_y + pente · (x · echelle_x)

    Les deux termes en `pente` portent l'inclinaison de la feuille : c'est une
    rotation, écrite au premier ordre — en deçà de 3°, l'écart avec la rotation
    exacte reste sous le pixel sur une page A4. Elle est appliquée au découpage
    de chaque zone, pas en faisant tourner la page : une image scannée ne subit
    ainsi **aucun ré-échantillonnage** avant d'être découpée.
    """

    angle: float          # inclinaison mesurée, en degrés (dérivée de la pente)
    pente: float          # tan(angle)
    echelle_x: float      # pixels par point
    echelle_y: float
    decalage_x: float     # en pixels
    decalage_y: float
    score: float = Field(ge=0.0, le=1.0)  # part des bords de cadre retrouvés
    ajuste: bool          # False = l'image était déjà dans le repère du gabarit

    def vers_pixels(self, x_pt: float, y_pt: float) -> tuple[int, int]:
        x, y = x_pt * self.echelle_x, y_pt * self.echelle_y
        return (
            int(round(x + self.decalage_x - self.pente * y)),
            int(round(y + self.decalage_y + self.pente * x)),
        )


class _PagePreparee:
    """Ce qu'on relève d'une page scannée avant de savoir à quelle page du sujet
    elle correspond.

    L'inclinaison et les profils d'encre ne dépendent que de la page elle-même :
    les relever une fois permet de confronter la page à chacune des pages du
    sujet sans tout recalculer — c'est ce qui rend l'appariement abordable.
    """

    __slots__ = ("largeur", "hauteur", "pente", "profil_lignes", "profil_colonnes")

    def __init__(self, image: Image.Image, seuil_encre: int) -> None:
        grise = image.convert("L")
        binaire = np.asarray(grise) < seuil_encre
        self.largeur, self.hauteur = grise.width, grise.height
        ys, xs = np.nonzero(binaire)
        self.pente, self.profil_lignes = _estimer_cisaillement(ys, xs, self.hauteur)
        # Les bords **verticaux** des cadres s'inclinent autant que les
        # horizontaux : sur une page de 1 900 px penchée de 1,25°, un bord de
        # cadre balaie 41 colonnes. Sans cette correction, le profil des colonnes
        # n'a plus de pic à caler et l'ajustement horizontal part à côté.
        self.profil_colonnes = _projeter(xs, ys, self.pente, self.largeur)


def _caler(
    page: _PagePreparee, cadres: list[CadreReponse], gabarit: GabaritSujet
) -> Recalage:
    """Cale une page préparée sur les cadres attendus d'une page du sujet.

    Les repères sont les **bords des cadres de réponse** — les seuls objets de la
    page dont on connaisse la position exacte, et les plus contrastés. Le score
    dit quelle part d'entre eux a été retrouvée : au-dessous de
    `SCORE_RECALAGE_MIN`, la page ne ressemble pas à celle du sujet.
    """
    bords_y = np.array(sorted({c.y0 for c in cadres} | {c.y1 for c in cadres}))
    bords_x = np.array(sorted({c.x0 for c in cadres} | {c.x1 for c in cadres}))

    # L'axe vertical d'abord : il porte deux bords par cadre, donc une quinzaine
    # de repères, et se cale sans ambiguïté. L'horizontal n'en a que deux — il est
    # cherché autour de l'échelle verticale, que le scanner lui impose de partager.
    echelle_y, decalage_y, score_y = _ajuster_axe(
        page.profil_lignes, bords_y, page.hauteur / gabarit.hauteur_page
    )
    echelle_x, decalage_x, score_x = _ajuster_axe(
        page.profil_colonnes, bords_x, echelle_y, _TOLERANCE_ECHELLE_X
    )

    # Le décalage vertical est mesuré sur le profil redressé, où la ligne d'un
    # point vaut `y·echelle_y + decalage_y`. Sur l'image, cette ligne est
    # décalée de `pente·X` : c'est ce que `vers_pixels` rétablit.
    return Recalage(
        angle=float(np.degrees(np.arctan(page.pente))),
        pente=page.pente,
        echelle_x=echelle_x,
        echelle_y=echelle_y,
        decalage_x=decalage_x,
        decalage_y=decalage_y,
        score=min(score_x, score_y),
        ajuste=True,
    )


def recaler_page(
    image: Image.Image,
    cadres: list[CadreReponse],
    gabarit: GabaritSujet,
    seuil_encre: int = SEUIL_ENCRE_DEFAUT,
) -> Recalage:
    """Aligne une page scannée sur les cadres attendus — inclinaison et échelle."""
    return _caler(_PagePreparee(image, seuil_encre), cadres, gabarit)


def apparier_pages(
    gabarit: GabaritSujet,
    pages_preparees: list[_PagePreparee],
) -> list[tuple[int, Recalage]]:
    """
    Associe à chaque page du sujet la page du scan qui lui correspond.

    **L'appariement ne peut pas être supposé 1:1.** Mesuré sur un scan réel : 12
    pages pour un sujet qui en compte 10, l'enseignant ayant numérisé la page de
    garde et la page de renseignements avec le reste. Découpées dans l'ordre,
    toutes les zones auraient été prises sur la mauvaise page — et le résultat
    aurait eu l'air normal, chaque zone contenant bien de l'écriture.

    Chaque page du scan est confrontée à chaque page du sujet ; on retient
    l'affectation qui maximise le total des scores **en gardant l'ordre** : une
    copie se numérise dans l'ordre, et l'exiger empêche deux pages qui se
    ressemblent de s'échanger.

    Retourne, pour chaque page du sujet, `(indice dans le scan, recalage)`.
    """
    pages_sujet = [p for p in range(1, gabarit.pages + 1) if gabarit.cadres_de_page(p)]
    m, n = len(pages_sujet), len(pages_preparees)
    if m > n:
        raise GabaritIncoherent(
            f"La copie compte {n} page(s) portant de l'encre, le sujet en compte "
            f"{m} avec des cadres de réponse. Une page manquante décalerait "
            f"toutes les zones : découpe refusée."
        )

    calages = [
        [_caler(page, gabarit.cadres_de_page(numero), gabarit) for page in pages_preparees]
        for numero in pages_sujet
    ]

    # Affectation croissante de coût maximal. `meilleur[i][j]` = meilleur total
    # pour les pages de sujet i… en n'utilisant que les pages de scan j…
    NEANT = float("-inf")
    meilleur = [[NEANT] * (n + 1) for _ in range(m + 1)]
    choix = [[-1] * (n + 1) for _ in range(m + 1)]
    for j in range(n + 1):
        meilleur[m][j] = 0.0
    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            prendre = calages[i][j].score + meilleur[i + 1][j + 1]
            passer = meilleur[i][j + 1]
            if prendre >= passer:
                meilleur[i][j], choix[i][j] = prendre, j
            else:
                meilleur[i][j], choix[i][j] = passer, choix[i][j + 1]

    apparie: list[tuple[int, Recalage]] = []
    j = 0
    for i in range(m):
        j = choix[i][j]
        apparie.append((j, calages[i][j]))
        j += 1

    for rang, (indice, calage) in enumerate(apparie):
        if calage.score < SCORE_RECALAGE_MIN:
            raise GabaritIncoherent(
                f"Page {pages_sujet[rang]} du sujet : aucune page du scan ne lui "
                f"correspond — au mieux {calage.score:.0%} des bords de cadre "
                f"retrouvés (page {indice + 1} du scan). Ce n'est vraisemblablement "
                f"pas une copie du sujet « {gabarit.source.name} », ou le scan est "
                f"trop dégradé."
            )
    return apparie


def decouper_zones(
    gabarit: GabaritSujet,
    pages: list[Path],
    dossier_sortie: Path,
    seuil_encre: int = SEUIL_ENCRE_DEFAUT,
    taux_vide: float = 0.0015,
    recaler: bool | None = None,
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

    ⚠ **Risque ouvert, et il ne se referme pas par le calcul.** Ce raisonnement
    tient sur le PDF, où le gris 191 est uniforme. Sur du papier, une imprimante
    laser ne rend pas un aplat gris par un gris uniforme mais par un **tramage de
    points noirs** — que le seuillage ne peut pas écarter. Constaté sur un scan
    réel d'un test de l'ancien format, dont les pointillés imprimés survivent.

    Le repli qu'on imagine d'abord — effacer les lignes à leur position, que le
    gabarit connaît — **ne s'applique pas** : les « lignes » sont des bandes
    jointives qui pavent toute la zone de réponse (voir `CadreReponse.lignes_y`).
    Leur position, c'est la zone entière ; l'effacement l'effacerait entière.

    Ce qu'il faudra traiter est donc le retrait d'une **trame** étendue à toute la
    zone, pas de quelques traits — un filtrage qui distingue un point isolé d'un
    trait de stylo. Il ne peut pas être réglé à l'aveugle : il dépend de la
    finesse de la trame, de la résolution du scanner et de l'épaisseur du trait,
    trois grandeurs qu'aucun rendu numérique ne donne. **À trancher sur le
    premier sujet Urie imprimé puis scanné** — même vierge, il suffit.

    **Recalage.** `recaler=None` (défaut) décide : si les images ont déjà les
    proportions du gabarit — le cas d'un PDF rendu — la correspondance est exacte
    et immédiate ; sinon c'est un scan, et chaque page est appariée à une page du
    sujet puis calée sur ses cadres. `True` force le recalage, `False` l'interdit
    et rétablit le refus d'une image aux mauvaises proportions.
    """
    pages_avec_cadres = [p for p in range(1, gabarit.pages + 1) if gabarit.cadres_de_page(p)]
    if len(pages) < len(pages_avec_cadres):
        raise GabaritIncoherent(
            f"La copie compte {len(pages)} page(s), le sujet en compte {gabarit.pages}. "
            f"Une page manquante décalerait toutes les zones : découpe refusée."
        )

    aux_proportions = all(_aux_proportions(chemin, gabarit) for chemin in pages)
    if recaler is False and not aux_proportions:
        # Sans recalage, une image aux mauvaises proportions se découpe sans rien
        # signaler, avec un décalage de plusieurs millimètres en bas de page : les
        # zones restent plausibles tout en attrapant la ligne de la question
        # voisine.
        raise GabaritIncoherent(
            f"Les proportions du scan ne sont pas celles du sujet "
            f"({gabarit.largeur_page:.0f}×{gabarit.hauteur_page:.0f} pt). La copie "
            f"doit être recalée sur le gabarit avant d'être découpée."
        )

    if recaler is True or (recaler is None and not aux_proportions):
        preparees = []
        for chemin in pages:
            with Image.open(chemin) as image:
                preparees.append(_PagePreparee(image, seuil_encre))
        appariement = apparier_pages(gabarit, preparees)
    else:
        # Un rendu du PDF : la page du sujet est la page du fichier, à l'identique.
        appariement = [
            (numero - 1, _recalage_direct(pages[numero - 1], gabarit))
            for numero in pages_avec_cadres
        ]

    dossier_sortie.mkdir(parents=True, exist_ok=True)
    zones: list[ZoneDecoupee] = []

    for numero, (indice, transformation) in zip(pages_avec_cadres, appariement):
        with Image.open(pages[indice]) as image:
            grise = image.convert("L")
            for cadre in gabarit.cadres_de_page(numero):
                zones.append(
                    _decouper_cadre(
                        grise, cadre, transformation, numero,
                        dossier_sortie, seuil_encre, taux_vide,
                    )
                )

    return zones


def _aux_proportions(chemin: Path, gabarit: GabaritSujet) -> bool:
    """L'image a-t-elle les proportions du sujet ? (le cas d'un PDF rendu)"""
    with Image.open(chemin) as image:
        echelle_x = image.width / gabarit.largeur_page
        echelle_y = image.height / gabarit.hauteur_page
    return abs(echelle_x - echelle_y) / max(echelle_x, echelle_y) <= _ECART_ECHELLE_MAX


def _recalage_direct(chemin: Path, gabarit: GabaritSujet) -> Recalage:
    """La transformation d'une image déjà dans le repère du gabarit."""
    with Image.open(chemin) as image:
        largeur, hauteur = image.width, image.height
    return Recalage(
        angle=0.0, pente=0.0,
        echelle_x=largeur / gabarit.largeur_page,
        echelle_y=hauteur / gabarit.hauteur_page,
        decalage_x=0.0, decalage_y=0.0,
        score=1.0, ajuste=False,
    )


def _extraire_cadre(
    grise: Image.Image, cadre: CadreReponse, t: Recalage
) -> tuple[np.ndarray, float, float]:
    """Sort l'intérieur du cadre de la page — retourne (pixels, échelle x, échelle y).

    L'image rendue est **dans le repère du gabarit** : le pixel `(u, v)` y
    correspond au point `(x0 + u/echelle_x, y0 + v/echelle_y)` du sujet, quelle
    que soit l'inclinaison de la feuille. Tout ce qui suit — effacement du code,
    effacement des lignes — se calcule donc en points du gabarit, sans avoir à
    reproduire la transformation.

    Quand la feuille est droite (`pente` nulle : un PDF rendu, un scan bien
    posé), c'est un simple recadrage. Inclinée, le cisaillement est confié à la
    transformation affine de Pillow : **une seule interpolation, sur la zone
    seule**, au lieu de faire tourner la page entière avant de la découper.
    """
    x0, y0 = cadre.x0 + _MARGE_DECOUPE, cadre.y0 + _MARGE_DECOUPE
    x1, y1 = cadre.x1 - _MARGE_DECOUPE, cadre.y1 - _MARGE_DECOUPE
    largeur = max(int(round((x1 - x0) * t.echelle_x)), 1)
    hauteur = max(int(round((y1 - y0) * t.echelle_y)), 1)

    if t.pente == 0.0:
        gauche, haut = t.vers_pixels(x0, y0)
        pixels = np.array(grise.crop((gauche, haut, gauche + largeur, haut + hauteur)))
    else:
        # Pillow lit (u, v) → (a·u + b·v + c, d·u + e·v + f) dans l'image source.
        c = x0 * t.echelle_x + t.decalage_x - t.pente * y0 * t.echelle_y
        f = y0 * t.echelle_y + t.decalage_y + t.pente * x0 * t.echelle_x
        zone = grise.transform(
            (largeur, hauteur), Image.AFFINE, (1.0, -t.pente, c, t.pente, 1.0, f),
            resample=Image.BICUBIC, fillcolor=255,
        )
        pixels = np.array(zone)

    return pixels, t.echelle_x, t.echelle_y


def _decouper_cadre(
    grise: Image.Image,
    cadre: CadreReponse,
    transformation: Recalage,
    numero: int,
    dossier_sortie: Path,
    seuil_encre: int,
    taux_vide: float,
) -> ZoneDecoupee:
    pixels, echelle_x, echelle_y = _extraire_cadre(grise, cadre, transformation)

    # Le code typographié est effacé avant tout comptage : il est imprimé en
    # noir, le seuillage ne peut pas l'écarter, et le laisser ferait passer pour
    # remplie une zone restée vierge.
    origine_x = cadre.x0 + _MARGE_DECOUPE
    origine_y = cadre.y0 + _MARGE_DECOUPE
    cx0 = max(int((cadre.code_x0 - _PAD_CODE - origine_x) * echelle_x), 0)
    cy0 = max(int((cadre.code_y0 - _PAD_CODE - origine_y) * echelle_y), 0)
    cx1 = max(int(round((cadre.code_x1 + _PAD_CODE - origine_x) * echelle_x)), 0)
    cy1 = max(int(round((cadre.code_y1 + _PAD_CODE - origine_y) * echelle_y)), 0)
    pixels[cy0:cy1, cx0:cx1] = 255

    encre = pixels < seuil_encre
    taux = float(encre.mean()) if pixels.size else 0.0

    nettoye = np.where(encre, pixels, np.uint8(255))
    chemin = dossier_sortie / f"{cadre.code}.png"
    Image.fromarray(nettoye).save(chemin)

    return ZoneDecoupee(
        code=cadre.code,
        format=cadre.format,
        page=numero,
        chemin=chemin,
        vide=taux < taux_vide,
        taux_encre=taux,
    )


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
