# Architecture cible — sortir de Streamlit
**Document de recommandation · 2026-07-30 · décision non prise**

Répond à deux questions posées ensemble : comment régler définitivement le problème des accents, et sur quoi construire la suite du produit.

---

# Partie 1 — Les accents

## Ce que c'est vraiment

Ce n'est **pas** un problème d'encodage, ni de Streamlit, ni de police. C'est un **défaut de saisie dans le classeur**, et la preuve en est que le classeur se contredit lui-même :

| Mot | Écrit sans accent | Écrit avec accent, dans le même fichier |
|---|---|---|
| après | 34 fois | 36 fois |
| carré | 29 fois | 10 fois |
| coordonnées | 31 fois | 7 fois |
| appliquée | 42 fois | 7 fois |

L'auteur a bien tapé des accents — 204 mots distincts en portent. Les formes nues sont des oublis, pas une convention.

**Périmètre mesuré** sur les colonnes destinées à être lues par un humain (`02_Competences`, `04_Questions`, `05_Grille_diagnostic`, `06_Distracteurs`) : 2 314 mots distincts, dont **150 à corriger** et **16 à arbitrer**.

## Pourquoi la correction automatique est un piège

L'idée naturelle — replier les accents et remplacer par la forme accentuée trouvée ailleurs — produit du faux français. Pour 16 mots, la forme **sans** accent est elle-même un mot français valide, et seule l'intention de l'auteur tranche :

| Écrit | Peut vouloir dire | Le piège |
|---|---|---|
| `calcule` | « je calcule » **ou** « calculé » | les deux existent |
| `eleve` | « élève » (l'apprenant) **ou** « élevé » (au carré) | contresens pédagogique |
| `cote` | « côté » (géométrie), « côte », « coté », **ou** « cote » (dimension) | 4 lectures |
| `a` | « a » (verbe avoir, 423 fois) **ou** « à » | la forme nue est le plus souvent correcte |

Un remplacement à l'aveugle écrirait « élevé au carré » là où il fallait « élève », dans un libellé lu par un parent. C'est exactement la règle du projet — **ne jamais deviner une donnée** — appliquée au texte.

## La solution retenue : corriger la source, garder un garde-fou

**1. Corriger dans le classeur, pas dans le code.** Le classeur doit de toute façon être relu par un enseignant de mathématiques avant d'être figé (`00_Notice` : « À VALIDER »). Les accents se corrigent dans le même passage. C'est le seul endroit où la correction est définitive : toute couche de rattrapage dans le code devrait être maintenue indéfiniment.

**2. Fournir la liste exacte.** `scripts/verifier_accents.py --rapport` produit `docs/accents_a_corriger.md` : chaque mot, sa correction, son nombre d'occurrences, les onglets concernés, et les 16 ambigus séparés avec leur piège explicité. C'est un document remettable tel quel.

**3. Verrouiller par un test.** `tests/test_accents_referentiel.py` fixe les plafonds actuels (150 / 16). Si une mise à jour du classeur **ajoute** des mots non accentués, la suite échoue. Si le classeur **s'améliore**, le test échoue aussi — pour forcer l'abaissement du plafond, sinon le garde-fou se relâcherait et laisserait passer une régression future.

C'est ce troisième point qui répond au « une bonne fois » : le problème ne peut plus revenir sans être vu. C'est précisément ce qui manquait aux `chunk_ids` cassés de l'ancien système, journalisés en `logger.debug` et donc invisibles pendant des mois.

**4. Si la source HTML des sujets est retrouvée**, elle donne les énoncés exacts avec accents et formules — les 150 mots disparaissent d'un coup. Cela vaut d'être demandé.

---

# Partie 2 — Sortir de Streamlit

## L'intuition est juste, et le moment est le bon

Deux mesures le montrent.

**Le code est déjà mal réparti.** `src/ui/app.py` fait **2 876 lignes** — 26 % de tout le code du projet — avec 41 fonctions, 342 appels `st.*`, 71 usages de `session_state` et 30 blocs HTML injectés en chaînes de caractères. C'est un monolithe qui va grossir avec les modules 8 et 9.

**Mais l'essentiel est déjà portable.** Sur 10 837 lignes dans `src/` :

| Couche | Lignes | Dépend de Streamlit ? |
|---|---|---|
| `src/api/` (5 clients LLM) | 2 751 | non |
| `src/pipeline/` | 2 300 environ | non |
| `src/knowledge/`, `src/models/`, `src/core/` | 1 400 environ | non |
| `src/services/`, `src/db/`, `src/integrations/` | 1 100 environ | non |
| **`src/ui/` (app.py + progress.py)** | **3 204** | **oui** |

**70 % du code migre sans être touché.** Les parties chères — clients IA, pipeline, RAG, génération PDF, intégration Sheets — sont indépendantes du framework. Une migration ne réécrit que la couche de présentation.

**Et surtout : les 11 tables du chantier Urie v2 ne sont pas encore écrites.** Seules `copie` et `document` existent. Si l'ORM doit changer, **c'est maintenant le moment le moins coûteux** — écrire 11 modèles SQLAlchemy + une migration Alembic pour les réécrire ensuite serait du travail jeté.

## Ce que Streamlit ne peut pas porter, concrètement

Ce ne sont pas des reproches génériques : chaque point bloque une exigence écrite du chantier.

**1. L'authentification n'est pas réelle — c'est le risque le plus sérieux.** Aujourd'hui : nom + PIN à 4 chiffres stocké **en clair** dans un Google Sheet, état de connexion dans `session_state`. Pas de jeton de session, pas d'expiration, pas de protection CSRF, pas d'autorisation vérifiée par requête. Or le dispositif conserve des **données scolaires nominatives d'élèves mineurs sur sept mois** (point ouvert #4 : obligations à vérifier auprès de la CIL du Burkina Faso). Streamlit n'offre aucun modèle de session ou de permission sur lequel bâtir — il faudrait tout écrire à la main, ce qui est précisément ce qu'il ne faut pas faire seul sur des données de mineurs.

**2. Le script entier se relance à chaque interaction.** Le tableau de validation du module 8 = 40 lignes × (choix + saisie de note) + aperçus d'images découpées. Chaque clic réexécute 2 876 lignes. Les 71 usages de `session_state` sont déjà des contournements de ce modèle.

**3. Le mobile est une exigence, pas un confort.** Le module 8 demande qu'« un tuteur remplisse une fiche de séance depuis son téléphone en moins de deux minutes » et note qu'« une fiche qui exige un ordinateur ne sera pas remplie ». Streamlit est faible sur mobile et ne laisse presque aucun contrôle sur le rendu.

**4. Pas d'URL.** Impossible de partager le lien d'un profil d'élève, d'une session, d'un rapport. Pour un outil à trois rôles (tuteur, responsable, admin) et des rapports destinés aux parents, c'est structurant.

**5. L'interface n'est pas testable.** `tests/test_ui_math.py` ne parvient même pas à s'importer sans `.env`, parce qu'`app.py` construit la configuration au chargement du module. 30 blocs de HTML en concaténation de chaînes ne se testent pas.

**6. Le pipeline bloque.** Les appels LLM durent des dizaines de secondes ; c'est déjà contourné par des threads.

## Recommandation : Django + HTMX

**Django** pour le socle, **HTMX** pour l'interactivité — sans framework JavaScript séparé.

### Pourquoi Django plutôt que FastAPI

| Besoin du projet | Django | FastAPI |
|---|---|---|
| Auth, sessions, permissions par rôle | intégré, éprouvé, audité | à écrire entièrement |
| Administration des 11 tables du référentiel | `admin` quasi gratuit | à écrire entièrement |
| ORM + migrations | intégrés | SQLAlchemy + Alembic (déjà en place, mais 2 tables seulement) |
| Formulaires, validation, CSRF | intégrés | à écrire |
| Stabilité sur 5–10 ans | LTS, compatibilité ascendante tenue depuis 20 ans | jeune, évolue vite |

Deux arguments pèsent lourd ici.

**L'`admin` Django n'est pas un gadget dans ce projet.** Le référentiel fait 11 tables relationnelles — compétences, prérequis, questions, signatures d'erreur, distracteurs, coûts, problèmes, transitions. Il faut pouvoir les parcourir, les filtrer, corriger une ligne. Django le donne en déclarant quelques classes. En FastAPI, c'est plusieurs semaines d'écrans à écrire à la main — une part significative du module 8.

**L'authentification est un enjeu de conformité, pas de confort.** Sur des données de mineurs, hériter d'un système de sessions et de permissions éprouvé vaut infiniment mieux que d'en écrire un.

### Pourquoi HTMX plutôt que React

Les besoins interactifs réels sont modestes : un tableau de validation, une fiche de séance à 5 champs, des tableaux de bord. HTMX les couvre entièrement, avec un seul langage, une seule base de code, aucune chaîne de build npm, et du HTML rendu côté serveur — donc léger, ce qui compte sur une connexion faible. React imposerait deux codebases à une équipe d'une personne, pour un bénéfice nul ici.

### Ce qui ne bouge pas

`src/api/`, `src/pipeline/`, `src/knowledge/`, `src/models/`, `src/core/`, `src/integrations/` migrent **sans modification**. Les modèles Pydantic de `src/models/domain.py` restent les objets de transport du pipeline — ils ne sont pas concurrents de l'ORM Django, qui ne gère que la persistance.

## Séquencement proposé

Le guide est explicite : « un seul chantier peut être prioritaire pour une seule personne ». Il ne faut donc **pas** mener la migration et les modules Urie en parallèle.

| # | Étape | Pourquoi à ce moment |
|---|---|---|
| 1 | **Accents** — remettre `docs/accents_a_corriger.md` au docteur | Indépendant, sans code, peut avancer en parallèle chez quelqu'un d'autre |
| 2 | **Décider du framework** | Point de non-retour : l'étape 3 écrit l'ORM |
| 3 | **Squelette Django + les 11 tables + import du référentiel + `admin`** — c'est le module 1, fait directement dans la cible | Les tables n'existent pas encore : coût de bascule quasi nul aujourd'hui, élevé dans deux semaines |
| 4 | **Migrer les écrans existants** (connexion, tableaux de bord, correction) et retirer Streamlit | Une seule interface en service, pas deux à maintenir |
| 5 | **Modules 2 à 9 dans Django** | — |

**Sur l'étape 3 et 4 :** pendant l'étape 3, Streamlit continue de tourner sur le flux de correction existant. Les deux applications lisent la même base Postgres, mais sans recouvrement — Django possède les nouvelles tables, Streamlit garde `copie` et `document`. Ce chevauchement est tenable parce qu'il est court et sans écriture croisée ; il ne faut pas le laisser s'installer.

**Ordre de grandeur honnête :** migrer 3 204 lignes d'interface, c'est plusieurs semaines à une personne. Ce n'est pas une après-midi. La contrepartie est qu'on ne le paiera qu'une fois, et que 70 % du code est épargné.

## Contraintes tranchées (2026-07-30)

| Point | Décision | Effet sur l'architecture |
|---|---|---|
| **Hors ligne** | ❌ non — connexion Internet requise | Rendu serveur simple. Pas de file d'attente locale, pas de synchronisation, pas de résolution de conflits. **Simplification majeure.** |
| **PWA** | ❌ non | Pas de service worker, pas de manifeste, pas de cache applicatif. HTML + HTMX suffisent. |
| **Localisation des données** | Neon, inchangé | La base ne bouge pas. Les modèles Django pointent sur la même instance Postgres. |

Ces trois réponses **lèvent la seule réserve** qui pesait sur la recommandation : sans besoin hors ligne, aucune API explicite n'est nécessaire, et Django REST Framework devient inutile. **Django + HTMX en rendu serveur est la bonne réponse, sans nuance.**

Conséquence concrète : le module 8 (« un tuteur remplit sa fiche depuis son téléphone en moins de deux minutes ») se traite par une page HTML responsive à 5 champs — quelques dizaines de lignes de gabarit, pas une application installable.

## Ce qui reste à décider

**Où tournera l'application.** C'est le seul point pratique encore ouvert. Neon héberge la **base**, pas l'application. Aujourd'hui Streamlit tourne **en local** sur la machine de l'utilisateur (`streamlit run`, pas de `Procfile`, `runtime.txt` seul vestige d'un déploiement envisagé). Une application Django multi-utilisateurs — tuteurs sur téléphone, responsables, admin — suppose une adresse joignable. À trancher : hébergeur, nom de domaine, certificat HTTPS (obligatoire dès qu'un PIN transite), sauvegardes.

> **À noter pour le point ouvert #4 (données de mineurs) :** dès que l'application quitte le poste local pour un serveur, les données nominatives transitent sur le réseau et deviennent accessibles depuis l'extérieur. HTTPS n'est plus une option, et le remplacement du PIN en clair par un vrai système d'authentification devient urgent — c'est précisément ce que Django apporte.

**Le calendrier.** S'il existe une échéance proche (une campagne de tests avec de vrais élèves), mieux vaut la passer sur Streamlit et migrer juste après, plutôt que d'être à mi-migration au mauvais moment.

---

## Résumé

| Question | Réponse |
|---|---|
| Les accents | Défaut de données dans le classeur, pas de code. Corriger à la source (liste fournie : `docs/accents_a_corriger.md`), ne **jamais** corriger automatiquement (16 mots ambigus produiraient du contresens), verrouiller par test pour que ça ne revienne pas. |
| Le framework | **Django + HTMX.** Auth et `admin` répondent aux deux vrais risques du projet : la conformité sur des données de mineurs, et le volume d'écrans du module 8. |
| Le moment | **Maintenant, avant le module 1.** Les 11 tables ne sont pas écrites : le coût de bascule est aujourd'hui à son minimum. |
| Le coût | ~30 % du code (3 204 lignes d'interface). Les 70 % restants — pipeline, IA, RAG, PDF, Sheets — migrent intacts. |
| Contraintes tranchées | Pas de hors ligne · pas de PWA · Neon inchangé → rendu serveur simple, pas d'API séparée. La réserve sur la connectivité est levée. |
| Reste à décider | **Où héberger l'application** (Neon ne fournit que la base ; l'app tourne aujourd'hui en local) + HTTPS obligatoire dès qu'un PIN transite. |
