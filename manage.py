#!/usr/bin/env python
"""Point d'entrée des commandes Django (voir docs/architecture_cible.md)."""
import os
import sys


def _faire_confiance_au_magasin_du_systeme() -> None:
    """Vérifie les certificats TLS avec le magasin du système, pas avec `certifi`.

    Un antivirus qui inspecte le HTTPS (Avast, Kaspersky, ESET…) remplace le
    certificat du serveur par un certificat qu'il signe lui-même. Sa racine est
    installée dans le magasin de Windows — les navigateurs l'acceptent — mais
    `certifi`, le paquet que les SDK Anthropic/OpenAI utilisent par défaut,
    embarque sa propre liste et ne la contient pas. Tout appel de modèle échoue
    alors sur `CERTIFICATE_VERIFY_FAILED`, sur une machine où le réseau marche
    par ailleurs.

    `truststore` fait déléguer la vérification au système. On ne désactive
    rien : ce qui est refusé par Windows reste refusé.

    Facultatif à dessein — sans le paquet, on retombe sur le comportement
    d'origine plutôt que d'empêcher `manage.py` de démarrer.
    """
    try:
        import truststore
    except ImportError:
        return
    truststore.inject_into_ssl()


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hakili.settings")
    _faire_confiance_au_magasin_du_systeme()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django est introuvable. Installer les dépendances : "
            "pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
