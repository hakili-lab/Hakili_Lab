# Hakili Lab — Correction Assistée par IA

> Outil de **correction assistée par IA** pour copies manuscrites de **mathématiques**,
> conçu pour les **tests de recrutement Hakili Lab** au **Burkina Faso (6e à 3e)**.
> L'objectif central : le **diagnostic pédagogique approfondi**.

---

## Vue d'ensemble

Hakili Lab assiste l'enseignant dans la correction de copies manuscrites numérisées. **L'IA propose, l'enseignant décide.** Le flux se déroule en deux phases :

**Phase A — Correction assistée**
1. L'enseignant scanne la copie et sélectionne le test (ou charge l'énoncé + barème)
2. L'IA transcrit la copie et propose une note pour chaque question
3. L'enseignant valide dans un **tableau de validation** : il accepte ou refuse chaque note IA
4. Le système calcule le **score final /20** en priorisant les décisions enseignant

**Phase B — Diagnostic approfondi** *(l'objectif central du produit)*
5. Pour chaque question échouée, le système récupère les leçons du programme officiel (RAG)
6. L'IA produit un diagnostic précis : causes cachées, lacunes par niveau, leçons non maîtrisées
7. Le rapport final est généré : deux tableaux synthétiques + diagnostic + plan de remédiation

Le système applique un **barème binaire strict 0/1** et intègre un **RAG** sur 121 leçons des curricula officiels 6e–3e.

**Coût en production : ~$0.02/copie.**

---

## Fonctionnalités

### Phase A — Correction assistée
- **Ingestion flexible** — PDF multi-pages, JPG, PNG (conversion automatique à 150 DPI)
- **Transcription multimodale** — texte, formules mathématiques, schémas ; zones `[ILLISIBLE]` avec score de confiance
- **Proposition IA** — note binaire 0/1 par question avec `observed_answer` et commentaire
- **Tableau de validation enseignant** — N° question · bonne réponse · réponse élève · note IA · Accepter/Refuser
- **Score final /20** — calculé en priorisant les décisions enseignant sur les propositions IA
- **Instructions expert** — critères contextuels optionnels injectés dans le prompt de correction

### Tests Hakili (mode auto-chargé)
- **Test d'entrée en 3e v1** — 33 questions NUM + GEO (compétences 6e → 4e)
- **Test d'entrée en 3e v2** — version révisée, barème + corrigé disponibles
- **Test d'entrée en 6e** — 33 questions NUM + GEO (compétences primaires CE1 → CM2)
- **Énoncé + barème pré-chargés** — l'enseignant ne charge que la copie de l'élève

### Phase B — Diagnostic approfondi (objectif central)
- **Base de connaissance** — 121 leçons du programme officiel MEN Burkina Faso (6e, 5e, 4e, 3e)
- **Diagnostic par question échouée** — causes cachées identifiées, pas de généricité
- **Ancrage curriculum** — chaque lacune référence une leçon officielle (`[4e_NUM_Ch4_L3]`, etc.)
- **Causes profondes** — ex. "confond (a+b)² = a²+b² (oubli du terme 2ab)" vs "lacune en algèbre"

### Rapport final
- **Tableau bonnes réponses** — N° question · points attribués
- **Tableau mauvaises réponses** — N° question · 0 / points possibles
- **Diagnostic approfondi** — lacunes précises par niveau scolaire + causes profondes
- **Plan de remédiation** — exercices ciblés en français académique
- **Export PDF XeLaTeX + JSON** — rapport enseignant + données brutes

---

## Architecture et pipeline

```
[Copie PDF/images — scanner 150 DPI ou photos smartphone]
               │
               ▼
╔══════════════════════════════════════════════════════════╗
║               PHASE A — CORRECTION ASSISTÉE             ║
╠══════════════════════════════════════════════════════════╣
║  1. Ingestion                                            ║  PDF → images 150 DPI
║     │                                                    ║
║     ▼                                                    ║
║  2. Transcription  (Gemini 2.5 Flash / Claude)           ║  texte + formules + [ILLISIBLE]
║     │                                                    ║
║     ▼                                                    ║
║  3. Correction IA  (DeepSeek V3 / Claude)                ║  proposition 0/1 par question
║     │                                                    ║
║     ▼                                                    ║
║  4. Tableau de validation enseignant          ← ARRÊT    ║
║     N° Q · bonne réponse · réponse élève                 ║
║     · note IA · [Accepter / Refuser]                     ║
║     │                                                    ║
║     ▼ (après validation)                                 ║
║  5. Score final /20                                      ║  décisions enseignant > IA
╠══════════════════════════════════════════════════════════╣
║               PHASE B — DIAGNOSTIC APPROFONDI           ║
╠══════════════════════════════════════════════════════════╣
║  6. RAG — récupération contexte programme                ║  leçons des questions échouées
║     │                                                    ║
║     ▼                                                    ║
║  7. Diagnostic  (Claude Opus 4.7)                        ║  causes cachées + CompetencyGaps
║     │                                                    ║
║     ▼                                                    ║
║  8. Remédiation  (Mistral Small / Claude)                ║  exercices ciblés par lacune
║     │                                                    ║
║     ▼                                                    ║
║  9. Rapport final PDF + JSON                             ║  tableaux synthèse + diagnostic
╚══════════════════════════════════════════════════════════╝
```

**Routing automatique :** si une clé API est absente ou si le provider échoue, le pipeline bascule sur Claude.

| Tâche | Provider principal | Fallback | Contrôle |
|---|---|---|---|
| Transcription | Gemini 2.5 Flash | Claude Sonnet 4.6 | `VISION_PROVIDER` |
| Correction (proposition) | DeepSeek V3 | Claude Sonnet 4.6 | `GRADING_PROVIDER` |
| Diagnostic | Claude Opus 4.7 | — | `DIAGNOSTIC_PROVIDER` |
| Remédiation | Mistral Small | Claude Sonnet 4.6 | `REMEDIATION_PROVIDER` |
| Extraction barème/énoncé | Claude Sonnet 4.6 | — | toujours Claude |

---

## Système RAG — base de connaissance curriculum

### Structure des fichiers
```
data/knowledge/
├── curriculum_6e.yaml        # 45 leçons : numériques + géométriques (6e)
├── curriculum_5e.yaml        # 33 leçons : multiples, fractions, triangles…
├── curriculum_4e.yaml        # 23 leçons : puissances, polynômes, Thalès, vecteurs…
├── curriculum_3e.yaml        # 20 leçons : Pythagore, trigonométrie, systèmes…
├── bareme_test_3e.yaml       # Barème enrichi test 3e v1 : 33 questions → chunk_ids
├── bareme_test_3e_v2.yaml    # Barème test 3e v2 (nouveau)
├── corrige_test_3e.yaml      # Corrigé officiel test 3e v1
├── corrige_test_3e_v2.yaml   # Corrigé officiel test 3e v2 (nouveau)
└── bareme_test_6e.yaml       # Barème enrichi test 6e : 33 questions → chunk_ids
```

### Format d'un chunk curriculum
```yaml
- id: 4e_NUM_Ch4_L3
  classe: 4e
  domaine: numerique
  chapitre: "Monômes et polynômes"
  lecon: "Identités remarquables"
  savoir: "Les trois identités : (a+b)² = a²+2ab+b² ; (a-b)² = a²-2ab+b² ; (a+b)(a-b) = a²-b²"
  savoir_faire:
    - Développer (a+b)² en utilisant l'identité
    - Factoriser une expression en reconnaissant une identité
  prerequis_ids: [4e_NUM_Ch4_L2]
  mots_cles: [identités remarquables, (a+b)², factorisation]
  erreurs_frequentes:
    - Écrire (a+b)² = a² + b² (oubli du terme 2ab)
```

### Flux RAG
1. L'enseignant sélectionne "Test d'entrée en 3e" → `bareme_id = "hakili_3e_v1"`
2. Après correction, les IDs des questions à 0 sont collectés
3. `CurriculumRetriever` récupère les chunks associés via le barème YAML
4. Le texte des leçons officielles est injecté dans `{{CURRICULUM_CONTEXT}}` du prompt diagnostic
5. Le LLM produit un diagnostic précis : "L'élève ne maîtrise pas `[4e_NUM_Ch4_L3]`…"
6. `CompetencyGap` objects stockés dans `DiagnosticResult.competency_gaps`

---

## Providers IA par tâche

| Tâche | Provider | Modèle | Justification | Coût/copie |
|---|---|---|---|---|
| Transcription | **Google Gemini** | gemini-2.5-flash | Vision native, tier gratuit 1M tok/j | $0.00 |
| Correction | **DeepSeek** | deepseek-chat (V3) | MATH-500 ~90%, meilleur score math | $0.005 |
| Diagnostic | **Claude** | claude-opus-4-7 | Raisonnement profond, causes cachées | $0.008 |
| Remédiation | **Mistral** | mistral-small-latest | Français académique natif | $0.003 |
| Barème/Énoncé | **Claude** | claude-sonnet-4-6 | tool_use forcé, extraction fiable | $0.010 |
| **Total** | | | | **~$0.02** |

> Analyse complète : [docs/ai_providers_analysis.md](docs/ai_providers_analysis.md)

---

## Stack technique

| Couche | Technologie |
|---|---|
| Interface | Streamlit 1.36 |
| Base de connaissance | YAML + pyyaml |
| IA — Vision | Google Gemini 2.5 Flash |
| IA — Raisonnement math | DeepSeek V3 + R1 (API compatible OpenAI) |
| IA — Génération French | Mistral Small 3.1 |
| IA — Extraction structurée | Anthropic Claude Sonnet 4.6 |
| Modèles de données | Pydantic v2 + pydantic-settings |
| PDF → images | PyMuPDF (fitz) · 150 DPI |
| Qualité image | OpenCV + Pillow |
| Génération PDF | XeLaTeX + Jinja2 (fallback ReportLab) |
| Retry API | Tenacity |
| Tests | Pytest |
| Linting / typage | Ruff + MyPy |

---

## Prérequis

- **Python 3.11 ou supérieur**
- **Clé API Anthropic** (obligatoire — fallback + extraction) — [console.anthropic.com](https://console.anthropic.com)
- **Clé API Google AI Studio** (recommandé — tier gratuit) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Clé API DeepSeek** (recommandé) — [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- **Clé API Mistral** (recommandé) — [console.mistral.ai](https://console.mistral.ai/api-keys)

---

## Démarrage rapide

### Windows (PowerShell)

```powershell
# 1. Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# 2. Lancer l'interface
streamlit run src\ui\app.py
```

> Si PowerShell bloque : `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Linux / Mac

```bash
source .venv/bin/activate
streamlit run src/ui/app.py
# ou
make run
```

L'interface s'ouvre sur `http://localhost:8501`.

---

## Installation

### Windows (PowerShell)

```powershell
git clone <url-du-repo>
cd hakili_ai_correction

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Copy-Item .env.example .env
# Ouvrir .env et renseigner les clés API
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

### Linux / Mac

```bash
git clone <url-du-repo>
cd hakili_ai_correction
make setup
cp .env.example .env
# Éditer .env avec les clés API
make run
```

---

## Configuration (`.env`)

```env
# ── Anthropic Claude (obligatoire — fallback + extraction + diagnostic) ───────
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL_HEAVY=claude-sonnet-4-6
CLAUDE_MODEL_OPUS=claude-opus-4-7

# ── Google Gemini — transcription vision (GRATUIT jusqu'à 1M tokens/jour) ────
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
VISION_PROVIDER=gemini          # "gemini" | "claude"

# ── DeepSeek — correction (V3) ───────────────────────────────────────────────
DEEPSEEK_API_KEY=sk-...
GRADING_PROVIDER=deepseek       # "deepseek" | "claude"
DIAGNOSTIC_PROVIDER=claude      # "claude" | "deepseek" | "mistral"

# ── Mistral — remédiation français académique ─────────────────────────────────
MISTRAL_API_KEY=...
REMEDIATION_PROVIDER=mistral    # "mistral" | "deepseek" | "claude"

# ── Seuils pipeline ───────────────────────────────────────────────────────────
CONFIDENCE_REVIEW_THRESHOLD=0.75

# ── Stockage local ────────────────────────────────────────────────────────────
RUNS_DIR=./runs
```

Tous les choix de providers se font **uniquement dans `.env`** — aucune modification de code requise.

---

## Utilisation

### Mode Test Hakili (recommandé)

**Phase A — Correction**
1. Aller sur l'onglet **Traitement unique**
2. Sélectionner **"Test Hakili : Test d'entrée en 3e"** (ou en 6e)
3. Un bandeau confirme : ✓ Énoncé pré-chargé · ✓ Barème 33 questions · ✓ RAG activé
4. Charger **uniquement la copie de l'élève** (PDF ou photos)
5. Ajouter des instructions expert si nécessaire (optionnel)
6. Cliquer **Lancer la transcription et la correction**
7. Accéder au **tableau de validation** — accepter ou refuser chaque note IA
8. Cliquer **Valider et générer le diagnostic**

**Phase B — Diagnostic et rapport**

9. L'IA produit le diagnostic approfondi ancré sur le programme officiel
10. Télécharger le **rapport PDF** (tableaux synthèse + diagnostic + remédiation)

### Mode Libre (devoirs personnalisés)

1. Sélectionner **"Mode libre"**
2. Charger la copie, l'énoncé (optionnel), et le barème (PDF ou texte)
3. Le reste est identique au mode Hakili

### Format barème (mode libre, saisie texte)

```
Q1 : Résoudre le système d'équations
Q2a : Calculer la limite de f en +∞
Q2b : Étudier la dérivabilité de f en 0
Q3 : Tracer la courbe représentative
```

### Recommandation scan

| Contexte | Recommandation | Réglages |
|---|---|---|
| Usage régulier | Scanner ADF (ex. Epson ES-65W ~$130) | 150 DPI · niveaux de gris · PDF |
| Usage occasionnel | Multifonction école | 150 DPI · niveaux de gris · PDF |
| Terrain / urgence | Smartphone + Microsoft Lens | Mode Document → PDF |

---

## Structure du projet

```
hakili_ai_correction/
│
├── src/
│   ├── api/
│   │   ├── claude_client.py          # Claude : extraction barème/énoncé · fallback tout pipeline
│   │   ├── gemini_client.py          # Gemini 2.0 Flash : transcription vision
│   │   ├── deepseek_client.py        # DeepSeek V3 : correction · R1 : diagnostic
│   │   └── mistral_client.py         # Mistral Small : remédiation + diagnostic (alt)
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings (.env) — tous providers
│   │   └── anonymizer.py             # Génération slug copy_id
│   ├── knowledge/
│   │   ├── curriculum_retriever.py   # RAG : chargement YAML + retrieval par chunk_id
│   │   └── test_registry.py          # Tests Hakili pré-chargés (énoncé + barème auto)
│   ├── models/
│   │   └── domain.py                 # Modèles Pydantic : Rubric, CopyGrade, DiagnosticResult, CompetencyGap…
│   ├── pipeline/
│   │   ├── ingestion.py              # PDF → images 150 DPI · multi-images
│   │   ├── image_quality.py          # Contrôle qualité (OpenCV + PIL)
│   │   ├── orchestrator.py           # Validation inter-étapes
│   │   ├── pipeline.py               # Pipeline 11 étapes · on_progress callback
│   │   └── pdf_report.py             # Génération rapports PDF (ReportLab)
│   └── ui/
│       ├── app.py                    # Interface Streamlit — mode Hakili + mode libre
│       └── progress.py               # Écran d'analyse animé (7 étapes + barre temps réel)
│
├── prompts/
│   ├── transcription_prompt.md       # Instructions transcription multimodale
│   ├── grading_prompt.md             # Instructions correction selon barème
│   ├── diagnostic_prompt.md          # Instructions diagnostic + slot {{CURRICULUM_CONTEXT}}
│   └── remediation_subject_prompt.md # Instructions génération exercices
│
├── data/
│   ├── Documents/
│   │   ├── Hakilisso test de niveau 3e.docx    # Énoncé test 3e (source)
│   │   ├── TEST DE NIVEAU,6eme,GROUPE 1.docx   # Énoncé test 6e (source)
│   │   └── Curricula maths post-primaire.docx  # Programme officiel source
│   └── knowledge/
│       ├── curriculum_6e.yaml    # 45 leçons programme officiel 6e
│       ├── curriculum_5e.yaml    # 33 leçons programme officiel 5e
│       ├── curriculum_4e.yaml    # 23 leçons programme officiel 4e
│       ├── curriculum_3e.yaml    # 20 leçons programme officiel 3e
│       ├── bareme_test_3e.yaml   # 33 questions test 3e → chunk_ids curriculum
│       └── bareme_test_6e.yaml   # 33 questions test 6e → lacune_type
│
├── docs/
│   ├── decision_register.md          # Registre des décisions structurantes
│   ├── ai_providers_analysis.md      # Analyse comparative LLM par tâche
│   └── input_pipeline_analysis.md    # Analyse OCR vs LLM + format d'entrée optimal
│
├── tests/
│   └── test_models.py
│
├── runs/                             # Sorties pipeline (local · non versionné)
├── .env.example
├── .env
├── requirements.txt
├── Makefile
└── CLAUDE.md
```

---

## Commandes développement

| Commande | Description |
|---|---|
| `make setup` | Créer le venv et installer les dépendances |
| `make run` | Lancer l'interface Streamlit |
| `make test` | Lancer les tests unitaires |
| `make lint` | Vérifier qualité du code (ruff + mypy) |

**Sans make (Windows) :**

```powershell
.\.venv\Scripts\pytest tests/ -v
.\.venv\Scripts\ruff check src/
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

---

## Décisions structurantes

| ID | Sujet | Décision |
|---|---|---|
| D-CEO-01 | Matières et niveaux | Mathématiques, **6e à la Terminale** |
| D-CEO-02 | Format barème | Binaire 0/1 par question et sous-question |
| D-CEO-03 | Stratégie IA | **Multi-provider** avec routing automatique + choix `.env` |
| D-CEO-04 | Instructions expert | Couche optionnelle d'instructions contextuelles |
| D-CEO-05 | Validation humaine | **Dans l'interface** via tableau de validation (Accepter/Refuser) |
| D-CEO-07 | Identification | Nom réel de l'élève (slug technique pour fichiers) |
| D-CEO-10 | Format entrée optimal | **PDF scanner 150 DPI** niveaux de gris |
| D-CEO-11 | Coût cible | ~$0.02/copie · ~$12/an pour 540 copies |
| D-CEO-12 | Diagnostic RAG | Ancré sur programme officiel MEN Burkina Faso (6e–3e) |
| D-CEO-13 | Tests Hakili pré-chargés | Énoncé + barème auto · enseignant charge uniquement la copie |
| D-CEO-14 | UI premium | Écran animé Hakili · 7 étapes en temps réel · instrument marketing |
| D-CEO-15 | Génération PDF | XeLaTeX + Jinja2 (fallback ReportLab) |
| **D-CEO-16** | **Mode correction** | **Correction assistée : IA propose, enseignant valide** |
| **D-CEO-17** | **Diagnostic central** | **Phase B après validation : diagnostic approfondi = valeur principale** |

Registre complet : [docs/decision_register.md](docs/decision_register.md)

---

## Limitations connues (prototype)

- Copie très dégradée (photo floue, faible éclairage) → confiance IA réduite
- Formules très complexes (intégrales multiples, matrices) → transcription approximative possible
- Écriture cursive très dense → zones `[ILLISIBLE]` possibles
- La base RAG couvre 6e–3e ; les tests évaluant le primaire (test 6e) n'ont pas de chunks KB
- Français uniquement
- Stockage local uniquement (prototype)

---

## Objectifs de validation

| Objectif | Cible |
|---|---|
| Taux d'accord IA / enseignant (avant validation) | ≥ 85% des questions |
| Temps Phase A (transcription + correction IA) | < 90 secondes |
| Temps Phase B (diagnostic après validation) | < 60 secondes |
| Qualité diagnostic | Chaque lacune référence une leçon officielle précise |
| Volume cible de validation | 100 copies réelles avec enseignant référent |

---

## Usage marketing et facturation

Le système est conçu comme **outil interne Hakili Lab** pour les enseignants :

- Le **rapport PDF** constitue un document professionnel livrable à l'enseignant
- Le **diagnostic RAG** ancré sur le programme officiel permet d'identifier précisément les lacunes
- Le **sujet de remédiation personnalisé** est un plan d'action concret et actionnable
- L'**interface animée** renforce l'image de marque Hakili pendant toute la durée de l'analyse

---

*Prototype confidentiel — Hakili Lab · Usage pédagogique exclusif · Burkina Faso*
