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
| 2. Organisation | PostgreSQL (3 tables) et ElasticSearch, dashboard Kibana | `create_database.sql`, `queries.sql`, `create_index_reviews.json`, `requetes_elasticsearch.txt`, `kibana_saved_objects.ndjson` |
| 3. Consommation | Modèle de sentiment TF-IDF + régression logistique (72,3 % d'accuracy) | `etape3_sentiment.ipynb`, `sentiment_model.pkl`, `vectorizer.pkl` |
| 4. Mise en production | API FastAPI (5 routes, 30 tests), Dockerfile, rapport de dérive | `main.py`, `test_main.py`, `Dockerfile`, `derive/rapport_derive.html` |
| 5. Automatisation | DAG Airflow quotidien, Prometheus, Grafana, logs de l'API, CI GitLab | `dags/scraping_dag.py`, `schema_dag.png`, `docker-compose.yml`, `monitoring/`, `.gitlab-ci.yml` |

---

## Lancer le projet

Prérequis : Docker Desktop installé et démarré.

1. Créer le fichier `.env` **dans le dossier `Etape 5/`** : copier `.env.example` en `Etape 5/.env` et renseigner `POSTGRES_PASSWORD`.
2. Lancer les 9 services :
   ```
   docker-compose -f "Etape 5/docker-compose.yml" up -d
   ```
3. Charger les avis dans ElasticSearch (une seule fois, depuis le dossier `Etape 2`) :
   ```
   cd "Etape 2"
   python load_reviews_to_es.py
   cd ..
   ```
4. Charger les dashboards Kibana (une seule fois ; le dashboard Grafana se charge tout seul) :
   ```
   python "Etape 5/dashboards.py" import
   ```
5. Lancer le DAG sans attendre 6 h : Airflow → `scraping_journalier_trustpilot` → ▶.

| Interface | Adresse |
|-----------|---------|
| API FastAPI | http://localhost:8000/docs |
| Airflow | http://localhost:8080 (admin / admin123) |
| Kibana | http://localhost:5601 → Dashboards |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin123) |

---

## Automatisation (Étape 5)

- DAG `scraping_journalier_trustpilot`, chaque jour à 6 h UTC : scraping → PostgreSQL → scoring du sentiment → ElasticSearch (schéma : `Etape 5/schema_dag.png`).
- Si Trustpilot bloque le scraping (HTTP 403), le DAG repart du dernier CSV collecté.
- Répartition des avis par note (% Excellent… % Bad) : `python "Etape 1 du projet/scraper_repartition_notes.py" --max 200` (ou `--tous`), puis relancer le DAG.

## Monitoring et logs

- Prometheus collecte `/metrics` toutes les 15 s ; Grafana affiche le dashboard « Supply Chain — Monitoring API ».
- Chaque appel à l'API est journalisé (route, statut, durée, sentiment) dans l'index ElasticSearch `api-logs`, visible dans le dashboard Kibana « Logs de l'API ».
- Après une modification des dashboards : `python "Etape 5/dashboards.py" export`, puis commit.

## Rapport de dérive (Étape 4)

```
python "Etape 4/derive/rapport_derive.py"
```
Compare les avis d'avant 2022 et depuis 2022 (χ², Kolmogorov-Smirnov, PSI) et produit `rapport_derive.html`.

## Tests et CI

- `pytest "Etape 4/test_main.py" -v` : 30 tests.
- GitLab CI à chaque push : tests (pytest sur PostgreSQL + lint flake8) → build et push de l'image Docker de l'API → job de déploiement manuel (staging).

---

## Sécurité

- Fichier `.env` jamais commité (voir `.gitignore`).
- Tous les identifiants passent par python-dotenv ou les variables d'environnement.
- Voir `.env.example` pour la liste des variables.
