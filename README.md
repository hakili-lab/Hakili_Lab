# Hakili Lab — Correction Assistée par IA

> Outil de **correction assistée par IA** pour copies manuscrites de **mathématiques**,
> conçu pour les **tests de recrutement Hakili Lab** au **Burkina Faso**.
> L'objectif central : le **diagnostic pédagogique approfondi**.

---

## Niveaux couverts — attention, deux périmètres différents

L'application gère des niveaux plus larges pour les tests que pour le diagnostic RAG. Pour éviter toute ambiguïté :

| Périmètre | Niveaux réellement couverts | Vérifié dans |
|---|---|---|
| **Tests Hakili pré-chargés** (Phase A — correction) | Du **primaire (CE1–CM2)** à la **Terminale**, via 6 tests pré-enregistrés (voir plus bas) | `src/knowledge/test_registry.py` (`_TEST_CATALOG`) |
| **Classes gérées par l'authentification/permissions** | **CP → Tle** (le primaire est présent côté Sheet enseignants même si aucun test ne l'évalue) | `src/core/classe_normalizer.py` (`CANONICAL_CLASSES`) |
| **Base de connaissance RAG (diagnostic Phase B)** | **6e, 5e, 4e, 3e uniquement** — 4 fichiers `curriculum_*.yaml`, aucun chunk pour le primaire, la 2nde, la 1ère ou la Terminale | `data/knowledge/curriculum_*.yaml` |

Concrètement : un test qui évalue des compétences de 2nde ou de Terminale (ex. `hakili_tle_v1`) peut être corrigé normalement (Phase A), mais son diagnostic RAG (Phase B) ne s'ancre que sur les prérequis 6e–3e éventuellement en jeu — jamais sur une leçon de 2nde/1ère/Tle elle-même, faute de chunk. Le test 6e (qui évalue en réalité des compétences CE1–CM2) n'a lui aucun chunk du tout (`chunk_ids: []` dans son barème) : c'est une limitation connue, listée plus bas.

---

## Vue d'ensemble

Hakili Lab assiste l'enseignant dans la correction de copies manuscrites numérisées. **L'IA propose, l'enseignant décide.** Le flux se déroule en deux phases :

**Phase A — Correction assistée**
1. L'enseignant se connecte (nom + PIN), sélectionne son élève, scanne la copie et choisit le test (ou charge l'énoncé + barème)
2. L'IA transcrit la copie et propose une note pour chaque question
3. L'enseignant valide dans un **tableau de validation** : il accepte ou refuse chaque note IA
4. Le système calcule le **score final /20** en priorisant les décisions enseignant

**Phase B — Diagnostic approfondi** *(l'objectif central du produit)*
5. Pour chaque question échouée, le système récupère les leçons du programme officiel (RAG, 6e–3e)
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
6 tests pré-enregistrés (`src/knowledge/test_registry.py`), énoncé + barème pré-chargés — l'enseignant ne charge que la copie de l'élève :

| Test | Niveaux évalués | Diagnostic RAG |
|---|---|---|
| Test d'entrée en 3e v1 | 6e · 5e · 4e | ✅ (6e–4e) |
| Test d'entrée en 3e v2 | 6e · 5e · 4e | ✅ (6e–4e) |
| Test d'entrée en 6e | CE1 · CE2 · CM1 · CM2 | ❌ (aucun chunk primaire) |
| Évaluation 2nde C | 6e · 5e · 4e · 3e · 2nde | ⚠️ partiel (prérequis 6e–3e seulement) |
| Évaluation 4e | 6e · 5e · 4e | ✅ (6e–4e) |
| Devoir Terminale | 4e · 3e · Tle | ⚠️ partiel (prérequis 4e–3e seulement) |

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
- **Export PDF + JSON** — rapport enseignant (HTML→PDF via xhtml2pdf) + données brutes

---

## Authentification et rôles

Il n'y a plus d'email ni de mot de passe : la connexion se fait par **sélection du nom** dans une liste déroulante recherchable (insensible casse/accents) puis saisie d'un **code PIN à 4 chiffres**. Le Sheet personnel (Google Sheets) est la **seule source de vérité** pour l'identité, le rôle, les affectations et le PIN — tout est relu à chaque connexion, jamais stocké en base (`src/services/auth_service.py`).

Trois rôles, lus directement depuis la colonne `role` du Sheet personnel (`src/services/user_service.py`, `src/db/models.py::UserRole`) :

| Rôle | Ce qu'il voit |
|---|---|
| **Enseignant** | Les élèves de sa/ses classe(s) précises (centre **et** niveau doivent correspondre à une affectation) |
| **Responsable** | Tous les élèves de son/ses centre(s) entier(s), toutes classes confondues (aucun filtre classe) |
| **Administrateur** | Tous les élèves, sans restriction — seul rôle à voir `contact_parents` et `identifiant_hakili` |

Une personne peut porter **plusieurs rôles à la fois** (« double casquette », ex. enseignant *et* responsable d'un centre) : elle choisit alors sa **casquette active** à la connexion et peut en changer, sans se reconnecter, via un sélecteur dans l'interface.

---

## Architecture des données

Deux sources de données, avec une séparation stricte des responsabilités :

- **Google Sheets** (`src/integrations/google_sheets.py`) — source de vérité pour tout ce qui concerne l'**identité** : élèves (nom, classe, centre, contact parent) et personnel (nom, rôle, affectations, PIN). Deux Sheets : un Sheet élèves (`GOOGLE_SHEET_ELEVES_ID`) et un Sheet personnel fusionné (`GOOGLE_SHEET_PERSONNEL_ID`) où le rôle de chaque ligne est lu dans sa colonne `role`. Les centres ne sont **plus une liste figée dans le code** : ils sont dérivés dynamiquement des valeurs vues dans les deux Sheets (`src/core/centre_normalizer.py`).
- **PostgreSQL (Neon)** (`src/db/models.py`, SQLAlchemy 2.0) — ne stocke **que** ce qui concerne la correction elle-même : deux tables, `Copie` (identifiant_hakili, classe, année scolaire, date de soumission, note finale) et `Document` (scan, rapport PDF, remédiation — stockés en BYTEA), reliées par `copy_id`. Aucune identité d'élève ou de professeur n'y est dupliquée — `identifiant_hakili` (texte calculé depuis les Sheets) relie une copie à un élève sans stocker son nom. Les écritures en base sont **best-effort** : une erreur réseau/DB ne bloque jamais le pipeline (voir `src/pipeline/pipeline.py`, `_db_persist_scan`), sauf l'unique vérification qu'un élève existe bien dans les Sheets avant tout appel IA payant.

**Confidentialité** — `contact_parents` et `identifiant_hakili` ne sont jamais affichés à l'écran hors du rôle Administrateur : ce sont des données personnelles, lues uniquement pour un usage interne (construction de l'identifiant technique et des noms de fichiers).

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
║  2. Transcription  (Gemini 2.5 Flash / Claude / Mistral) ║  texte + formules + [ILLISIBLE]
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
║  6. RAG — récupération contexte programme (6e–3e)        ║  leçons des questions échouées
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

**Routing automatique :** si une clé API est absente ou si le provider principal échoue, le pipeline bascule sur un **fallback GPT-5 (OpenAI)** pour la transcription, la correction, le diagnostic et la remédiation. Claude reste seul utilisé, sans fallback, là où il n'y a pas d'alternative : extraction du sujet/barème, barème virtuel, enrichissement 20/20 (`src/core/config.py`, `src/pipeline/pipeline.py`).

Ce mécanisme repose sur une **convention respectée par chaque client**, pas sur une garantie structurelle du pipeline : chaque méthode doit catcher ses propres erreurs et retourner `success=False` plutôt que laisser une exception remonter, sans quoi le fallback est court-circuité. Point de vigilance pour tout nouveau client IA ajouté au projet.

| Tâche | Provider principal | Fallback | Contrôle |
|---|---|---|---|
| Transcription | Gemini 2.5 Flash | **GPT-5 (OpenAI)** | `VISION_PROVIDER` |
| Correction (proposition) | DeepSeek V3 | **GPT-5 (OpenAI)** | `GRADING_PROVIDER` |
| Diagnostic | Claude Opus 4.7 | **GPT-5 (OpenAI)** | `DIAGNOSTIC_PROVIDER` |
| Remédiation | Mistral Small | **GPT-5 (OpenAI)** | `REMEDIATION_PROVIDER` |
| Extraction barème/énoncé | Claude Sonnet 4.6 | — (aucun) | toujours Claude |

### Résilience et cas limites de la transcription

- **Renumérotation déterministe des pages** — au-delà de 3 pages, la transcription est découpée en lots parallèles (`_MAX_PAGES_PER_BATCH`, `gemini_client.py` / `claude_client.py`) ; après fusion, chaque page est renumérotée selon son rang réel dans la liste fusionnée plutôt que selon le `page_number` renvoyé par le modèle (une consigne de prompt, jamais garantie), ce qui évite toute collision d'identifiant côté interface.
- **Repli `confidence=0.3`** — si le modèle omet le champ `confidence` d'une page malgré le schéma d'outil qui le déclare `required` (`claude_client.py::_normalize_transcription`), la page reçoit une confiance délibérément basse : sous le seuil de relecture enseignant (`min_confidence=0.40`, `orchestrator.py::validate_transcription`), donc signalée à l'enseignant plutôt que silencieusement acceptée.
- **Timeout adaptatif du fallback OpenAI** — `openai_client.py::_transcribe_timeout` (base 90 s + 12 s/page, plafond 300 s) : ce client transcrit toutes les pages en un seul appel, sans découpage en lots contrairement à Gemini/Claude, et reste donc structurellement plus exposé aux copies longues.

---

## Système RAG — base de connaissance curriculum

### Structure des fichiers
```
data/knowledge/
├── curriculum_6e.yaml        # 45 leçons : numériques + géométriques (6e)
├── curriculum_5e.yaml        # 33 leçons : multiples, fractions, triangles…
├── curriculum_4e.yaml        # 23 leçons : puissances, polynômes, Thalès, vecteurs…
├── curriculum_3e.yaml        # 20 leçons : Pythagore, trigonométrie, systèmes…
├── bareme_test_3e.yaml       # Barème enrichi test 3e v1 → chunk_ids
├── bareme_test_3e_v2.yaml    # Barème test 3e v2
├── bareme_test_4e.yaml       # Barème test 4e
├── bareme_test_6e.yaml       # Barème test 6e (chunk_ids vides — primaire, hors RAG)
├── bareme_test_2ndeC.yaml    # Barème test 2nde C → chunk_ids 6e–3e (prérequis)
├── bareme_test_tle.yaml      # Barème test Terminale → chunk_ids 4e–3e (prérequis)
└── corrige_test_*.yaml       # Corrigés officiels correspondants
```

Il n'existe **aucun** `curriculum_2ndeC.yaml` ni `curriculum_tle.yaml` — voir la section « Niveaux couverts » plus haut.

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
1. L'enseignant sélectionne un test Hakili → `bareme_id` correspondant (ex. `"hakili_3e_v1"`)
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
| Fallback (tous providers) | **OpenAI** | gpt-5 | Filet de secours si le provider principal échoue | — |
| **Total** | | | | **~$0.02** |

> Analyse complète : [docs/ai_providers_analysis.md](docs/ai_providers_analysis.md)

---

## Stack technique

| Couche | Technologie |
|---|---|
| Interface | Streamlit 1.36+ |
| Base de connaissance | YAML + pyyaml |
| IA — Vision | Google Gemini 2.5 Flash |
| IA — Raisonnement math | DeepSeek V3 + R1 (API compatible OpenAI) |
| IA — Génération French | Mistral Small 3.1 |
| IA — Extraction structurée | Anthropic Claude Sonnet 4.6 |
| IA — Fallback | OpenAI GPT-5 |
| Modèles de données | Pydantic v2 + pydantic-settings |
| Base de données | PostgreSQL (Neon) + SQLAlchemy 2.0 (`Mapped[]`/`mapped_column()`) |
| Migrations base de données | Alembic |
| Source de vérité élèves/personnel | Google Sheets — gspread + google-auth |
| PDF → images | PyMuPDF (fitz) · 150 DPI |
| Qualité image | OpenCV + Pillow |
| Génération PDF | xhtml2pdf (HTML+CSS → PDF, pur Python) + Jinja2 |
| Retry API | Tenacity |
| Tests | Pytest |
| Linting / typage | Ruff (config explicite `ruff.toml`) + MyPy |
| Intégration continue | GitHub Actions |

---

## Prérequis

- **Python 3.11 ou supérieur**
- **Clé API Anthropic** (obligatoire — fallback + extraction) — [console.anthropic.com](https://console.anthropic.com)
- **Clé API Google AI Studio** (recommandé — tier gratuit) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Clé API DeepSeek** (recommandé) — [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- **Clé API Mistral** (recommandé) — [console.mistral.ai](https://console.mistral.ai/api-keys)
- **Compte de service Google** (nécessaire en pratique — identité élèves/personnel) — voir section Configuration
- **Base PostgreSQL** (nécessaire en pratique — persistance copies/documents/notes), ex. [neon.tech](https://neon.tech)

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
cd Hakili_Lab

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Copy-Item .env.example .env
# Ouvrir .env et renseigner les clés API + Google Sheets + base de données
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

### Linux / Mac

```bash
git clone <url-du-repo>
cd Hakili_Lab
make setup
cp .env.example .env
# Éditer .env avec les clés API + Google Sheets + base de données
make run
```

---

## Configuration (`.env`)

Liste complète, vérifiée dans `src/core/config.py` (classe `Settings`) :

```env
# ── Obligatoire ────────────────────────────────────────────────────────────────
# Sans valeur par défaut dans Settings — le démarrage échoue si absent.
ANTHROPIC_API_KEY=sk-ant-...

# ── Nécessaire en pratique ───────────────────────────────────────────────────────
# Techniquement optionnels pour Pydantic (défaut ""), mais sans eux :
# pas d'authentification, pas d'élèves accessibles, pas de persistance des copies.

# Google Sheets — source de vérité élèves/personnel (compte de service)
# En local : GOOGLE_SERVICE_ACCOUNT_FILE (chemin vers un fichier JSON existant).
# Sur Streamlit Cloud (pas de fichier local) : GOOGLE_SERVICE_ACCOUNT_JSON à la
# place, avec le contenu JSON complet de la clé en une seule ligne.
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
GOOGLE_SERVICE_ACCOUNT_JSON=
GOOGLE_SHEET_ELEVES_ID=
GOOGLE_SHEET_PERSONNEL_ID=

# PostgreSQL (Neon) — persistance copies/documents/notes. Best-effort : son
# absence ne bloque pas le pipeline, mais rien n'est alors sauvegardé.
DATABASE_URL=postgresql://user:password@host/dbname

# ── Modèles Claude ────────────────────────────────────────────────────────────
CLAUDE_MODEL_HEAVY=claude-sonnet-4-6
CLAUDE_MODEL_LIGHT=claude-sonnet-4-6
CLAUDE_MODEL_OPUS=claude-opus-4-7

# ── Google Gemini — transcription vision (gratuit jusqu'à 1M tokens/jour) ────
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
VISION_PROVIDER=gemini          # "gemini" | "claude" | "mistral"

# ── DeepSeek — correction (V3) ───────────────────────────────────────────────
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL_V3=deepseek-chat
DEEPSEEK_MODEL_R1=deepseek-reasoner
GRADING_PROVIDER=deepseek       # "deepseek" | "claude"
DIAGNOSTIC_PROVIDER=claude      # "claude" | "deepseek" | "mistral"

# ── Mistral — remédiation français académique ─────────────────────────────────
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-small-latest
MISTRAL_VISION_MODEL=pixtral-12b-2409
REMEDIATION_PROVIDER=mistral    # "mistral" | "deepseek" | "claude"

# ── OpenAI — filet de secours GPT-5 (transcription, correction, diagnostic,
#    remédiation, nom élève) ─────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5

# ── Seuils pipeline ───────────────────────────────────────────────────────────
CONFIDENCE_REVIEW_THRESHOLD=0.75

# ── Stockage / divers ─────────────────────────────────────────────────────────
RUNS_DIR=./runs
SUBJECT=mathematics
DEBUG=false
```

Tous les choix de providers se font **uniquement dans `.env`** — aucune modification de code requise.

---

## Utilisation

### Mode Test Hakili (recommandé)

**Phase A — Correction**
1. Se connecter (nom + PIN), aller sur l'onglet **Traitement unique**
2. Sélectionner un **test Hakili** (3e v1/v2, 6e, 4e, 2nde C ou Terminale — voir tableau plus haut)
3. Un bandeau confirme : ✓ Énoncé pré-chargé · ✓ Barème · ✓ RAG activé (si applicable au test choisi)
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
Hakili_Lab/
│
├── src/
│   ├── api/
│   │   ├── claude_client.py          # Claude : extraction barème/énoncé · diagnostic · fallback partiel
│   │   ├── gemini_client.py          # Gemini 2.5 Flash : transcription vision
│   │   ├── deepseek_client.py        # DeepSeek V3 : correction · R1 : diagnostic (alt)
│   │   ├── mistral_client.py         # Mistral Small/Pixtral : remédiation + diagnostic (alt) + transcription (alt)
│   │   └── openai_client.py          # GPT-5 : fallback transcription/correction/diagnostic/remédiation
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings (.env) — tous providers et accès données
│   │   ├── anonymizer.py             # Génération slug copy_id
│   │   ├── classe_normalizer.py      # Normalisation classe (CP→Tle) + comparaison de niveau
│   │   ├── centre_normalizer.py      # Normalisation + dérivation dynamique des centres
│   │   └── tendance.py               # Calcul de tendance de progression d'un élève
│   ├── db/
│   │   ├── models.py                 # SQLAlchemy 2.0 : Copie, Document, UserRole (Mapped[]/mapped_column())
│   │   └── database.py               # Engine + session (Neon Postgres)
│   ├── integrations/
│   │   └── google_sheets.py          # Lecture Google Sheets — source de vérité élèves/personnel
│   ├── knowledge/
│   │   ├── curriculum_retriever.py   # RAG : chargement YAML + retrieval par chunk_id
│   │   ├── test_registry.py          # Tests Hakili pré-chargés (énoncé + barème auto)
│   │   └── answer_loader.py          # Chargement des corrigés officiels
│   ├── models/
│   │   └── domain.py                 # Modèles Pydantic : Rubric, CopyGrade, DiagnosticResult, CompetencyGap…
│   ├── pipeline/
│   │   ├── ingestion.py              # PDF → images 150 DPI · multi-images
│   │   ├── orchestrator.py           # Validation inter-étapes
│   │   ├── pipeline.py               # Pipeline Phase A + Phase B · on_progress callback
│   │   ├── pdf_report_html.py        # Génération rapport PDF (xhtml2pdf + Jinja2)
│   │   ├── pdf_remediation_html.py   # Génération PDF sujet de remédiation
│   │   ├── text_structuring.py       # Découpage structurel des textes LLM (intro + items numérotés)
│   │   └── math_format.py            # Formatage mathématique partagé PDF/UI
│   ├── services/
│   │   ├── auth_service.py           # Authentification nom + PIN (Sheet personnel)
│   │   ├── user_service.py           # Contrôle d'accès aux élèves selon rôle/casquette
│   │   └── copie_service.py          # CRUD Copie/Document (PostgreSQL)
│   └── ui/
│       ├── app.py                    # Interface Streamlit — connexion, mode Hakili, mode libre, gestion
│       └── progress.py               # Écran d'analyse animé (étapes en temps réel)
│
├── prompts/
│   ├── transcription_prompt.md       # Instructions transcription multimodale
│   ├── grading_prompt.md             # Instructions correction selon barème
│   ├── diagnostic_prompt.md          # Instructions diagnostic + slot {{CURRICULUM_CONTEXT}}
│   └── remediation_subject_prompt.md # Instructions génération exercices
│
├── data/
│   ├── Documents/                    # Énoncés sources (DOCX) des tests Hakili
│   └── knowledge/                    # Curricula + barèmes + corrigés (voir section RAG)
│
├── templates/                        # Templates Jinja2 pour la génération PDF (.html.j2)
│
├── migrations/                       # Migrations Alembic (schéma PostgreSQL)
│   └── versions/
│
├── credentials/                      # Clé JSON du compte de service Google (local, JAMAIS versionné)
│
├── .github/workflows/
│   └── ci.yml                        # GitHub Actions : ruff + mypy + pytest à chaque push/PR
│
├── docs/
│   ├── decision_register.md          # Registre des décisions structurantes
│   ├── ai_providers_analysis.md      # Analyse comparative LLM par tâche
│   └── input_pipeline_analysis.md    # Analyse OCR vs LLM + format d'entrée optimal
│
├── tests/                            # 7 fichiers, 125 tests (voir section Tests)
│
├── runs/                             # Sorties pipeline (local · non versionné)
├── ruff.toml                         # Config ruff explicite (figée dans le temps)
├── mypy.ini                          # Config mypy (plugins pydantic/sqlalchemy)
├── alembic.ini                       # Config Alembic
├── .env.example
├── .env
├── requirements.txt
├── Makefile
└── CLAUDE.md
```

---

## Tests

**125 tests** répartis sur **7 fichiers** dans `tests/` :

| Fichier | Périmètre |
|---|---|
| `test_models.py` | Modèles Pydantic (`QuestionGrade`, `CopyGrade`, `Rubric`, `TranscriptionResult`, `DiagnosticResult`…) |
| `test_google_sheets.py` | Lecture/normalisation Google Sheets |
| `test_knowledge_2ndeC.py` | Barème et corrigé du test 2nde C |
| `test_math_rendering.py` | Rendu mathématique (formules, exposants) |
| `test_tendance.py` | Calcul de tendance de progression élève |
| `test_text_structuring.py` | Découpage structurel des textes LLM |
| `test_ui_math.py` | Helpers de notation mathématique de l'interface |

```bash
pytest tests/ -v
```

---

## Qualité de code et intégration continue

- **Ruff** — linting, config explicite dans `ruff.toml` (règles `E4`/`E7`/`E9`/`F`/`I`/`RUF100` sélectionnées explicitement pour que le comportement ne varie plus silencieusement d'une version de ruff à l'autre) : **0 erreur**
- **MyPy** — typage statique (`mypy src/ --ignore-missing-imports`) : **0 erreur**
- **Pytest** — **125 tests**, tous verts
- **GitHub Actions** (`.github/workflows/ci.yml`) — ruff, mypy et pytest s'exécutent à chaque push et pull request sur `main`/`develop`, sur Python 3.11 et 3.12 ; les trois étapes sont bloquantes

```bash
ruff check src/ tests/
mypy src/ --ignore-missing-imports
pytest tests/ -v
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
.\.venv\Scripts\ruff check src/ tests/
.\.venv\Scripts\mypy src/ --ignore-missing-imports
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

---

## Décisions structurantes

| ID | Sujet | Décision |
|---|---|---|
| D-CEO-01 | Matières et niveaux | Mathématiques, **6e à la Terminale** (tests) — RAG diagnostic limité à 6e–3e |
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
| D-CEO-15 | Génération PDF | xhtml2pdf (HTML+CSS → PDF, pur Python) + Jinja2 |
| **D-CEO-16** | **Mode correction** | **Correction assistée : IA propose, enseignant valide** |
| **D-CEO-17** | **Diagnostic central** | **Phase B après validation : diagnostic approfondi = valeur principale** |
| **D-CEO-18** | **Source de vérité identité** | **Google Sheets (élèves + personnel) — PostgreSQL ne stocke plus que copies/documents/notes** |
| **D-CEO-19** | **Authentification** | **Nom (liste déroulante) + PIN 4 chiffres en clair dans le Sheet, sans hachage — risque assumé (Sheet réservé, pas de données bancaires)** |
| **D-CEO-20** | **Centres** | **Dérivés dynamiquement des Google Sheets (élèves + personnel) — plus de liste figée dans le code** |
| **D-CEO-21** | **Double casquette** | **Une personne enseignant + responsable choisit sa casquette active à la connexion : casquette Responsable = tout le centre, casquette Enseignant = filtrée par classe** |
| **D-CEO-22** | **Confidentialité élèves** | **`contact_parents` et `identifiant_hakili` ne sont jamais affichés hors du rôle Administrateur** |

Registre complet : [docs/decision_register.md](docs/decision_register.md)

---

## Limitations connues (prototype)

- Copie très dégradée (photo floue, faible éclairage) → confiance IA réduite (une confiance anormalement basse sur une seule page peut aussi provenir du repli automatique `confidence=0.3` en cas d'omission du champ par le modèle — voir « Résilience et cas limites de la transcription »)
- Formules très complexes (intégrales multiples, matrices) → transcription approximative possible
- Écriture cursive très dense → zones `[ILLISIBLE]` possibles
- La base RAG couvre 6e–3e uniquement ; le test 6e (qui évalue en réalité le primaire CE1–CM2) n'a aucun chunk KB, et les tests 2nde C / Terminale n'ont de diagnostic RAG que sur leurs prérequis 6e–3e, jamais sur leur propre niveau
- Français uniquement
- Persistance PostgreSQL best-effort : une base non configurée ou temporairement indisponible n'interrompt pas la correction, mais rien n'est alors sauvegardé pour cette copie

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
