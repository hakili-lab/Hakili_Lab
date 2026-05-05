# Hakili Lab — Correction Intelligente de Copies Manuscrites

> Prototype IA pour l'évaluation et la remédiation de copies manuscrites de mathématiques et physique-chimie.

---

## Vision

Hakili Lab développe un assistant IA qui aide les enseignants à :

- **Corriger** des copies manuscrites numérisées, question par question, selon un barème fourni.
- **Diagnostiquer** les lacunes de chaque élève par compétence.
- **Générer** un plan de remédiation personnalisé.
- **Produire** un rapport PDF structuré et un export JSON pour l'analyse.

L'outil assiste l'enseignant — il ne remplace pas son jugement. Toute note finale est validée par un humain.

---

## Fonctionnalités MVP

| Fonctionnalité | Statut |
|---|---|
| Upload copie PDF multi-pages / JPG / PNG | Prêt (UI) |
| Upload énoncé et barème | Prêt (UI) |
| Contrôle qualité image (résolution, luminosité) | Implémenté |
| Transcription structurée via LLM multimodal | À câbler |
| Correction question par question selon barème | À câbler |
| Score de confiance + flag révision humaine | Modélisé |
| Diagnostic par compétence | À câbler |
| Rapport PDF enseignant | Implémenté (base) |
| Export JSON structuré | Modélisé |
| Interface de validation enseignant | À câbler |

---

## Architecture

```
Copie PDF/images
      │
      ▼
┌─────────────────┐
│   Ingestion     │  PDF → images, anonymisation, stockage local
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Qualité Image   │  Résolution, flou, luminosité, orientation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Transcription   │  LLM multimodal → JSON structuré
│    (VLM)        │  texte + formules + schémas + [ILLISIBLE]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Correction    │  Mapping réponse ↔ barème → note + confiance
│    (LLM)        │  requires_teacher_review si incertitude
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Diagnostic    │  Compétences maîtrisées / lacunes / erreurs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PDF + JSON     │  Rapport enseignant + export données
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validation     │  Revue humaine obligatoire avant restitution
│  Enseignant     │
└─────────────────┘
```

---

## Structure du projet

```
hakili_ai_correction/
├── src/
│   ├── api/          # Abstraction fournisseurs IA (Anthropic, OpenAI, Gemini)
│   ├── core/         # Configuration, paramètres
│   ├── models/       # Modèles Pydantic (domaine métier)
│   ├── pipeline/     # Ingestion, OCR/VLM, correction, diagnostic, rapport
│   ├── ui/           # Interface Streamlit
│   └── utils/        # Logs, anonymisation, validation JSON
├── prompts/          # Prompts LLM (transcription, correction, diagnostic)
├── data/schemas/     # Schémas JSON de sortie (source de vérité)
├── docs/             # Stratégie, architecture, décisions, brief CEO
├── tests/            # Tests unitaires et d'intégration
├── .env.example      # Variables d'environnement (template)
├── Makefile          # Commandes projet (Linux/Mac)
├── setup.ps1         # Script setup Windows PowerShell
└── requirements.txt  # Dépendances épinglées
```

---

## Installation

### Prérequis
- Python 3.11+
- Une clé API : [Anthropic](https://console.anthropic.com) *(recommandé)*, OpenAI, ou Google

### Linux / Mac
```bash
git clone https://github.com/UrieThiombiano/Hakili_Lab.git
cd Hakili_Lab
make setup
cp .env.example .env
# Éditez .env et renseignez votre clé API
make run
```

### Windows (PowerShell)
```powershell
git clone https://github.com/UrieThiombiano/Hakili_Lab.git
cd Hakili_Lab
.\setup.ps1
# Éditez .env et renseignez votre clé API
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

---

## Commandes

| Commande | Description |
|---|---|
| `make setup` | Créer le venv et installer les dépendances |
| `make run` | Lancer l'interface de démonstration |
| `make test` | Lancer les tests |
| `make lint` | Vérifier la qualité du code |
| `make clean` | Nettoyer le cache Python |

---

## Fournisseurs IA supportés

| Fournisseur | Variable `.env` | Modèle par défaut |
|---|---|---|
| Anthropic *(recommandé)* | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Google | `GOOGLE_API_KEY` | `gemini-2.0-flash` |

---

## Confidentialité & Sécurité

- Les copies sont **anonymisées** avant traitement (suppression nom, métadonnées EXIF).
- Stockage **local uniquement** au stade prototype — aucune donnée envoyée à des serveurs tiers sauf l'API IA choisie.
- Les logs ne contiennent **jamais** de données personnelles ni d'images.
- La validation humaine est **obligatoire** avant toute restitution officielle.

---

## Évaluation

Le prototype sera évalué sur 100 copies réelles avec les métriques suivantes :

| Métrique | Cible |
|---|---|
| Écart absolu moyen (note IA vs enseignant) | < 1 point |
| Taux d'accord exact ou ±0.5 pt | > 70 % |
| Taux de questions nécessitant révision | < 20 % |
| Taux d'échec qualité image | < 5 % |
| Temps gagné par copie | > 50 % |

---

## Avertissement

Ce prototype est un **outil d'assistance**. Il ne produit pas de notes officielles sans validation humaine. En cas d'écriture illisible, de formule ambiguë ou de barème incomplet, le système signale explicitement une révision humaine requise.

---

## Roadmap

| Sprint | Contenu | Durée |
|---|---|---|
| S0 | Fondations Python, config, modèles | 3 jours |
| S1 | Abstraction IA + ingestion PDF | 1 semaine |
| S2 | Transcription + correction bout-en-bout | 1 semaine |
| S3 | Diagnostic + PDF + UI complète | 1 semaine |
| S4 | Robustesse + tests | 1 semaine |
| S5 | CI/CD + évaluation 30 copies | 1 semaine |
| S6 | Évaluation 100 copies + rapport final | 1 semaine |

---

*Hakili Lab — Prototype confidentiel. Ne pas diffuser sans autorisation.*
