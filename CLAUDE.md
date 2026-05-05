# CLAUDE.md — Hakili Lab AI Copy Correction Assistant

## Rôle de Claude Code
Tu es l'assistant d'ingénierie du projet Hakili Lab : outil d'évaluation et de remédiation assistée par IA pour copies manuscrites de mathématiques et physique-chimie.

Objectif : produire un prototype professionnel, testable, documenté, maintenable, et prêt pour une évaluation sur 100 copies réelles.

## Contraintes non négociables
- Python comme backend principal.
- Interface de démonstration légère : priorité à Streamlit si Shiny Python ralentit le projet ; Shiny reste acceptable si imposé.
- Entrées : JPG, PNG, PDF multi-pages.
- Sorties : rapport PDF structuré + export JSON.
- Correction strictement basée sur l'énoncé et le barème fournis.
- Ne jamais inventer une réponse illisible : signaler l'incertitude.
- Garder une trace de confiance par page, question et sous-question.
- Prévoir une validation humaine avant toute restitution officielle.
- Confidentialité : anonymisation par défaut, stockage local par défaut au stade prototype.

## Architecture cible
Pipeline recommandé :
1. Ingestion : upload PDF/images + énoncé + barème.
2. Prétraitement : conversion PDF -> images, rotation, cadrage, amélioration contraste, découpage page par page.
3. Contrôle qualité image : flou, luminosité, page manquante, ordre des pages.
4. Transcription multimodale structurée : texte, calculs, formules, schémas, zones incertaines.
5. Mapping question -> réponse élève.
6. Correction selon barème.
7. Diagnostic compétences.
8. Remédiation personnalisée.
9. Génération PDF + JSON.
10. Interface enseignant : revue, correction manuelle, validation.

## Décision stratégique importante
Ne pas construire un outil qui demande à l'équipe de photographier et envoyer chaque exercice un par un. Le flux recommandé est : scanner ou photographier toute la copie, puis laisser le système découper et organiser les pages. Pour un MVP, accepter aussi plusieurs images dans l'ordre.

## Qualité attendue du code
- Typage Python partout où utile.
- Pydantic pour les schémas de données.
- Tests unitaires sur parsing, scoring, génération JSON.
- Séparation claire entre modèle IA, logique métier et interface.
- Configuration par `.env`.
- Logs propres sans données personnelles sensibles.
- README exploitable par un nouveau développeur.

## Style de travail
Avant de coder :
1. Lire `docs/analysis_and_strategy.md`.
2. Lire `docs/decision_register.md`.
3. Lire `data/schemas/*.json`.
4. Proposer un plan court.
5. Implémenter par petites étapes testables.

## Commandes attendues
- `make setup` : créer environnement et installer dépendances.
- `make test` : lancer tests.
- `make run` : lancer l'interface de démonstration.
- `make lint` : vérifier format et qualité.

