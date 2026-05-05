# Brief Décisionnel CEO — Hakili Lab AI Correction
**Document confidentiel — Mai 2026**

---

## Résumé exécutif

Hakili Lab développe un prototype d'assistant IA pour la correction de copies manuscrites. L'outil réduit le temps de correction, formalise les diagnostics pédagogiques et génère des plans de remédiation personnalisés.

**État actuel :** architecture et stratégie validées, fondations techniques posées, pipeline IA à implémenter sur 6 semaines.

**Objectif :** évaluation sur 100 copies réelles d'ici 3 mois.

---

## Ce que le système fait

```
Enseignant uploade :          Le système produit :
  • Copie élève (PDF/photo)  →   • Note question par question
  • Énoncé                   →   • Score de confiance IA
  • Barème                   →   • Zones nécessitant révision humaine
                             →   • Diagnostic de compétences
                             →   • Plan de remédiation
                             →   • Rapport PDF + données JSON
```

**Garantie clé :** aucune note n'est restituée sans validation humaine de l'enseignant.

---

## Décisions critiques requises

Ces 8 décisions sont bloquantes pour le démarrage de l'implémentation.

---

### DÉCISION 1 — Périmètre matières du MVP
**Question :** Mathématiques uniquement, ou Mathématiques + Physique-Chimie dès le MVP ?

**Impact :** les prompts, le parsing du barème et les compétences diagnostiquées sont différents selon la matière.

**Options :**
| Option | Avantage | Risque |
|---|---|---|
| A — Maths uniquement | Focalisation, délivraison plus rapide | Périmètre limité |
| B — Maths + PC | Validation plus large dès le départ | Plus de complexité, délai +2 semaines |

**Recommandation :** Option A pour le MVP, extension PC en Sprint 4.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 2 — Format standard du barème
**Question :** Sous quel format les enseignants fourniront-ils le barème ?

**Impact :** détermine le module de parsing (texte libre vs structuré).

**Options :**
| Format | Facilité enseignant | Fiabilité parsing IA |
|---|---|---|
| A — Texte libre / PDF | Très facile | Moyenne (IA doit interpréter) |
| B — Tableau Excel structuré | Moyenne | Bonne |
| C — JSON fourni par Hakili | Difficile | Excellente |
| D — Formulaire dans l'interface | Bonne | Excellente |

**Recommandation :** Option A pour le MVP (le moins de friction pour l'enseignant), avec validation manuelle du parsing.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 3 — Fournisseur IA autorisé pour les copies réelles
**Question :** Quel(s) fournisseur(s) IA sont autorisés pour traiter des copies d'élèves réelles ?

**Impact :** conformité RGPD, contrats de données, choix de la clé API.

**Options :**
| Fournisseur | Performance vision | Coût estimé / copie | Résidence données |
|---|---|---|---|
| Anthropic Claude | Excellente | ~0.10–0.30 € | USA (Anthropic) |
| OpenAI GPT-4o | Excellente | ~0.10–0.25 € | USA (Microsoft Azure) |
| Google Gemini | Très bonne | ~0.05–0.15 € | USA (Google Cloud) |
| Modèle local (Ollama) | Moyenne | ~0 (hardware) | 100 % local |

**Recommandation :** Anthropic Claude pour le prototype (meilleure cohérence), avec anonymisation obligatoire avant envoi.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 4 — Tolérance d'erreur de notation acceptable
**Question :** Quel écart entre la note IA et la note enseignant est acceptable ?

**Impact :** définit les métriques de succès du prototype et le niveau de validation humaine requis.

**Options :**
| Seuil | Signification | Niveau de révision humaine |
|---|---|---|
| A — ±0.5 pt | Très strict | Élevé (30–40 % de révisions) |
| B — ±1 pt | Standard | Moyen (15–25 % de révisions) |
| C — ±2 pt | Permissif | Faible (5–10 % de révisions) |

**Recommandation :** Option B (±1 pt) pour le MVP.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 5 — Format du rapport PDF destiné aux enseignants
**Question :** Quel est le format exact du rapport PDF produit pour l'enseignant ?

**Impact :** design et implémentation du module de génération PDF (Sprint 3).

**Contenu minimal attendu (à confirmer) :**
- [ ] Note totale et détail par question
- [ ] Commentaire pédagogique par question
- [ ] Zones marquées "Révision requise"
- [ ] Diagnostic des compétences
- [ ] Plan de remédiation élève
- [ ] Score de confiance IA visible
- [ ] Logo Hakili Lab
- [ ] Signature / validation enseignant

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 6 — Politique de confidentialité et consentement
**Question :** Quel protocole de consentement est requis avant de traiter des copies d'élèves réelles ?

**Contexte légal :** copies = données personnelles de mineurs → RGPD applicable.

**Questions à trancher :**
- L'établissement a-t-il une autorisation DPO pour utiliser un LLM externe sur des données élèves ?
- Les parents seront-ils informés ? Consentement requis ?
- Les copies utilisées pour l'évaluation sur 100 seront-elles anonymisées *avant* ou *après* traitement ?

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 7 — Ressources internes pour la remédiation
**Question :** Le plan de remédiation peut-il pointer vers des ressources internes Hakili Lab ?

**Impact :** le module de diagnostic peut référencer des exercices ou supports spécifiques si fournis.

**Options :**
| Option | Description |
|---|---|
| A — Remédiation générique | L'IA suggère des thèmes, l'enseignant choisit les ressources |
| B — Librairie Hakili | L'IA pointe vers des exercices référencés dans une base fournie |

**Recommandation :** Option A pour MVP, Option B en v2 si base de ressources disponible.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

### DÉCISION 8 — Qui valide les corrections avant restitution ?
**Question :** Qui est responsable de la validation finale des notes ?

**Options :**
| Scénario | Description |
|---|---|
| A — L'enseignant correcteur uniquement | Revue individuelle, plus précis |
| B — L'enseignant + un coordinateur pédagogique | Double validation, plus sécurisé |
| C — L'enseignant avec seuillage de confiance | Validation obligatoire uniquement si confiance IA < seuil |

**Recommandation :** Option C (efficacité + sécurité) — configurable par établissement.

> **Décision Hakili Lab :** _______________  **Date :** _______________

---

## Budget IA estimé

| Volume | Coût Anthropic estimé | Coût Google Gemini estimé |
|---|---|---|
| 5 copies (test interne) | < 2 € | < 1 € |
| 30 copies (évaluation intermédiaire) | 5–15 € | 2–7 € |
| 100 copies (évaluation finale) | 15–50 € | 5–20 € |
| 1 000 copies / an (production) | 150–500 € | 50–200 € |

*Estimations indicatives selon longueur des copies et nombre de pages.*

---

## Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Images floues / illisibles | Élevée | Élevé | Contrôle qualité + demande de rescan |
| Hallucination sur écriture ambiguë | Moyenne | Élevé | Score confiance + flag révision humaine |
| Barème ambigu ou incomplet | Moyenne | Moyen | Validation barème avant lancement |
| Coût API sur grand volume | Faible | Moyen | Calcul coût par copie, cache prompts |
| Refus RGPD pour copies réelles | Moyenne | Très élevé | Anonymisation + accord DPO en amont |
| Rejet par les enseignants | Faible | Élevé | UX simple + gain de temps démontrable |

---

## Prochaines étapes (en attente de vos décisions)

1. **J+1 :** Valider les 8 décisions ci-dessus.
2. **J+2 :** Choisir le fournisseur IA et obtenir la clé API.
3. **J+3 :** Identifier les 5 premières copies de test (anonymisées).
4. **J+7 :** Premier pipeline bout-en-bout sur une copie réelle.
5. **J+30 :** Évaluation sur 30 copies avec enseignant référent.
6. **J+90 :** Évaluation sur 100 copies, rapport technique, soutenance.

---

*Document préparé par l'équipe technique Hakili Lab — Confidentiel*
*Toute décision prise doit être consignée dans `docs/decision_register.md`*
