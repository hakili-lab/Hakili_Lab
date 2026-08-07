# Audit de la base de données et de la base de connaissance
**2026-07-30** · constats mesurés, pas déclaratifs — chaque chiffre est reproductible par les commandes indiquées.

---

## Verdict en une page

Le **référentiel est sain** : 101 compétences, 280 questions, 1 031 signatures, 284 options QCM, zéro violation d'intégrité. C'est la fondation, et elle tient.

Ce qui ne tient pas se répartit en trois familles :

1. **Le produit ne peut pas encore fonctionner** — 75 % des questions n'ont pas de corrigé. La correction automatique ne marche que sur les QCM.
2. **La base de connaissance a deux moitiés qui ne se parlent pas** — 121 leçons de curriculum, aucune rattachée aux compétences, 69 jamais référencées, 16 références cassées.
3. **Des trous dans le référentiel lui-même** — 4 notions enseignées n'ont aucune compétence, 27 compétences n'ont qu'un coût estimé.

Aucun de ces points ne demande un travail technique important. Ils demandent tous des **décisions et de la saisie pédagogique** — c'est le goulot, et il n'est pas de nature informatique.

---

## 1. État de la base

### 1.1 Volumétrie

| Table | Lignes | Constat |
|---|---|---|
| `Competence` | 101 | complet |
| `TypeErreur` | 7 | liste fermée, conforme |
| `Prerequis` | 136 | graphe acyclique, 6 racines |
| `CoutRemediation` | 606 | dont **162 estimés** (§3.3) |
| `Question` | 280 | 7 tests × 40 |
| `SignatureErreur` | 1 031 | 3 à 4 par question, **100 % couvertes** |
| `OptionQcm` | 284 | 71 QCM, tous avec bonne réponse |
| `Session`, `Evaluation`, `Reponse`, `Probleme`, `Transition`, `Seance` | **0** | jamais alimentées — le dispositif n'a jamais tourné |

### 1.2 Intégrité — aucun défaut

```
questions sans signature      0
QCM sans option               0
QCM sans bonne réponse        0
compétences sans coût         0
```

L'import est strict : un code inconnu fait échouer l'opération avant toute écriture. C'est ce qui explique ces zéros, et c'est à conserver.

### 1.3 Deux ORM sur une même base — dette structurelle assumée

| Propriétaire | Tables |
|---|---|
| SQLAlchemy (pipeline) | `copie`, `document` |
| Django | 13 tables métier + auth et sessions |

Le lien entre les deux — `Evaluation.copy_id`, `Correction.copy_id` → `copie.copy_id` — est un **champ texte sans contrainte de clé étrangère**. C'était le bon choix pendant la migration (une clé étrangère inter-ORM rend la base de test inutilisable), mais il a une conséquence à connaître : **rien n'empêche une `Correction` de pointer vers une copie inexistante**. Le cas se produit si le pipeline échoue avant d'écrire la `Copie` — par exemple quand l'élève n'est pas trouvé dans les Sheets.

Migrations : 4 révisions Alembic + 4 migrations Django. Aucune divergence détectée.

---

## 2. Constats classés par gravité

### 🔴 CRITIQUE — empêche la mise en service

**C1. 209 questions sur 280 n'ont pas de corrigé (75 %).**

| Test | Questions | Avec corrigé | Couverture |
|---|---|---|---|
| chacun des 7 | 40 | 10 (les QCM) | **25 %** |

Sans réponse attendue, l'outil n'a rien à quoi comparer la copie. La correction automatique ne fonctionne que sur les QCM, et les modules 3 à 9 n'ont pas de matière. *C'est le seul point qui empêche réellement le produit d'exister.*

**C2. Aucune correction réelle n'a jamais été exécutée de bout en bout.**

Les 6 tables de suivi sont vides. Toute la chaîne — transcription, correction, diagnostic, rapport — n'a été éprouvée que par des tests qui simulent le pipeline. Un défaut d'intégration ne se verrait qu'au premier essai réel.

### 🟠 MAJEUR — dégrade la valeur du produit

**M1. Le curriculum RAG est orphelin.**

```
121 leçons définies
  0 rattachées à un code canonique     <- arbitrage C
 69 jamais référencées                 (57 % de la base morte)
 16 références cassées                 (pointent vers des leçons inexistantes)
```

Ces 99 Ko de contenu pédagogique rédigé — savoirs, savoir-faire, erreurs fréquentes — sont inexploitables tant que le rapprochement n'est pas fait. Le module 7 (fiches de remédiation) en dépend directement.

**M2. Quatre notions enseignées n'ont aucune compétence au référentiel.**

Vérifié par recherche exhaustive dans les libellés **et** descriptions des 101 compétences : `probabilité`, `angle inscrit`, `similitude`, `variance / écart-type`. Un élève échouant dessus **ne peut pas être diagnostiqué**. S'y ajoute un décalage de niveau sur l'homothétie (curriculum 3e, référentiel 2nde C).

**M3. 162 des 606 coûts sont des estimations.**

Les 27 compétences de lycée n'ont pas de volume officiel ; une valeur de repli de 4 h leur est appliquée (D-CEO-29). Le palier d'un élève de 2nde ou de 1ère repose donc sur une estimation — marquée comme telle en base, mais qui détermine ce qu'une famille paiera.

### 🟡 MOYEN — dette à résorber

**Y1. 150 mots sans accent + 16 ambigus** dans les textes affichés à l'écran et dans les rapports lus par les parents.

**Y2. `runs/` est du disque local**, effacé à chaque redéploiement sur Railway ou Render. Les documents durables sont en base, mais une correction en cours perd ses fichiers de travail.

**Y3. Une seule instance possible.** Le thread de traitement vit dans un processus donné ; avec plusieurs instances, une correction lancée sur l'une paraîtrait figée aux autres.

**Y4. Streamlit est toujours présent** — 3 200 lignes d'interface morte, plus `streamlit` et `pandas` en dépendances.

**Y5. Aucune contrainte ne protège le lien `copy_id`** (§1.3) : une `Correction` peut pointer vers une copie qui n'existe pas.

### 🟢 MINEUR — à signaler, sans urgence

**N1. Quatre compétences ne sont évaluées par aucun test** : `G.SYMO` (symétrie orthogonale, 6e), `N.MAJ` (majorant/minorant, 2nde C), `F.COMP` (composition d'applications, 4e), `F.REL` (relations et fonctions, 6e). Soit les tests les ignorent à tort, soit ces compétences sont superflues.

**N2. `F.REL` est une racine du graphe de prérequis alors qu'elle est introduite en 6e**, quand les cinq autres racines sont toutes du primaire. Probable prérequis oublié. `F.REL` cumule trois anomalies — racine inattendue, jamais évaluée, libellé générique lors du rapprochement : elle mérite un examen.

**N3. Six compétences sans prérequis déclarés** — cohérent pour cinq d'entre elles (primaire), sauf `F.REL`.

---

## 3. Plan de remédiation, étape par étape

Les étapes sont **ordonnées par dépendance**, pas par difficulté. Chaque étape indique qui agit — c'est le point important : la plupart ne sont pas du travail technique.

### Étape 1 — Prouver que la chaîne fonctionne *(1 heure, vous)*
> Lève **C2**. Rien ne doit avancer avant.

1. Créer `.env` depuis `.env.example` avec `ANTHROPIC_API_KEY`, `DATABASE_URL` et les trois identifiants Sheets.
2. `python manage.py verifier_installation` — dit ce qui manque, avec la conséquence de chaque manque.
3. Imprimer un sujet depuis `/sujets/`, le faire remplir à la main, le scanner à 150 DPI.
4. `python manage.py verifier_installation --copie copie.pdf --test socle_3eme --eleve HAK-...`

**Critère de réussite :** une note finale et un rapport PDF sortent. Tant que ce n'est pas le cas, tout le reste est théorique.

### Étape 2 — Débloquer un seul niveau *(4 à 6 heures, enseignant de maths)*
> Lève **C1** partiellement — et c'est suffisant pour démarrer.

Ne pas viser les 209 corrigés. **Un seul test = 30 corrigés** (40 questions moins 10 QCM déjà faits).

1. Ouvrir `Lot_a_completer_2026-07-30.xlsx`, feuille `01_Corriges`, filtrer sur un niveau.
2. Remplir « Réponse attendue » — la démarche est facultative pour la partie A.
3. `python scripts/integrer_corriges.py --lot ...` puis `python scripts/generer_baremes_socle.py`

**Critère :** ce niveau passe de 25 % à 100 % de couverture. Les modules 3 et 4 deviennent possibles pour lui.

### Étape 3 — Retirer Streamlit *(2 heures, moi)*
> Lève **Y4**. Ne dépend que de l'étape 1.

Supprimer `src/ui/`, retirer `streamlit` et `pandas`, mettre à jour `README.md` et le registre. Tout est prêt : aucun test ne dépend plus de Streamlit.

### Étape 4 — Rattacher le curriculum *(2 à 3 heures, enseignant de maths)*
> Lève **M1**. Débloque le module 7.

1. `Lot_rapprochement_curriculum_2026-07-30.xlsx` — 31 propositions nettes à confirmer d'un coup d'œil, 85 à trancher, 5 sans candidat.
2. `python scripts/integrer_rapprochement.py --lot ...`

**Critère :** les 121 leçons portent un `code_competence` ou la mention « AUCUNE ». Le contenu rédigé devient alors indexable par compétence et peut enrichir l'ancrage du diagnostic.

### Étape 5 — Trancher les trous du référentiel *(1 heure, décision)*
> Lève **M2**.

Feuille `05_Notions_non_couvertes` : quatre notions sans compétence, plus le décalage sur l'homothétie. Trois issues par notion — créer une compétence, la rattacher à une compétence générique existante (`D.STAT1` couvre-t-elle la variance ?), ou constater qu'elle n'est pas évaluée et n'a pas besoin d'exister.

### Étape 6 — Sécuriser le déploiement *(3 heures, moi + vous)*
> Lève **Y2**, **Y3**, **Y5**.

1. Choisir l'hébergeur, **attacher un volume persistant** sur `runs/`, rester à une instance.
2. Ajouter un contrôle d'intégrité sur `copy_id` — une commande qui signale les `Correction` orphelines, plutôt qu'une contrainte de base impossible entre deux ORM.

### Étape 7 — Corriger les accents *(2 heures, enseignant de maths)*
> Lève **Y1**. Peut se faire en même temps que l'étape 2 ou 4.

Feuilles `02_Accents` et `03_Accents_a_arbitrer` — la correction se fait **dans le classeur source**, pas dans le code. Le garde-fou empêche déjà la situation d'empirer.

### Étape 8 — Examiner les anomalies mineures *(1 heure, enseignant de maths)*
> Lève **N1**, **N2**, **N3**.

Les quatre compétences jamais évaluées, et surtout `F.REL` qui cumule trois anomalies.

### Étape 9 — Généraliser *(le reste)*
Les 179 corrigés des six autres niveaux, puis les modules 2 à 9 selon la feuille de route.

---

## 4. Ce qu'il ne faut pas faire

**Ne pas attaquer le module 4 avant le module 3.** Sans corpus de référence tagué à la main, on n'a aucun moyen de mesurer si le diagnostic est bon. C'est la seule instruction du guide qui dit explicitement de ne pas sauter une étape.

**Ne pas supprimer les anciens barèmes** avant que l'étape 4 soit faite : ils portent le seul ancrage encore fonctionnel pour le mode libre.

**Ne pas déployer sur plusieurs instances** tant qu'aucune file de tâches n'est en place.

**Ne pas prendre les coûts estimés pour des valeurs officielles.** Ils déterminent le palier, donc la facture d'une famille. L'admin les affiche en orange — ce marquage doit survivre à toute refonte de l'interface.

---

## 5. Reproduire cet audit

```bash
python manage.py verifier_installation          # configuration, base, clés, référentiel
python scripts/verifier_accents.py              # 150 + 16
python scripts/rapprocher_curriculum.py         # état du rattachement
python manage.py test                           # 112 tests
python -m pytest tests/                         # 218 tests
```
