# Analyse comparative des fournisseurs IA — Choix par tâche

**Hakili Lab — Document technique**
**Date : 2026-06-05 (mis à jour 2026-06-11)**

---

## Contexte et contrainte de départ

Le prototype initial utilisait **Claude Opus 4.7 exclusivement** pour toutes les tâches.
Coût observé sur une copie réelle de 15-20 pages : **~$8.00/copie**.

Pour un déploiement sur 3 classes × 6 évaluations × 30 élèves = 540 copies/an, ce coût représentait **~$4 300/an** — hors de portée pour un établissement scolaire.

**Objectif :** identifier le meilleur modèle par tâche, en priorisant qualité d'abord, puis coût.

---

## 1. Cartographie des tâches et leurs exigences

| # | Tâche | Type | Vision ? | Exigence principale |
|---|---|---|---|---|
| 1 | Transcription | Multimodale | ✅ Oui | Précision sur manuscrit + formules |
| 2 | Correction | Raisonnement structuré | ❌ Non | Logique mathématique + JSON fiable |
| 3 | Diagnostic | Analyse de fond | ❌ Non | Inférence causale multi-étapes |
| 4 | Remédiation | Génération créative | ❌ Non | Qualité du français académique |
| 5 | Extraction barème | Vision + JSON | ✅ Oui | Extraction structurée depuis PDF |
| 6 | Extraction énoncé | Vision + texte | ✅ Oui | Transcription fidèle |

---

## 2. Tableau comparatif des modèles candidats

### Tarifs de référence (juin 2026, USD par million de tokens)

| Modèle | Input | Output | Vision | Tier gratuit |
|---|---|---|---|---|
| Claude Opus 4.7 | $5.00 | $25.00 | ✅ | ❌ |
| Claude Sonnet 4.6 | $3.00 | $15.00 | ✅ | ❌ |
| Claude Haiku 4.5 | $1.00 | $5.00 | ✅ | ❌ |
| **Gemini 2.5 Flash** | **$0.10** | **$0.40** | **✅** | **✅ 1M tok/j** |
| Gemini 2.0 Flash | $0.10 | $0.40 | ✅ | ✅ 1M tok/j |
| GPT-4o | $2.50 | $10.00 | ✅ | ❌ |
| GPT-4o mini | $0.15 | $0.60 | ✅ | ❌ |
| Mistral Small 3.1 | $0.10 | $0.30 | ✅ | ❌ |
| Mistral Large 2 | $2.00 | $6.00 | ✅ | ❌ |
| **DeepSeek V3** | **$0.27** | **$1.10** | ❌ | ❌ |
| **DeepSeek R1** | **$0.55** | **$2.19** | ❌ | ❌ |
| Llama 3.2 11B Vision (Groq) | $0.18 | $0.18 | ✅ | ❌ |

### Performances sur le raisonnement mathématique (benchmark MATH-500)

| Modèle | Score MATH-500 | Catégorie |
|---|---|---|
| **DeepSeek V3** | **~90%** | Leader |
| Claude Opus 4.7 | ~82% | Très bon |
| GPT-4o | ~76% | Bon |
| Claude Sonnet 4.6 | ~78% | Bon |
| GPT-4o mini | ~70% | Correct |
| Gemini 2.0 Flash | ~72% | Correct |
| Mistral Small 3.1 | ~65% | Correct |

---

## 3. Analyse par tâche

### Tâche 1 — Transcription *(vision multimodale, critique)*

**Gagnant : Gemini 2.5 Flash**

Gemini a été conçu comme un modèle multimodal natif — vision et texte sont traités conjointement depuis la pré-entraînement, contrairement aux modèles texte auxquels la vision a été ajoutée ultérieurement. Cette architecture native confère une meilleure compréhension des mises en page mathématiques complexes (fractions, exposants, tableaux).

Arguments techniques :
- Contexte de 1 000 000 tokens → toute la copie dans une seule session possible
- Tier gratuit : 15 RPM et 1M tokens/jour → **$0 pour le volume d'une école**
- Batch natif : traite 3 pages par appel (vs 1 page pour Claude sans optimisation)

Candidats écartés :
- **GPT-4o** : excellent mais 25× plus cher, aucun tier gratuit
- **Llama 3.2 Vision** : modèle 11B insuffisant pour formules manuscrites complexes
- **OCR local (Tesseract, EasyOCR)** : ~60% CER sur formules manuscrites vs ~10-15% pour LLM — rejeté définitivement

```
Décision : Gemini 2.5 Flash  →  $0/copie (tier gratuit)
```

---

### Tâche 2 — Correction selon barème *(raisonnement mathématique structuré)*

**Gagnant : DeepSeek V3**

DeepSeek V3 est entraîné massivement sur des corpus mathématiques (compétitions, manuels, exercices) et atteint ~90% sur MATH-500 — score supérieur à Claude Opus 4.7 (~82%) à un coût 18× inférieur en output. L'API DeepSeek est compatible OpenAI, ce qui simplifie l'intégration.

Arguments techniques :
- `response_format: {"type": "json_object"}` → JSON garanti
- Excellente capacité à suivre des instructions précises (application stricte d'un barème)
- Prix : $0.27/$1.10 par MTok — rapport qualité/prix inégalé pour le raisonnement math

Candidats écartés :
- **Claude Sonnet 4.6** : bon mais 3× plus cher en input, 14× en output vs DeepSeek V3
- **GPT-4o mini** : légèrement inférieur sur math, sans avantage de coût

Note sur la confidentialité : les données transmises à DeepSeek (transcription + barème) ne contiennent pas d'informations sensibles — les noms fréquents en contexte burkinabè (ex. Ouedraogo Moussa : >2 000 personnes) n'identifient pas un individu.

```
Décision : DeepSeek V3  →  ~$0.005/copie
```

---

### Tâche 3 — Diagnostic des causes cachées *(analyse multi-étapes)*

**Gagnant : Claude Opus 4.7** *(décision révisée 2026-06-11)*

**Décision initiale (2026-06-05) :** DeepSeek R1.
**Décision révisée (2026-06-11) :** **Claude Opus 4.7** — configuré comme `DIAGNOSTIC_PROVIDER=claude` dans `.env`.

**Justification de la révision :** Le diagnostic est la tâche la plus complexe du pipeline — elle requiert de raisonner sur plusieurs erreurs simultanément, d'identifier des causes cachées (ex. confusion de signe lors du transposement), et de produire un JSON structuré précis incluant `CompetencyGap` avec des `chunk_ids` ancrés sur le curriculum RAG. Claude Opus 4.7 produit une meilleure fidélité de structure JSON et un meilleur ancrage sur les données RAG injectées dans le contexte.

DeepSeek R1 reste une option valide via `DIAGNOSTIC_PROVIDER=deepseek` mais nécessite un prompting plus défensif (pas de system message, pas de response_format JSON forcé).

```
Décision : Claude Opus 4.7  →  ~$0.008/copie
```

---

### Tâche 4 — Génération du sujet de remédiation *(français académique)*

**Gagnant : Mistral Small 3.1**

Mistral AI est une société française. Ses modèles sont entraînés sur des corpus pédagogiques francophones natifs — manuels scolaires français, annales, exercices corrigés. Cette imprégnation se traduit par :

- Vocabulaire pédagogique natif (*"On pose", "Montrer que", "En déduire", "Soit f définie sur"*)
- Terminologie mathématique conforme au programme francophone (CEDEAO/UEMOA)
- Structure d'énoncé cohérente avec les habitudes des élèves burkinabè
- Absence de calque de l'anglais dans les formulations mathématiques

À $0.10/$0.30 par MTok, Mistral Small 3.1 est également très compétitif en coût.

```
Décision : Mistral Small 3.1  →  ~$0.003/copie
```

---

### Tâches 5 & 6 — Extraction barème + énoncé *(vision)*

Même profil que la transcription — tâches de vision sur documents PDF. Gemini 2.0 Flash reste le choix optimal. Ces tâches ne sont exécutées qu'une fois par session (pas par page), leur coût est négligeable.

Extraction barème/énoncé reste sur **Claude Sonnet** pour garantir la robustesse des appels `tool_use` forcé — ces extractions nécessitent un JSON très précisément structuré (IDs de questions, hiérarchie parent/enfant).

```
Décision : Claude Sonnet 4.6 (barème/énoncé)  →  ~$0.01/copie
```

---

## 4. Architecture finale du pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE HAKILI LAB                             │
│                                                                     │
│  [PDF scan 150 DPI]                                                 │
│          │                                                          │
│          ▼                                                          │
│  TRANSCRIPTION ──── Gemini 2.0 Flash ─────── $0.00/copie           │
│          │          (vision native, 3 pages/appel, tier gratuit)    │
│          │                                                          │
│          ▼                                                          │
│  CORRECTION ─────── DeepSeek V3 ──────────── $0.005/copie          │
│          │          (MATH-500 ~90%, json_object forcé)              │
│          │                                                          │
│          ▼                                                          │
│  DIAGNOSTIC ─────── Claude Opus 4.7 ──────── $0.008/copie          │
│          │          (raisonnement profond, causes cachées + RAG)    │
│          │                                                          │
│          ▼                                                          │
│  REMÉDIATION ────── Mistral Small 3.1 ─────── $0.003/copie         │
│                     (français académique natif)                     │
│                                                                     │
│  BARÈME/ÉNONCÉ ──── Claude Sonnet 4.6 ─────── $0.010/copie         │
│                     (tool_use forcé, extraction structurée)         │
├─────────────────────────────────────────────────────────────────────┤
│  TOTAL ESTIMÉ                                  ~$0.02/copie         │
└─────────────────────────────────────────────────────────────────────┘
```

**Fallback automatique :** si une clé API est absente ou si le provider échoue (quota, solde, réseau), le pipeline bascule sur Claude — aucune interruption.

| Tâche | Fallback | Modèle Claude |
|---|---|---|
| Transcription | Claude | Sonnet 4.6 |
| Correction | Claude | Sonnet 4.6 |
| Diagnostic | Claude | Haiku 4.5 |
| Remédiation | Claude | Sonnet 4.6 |

---

## 5. Modèle de coût annuel

**Hypothèse : 3 classes × 6 évaluations × 30 élèves × 17 pages = 9 180 pages, 540 copies/an**

### Volume Gemini (tier gratuit)
- 9 180 pages × 1 500 tokens/page = **13,77 M tokens/an**
- Répartis sur ~180 jours scolaires = **76 500 tokens/jour**
- Tier gratuit = **1 000 000 tokens/jour** → marge ×13 → **$0/an**

### Coût DeepSeek (correction + diagnostic)
| Étape | Input estimé | Output estimé | Coût/copie | Coût/an |
|---|---|---|---|---|
| Correction (V3) | ~12 000 tok | ~4 000 tok | $0.0076 | $4.10 |
| Diagnostic (R1) | ~5 000 tok | ~2 000 tok | $0.0072 | $3.89 |

### Coût Mistral (remédiation)
| Étape | Input estimé | Output estimé | Coût/copie | Coût/an |
|---|---|---|---|---|
| Remédiation | ~3 000 tok | ~4 000 tok | $0.0022 | $1.19 |

### Coût Claude (barème/énoncé)
| Étape | Fréquence | Coût estimé/an |
|---|---|---|
| Extraction barème | 1 fois/évaluation (18/an) | ~$0.50 |
| Extraction énoncé | 1 fois/évaluation | ~$0.50 |

### Récapitulatif annuel

| Provider | Tâche | Coût/an |
|---|---|---|
| Gemini 2.0 Flash | Transcription (9 180 pages) | **$0** |
| DeepSeek V3 | Correction (540 copies) | **$4.10** |
| DeepSeek R1 | Diagnostic (540 copies) | **$3.89** |
| Mistral Small 3.1 | Remédiation (540 copies) | **$1.19** |
| Claude Sonnet 4.6 | Barème + Énoncé (36 extractions) | **$1.00** |
| **TOTAL** | | **~$10–15/an** |

**Réduction de coût vs pipeline initial :** $4 300/an → **$12/an = réduction ×360**

---

## 6. Risques et mitigations

| Risque | Probabilité | Mitigation |
|---|---|---|
| Gemini free tier dépassé (école > 300 élèves) | Faible | Passer au tier payant : $2/an supplémentaires |
| Gemini free tier indisponible selon région | **Constaté** | Fallback automatique Claude · voir §8 |
| DeepSeek solde insuffisant | **Constaté** | Fallback automatique Claude · voir §8 |
| Qualité Mistral insuffisante pour exercices complexes | Faible | Migrer vers Mistral Large 2 ($6/MTok output) |
| DeepSeek R1 lent (raisonnement) | Moyen | Latence ~10-20s acceptable (non bloquant) |

---

## 7. Décision retenue

> **Architecture multi-provider avec routing automatique basé sur les clés API disponibles.**
>
> Chaque provider est sélectionné pour la tâche où son avantage est le plus décisif :
> - Gemini → vision gratuite et native
> - DeepSeek → raisonnement mathématique leader
> - Mistral → génération pédagogique en français
> - Claude → fiabilité sur extraction structurée (tool_use)
>
> En l'absence d'une clé **ou en cas d'échec du provider**, le pipeline bascule sur Claude sans interruption.
> Coût cible en production : **~$0.02/copie, ~$12/an pour une école de taille standard.**

---

## 8. Retours d'expérience — Tests réels (2026-06-05)

### 8.1 Gemini 2.0 Flash — Erreur `limit: 0` (free tier indisponible)

**Symptôme observé :**
```
429 RESOURCE_EXHAUSTED
Quota exceeded for metric: generate_content_free_tier_requests, limit: 0
Quota exceeded for metric: generate_content_free_tier_input_token_count, limit: 0
```

**Cause :** `limit: 0` n'est pas un quota épuisé — c'est l'absence totale de quota free tier pour ce compte/projet. Constaté avec deux projets Google AI Studio différents (BailExpress, HAKILI). Ce comportement se produit fréquemment hors des régions USA/Europe, y compris en Afrique de l'Ouest.

**Ce qui ne fonctionne pas :**
- Les clés AI Studio au format `AQ.Ab8RN6I...` créées depuis un compte associé à une région non couverte par le free tier
- Changer de projet Google n'a pas résolu le problème

**Solution :**
1. **Court terme** : `VISION_PROVIDER=claude` dans `.env` → Claude Sonnet gère la transcription, fallback automatique activé
2. **Long terme** : activer la facturation sur le projet Google Cloud → le tier payant ($0.10/$0.40 par MTok) prend le relais. Pour 540 copies/an : ~$2/an

**Configuration `.env` actuellement utilisée :**
```env
VISION_PROVIDER=claude   # Gemini désactivé jusqu'à activation facturation Google
```

---

### 8.2 DeepSeek — Erreur `402 Insufficient Balance`

**Symptôme observé :**
```
402 - {'error': {'message': 'Insufficient Balance', 'code': 'invalid_request_error'}}
```

**Cause :** DeepSeek impose des **crédits prépayés** — il n'y a pas de tier gratuit pour l'API DeepSeek V3/R1. Le compte nécessite un rechargement avant la première utilisation.

**Rechargement :** [platform.deepseek.com](https://platform.deepseek.com) → compte → dépôt minimum ~$5. À ce tarif ($0.27/$1.10 par MTok pour V3), $5 couvre environ **600 corrections complètes** — soit plus d'un an d'utilisation pour une école standard.

**Solution court terme :** fallback Claude automatique actif pendant cette période.

---

### 8.3 Architecture de fallback — Implémentation

Suite aux incidents ci-dessus, le pipeline a été renforcé avec des fallbacks sur **toutes les étapes critiques** :

```
Transcription  : Gemini 2.0 Flash    →  échec  →  Claude Sonnet 4.6
Correction     : DeepSeek V3         →  échec  →  Claude Sonnet 4.6
Diagnostic     : DeepSeek R1         →  échec  →  Claude Haiku 4.5
Remédiation    : Mistral Small 3.1   →  échec  →  Claude Sonnet 4.6
Extraction barème/énoncé : Claude Sonnet 4.6 (primaire, pas de fallback)
```

Le fallback se déclenche sur **toute erreur** (429, 402, timeout, erreur réseau) — pas seulement les erreurs de quota. L'utilisateur n'est jamais bloqué tant que la clé Anthropic est valide.

**Coût en mode dégradé (tout sur Claude Sonnet) :** ~$0.20-0.30/copie, soit ~$120-160/an. Acceptable pour la phase de test.

---

### 8.4 Tableau de disponibilité des providers (état 2026-06-11)

| Provider | Statut | Condition de blocage | Action requise |
|---|---|---|---|
| **Claude Sonnet 4.6** | ✅ Opérationnel | — | Aucune |
| **Claude Opus 4.7** | ✅ Opérationnel | — | Aucune (diagnostic provider actuel) |
| **Gemini 2.5 Flash** | ⚠️ Bloqué (région) | `limit: 0` sur compte BF | Activer facturation Google Cloud |
| **DeepSeek V3** | ⚠️ Bloqué (solde) | `402 Insufficient Balance` | Recharger ~$5 sur platform.deepseek.com |
| **DeepSeek R1** | ⚠️ Bloqué (solde) | `402 Insufficient Balance` | Idem DeepSeek V3 (même compte) |
| **Mistral Small** | ❓ Non testé | — | Tester avec clé valide |

---

*Hakili Lab — Document d'analyse interne · 2026-06-05 (mis à jour 2026-06-11)*
