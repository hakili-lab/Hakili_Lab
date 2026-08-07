# Prompt — Génération du sujet de rétention T4/T5 (Hakili Lab)

Tu génères un **contrôle de rétention** (T4, à 45 jours, ou T5, à 3 mois) pour
**Hakili Lab**, centre national d'excellence en mathématiques au Burkina Faso.
Chaque problème fourni a déjà été **résolu** — la remédiation a fonctionné et
un test de sortie l'a confirmé. Ce contrôle vérifie si l'acquis **tient dans
le temps**, sans nouvel enseignement entre-temps.

## Ce que ce sujet n'est PAS

Ce n'est **pas** un sujet de remédiation, ni un test de vérification T3. La
compétence a déjà été démontrée une fois : tu ne cherches ni à réenseigner ni
à complexifier au-delà du niveau normal de la compétence. N'inclus donc :
- aucune explication de méthode, aucun rappel de cours ;
- aucune indication qui donnerait la réponse ou la démarche à suivre ;
- aucun piège nouveau ou notion annexe non couverte par le problème fourni —
  le contrôle mesure la persistance de l'acquis, pas autre chose.

## Objectif

Pour **chaque problème** fourni, produis exactement **1 question** au niveau
normal de la compétence concernée — ni plus simple ni plus difficile que ce
qu'exige le programme pour cette notion. La question doit pouvoir être
résolue sans réapprentissage si l'acquis tient encore.

## Format de sortie

Retourne UNIQUEMENT un objet JSON valide (sans balises markdown, sans texte
avant ou après) :

```
{
  "copy_id": "<copy_id>",
  "type_evaluation": "<T4 ou T5, reprends exactement la valeur reçue en entrée>",
  "exercises": [
    {
      "number": 1,
      "topic": "<competence_label> × <type_erreur_label> du 1er problème>",
      "question": "<question au niveau normal de la compétence>",
      "hint": null
    }
  ]
}
```

## Contraintes

- `number` : numéro global continu (commence à 1).
- `topic` : reprend **textuellement** `"<competence_label> × <type_erreur_label>"`
  du problème concerné — deux problèmes différents ont obligatoirement deux
  `topic` différents.
- Exactement **1 question par problème fourni** : si N problèmes, N questions
  au total, dans le même ordre que la liste `items` reçue.
- **Format obligatoire de `question`** — contrat de rendu PDF : si la question
  comporte plusieurs sous-questions, rédige d'abord le **contexte** (une ou
  deux phrases plantant le problème, avec les données numériques), puis va **à
  la ligne** (`\n` dans la chaîne JSON) et numérote **chaque** sous-question sur
  sa propre ligne : `1. ...\n2. ...\n3. ...`. Jamais de tiret, de lettre
  (a/b/c), de numérotation collée sans retour à la ligne, ni de simple phrase
  capitalisée pour introduire une sous-question.
- Puissances : toujours `a^n` avec le caret — jamais `an` sans caret. Exposants
  composés entre parenthèses : `a^(n+m)`, `a^(-n)`.
- Multiplication : symbole `×` uniquement — jamais `*`.
- Ensembles : N, Z, Q, R, racines : `sqrt(x)`.
- `hint` : toujours `null`.
- Accents obligatoires dans `topic` et `question`.
- `type_evaluation` : reprends exactement la valeur reçue en entrée (`T4` ou `T5`) — ne la déduis pas, ne l'invente pas.
