# Supply Chain — Satisfaction des clients 🚚

**Projet Data Engineering — Liora / DataScientest**  
**Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER**

---

## Description

Pipeline de données end-to-end pour analyser la satisfaction client
dans la supply chain, à partir des avis Trustpilot.

---

## Architecture du projet

---

## Étapes

| Étape | Contenu | Outils |
|-------|---------|--------|
| Étape 1 | Scraping Trustpilot (entreprises + avis ShowroomPrivé) | Selenium, BeautifulSoup |
| Étape 2 | Stockage structuré + recherche | PostgreSQL, ElasticSearch, Kibana |
| Étape 3 | Modèle ML analyse de sentiment | scikit-learn (TF-IDF + Régression Logistique) |
| Étape 4 | API REST + tests | FastAPI, pytest (30 tests) |
| Étape 5 | Automatisation + monitoring | Airflow, Docker Compose, Prometheus, Grafana |

---

## Lancer le projet (Étape 5 — stack complète)

**Prérequis :** Docker Desktop installé et démarré

```bash
# 1. Créer le fichier .env (voir .env.example)
cp .env.example .env
# Editer .env et renseigner POSTGRES_PASSWORD

# 2. Lancer tous les services
docker-compose -f "Etape 5/docker-compose.yml" up -d

# 3. Accéder aux interfaces
#    API FastAPI  : http://localhost:8000/docs
#    Airflow      : http://localhost:8080  (admin / admin123)
#    Kibana       : http://localhost:5601
#    Prometheus   : http://localhost:9090
#    Grafana      : http://localhost:3000  (admin / admin123)
```

---

## Tests (Étape 4)

```bash
cd "Etape 4"
pip install -r requirements.txt
pytest test_main.py -v
# 30 tests — tous verts ✅
```

---

## Modèle ML (Étape 3)

- **Données** : 592 avis réels ShowroomPrivé (Trustpilot)
- **Algorithme** : Régression Logistique + TF-IDF (1000 features, bigrammes)
- **Accuracy** : 72.3% — class_weight='balanced' pour corriger le déséquilibre des classes
- **Classes** : positif / neutre / négatif

---

## Sécurité

- Fichier .env jamais commité (voir .gitignore)
- Toutes les credentials via python-dotenv
- Voir .env.example pour la liste des variables nécessaires
