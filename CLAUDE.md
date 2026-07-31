# CLAUDE.md — Hakili Lab AI Assisted Correction

## Rôle de Claude Code

Tu es l'assistant d'ingénierie du projet Hakili Lab : outil de correction assistée par IA pour copies manuscrites de mathématiques, utilisé par les enseignants Hakili Lab au Burkina Faso.

**Objectif central actuel : remplacer le diagnostic en texte libre par un système de suivi structuré et traçable.** Le diagnostic n'est plus une phrase générée par un LLM — c'est une liste d'objets comptables (`compétence × type d'erreur`), avec un cycle de vie d'états daté, qui permet de mesurer une progression, de comparer des élèves, et de calculer un coût de remédiation. C'est le chantier "Urie v2" (`guide-urie.md`, `protocole-urie.md`, 28 juillet 2026), décrit en détail plus bas.

Ce document a deux parties : l'état réel de l'infrastructure aujourd'hui, puis le chantier en cours.

---

## Partie 1 — État réel de l'infrastructure

`docs/decision_register.md` (D001 à D-CEO-25) est la **source de vérité datée** pour toute décision d'architecture. Lis-le avant de toucher à l'auth, à la persistance, ou aux Sheets — ce qui suit n'en est qu'un résumé, il peut avoir été complété depuis.

### ⚠ Migration en cours : Streamlit → Django (D-CEO-28)

Le projet est **en transition**. Django porte désormais le socle de données du chantier Urie v2 ; Streamlit porte encore toute l'interface existante. Les deux tournent sur la même base Neon, sans recouvrement d'écriture.

| Ce qui est en Django | Ce qui reste sur Streamlit |
|---|---|
| Les 11 tables du référentiel et du suivi | **Rien de fonctionnel** — `src/ui/app.py` est conservé comme filet |
| Authentification nom+PIN adossée au Sheet (`comptes/`) | |
| Suivi des élèves, profil, documents, statistiques (`suivi_web/`) | |
| Correction : copie unique, classe entière, mode libre (`correction_web/`) | |

Le pipeline (`src/api/`, `src/pipeline/`, `src/knowledge/`) est **indépendant du
framework** et sert aux deux. Streamlit ne sera supprimé qu'après un essai réel de
bout en bout : `manage.py verifier_installation --copie … --test … --eleve …`

`src/api/`, `src/pipeline/`, `src/knowledge/`, `src/models/`, `src/core/`, `src/integrations/` sont **indépendants du framework** — ne pas y introduire de dépendance à Django ou à Streamlit.

**Commandes :**
```bash
DEBUG=true python manage.py runserver                 # interface web (admin sur /admin/)
DEBUG=true python manage.py verifier_installation     # contrôle avant mise en service
DEBUG=true python manage.py importer_referentiel      # import du classeur (idempotent)
DEBUG=true DATABASE_URL="sqlite:///:memory:" python manage.py test   # tests Django
python -m pytest tests/                               # tests du pipeline
```
Note : `DATABASE_URL` suit la convention SQLAlchemy (`sqlite:///:memory:`, trois barres)
— la même URL sert aux deux ORM.

Deux pièges à connaître : les settings Django **ne lisent pas** `src/core/config.py` (son `Settings()` exige `anthropic_api_key`, ce qui casserait `migrate`), et `Evaluation.copy_id` est un **champ texte, pas une clé étrangère** — la table `copie` appartient à SQLAlchemy pendant la transition.

### Persistance : deux systèmes, un seul rôle chacun
- **Google Sheets** (`src/integrations/google_sheets.py`) — source de vérité pour l'**identité** : élèves (`get_eleves()`) et personnel (`get_personnel()`, un seul Sheet fusionné pour enseignants/responsables/admin, colonne `role`). Contrôlé par un tiers (le docteur), lecture seule côté app. **Ne jamais recréer une table `eleve` ou `utilisateur` en base** — ça a déjà été fait et démoli deux fois (D-CEO-20, D-CEO-21) parce que ça crée une deuxième source de vérité qui diverge.
- **Postgres/Neon** (`src/db/database.py`, `src/db/models.py`, migrations Alembic) — ne garde que ce qui concerne la correction elle-même : `copie` (copy_id, `identifiant_hakili` texte — pas de FK vers une table élève —, classe, notes) et `document` (scan/rapport/remédiation en BYTEA). Le pipeline y écrit en best-effort à 5 points d'injection (D-CEO-19) ; le seul point non best-effort est la vérification que l'élève existe dans le Sheet **avant** tout appel IA (D-CEO-20).
- `pool_pre_ping=True` / `pool_recycle=300` sur le moteur SQLAlchemy — Neon met la base en veille, ne pas retirer ça sans comprendre pourquoi c'est là (D-CEO-19).

### Authentification et rôles
Connexion par **nom (liste déroulante recherchable) + PIN à 4 chiffres**, les deux lus dans le Sheet personnel à chaque connexion — pas de mot de passe, pas de table `credentials` en base (supprimée, D-CEO-25). Rôles : `administrateur`, `responsable`, `enseignant`, dérivés de la colonne `role` du Sheet. `src/services/auth_service.py` porte la logique ; `UserRole` (`src/db/models.py`) n'est plus qu'un enum de confort, pas un type de colonne SQL.

Centres dérivés dynamiquement des Sheets (`src/core/centre_normalizer.py`, `deriver_centres()`) — plus de liste figée. Un centre vu une seule fois est signalé "suspect" sans jamais être bloqué.

### Périmètre : un centre d'encadrement, pas une école (D-CEO-32)
**Toute personne autorisée voit tous les élèves et peut corriger n'importe quelle copie.** Le cloisonnement par centre et par classe a été retiré : les enseignants tournent et reprennent les copies d'un collègue absent, le filtrage bloquait un travail légitime sans rien protéger. Une copie mal attribuée est empêchée par la **sélection explicite de l'élève** (D-CEO-20), pas par le périmètre. Le rôle ne commande plus qu'une chose : l'accès à l'administration. Les affectations (centre, classe) restent lues du Sheet, à titre informatif.

### Écrans (`suivi_web/`, migrés depuis Streamlit)
- **Accueil** : liste des élèves avec pastille de tendance (vert/orange/rouge/gris, `src/core/tendance.py`, `SEUIL_TENDANCE = 1.0`), baisses en premier.
- **Profil élève** : une seule vue pour tous les rôles — tendance, copies chronologiques, documents servis par jeton signé (`suivi_web/jetons.py`, jamais `identifiant_hakili` en clair dans une URL).
- **Parcours** (`/parcours/<jeton>/`) : plan de remédiation ordonné, volume, palier, inscription au programme.
- **Admin** : statistiques + `/personnel/` en lecture seule (qui peut se connecter, qui ne le peut pas, comptes en défaut en premier).

### Pipeline de correction (existant, réutilisable — chantier Urie v2 vient s'y ajouter, pas le remplacer entièrement)
- Ingestion PDF/images 150 DPI (`src/pipeline/ingestion.py`)
- Transcription multimodale (Gemini 2.5 Flash / Claude Sonnet fallback)
- Correction binaire 0/1 proposée par IA, validée par l'enseignant dans un tableau (`TeacherDecision`, `src/models/domain.py` — **déjà implémenté**, `compute_final_score()` priorise la décision enseignant)
- Diagnostic + remédiation + export PDF/HTML (`src/pipeline/pdf_report_html.py`, `pdf_remediation_html.py`)
- Routing multi-provider automatique par tâche, fallback Claude (table complète : voir `docs/decision_register.md` D-CEO-03)

**Attention à un piège de doc :** `README.md` décrit encore `TeacherDecision` et le tableau de validation comme "à construire". **C'est fait.** Ne t'y fie pas pour l'état d'avancement — vérifie `docs/urie_v2_roadmap.md` et `docs/decision_register.md`. (`AGENTS.md` portait la même erreur : supprimé au nettoyage du 2026-07-30.)

---

## Partie 2 — Chantier en cours : Urie v2, le suivi structuré

### Documents de référence (à lire dans cet ordre, avant tout code de ce chantier)
1. `protocole-urie.md` (racine du dépôt de travail, hors `Hakili_Lab/`) — le vocabulaire et les règles métier
2. `guide-urie.md` — les 9 modules à construire, module par module
3. `Referentiel_Urie_v0.xlsx` — le classeur : 101 compétences, 7 types d'erreur, 1031 signatures d'erreur, 284 distracteurs QCM tagués, 444 coûts de remédiation précalculés

### Le principe : un problème = une compétence × un type d'erreur
L'unité de suivi n'est plus un score mais un **problème**, avec un cycle de vie d'états datés : `hypothese → confirme/ecarte → en_remediation → resolu/non_resolu → regresse → clos`. Sept types d'erreur, liste **fermée** : `PRQ` (prérequis manquant), `CPT` (conceptuelle), `MOD` (modélisation), `PRC` (procédurale), `CNS` (connaissance non disponible), `RED` (rédaction), `ATT` (inattention — ne donne jamais lieu à remédiation).

### Trois règles non négociables
1. **Aucun code de compétence ou de type d'erreur n'est inventé.** Tout vient du référentiel. Un code absent est un bug, pas une variante.
2. **Aucune sortie en texte libre côté diagnostic structuré.** Chaque module rend des objets structurés à champs fixes.
3. **Aucune tâche n'est automatisée avant d'avoir été faite à la main une fois** — sans point de comparaison (le corpus de référence, module 3), impossible de savoir si un module fonctionne.

### Décision d'architecture actée (ne pas suivre le guide littéralement ici)
Le guide (`guide-urie.md`) prescrit une base **SQLite séparée** à 11 tables. **Décision actée avec l'utilisateur : ces tables vivent dans la base Neon/Postgres existante**, pas dans une SQLite isolée — une seule base pour toute la persistance applicative, cohérent avec la discipline "une seule source de vérité" déjà appliquée au projet (D-CEO-20/21/25). Détail complet du schéma retenu : `C:\Users\Urie\.claude\plans\dynamic-wandering-duckling.md`.

Points clés de cette adaptation :
- `evaluation` référence `copie.copy_id` (nullable) au lieu de dupliquer le stockage des scans/documents — un `T0`/`T1`/etc. réutilise la `Copie` déjà persistée par le pipeline existant.
- L'identité élève reste `identifiant_hakili` (texte), jamais une FK vers une table `eleve` — cohérent avec D-CEO-20.
- Nommer la table de session `session_urie` (pas `session`, ambigu avec la session Streamlit).
- Import du classeur via un script idempotent (pattern `seed_users.py`), pas de saisie manuelle des tables référentiel/banque de questions.

Le diagnostic structuré (module 4) **remplace directement** l'actuel `DiagnosticResult`/`CompetencyGap` en texte libre — niveau par niveau, au fur et à mesure que le référentiel et la grille de diagnostic couvrent ce niveau. Pas de coexistence longue entre les deux systèmes.

### Les 9 modules — suivi détaillé dans `docs/urie_v2_roadmap.md`

Ce chantier se déroule en 9 modules dépendants (0 → 9, chacun a besoin des précédents : appropriation du référentiel, socle de données, lecture des copies par zones, corpus de référence, diagnostic contraint, composition du test de confirmation, palier et plan de remédiation, génération des fiches, interfaces de saisie, restitution et indicateurs).

**`docs/urie_v2_roadmap.md` est la seule source de vérité sur l'avancement** — statut par module, sous-tâches, critères de fin, jalons de validation, et un journal de bord daté. **Lis-le en début de session, mets-le à jour en fin de session.** Ne pas recréer un deuxième tableau de suivi ici : ce serait reproduire l'erreur "deux sources de vérité" déjà corrigée deux fois sur ce projet (D-CEO-20, D-CEO-21).

**Jalon de validation obligatoire avant tout déploiement réel du module 4 :** cent sorties consécutives valides (aucun code hors référentiel), diagnostic comparé au tagage manuel du corpus de référence, écart mesuré et consigné.

### Protocole T0→T5 — cinq étapes, pas six (D-CEO-33)
T0 positionnement (1h30) → diagnostic machine → T1 confirmation (45min, discrimine chaque hypothèse) → **inscription au programme** (décision humaine, `Session.inscrire()`) → remédiation hors plateforme (8-20h) → T3 vérification en fin de volume horaire → T4/T5 rétention (45j, 3 mois). **T2 (mi-parcours) est retiré** — il ne correspond pas à la pratique du centre. **Un même type d'évaluation peut se répéter** (plusieurs T3 tant que les lacunes tiennent), distingué par un rang attribué automatiquement.

Palier selon coût total à T1 : A (<8h, ciblé) · B (8-20h, complet) · C (>20h, hors dispositif — le dire clairement plutôt que vendre un plan voué à l'échec ; `inscrire()` refuse le palier C sans motif explicite tracé).

Sept états de session (D-CEO-34), dont **trois sorties sans remédiation à ne pas confondre** : `sans_suite` (T1 n'a rien confirmé — c'est un **bon** résultat), `hors_dispositif` (palier C, orientation), `abandonnee` (retrait de la famille). Le détail fait foi dans `docs/cycle_de_suivi.md`.

---

## Contraintes actives (fusion existant + chantier Urie v2)

- Python + **Django (rendu serveur, HTMX)** — Streamlit n'est plus qu'un filet en attente de l'essai réel de bout en bout (D-CEO-28).
- Barème binaire 0/1 par question et sous-question (hors nouveau format QCM/court/rédigé du chantier Urie).
- L'enseignant a toujours le dernier mot sur le score (`TeacherDecision`, déjà implémenté).
- **Aucun code de compétence ou de type d'erreur inventé — tout vient du référentiel.**
- **Aucun appel LLM pour interpréter un QCM** — la table `option_qcm` donne la réponse directement.
- Identité élève/personnel : Google Sheets, jamais recréée en base.
- Coût cible pipeline correction : ~$0.02/copie (avec Gemini actif).

---

## Style de travail

Avant de coder sur ce dépôt :
1. Lire `docs/decision_register.md` — décisions actives et datées.
2. Si la tâche touche le chantier Urie v2 : lire aussi `protocole-urie.md`, `guide-urie.md`, et parcourir `Referentiel_Urie_v0.xlsx`.
3. Lire `src/models/domain.py` (schémas pipeline existant) et `src/db/models.py` (schéma Postgres existant) avant d'ajouter un champ ou une table.
4. Proposer un plan si la tâche touche plusieurs modules ou plusieurs fichiers.
5. Ne pas recréer ce qui existe — vérifier `src/knowledge/`, `src/pipeline/`, `src/api/`, `src/services/`, `src/integrations/` avant d'écrire une nouvelle fonction.
6. Ne jamais réintroduire une table `eleve` ou `utilisateur`/`credentials` en Postgres — l'identité vit dans les Sheets (D-CEO-20/21/25).

---

## Ce qu'il ne faut pas faire

- Ouvrir le chantier du site web en parallèle du chantier Urie v2. Un seul chantier prioritaire à la fois.
- Ajouter une colonne, un état ou un type d'erreur au référentiel sans en parler.
- Laisser un LLM produire une phrase là où un code structuré est attendu (diagnostic module 4).
- Appeler un modèle de langage pour interpréter un QCM.
- Sauter le module 3 (corpus de référence) — c'est lui qui donne à tous les autres leur point de comparaison.
- Stocker un code local de matrice (`N-a`, `G-c`...) en base — seuls les codes canoniques de l'onglet `02_Competences` sont stables entre niveaux.

---

## Commandes

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
$env:DEBUG="true"; python manage.py runserver     # interface Django, admin sur /admin/
streamlit run src\ui\app.py                       # filet, le temps de l'essai réel

# Unix / make
make setup && make run          # lance Django
make run-streamlit              # l'ancienne interface, tant qu'elle est en service
make test
make lint

# Migrations (Alembic, base Neon)
alembic upgrade head
alembic downgrade -1
```

---

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `src/pipeline/pipeline.py` | Pipeline de correction principal (Phase A/B, déjà scindé) |
| `src/models/domain.py` | Schémas Pydantic pipeline — `TeacherDecision`, `CopyGrade`, `DiagnosticResult` |
| `hakili/settings.py` | Configuration Django — base Neon, sécurité, support SQLite pour les tests |
| `referentiel/models.py` | 7 tables du référentiel et de la banque de questions (importées du classeur) |
| `suivi/models.py` | 6 tables de suivi — `Probleme.changer_etat()`, `Transition`, `Session.inscrire()` et `calculer_palier()`, cœur du dispositif |
| `suivi/plan.py` | Plan de remédiation — tri topologique sur les prérequis, coût, palier (module 6) |
| `referentiel/couts.py` | Formule de coût — arrondi 0,5 h, plancher 0,5, plafond 4, volume de repli lycée (D-CEO-29) |
| `referentiel/contexte.py` | Ancrage du diagnostic reconstruit depuis le référentiel (D-CEO-30) |
| `comptes/` | Authentification Django adossée au Sheet — session signée, décorateurs d'accès |
| `correction_web/` | Flux de correction sous Django — copie unique, lot, mode libre ; état en base, pas en session |
| `suivi_web/jetons.py` | Jetons signés dans les URL à la place de `identifiant_hakili` (D-CEO-25) |
| `referentiel/management/commands/importer_referentiel.py` | Import idempotent du classeur |
| `src/db/models.py` | Schéma SQLAlchemy — `copie` et `document` seulement (Streamlit) |
| `src/db/database.py` | Connexion Neon (`pool_pre_ping`, `pool_recycle`) |
| `src/integrations/google_sheets.py` | Source de vérité identité élèves/personnel |
| `src/services/auth_service.py` | Authentification nom+PIN par rôle |
| `src/core/tendance.py` | Calcul de tendance (pattern à réutiliser pour les indicateurs module 9) |
| `src/core/centre_normalizer.py` | Dérivation des centres depuis les Sheets |
| `src/ui/app.py` | Interface Streamlit — navigation par menu interne, tous les tableaux de bord |
| `docs/decision_register.md` | Toutes les décisions actives et datées — source de vérité |
| `docs/cycle_de_suivi.md` | **Le cycle T0→T5 en détail** — états d'un problème, règles de décision, ce que le cycle produit. Fait foi sur le déroulé |
| `docs/audit_donnees.md` | Audit de la base et de la connaissance — constats classés par gravité, plan en 9 étapes |
| `docs/urie_v2_roadmap.md` | Chantier Urie v2 — avancement détaillé, jalons, journal de bord — source de vérité sur "où en est-on" |
| `docs/harmonisation_donnees.md` | Écart ancien système ↔ référentiel Urie v2 — arbitrages en attente, défauts constatés. **À lire avant le module 1** |
| `docs/deploiement.md` | Mise en service Railway/Render — variables, limites de stockage, données de mineurs |
| `docs/architecture_cible.md` | Recommandation de sortie de Streamlit (Django + HTMX) + traitement des accents. **Décision à trancher avant le module 1** |
| `docs/accents_a_corriger.md` | Généré — liste des accents à corriger dans le classeur, à remettre au docteur |
| `guide-urie.md` | Chantier Urie v2 — les 9 modules, détaillés |
| `protocole-urie.md` | Chantier Urie v2 — vocabulaire, taxonomie, protocole T0-T5 |
| `Referentiel_Urie_v0.xlsx` | Classeur référentiel — compétences, types d'erreur, grille de diagnostic, coûts |

---

## Dette documentaire connue

`README.md` décrit un état du produit antérieur à D-CEO-16 : tableau de validation "à construire", aucune mention de Postgres, des Sheets, de l'authentification ni de Django. C'est le dernier document périmé du projet — `AGENTS.md` et `docs/implementation_plan.md`, qui portaient la même erreur, ont été supprimés au nettoyage du 2026-07-30.
