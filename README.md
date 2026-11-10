# Supply Chain — Satisfaction des clients

**Projet Data Engineering — Liora / DataScientest**
**Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER**

---

## Description

Pipeline de données de bout en bout pour analyser la satisfaction client dans la supply chain, à partir des avis Trustpilot : collecte, stockage, modèle de sentiment, API, automatisation quotidienne, monitoring et CI/CD.

---

## Étapes et livrables

| Étape | Contenu | Livrables dans le dépôt |
|-------|---------|-------------------------|
| 1. Récolte | Scraping Trustpilot : 10 664 entreprises (3 catégories) et 592 avis ShowroomPrivé | `companies_trustpilot.csv`, `showroom_reviews.json`, `scraper_*.py`, comptes rendus `.docx` |
| 2. Organisation | PostgreSQL (3 tables) et ElasticSearch, dashboard Kibana | `create_database.sql`, `queries.sql`, `create_index_reviews.json`, `requetes_elasticsearch.txt`, `kibana_saved_objects.ndjson` (export réel des dashboards ; `kibana_dashboard.html` n'est qu'un aperçu statique) |
| 3. Consommation | Modèle de sentiment TF-IDF + régression logistique (72,3 % d'accuracy) | `etape3_sentiment.ipynb`, `sentiment_model.pkl`, `vectorizer.pkl` |
| 4. Mise en production | API FastAPI (5 routes, 30 tests), Dockerfile, rapport de dérive | `main.py`, `test_main.py`, `Dockerfile`, `derive/rapport_derive.html` |
| 5. Automatisation | DAG Airflow quotidien, Prometheus, Grafana, logs de l'API, CI GitLab | `dags/scraping_dag.py`, `schema_dag.png`, `docker-compose.yml`, `init/`, `monitoring/`, `.gitlab-ci.yml` |

---

## Lancer le projet

Prérequis : Docker Desktop installé et démarré.

1. Créer **un seul** fichier `.env`, à la racine du projet : copier `.env.example` en `.env` et renseigner `POSTGRES_PASSWORD`. Il sert à la fois aux conteneurs Docker et aux scripts Python.
2. Lancer les 10 services :
   ```
   docker-compose -f "Etape 5/docker-compose.yml" up -d
   ```

C'est tout. Au premier démarrage, sans aucune commande de plus :

- PostgreSQL crée ses tables (`Etape 2/create_database.sql`) ;
- le conteneur `kibana-init` charge les 592 avis dans l'index `reviews` et importe les dashboards Kibana, puis s'arrête ;
- Grafana charge son dashboard depuis `Etape 5/monitoring/grafana/provisioning/dashboards/` ;
- le DAG Airflow est actif dès le départ et fait sa première exécution dans les minutes qui suivent : les 10 664 entreprises arrivent dans PostgreSQL, puis dans ElasticSearch.

Compter 3 à 5 minutes la première fois (téléchargement des images, démarrage de Kibana). `docker ps -a` doit montrer `kibana-init` et `airflow-init` en « Exited (0) », et les 8 autres services en « Up ».

| Interface | Adresse |
|-----------|---------|
| API FastAPI | http://localhost:8000/docs |
| Airflow | http://localhost:8080 (admin / admin123) |
| Kibana | http://localhost:5601 → Dashboards |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin123) |

Le guide ci-dessous détaille chaque étape sous Windows, avec toutes les commandes et les requêtes de démonstration.

---

## Guide pas à pas (Windows, PowerShell)

Suivez les étapes dans l'ordre. Chaque bloc de code se copie tel quel dans PowerShell ; le résultat attendu est écrit juste en dessous. Les étapes 1 à 3 ne se font qu'une seule fois par ordinateur.

### 1. Installer Docker Desktop et Git

Installer [Docker Desktop](https://www.docker.com/products/docker-desktop/) et [Git](https://git-scm.com/download/win), puis redémarrer l'ordinateur.

### 2. Récupérer le projet

```powershell
cd $HOME\Desktop
git clone https://github.com/Deanzeno/satisfaction-client-supply-chain.git
cd satisfaction-client-supply-chain
```

Le dossier `satisfaction-client-supply-chain` apparaît sur le Bureau.

### 3. Créer le fichier `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Dans le Bloc-notes, remplacer `ton_mot_de_passe_ici` par un mot de passe de votre choix, puis enregistrer et fermer. Ce fichier reste sur l'ordinateur : il est dans le `.gitignore`, il ne part jamais sur GitHub.

### 4. Lancer le projet

Ouvrir Docker Desktop et attendre « Engine running » en bas à gauche. Puis, dans PowerShell :

```powershell
cd $HOME\Desktop\satisfaction-client-supply-chain
git pull
docker-compose -f "Etape 5/docker-compose.yml" up -d
```

Compter 1 à 2 minutes (3 à 5 minutes la première fois). À la fin, chaque ligne commence par ✔.

### 5. Vérifier que tout tourne

```powershell
docker ps -a
```

Résultat attendu : 8 conteneurs en `Up`, et 2 en `Exited (0)` : `airflow-init` et `kibana-init`. C'est normal : ils préparent le projet puis s'arrêtent, et le 0 veut dire qu'ils ont réussi.

### 6. Ouvrir les pages

| Page | Adresse | Ce qu'on doit voir |
|------|---------|--------------------|
| API | http://localhost:8000/docs | 5 routes |
| Airflow | http://localhost:8080 (admin / admin123) | le DAG `scraping_journalier_trustpilot`, cases vertes |
| ElasticSearch | http://localhost:9200/_cat/indices?v | 3 index en `green` |
| Kibana | http://localhost:5601 → Dashboards | « Supply Chain — Satisfaction des clients » et « Supply Chain — Logs de l'API » |
| Prometheus | http://localhost:9090 → Status → Targets | `fastapi_supply_chain` en `UP` |
| Grafana | http://localhost:3000 (admin / admin123) → Dashboards | « Supply Chain — Monitoring API » |

### 7. Tester l'API

Dans http://localhost:8000/docs : ouvrir `POST /predict`, cliquer sur **Try it out**, remplacer le texte par celui-ci, puis cliquer sur **Execute**.

```json
{"texte": "Très mauvais service, je ne recommande pas"}
```

Réponse attendue : `"sentiment": "negatif"`, `"confiance": 0.64`. Avec `{"texte": "Livraison rapide, produit parfait, je recommande"}`, la réponse est `"positif"`, `0.74`.

Puis ouvrir `GET /stats`, **Try it out**, **Execute** : 9 966 boutiques (`clothing_store`, 3,57 de moyenne), 648 transporteurs (`courier_service`, 2,27) et 47 distributeurs (`atm`, 2,14).

### 8. Prouver que PostgreSQL est rempli

Dans PowerShell, toujours dans le dossier du projet. Si votre `.env` a un autre `POSTGRES_USER`, remplacer `postgres` après `-U`.

Requête 1, le nombre de lignes de chaque table :

```powershell
docker exec etape5-postgres-1 psql -U postgres -d satisfaction_client -c "SELECT (SELECT COUNT(*) FROM categorie) AS categories, (SELECT COUNT(*) FROM entreprise) AS entreprises, (SELECT COUNT(*) FROM statistiques_avis) AS lignes_statistiques;"
```

Résultat attendu : `3 | 10661 | …`. La troisième colonne est un multiple de 10 664, car chaque exécution du DAG ajoute une ligne par entreprise (31 992 après 3 exécutions).

Requête 2, une jointure sur les trois tables : les 5 transporteurs les plus commentés.

```powershell
docker exec etape5-postgres-1 psql -U postgres -d satisfaction_client -c "SELECT e.nom AS transporteur, s.trustscore, s.nb_avis_total FROM (SELECT DISTINCT ON (entreprise_id) * FROM statistiques_avis ORDER BY entreprise_id, id DESC) s JOIN entreprise e ON e.id = s.entreprise_id JOIN categorie c ON c.id = e.categorie_id WHERE c.nom = 'courier_service' ORDER BY s.nb_avis_total DESC LIMIT 5;"
```

Résultat attendu :

```
   transporteur    | trustscore | nb_avis_total
-------------------+------------+---------------
 DHL               |        1.3 |         30278
 Stackry           |        4.2 |         14068
 MyUS.com          |        3.3 |         12947
 Parcel Monkey USA |        4.1 |         12080
 Instacart         |        1.2 |         12020
```

### 9. Prouver qu'ElasticSearch est rempli

Ouvrir la console de Kibana : http://localhost:5601/app/dev_tools#/console. Effacer la partie gauche (Ctrl+A puis Suppr), coller les deux requêtes, puis cliquer sur ▶ à côté de chacune.

```
GET companies_supply_chain/_search
{
  "size": 0,
  "track_total_hits": true,
  "aggs": {
    "par_categorie": {
      "terms": { "field": "categorie" },
      "aggs": { "trustscore_moyen": { "avg": { "field": "trustscore" } } }
    }
  }
}

GET reviews/_search
{
  "size": 3,
  "_source": ["nb_etoiles", "titre"],
  "query": { "match": { "contenu": "delivery" } },
  "aggs": { "par_note": { "terms": { "field": "nb_etoiles" } } }
}
```

Résultats attendus :

- requête 1 : 10 661 entreprises au total ; `clothing_store` 9 966 (moyenne 3,57), `courier_service` 648 (2,27), `atm` 47 (2,14). Les mêmes chiffres que PostgreSQL ;
- requête 2 : 21 avis contiennent « delivery », dont 13 à une étoile.

### 10. Prometheus et Grafana

Dans Prometheus (http://localhost:9090), onglet **Graph**, taper cette requête puis cliquer sur **Execute** : elle donne le nombre total de requêtes reçues par l'API depuis son démarrage.

```
sum(http_requests_total)
```

Dans Grafana (http://localhost:3000), le dashboard « Supply Chain — Monitoring API » montre l'API en ligne, le nombre de requêtes, les erreurs 5xx et le temps de réponse.

### 11. Arrêter le projet

```powershell
docker-compose -f "Etape 5/docker-compose.yml" stop
```

Les données sont gardées : l'étape 4 relance tout. Ne pas utiliser `down -v`, qui efface les bases.

### Si quelque chose ne marche pas

| Ce que vous voyez | Ce qu'il faut faire |
|-------------------|---------------------|
| `The "POSTGRES_DB" variable is not set` | Vous n'êtes pas dans le bon dossier, ou le `.env` manque. Refaire `cd $HOME\Desktop\satisfaction-client-supply-chain`, puis `Test-Path .env` doit répondre `True`. |
| `ports are not available` … `9090` | Ouvrir PowerShell en administrateur, taper `net stop winnat` puis `net start winnat`, et relancer l'étape 4. |
| Un conteneur reste en `Restarting` | Lire son erreur : `docker logs etape5-<nom>-1 --tail 40` (par exemple `etape5-api-1`). |
| Airflow ou Kibana ne s'ouvre pas | Attendre une minute de plus et recharger la page : ce sont les services les plus lents à démarrer. |

---

## Automatisation (Étape 5)

Le DAG `scraping_journalier_trustpilot` tourne chaque jour à 6 h UTC : scraping → PostgreSQL → scoring du sentiment → ElasticSearch. Si Trustpilot bloque le scraping (HTTP 403), il repart du dernier CSV collecté.

![Schéma du DAG](Etape%205/schema_dag.png)

Le même DAG dans l'interface Airflow (`Etape 5/capture_dag_airflow.jpg`) :

![DAG dans Airflow](Etape%205/capture_dag_airflow.jpg)

Répartition des avis par note (% Excellent… % Bad) : `python "Etape 1 du projet/scraper_repartition_notes.py" --max 200` (ou `--tous`), puis relancer le DAG.

## Monitoring et logs

- Prometheus collecte `/metrics` toutes les 15 s ; Grafana affiche le dashboard « Supply Chain — Monitoring API ».
- Chaque appel à l'API est journalisé (route, statut, durée, sentiment) dans l'index ElasticSearch `api-logs`, visible dans le dashboard Kibana « Logs de l'API ».
- Après une modification des dashboards dans Kibana ou Grafana : `python "Etape 5/dashboards.py" export`, puis commit.

## Rapport de dérive (Étape 4)

```
python "Etape 4/derive/rapport_derive.py"
```
Compare les avis d'avant 2022 et depuis 2022 (χ², Kolmogorov-Smirnov, PSI) et produit `rapport_derive.html`.

## Tests et CI/CD

- `pytest "Etape 4/test_main.py" -v` : 30 tests.
- GitLab CI à chaque push :
  1. **test** : 30 tests pytest sur un PostgreSQL de test, et lint flake8 ;
  2. **build** : construction de l'image Docker de l'API et publication dans le registre GitLab ;
  3. **deploy** : l'image publiée est déployée dans un environnement de staging éphémère (PostgreSQL + API), puis vérifiée par des tests de fumée sur `/`, `/predict`, `/companies`, `/stats` et `/metrics`. L'environnement est supprimé à la fin du job.

---

## Sécurité

- Fichier `.env` jamais commité (voir `.gitignore`).
- Tous les identifiants passent par le `.env` : `env_file` pour les conteneurs, python-dotenv pour les scripts. Aucun mot de passe de base de données dans le docker-compose.
- Voir `.env.example` pour la liste des variables.
