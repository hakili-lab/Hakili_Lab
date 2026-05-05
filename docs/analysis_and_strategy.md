# Analyse et stratégie technique

## 1. Problème réel
Hakili Lab veut réduire le temps de correction de centaines de copies manuscrites et mieux formaliser les diagnostics individuels. Le besoin n'est pas seulement de « corriger avec l'IA » : il faut industrialiser un flux fiable, rapide et contrôlable par l'enseignant.

## 2. Point d'attention majeur : ingestion des copies
### Mauvaise approche
Demander à l'équipe de prendre des photos question par question ou copie par copie sans cadre strict. C'est lent, source d'erreurs et difficile à standardiser.

### Approche recommandée
Flux principal : une copie complète par élève, scannée en PDF multi-pages ou photographiée page par page dans l'ordre.

Le système doit ensuite :
- convertir le PDF en images ;
- détecter la qualité de chaque page ;
- demander une reprise uniquement si la page est trop floue, tronquée ou mal orientée ;
- découper/matcher les réponses avec les questions à partir de l'énoncé et du barème.

### Pourquoi pas scanner toute la copie uniquement ?
C'est le meilleur flux opérationnel, mais il faut imposer une bonne résolution. Un scan complet n'est pas mauvais pour les modèles si les pages sont nettes, bien orientées et exportées en images haute qualité. Le vrai risque est un PDF compressé, sombre ou mal cadré.

## 3. Choix MVP recommandé
- Entrée : PDF multi-pages par élève + énoncé PDF/texte + barème PDF/texte.
- Interface : Streamlit pour aller vite, sauf obligation stricte Shiny.
- IA : commencer avec Claude ou Gemini multimodal pour transcription/correction ; garder une abstraction pour tester plusieurs modèles.
- Stockage : local au début, dossier `runs/`, avec anonymisation des noms.
- Sorties : JSON structuré + PDF enseignant/parent.

## 4. Architecture optimale
Pipeline en 10 étapes :
1. Upload des fichiers.
2. Normalisation des entrées.
3. Conversion PDF -> images.
4. Contrôle qualité image.
5. Transcription structurée.
6. Association réponse-question.
7. Correction selon barème.
8. Diagnostic par compétence.
9. Plan de remédiation.
10. Génération PDF + export JSON.

## 5. Principe anti-hallucination
L'IA doit produire trois niveaux :
- `observed_answer` : ce qui est réellement lu sur la copie ;
- `interpretation` : ce que le modèle pense que l'élève voulait faire ;
- `uncertainties` : zones illisibles ou ambiguës.

Si une réponse est illisible, la note doit être proposée avec prudence ou marquée `requires_teacher_review`.

## 6. Évaluation
Comparer à un enseignant de référence :
- écart absolu moyen de note ;
- taux d'accord exact ou à ±0,5 point ;
- taux de questions nécessitant revue humaine ;
- pertinence des commentaires ;
- temps gagné par copie ;
- taux d'échec pour images de mauvaise qualité.

## 7. Confidentialité
Au stade prototype :
- anonymiser les copies ;
- éviter les noms/prénoms dans les prompts ;
- ne pas logguer les images ou données personnelles ;
- documenter clairement le fournisseur IA utilisé ;
- demander consentement ou autorisation interne avant test sur copies réelles.

## 8. Limite claire
Le prototype doit assister la correction. Il ne doit pas promettre une correction autonome fiable à 100 %, surtout en mathématiques avec écritures manuscrites, étapes de calcul et schémas.
