# Politique de sécurité — Hakili Lab

## Données traitées

Ce prototype traite des copies d'élèves qui peuvent contenir :
- Des noms et prénoms d'élèves (données personnelles)
- Des évaluations scolaires (données sensibles selon le contexte)
- Des images de copies manuscrites

## Mesures en place

### Anonymisation
- Les copies sont anonymisées avant traitement : le nom de l'élève est remplacé par un identifiant (`anon_001`, `anon_002`, etc.)
- Les métadonnées EXIF des images (géolocalisation, appareil photo) sont supprimées avant envoi à l'API

### Stockage
- Toutes les données sont stockées **localement** dans le dossier `runs/`
- Le dossier `runs/` est exclu du versionnement git (`.gitignore`)
- Aucune base de données distante au stade prototype

### Logs
- Les logs ne contiennent ni noms d'élèves, ni images, ni notes brutes
- Seuls les identifiants anonymisés et les statuts de traitement sont loggués

### Clés API
- Les clés API ne sont jamais committées (`.env` est dans `.gitignore`)
- Utiliser uniquement `.env.example` comme référence

### Appels API externes
- Les images anonymisées et les transcriptions sont envoyées au fournisseur IA choisi
- Consulter les politiques de données de votre fournisseur IA avant usage sur copies réelles :
  - Anthropic : https://www.anthropic.com/legal/privacy
  - OpenAI : https://openai.com/policies/privacy-policy
  - Google : https://policies.google.com/privacy

## Avant tout usage sur copies réelles

1. Obtenir l'accord du Délégué à la Protection des Données (DPO) de l'établissement
2. Vérifier que le fournisseur IA choisi est conforme RGPD (ou obtenir une dérogation)
3. Informer les élèves et parents si requis
4. Ne jamais utiliser des copies nominatives sans autorisation explicite

## Signaler une vulnérabilité

Contacter : uriethiombiano853@gmail.com
