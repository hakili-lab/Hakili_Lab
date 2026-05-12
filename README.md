# Hakili Lab — Correction IA de copies manuscrites

Outil d'évaluation et de remédiation assistée par IA pour copies manuscrites de **mathématiques**.  
Pipeline complet : ingestion PDF/image → transcription → correction → diagnostic → rapport PDF.

---

## État d'avancement — 12 mai 2026

### Ce qui est implémenté et fonctionnel

| Composant | Fichier(s) | État |
|---|---|---|
| Modèles Pydantic (domaine complet) | `src/models/domain.py` | ✅ Complet |
| Configuration `.env` via Pydantic Settings | `src/core/config.py` | ✅ Complet |
| Anonymisation E-001… + CSV persistant | `src/core/anonymizer.py` | ✅ Complet |
| Ingestion PDF multi-pages (PyMuPDF) | `src/pipeline/ingestion.py` | ✅ Complet |
| Ingestion images JPG/PNG multi-fichiers | `src/pipeline/ingestion.py` | ✅ Complet |
| Contrôle qualité image (flou, luminosité, résolution) | `src/pipeline/image_quality.py` | ✅ Complet |
| Client Claude avec retry + prompt caching | `src/api/claude_client.py` | ✅ Complet |
| Transcription multimodale (claude-opus-4-7) | `src/api/claude_client.py` | ✅ Câblé |
| Correction selon barème 0/1 (claude-opus-4-7) | `src/api/claude_client.py` | ✅ Câblé |
| Couche instructions expert optionnelle | `src/api/claude_client.py` | ✅ Câblé |
| Diagnostic pédagogique (claude-haiku-4-5) | `src/api/claude_client.py` | ✅ Câblé |
| Orchestrateur pipeline complet | `src/pipeline/pipeline.py` | ✅ Complet |
| Rapport PDF 7 éléments (D-CEO-06) | `src/pipeline/pdf_report.py` | ✅ Complet |
| Export JSON structuré | `src/pipeline/pipeline.py` | ✅ Complet |
| Prompts (transcription, correction, diagnostic) | `prompts/` | ✅ Rédigés |
| Interface Streamlit — Mode Copie Unique | `src/ui/app.py` | ✅ Complet |
| Interface Streamlit — Mode Batch | `src/ui/app.py` | ✅ Complet |
| Synthèse de classe (batch) | `src/ui/app.py` | ✅ Complet |
| Tests unitaires modèles (binaire, Pydantic) | `tests/test_models.py` | ✅ Complet |

### Ce qui reste à faire

| Tâche | Priorité | Notes |
|---|---|---|
| Tester le pipeline end-to-end sur de vraies copies | 🔴 Critique | Prompts non validés sur copies réelles |
| Ajuster les prompts (`prompts/*.md`) après premiers tests | 🔴 Critique | Itération nécessaire sur la transcription manuscrite |
| Tests d'intégration pipeline (ingestion → PDF) | 🟠 Haute | Seuls les modèles sont couverts actuellement |
| Tests du parsing barème (formats texte variés) | 🟠 Haute | `_parse_rubric_text` non testé |
| Vérifier le logo Hakili Lab dans le PDF | 🟡 Moyenne | Dépend de `src/ui/hakili_logo.png` |
| Enrichir la synthèse batch (distribution compétences) | 🟡 Moyenne | Actuellement : notes uniquement |
| Évaluation sur 100 copies avec enseignant référent | 🟡 Moyenne | Objectif D005 |
| Mesurer la précision (écart IA vs enseignant) | 🟡 Moyenne | Cible : ±0 pt avec instructions expert |
| État qualité image "medium" (pages mixtes) | 🟢 Basse | Actuellement binaire good/poor |
| Packaging / déploiement (Docker ou service cloud) | 🟢 Basse | Hors périmètre MVP |

---

## Prérequis

- **Python 3.11+**
- **Clé API Anthropic** — [console.anthropic.com](https://console.anthropic.com)
- `make` facultatif (Linux/Mac natif · Windows : `winget install GnuWin32.Make`)

---

## Installation et lancement

### Linux / Mac

```bash
git clone <url-du-repo>
cd hakili_ai_correction

# 1. Créer l'environnement et installer les dépendances
make setup

# 2. Configurer les variables d'environnement
cp .env.example .env
# Ouvrir .env et renseigner ANTHROPIC_API_KEY

# 3. Lancer l'interface
make run
```

### Windows (PowerShell)

```powershell
git clone <url-du-repo>
cd hakili_ai_correction

# 1. Créer l'environnement et installer les dépendances
python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

# 2. Configurer les variables d'environnement
Copy-Item .env.example .env
# Ouvrir .env dans un éditeur et renseigner ANTHROPIC_API_KEY

# 3. Lancer l'interface
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

### Windows avec make

```powershell
make setup
# Éditer .env
make run
```

---

## Variables d'environnement (`.env`)

```env
# Obligatoire
ANTHROPIC_API_KEY=sk-ant-...

# Modèles (valeurs par défaut correctes — ne pas modifier sans raison)
CLAUDE_MODEL_HEAVY=claude-opus-4-7            # transcription + correction
CLAUDE_MODEL_LIGHT=claude-haiku-4-5-20251001  # diagnostic

# Seuils qualité image
CONFIDENCE_REVIEW_THRESHOLD=0.75
IMAGE_MIN_RESOLUTION=1000
IMAGE_BLUR_THRESHOLD=100.0

# Stockage local
RUNS_DIR=./runs
```

---

## Commandes disponibles

| Commande | Description |
|---|---|
| `make setup` | Créer le venv et installer les dépendances |
| `make run` | Lancer l'interface Streamlit |
| `make test` | Lancer les tests unitaires |
| `make lint` | Vérifier la qualité du code (ruff + mypy) |
| `make clean` | Nettoyer le cache Python |

---

## Structure du projet

```
hakili_ai_correction/
│
├── src/
│   ├── api/
│   │   └── claude_client.py      # Client Anthropic : transcription, correction, diagnostic
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (.env)
│   │   └── anonymizer.py         # Numérotation E-001… + CSV correspondance
│   ├── models/
│   │   └── domain.py             # Modèles Pydantic (Rubric, CopyGrade, Diagnostic…)
│   ├── pipeline/
│   │   ├── ingestion.py          # PDF → images / images → session
│   │   ├── image_quality.py      # Contrôle qualité (OpenCV + PIL)
│   │   ├── pipeline.py           # Orchestrateur complet
│   │   └── pdf_report.py         # Génération rapport PDF (ReportLab)
│   └── ui/
│       ├── app.py                # Interface Streamlit (Unique + Batch + À propos)
│       └── hakili_logo.png       # Logo (requis pour l'en-tête PDF et la sidebar)
│
├── prompts/
│   ├── transcription_prompt.md   # Prompt transcription multimodale
│   ├── grading_prompt.md         # Prompt correction selon barème
│   └── diagnostic_prompt.md      # Prompt diagnostic + remédiation
│
├── data/schemas/
│   ├── rubric.schema.json        # Schéma JSON barème
│   ├── grading.schema.json       # Schéma JSON correction
│   └── transcription.schema.json # Schéma JSON transcription
│
├── tests/
│   └── test_models.py            # Tests unitaires Pydantic
│
├── docs/
│   ├── decision_register.md      # Registre des décisions (D001–D-CEO-09)
│   ├── analysis_and_strategy.md  # Analyse et stratégie
│   └── architecture.md           # Architecture technique
│
├── runs/                         # Sorties pipeline (gitignored sauf .gitkeep)
├── .env.example                  # Template variables d'environnement
├── requirements.txt              # Dépendances Python épinglées
├── Makefile                      # Commandes projet
└── CLAUDE.md                     # Instructions Claude Code
```

---

## Flux de traitement

```
Copie PDF ou image(s)
        │
        ▼
   Ingestion        PDF → images haute résolution (300 dpi) · nommage page_01…
        │
        ▼
 Qualité image      Flou (Laplacien) · luminosité · résolution minimale
        │            ⚠ Avertissement si insuffisant (non bloquant)
        ▼
 Transcription      claude-opus-4-7 · texte + formules + schémas + [ILLISIBLE]
        │
        ▼
  Correction        claude-opus-4-7 · score 0/1 par question · confiance · commentaire
        │            + instructions expert optionnelles (D-CEO-04)
        ▼
  Diagnostic        claude-haiku-4-5 · forces · lacunes · plan de remédiation
        │
        ▼
  PDF + JSON        Rapport 7 éléments (D-CEO-06) · export données structuré
        │
        ▼
 Téléchargement     Rapport PDF · JSON · fiche de correspondance anonyme
```

---

## Décisions structurantes

Registre complet : [docs/decision_register.md](docs/decision_register.md)

| ID | Décision |
|---|---|
| D-CEO-01 | Mathématiques uniquement pour le MVP |
| D-CEO-02 | Barème binaire 0/1 — aucune notation partielle |
| D-CEO-03 | Anthropic Claude exclusivement (opus pour le raisonnement, haiku pour les tâches légères) |
| D-CEO-04 | Instructions expert optionnelles injectées dans le prompt de correction |
| D-CEO-05 | Validation humaine hors plateforme — l'enseignant valide sur le PDF exporté |
| D-CEO-06 | Rapport PDF : note · commentaires · révisions · diagnostic · remédiation · confiance · logo |
| D-CEO-07 | Anonymisation automatique — le PDF ne contient jamais le nom de l'élève |
| D-CEO-09 | Deux modes d'interface : Copie Unique et Batch |

---

## Confidentialité

- Données stockées **localement** dans `runs/` — aucun envoi cloud hors API Anthropic
- Noms remplacés par `E-001`, `E-002`… avant tout traitement IA
- Fiche de correspondance `nom ↔ numéro` téléchargeable séparément, jamais incluse dans les rapports
- Les logs ne contiennent aucune donnée personnelle

---

*Prototype confidentiel — Hakili Lab · Usage pédagogique exclusif*
