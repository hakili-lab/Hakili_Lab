# Plan d'implémentation — Correction assistée par IA
**Hakili Lab · Version cible · Rédigé le 2026-06-11**

---

## Objectif de la transformation

Passer d'un pipeline automatique (IA corrige → rapport) à un flux assisté en deux phases :
- **Phase A** : IA propose les notes → tableau de validation → score final validé par l'enseignant
- **Phase B** : Diagnostic approfondi ancré sur le programme officiel → rapport centré sur les lacunes

---

## Vue d'ensemble des phases

| Phase | Durée estimée | Dépendances |
|---|---|---|
| **Phase 1** — Modèles de données | 0.5 journée | — |
| **Phase 2** — Pipeline scindé A + B | 1 journée | Phase 1 |
| **Phase 3** — Tableau de validation enseignant | 2 journées | Phase 2 |
| **Phase 4** — Score final + calcul /20 | 0.5 journée | Phase 3 |
| **Phase 5** — Diagnostic renforcé (Phase B) | 1 journée | Phase 1 |
| **Phase 6** — Rapport reformaté | 1 journée | Phase 4 + Phase 5 |
| **Phase 7** — Tests et intégration | 0.5 journée | Toutes |

**Total estimé : 6–7 journées de développement**

---

## Phase 1 — Modèles de données (`src/models/domain.py`)

### Ce qui change
Ajouter les champs nécessaires à la validation enseignant dans les modèles existants.

### Tâches

**1.1 — Ajouter `TeacherDecision` (enum)**
```python
from enum import Enum

class TeacherDecision(str, Enum):
    pending = "pending"    # pas encore décidé
    accepted = "accepted"  # enseignant accepte la note IA
    refused = "refused"    # enseignant refuse et saisit sa propre note
```

**1.2 — Enrichir `QuestionGrade`**
```python
class QuestionGrade(BaseModel):
    rubric_item_id: str
    score: float                           # proposition IA (0 ou max_score)
    confidence: float
    comment: str
    observed_answer: str
    correct_answer: str = ""               # NOUVEAU : bonne réponse (corrigé officiel ou calculée)
    requires_review: bool
    teacher_decision: TeacherDecision = TeacherDecision.pending  # NOUVEAU
    teacher_score: float | None = None     # NOUVEAU : note saisie par l'enseignant si refus
```

**1.3 — Enrichir `CopyGrade`**
```python
class CopyGrade(BaseModel):
    copy_id: str
    total_score: float          # proposition IA (inchangé)
    total_possible: float
    questions: list[QuestionGrade]
    expert_instructions_used: bool = False
    final_score: float | None = None       # NOUVEAU : calculé après validation enseignant
    validation_complete: bool = False      # NOUVEAU : True quand toutes questions décidées
```

**1.4 — Ajouter méthode de calcul du score final**
```python
# Dans CopyGrade ou dans pipeline.py

def compute_final_score(grade: CopyGrade) -> float:
    """Calcule le score /total_possible en priorisant les décisions enseignant."""
    total = 0.0
    for q in grade.questions:
        if q.teacher_decision == TeacherDecision.refused and q.teacher_score is not None:
            total += q.teacher_score
        else:
            total += q.score  # note IA (si accepted ou pending)
    return total
```

**Fichier modifié :** `src/models/domain.py`

---

## Phase 2 — Pipeline scindé en Phase A et Phase B (`src/pipeline/pipeline.py`)

### Ce qui change
Le pipeline actuel est un seul bloc linéaire. Il faut le scinder en deux fonctions distinctes, avec un point d'arrêt entre les deux pour la validation enseignant.

### Tâches

**2.1 — Renommer et scinder `_run()` en deux fonctions**

```python
def run_phase_a(
    *,
    copy_id: str,
    student_name: str,
    file_paths: list[Path],
    rubric: Rubric,
    subject_text: str = "",
    expert_instructions: str = "",
    official_answers: str = "",
    bareme_id: str = "",
    runs_dir: Path | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> PipelineResult:
    """
    Phase A : ingestion → transcription → correction IA.
    Retourne un PipelineResult avec grade.validation_complete = False.
    Le pipeline s'arrête ici — l'enseignant doit valider.
    """
    # étapes 1 à 5 de l'ancien _run()
    ...


def run_phase_b(
    *,
    result: PipelineResult,
    bareme_id: str = "",
    runs_dir: Path | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> PipelineResult:
    """
    Phase B : RAG + diagnostic + remédiation + export PDF.
    Reçoit le PipelineResult de la Phase A avec grade.validation_complete = True.
    """
    # étapes 6 à 11 de l'ancien _run()
    ...
```

**2.2 — Conserver `run_single_copy()` comme wrapper de compatibilité (batch)**
Pour le mode batch, on peut enchaîner Phase A → validation automatique (tout accepté) → Phase B.

**Fichier modifié :** `src/pipeline/pipeline.py`

---

## Phase 3 — Tableau de validation enseignant (`src/ui/app.py`)

### Ce qui change
Ajouter un nouveau composant Streamlit : le tableau de validation qui s'affiche après la Phase A.

### Maquette du tableau

```
┌─────┬─────────────────────┬────────────────────┬──────────┬──────────────────────────┐
│ N°  │ Bonne réponse       │ Réponse de l'élève │ Note IA  │ Décision enseignant       │
├─────┼─────────────────────┼────────────────────┼──────────┼──────────────────────────┤
│ Q1  │ 15                  │ 15                 │ 1 / 1    │ ✅ Accepter               │
│ Q2a │ 2x + 3              │ 2x                 │ 0 / 1    │ ✅ Accepter               │
│ Q2b │ x = -3/2            │ [ILLISIBLE]        │ 0 / 1    │ ❌ Refuser → [0.5] pts    │
│ Q3  │ Voir corrigé        │ Réponse correcte   │ 1 / 1    │ ❌ Refuser → [0  ] pts    │
├─────┴─────────────────────┴────────────────────┴──────────┴──────────────────────────┤
│  Score IA : 12.5 / 20        Score final (après validation) : 13 / 20                │
│                                          [ Valider et générer le diagnostic → ]       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Tâches

**3.1 — Fonction `render_validation_table(grade: CopyGrade) -> CopyGrade`**

```python
def render_validation_table(grade: CopyGrade) -> CopyGrade:
    """
    Affiche le tableau de validation et retourne le CopyGrade mis à jour
    avec les teacher_decision de l'enseignant.
    """
```

Logique par ligne :
- Colonne "N° question" : `q.rubric_item_id`
- Colonne "Bonne réponse" : `q.correct_answer` (depuis le corrigé officiel ou la proposition IA)
- Colonne "Réponse de l'élève" : `q.observed_answer`
- Colonne "Note IA" : `f"{q.score} / {rubric_item.max_score}"`
- Colonne "Décision" :
  - Radio : "Accepter" / "Refuser"
  - Si "Refuser" : `st.number_input` pour saisir la note corrigée (entre 0 et max_score)

**3.2 — Gestion du state Streamlit**

Utiliser `st.session_state` pour persister :
- `st.session_state["phase_a_result"]` — le PipelineResult de la Phase A
- `st.session_state["validation_done"]` — booléen

**3.3 — Bouton "Valider et générer le diagnostic"**

Ce bouton :
1. Calcule le score final via `compute_final_score(grade)`
2. Marque `grade.validation_complete = True`
3. Déclenche `run_phase_b(result=...)` dans un thread Streamlit
4. Affiche l'écran de progression de la Phase B

**3.4 — Indicateurs visuels**
- Ligne acceptée : fond légèrement vert
- Ligne refusée : fond légèrement orange + champ de saisie
- Ligne `[ILLISIBLE]` : icône d'alerte visible
- Compteur en temps réel : "X / 33 questions validées"

**Fichier modifié :** `src/ui/app.py`

---

## Phase 4 — Score final et calcul /20 (`src/pipeline/pipeline.py` + `src/models/domain.py`)

### Tâches

**4.1 — `compute_final_score()` appelée dans `run_phase_b`**

Au début de `run_phase_b`, avant le RAG :
```python
grade.final_score = compute_final_score(grade)
grade.validation_complete = True
```

**4.2 — Conversion en note /20**

Le score brut est sur `total_possible` (barème). La conversion en note /20 :
```python
note_sur_20 = round(grade.final_score / grade.total_possible * 20, 2)
```

Cette valeur est affichée dans l'interface et le rapport.

---

## Phase 5 — Diagnostic renforcé (`prompts/diagnostic_prompt.md` + `src/api/claude_client.py`)

### Ce qui change
Le diagnostic reçoit maintenant les **décisions finales de l'enseignant** (pas seulement les scores IA). Il s'appuie exclusivement sur les questions avec `final_score = 0` (confirmées échouées par l'enseignant).

### Tâches

**5.1 — Filtrer les questions pour le diagnostic**

Ne lancer le RAG et le diagnostic que sur les questions où la décision finale est un échec :
```python
failed_ids = [
    q.rubric_item_id
    for q in result.grade.questions
    if _final_score_for_question(q) == 0
]
```

**5.2 — Enrichir le prompt diagnostic**

Le prompt doit recevoir, pour chaque question échouée :
- `rubric_item_id` + `label` (ce que la question demande)
- `correct_answer` (bonne réponse)
- `observed_answer` (ce que l'élève a réellement écrit)
- `comment` IA (son diagnostic initial)
- Le chunk curriculum associé (depuis le RAG)

Le prompt doit produire pour chaque question échouée :
- **Cause cachée** : pourquoi l'élève a commis cette erreur spécifique ?
- **Niveau de la lacune** : quelle classe cette compétence devait-elle être acquise ?
- **Référence programme** : chunk_id + chapitre + leçon
- **Exemple de l'erreur type** (depuis `erreurs_frequentes` du curriculum)

**5.3 — Mettre à jour `prompts/diagnostic_prompt.md`**

Ajouter une section explicite :
```
## Pour chaque question échouée (score final = 0)
1. Identifie la cause cachée (pas le symptôme : "a mis 2x au lieu de 2x+3" → cause : "ne maîtrise pas la distributivité")
2. Identifie à quelle classe cette compétence devait être acquise
3. Cite le chunk du programme officiel fourni dans CURRICULUM_CONTEXT
4. Cite une erreur fréquente du programme si disponible
```

**Fichiers modifiés :** `prompts/diagnostic_prompt.md`, `src/api/claude_client.py`

---

## Phase 6 — Rapport reformaté (`src/pipeline/pdf_report_latex.py` + templates)

### Ce qui change
Le rapport actuel liste tous les commentaires par question. Le nouveau rapport a une structure différente :

```
┌─────────────────────────────────────────┐
│  RAPPORT DE CORRECTION — [NOM] — [DATE] │
│  Note finale : 13 / 20                  │
├─────────────────────────────────────────┤
│  TABLEAU 1 — BONNES RÉPONSES            │
│  Q1 · Q3 · Q4a · Q5 · ...  → X points  │
├─────────────────────────────────────────┤
│  TABLEAU 2 — MAUVAISES RÉPONSES         │
│  Q2a · Q2b · Q4b · ...     → 0 / X pts │
├─────────────────────────────────────────┤
│  DIAGNOSTIC PÉDAGOGIQUE APPROFONDI      │
│                                         │
│  Domaine NUMÉRIQUE                      │
│  [4e_NUM_Ch4_L3] Identités remarquables │
│  Cause : écrit (a+b)² = a²+b²           │
│  Leçon concernée : 4e — Chap. 4         │
│                                         │
│  Domaine GÉOMÉTRIQUE                    │
│  [3e_GEO_Ch2_L1] Théorème de Pythagore  │
│  Cause : applique mal l'hypoténuse       │
│  Leçon concernée : 3e — Chap. 2         │
├─────────────────────────────────────────┤
│  PLAN DE REMÉDIATION                    │
│  5 exercices ciblés par lacune          │
└─────────────────────────────────────────┘
```

### Tâches

**6.1 — Mettre à jour le template LaTeX `rapport_correction.tex`**
- Supprimer la section "commentaires par question"
- Ajouter les deux tableaux synthèse en tête
- Reorganiser le corps : diagnostic par domaine → plan de remédiation

**6.2 — Mettre à jour `generate_copy_report()` dans `pdf_report_latex.py`**
- Passer `final_score` (validé enseignant) et la note /20
- Séparer les questions en deux listes (bonnes / mauvaises réponses)
- Structurer les `CompetencyGap` par domaine

**Fichiers modifiés :** `src/pipeline/pdf_report_latex.py`, `templates/rapport_correction.tex`

---

## Phase 7 — Tests et intégration

### Tâches

**7.1 — Tests unitaires**
- `tests/test_teacher_validation.py` : tester `compute_final_score()` avec différents scénarios de décisions
- `tests/test_domain.py` : tester les nouveaux champs Pydantic

**7.2 — Test d'intégration end-to-end**
- Lancer Phase A sur une copie de test connue
- Simuler des décisions enseignant (tout accepter, puis quelques refus)
- Vérifier que Phase B produit un diagnostic cohérent

**7.3 — Validation UI**
- Vérifier le rendu du tableau sur des barèmes de tailles variées (10, 20, 33 questions)
- Vérifier la persistance du state entre Phase A et Phase B

---

## Résumé des fichiers touchés

| Fichier | Type de changement |
|---|---|
| `src/models/domain.py` | Ajout `TeacherDecision`, nouveaux champs `QuestionGrade` + `CopyGrade` |
| `src/pipeline/pipeline.py` | Scission en `run_phase_a()` + `run_phase_b()` |
| `src/ui/app.py` | Nouveau composant `render_validation_table()` + gestion session state |
| `prompts/diagnostic_prompt.md` | Instructions enrichies pour le diagnostic par question échouée |
| `src/api/claude_client.py` | Injection des données validation dans le prompt diagnostic |
| `src/pipeline/pdf_report_latex.py` | Nouvelle structure rapport (tableaux synthèse + diagnostic central) |
| `templates/rapport_correction.tex` | Template LaTeX reformaté |
| `tests/` | Nouveaux tests unitaires + intégration |

**Fichiers non touchés (infrastructure stable) :**
`src/pipeline/ingestion.py`, `src/pipeline/orchestrator.py`, `src/knowledge/`, `src/api/gemini_client.py`, `src/api/deepseek_client.py`, `src/api/mistral_client.py`, `src/core/config.py`

---

## Ordre d'implémentation recommandé

```
Phase 1 (domain.py)
    ↓
Phase 2 (pipeline.py scission)
    ↓
Phase 4 (compute_final_score)
    ↓
Phase 3 (UI tableau validation)  ←  le plus long, commencer tôt
    ↓
Phase 5 (diagnostic renforcé)
    ↓
Phase 6 (rapport reformaté)
    ↓
Phase 7 (tests)
```

Commencer par Phase 1 (30 min) permet de débloquer tout le reste.

---

*Hakili Lab · Plan interne · 2026-06-11*
