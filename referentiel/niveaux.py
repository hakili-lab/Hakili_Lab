"""
Ordre des niveaux scolaires — une seule définition pour tout le projet.

Sert à deux endroits qui posent la même question : « cette compétence a-t-elle
déjà été enseignée au moment du test ? »

· Le tagage du corpus (module 3) le signale en avertissement — une compétence
  introduite au niveau du test, ou après, n'a pas encore été vue et l'échec y est
  normal. Relevé à la main sur une copie d'entrée en 5ème taguée `N.FRA2`,
  compétence de 5ème.
· Le diagnostic sans ancrage (module 4) s'en sert pour **restreindre** le
  catalogue soumis au modèle : proposer les compétences de Terminale pour une
  copie de 6ème ouvrirait des milliers de rapprochements absurdes.

Les libellés sont ceux du classeur (`niveau_intro`), sans accents : ce sont des
clés de rapprochement, pas du texte d'interface.
"""
from __future__ import annotations

#: Du plus ancien au plus récent. `Primaire` couvre les 17 compétences que le
#: classeur place avant la 6ème.
ORDRE_NIVEAUX: dict[str, int] = {
    "Primaire": 0,
    "6eme": 1,
    "5eme": 2,
    "4eme": 3,
    "3eme": 4,
    "2ndeC": 5,
    "1ereD": 6,
    "tleD": 7,
}


def deja_enseigne(niveau_intro: str, niveau_test: str) -> bool:
    """Vrai si `niveau_intro` précède strictement le niveau du test.

    Un test d'entrée **en** 5ème évalue ce qui précède la 5ème : une compétence
    introduite en 5ème n'y a pas sa place. L'égalité compte donc comme « pas
    encore enseignée ».

    Un niveau inconnu rend `False` — mieux vaut restreindre trop que proposer une
    compétence hors de portée.
    """
    rang_intro = ORDRE_NIVEAUX.get(niveau_intro)
    rang_test = ORDRE_NIVEAUX.get(niveau_test)
    if rang_intro is None or rang_test is None:
        return False
    return rang_intro < rang_test
