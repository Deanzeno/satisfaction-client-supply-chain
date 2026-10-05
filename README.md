# Supply Chain — Satisfaction des clients

**Projet Data Engineering — Liora / DataScientest**
**Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER**

---

## Description

Pipeline de donnees end-to-end pour analyser la satisfaction client dans la supply chain, a partir des avis Trustpilot.

---

## Etapes

| Etape | Contenu | Outils |
|-------|---------|--------|
| Etape 1 | Scraping Trustpilot (entreprises + avis ShowroomPrive) | Selenium, BeautifulSoup |
| Etape 2 | Stockage structure + recherche | PostgreSQL, ElasticSearch, Kibana |
| Etape 3 | Modele ML analyse de sentiment | scikit-learn (TF-IDF + Regression Logistique) |
| Etape 4 | API REST + tests | FastAPI, pytest (30 tests) |
| Etape 5 | Automatisation + monitoring | Airflow, Docker Compose, Prometheus, Grafana |

---

## Lancer le projet

Prerequisites : Docker Desktop installe et demarre

1. Creer le fichier .env : copier .env.example en .env et renseigner POSTGRES_PASSWORD
2. Lancer : docker-compose -f 'Etape 5/docker-compose.yml' up -d
3. Interfaces :
   - API FastAPI  : http://localhost:8000/docs
   - Airflow      : http://localhost:8080  (admin / admin123)
   - Kibana       : http://localhost:5601
   - Prometheus   : http://localhost:9090
   - Grafana      : http://localhost:3000  (admin / admin123)

---

## Tests (Etape 4)

pytest test_main.py -v -- 30 tests, tous verts

---

## Modele ML (Etape 3)

- Donnees : 592 avis reels ShowroomPrive (Trustpilot)
- Algorithme : Regression Logistique + TF-IDF (1000 features, bigrammes)
- Accuracy : 72.3%
- Classes : positif / neutre / negatif

---

## Securite

- Fichier .env jamais commite (voir .gitignore)
- Toutes les credentials via python-dotenv
- Voir .env.example pour la liste des variables
