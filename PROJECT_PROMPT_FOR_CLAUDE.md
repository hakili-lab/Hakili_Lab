# Prompt maître à donner à Claude Code

Tu es Claude Code dans VS Code. Je veux que tu mettes en place un environnement professionnel GitHub pour le projet Hakili Lab : outil d'évaluation et de remédiation assistée par IA pour copies manuscrites.

Contexte : le projet doit ingérer des copies manuscrites scannées ou photographiées, accompagnées d'un énoncé et d'un barème, puis produire une transcription, une correction question par question, un diagnostic pédagogique, un plan de remédiation, un rapport PDF et un export JSON.

Contraintes :
- Python backend.
- Interface démo légère, Streamlit acceptable pour MVP ; Shiny Python si explicitement demandé.
- Entrées : JPG, PNG, PDF multi-pages.
- Sorties : PDF + JSON.
- Confidentialité : anonymisation, stockage local par défaut, pas de logs sensibles.
- Robustesse : détecter copies floues, mal cadrées, pages manquantes ou illisibles.
- Validation humaine obligatoire.

Ta mission :
1. Lire tous les fichiers du repo, notamment `CLAUDE.md`, `docs/analysis_and_strategy.md`, `docs/decision_register.md` et `data/schemas/`.
2. Améliorer la structure si nécessaire sans casser la simplicité du MVP.
3. Compléter les modules Python suivants :
   - ingestion PDF/images ;
   - contrôle qualité image ;
   - abstraction fournisseur IA ;
   - transcription structurée ;
   - correction selon barème ;
   - diagnostic/remédiation ;
   - génération rapport PDF ;
   - interface enseignant de revue/validation.
4. Ajouter une documentation GitHub professionnelle : README, architecture, setup, usage, sécurité, évaluation, limites.
5. Ajouter tests, lint, CI GitHub Actions.
6. Ne jamais coder une correction qui invente en cas d'illisibilité : tout doit remonter `requires_teacher_review`.
7. Garder les sorties JSON conformes aux schémas.
8. À chaque étape, proposer un plan court, implémenter, puis lancer tests/lint.

Commence par auditer le repo et donne-moi le premier plan d'implémentation en 6 étapes maximum.
