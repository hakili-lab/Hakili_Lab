# Brief projet Hakili Lab — Synthèse technique

## Vision

Hakili Lab développe un assistant IA pour corriger des copies manuscrites numérisées, diagnostiquer les lacunes des élèves et générer des plans de remédiation personnalisés.

**Positionnement :** outil d'assistance à l'enseignant — pas de correction autonome, validation humaine obligatoire.

## Stratégie gagnante

Ne pas viser une correction parfaite dès le départ. Viser un assistant fiable, auditable, avec mesure de confiance, qui fait gagner du temps à l'enseignant sur les cas faciles et le guide sur les cas ambigus.

## Flux terrain

```
1. L'enseignant scanne toute la copie (PDF multi-pages) ou photos dans l'ordre
2. Il uploade l'énoncé et le barème
3. Le système vérifie la qualité des pages
4. L'IA transcrit puis corrige avec score de confiance
5. L'enseignant révise les zones marquées "à vérifier"
6. Le système génère le PDF rapport + export JSON
```

## Décisions prises

| ID | Décision | Statut |
|---|---|---|
| D001 | Ingestion copie complète (pas question par question) | Validée |
| D002 | Validation humaine obligatoire avant restitution | Validée |
| D003 | JSON source de vérité, PDF rendu final | Validée |
| D004 | Abstraction fournisseur IA (Claude / OpenAI / Gemini) | Validée |
| D005 | Streamlit pour MVP | À confirmer |
| D006 | Stockage local anonymisé (prototype) | Validée |
| D007 | Évaluation sur 100 copies avec enseignant référent | Validée |

## Décisions en attente (voir `ceo_decision_brief.md`)

1. Périmètre matières : Maths seul ou Maths + PC ?
2. Format du barème attendu des enseignants
3. Fournisseur IA autorisé sur données réelles (RGPD)
4. Tolérance d'erreur de notation (±0.5 / ±1 / ±2 pts)
5. Format du rapport PDF enseignant
6. Protocole de consentement élèves / parents
7. Ressources internes de remédiation disponibles
8. Qui valide la correction avant restitution

## Roadmap MVP — 3 mois

```
Mois 1 : pipeline bout-en-bout sur 5 copies
  Sprint 0 (3j) : fondations Python
  Sprint 1 (1s) : abstraction IA + ingestion PDF
  Sprint 2 (1s) : transcription + correction

Mois 2 : robustesse et rapport
  Sprint 3 (1s) : diagnostic + PDF + UI complète
  Sprint 4 (1s) : robustesse + tests sur 30 copies

Mois 3 : évaluation et soutenance
  Sprint 5 (1s) : CI/CD + évaluation 30 copies
  Sprint 6 (1s) : évaluation 100 copies + rapport technique
```

## Risques principaux

| Risque | Mitigation |
|---|---|
| Images floues / mal cadrées | Contrôle qualité automatique + demande rescan |
| Hallucination sur illisible | Règle stricte : `[ILLISIBLE]` → `requires_teacher_review` |
| Barème ambigu | Validation barème avant lancement pipeline |
| Coût API | Estimation < 0.30 € / copie, cache prompts activé |
| RGPD sur données élèves | Anonymisation avant appel API, accord DPO |
| Rejet enseignants | UX simple, démontrer le gain de temps |

## Métriques de succès

| Métrique | Cible MVP |
|---|---|
| Écart moyen note IA vs enseignant | < 1 point |
| Taux accord exact ou ±0.5pt | > 70 % |
| Taux de révision humaine requise | < 20 % |
| Temps gagné par copie | > 50 % |
| Taux d'échec qualité image | < 5 % |

## État du code (mai 2026)

- Architecture documentée : **complète**
- Schémas JSON : **complets**
- Prompts LLM : **complets**
- Config Python + modèles Pydantic : **en place**
- Pipeline IA (transcription, correction, diagnostic) : **à implémenter**
- Interface complète : **à câbler**
- Tests d'intégration : **à écrire**
- CI/CD : **à mettre en place**
