Refactor UI — Sidebar dashboard

Résumé des changements effectués:
- `templates_django/base.html` : nouveau layout `app-shell` avec `aside.sidebar`, `div.page`, `div.topbar`, `main.content`.
- Styles CSS centralisés et ajout de règles pour la sidebar (icônes SVG, responsive mobile-first).
- Titres de page déplacés vers le bloc `{% block page_titre %}` dans les templates enfants.
- Templates enfants modifiés :
  - `comptes/templates/comptes/connexion.html`
  - `correction_web/templates/correction_web/*.html` (liste, lot, nouvelle, progression, relecture, resultats, sujets, validation)
  - `suivi_web/templates/suivi_web/*.html` (accueil, eleve_detail, personnel, session_detail, statistiques)

Comment tester localement:

1. Lancer le serveur Django (depuis le workspace racine):

```bash
# activer l'environnement virtuel si nécessaire
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

2. Ouvrir `http://127.0.0.1:8000/` et naviguer sur les écrans suivants:
- Connexion
- Corriger une copie
- Liste des corrections
- Valider les notes
- Suivi des élèves, fiche élève et parcours

3. Tests responsive:
- Mode mobile: réduire la fenêtre à < 920px et vérifier que la sidebar passe en haut (barre horizontale) et que la topbar reste visible.
- Mode desktop: vérifier que la `sidebar` est visible à gauche (260px) et que la `page-titre` apparaît dans la `topbar`.

Prochaines étapes recommandées:
- Ajouter un bouton de bascule (collapse) pour la sidebar sur desktop — implémenté.
- Comportement drawer mobile : ouverture par bouton et overlay — implémenté.
 - Polices : augmentation légère des tailles de base pour meilleure lisibilité — implémenté.
 - Persistance de l'état collapsed de la sidebar (localStorage) — implémenté.
- Affiner les icônes et remplacer par un set cohérent (Feather/Material icons).
- Ajouter tests d'interface visuels ou captures d'écran pour CI (optionnel).
- Commit des modifications avec message clair et revue.

Fait par: GitHub Copilot (assistance de refactor UI)
Date: 2026-08-05
