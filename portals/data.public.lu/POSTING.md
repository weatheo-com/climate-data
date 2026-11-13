# Publier sur data.public.lu (liste pour le propriétaire)

Prérequis : les fichiers du dépôt sont attachés à la release v1.0.0 de https://github.com/weatheo-com/climate-data (les URL des ressources en dépendent).

1. Créer un compte sur https://data.public.lu (ou se connecter).
2. Créer l'organisation « Weatheo (by CODELIO) » avec le texte de `ORG.md` (site : https://weatheo.com). Noter son identifiant (page de l'organisation, ou `GET https://data.public.lu/api/1/organizations/?q=Weatheo`).
3. Créer la clé API : profil > Développeur > Clé API. L'exporter sans l'écrire dans un fichier : `export UDATA_API_KEY=...`
4. Dry run (rien n'est envoyé), depuis la racine du dépôt climate-data :

```
python scripts/publish_udata.py --base https://data.public.lu --meta portals/data.public.lu/LU-A.json --org <ORG_ID> --lookup
python scripts/publish_udata.py --base https://data.public.lu --meta portals/data.public.lu/LU-B.json --org <ORG_ID> --lookup
```

5. Publication réelle, avec `--lookup` implicite via `--apply` (met à jour si le jeu existe déjà) :

```
python scripts/publish_udata.py --base https://data.public.lu --meta portals/data.public.lu/LU-A.json --org <ORG_ID> --apply
python scripts/publish_udata.py --base https://data.public.lu --meta portals/data.public.lu/LU-B.json --org <ORG_ID> --apply
```

6. Vérifier sur le portail : licence CC BY, fréquence irrégulière, couverture temporelle 1961-2020, trois ressources par jeu.
7. Couverture spatiale : `publish_udata.py` envoie la clé `spatial` des fichiers JSON (granularité « Commune (lu:commune) », zone « Luxembourg (country:lu) ») ; la vérifier sur la page du jeu, à défaut la renseigner dans l'interface.
8. Pas de réutilisation sur ce portail.
