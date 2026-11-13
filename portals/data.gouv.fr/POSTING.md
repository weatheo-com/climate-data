# Publier sur data.gouv.fr (liste pour le propriétaire)

Prérequis : les fichiers du dépôt sont attachés à la release v1.0.0 de https://github.com/weatheo-com/climate-data (les URL des ressources en dépendent).

1. Créer un compte sur https://www.data.gouv.fr (ou se connecter).
2. Créer l'organisation « Weatheo (by CODELIO) » avec le texte de `ORG.md` (site : https://weatheo.com). Noter son identifiant (page de l'organisation, ou `GET https://www.data.gouv.fr/api/1/organizations/?q=Weatheo`).
3. Créer la clé API : profil > Développeur > Clé API. L'exporter sans l'écrire dans un fichier : `export UDATA_API_KEY=...`
4. Dry run (rien n'est envoyé), depuis la racine du dépôt climate-data :

```
python scripts/publish_udata.py --base https://www.data.gouv.fr --meta portals/data.gouv.fr/FR-A.json --org <ORG_ID> --lookup
python scripts/publish_udata.py --base https://www.data.gouv.fr --meta portals/data.gouv.fr/FR-B.json --org <ORG_ID> --lookup
```

5. Publication réelle, avec `--lookup` implicite via `--apply` (met à jour si le jeu existe déjà) :

```
python scripts/publish_udata.py --base https://www.data.gouv.fr --meta portals/data.gouv.fr/FR-A.json --org <ORG_ID> --apply
python scripts/publish_udata.py --base https://www.data.gouv.fr --meta portals/data.gouv.fr/FR-B.json --org <ORG_ID> --apply
```

6. Vérifier sur le portail : licence CC BY, fréquence irrégulière, couverture temporelle 1961-2020, trois ressources par jeu.
7. Couverture spatiale : `publish_udata.py` envoie la clé `spatial` des fichiers JSON (granularité « Commune (fr:commune) », zone « France métropolitaine (country-subset:fr:metro) ») ; la vérifier sur la page du jeu, à défaut la renseigner dans l'interface.
8. Réutilisation : `REUSE.json` (type application, url https://weatheo.com/fr, thème environment_and_energy ; types et thèmes vérifiés sur /api/1/reuses/types/ et /api/1/reuses/topics/). Le script la crée ou la met à jour (même titre dans l'organisation) : `python scripts/publish_udata.py --base https://www.data.gouv.fr --reuse portals/data.gouv.fr/REUSE.json --org <id>` (essai à blanc, `--lookup` pour résoudre les slugs, puis `--apply`) ; les jeux rattachés viennent de la clé `datasets` de REUSE.json (slugs ou ids : « Liste des communes de France », FR-A et FR-B), l'image de la clé `image` si présente. À défaut, la créer dans l'interface (Publier > Réutilisation) et lui rattacher ces trois jeux.
