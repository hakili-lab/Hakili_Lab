# Architecture finale — Hakili Lab AI Correction
**Version 1.0 — 2026-05-08**
**Matière : Mathématiques | Fournisseur IA : Anthropic Claude**

---

## Vue d'ensemble

Le système corrige des copies manuscrites de mathématiques en suivant un pipeline séquentiel. Chaque étape produit un artefact JSON validé par un schéma Pydantic. Le rapport final est affiché dans l'interface, puis téléchargeable en PDF. La validation humaine se fait hors plateforme, sur le rapport exporté.

---

## Pipeline de traitement

```
┌─────────────────────────────────────────────────────────────────────┐
│                       INTERFACE ENSEIGNANT                          │
│                          (Streamlit)                                │
│                                                                     │
│   Mode Copie Unique                 Mode Batch                      │
│   ─────────────────                 ──────────────────              │
│   • Upload 1 copie (PDF/images)     • Upload N copies               │
│   • Upload énoncé                   • Upload énoncé commun          │
│   • Upload barème                   • Upload barème commun          │
│   • [Optionnel] Instructions expert • Saisie liste élèves           │
│   • Saisie nom élève                                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ANONYMISATION (S0)                              │
│  • Attribution numéro élève (E-001, E-002, …)                      │
│  • Fiche correspondance nom ↔ numéro stockée séparément             │
│  • Suppression métadonnées EXIF des images                          │
│  → runs/{copy_id}/  (copy_id = numéro anonyme)                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INGESTION (S1)                                 │
│  • PDF multi-pages → images JPG (PyMuPDF)                          │
│  • Images multiples → liste ordonnée                               │
│  • Organisation : runs/{copy_id}/pages/page_01.jpg, …              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CONTRÔLE QUALITÉ IMAGE (S1)                        │
│  • Résolution minimale (1000×1000 px)                              │
│  • Détection flou (variance Laplacien, OpenCV)                     │
│  • Luminosité (PIL ImageStat)                                      │
│  • Ordre et complétude des pages                                   │
│  → Si qualité insuffisante : alerte + demande rescan               │
│  → Artefact : runs/{copy_id}/quality_report.json                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│               TRANSCRIPTION MULTIMODALE (S2)                        │
│  Modèle : claude-opus-4-7 (vision)                                 │
│                                                                     │
│  • Envoi des pages au modèle Claude                                │
│  • Extraction structurée : texte, calculs, formules LaTeX          │
│  • Marquage explicite des zones [ILLISIBLE]                        │
│  • Score de confiance par zone                                     │
│  • Validation schéma : TranscriptionResult (Pydantic)              │
│  → Artefact : runs/{copy_id}/transcription.json                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  PARSING DU BARÈME (S2)                             │
│  • Lecture de l'énoncé et du barème (PDF/texte)                    │
│  • Extraction questions et sous-questions                          │
│  • Format : liste plate de questions (sous-questions = questions)  │
│  • Chaque item : identifiant, intitulé, points_max = 1             │
│  → Artefact : runs/{copy_id}/rubric.json                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CORRECTION SELON BARÈME (S2)                       │
│  Modèle : claude-opus-4-7                                          │
│                                                                     │
│  Prompt système inclut :                                           │
│    [1] L'énoncé complet                                            │
│    [2] Le barème (questions + points)                              │
│    [3] La transcription de l'élève                                 │
│    [4] Instructions expert [OPTIONNEL — si fournies]               │
│                                                                     │
│  Pour chaque question :                                            │
│    • score : 0 ou 1 (binaire strict)                              │
│    • confidence : 0.0 → 1.0                                        │
│    • comment : commentaire pédagogique                             │
│    • requires_review : true si confidence < seuil configurable     │
│    • observed_answer : texte brut de la réponse élève             │
│                                                                     │
│  • Validation schéma : CopyGrade / QuestionGrade (Pydantic)        │
│  → Artefact : runs/{copy_id}/grading.json                          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DIAGNOSTIC (S3)                                 │
│  Modèle : claude-opus-4-7                                          │
│                                                                     │
│  • Analyse des erreurs par type de compétence mathématique         │
│  • Identification des lacunes récurrentes                          │
│  • Compétences maîtrisées vs non maîtrisées                        │
│  • Plan de remédiation priorisé (générique, sans librairie)        │
│  • Validation schéma : DiagnosticResult (Pydantic)                 │
│  → Artefact : runs/{copy_id}/diagnostic.json                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                GÉNÉRATION DU RAPPORT (S3)                           │
│                                                                     │
│  Contenu :                                                         │
│    • Note totale et détail par question (avec sous-questions)      │
│    • Commentaire pédagogique par question                          │
│    • Zones marquées "Révision requise"                             │
│    • Diagnostic des compétences                                    │
│    • Plan de remédiation                                           │
│    • Score de confiance IA visible                                 │
│    • Logo Hakili Lab                                               │
│    • Numéro anonyme élève (jamais le nom)                          │
│                                                                     │
│  Formats :                                                         │
│    • JSON consolidé : runs/{copy_id}/export.json                   │
│    • PDF rendu    : runs/{copy_id}/report.pdf  (ReportLab)         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  RESTITUTION DANS L'INTERFACE                       │
│                                                                     │
│  • Affichage complet du rapport dans Streamlit                     │
│  • Bouton "Télécharger le PDF"                                     │
│  • Bouton "Télécharger la fiche de correspondance" (nom ↔ numéro) │
│  • Mode Batch : synthèse de classe (distribution notes,           │
│    compétences collectives, élèves à risque)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Structure des modules

```
src/
├── core/
│   ├── config.py          # Settings Pydantic (variables .env)
│   └── anonymizer.py      # Attribution numéros + fiche correspondance
│
├── pipeline/
│   ├── ingestion.py       # PDF → images, organisation dossiers
│   ├── image_quality.py   # Contrôle qualité par page
│   ├── transcription.py   # Appel Claude vision, parsing JSON
│   ├── rubric_parser.py   # Parsing barème → liste questions binaires
│   ├── correction.py      # Correction avec prompt expert optionnel
│   ├── diagnostic.py      # Analyse compétences + remédiation
│   └── pdf_report.py      # Génération PDF (ReportLab + Jinja2)
│
├── models/
│   ├── transcription.py   # TranscriptionResult, PageTranscription
│   ├── rubric.py          # Rubric, RubricItem
│   ├── grading.py         # CopyGrade, QuestionGrade
│   └── diagnostic.py      # DiagnosticResult, SkillAssessment
│
├── api/
│   └── claude_client.py   # Client Anthropic — transcription + correction
│
└── ui/
    ├── app.py             # Point d'entrée Streamlit
    ├── single_copy.py     # Interface mode Copie Unique
    └── batch.py           # Interface mode Batch
```

---

## Schéma de données — Barème binaire

```python
class RubricItem(BaseModel):
    id: str                  # "Q1", "Q2a", "Q2b", "Q3"
    label: str               # Intitulé de la question
    max_score: Literal[1]    # Toujours 1 — notation binaire
    parent_id: str | None    # "Q2" si sous-question de Q2

class Rubric(BaseModel):
    subject: Literal["mathematics"]
    total_points: int
    items: list[RubricItem]
```

```python
class QuestionGrade(BaseModel):
    rubric_item_id: str
    score: Literal[0, 1]     # Binaire strict
    confidence: float        # 0.0 → 1.0
    comment: str             # Commentaire pédagogique
    observed_answer: str     # Réponse brute élève
    requires_review: bool    # True si confidence < seuil

class CopyGrade(BaseModel):
    copy_id: str             # Numéro anonyme (jamais le nom)
    total_score: int
    total_possible: int
    questions: list[QuestionGrade]
    expert_instructions_used: bool
```

---

## Couche d'instructions expert (optionnelle)

L'enseignant peut saisir avant correction des instructions contextuelles pour le devoir :

```
Exemples d'instructions expert :
  - "Accepter 'f(x) = 2x' et '2x' comme réponses équivalentes pour Q1"
  - "Pour Q3b, la démarche compte même si le résultat est faux : donner 1 si la méthode est correcte"
  - "Tolérer les erreurs de calcul arithmétique mineurs si la logique algébrique est correcte"
```

Ces instructions sont injectées dans le prompt système de correction :
```python
system_prompt = BASE_CORRECTION_PROMPT
if expert_instructions:
    system_prompt += f"\n\n## Instructions spécifiques à ce devoir\n{expert_instructions}"
```

---

## Anonymisation — Flux détaillé

```
Session enseignant
│
├── Saisie noms élèves : ["Alice Martin", "Bob Dupont", …]
│
├── Attribution automatique :
│   E-001 → Alice Martin
│   E-002 → Bob Dupont
│   …
│
├── Stockage fiche : runs/session_{date}/correspondence.csv
│   (séparé des copies, non inclus dans les exports)
│
├── Traitement copies : runs/E-001/, runs/E-002/, …
│   (aucun nom dans les artefacts)
│
└── Export final :
    ├── report_E-001.pdf   ← contient "E-001" uniquement
    └── correspondence.csv ← téléchargeable séparément
```

---

## Mode Batch — Synthèse de classe

En plus des rapports individuels, le mode Batch génère :

```json
{
  "session_id": "batch_2026-05-08",
  "total_copies": 30,
  "class_average": 14.2,
  "score_distribution": {"0-5": 2, "6-10": 5, "11-15": 15, "16-20": 8},
  "weakest_skills": ["Factorisation", "Résolution équation second degré"],
  "strongest_skills": ["Calcul littéral simple", "Développement"],
  "copies_requiring_review": ["E-003", "E-017"]
}
```

---

## Configuration `.env`

```env
# Fournisseur IA
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL_HEAVY=claude-opus-4-7
CLAUDE_MODEL_LIGHT=claude-haiku-4-5-20251001

# Seuils
CONFIDENCE_REVIEW_THRESHOLD=0.75   # En dessous → requires_review: true
IMAGE_MIN_RESOLUTION=1000           # Pixels (côté court)
IMAGE_BLUR_THRESHOLD=100.0          # Variance Laplacien minimale

# Stockage
RUNS_DIR=./runs
SUBJECT=mathematics
```

---

## Stockage local

```
runs/
├── session_2026-05-08/
│   ├── correspondence.csv          ← fiche nom ↔ numéro (confidentielle)
│   ├── E-001/
│   │   ├── pages/
│   │   │   ├── page_01.jpg
│   │   │   └── page_02.jpg
│   │   ├── quality_report.json
│   │   ├── transcription.json
│   │   ├── rubric.json
│   │   ├── grading.json
│   │   ├── diagnostic.json
│   │   ├── export.json
│   │   └── report.pdf
│   └── E-002/
│       └── …
└── batch_summary_2026-05-08.json   ← synthèse classe (mode Batch)
```

---

## Références

- Décisions : [decision_register.md](decision_register.md)
- Brief CEO : [ceo_decision_brief.md](ceo_decision_brief.md)
- Analyse stratégique : [analysis_and_strategy.md](analysis_and_strategy.md)
