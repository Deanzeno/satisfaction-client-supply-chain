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
