# Feuille de route — Chantier Urie v2 (suivi structuré)
**Document de pilotage — fait foi pour l'avancement.** `CLAUDE.md` renvoie ici pour le détail ; ce fichier est la seule source de vérité sur "où en est-on" — ne pas dupliquer le suivi ailleurs.

**Dernière mise à jour :** 2026-07-31 (module 2 entamé — gabarit et découpe ; travail versionné sur `chantier/urie-v2-django`)
**Où en est-on (résumé en une ligne) :** Modules 0 et **1 ✅ faits** · **Module 2 🟨 gabarit lu dans le PDF source, 280/280 cadres, découpe et nettoyage faits** — reste le recalage · **Module 6 🟨 le moteur du plan et du palier tourne** · **interface migrée sur Django**. Trois choses bloquent, toutes hors code : une **copie scannée** (module 2), les **209 corrigés** (arbitrage B), et un **essai réel de bout en bout** avant de retirer Streamlit. Le **Module 3** (corpus de référence) est le seul chantier qui avance sans rien attendre.

**État vérifié le 2026-07-31 : 204 tests Django + 242 pytest = 446 tests passent.**

**Pour reprendre le travail sur Django :**
```bash
DEBUG=true DATABASE_URL="sqlite:///:memory:" python manage.py test         # les 170 tests Django
DEBUG=true python manage.py importer_referentiel --a-blanc                 # contrôle sans écriture
DEBUG=true python manage.py runserver                                      # admin sur /admin/
DEBUG=true python manage.py verifier_installation                          # contrôle avant mise en service
```
Note : `DATABASE_URL` suit la convention SQLAlchemy — `sqlite:///:memory:`, **trois** barres.

> ⚠️ **Le manque qui pèse encore — détail dans `docs/harmonisation_donnees.md`.** Le référentiel ne contient **aucune bonne réponse** pour les 209 questions non-QCM — manque non signalé par `guide-urie.md`, qui bloque les modules 3 à 9. Les champs sont en place et vides (Module 1 fait), donc aucune migration corrective ne sera nécessaire : il reste à faire **remplir** le lot par le relecteur pédagogique.
>
> Arbitrages rendus : **A** (archivage), **D** (barème /20), **G** (source = le classeur). En attente : **B** (corrigés), **C** (curriculum RAG), **E** (volumes lycée), **F** (format `construction`).

---

## Comment reprendre le travail (lire ceci en premier, à chaque session)

1. Lire la ligne "Où en est-on" ci-dessus.
2. Lire les 3 dernières entrées du **Journal de bord** (fin de ce document) — elles disent ce qui a été fait, ce qui a été décidé, et ce qui bloquait à la fin de la dernière session.
3. Ouvrir le module marqué 🟨 (en cours) dans le tableau ci-dessous, ou le premier ⬜ si aucun n'est en cours. Reprendre à la première sous-tâche non cochée.
4. Avant de coder quoi que ce soit sur ce chantier : relire `protocole-urie.md`, `guide-urie.md`, et la section "Chantier en cours" de `CLAUDE.md`.
5. **À la fin de la session** (même partielle) : cocher les sous-tâches faites, mettre à jour le statut du module concerné, mettre à jour la ligne "Où en est-on", et ajouter une entrée au Journal de bord. Un module qui progresse sans que ce fichier soit mis à jour est une session perdue pour la suivante.

---

## Vue d'ensemble

| # | Module | Statut | Bloqué par |
|---|---|---|---|
| 0 | Appropriation du référentiel | ✅ Fait (2026-07-30) | — |
| 1 | Socle de données (Neon, Django) | ✅ Fait (2026-07-30) | — |
| 2 | Lecture des copies par zones | 🟨 En cours (2026-07-31) — gabarit et découpe faits | Un **sujet Urie** imprimé, rempli et scanné, pour le recalage |
| 3 | Corpus de référence | 🟨 En cours (2026-07-31) — outil de tagage prêt | 5 copies à réunir (1/5) |
| 4 | Diagnostic contraint | ⬜ À faire | Module 2, Module 3 |
| 5 | Composition du test de confirmation (T1) | ⬜ À faire | Module 4 |
| 6 | Palier et plan de remédiation | 🟨 En cours (2026-07-30) — moteur fait, séances à planifier | Module 4 pour l'alimenter en vrais problèmes |
| 7 | Génération des fiches | ⬜ À faire | Module 6 |
| 8 | Interfaces de saisie | 🟨 Amorcé — admin sur les 11 tables + écran de parcours/inscription | Module 1 (peut démarrer en parallèle dès que le socle existe) |
| 9 | Restitution et indicateurs | ⬜ À faire | Module 1, 6, 7, 8 |

Légende : ⬜ à faire · 🟨 en cours · ✅ fait · 🔴 bloqué (voir colonne "Bloqué par" ou Journal)

---

## Jalons de validation (go/no-go — ne pas franchir sans eux)

- **Avant le Module 4 en conditions réelles :** Module 3 doit avoir produit au moins 5 copies entièrement taguées et marquées corpus de référence.
- **Avant tout déploiement du Module 4 auprès d'un enseignant :** 100 sorties consécutives valides (aucun code hors référentiel) + écart mesuré et consigné entre le diagnostic automatique et le tagage manuel du corpus.
- **Avant de couper l'ancien diagnostic texte libre pour un niveau donné :** le Module 4 doit être validé sur ce niveau précis (le remplacement se fait niveau par niveau, pas globalement — voir `CLAUDE.md`).
- **Avant toute perspective commerciale institutionnelle :** point ouvert #4 ci-dessous (données personnelles de mineurs) doit être traité, pas seulement noté.

---

## Détail par module

### Module 0 — Appropriation du référentiel ✅ **FAIT (2026-07-30)**
**Objectif :** savoir lire le classeur avant d'écrire la moindre ligne de code qui s'en sert.

- [x] Parcourir les 9 onglets de `Referentiel_Urie_v0.xlsx` dans l'ordre, en commençant par `00_Notice`.
- [x] Prendre le test d'entrée en 3ème, choisir 3 questions (dont ≥1 QCM) → **L5** (QCM), **L7** (court), **G13** (rédigé, partie B).
- [x] Pour chacune, retrouver : compétence canonique, signatures d'erreur, types d'erreur des distracteurs, coût de remédiation.
- [x] Répondre à la question de contrôle.

**Réponse à la question de contrôle** — *un élève coche l'option a) à la question L5 du test de 3ème :*
> L5 = « Développer (2x−3)² », format QCM, compétence canonique **`L.IDR`** (Identités remarquables : développement, introduite en 4ème, volume officiel 2 h).
> Option a) = `4x² + 9` → `06_Distracteurs` la tague **`CPT`** (« oubli complet du double produit : (a−b)² traité comme a²+b² »).
> **Problème à créer : `L.IDR × CPT`**, en état `hypothese`, avec sa ligne dans `transition`.
> **Coût : 0,5 h** (`08_Cout_remediation` : 2 h × 0,35 = 0,7 h → arrondi à la demi-heure = 0,5 h).
> Aucun appel LLM n'est nécessaire : la lettre cochée suffit.

**Vérifications d'intégrité effectuées sur le classeur (utiles au module 1 — l'import peut compter dessus) :**
- 280 questions = 7 tests × 40, toutes rattachées à une compétence existante (0 code inconnu).
- 1031 signatures, 280/280 questions couvertes, 3 à 4 signatures par question ; 0 type d'erreur inconnu, 0 compétence inconnue.
- 284 options QCM, 0 type d'erreur inconnu.
- `07_Couverture` : 116 lignes, **écart = 0 partout**.
- Règle du protocole « RED uniquement en partie B » : **respectée** (68/68 signatures RED en partie B).
- Répartition des signatures : CPT 345 · PRC 233 · CNS 134 · ATT 101 · PRQ 92 · RED 68 · MOD 58.
- Le piège des codes locaux est réel et vérifié : `N-a` désigne **7 compétences canoniques différentes** selon le test (N.NUM en 6ème, N.DIVIS en 4ème, N.ENS en 3ème, N.RAC/N.PUI/N.VAB en 1ereD/tleD…). Un code local peut aussi pointer vers **plusieurs** codes canoniques (`L-a → L.DEV1 ; L.IDR`).

**Trois points remontés (à trancher par l'utilisateur / le docteur, pas par l'implémentation) :**
1. **`08_Cout_remediation` contient 444 = 74 × 6 lignes, pas 101 × 7.** Deux exclusions structurelles, toutes deux légitimes mais qui doivent être gérées explicitement dans le code : `ATT` n'a **aucune** ligne de coût (non remédiable, coefficient 0) — le module 6 doit traiter `ATT` comme coût 0, **pas** comme « ligne manquante = erreur » ; et les **27 compétences du lycée** (15 en 2ndeC, 12 en 1ereD) ont un volume horaire `"non disponible"` et donc aucun coût — un problème diagnostiqué sur une compétence de lycée **ne peut pas être chiffré aujourd'hui**, ce qui bloque le calcul de palier (module 6) pour ces niveaux. C'est le point ouvert #2 ci-dessous, mais son impact concret est plus large qu'annoncé : il ne dégrade pas seulement la précision, il empêche le palier A/B/C d'être calculé pour un élève de 2ndeC ou 1ereD.
2. **Un 4ème format de question existe : `construction` (7 questions).** `guide-urie.md` (module 2) ne décrit que 3 formats de cadre (QCM 1 ligne, court 2 lignes, rédigé 8 lignes). Les 7 questions `construction` (toutes en partie B, barème 3, une par niveau de la 6ème à la 3ème) attendent un **tracé géométrique** (règle/compas), pas du texte. Le module 2 doit prévoir ce cas, et le module 4 ne pourra vraisemblablement pas le diagnostiquer automatiquement — à orienter vers la saisie humaine (module 8).
3. **`ATT` apparaît 2 fois en partie B** alors que le protocole présente l'inattention comme un phénomène de partie A (99 des 101 signatures ATT y sont). Anomalie mineure, sans doute volontaire — signalée pour mémoire, ne bloque rien.

**Critère de fin :** ✅ atteint — la question de contrôle a une réponse immédiate et tracée jusqu'au classeur.
**Fichiers concernés :** aucun (exercice manuel, aucun code produit).

---

### Module 1 — Socle de données (Neon/Postgres)
**Objectif :** les 11 tables du guide, greffées sur la base Postgres existante — pas de SQLite séparée (décision actée, voir `CLAUDE.md`).

> **Prérequis : lire `docs/harmonisation_donnees.md`.** Arbitrages A et D rendus (archivage fait, barème /20). Prévoir dès la première version les colonnes `question.reponse_attendue` et `question.solution`, même vides — les ajouter après coup coûterait une migration supplémentaire (arbitrage B encore en attente, mais le schéma ne doit pas l'attendre).

- [ ] **Barème sur 20** (décision D) : `question.bareme` en `Numeric(8,4)`, converti à l'import par `bareme_classeur / 3` (partie A → 0,3333 ; partie B → 1,0).
- [ ] **Règle de calcul du score, à appliquer partout :** la note se calcule contre la **somme réelle des `max_score`**, jamais contre un total déclaré en métadonnée. C'est la condition pour qu'une copie parfaite vaille exactement 20/20 malgré les tiers de point — et c'est aussi le correctif du bug §5.1 de `harmonisation_donnees.md`.
- [ ] Ajouter dans `src/db/models.py` les modèles SQLAlchemy des 4 tables référentiel : `Competence`, `Prerequis`, `TypeErreur`, `CoutRemediation`.
- [ ] Ajouter les 3 tables banque de questions : `Question`, `SignatureErreur`, `OptionQcm`.
- [ ] Ajouter les 4 tables suivi : `SessionUrie` (nom retenu pour éviter l'ambiguïté avec la session Streamlit), `Evaluation` (FK nullable vers `Copie.copy_id`), `Reponse`, `Probleme`, `Transition`, `Seance` — soit 6 tables, pas 4 (le guide en compte 7 dans ce groupe en réalité : eleve/session/evaluation/reponse/probleme/transition/seance ; `eleve` est *exclue* ici puisque l'identité reste dans les Sheets, D-CEO-20).
- [ ] Contraintes en base : `evaluation.type` ∈ {T0..T5}, `probleme.etat` ∈ {hypothese, confirme, ecarte, en_remediation, resolu, non_resolu, regresse, clos}, `session_urie.palier` ∈ {A, B, C} — via `Enum` Postgres natif ou `CheckConstraint`.
- [ ] Générer et relire la révision Alembic (`alembic revision --autogenerate`, suite de `f8928cd01df9`).
- [ ] **Si un `Enum` Postgres natif est utilisé :** vérifier que le `downgrade()` fait `DROP TYPE` explicitement (piège déjà rencontré en D-CEO-20/21 — un simple `drop_table` ne suffit pas).
- [ ] Tester le cycle complet `alembic downgrade base` → `alembic upgrade head` (comme fait systématiquement dans les migrations précédentes du projet).
- [ ] Écrire `import_referentiel.py` (racine ou `scripts/`, pattern idempotent de `seed_users.py`) : lit les 9 onglets via `openpyxl`, upsert les 7 tables référentiel + banque de questions par code (clé stable).
- [ ] Faire tourner l'import contre le classeur réel, vérifier les compteurs (101 compétences, 7 types d'erreur, 280 questions, 1031 signatures, 284 options QCM, 444 coûts).

**Critère de fin :** l'import remplit les 7 tables référentiel/banque de questions sans erreur ; un élève fictif peut être suivi de T0 à T5 avec toutes ses transitions enregistrées (test manuel ou script jetable).
**Fichiers concernés :** `src/db/models.py`, `migrations/versions/<nouvelle>.py`, `import_referentiel.py` (nouveau).

---

### Module 2 — Lecture des copies par zones 🟨 **EN COURS (2026-07-31) — gabarit et découpe faits**
**Objectif :** transformer un sujet rempli et scanné en une liste `(code_question, image_de_la_réponse)`.

> **Écart assumé avec `guide-urie.md`, et c'est le point de conception du module.** Le guide prescrit de *détecter* les rectangles sur le scan puis de lire au **OCR** le code de chaque cadre. Inutile : les 7 sujets sont produits par WeasyPrint et leur PDF **porte déjà** la position exacte de chaque cadre et son code. Le gabarit est donc lu à la source, pas deviné sur le scan. Ça supprime l'étape la plus fragile de la chaîne — un OCR sur trois caractères à 150 DPI aurait été le premier point de panne, et une confusion `G1`/`G7` aurait attribué une réponse à la mauvaise question **sans que rien ne le signale**. Il ne reste qu'un seul problème à résoudre sur le scan : le recalage.

- [x] **Gabarit extrait du PDF source** (`extraire_gabarit`) : code, page, rectangle, format et nombre de lignes de chaque cadre. **Vérifié 280/280 sur les 7 sujets**, 0 manquant, 0 en trop, 0 doublon.
- [x] **Règles de lecture exprimées en plages, pas en constantes relevées** (D-CEO-35) : plages de gris et fractions de la largeur de page, au lieu de l'égalité à 0,478431 / 480 pt / 8 lignes. Le sujet est un document vivant — régénéré, il changera de marges et de teintes, et une égalité stricte aurait fait échouer la lecture **totalement** (zéro cadre trouvé), pas partiellement. Au-delà de 2 lignes de guidage, la question est rédigée, qu'il y en ait 6, 8 ou 10.
- [x] Le format se **déduit de la géométrie** (1 ligne = `qcm`, 2 = `court`, ≥3 = `redige`, 0 ligne = `construction`) et n'est pas lu dans le barème — les deux sont ensuite confrontés (`verifier_gabarit`). C'est le garde-fou contre un sujet d'une autre version que celle chargée en base : les codes ou les formats divergent, et on le sait **avant** d'attribuer des réponses aux mauvaises questions.
- [x] Découpe de l'intérieur du cadre (`decouper_zones`), une image PNG par code, échelle déduite de l'image (aucune hypothèse de résolution).
- [x] Suppression des lignes de guidage par seuillage — blanchiment plutôt que binarisation franche, pour qu'un trait de crayon clair reste lisible.
- [x] **Le code typographié est effacé de la zone découpée.** Il est imprimé en noir dans le coin du cadre : le seuillage ne peut pas l'écarter, et le laisser ferait passer pour remplie une zone restée vierge. Sa position exacte vient du PDF, comme le reste.
- [x] Détection des zones **vierges** (`vide`, `taux_encre`) — « pas de réponse » est une donnée de diagnostic à part entière, et ça évite d'envoyer une image blanche au modèle.
- [x] Les **4** formats sont gérés, pas 3 : `qcm` (71), `court` (139), `redige` (63) et `construction` (7, non prévu par `guide-urie.md`).
- [x] **Le scan se fait hors plateforme** — ce qui entre est un PDF multipage ou des images. `resolution_scan()` donne la définition native de la source pour ne pas rendre un scan 200 DPI dans une image 150 DPI, et `ingest_pdf(dpi=…)` accepte désormais la résolution voulue (150 reste le défaut, D-CEO-10).
- [x] **Garde-fou : un scan brut passé à la découpe est refusé.** Les proportions d'un scan ne sont pas celles du sujet (mesures ci-dessous) ; découpé tel quel le décalage atteint plusieurs millimètres en bas de page — assez pour attraper la ligne de la question voisine, pas assez pour que le résultat ait l'air faux.
- [x] **Seuil d'encre confronté à un scan réel** : `SEUIL_ENCRE_DEFAUT = 140` tombe au milieu d'un large plateau (la proportion de pixels sombres ne bouge que de 1,85 % à 3,47 % entre les seuils 120 et 200). Réglage non critique tant que le scan n'est pas sous-exposé.
- [ ] 🔴 **Risque ouvert — le seuillage pourrait ne pas suffire à effacer les lignes de guidage.** Sur le scan réel, l'écriture de l'élève ressort intacte (l'objectif est atteint de ce côté) mais **les lignes pointillées imprimées survivent au seuil**. Elles sont imprimées en noir, pas en gris pâle. Or une imprimante laser rend un aplat gris 0,749 par un **tramage de points noirs**, pas par un gris uniforme : une fois imprimées puis scannées, les lignes de guidage des sujets Urie pourraient se comporter comme ces pointillés et non comme le 191 uniforme du PDF. **Se tranche en une manipulation** : imprimer un sujet Urie, le scanner vierge, mesurer le niveau de gris des lignes. Si le tramage est confirmé, l'effacement devra s'appuyer sur la **position connue** des lignes (elle est dans le gabarit) plutôt que sur leur clarté.
- [ ] **Reste — recalage du scan sur le gabarit** (translation, échelle, rotation), **par page**. Demande une copie d'un **sujet Urie** imprimée et scannée : le scan reçu est d'un test de l'ancien format, sans cadres ni codes, il n'y a aucun gabarit sur lequel le recaler.
- [ ] **Reste** — décider du traitement du format `construction` : la zone se découpe comme les autres, mais le diagnostic automatique n'est vraisemblablement pas atteignable dessus → orientation vers la saisie humaine (module 8).
- [ ] **Reste** — point d'insertion dans `src/pipeline/` : nouvelle étape avant la transcription actuelle, déclenchée pour les seuls tests à cadres ancrés (les tests archivés gardent la transcription pleine page).

**Critère de fin :** sur un sujet rempli et scanné, les 40 cadres sont détectés, correctement associés à leur code de question, et découpés proprement.
**Fichiers concernés :** `src/pipeline/zones.py`, réutilise `src/pipeline/ingestion.py` pour la conversion 150 DPI.
**Tests :** `tests/test_zones.py` (20) — 13 sur un sujet fabriqué dans le test, 7 sur les vrais sujets (ignorés si les PDF sont absents, ils ne sont pas versionnés).

**⚠ Ce qu'il faut pour finir ce module :** un **sujet Urie** (`Test_diagnostique_entree_*.pdf`) imprimé, rempli à la main, et scanné. Consignes d'impression sur `/sujets/` : noir et blanc, recto seul, **sans réduction**. Un scan d'un test de l'ancien format ne peut pas servir : sans cadres ancrés ni codes, il n'y a pas de gabarit sur lequel recaler.

#### Ce qu'un scan réel a appris (mesuré le 2026-07-31 sur `TEST 4 3e.pdf`, HP Scan, 200 DPI, 12 pages)

| Mesure | Valeur | Ce que ça impose |
|---|---|---|
| Taille de page | 612 pt de large, hauteur **variable de 835 à 851 pt d'une feuille à l'autre du même fichier** | Le recalage ne peut pas s'appuyer sur le rectangle de la page. Il doit s'ancrer sur le **contenu** — les cadres eux-mêmes — et se faire **page par page**. |
| Inclinaison | −1,25° · −1,25° · +1,00° selon la page | Redressement **par page**, jamais global. |
| Papier / encre | papier à 254, distribution franchement bimodale | Seuil d'encre non critique (plateau 120–200). |
| Couleur de l'encre | 75 % des pixels sombres = imprimé (neutre), 22 % = stylo bleu (élève), 2,3 % = **rouge (correction de l'enseignant)** | Sur les copies déjà corrigées à la main, la correction du professeur est **séparable par la couleur**. Sans ce tri, un diagnostic lirait la correction de l'enseignant comme la production de l'élève. Compte surtout pour le **module 3** (corpus constitué d'anciennes copies). |
| Nombre de pages | 12 pages pour un sujet qui en compte 10 (page de garde + page de renseignements) | L'appariement page scannée ↔ page du sujet ne peut pas être supposé 1:1. À traiter avec le recalage. |

---

### Module 3 — Corpus de référence 🟨 **EN COURS (2026-07-31) — l'outil de tagage est prêt**
**Objectif :** un jeu de copies taguées à la main pour mesurer objectivement le Module 4.

- [x] **Marquer les copies du corpus** — `Evaluation.corpus_reference`, avec `tague_par` et `date_tagage`. Une contrainte en base refuse un marquage sans auteur ni date : on ne saurait ni qui interroger sur un tagage discutable, ni à quelle version du référentiel il se rapporte. *(Le module 1 avait laissé ce point « à définir ».)*
- [x] **Deux champs ajoutés à `Probleme`**, dont le module 4 a besoin autant que le module 3 : `evaluation_origine` (la passation qui a révélé le problème) et `justification` (ce qu'on a lu sur la copie). La justification est ce qui rend un désaccord entre le corpus et le module 4 **arbitrable**, au lieu d'un simple écart de comptage.
- [x] **Outil de saisie : `manage.py taguer_corpus --fichier …`** (arbitrage rendu : un fichier YAML plutôt qu'un écran — le tagage est lent et discutable, un fichier se relit, se compare et se reprend le lendemain ; un formulaire perd tout à la première fermeture d'onglet). Options `--a-blanc` et `--remplacer`.
- [x] **Validation complète avant toute écriture** : aucun code inventé, justification obligatoire, `ATT` non confirmable, couple en double refusé. Un corpus à moitié écrit serait pire que pas de corpus — il aurait l'air complet.
- [x] Rassembler ≥5 anciennes copies d'élèves Hakili Lab — **5 réunies** (2 en 3ème, 2 en 5ème, 1 en 6ème).
- [ ] Taguer les 5 copies — **3 sur 5 faites** (`corpus_3e_01`, `corpus_3e_02`, `corpus_5e_03`). Restent 1 copie de 5ème et 1 de 6ème.
- [x] **Outil durci après trois copies** (voir le journal du 2026-07-31) : consultation du référentiel pendant le tagage, libellés rappelés au compte rendu, codes proches suggérés, contrôle de niveau, étanchéité avec le suivi réel, `manage.py corpus` pour relire l'étalon, rapport d'hésitations.
- [ ] **Deux types d'erreur manquent au corpus : `PRQ` et `RED`.** Signalé par `manage.py corpus` — le module 4 ne pourra pas être mesuré sur eux. À chercher explicitement dans les deux dernières copies : `RED` est un résultat juste sans justification (partie B), `PRQ` un échec corrélé sur plusieurs compétences partageant un prérequis.
- [ ] Pour chaque copie : relever chaque réponse fausse, chercher la signature correspondante dans `05_Grille_diagnostic`, noter le problème (`code_competence` + `code_type_erreur`).
- [ ] Enregistrer chaque problème taggé dans les tables du Module 1 (`probleme`, `transition` en état `hypothese` ou directement `confirme` selon le protocole retenu pour le tagage manuel).
- [ ] Noter chaque cas d'hésitation et pourquoi — ce sont des défauts potentiels du référentiel, à remonter à l'utilisateur (pas à corriger seul, cf. `CLAUDE.md` "ce qui n'est pas de ton ressort").
- [x] Marquer explicitement ces copies comme « corpus de référence » — fait, voir ci-dessus.

**Critère de fin :** au moins 5 copies entièrement taguées en base et marquées comme corpus de référence.
**Fichiers concernés :** `suivi/models.py` (marqueur + `evaluation_origine`, `justification`), `suivi/management/commands/taguer_corpus.py`, `referentiel/couts.py` (`cout_precalcule`), `data/corpus/exemple.yaml`.
**Tests :** `suivi/tests_corpus.py` (16).

**⚠ Une règle à ne pas enfreindre plus tard :** le module 4 **ne doit jamais écrire** dans les problèmes d'une évaluation marquée `corpus_reference`. La mesure se fait en comparant sa sortie à ces problèmes, pas en les mettant à jour — un étalon qu'on corrige au fur et à mesure ne mesure plus rien.

**⚠ Ce que le corpus ne peut pas porter pour une copie de l'ancien format.** `Reponse` exige une clé étrangère vers les 280 questions Urie : une copie de l'ancien format n'en a aucune, donc **aucune `Reponse` n'est enregistrable** pour elle. Seuls les `Probleme` le sont — et c'est suffisant, puisque le problème est précisément l'unité que le module 4 produit et contre laquelle il sera mesuré.

---

### Module 4 — Diagnostic contraint
**Objectif :** remplacer le rapport en texte libre par une liste de problèmes structurés.

- [ ] Définir le format de sortie structuré strict : `(code_competence, code_type_erreur, citation)`, rien d'autre.
- [ ] Fournir au modèle les signatures d'erreur de la question concernée (`signature_erreur`) — le modèle reconnaît, ne devine pas.
- [ ] Implémenter le rejet + nouvelle demande si la sortie ne respecte pas le format ou utilise un code inconnu du référentiel.
- [ ] Court-circuiter entièrement le modèle pour les QCM : lettre cochée → `option_qcm` → type d'erreur directement, aucun appel LLM.
- [ ] Écrire chaque problème produit dans `probleme` (état `hypothese`) + sa ligne dans `transition`.
- [ ] Décider du point d'intégration dans le pipeline existant : remplace l'appel `DiagnosticResult` texte libre, mais **seulement pour les niveaux couverts par le référentiel** (voir décision actée dans `CLAUDE.md`) — prévoir la bascule conditionnelle par niveau/test.
- [ ] Faire tourner sur les copies du corpus de référence (Module 3), comparer au tagage manuel, mesurer et consigner l'écart.
- [ ] Atteindre 100 sorties consécutives valides (aucun code hors référentiel) avant tout déploiement réel.

**Critère de fin :** 100 sorties consécutives valides + écart diagnostic automatique / tagage manuel mesuré et consigné (jalon de validation ci-dessus).
**Fichiers concernés :** `prompts/` (nouveau prompt diagnostic contraint), `src/api/*_client.py` (fonction dédiée), `src/pipeline/pipeline.py` (point de bascule par niveau).

---

### Module 5 — Composition du test de confirmation (T1)
**Objectif :** générer automatiquement un T1 qui départage les hypothèses, pas un T0 raccourci.

- [ ] Pour chaque problème en état `hypothese`, générer une question qui sépare deux causes possibles du même échec (ex. exécution simple vs lourde pour distinguer `CPT` de `PRC`).
- [ ] Rejeter toute question qui ne discrimine rien.
- [ ] Produire le sujet T1 au même format PDF que les tests d'entrée (cadres de réponse ancrés par code), pour que le Module 2 puisse le relire.
- [ ] À l'issue de T1, faire passer chaque problème à `confirme` ou `ecarte`, avec sa transition enregistrée.

**Critère de fin :** à partir d'une liste de problèmes en hypothèse, le module génère un sujet T1 imprimable dont chaque question est reliée à l'hypothèse qu'elle tranche.
**Fichiers concernés :** nouveau générateur (`src/pipeline/` ou module dédié), réutilise le moteur de génération PDF existant (`pdf_report_html.py` / équivalent).

---

### Module 6 — Palier et plan de remédiation 🟨 **EN COURS (2026-07-30) — moteur fait**
**Objectif :** passer des problèmes confirmés à un plan de travail chiffré.

- [x] Additionner les coûts (`cout_remediation`) des problèmes en état `confirme` pour une session donnée — `Session.cout_total_confirme`.
- [x] Traiter `ATT` comme coût **0**, pas comme une ligne manquante : `08_Cout_remediation` ne contient aucune ligne `ATT` par construction (non remédiable). `Probleme.cout_estime` vaut 0 par défaut, et le modèle refuse par ailleurs qu'un `ATT` soit confirmé ou remédié.
- [x] Gérer l'absence de coût pour les 27 compétences de lycée — **résolu par D-CEO-29** : volume de repli de 4 h, marqué `volume_estime` / `estime` pour qu'une valeur dérivée ne passe jamais pour un chiffre officiel. `CoutRemediation` passe de 444 à 606 lignes, le palier redevient calculable en 2ndeC/1ereD.
- [x] Déterminer le palier : A (<8h), B (8-20h), C (>20h — le dire clairement, ne pas proposer de plan voué à l'échec) — `Session.calculer_palier()`, et `inscrire()` **refuse** le palier C sans dérogation motivée et tracée (D-CEO-34).
- [x] Ordonner le plan selon le graphe des prérequis (`prerequis`) — tri topologique par couches dans `suivi/plan.py`, départagé à égalité par le niveau d'introduction (le plus fondamental d'abord). Un cycle dans le graphe ne fait pas boucler.
- [x] Écran de restitution : `/parcours/<jeton>/` affiche le plan ordonné, le volume, le palier, les hypothèses restantes et le bouton d'inscription (POST seulement).
- [ ] **Reste :** dérouler le plan en **séances** (`Seance` existe en base et dans l'admin, rien ne la remplit encore) — c'est ce qui manque au critère de fin.
- [ ] **Reste :** validation sur des données réelles — le moteur n'a encore tourné que sur des problèmes créés à la main, faute de Module 4.

**Critère de fin :** pour une session donnée, le module produit un plan ordonné, un coût total, un palier, et une séquence de séances respectant l'ordre des prérequis.
**Fichiers concernés :** `suivi/plan.py` (calcul), `suivi/models.py` (`calculer_palier`, `inscrire`), `suivi_web/views.py` + `templates/suivi_web/session_detail.html` (restitution), `referentiel/couts.py` (formule de coût).
**Tests :** `suivi/tests_plan.py` (12) + les tests de parcours de `suivi_web/tests.py`.

---

### Module 7 — Génération des fiches
**Objectif :** une séance prête à l'emploi pour le tuteur, pas de la matière première.

- [ ] Unité de fiche = compétence × type d'erreur (pas le chapitre).
- [ ] Contenu obligatoire : objectif en termes de compétence, prérequis à vérifier en ouverture, déroulé minuté, exercices gradués, critère de réussite observable.
- [ ] Génération à la demande, pour les problèmes réellement confirmés.
- [ ] Versionnement : la version corrigée par le tuteur remplace la version générée dans le catalogue.

**Critère de fin :** une fiche générée est utilisable en séance sans retouche par un tuteur qui découvre le dossier.
**Fichiers concernés :** nouveau générateur + stockage versionné (table à ajouter au Module 1 si pas déjà prévu, ou réutilisation de `document` avec un nouveau `type`).

---

### Module 8 — Interfaces de saisie 🟨 **AMORCÉ**
**Objectif :** deux écrans, pas davantage, intégrés à l'app existante.

- [ ] Écran 1 : saisie/correction des réponses d'une évaluation, copie découpée affichée à côté du champ. *(dépend du Module 2 pour la découpe ; le tableau de validation du pipeline existant en couvre déjà la moitié)*
- [ ] Écran 2 : fiche de séance tuteur, 5 champs (problèmes travaillés, blocage, déblocage, travail donné, appréciation), utilisable au téléphone en moins de 2 minutes.
- [x] Réutiliser l'auth déjà en place plutôt que créer un nouveau système d'accès — fait côté Django (`comptes/`, décorateurs `connexion_requise` / `admin_requis`), et non plus dans `src/ui/app.py`.
- [x] Acquis en chemin, à ne pas refaire : l'**admin Django sur les 11 tables** couvre la consultation et la correction ponctuelle, et l'écran `/parcours/<jeton>/` porte déjà l'inscription au programme.

**Critère de fin :** un tuteur remplit une fiche de séance depuis son téléphone en moins de 2 minutes ; une évaluation complète peut être corrigée à l'écran sans manipuler de fichier.
**Fichiers concernés :** `src/ui/app.py` (nouveaux onglets/vues).

---

### Module 9 — Restitution et indicateurs
**Objectif :** les deux documents qui donnent sa valeur au produit.

- [ ] Rapport de fin de remédiation (parents) : 2 pages, problèmes ouverts/résolus/restants, travail effectué.
- [ ] Tableau de bord interne, 5 indicateurs calculés depuis `transition` :
  - [ ] Taux de résolution à T3 (résolus / confirmés)
  - [ ] Taux de rétention à 45 jours (T4)
  - [ ] Taux de rétention à long terme (T5)
  - [ ] Taux de confirmation à T1 (confirmés / hypothèses) — sain entre 60 et 80%
  - [ ] Écart durée estimée / durée réelle par type d'erreur (recalibrage futur des coefficients)
- [ ] Réutiliser le moteur PDF existant (`pdf_report_html.py`) pour le rapport parents.
- [ ] Réutiliser le pattern de tableau de bord déjà validé (`src/core/tendance.py`, D-CEO-23) pour l'affichage des indicateurs.

**Critère de fin :** les deux documents se génèrent depuis la base sans aucune retouche manuelle.
**Fichiers concernés :** `src/pipeline/pdf_report_html.py` (nouveau template), `src/ui/app.py` (nouvel onglet indicateurs).

---

## Points ouverts (hérités de `protocole-urie.md` §12 — à ne pas perdre de vue)

1. **Extension au-delà des maths** — quelles matières, dans quel ordre, taxonomie transposable ou non. Non tranché.
2. **Volumes horaires du lycée manquants** — ✅ **traité par D-CEO-29 (repli de 4 h), reste à confirmer par le terrain.** 74/101 compétences ont un volume officiel ; les 27 compétences de lycée (15 en 2ndeC, 12 en 1ereD) reçoivent 4 h — la médiane des volumes réels du collège — ce qui rend le palier de nouveau calculable sur ces niveaux (`CoutRemediation` : 444 officiels + 162 estimés = 606). **C'est une estimation et elle est marquée comme telle** (`volume_estime`, `estime`, mention orange dans l'admin, signalement `repose_sur_estimation` dans le plan) ; le classeur source continue d'indiquer « non disponible ». Reste à obtenir les vrais volumes — le remplacement sera trivial, et la feuille `04_Volumes_lycee` du lot à compléter le demande (arbitrage E).
3. **Tarification** — à poser avant toute mise à l'échelle. Non tranché, pas du ressort technique.
4. **Données personnelles de mineurs** — obligations à vérifier auprès de la CIL du Burkina Faso, consentement parental à prévoir dès le premier élève suivi dans ce dispositif. **Bloquant pour toute perspective commerciale institutionnelle.**
5. **Validation pédagogique** — le référentiel doit être relu par un enseignant de mathématiques avant d'être figé (`00_Notice` du classeur le dit déjà : "A VALIDER").
6. **Recalibration** — réviser les coefficients de coût après 20 sessions closes (dépend du Module 9, indicateur écart durée estimée/réelle).

---

## Lot à faire compléter par le relecteur pédagogique

Quatre manques du référentiel demandent tous un enseignant de mathématiques — et tombent dans le même passage que la validation pédagogique déjà exigée par `00_Notice` (« À VALIDER »). Ils ont été rassemblés en **un seul classeur pré-rempli**.

```bash
python scripts/generer_lot_a_completer.py       # produit Lot_a_completer_<date>.xlsx
# … le relecteur remplit les colonnes sur fond crème …
python scripts/integrer_corriges.py --lot ../Lot_a_completer_<date>.xlsx
python scripts/generer_baremes_urie.py          # les corrigés sont repris
```

| Feuille | Contenu | Arbitrage |
|---|---|---|
| `01_Corriges` | **209 questions sans réponse attendue** — le plus important | B |
| `02_Accents` | 150 mots à réaccentuer | — |
| `03_Accents_a_arbitrer` | 16 mots ambigus (« calcule » ou « calculé » ?) | — |
| `04_Volumes_lycee` | 27 compétences sans volume horaire | E |
| `05_Questions_construction` | 7 questions attendant un tracé : que vérifier ? | F |

**Le point de conception qui compte :** les corrigés saisis vont dans `data/knowledge/corriges_urie.yaml`, **séparé des barèmes**. `generer_baremes_urie.py` régénère les barèmes depuis le classeur source et les écraserait s'ils y étaient stockés — plusieurs heures de travail d'enseignant perdues au premier `git pull` suivi d'une régénération. Le générateur fusionne ce fichier séparé à chaque exécution.

**Vérifié** par un aller-retour complet avec un lot d'essai : saisie → réintégration → régénération, les corrigés survivent. L'anomalie « démarche saisie sans réponse attendue » est détectée et signalée (c'est la réponse qui sert à corriger, pas la démarche). Données d'essai supprimées après vérification.

Les feuilles 02 à 05 ne sont **pas** réinjectées automatiquement : elles corrigent le classeur source, qui appartient au docteur. Le script rapporte ce qui a été rempli pour qu'on sache quoi reporter.

---

## Rapprochement curriculum ↔ compétences (arbitrage C)

```bash
python scripts/rapprocher_curriculum.py --lot     # analyse + classeur à valider
python scripts/integrer_rapprochement.py --lot ../Lot_rapprochement_curriculum_<date>.xlsx
```

Écrit un `code_competence` dans chaque leçon des `curriculum_*.yaml` : le module 7 pourra alors retrouver le contenu pédagogique d'un problème `compétence × type d'erreur` sans jointure supplémentaire.

| Feuille | Lignes | Ce qu'on attend |
|---|---|---|
| `01_A_confirmer` | 31 | Proposition nette — un coup d'œil, O ou N |
| `02_A_trancher` | 85 | Ambigu — à décider une par une |
| `03_Sans_proposition` | 5 | Code, **ou « AUCUNE »** si le référentiel ne couvre pas la notion |
| `04_Competences_sans_lecon` | 76 | Pour information (dont 27 de lycée, hors couverture du curriculum) |
| `05_Notions_non_couvertes` | 5 | Lacunes constatées du référentiel — décision de fond |

### Trois constats qui valent plus que le rapprochement lui-même

**1. Quatre notions enseignées n'ont aucune compétence.** Vérifié par recherche exhaustive dans les libellés **et** les descriptions des 101 compétences : `probabilité`, `angle inscrit`, `similitude / figures semblables`, `variance / écart-type` sont absents. Un élève échouant sur ces notions **ne peut pas être diagnostiqué** aujourd'hui. Ce ne sont pas des échecs de rapprochement : il n'y a rien à rapprocher.

**2. Un décalage de niveau sur l'homothétie.** Le curriculum l'enseigne en 3e ; le référentiel place `G.HOM` (« Transformations du plan ») en 2nde C. L'un des deux se trompe, ou il s'agit de deux notions différentes.

**3. Deux signaux de rapprochement se sont révélés inutilisables**, et c'est documenté dans le script pour qu'on ne les réessaie pas : les **numéros de chapitre** (le curriculum écrit `Ch4` là où le classeur écrit `ch15` pour la même notion — les deux découpages ne coïncident pas) et les **domaines** (2 côté curriculum, 8 côté classeur). Seuls le libellé de leçon et la classe portent de l'information.

### Ce que l'outil fait, et ne fait pas
Il **propose**, il ne décide pas — le rapprochement est un jugement pédagogique. Un premier réglage ne donnait que 17 propositions nettes ; l'examen des cas rejetés a montré qu'ils étaient majoritairement corrects et que le vocabulaire différait systématiquement entre les deux sources (« fonction » contre « application », « fréquence » contre « statistique »). Une table d'équivalences relevée sur pièces — non devinée — a porté les propositions nettes à 31 et réduit les leçons sans candidat de 35 à 5.

Limite structurelle assumée : certaines compétences ont un libellé volontairement large (« Statistique du college », « Transformations du plan ») qui recouvre plusieurs leçons. Aucune ressemblance textuelle ne peut les reconnaître — elles sont signalées comme génériques pour que le relecteur sache qu'un rapprochement large est attendu, plutôt que de conclure à une lacune.

**Vérifié** par un aller-retour complet : acceptation, correction, réponse « AUCUNE », refus sans code de remplacement et code inexistant — les deux anomalies sont détectées et signalées, les curricula restaurés après essai.

---

## Journal de bord

### 2026-07-30 (suite) — Nettoyage, et un bug sérieux qu'il a révélé
- **Nettoyage** : 22 fichiers supprimés (docs périmées, schémas JSON morts, orphelins), 3 bibliothèques retirées. Détail et faux positifs écartés : D-CEO-31.
- **Bug découvert en inventoriant : le RAG était mort sur les 7 nouveaux tests.** `urie_3eme` recevait 0 caractère de contexte programme, contre 2 048 pour un ancien test. Cause : l'ancrage passait par `chunk_ids`, champ que les barèmes générés depuis le classeur n'ont pas. Le pipeline n'échouait pas — il produisait un diagnostic générique, exactement ce que D-CEO-12 qualifie d'inutilisable.
- **Réparé sans attendre l'arbitrage C** : le contexte est reconstruit depuis le référentiel (compétence, chaîne de prérequis sur deux niveaux, signatures propres à la question). Mesuré : 3 490 caractères et 3 lacunes pour trois questions de 3ème. Voir D-CEO-30.
- **Un diagnostic sans ancrage est désormais journalisé en avertissement** — c'est ce silence qui avait laissé le défaut vivre.
- **Vérifié :** 112 tests Django + 218 pytest = **330 tests passent**, et `src/` ne contient toujours aucun import Django.

### 2026-07-30 (suite) — Sujets intégrés au projet
Les 7 PDF ont été déposés dans `data/Documents/`, et les anciens DOCX retirés. Deux conséquences traitées :

- **Les avertissements « DOCX introuvable » sur les tests archivés étaient trompeurs** : leurs sujets ont été refaits, l'absence est normale. Passés en information pour les tests archivés, l'avertissement restant réservé aux cas réellement anormaux. Vérifié que les tests archivés gardent leurs `niveaux` — c'est ce dont dépend la résolution de classe des copies historiques.
- **Les sujets deviennent imprimables depuis l'application** (`/sujets/`). L'élève compose **sur le sujet** : l'enseignant doit pouvoir l'imprimer autant de fois qu'il a d'élèves, sans aller chercher le bon fichier ailleurs — avec le risque de distribuer la mauvaise version. Réservé aux personnes connectées : un sujet d'évaluation diffusé à l'avance perd sa valeur diagnostique. Les tests archivés n'ont pas de sujet et ne sont donc pas distribuables.
- La page rappelle les consignes d'impression qui conditionnent la lecture automatique : noir et blanc, recto seul, **sans réduction** — les cadres doivent garder leur taille, c'est ce qui permettra au module 2 de les détecter.

**Vérifié :** 87 tests Django + 218 pytest = **305 tests passent**.

*Ajouter une entrée à chaque session de travail sur ce chantier — même courte, même si rien n'a été codé. Format : date, ce qui a été fait, décisions prises, ce qui bloque, prochaine étape.*

### 2026-07-30
- Lu `guide-urie.md`, `protocole-urie.md`, exploré `Referentiel_Urie_v0.xlsx` (9 onglets confirmés : 101 compétences, 7 types d'erreur, 280 questions, 1031 signatures, 284 distracteurs, 444 coûts), vérifié le format des nouveaux sujets sur `Test_diagnostique_entree_6eme.pdf` (cadres ancrés confirmés).
- Constaté que `docs/decision_register.md` est à jour et fiable, mais que `CLAUDE.md`/`AGENTS.md`/`README.md` sont périmés (décrivent le tableau de validation enseignant comme "à construire" alors qu'il est implémenté ; ignorent totalement Postgres/Neon, Google Sheets, l'auth par rôle).
- **Décisions actées avec l'utilisateur :** (1) les 11 tables du guide vivent dans Postgres/Neon existant, pas une SQLite séparée ; (2) le diagnostic structuré remplace directement le diagnostic texte libre, niveau par niveau ; (3) `CLAUDE.md` réécrit en place plutôt qu'un nouveau document séparé.
- `Hakili_Lab/CLAUDE.md` réécrit : état réel de l'infra + chantier Urie v2 comme priorité active.
- Ce document (`docs/urie_v2_roadmap.md`) créé comme source de vérité unique pour l'avancement, avec détail des 9 modules, jalons de validation, et ce journal.
- **Bloqué par :** rien techniquement — le Module 0 (appropriation manuelle du référentiel) peut démarrer immédiatement.
- **Prochaine étape :** Module 0, puis Module 1 (migration Alembic).

### 2026-07-30 (suite) — Module 0 terminé
- Parcouru les 9 onglets du classeur. Tracé 3 questions du test de 3ème (L5 QCM, L7 court, G13 rédigé) de bout en bout : `04_Questions` → `05_Grille_diagnostic` → `06_Distracteurs` → `08_Cout_remediation`.
- Question de contrôle répondue : **L5 option a) → problème `L.IDR × CPT` → 0,5 h** (détail et dérivation dans la fiche Module 0 ci-dessus).
- **Intégrité du classeur vérifiée par script : 0 violation.** Aucune question sans compétence, aucune signature avec type/compétence inconnu, aucun distracteur avec type inconnu, `07_Couverture` à écart 0 sur ses 116 lignes, 280/280 questions couvertes par 3-4 signatures. Le module 1 peut écrire un import strict (échec sur code inconnu) sans craindre de faux positifs.
- Piège des codes locaux confirmé empiriquement : `N-a` = 7 compétences canoniques différentes selon le test ; un code local peut aussi pointer vers plusieurs codes canoniques.
- **3 anomalies remontées** (détail dans la fiche Module 0) : (1) `08_Cout_remediation` = 74 × 6, pas 101 × 7 — `ATT` sans ligne de coût par construction, et 27 compétences lycée sans coût, ce qui **rend le palier du module 6 incalculable en 2ndeC/1ereD** ; (2) un **4ème format de question, `construction` (7 questions)**, absent de `guide-urie.md` module 2 — attend un tracé, pas du texte ; (3) `ATT` apparaît 2 fois en partie B, mineur.
- Fiches Module 2 et Module 6 et point ouvert #2 mis à jour en conséquence.
- **Bloqué par :** rien. Les anomalies 1 et 2 demandent un arbitrage utilisateur/docteur mais ne bloquent pas le Module 1.
- **Prochaine étape :** Module 1 — modèles SQLAlchemy, migration Alembic, script `import_referentiel.py`.

### 2026-07-30 (suite) — Investigation harmonisation des données
- Investigation demandée sur l'écart entre les données de test existantes (`Hakili_Lab/data/knowledge/`) et le référentiel Urie v2. Résultat complet : **`docs/harmonisation_donnees.md`**.
- **Résultat central :** les 7 nouveaux PDF et le classeur sont **parfaitement alignés** (280/280 codes de question identiques, intitulés correspondant mot à mot). L'ancien système n'est aligné avec rien : aucun identifiant commun, vocabulaire de compétences en texte libre, ancrage par `chunk_ids` disjoint des codes canoniques, nombre de questions variable (26 à 54 contre 40 systématiques).
- **Manque bloquant découvert, non signalé par `guide-urie.md` :** le référentiel ne contient de bonne réponse que pour les 71 QCM. **209 questions sur 280 (75 %) n'ont aucun corrigé** — la Phase A est impossible dessus, ce qui bloque les modules 3 à 9. L'ancien système, lui, a des corrigés complets et de bonne qualité (format `reponse` + `solution`), transposable comme modèle.
- **Divergence de barème :** classeur sur 60 pts (30 A + 30 B), PDF sur 20 pts. Rapport exactement 3, poids relatifs identiques — conversion mécanique, mais l'échelle de stockage doit être tranchée avant la migration.
- **4 défauts actifs constatés dans l'ancien système** (documentés, non corrigés) : (1) **bug de notation en production** — une copie parfaite donne 20,5/20 au test 3e v1, 18,5/20 au 3e v2, 19,5/20 au tle, à cause du dénominateur `total_possible` divergent de la somme réelle des `max_score` ; (2) `meta.total_questions` faux dans 4 barèmes sur 6 ; (3) `bareme_test_3e.yaml` utilise `score_max` alors que le loader ne lit que `points_originaux` — champ silencieusement ignoré ; (4) **RAG dégradé en silence** : 16 `chunk_ids` cassés, 69/121 chunks jamais utilisés, 38 questions sans ancrage, le tout journalisé en `logger.debug` donc invisible en exploitation.
- **6 arbitrages formulés** (§9 du document) : A archivage des anciens tests · **B production des 209 corrigés — chemin critique** · C sort du curriculum RAG · D échelle de barème · E volumes lycée · F traitement du format `construction`.
- **Bloqué par :** arbitrages B et D à rendre avant d'écrire la migration du Module 1 (le schéma de la table `question` en dépend).
- **Prochaine étape :** décision utilisateur sur les arbitrages, puis Module 1.

### 2026-07-30 (suite) — Arbitrages A et D rendus et appliqués
- **Décision A → A1 : les 6 anciens tests sont archivés.** Appliqué dans `src/knowledge/test_registry.py` : champ `archive: True` sur les 6 entrées du catalogue, nouveau champ `HakiliTest.archive`, `available_tests()` filtre les archivés, `all_tests()` ajouté pour l'historique.
- **Archivage fait sans casser l'historique** — point vérifié avant de coder : `get_test()` continue de résoudre les tests archivés, car `pipeline.py:375` s'en sert pour déterminer la classe d'une copie déjà corrigée (`_apply_extracted_classe`). Les retirer du catalogue aurait dégradé silencieusement la relecture des copies existantes. Seul `available_tests()` (menu de sélection UI) les masque.
- **Conséquence visible assumée :** l'interface ne propose plus aucun test Hakili tant que les 7 nouveaux ne sont pas intégrés — le menu ne contient que « Test personnalisé ». Comportement attendu de A1, signalé à l'utilisateur.
- **Décision D : barème stocké sur 20.** Conversion `bareme_classeur / 3` à l'import. Le tiers de point (partie A) n'étant pas représentable exactement, la décision s'accompagne d'une règle : **la note se calcule toujours contre la somme réelle des `max_score`, jamais contre un total déclaré.** Cette règle rend l'imprécision inoffensive (copie parfaite = 20,00 exactement) et corrige du même coup le bug §5.1 constaté en production. Elle donne enfin un usage au champ `rubric_actual_max` déjà présent mais inutilisé dans `CopyGrade`.
- **Vérifié :** `available_tests()` vide, `all_tests()`/`ids` complets, `get_test('hakili_3e_v1')` résout toujours (archive=True, niveaux intacts). Suite de tests : **102 passent**. Les 2 erreurs de collecte (`test_google_sheets.py`, `test_ui_math.py`) sont pré-existantes et sans rapport — absence de `.env` local, `ANTHROPIC_API_KEY` manquante à l'import de `config.py`.
- **Bloqué par :** rien pour le Module 1. Arbitrages B, C, E, F toujours en attente (B est le chemin critique pour les modules 3 à 9).
- **Prochaine étape :** Module 1 — modèles SQLAlchemy, migration Alembic, `import_referentiel.py`.

### 2026-07-30 (suite) — Les 7 nouveaux tests générés et opérationnels
- **Découverte qui a changé l'approche : les énoncés ne sont pas extractibles des PDF.** Les 7 sujets sont produits par WeasyPrint et **toutes les mathématiques sont dessinées en vectoriel** (211 tracés sur une page, aucun span de texte). L'extraction rend la prose sans les formules : `N5` → « Recopier et compléter avec le symbole  ou le symbole  :  et  . ». Tous les modes d'extraction testés, aucune source HTML ni script générateur trouvé sur le disque.
- **Nuance importante : les codes de cadre s'extraient parfaitement** — c'est ce qui avait permis la vérification 280/280, et c'est tout ce dont le module 2 a besoin. Le problème ne touche que les énoncés littéraux.
- **Point qui débloque tout :** dans ce format l'élève compose **sur le sujet**, donc la copie scannée porte l'énoncé imprimé que l'IA transcrit. `subject_text` devient non critique, alors qu'il aurait été bloquant dans l'ancien format à copie séparée.
- **Décision G (nouvelle) : le classeur est la source des données de test**, pas les PDF. `04_Questions` donne code/partie/format/barème/compétence/intitulé, `06_Distracteurs` donne les options QCM avec la bonne réponse.
- **Livré :** `scripts/generer_baremes_urie.py` (idempotent, vérifié par hachage) génère les 7 `data/knowledge/bareme_urie_*.yaml`. **280 questions, 71 QCM avec bonne réponse, 209 champs `reponse_attendue`/`solution` vides** prêts pour l'arbitrage B — aucune migration corrective ne sera nécessaire.
- **Format YAML plat** (`questions`) et non l'ancien découpage `questions_numeriques`/`questions_geometriques` : les 7 domaines du référentiel (N, L, G, D, F, M, S, T) n'y rentrent pas. `_build_rubric_from_yaml` accepte désormais les deux formats — l'ancien reste lu pour les tests archivés.
- **Les 7 tests déclarent une classe canonique unique** (`6e`…`Tle`) au lieu des niveaux évalués. Vérifié au passage que `normalize_classe` ne reconnaît **pas** `2ndeC`/`1ereD`/`TleD` (retourne `None`) — d'où l'emploi des formes canoniques. Bénéfice : `resolve_classe` a un garde-fou exact et un repli fiable si l'extraction d'en-tête échoue, ce que les anciens tests n'offraient pas.
- **Propriété centrale vérifiée : une copie parfaite vaut exactement 20,0/20 sur les 7 tests**, malgré les tiers de point de la partie A (somme réelle 19,99999, absorbée par l'arrondi au quart). Verrouillé par test de régression.
- **Vérifié :** `tests/test_baremes_urie.py` — 40 questions/test, structure 30 A + 10 B, barème /20 = classeur/3, classe reconnue par le normaliseur, codes uniques, QCM avec bonne réponse unique, distracteurs tagués par un type de la liste fermée, 209 sans corrigé = exactement les non-QCM, copie parfaite = 20/20, copie nulle = 0/20, archivés masqués mais résolus. **168 tests passent** (102 avant, 66 nouveaux).
- **Limite cosmétique connue :** les intitulés du classeur sont en ASCII replié (254/280 sans accents) et apparaissent tels quels comme libellés dans l'interface. Sans effet sur la correction ni le diagnostic ; corrigeable plus tard sans changement de schéma.
- **Bloqué par :** rien. **Prochaine étape : Module 1.**

### 2026-07-30 (suite) — Accents traités, architecture cible recommandée
- **Accents : ce n'est pas un problème d'encodage mais de saisie dans le classeur**, qui se contredit lui-même (« apres » 34× vs « après » 36×, « carre » 29× vs « carré » 10×). L'auteur a bien tapé des accents (204 mots distincts en portent) — les formes nues sont des oublis.
- **Mesuré : 150 mots à corriger, 16 à arbitrer** sur 2 314 mots distincts des colonnes lisibles.
- **Correction automatique écartée délibérément :** pour 16 mots, la forme sans accent est aussi un mot français valide — « calcule » (je calcule) ou « calculé » ? « eleve » (l'élève) ou « élevé » (au carré) ? « cote » a 4 lectures. Un remplacement à l'aveugle écrirait un contresens pédagogique dans un libellé lu par un parent. Même règle que partout : ne jamais deviner une donnée.
- **Livré :** `scripts/verifier_accents.py --rapport` → `docs/accents_a_corriger.md`, document remettable tel quel au docteur (mot, correction, occurrences, onglets, et les 16 ambigus séparés avec leur piège explicité). La correction se fait dans le classeur, pendant la relecture pédagogique déjà requise par `00_Notice`.
- **Verrou :** `tests/test_accents_referentiel.py` fixe les plafonds (150 / 16) et échoue si le classeur régresse — **et aussi s'il s'améliore**, pour forcer l'abaissement du plafond, sinon le garde-fou se relâcherait. C'est ce qui répond au « une bonne fois » : le défaut ne peut plus revenir sans être vu, contrairement aux `chunk_ids` cassés restés invisibles en `logger.debug`.
- **172 tests passent** (168 avant).
- **Architecture : recommandation écrite dans `docs/architecture_cible.md`** — sortir de Streamlit pour **Django + HTMX**. Mesures à l'appui : `app.py` fait 2 876 lignes (26 % du projet, 342 appels `st.*`, 71 `session_state`, 30 blocs HTML en chaînes), mais **70 % du code est déjà indépendant du framework** (pipeline, clients IA, RAG, PDF, Sheets migrent intacts). Les deux arguments décisifs pour Django : l'auth/permissions intégrées (données nominatives de mineurs sur 7 mois, point ouvert #4 / CIL Burkina Faso — le PIN est aujourd'hui en clair dans un Sheet, sans jeton de session ni autorisation par requête) et l'`admin` qui couvre presque gratuitement les écrans du module 8 sur 11 tables relationnelles.
- **Le moment est critique :** les 11 tables ne sont pas encore écrites. Décider du framework **avant** le Module 1, sinon 11 modèles SQLAlchemy + une migration Alembic seront à jeter.
- **Bloqué par :** décision framework, et une question qui la conditionne — **les centres ont-ils une connexion fiable ?** Si le tuteur doit remplir sa fiche hors ligne, il faut une PWA avec file d'attente locale, ce qui change la conception.
- **Prochaine étape :** trancher l'architecture, puis Module 1 dans la cible retenue.

### 2026-07-30 (suite) — Contraintes d'architecture tranchées
- **Décidé : pas de hors ligne** (connexion Internet requise), **pas de PWA**, **base sur Neon inchangée**.
- **Effet :** ces trois réponses lèvent la seule réserve qui pesait sur la recommandation. Sans besoin hors ligne, aucune API explicite n'est nécessaire et Django REST Framework devient inutile — **Django + HTMX en rendu serveur est la réponse, sans nuance.** Le module 8 (fiche tuteur sur téléphone) devient une page HTML responsive à 5 champs, pas une application installable.
- **Simplification obtenue :** pas de service worker, pas de file d'attente locale, pas de synchronisation ni de résolution de conflits.
- **Seul point pratique encore ouvert : où héberger l'application.** Vérifié que l'app tourne aujourd'hui **en local** (`streamlit run`, aucun `Procfile`, `runtime.txt` seul vestige d'un déploiement envisagé) — Neon ne fournit que la base. Une app Django multi-utilisateurs (tuteurs sur téléphone, responsables, admin) suppose une adresse joignable : hébergeur, domaine, HTTPS, sauvegardes.
- **Conséquence à ne pas manquer sur le point ouvert #4 :** dès que l'application quitte le poste local, les données nominatives de mineurs transitent sur le réseau. HTTPS devient obligatoire et le remplacement du PIN en clair par une vraie authentification devient urgent — c'est exactement ce que Django apporte.
- **Bloqué par :** choix de l'hébergement, et feu vert sur la migration (plusieurs semaines d'interface).
- **Prochaine étape :** feu vert → squelette Django + les 11 tables (= Module 1 fait directement dans la cible).

### 2026-07-30 (suite) — ✅ Module 1 fait, en Django
- **Décidé :** hébergement **Railway ou Render** ; feu vert pour Django. Django 5.2 installé, ajouté à `requirements.txt`.
- **Livré :** projet `hakili/` (settings, urls, wsgi, asgi) + apps `referentiel` et `suivi` + `manage.py`. `src/` n'a pas été touché — pipeline, clients IA, RAG, PDF et Sheets restent intacts, et Streamlit continue de tourner.
- **11 tables migrées** : `referentiel` (Competence, Prerequis, TypeErreur, CoutRemediation, Question, SignatureErreur, OptionQcm) et `suivi` (Session→`session_urie`, Evaluation, Reponse, Probleme, Transition, Seance). Cycle descente/remontée testé, comme sur les migrations Alembic précédentes.
- **Import du référentiel** (`manage.py importer_referentiel`, idempotent, vérifié sur deux passages) : **7 types · 101 compétences · 136 prérequis · 444 coûts · 280 questions · 1031 signatures · 284 options · 71 QCM corrigés · 209 sans corrigé**. Chiffres identiques au module 0. Contrôle d'intégrité **avant** toute écriture : un code inconnu fait échouer l'import avec un message précis, plutôt que d'écrire à moitié.
- **Vérifié en base : L5 du test de 3ème redonne exactement la réponse du module 0** — `L.IDR × CPT`, coût 0,50 h, bonne réponse `d`, distracteurs tagués CPT/PRC/PRC.
- **Admin configuré** sur les 11 tables : compétences filtrables par domaine et niveau (volume manquant signalé en rouge), questions par test/format avec leurs signatures et options en ligne, problèmes avec état coloré et historique des transitions. C'est ce qui remplace une bonne part des écrans du module 8.
- **`Transition` est protégée par le code, pas par la discipline** : `Probleme.changer_etat()` refuse un enchaînement non prévu, écrit la transition dans la même opération atomique, et `Transition.save()` refuse toute modification après création. L'admin met `etat` en lecture seule pour qu'on ne puisse pas contourner la méthode.
- **Deux décisions de conception prises en cours de route, motivées :**
  1. **Les settings Django ne lisent pas `src/core/config.py`** — `Settings()` exige `anthropic_api_key` sans défaut, ce qui ferait échouer `manage.py migrate` sur une machine sans clé LLM, alors qu'une migration n'appelle aucun modèle.
  2. **`Evaluation.copy_id` est un champ texte, pas une clé étrangère.** Tentée d'abord en FK vers une `Copie` non gérée : les tests ont révélé que Django ne crée pas les tables non gérées en base de test, donc toute insertion échouait. Le contournement (lanceur de tests flexant `managed`) ne marche pas non plus, les migrations figeant `managed: False`. Le lien souple est de toute façon le bon choix — c'est exactement le précédent de `identifiant_hakili` (D-CEO-20) : quand la donnée référencée est hors du territoire de Django, on garde un identifiant et on documente. Deviendra une vraie FK quand `copie` passera sous Django.
- **Réglages Neon repris de D-CEO-19 :** `CONN_HEALTH_CHECKS` (= `pool_pre_ping`) et `CONN_MAX_AGE=300` (= `pool_recycle`) — sans quoi les connexions mortes après la mise en veille de Neon provoqueraient des écritures perdues, comme constaté à l'époque.
- **Sécurité posée d'emblée :** `DJANGO_SECRET_KEY` obligatoire hors DEBUG (échec au démarrage plutôt qu'une clé de repli), HTTPS forcé, cookies sécurisés, HSTS, en-tête proxy Railway/Render. Nécessaire dès que l'application quitte le poste local avec des données de mineurs.
- **Vérifié :** 15 tests Django (`manage.py test suivi`) dont **le parcours complet T0→T5 d'un élève fictif avec toutes ses transitions** — le critère de fin du module 1 tel qu'écrit dans `guide-urie.md`. Plus : transitions interdites refusées, états terminaux bloqués, `ATT` ne pouvant jamais être confirmé, atomicité de `changer_etat`, unicité d'un problème par session, immuabilité des transitions, calcul du taux de confirmation. **Les 172 tests pytest existants passent toujours** — aucune régression sur Streamlit.
- **Support SQLite ajouté** à `DATABASE_URL` pour que tests et intégration continue tournent sans Neon ; la production reste sur Neon.
- **Bloqué par :** rien. **Prochaine étape :** Module 2 (lecture des copies par zones) ou migration des écrans Streamlit vers Django — à arbitrer.

### 2026-07-30 (suite) — Migration Streamlit → Django : fondations posées
Décision : migrer l'interface **avant** de continuer les modules Urie, pour ne pas maintenir deux interfaces longtemps.

**Fait**
- **Logique métier extraite de `app.py`** vers `src/services/identite_service.py` : rôles valides d'une personne, vue utilisateur par casquette, recherche insensible casse/accents/ordre, nommage des documents, appariement fichier ↔ élève en batch. C'était du métier enfermé dans un fichier Streamlit de 2 876 lignes, donc intestable et perdu avec lui. `app.py` passe à 2 778 lignes et pointe vers le service par alias — aucune duplication. **23 tests** écrits au passage, dont les pièges déjà rencontrés (recherche insensible à l'ordre des mots, casquette responsable couvrant tout le centre).
- **Authentification Django adossée au Sheet** (`comptes/`) : backend relisant le Sheet personnel à chaque connexion, compte Django miroir **sans mot de passe utilisable** (le PIN reste dans le Sheet — pas de seconde source de vérité), rôle et casquette en session, décorateurs `connexion_requise` / `admin_requis`. Gain concret : vraie session signée et expirante (8 h), CSRF, autorisation vérifiée par requête — au lieu d'un booléen dans `session_state`.
- **Écrans migrés** : liste des élèves du périmètre avec pastille de tendance (`calculer_tendance` réutilisée, pas réécrite), recherche, tri des élèves en baisse en premier, statistiques admin, en-tête avec sélecteur de casquette. Gabarits responsive (`templates_django/base.html`), champs à 16 px pour éviter le zoom automatique sur iOS, `<select>` natif pour la connexion (le sélecteur du téléphone est déjà recherchable).
- **22 tests d'accès** figeant les scénarios vérifiés à la main sur Streamlit : PIN correct/incorrect, PIN absent du Sheet, rôle non reconnu, personne retirée du Sheet, cloisonnement responsable (tout son centre) / enseignant (sa classe) / admin (tout), changement de casquette refusé si non porté, refus en GET, aucune donnée sensible à l'écran (`contact_parents`, `identifiant_hakili`).

**Trois défauts trouvés et corrigés en cours de route**
1. **`anthropic_api_key` était obligatoire à l'import de la configuration**, or `google_sheets` et `db/database` en dépendent : `manage.py check`, `migrate` et même l'affichage d'une liste d'élèves échouaient sans clé LLM, alors qu'aucun de ces chemins n'appelle un modèle. Rendue facultative à l'import, avec l'exigence rétablie dans `ClaudeClient.__init__` — là où elle sert. **Effet de bord bénéfique : les 2 erreurs de collecte pytest qui traînaient (`test_google_sheets`, `test_ui_math`) sont réparées, la suite tourne maintenant sans `.env`.**
2. **Commentaires de gabarit multi-lignes rendus en clair dans la page** : Django ne supporte `{# #}` que sur une ligne. Convertis en `{% comment %}`.
3. **Une base injoignable rendait une erreur 500** au lieu de dégrader : la liste des élèves vient des Sheets et reste affichable sans les notes. La vue affiche désormais la liste sans la tendance, en le disant — Neon se met en veille, ce cas arrivera.

**Choix de conception notable :** les modules Django importent `google_sheets` **en tant que module**, pas ses fonctions par leur nom. Une fonction importée par son nom fige sa référence et devient impossible à simuler en test sans connaître tous les modules qui l'ont importée — c'est ce qui faisait échouer les 21 premiers tests d'authentification.

**Reste à migrer** (Streamlit reste en service en attendant) :
- Historique détaillé d'un élève, profil enseignant, comparaison chronologique, aperçu et téléchargement des PDF.
- **Le flux de correction** (traitement unique et batch) — le point dur : le pipeline dure 60 à 90 s et comporte des arrêts de validation humaine (relecture de transcription, tableau de validation). Demande un état persisté et un suivi de progression, là où Streamlit s'appuyait sur `session_state` et des threads.
- Retrait effectif de Streamlit et de ses dépendances.

**Vérifié :** 37 tests Django + 218 pytest = **255 tests passent**.

### 2026-07-30 (suite) — Vues de gestion et flux de correction migrés
**Vues de gestion terminées**
- Profil d'un élève : tendance, résumé chiffré, copies chronologiques, documents. **Une seule vue pour les trois rôles** au lieu des onglets Historique / Comparaison / Profil de Streamlit : sur un même élève ils affichaient la même chronologie (constat déjà fait en D-CEO-24), les fusionner supprime la duplication sans rien retirer.
- Documents servis directement par le navigateur : **plus de conversion PDF → PNG**, que Streamlit était obligé de faire faute de pouvoir embarquer un PDF. Le type réel est lu dans les premiers octets (un scan peut être une photo), pas déduit du champ `type`.
- **Jetons signés dans les URL** (`suivi_web/jetons.py`) plutôt que `identifiant_hakili` en clair. Motif : D-CEO-25 a explicitement retiré cet identifiant de l'interface, et une URL le ferait réapparaître dans la barre d'adresse, l'historique, les journaux et les en-têtes `Referer`. Bénéfice supplémentaire : un identifiant en clair s'énumère, un jeton forgé ne passe pas la signature.
- **L'autorisation est revérifiée sur l'URL du document**, pas seulement sur la page qui affiche le lien — sans quoi une URL partagée suffirait à récupérer la copie d'un élève d'un autre centre.

**Flux de correction migré (mode copie unique)**
- `correction_web/` : dépôt de copie, transcription en tâche de fond, relecture de la transcription, correction, tableau de validation, diagnostic, résultats.
- **L'état vit en base, pas en session** : le pipeline dure 60 à 90 s et comporte deux arrêts humains. Streamlit gardait cet état dans `session_state` (mémoire du processus) — intransposable, puisque plusieurs processus servent les requêtes en production et que rien ne garantit que la requête suivante tombe sur celui qui détient l'objet.
- **Sérialisation explicite en JSON, pas de pickle** (`correction_web/serialisation.py`) : un pickle casse au moindre changement de champ et désérialiser revient à exécuter du code venant de la base. La conversion s'appuie sur `model_dump()`, déjà utilisé par le pipeline pour son export `result.json`.
- **Un thread, pas de file de tâches** : Redis + RQ serait plus robuste mais ajoute un service à déployer, pour un besoin réel de quelques corrections simultanées. Limite assumée et traitée : `signaler_si_abandonnee` passe en échec une correction qui ne progresse plus depuis 15 minutes, au lieu de laisser une barre tourner indéfiniment après un redéploiement.
- `close_old_connections()` en fin de thread — sans quoi Django laisse une connexion ouverte par thread jusqu'à saturer le pool côté Neon.
- **Une seule URL par copie**, qui affiche l'écran correspondant à l'état : l'enseignant peut recharger, fermer l'onglet et revenir, il retombe au bon endroit.

**19 tests sur le flux**, centrés sur D-CEO-16 (« l'IA propose, l'enseignant décide ») : tout accepter garde les notes de l'IA, refuser impose celle de l'enseignant, note bornée au barème (une faute de frappe ne doit pas produire un 25/20), saisie illisible valant 0 sans bloquer la copie, **virgule acceptée comme séparateur décimal** (un enseignant francophone tape « 0,5 »), élève hors périmètre refusé **avant tout appel IA** (D-CEO-20), format de fichier refusé, correction abandonnée détectée.

**À connaître pour le déploiement :** le pipeline écrit ses fichiers intermédiaires dans `runs/`, sur disque local. Sur Railway ou Render sans volume persistant, ce dossier disparaît au redéploiement — les documents durables (scan, rapport, remédiation) sont déjà en base, donc rien d'irremplaçable n'est perdu, mais une correction en cours au moment du redéploiement devra être relancée. Prévoir un volume, ou l'accepter.

**Vérifié :** 72 tests Django + 218 pytest. Migration complète rejouée sur base neuve.

### 2026-07-30 (suite) — Mode lot migré, rendu mathématique récupéré
- **Mode lot** (`correction_web:lot`) : dépôt d'une classe entière, élève de chaque copie déduit du **nom de fichier** apparié aux Sheets. Sans correspondance unique, la copie est écartée et signalée — jamais attribuée au hasard (D-CEO-20). Un fichier invalide n'empêche pas le traitement des vingt-neuf autres.
- **Différence assumée avec Streamlit :** son mode lot produisait des rapports complets **sans qu'aucun enseignant ait vu une seule note**, ce qui contredisait D-CEO-16 (« la correction automatique sans validation est inacceptable pour un document officiel »). Ici, la Phase A tourne d'affilée — la relecture de transcription reste sautée, la relire trente fois coûterait plus cher que la correction — mais **le tableau de validation est conservé** : les copies arrivent dans la liste, à valider une par une. Déposer reste une seule action.
- **Rendu mathématique récupéré** (`src/services/affichage_math.py` + filtre de gabarit `|math`) : `_mh` / `_mt` étaient enfermés dans `app.py`. Sans eux, la table de validation aurait affiché « x^2 » et « <= » au lieu de x² et ≤ — ce n'est pas cosmétique, c'est ce que l'enseignant compare pour décider d'une note. `tests/test_ui_math.py` ne dépend plus de Streamlit.
- **Défaut trouvé dans mes propres tests :** l'assertion « aucune donnée sensible à l'écran » cherchait la sous-chaîne « H3 », qui apparaît par hasard dans les signatures base64 des jetons (`…VyO4H3b8…`) — test instable qui échouait au gré des signatures. Corrigé par des identifiants de test réalistes (`HAK-2026-0001`), et le motif est documenté dans le test pour que personne ne les raccourcisse.

**Vérifié :** 77 tests Django + 218 pytest = **295 tests passent**. Plus aucun test ne dépend de Streamlit.

### 2026-07-30 (suite) — Mode libre migré
Test personnalisé (sujet hors catalogue) désormais disponible dans l'interface Django : barème vide et sujet déposé transmis au pipeline, qui en extrait le barème — exactement le fonctionnement de l'ancienne interface. Le sujet est **obligatoire** dans ce mode : sans lui, aucun barème ne peut être établi et la correction n'aurait rien à quoi se comparer. `bareme_id` est laissé vide plutôt que « libre », sinon la résolution de classe et le RAG chercheraient un test de catalogue inexistant.

**Vérifié :** 81 tests Django + 218 pytest = **299 tests passent**.

### ⚠ Retrait de Streamlit — un seul point bloquant
Streamlit **reste en service**, délibérément.

**Il manque un essai réel de bout en bout.** Cet environnement n'a pas de clés API : tous les tests simulent le pipeline. Une correction complète sur une vraie copie — vraies API, vraie base Neon, vrai Sheet — doit être passée avant de retirer le filet.

Tout le reste est prêt :
- Toutes les fonctions métier enfermées dans `app.py` ont été extraites (`src/services/identite_service.py`, `src/services/affichage_math.py`).
- Plus aucun test ne dépend de Streamlit.
- Les quatre écrans sont couverts : correction d'une copie, correction d'une classe, suivi des élèves, statistiques — plus le mode libre.

**Marche à suivre une fois l'essai passé :** supprimer `src/ui/`, retirer `streamlit` de `requirements.txt` et le dossier `.streamlit/`, mettre à jour `README.md`, `CLAUDE.md` et le registre des décisions.

### 2026-07-30 (suite) — Mise en service préparée
**Constat en préparant le déploiement : l'application ne pouvait pas être déployée.** Aucun serveur web dans `requirements.txt`, aucun `Procfile` — `runserver` n'est pas un serveur de production. Comblé :
- `gunicorn` et `whitenoise` ajoutés ; WhiteNoise sert les fichiers statiques sans serveur web séparé, ni Railway ni Render n'en fournissant. Chaîne `collectstatic` vérifiée (381 fichiers post-traités).
- `Procfile` valable pour Railway comme pour Render, avec `release: migrate` avant chaque mise en ligne. `--threads 4` parce que les corrections tournent dans un thread du processus web ; `--timeout 180` pour le dépôt d'un lot sur connexion lente.
- Makefile mis à jour : `make run` lance désormais Django, `make run-streamlit` reste disponible le temps de la validation.

**`manage.py verifier_installation`** : contrôle avant mise en service — configuration Django, base et migrations, Sheets, clés d'API, référentiel importé, stockage inscriptible, XeLaTeX. Chaque manque est nommé **avec sa conséquence** (« aucune correction ne peut démarrer », « l'application refusera toutes les requêtes »). Avec `--copie`, la commande exécute une correction réelle de bout en bout : c'est le contrôle qui conditionne le retrait de Streamlit, rendu accessible en une commande.

**`docs/deploiement.md`** : variables d'environnement avec leur rôle et leur criticité, procédure, et deux points qui demandent un arbitrage.

**Deux limites de déploiement identifiées, à trancher :**
1. **`runs/` est du disque local et Railway/Render l'effacent à chaque redéploiement.** Les documents durables sont en base, donc rien d'irremplaçable n'est perdu — mais une correction en cours perd ses fichiers de travail (détectée comme abandonnée après 15 minutes). Soit un volume persistant, soit l'accepter et redéployer hors heures de correction.
2. **Une seule instance.** Le suivi de progression passe par la base, mais le thread de travail vit dans un processus donné : avec plusieurs instances, une correction lancée sur l'une paraîtrait figée aux autres. Tant qu'aucune file de tâches n'est en place, rester à une instance.

**`SECURE_HSTS_PRELOAD` laissé à False délibérément** — `check --deploy` le signale, ce n'est pas un oubli : le préchargement est une porte à sens unique (radiation en plusieurs mois) et n'a aucun sens sur un sous-domaine mutualisé où l'en-tête est hérité. À réexaminer avec un domaine propre.

**Vérifié :** `check --deploy` en conditions de production ne laisse que deux avertissements, tous deux expliqués. 81 tests Django + 218 pytest = **299 tests passent**.

### 2026-07-30 (fin de soirée) — Le cycle réel, et le moteur du plan de remédiation
Trois décisions de fond ont été prises après confrontation du protocole à la pratique du centre, puis le module 6 a été attaqué dans la foulée.

**Ce que le modèle métier avait de faux, corrigé (D-CEO-32, 33, 34)**
- **Périmètre unique (D-CEO-32).** Hakili Lab est un **centre d'encadrement, pas une école** : les enseignants tournent et reprennent les copies d'un collègue absent. Le cloisonnement par centre et par classe bloquait un travail légitime sans rien protéger — il est retiré, le sélecteur de casquette avec. La sécurité se joue en amont, à l'autorisation : présent dans le Sheet du personnel avec un code d'accès, on travaille ; retiré, on ne se connecte plus. Nouvel écran `/personnel/` en lecture seule pour *voir* cet état, les comptes en défaut affichés en premier.
- **T2 retiré, évaluations répétables (D-CEO-33).** Le cycle passe à cinq étapes : T0 → T1 → remédiation hors plateforme → T3 (fin du volume horaire) → T4 (45 j) → T5 (3 mois). `UniqueConstraint(session, type)` interdisait un second T3 alors que l'enseignant relance un test tant que les lacunes tiennent : remplacée par `(session, type, numero)`, le rang étant attribué à la création. Les indicateurs du module 9 comptent des **transitions**, pas « la » T1 — ils agrègent naturellement les passages multiples.
- **États de session et inscription (D-CEO-34).** Sept états au lieu de trois, dont trois sorties **sans** remédiation distinguées à dessein : `sans_suite` (T1 n'a rien confirmé — **c'est un bon résultat**, le confondre avec un abandon transformerait une réussite en échec dans les comptes rendus), `hors_dispositif` (palier C), `abandonnee`. `Session.inscrire()` bascule les problèmes confirmés en remédiation, date l'inscription, et refuse le palier C sans motif explicite conservé dans les transitions.

**Module 6 — le moteur tourne (`suivi/plan.py`)**
- **Tri topologique sur le graphe des prérequis**, restreint aux compétences réellement en difficulté : un problème dont un prérequis est lui-même en difficulté se traite après lui. À égalité, on commence par la compétence introduite le plus tôt. C'est ce qui distingue une remédiation d'un rattrapage — travailler les identités remarquables avec un élève qui ne sait pas additionner deux relatifs est du temps perdu, et le tuteur ne le découvrirait qu'en séance.
- **Un cycle dans le graphe ne fait pas boucler** : la base l'interdit, mais un import mal formé pourrait en créer un — on verse le reste par niveau plutôt que de tourner indéfiniment.
- **Seuls les problèmes `confirme` et `en_remediation` entrent au plan.** Une hypothèse non vérifiée n'a rien à y faire : c'est tout l'objet du test de confirmation. Les problèmes déjà en remédiation y restent, sinon le tuteur perdrait sa feuille de route juste après l'inscription.
- **Chaque étape porte de la matière pour la séance** : les signatures d'erreur du référentiel propres au type diagnostiqué (4 au plus), et la liste des prérequis eux-mêmes en difficulté.
- **`repose_sur_estimation` est remonté jusqu'à l'écran** quand le plan s'appuie sur un volume de repli (D-CEO-29). Ce chiffre détermine ce qu'une famille paiera : il ne doit pas passer pour un volume officiel.
- **Écran `/parcours/<jeton>/`** : plan ordonné, volume, palier, hypothèses restantes, bouton d'inscription. Inscription **en POST seulement** — elle engage un volume horaire et vraisemblablement une facturation, elle ne doit pas pouvoir arriver par un lien cliqué. Jeton signé comme partout ailleurs (D-CEO-25), autorisation revérifiée sur l'URL.

**Ce qui manque encore au module 6 :** la **planification en séances** — la table `Seance` existe et l'admin l'expose, mais rien ne la remplit. Et le moteur n'a tourné que sur des problèmes créés à la main : sans Module 4, il n'a pas encore vu un seul diagnostic réel.

**Vérifié :** 12 tests sur le plan (ordre indépendant de l'ordre de saisie, prérequis hors difficulté ignoré, cycle non bouclant, hypothèses exclues, volume estimé signalé) + 7 sur l'écran de parcours (inscription refusée en GET, palier C exigeant un motif, bouton disparaissant une fois inscrit, parcours hors périmètre en 404). **170 tests Django + 218 pytest = 388 tests passent.**

**Bloqué par :** rien techniquement. **Prochaine étape : Module 2** (lecture des copies par zones) — c'est le seul chemin vers le Module 4, dont tout le reste dépend.

> ⚠ **Un point de gestion, hors code, qui pèse plus que le prochain module :**
> **L'essai réel de bout en bout n'a toujours pas eu lieu** (pas de clés API dans cet environnement) — c'est lui qui conditionne le retrait de Streamlit, et il conditionne aussi la confiance qu'on peut accorder à tout ce qui précède.

### 2026-07-31 (suite) — L'outil de tagage durci par l'usage
Trois copies taguées ont montré où l'outil laissait passer. Six correctifs, dans l'ordre du risque.

**1. La validation attrapait les codes inventés, pas les codes faux.** C'est le trou principal, et il s'est refermé sur moi : le tagage de la copie 1 a conclu qu'aucune compétence ne couvrait le vocabulaire géométrique, alors que `G.VOC` existe — 17 compétences de niveau primaire avaient échappé à ma lecture. Un code inventé est rejeté ; un code **valide mais mal choisi** passait sans un mot et salissait l'étalon de façon invisible. Trois parades : `--chercher <mot>` et `--chercher --niveau <niveau>` mettent le référentiel sous la main pendant le tagage ; un code rejeté fait proposer les codes proches ; le compte rendu **rappelle le libellé en toutes lettres** de chaque code retenu — relu, un mauvais choix a une chance de sauter aux yeux.

**2. Un problème de corpus pouvait contaminer le suivi réel d'un élève.** `cout_total_confirme` et `inscrire()` filtrent par **session**, pas par évaluation. Taguer une copie d'archive sous l'identifiant d'un élève réellement suivi aurait fait entrer ces problèmes dans son palier — donc dans ce que sa famille paierait. Trois verrous : la session de tagage est marquée `corpus_reference`, elle refuse `etablir_le_plan()` et `inscrire()`, et le tagage **refuse** une session de suivi réel en le disant clairement. Une reprise de données marque les sessions taguées avant l'existence du drapeau — sans elle, les trois premières copies seraient devenues des sessions « réelles ».

**3. Aucun contrôle de cohérence de niveau.** `N.FRA2` (5ème) avait été tagué sur une copie d'entrée **en** 5ème : la compétence n'est pas encore enseignée, l'échec y est normal. Un avertissement le signale désormais — sans refuser, parce que c'est un jugement.

**4. Le coût était figé au tagage.** Les 27 volumes de lycée sont des valeurs de repli (D-CEO-29) ; le jour où les vrais arriveront, les coûts du corpus resteraient faux en silence. `manage.py corpus` détecte l'écart, `--recalculer` le corrige.

**5. On ne pouvait pas relire le corpus.** `manage.py corpus` donne la composition, la répartition des sept types, et les compétences taguées plusieurs fois sur une même copie. **Premier résultat utile, immédiatement :** le corpus ne contient **aucun `PRQ` ni `RED`** — le module 4 ne pourrait pas être mesuré sur ces deux types. C'est une consigne concrète pour les deux dernières copies.

**6. Les hésitations étaient éparpillées.** `manage.py corpus --hesitations` les rassemble depuis les fichiers — 11 sur 3 copies. Elles restent en YAML à dessein : une hésitation est un jugement en attente d'arbitrage, la mettre en base lui donnerait un statut qu'elle n'a pas.

**Vérifié :** 34 tests sur le corpus, cycle de migration testé dans les deux sens, `makemigrations --check` stable. **204 Django + 242 pytest = 446 tests passent.** L'outil est ensuite repassé sur le corpus réel : les 3 copies ressortent intactes.

### 2026-07-31 (suite) — Deux premières copies taguées, et un contraste qui valide la démarche
Les 5 copies sont réunies (2 en 3ème, 2 en 5ème, 1 en 6ème). Les **deux copies de 3ème** — même sujet, même correcteur — sont taguées.

| | copie 1 | copie 2 |
|---|---|---|
| Note | 0,25/20 | forte |
| Problèmes | **22** | **10** |
| Coût | **34,5 h → palier C** | **8,5 h → palier B** |
| Types dominants | CPT (13/22) | PRC (4), ATT (3), CNS (2) |

**C'est ce contraste qui fait le corpus.** Une copie s'effondre — presque tout est conceptuel, la remédiation courte est hors de portée et le dispositif doit le dire. L'autre réussit l'essentiel et n'échoue que sur des gestes : signes dans les fractions, exposant perdu à la recopie, hachure du mauvais côté d'une inéquation pourtant bien résolue. **Le module 4 sera jugé sur sa capacité à distinguer les deux**, pas à détecter l'effondrement — que n'importe quelle heuristique repère.

Deux mécanismes déjà éprouvés en conditions réelles au passage : les trois `ATT` de la copie 2 sont **comptés 0 h**, et le palier bascule de B à C entre les deux copies sans intervention.

**Ce que le tagage a appris sur le référentiel — 8 hésitations relevées, dont trois qui comptent :**
1. **Aucune compétence ne couvre le vocabulaire géométrique de base.** La copie 1 répond « parallèle » ou « perpendiculaire » à quatre questions attendant un point ou une mesure — échec corrélé sur `G.SYMC`, `G.SYMO`, `G.ANG3`, `G.TRIP`, c'est-à-dire la signature exacte de **PRQ**. Mais PRQ exige de *nommer* le prérequis, et il n'existe pas. Faute de mieux, quatre `CPT` séparés ont été posés — ce qui **gonfle mécaniquement le coût** d'un élève dont le problème est unique. Le référentiel a-t-il besoin d'une compétence transversale de vocabulaire géométrique ?
2. **La frontière ATT / PRC n'est pas nette**, et elle n'est pas neutre : `ATT` vaut 0 h, `PRC` vaut au moins 0,5 h. Un `x³` recopié `x` est-il une inattention ou une exécution ratée ? Le classement change la facture.
3. **Trois `ATT` sur une même copie** interrogent le protocole : chacune se justifie isolément, mais les écarter toutes à T1 ferait peut-être disparaître un profil réel — élève rapide et négligent — que le référentiel ne sait pas nommer.

**Décision prise sur les données personnelles :** les copies portent nom complet, établissement et téléphone d'élèves mineurs. Le corpus emploie des identifiants **non nominatifs** (`CORPUS-3E-01`…) : c'est un instrument de mesure, il n'a aucun besoin de nommer un enfant. À confirmer si ces élèves doivent aussi être suivis pour de vrai.

**Reste :** les 3 dernières copies (2 en 5ème, 1 en 6ème, 14 pages chacune).

### 2026-07-31 (suite) — Module 3 : l'étalon a maintenant où se poser
Le module 1 avait laissé le marqueur du corpus « à définir ». Il est défini, et deux manques sont apparus en le posant.

**Ce qui a été ajouté au socle**
- `Evaluation.corpus_reference`, `tague_par`, `date_tagage`, avec une **contrainte en base** : pas de marquage sans auteur ni date. Un corpus anonyme n'est pas discutable — deux personnes ne taguent pas tout à fait pareil, et c'est une information, pas un défaut.
- **`Probleme.evaluation_origine` et `Probleme.justification`.** Le premier relie un problème à la passation qui l'a révélé — sans lui, refaire un tagage aurait obligé à supprimer *tous* les problèmes de la session, y compris le suivi réel de l'élève. Le second porte ce qu'on a lu sur la copie : c'est ce qui rendra un désaccord entre le corpus et le module 4 **arbitrable**, au lieu d'un écart de comptage muet. Le module 4 en a besoin autant que le module 3 — c'est la « citation » que le guide lui demande de produire.

**Arbitrage rendu : un fichier, pas un écran.** Le tagage est lent et discutable — on relit, on hésite, on corrige. Un fichier se relit, se compare, se reprend le lendemain ; un formulaire perd tout à la première fermeture d'onglet. `manage.py taguer_corpus --fichier … [--a-blanc] [--remplacer]`.

**La validation est complète avant toute écriture**, et c'est le point qui compte : un corpus à moitié écrit serait pire que pas de corpus du tout — il aurait l'air complet. Sont refusés : un code de compétence ou de type d'erreur absent du référentiel, une justification vide, un `ATT` confirmé, un couple en double, un état autre qu'hypothèse ou confirmation.

**Un bug de fond corrigé au passage.** `Session.Meta` construisait une contrainte à partir d'un `frozenset` : l'ordre d'itération changeant d'une exécution à l'autre, `makemigrations` croyait la contrainte modifiée **à chaque appel** et produisait une migration parasite — c'est l'origine des migrations 0003 et 0004, qui ne font rien d'autre. `sorted()` au lieu de `list()` : un second `makemigrations` ne détecte plus rien.

**Deux limites à connaître, consignées dans la fiche du module :**
1. Le module 4 **ne devra jamais écrire** dans les problèmes d'une évaluation du corpus. Un étalon qu'on corrige au fur et à mesure ne mesure plus rien.
2. Pour une copie de l'**ancien format**, aucune `Reponse` n'est enregistrable — ce modèle exige une clé étrangère vers les 280 questions Urie, qu'une ancienne copie n'a pas. Seuls les `Probleme` le sont, et c'est suffisant : c'est l'unité que le module 4 produit.

**Vérifié :** 16 tests dédiés, cycle de migration testé dans les deux sens. **186 Django + 242 pytest = 428 tests passent.**

**Reste :** réunir les copies (**1 sur 5**) et faire le tagage lui-même.

### 2026-07-31 (suite) — Format des sujets confirmé, lecture rendue tolérante (D-CEO-35)
**Question posée, réponse obtenue :** les sujets v2 **conservent leurs cadres ancrés et leurs codes de question**. `TEST 4 3e.pdf` était une copie d'archive de l'ancien format, pas une préfiguration des sujets à venir. La conception du module 2 tient donc telle quelle — il ne lui manque que le recalage.

**Conséquence à ne pas perdre :** le format à cadres ancrés n'est plus une commodité de mise en page, c'est **une dépendance du diagnostic structuré**. Un sujet sans cadres ni codes ne peut pas être découpé en zones, donc ne peut pas alimenter le module 4. Toute régénération des sujets doit les conserver — c'est acté en D-CEO-35.

**Adaptation faite dans la foulée.** Les règles de lecture étaient collées aux valeurs relevées sur les 7 PDF d'aujourd'hui : gris exactement 0,478431, largeur supérieure à 480 pt, exactement 8 lignes pour une rédaction. Le sujet est un document vivant : régénéré, il changera de marges et de teintes. Les règles sont désormais exprimées en **plages de gris** et en **fractions de la largeur de page**, et toute question de plus de 2 lignes est une rédaction. Ce qui était en jeu : avec des valeurs exactes, une simple retouche du gabarit d'impression aurait fait échouer la lecture **totalement** — zéro cadre trouvé, module 2 arrêté net — et non partiellement.

**Vérifié :** les 280 cadres des 7 sujets sont toujours retrouvés avec les règles tolérantes, et 2 tests verrouillent la tolérance (une teinte différente, une rédaction à 6 lignes). 24 tests sur les zones, **170 Django + 242 pytest = 412 tests passent**.

### 2026-07-31 (suite) — Un scan réel, et ce qu'il a corrigé dans la conception
**Contrainte posée :** le scan se fait **hors plateforme**. Ce qui entre est un **PDF multipage ou des images** — jamais un flux scanner piloté par l'application. Pris en compte : `resolution_scan()` donne la définition native de la source, et `ingest_pdf` accepte désormais un `dpi` (150 reste le défaut, D-CEO-10) pour ne pas rendre un scan 200 DPI dans une image 150 DPI, puis recadrer au dixième de page ce qui a déjà été dégradé.

**Le fichier reçu (`TEST 4 3e.pdf`) est un test de l'ancien format**, pas un sujet Urie : pas de cadres ancrés, pas de codes de question, dotté de pointillés et déjà corrigé au stylo rouge. Il ne peut pas servir de pièce d'essai au module 2 — il n'y a aucun gabarit sur lequel le recaler. Il reste précieux pour deux autres choses : il **calibre le côté scan** (tableau dans la fiche du module 2), et c'est exactement le matériau que demande le **module 3** (« rassembler ≥5 anciennes copies »).

**Ce que les mesures ont changé :**
- **Le recalage ne peut pas s'appuyer sur le rectangle de la page.** La hauteur varie de **835 à 851 pt d'une feuille à l'autre du même fichier**, et la largeur est de 612 pt là où le sujet en fait 595,3. Une mise à l'échelle sur les bords de page serait fausse de 2 à 3 %. L'ancrage doit se faire sur le **contenu** — les cadres eux-mêmes.
- **L'inclinaison varie d'une page à l'autre** (−1,25°, −1,25°, +1,00°) : redressement par page, jamais global.
- **La correction de l'enseignant est séparable par la couleur** (2,3 % de pixels rouges contre 22 % de bleu élève et 75 % d'imprimé neutre). Sur une ancienne copie corrigée à la main, un diagnostic qui ignore la couleur lit la correction du professeur comme la production de l'élève. À traiter au module 3.
- **Le scan compte 12 pages pour un sujet de 10** (page de garde, page de renseignements) : l'appariement page scannée ↔ page du sujet ne peut pas être supposé 1:1.

**Ajouté en conséquence :** `decouper_zones` **refuse** une page dont les proportions ne sont pas celles du sujet. Sans ce garde-fou, un scan brut se découpait sans rien signaler, avec un décalage de plusieurs millimètres en bas de page — assez pour attraper la ligne de la question voisine, pas assez pour que le résultat ait l'air faux.

**Données personnelles :** ce scan porte le nom complet d'une élève, son établissement et un numéro de téléphone. Il n'est **pas** versionné et n'a pas été copié dans le dépôt. C'est le point ouvert #4 sous sa forme concrète, plus une question de principe.

**Essai de bout en bout sur le scan reçu**, pour voir ce qui tient sur du vrai matériel :
1. `resolution_scan` → **200 DPI**, et le rendu se fait à 200 au lieu de 150. ✅
2. `ingest_pdf` → **12 pages** extraites (1700×2348, 1700×2356… — les hauteurs diffèrent d'une page à l'autre, comme mesuré). ✅
3. `decouper_zones` contre le gabarit du sujet 3ème → **refusé**, avec le motif exact : « 2,3 % d'écart entre les échelles horizontale et verticale ». Le garde-fou fonctionne sur du matériel réel, c'était son objet. ✅
4. Nettoyage appliqué à de vrais pixels scannés → **l'écriture de l'élève ressort intacte**, mais **les lignes pointillées imprimées survivent** (8,8 % de pixels conservés). ⚠️

**Le point 4 est le résultat qui compte, et c'est une mauvaise nouvelle utile.** Ces pointillés sont imprimés en noir : le seuillage ne pouvait pas les enlever, et il ne le prétendait pas. Mais il ouvre une question que le rendu numérique du PDF ne pouvait pas poser — **une imprimante laser rend un aplat gris 0,749 par un tramage de points noirs**, pas par un gris uniforme. Si c'est le cas, les lignes de guidage des sujets Urie se comporteront une fois imprimées comme ces pointillés, et `decouper_zones` les laissera passer alors que tous ses tests passent sur le PDF d'origine. **Le seuillage seul ne suffira peut-être pas** ; le repli est l'effacement par **position connue**, puisque le gabarit porte déjà la position exacte de chaque ligne.

**Vérifié :** 22 tests sur les zones, **170 Django + 240 pytest = 410 tests passent**.

**Prochaine étape :** le recalage, dès qu'un sujet Urie imprimé aura été scanné. **Le même scan tranche le risque du point 4** — même vierge, il suffit à mesurer le gris des lignes imprimées. En attendant, le **Module 3** est le seul chantier qui n'attend rien, et le fichier reçu en est la première pièce.

### 2026-07-31 (suite) — Module 2 : le gabarit ne se devine pas, il se lit
**La question qui a décidé du module :** faut-il détecter les cadres sur le scan, comme le prescrit `guide-urie.md` ? **Non.** Les 7 sujets sont produits par WeasyPrint et leur PDF porte la position exacte de chaque cadre et son code. Vérifié avant d'écrire la moindre ligne : **280/280 cadres retrouvés sur les 7 sujets**, 0 manquant, 0 en trop, 0 doublon, et le nombre de lignes de guidage concorde avec le format annoncé par le barème sur les 280 (qcm 71 × 1 ligne, court 139 × 2, redige 63 × 8, construction 7 × 0).

Conséquence : **l'OCR disparaît de la chaîne.** C'était le premier point de panne — trois caractères à 150 DPI, à côté de l'écriture d'un élève —, et une confusion `G1`/`G7` aurait attribué une réponse à la mauvaise question sans que rien ne le signale. Le seul problème qui reste sur le scan est le recalage.

**La signature graphique des sujets, relevée sur pièces** (c'est elle qui rend le gabarit lisible) : les cadres sont des aplats gris, pas des traits. Bord **0,478** pour les cadres à lignes, **0,600** pour les cadres vides de `construction`, lignes de guidage **0,749**. Le code de la question est imprimé **deux fois** — en marge à côté de l'énoncé, et à l'intérieur du cadre en haut à gauche : c'est l'inclusion dans le rectangle qui les départage, rien d'autre.

**Deux choses trouvées en écrivant les tests, qui auraient coûté cher plus tard :**
1. **Le code imprimé dans le cadre est noir**, donc indiscernable de l'écriture au seuillage. Laissé en place, il met de l'encre dans toute zone découpée et **aucune copie vierge n'aurait jamais été reconnue comme telle**. Il est maintenant effacé à partir de sa position exacte, elle aussi lue dans le PDF.
2. **`numpy` n'était pas déclaré** dans `requirements.txt` — il n'arrivait que par `pandas`, qui part avec Streamlit. Le retrait du filet aurait cassé la découpe. Déclaré explicitement.

**Livré :** `src/pipeline/zones.py` — `extraire_gabarit`, `verifier_gabarit`, `decouper_zones`. Indépendant du framework. La découpe blanchit le fond plutôt que de binariser franchement (un trait de crayon clair reste lisible pour un modèle de vision), et signale les zones vierges : « pas de réponse » est une donnée de diagnostic à part entière, et ça évite d'envoyer une image blanche au modèle.

**`verifier_gabarit` est un garde-fou d'exploitation, pas une aide au développement :** le format est déduit de la géométrie du cadre, jamais lu dans le barème, puis les deux sont confrontés. Si un enseignant scanne un sujet d'une autre version que celle chargée en base, les codes ou les formats divergent — et on l'apprend avant d'attribuer des réponses aux mauvaises questions.

**Vérifié :** `tests/test_zones.py`, 20 tests. 13 tournent sur un sujet fabriqué dans le test lui-même, qui reproduit la signature graphique des vrais — les 7 sujets sont des PDF non versionnés, la CI ne les a pas. Les 7 autres vérifient les 280 cadres réels contre les barèmes, et sont **ignorés** faute de fichiers plutôt que de tomber en échec. **170 tests Django + 238 pytest = 408 tests passent.**

**Bloqué par :** une copie **imprimée, remplie à la main, scannée**. Le recalage et le seuil d'encre ne peuvent pas être calibrés sur un rendu numérique parfait — il n'y a rien à y redresser, et le contraste y est idéal. Consignes d'impression rappelées sur `/sujets/` : noir et blanc, recto seul, **sans réduction**.

**Prochaine étape :** avec un scan, le recalage puis la calibration du seuil. Sans scan, le **Module 3** (corpus de référence) peut avancer en parallèle — il ne dépend que du module 1 et se fait à la main.

### 2026-07-31 — Le travail est versionné
Le socle Django n'était pas suivi par git : rien n'avait été commité depuis le **2026-07-23**, une semaine de travail ne tenait que sur un disque. Corrigé — **10 commits découpés par domaine** sur la branche `chantier/urie-v2-django`, poussée sur `origin`.

Découpage : nettoyage des documents périmés · socle Django + authentification · `referentiel/` (module 1) · `suivi/` (modules 1 et 6) · `suivi_web/` · `correction_web/` · extraction de la logique métier hors de l'interface · scripts et barèmes · mise en service · documentation.

**Branche plutôt que `main`** : `main` est partagée avec le collègue (l'historique porte plusieurs fusions) et cette semaine de travail n'a pas été relue. Le rattrapage sera un fast-forward.

**Vérifié avant de commiter :** aucun secret n'entre dans le dépôt (`.env`, `credentials/`, `*.json`, `logs/`, `runs/`, `dev.db` couverts par `.gitignore` — les 138 fichiers ajoutés ont été scannés) ; les 22 suppressions étaient bien intentionnelles (doc périmée et sources remplacées). **170 tests Django + 218 pytest = 388 tests passent** sur l'arbre commité.

**Reste inchangé :** l'essai réel de bout en bout, toujours en attente de clés API. **Prochaine étape technique : Module 2.**
