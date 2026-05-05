# Decision Register

| ID | Décision | Statut | Justification |
|---|---|---|---|
| D001 | Ingestion par copie complète PDF/images, pas question par question | Recommandée | Plus rapide, moins fastidieux, meilleur flux terrain |
| D002 | Validation humaine obligatoire avant rapport final | Recommandée | Réduit les risques de notes injustes |
| D003 | JSON structuré comme source de vérité, PDF comme rendu | Recommandée | Facilite évaluation, audit et réutilisation |
| D004 | Abstraction fournisseur IA | Recommandée | Comparer Claude, Gemini, OpenAI sans réécrire le pipeline |
| D005 | Streamlit pour MVP sauf obligation Shiny | À décider | Plus rapide à implémenter en Python |
| D006 | Stockage local anonymisé pour prototype | Recommandée | Simplicité + confidentialité |
| D007 | Évaluation sur 100 copies avec enseignant référent | Obligatoire | Exigence du cahier de charges |

## Décisions à prendre par Hakili Lab avant implémentation
1. Matière et niveau prioritaires pour le MVP : mathématiques uniquement ou maths + physique-chimie ?
2. Format standard du barème : texte libre, PDF, tableau Excel, JSON ?
3. Tolérance d'erreur acceptable : écart de note maximal ?
4. Fournisseur IA autorisé pour les copies réelles : Claude, OpenAI, Gemini, local ?
5. Politique de confidentialité et consentement.
6. Ressources internes disponibles pour remédiation.
7. Format exact du rapport PDF attendu.
8. Qui valide les corrections avant restitution ?
