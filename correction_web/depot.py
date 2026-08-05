"""Le dépôt de copies, côté Django — l'implémentation de `src/pipeline/depot.py`.

Remplace `src/services/copie_service.py` et les sessions SQLAlchemy ouvertes à la
main dans le pipeline (D-CEO-40). Django gère les connexions ; il ne reste que
les quatre gestes eux-mêmes.

**Les quatre opérations sont rejouables**, et ce n'est pas un raffinement. Le
pipeline enveloppe chaque écriture dans un retry (`_retry_db`) parce qu'une base
serverless refuse parfois la première connexion après une inactivité. Avec les
anciennes fonctions, ce retry ne pouvait pas fonctionner : la seconde tentative
recréait la copie et échouait sur la clé primaire, ou ajoutait un **second**
document du même type. Ce défaut était invisible — le retry existait, il ne
rattrapait rien.

`ajouter_document` remplace donc le document de même type au lieu d'en empiler
un autre. C'est aussi la correction d'un défaut de fond : `get_document_by_type`
prenait le premier trouvé, sans ordre garanti. Une copie recorrigée pouvait
servir l'ancien rapport.
"""
from __future__ import annotations

from django.db import transaction

from suivi.models import Copie, Document


class DepotDjango:
    def creer_copie(
        self, *, copy_id: str, identifiant_hakili: str, classe: str, annee_scolaire: str
    ) -> None:
        Copie.objects.get_or_create(
            copy_id=copy_id,
            defaults={
                "identifiant_hakili": identifiant_hakili,
                "classe": classe,
                "annee_scolaire": annee_scolaire,
            },
        )

    def ajouter_document(self, *, copy_id: str, type_document: str, contenu: bytes) -> None:
        with transaction.atomic():
            Document.objects.filter(copie_id=copy_id, type=type_document).delete()
            Document.objects.create(
                copie_id=copy_id, type=type_document, fichier=contenu
            )

    def maj_notes(self, *, copy_id: str, notes_finales: float | None) -> None:
        Copie.objects.filter(copy_id=copy_id).update(notes_finales=notes_finales)

    def maj_classe(self, *, copy_id: str, classe: str) -> None:
        Copie.objects.filter(copy_id=copy_id).update(classe=classe)
