# 📊 Satisfaction Client Supply Chain

Projet de collecte, stockage et visualisation d'avis clients provenant de différentes plateformes (Trustpilot, ShowroomPrivé, etc.).

L'objectif est de mettre en place une pipeline de données complète allant du scraping jusqu'à la visualisation des indicateurs dans un dashboard Streamlit alimenté par Elasticsearch.

---

# 📁 Structure du projet

```
.
├── Configuration/
├── Dashboard/
├── Data/
├── Documentation/
├── ElasticSearch/
├── Old/
└── Scrappers/
```

## 📂 Configuration

Contient les fichiers de configuration du projet :

- fichiers Docker
- configuration Elasticsearch

---

## 📂 Dashboard

Application **Streamlit** (à date extract Kibana) permettant de visualiser les données collectées.

Fonctionnalités prévues :

- Tableau de bord interactif
- KPI
- Evolution des notes
- Répartition des avis
- Filtres par entreprise et date

---

## 📂 Data

Contient les données utilisées durant le projet.

Exemples :

- exports CSV
- fichiers JSON
- jeux de données temporaires
- données de tests

Cette partie va servir d'historique ou de sauvegarde des données brutes.

---

## 📂 Documentation

Documentation technique du projet :

- architecture
- modèle de données
- repoting d'avancement
- documentation API
- choix techniques
