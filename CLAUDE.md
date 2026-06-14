# CLAUDE.md — Hakili Lab AI Assisted Correction

## Rôle de Claude Code
Tu es l'assistant d'ingénierie du projet Hakili Lab : outil de **correction assistée par IA** pour copies manuscrites de mathématiques, conçu pour les tests de recrutement Hakili Lab au Burkina Faso (niveaux 6e à 3e).

**Objectif central : le diagnostic pédagogique approfondi.** La correction IA n'est qu'une première passe — c'est l'enseignant qui valide, et c'est le diagnostic qui constitue la valeur ajoutée du produit.

---

## Vision du produit (état cible)

### Flux en deux phases

**Phase A — Correction assistée**
1. L'enseignant scanne la copie de l'élève (PDF ou photos)
2. Le système charge l'énoncé + le barème (auto si test Hakili standard)
3. L'IA transcrit la copie et propose une note par question
4. L'enseignant accède au **tableau de validation** : il accepte ou refuse chaque note IA
5. Le système calcule le **score final /20** en priorisant les décisions enseignant

**Phase B — Diagnostic approfondi** (déclenchée après validation)
6. Le système interroge les curricula officiels (RAG) pour chaque question échouée
7. L'IA produit un diagnostic précis : causes cachées, lacunes par niveau, leçons non maîtrisées
8. Le rapport final est généré

### Tableau de validation enseignant (interface clé)
| N° question | Bonne réponse | Réponse de l'élève | Note IA | Décision enseignant |
|---|---|---|---|---|
| Q1 | 15 | 15 | 1/1 | ✅ Accepter |
| Q2a | 2x+3 | 2x | 0/1 | ❌ Refuser → saisir note |
| Q3b | Voir corrigé | [ILLISIBLE] | 0/1 | ✅ Accepter |

L'enseignant coche "Accepter" ou "Refuser" pour chaque ligne. Si refus, il saisit la note corrigée.

### Rapport final
Deux tableaux brefs en tête :
- **Bonnes réponses** : N° question | Points attribués
- **Mauvaises réponses** : N° question | 0 / Points possibles

Puis le corps du rapport : **diagnostic pédagogique approfondi + plan de remédiation**.
Pas de long listing de commentaires par question — le rapport se concentre sur les lacunes.

---

## Ce qui est implémenté (infrastructure réutilisable)

### Reste intact
- Ingestion PDF/images (PyMuPDF, 150 DPI)
- Transcription multimodale (Gemini 2.5 Flash / Claude Sonnet)
- Correction IA binaire 0/1 (DeepSeek V3 / Claude) — devient une "proposition" soumise à l'enseignant
- RAG curriculum (121 leçons 6e→3e, `CurriculumRetriever`)
- Diagnostic (`DiagnosticResult`, `CompetencyGap`)
- Remédiation (Mistral Small / Claude)
- Export PDF XeLaTeX + JSON
- Architecture multi-provider avec fallback automatique
- TestRegistry (tests Hakili pré-chargés)

### À construire
- Modèle `TeacherDecision` et champs de validation dans `QuestionGrade`
- Pipeline en deux phases avec point d'arrêt après la correction
- Composant Streamlit : tableau de validation enseignant
- Calcul du score final priorisant les décisions enseignant
- Rapport reformaté (tableaux synthétiques + diagnostic central)

---

## Architecture multi-provider (inchangée)
| Tâche | Provider par défaut | Fallback |
|---|---|---|
| Transcription | Gemini 2.5 Flash | Claude Sonnet 4.6 |
| Correction (proposition) | DeepSeek V3 | Claude Sonnet 4.6 |
| Diagnostic | Claude Opus 4.7 | — |
| Remédiation | Mistral Small | Claude Sonnet 4.6 |
| Extraction barème/énoncé | Claude Sonnet 4.6 | — |

---

## Contraintes actives
- Python + Streamlit uniquement.
- Barème binaire 0/1 par question et sous-question.
- L'enseignant a toujours le dernier mot sur le score (priorité décision humaine).
- Diagnostic ancré sur le programme officiel MEN Burkina Faso — pas de généricité.
- Stockage local, identification par nom réel de l'élève.
- Coût cible : ~$0.02/copie (avec Gemini actif).

---

## Qualité du code
- Pydantic v2 pour tous les schémas.
- Séparation : `src/api/` | `src/pipeline/` | `src/models/` | `src/ui/` | `src/knowledge/`
- Configuration par `.env` via `pydantic-settings`.

---

## Style de travail
Avant de coder :
1. Lire `docs/decision_register.md` — décisions actives.
2. Lire `src/models/domain.py` — schémas de référence.
3. Proposer un plan si la tâche touche plusieurs modules.
4. Ne pas recréer ce qui existe — vérifier `src/knowledge/`, `src/pipeline/`, `src/api/`.

---

## Commandes
```powershell
# Windows
.\.venv\Scripts\Activate.ps1
streamlit run src\ui\app.py

# Unix / make
make setup && make run
make test
make lint
```

---

## Fichiers clés
| Fichier | Rôle |
|---|---|
| `src/pipeline/pipeline.py` | Pipeline principal (à scinder en Phase A + Phase B) |
| `src/pipeline/orchestrator.py` | Validateurs entre étapes |
| `src/models/domain.py` | Schémas Pydantic — ajouter `TeacherDecision` ici |
| `src/ui/app.py` | Interface — ajouter le tableau de validation ici |
| `src/knowledge/curriculum_retriever.py` | RAG curricula |
| `src/knowledge/test_registry.py` | Tests Hakili pré-chargés |
| `docs/decision_register.md` | Toutes les décisions actives |
| `docs/implementation_plan.md` | Plan de transformation en phases |
