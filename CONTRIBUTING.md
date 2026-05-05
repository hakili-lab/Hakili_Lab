# Contribuer au projet Hakili Lab

## Prérequis

- Python 3.11+
- `make` ou PowerShell (Windows)
- Une clé API Anthropic (pour les tests d'intégration)

## Installation développeur

```bash
git clone https://github.com/UrieThiombiano/Hakili_Lab.git
cd Hakili_Lab
make setup
cp .env.example .env
# Renseigner les clés API dans .env
```

## Workflow

1. Créer une branche depuis `main` : `git checkout -b feature/nom-fonctionnalite`
2. Implémenter en suivant le pipeline défini dans `docs/architecture.md`
3. Ajouter des tests dans `tests/`
4. Vérifier : `make lint && make test`
5. Ouvrir une Pull Request vers `main`

## Règles de code

- Typage Python partout (`from __future__ import annotations` si nécessaire)
- Modèles Pydantic pour tous les artefacts de données
- Pas de nom d'élève ni d'image dans les logs
- `requires_teacher_review: True` obligatoire si la confiance est < seuil
- JSON de sortie toujours validé contre le schéma correspondant

## Structure des commits

```
feat: ajouter module d'ingestion PDF
fix: corriger détection de flou sur images petites
docs: mettre à jour architecture.md
test: ajouter tests d'intégration transcription
```

## Tests

```bash
make test          # Lancer tous les tests
pytest tests/test_models.py -v    # Un fichier spécifique
pytest -k "ingestion" -v          # Par mot-clé
```

## Contact

Urie Thiombiano — uriethiombiano853@gmail.com
