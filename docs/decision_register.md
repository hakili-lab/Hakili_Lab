# Registre des Décisions — Hakili Lab AI Correction
**Mis à jour le : 2026-06-08**

---

## Décisions initiales d'architecture (fondations techniques)

| ID | Décision | Statut | Justification |
|---|---|---|---|
| D001 | Ingestion par copie complète PDF/images, pas question par question | **Validée** | Plus rapide, moins fastidieux, meilleur flux terrain |
| D002 | JSON structuré comme source de vérité, PDF comme rendu | **Validée** | Facilite évaluation, audit et réutilisation |
| D003 | Streamlit pour l'interface MVP | **Validée** | Plus rapide à implémenter en Python |
| D004 | Stockage local anonymisé pour prototype | **Validée** | Simplicité + confidentialité |
| D005 | Évaluation sur 100 copies avec enseignant référent | **Validée** | Exigence du cahier de charges |

---

## Décisions CEO — 2026-05-08

### D-CEO-01 — Périmètre matières et niveaux du MVP
**Décision :** Mathématiques uniquement, tous niveaux du secondaire : **6e à la Terminale**.

---

### D-CEO-02 — Format du barème
**Décision :** Notation binaire — **1 ou 0** par question (ou sous-question).

**Règle métier clé :** Une question comportant N sous-questions est décomposée en N questions indépendantes, chacune valant 1 point. Il n'y a pas de notation partielle : une réponse est correcte (1) ou incorrecte (0).

*Exemple : Question 3 avec 3 sous-questions → Q3a (1 pt), Q3b (1 pt), Q3c (1 pt). La note de Q3 = somme des sous-questions.*

**Impact :** Le module de parsing du barème et le schéma `grading.json` sont simplifiés : `max_score` est toujours un entier, `score` est toujours 0 ou 1 par item.

---

### D-CEO-03 — Stratégie fournisseurs IA *(révisée 2026-06-05)*
**Décision initiale (2026-05-08) :** Anthropic Claude exclusivement.
**Décision révisée (2026-06-05) :** **Architecture multi-provider avec routing automatique par tâche.**

**Contexte de révision :** Un run réel sur une copie de 15-20 pages a coûté ~$8 avec Claude Opus 4.7 exclusif. L'analyse comparative a montré que chaque tâche a un provider optimal différent.

**Répartition finale :**

| Tâche | Provider | Modèle | Justification clé |
|---|---|---|---|
| Transcription | Google Gemini | gemini-2.0-flash | Vision native, tier gratuit 1M tok/j |
| Correction | DeepSeek | deepseek-chat (V3) | MATH-500 ~90%, 18× moins cher qu'Opus |
| Diagnostic | DeepSeek | deepseek-reasoner (R1) | Modèle de raisonnement, causes cachées |
| Remédiation | Mistral | mistral-small-latest | Français académique natif |
| Extraction structurée | Claude | claude-sonnet-4-6 | tool_use forcé, fiabilité JSON |

**Routing :** automatique selon clés API disponibles dans `.env` — fallback Claude si clé absente.

**Analyse complète :** [docs/ai_providers_analysis.md](ai_providers_analysis.md)

**Coût résultant :** ~$0.02/copie vs ~$8.00/copie initial — réduction ×400.

---

### D-CEO-04 — Couche d'instructions expert (optionnelle)
**Décision :** Ajout d'une **couche optionnelle d'instructions expert** injectée dans le prompt de correction.

**Fonctionnement :** Avant de lancer la correction, l'enseignant peut saisir des instructions contextuelles propres au devoir : attentes spécifiques, points de vigilance, critères d'interprétation. Ces instructions sont injectées dans le prompt système de l'IA pour affiner la correction.

**Tolérance :** La tolérance d'erreur cible est volontairement ambitieuse (proche de ±0 pt) grâce à cette couche contextuelle. L'objectif est que l'IA produise une correction de très haute qualité lorsque les instructions expert sont fournies.

**Cette couche est optionnelle :** sans instructions, la correction reste basée uniquement sur l'énoncé et le barème.

---

### D-CEO-05 — Validation humaine
**Décision :** La **validation humaine est supprimée du pipeline applicatif**.

**Justification :** Elle se fait hors plateforme, par l'enseignant directement sur le rapport généré. Le système ne bloque plus la restitution en attente d'une validation dans l'interface.

**Conséquence :** Le flag `requires_teacher_review` reste présent dans les données JSON (information utile), mais aucun écran de validation n'est intégré dans le flux.

---

### D-CEO-06 — Format du rapport PDF
**Décision :** Contenu minimal du rapport :

- Note totale et détail par question (avec sous-questions)
- Commentaire pédagogique par question
- Zones marquées "Révision requise" (si confiance IA faible)
- Diagnostic des compétences maîtrisées / lacunes
- Plan de remédiation élève
- Score de confiance IA visible
- Logo Hakili Lab
- Numéro d'anonymisation de l'élève (pas de nom)

**Mode d'affichage :** Le contenu du rapport est d'abord affiché directement dans l'interface Streamlit. Un bouton "Télécharger le PDF" permet ensuite d'exporter le rapport.

---

### D-CEO-07 — Politique d'identification *(anonymisation supprimée)*
**Décision :** **Suppression de l'anonymisation.** Les copies sont identifiées par le nom réel de l'élève.

**Processus :**
1. L'enseignant saisit le nom de l'élève (copie unique) ou le fichier est nommé avec le nom de l'élève (batch).
2. Un identifiant technique sûr (slug, ex. `aminata_sawadogo`) est dérivé du nom pour les dossiers et fichiers.
3. Le PDF exporté affiche le nom réel de l'élève.
4. Aucune fiche de correspondance n'est générée.

**Justification :** La correction est un acte pédagogique interne — l'anonymisation compliquait le flux sans apporter de valeur dans le contexte d'utilisation réel.

---

### D-CEO-08 — Ressources internes pour la remédiation
**Décision :** Reporté — remédiation **générique** pour le MVP. L'IA suggère des thèmes et types d'exercices sans pointer vers une base de ressources. Option B (librairie Hakili) réservée à une version ultérieure.

---

### D-CEO-09 — Deux modes d'interface
**Décision :** L'interface Streamlit propose **deux modes distincts** :

| Mode | Description |
|---|---|
| **Copie Unique** | Traitement et correction d'une seule copie, résultat immédiat |
| **Batch** | Traitement d'un lot de copies (plusieurs élèves en une session), rapport consolidé |

Les deux modes partagent le même pipeline. Le mode Batch ajoute une boucle d'itération et une synthèse de classe (distribution des notes, compétences globales).

---

### D-CEO-10 — Format d'entrée optimal *(nouveau 2026-06-05)*
**Décision :** **PDF multi-pages scanné à 150 DPI, mode niveaux de gris.**

> **DPI** (*Dots Per Inch*) : nombre de pixels capturés par pouce (2,54 cm) de document physique. Un scan A4 à 150 DPI produit une image de 1 240 × 1 754 pixels, suffisant pour lire exposants et barres de fraction. À 300 DPI, l'image est 4× plus lourde sans gain de qualité pour un LLM.

**Justification :**
- 150 DPI satisfait le critère de Nyquist pour les traits manuscrits (≥ 2× la fréquence des éléments les plus fins)
- Scanner = distorsion perspective nulle (θ = 0°) vs photo téléphone (θ = 20-35° → 13% compression)
- Niveaux de gris : conserve les demi-tons (traits pâles) contrairement au N&B pur
- 300 DPI = overkill : +80% de tokens sans gain perceptible pour un LLM

**Matériel recommandé :**
- Usage régulier : Scanner ADF (ex. Epson WorkForce ES-65W, ~$130)
- Terrain : Smartphone + Microsoft Lens (mode Document → correction perspective automatique)

**Analyse complète :** [docs/input_pipeline_analysis.md](input_pipeline_analysis.md)

---

### D-CEO-11 — Coût cible et volume de référence *(nouveau 2026-06-05)*
**Décision :** Coût cible en production validé : **~$0.02/copie (avec Gemini), ~$12/an pour 540 copies.**

**Hypothèse de référence :**
- Volume : 3 classes × 6 évaluations × 30 élèves = 540 copies/an
- Pages/copie : ~11 pages (constaté sur copie réelle, 150 DPI)
- Total pages : ~5 940 pages/an → 33 pages/jour scolaire (Gemini tier gratuit : 1M tok/j)

**Coût réel mesuré par scénario (11 pages, 150 DPI) :**

| Scénario | Transcription | Correction | Diagnostic | Remédiation | **Total/copie** | **Total 100 copies** |
|---|---|---|---|---|---|---|
| Optimal (Gemini actif) | Gemini Flash ~$0.008 | DeepSeek V3 | DeepSeek R1 | Mistral | **~$0.028** | ~$2.80 |
| Actuel (Gemini KO, région) | Sonnet 4.6 ~$0.27 | DeepSeek V3 | DeepSeek R1 | Mistral | **~$0.29** | ~$29 |
| Fallback total (Claude seul) | Sonnet 4.6 ~$0.27 | Sonnet 4.6 | Haiku 4.5 | Sonnet 4.6 | **~$0.48** | ~$48 |

**Poste dominant : la transcription (vision).** Elle représente 93% du coût actuel parce que Claude Sonnet traite les images à $3/M tokens vs $0.10/M pour Gemini Flash. Réactiver Gemini réduirait le coût par 10.

**Seuil d'alerte :** si le volume dépasse 200 copies/jour avec Gemini actif, passer au tier payant (~$2/an supplémentaires).

---

### D-CEO-12 — Diagnostic ancré sur le programme officiel (RAG) *(nouveau 2026-06-08)*
**Décision :** Implémenter un système **RAG (Retrieval-Augmented Generation)** basé sur les curricula officiels du Burkina Faso pour le secondaire (6e → 3e).

**Architecture RAG :**
1. **Base de connaissance** (`data/knowledge/curriculum_*.yaml`) — 121 leçons structurées par classe, domaine, chapitre et leçon, avec `savoir`, `savoir_faire[]`, `prerequis_ids[]`, `mots_cles[]`, `erreurs_frequentes[]`
2. **Barèmes enrichis** (`data/knowledge/bareme_test_*.yaml`) — chaque question du test est mappée à ses `chunk_ids` de curriculum
3. **Retrieval** (`src/knowledge/curriculum_retriever.py`) — à la fin de la correction, les chunks associés aux questions échouées sont récupérés et injectés dans le prompt diagnostic via `{{CURRICULUM_CONTEXT}}`
4. **Sortie structurée** — `DiagnosticResult.competency_gaps: list[CompetencyGap]` avec chunk_id, classe, domaine, leçon, savoir_faire, erreurs_fréquentes

**Justification :** Un diagnostic qui dit "lacune en algèbre" est inutilisable. Un diagnostic qui dit "l'élève ne maîtrise pas `[4e_NUM_Ch4_L3] Identités remarquables` — erreur fréquente : (a+b)² = a²+b² (oubli de 2ab)" est actionnable par l'enseignant et valorisable auprès des parents.

**Couverture actuelle :** 6e, 5e, 4e, 3e. Le primaire (CE1–CM2, pertinent pour le test 6e) n'a pas encore de chunks — le diagnostic reste valide mais sans références de leçons spécifiques.

**Backward-compatible :** `get_diagnostic_context()` retourne `""` si `bareme_id` absent ou si aucune question échouée → le pipeline tourne sans RAG sans modification.

---

### D-CEO-13 — Tests Hakili pré-chargés (TestRegistry) *(nouveau 2026-06-08)*
**Décision :** Créer un **catalogue de tests standards Hakili** (`src/knowledge/test_registry.py`) qui auto-charge l'énoncé et le barème de chaque test standard au démarrage de la session.

**Flux enseignant avec TestRegistry :**
1. L'enseignant sélectionne "Test d'entrée en 3e" dans le menu déroulant
2. Un bandeau confirme : `✓ Énoncé pré-chargé (3 777 car.) · ✓ Barème 33 questions · ✓ RAG activé`
3. L'enseignant charge **uniquement la copie de l'élève** (PDF ou photos)
4. Aucun upload d'énoncé ni de barème n'est demandé

**Tests disponibles (v1) :**

| ID | Label | DOCX source | Barème YAML | Questions |
|---|---|---|---|---|
| `hakili_3e_v1` | Test d'entrée en 3e | `Hakilisso test de niveau 3e.docx` | `bareme_test_3e.yaml` | 33 (NUM + GEO) |
| `hakili_6e_v1` | Test d'entrée en 6e | `TEST DE NIVEAU,6eme,GROUPE 1.docx` | `bareme_test_6e.yaml` | 33 (NUM + GEO) |

**Justification :** Éliminer la friction opérationnelle (upload énoncé + saisie barème à chaque copie) est critique pour que l'outil soit utilisé quotidiennement par les enseignants Hakili sans formation.

**Extension :** Ajouter un test = ajouter une entrée dans `_TEST_CATALOG` + un DOCX dans `data/Documents/` + un YAML dans `data/knowledge/`. Aucune modification du code pipeline nécessaire.

---

### D-CEO-14 — Interface premium et positionnement marketing *(nouveau 2026-06-08)*
**Décision :** L'interface doit refléter le positionnement premium de Hakili Lab et fonctionner comme **instrument marketing** auprès des parents d'élèves.

**Implémentation (`src/ui/progress.py`) :**
- **Écran "Analyse en cours"** (remplace le spinner Streamlit générique) avec 7 étapes nommées, barre de progression temps réel (%, transition CSS cubic-bezier), logo Hakili animé (pulsation avec lueur)
- **Palette identitaire** : `#001e4a` (bleu marine), `#4a90e2` (bleu Hakili), `#27ae60` (vert validation)
- **Langage** : "Correction intelligente — ensemble voting", "Diagnostic pédagogique approfondi", "Génération du plan de remédiation" — vocabulaire expert qui justifie la valeur
- **Validation** : bandeau vert "✓ Analyse complète — rapport disponible" à la fin

**Étapes visibles (7) :**

| Étape | Label affiché | % déclenchement |
|---|---|---|
| ingestion | Ingestion & contrôle qualité image | 8% |
| transcription | Transcription multimodale (manuscrit) | 28% |
| correction | Correction intelligente — ensemble voting | 55% |
| rag | Récupération du contexte programme | 68% |
| diagnostic | Diagnostic pédagogique approfondi | 80% |
| remediation | Génération du plan de remédiation | 90% |
| export | Export PDF & rapport JSON | 98% |

**Modèle commercial visé :** Outil interne Hakili Lab pour les enseignants. Le rapport PDF + sujet de remédiation constituent le livrable.

**Justification :** Un outil qui produit un "spinner" générique n'est pas facturable. Un outil qui montre en temps réel une "Transcription multimodale" puis un "Diagnostic pédagogique approfondi" ancré sur le programme officiel justifie un prix premium.

---

## Tableau de synthèse

| ID | Sujet | Décision finale | Date |
|---|---|---|---|
| D001 | Flux d'ingestion | Copie complète (pas exercice par exercice) | 2026-05-08 |
| D002 | Source de vérité | JSON → PDF | 2026-05-08 |
| D003 | Interface | Streamlit | 2026-05-08 |
| D004 | Stockage | Local pour prototype | 2026-05-08 |
| D005 | Volume cible | 100 copies réelles | 2026-05-08 |
| D-CEO-01 | Matières et niveaux | Mathématiques, **6e à la Terminale** | 2026-05-08 |
| D-CEO-02 | Format barème | Binaire 0/1 par question et sous-question | 2026-05-08 |
| D-CEO-03 | Stratégie IA | **Multi-provider** (Gemini + DeepSeek + Mistral + Claude) | **2026-06-05** |
| D-CEO-04 | Instructions expert | Couche optionnelle d'instructions contextuelles | 2026-05-08 |
| D-CEO-05 | Validation humaine | Hors plateforme (enseignant sur PDF exporté) | 2026-05-08 |
| D-CEO-06 | Rapport PDF | Note · commentaires · diagnostic · remédiation · confiance | 2026-05-08 |
| D-CEO-07 | Identification | Nom réel de l'élève (slug technique pour fichiers) | 2026-05-08 |
| D-CEO-08 | Remédiation | Sujet d'exercices personnalisé (5 exos/lacune) | 2026-05-08 |
| D-CEO-09 | Modes interface | Copie Unique + Batch | 2026-05-08 |
| D-CEO-10 | Format entrée | **PDF scanner 150 DPI, niveaux de gris** | **2026-06-05** |
| D-CEO-11 | Coût cible | **~$0.02/copie · ~$12/an** pour 540 copies | **2026-06-05** |
| D-CEO-12 | Diagnostic RAG | Ancré sur programme officiel MEN Burkina Faso (121 leçons 6e→3e) | **2026-06-08** |
| D-CEO-13 | Tests Hakili pré-chargés | TestRegistry : énoncé + barème auto · enseignant charge uniquement la copie | **2026-06-08** |
| D-CEO-14 | UI premium · marketing | Écran animé Hakili · 7 étapes en temps réel · logo pulsant · facturable parents | **2026-06-08** |
