"""
Jetons opaques pour désigner un élève dans une URL.

Pourquoi ne pas mettre `identifiant_hakili` directement dans l'URL
-----------------------------------------------------------------
D-CEO-25 a explicitement retiré la colonne « Identifiant » de l'interface :
`identifiant_hakili` ne doit jamais être affiché. Une URL le ferait réapparaître
dans la barre d'adresse, l'historique du navigateur, les journaux du serveur, les
en-têtes `Referer` et la moindre capture d'écran partagée.

Deuxième bénéfice, moins évident mais réel : un identifiant en clair se devine et
s'énumère. `can_access_eleve` refuserait bien l'accès, mais la seule différence
entre un 403 et un 404 renseigne déjà sur l'existence d'un élève. Un jeton signé
supprime cette surface : une valeur forgée ne passe pas la signature.

Le jeton est stable tant que `DJANGO_SECRET_KEY` ne change pas — les liens restent
donc partageables entre collègues et peuvent être mis en favori. Changer la clé les
invalide, ce qui est le comportement attendu d'un secret tournant.
"""
from __future__ import annotations

from django.core import signing

_SEL = "hakili.eleve"


def jeton_eleve(identifiant: str) -> str:
    """Jeton opaque et signé désignant un élève."""
    return signing.dumps(identifiant, salt=_SEL)


def identifiant_depuis_jeton(jeton: str) -> str | None:
    """Identifiant d'origine, ou `None` si le jeton est absent, forgé ou altéré.

    Pas de date d'expiration : un lien vers le profil d'un élève reste valable tant
    que l'élève existe. Mettre une durée de vie obligerait un tuteur à repasser par
    la liste à chaque fois, sans rien protéger de plus — l'autorisation est vérifiée
    à chaque requête de toute façon.
    """
    try:
        return signing.loads(jeton, salt=_SEL)
    except signing.BadSignature:
        return None
