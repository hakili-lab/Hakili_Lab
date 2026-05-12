# Registre des Décisions — Hakili Lab AI Correction
**Mis à jour le : 2026-05-08**

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

### D-CEO-01 — Périmètre matières du MVP
**Décision :** Mathématiques uniquement.

---

### D-CEO-02 — Format du barème
**Décision :** Notation binaire — **1 ou 0** par question (ou sous-question).

**Règle métier clé :** Une question comportant N sous-questions est décomposée en N questions indépendantes, chacune valant 1 point. Il n'y a pas de notation partielle : une réponse est correcte (1) ou incorrecte (0).

*Exemple : Question 3 avec 3 sous-questions → Q3a (1 pt), Q3b (1 pt), Q3c (1 pt). La note de Q3 = somme des sous-questions.*

**Impact :** Le module de parsing du barème et le schéma `grading.json` sont simplifiés : `max_score` est toujours un entier, `score` est toujours 0 ou 1 par item.

---

### D-CEO-03 — Fournisseur IA
**Décision :** **Anthropic Claude** exclusivement pour le prototype et la production.

**Justification :** Meilleures performances sur les tâches de raisonnement mathématique. L'abstraction multi-fournisseur (D004 initiale) est simplifiée : Claude reste le fournisseur unique, aucun switch de provider prévu.

**Modèle cible :** `claude-opus-4-7` pour la correction (raisonnement), `claude-haiku-4-5-20251001` pour les tâches légères (contrôle qualité, résumé).

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

### D-CEO-07 — Politique d'anonymisation
**Décision :** Système de **numérotation anonyme** avec fiche de correspondance séparée.

**Processus :**
1. L'enseignant saisit le nom de chaque élève avant traitement.
2. Le système attribue automatiquement un numéro anonyme (ex. `E-001`, `E-002`).
3. La fiche de correspondance `nom ↔ numéro` est stockée localement, séparément des copies traitées.
4. Tous les artefacts (JSON, PDF) ne contiennent que le numéro.
5. L'enseignant peut télécharger la fiche de correspondance en fin de session.

**Le PDF exporté ne contient jamais le nom de l'élève.**

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

## Tableau de synthèse

| ID | Sujet | Décision finale |
|---|---|---|
| D001 | Flux d'ingestion | Copie complète (pas exercice par exercice) |
| D002 | Source de vérité | JSON → PDF |
| D003 | Interface | Streamlit |
| D004 | Stockage | Local + anonymisé |
| D005 | Volume cible | 100 copies réelles |
| D-CEO-01 | Matières | Mathématiques uniquement |
| D-CEO-02 | Format barème | Binaire 0/1 par question et sous-question |
| D-CEO-03 | Fournisseur IA | Anthropic Claude (exclusif) |
| D-CEO-04 | Tolérance / instructions expert | Couche optionnelle d'instructions expert |
| D-CEO-05 | Validation humaine | Supprimée du pipeline (hors plateforme) |
| D-CEO-06 | Rapport PDF | 7 éléments + affichage plateforme + téléchargement |
| D-CEO-07 | Confidentialité | Numérotation anonyme + fiche de correspondance |
| D-CEO-08 | Remédiation | Générique (librairie Hakili reportée) |
| D-CEO-09 | Modes interface | Copie Unique + Batch |
