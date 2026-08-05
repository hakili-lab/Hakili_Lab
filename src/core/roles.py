"""Les trois rôles du personnel.

Vivait dans `src/db/models.py`, sans jamais y être un type de colonne SQL :
l'identité du personnel a quitté PostgreSQL en D-CEO-21/25 et vit dans le Sheet.
Ce n'était plus qu'un enum Python coincé dans une couche de persistance, et il
obligeait tout ce qui parle de rôles à importer SQLAlchemy. Sorti de là au
retrait du second ORM (D-CEO-40).

Les valeurs sont alignées sur la colonne `role` du Sheet personnel
(`src/integrations/google_sheets.py`), qui en est la source de vérité — les
changer ici sans les changer là-bas casserait la connexion en silence.
"""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    admin = "administrateur"
    responsable_centre = "responsable"
    enseignant = "enseignant"
