# Architecture technique — Hakili Lab AI Correction

## Vue d'ensemble

Le système est organisé en pipeline linéaire avec des points de contrôle humain. Chaque étape produit un artefact JSON validé contre un schéma strict.

## Diagramme de flux

```
┌──────────────────────────────────────────────────┐
│                  INTERFACE ENSEIGNANT             │
│                   (Streamlit UI)                  │
│  Upload copie | Upload énoncé | Upload barème     │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│                  INGESTION (S1)                   │
│  • PDF → images (PyMuPDF)                        │
│  • Anonymisation (suppression nom, EXIF)          │
│  • Stockage local : runs/{copy_id}/pages/         │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│             CONTRÔLE QUALITÉ IMAGE (S1)           │
│  • Résolution minimale (1000×1000px)             │
│  • Flou (variance Laplacien via OpenCV)           │
│  • Luminosité (PIL ImageStat)                    │
│  • Orientation estimée                            │
│  → Si mauvaise qualité : demande de rescan        │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│              TRANSCRIPTION VLM (S2)               │
│  • Envoi pages au modèle multimodal               │
│  • Retour JSON : texte + formules + schémas       │
│  • Zones [ILLISIBLE] explicitement marquées       │
│  • Validation contre transcription.schema.json    │
│  → Artefact : runs/{copy_id}/transcription.json   │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│              CORRECTION BARÈME (S2)               │
│  • Parsing barème (texte / PDF)                  │
│  • Mapping réponse ↔ question                    │
│  • Note + confiance + commentaire par question    │
│  • requires_teacher_review si confiance < seuil   │
│  • Validation contre grading.schema.json          │
│  → Artefact : runs/{copy_id}/grading.json         │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│              DIAGNOSTIC (S3)                      │
│  • Analyse compétences maîtrisées / lacunes       │
│  • Erreurs récurrentes identifiées                │
│  • Plan de remédiation priorisé                   │
│  • Validation contre diagnostic.schema.json       │
│  → Artefact : runs/{copy_id}/diagnostic.json      │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│           GÉNÉRATION RAPPORT (S3)                 │
│  • PDF structuré (ReportLab + Jinja2)            │
│  • Export JSON consolidé                          │
│  → runs/{copy_id}/report.pdf                      │
│  → runs/{copy_id}/export.json                     │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│         VALIDATION HUMAINE OBLIGATOIRE            │
│  • Interface de revue des items flaggés           │
│  • Correction manuelle possible                   │
│  • Bouton "Valider et générer rapport final"      │
│  → Rapport final signé par l'enseignant           │
└──────────────────────────────────────────────────┘
```

## Structure des modules

### `src/api/` — Abstraction fournisseur IA

```python
AIProvider (interface abstraite)
    ├── AnthropicProvider   → claude-sonnet-4-6
    ├── OpenAIProvider      → gpt-4o
    └── GoogleProvider      → gemini-2.0-flash
```

Changer de fournisseur = modifier `AI_PROVIDER` dans `.env`. Aucun changement de code.

### `src/pipeline/` — Étapes du pipeline

| Module | Responsabilité |
|---|---|
| `ingestion.py` | PDF → images, anonymisation, organisation dossiers |
| `image_quality.py` | Contrôle qualité, rapport par page |
| `transcription.py` | Appel VLM, parsing JSON, validation schéma |
| `correction.py` | Parsing barème, correction, score confiance |
| `diagnostic.py` | Analyse compétences, plan remédiation |
| `pdf_report.py` | Génération rapport PDF structuré |

### `src/models/` — Schémas Pydantic

Chaque artefact JSON a un modèle Pydantic correspondant pour la validation en mémoire et la sérialisation :

| Modèle | JSON Schema |
|---|---|
| `TranscriptionResult` | `transcription.schema.json` |
| `CopyGrade` + `QuestionGrade` | `grading.schema.json` |
| `DiagnosticResult` | `diagnostic.schema.json` |

### `src/core/` — Configuration

`Settings` (Pydantic BaseSettings) charge toutes les variables depuis `.env` :
- Clés API par fournisseur
- Modèle IA par fournisseur
- Seuils qualité image
- Seuil de confiance pour révision humaine
- Chemin de stockage

## Principes anti-hallucination

Le système produit 3 niveaux d'output pour chaque réponse :

```json
{
  "observed_answer": "ce qui est réellement lisible sur la copie",
  "interpretation": "ce que le modèle pense que l'élève voulait écrire",
  "uncertainties": ["zone floue page 2", "signe ambigu dans formule Q3"]
}
```

Si `uncertainties` est non vide → `confidence` baisse automatiquement → `requires_teacher_review: true` si en dessous du seuil.

## Stockage local

```
runs/
└── anon_001/
    ├── pages/
    │   ├── page_01.jpg
    │   └── page_02.jpg
    ├── transcription.json
    ├── grading.json
    ├── diagnostic.json
    ├── report.pdf
    └── export.json
```

Aucune donnée ne quitte la machine sauf les appels API (images anonymisées + texte).

## Décisions d'architecture enregistrées

Voir [decision_register.md](decision_register.md) pour le registre complet.

| ID | Décision |
|---|---|
| D001 | Ingestion par copie complète, pas exercice par exercice |
| D002 | Validation humaine obligatoire |
| D003 | JSON comme source de vérité, PDF comme rendu |
| D004 | Abstraction fournisseur IA |
| D005 | Streamlit pour MVP |
| D006 | Stockage local anonymisé |
| D007 | Évaluation sur 100 copies |
