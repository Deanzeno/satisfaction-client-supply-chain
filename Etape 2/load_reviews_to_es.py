"""
Script pour créer l'index ElasticSearch "reviews"
et y insérer les avis récoltés à l'étape 1 (showroom_reviews.json)
"""

import json
from elasticsearch import Elasticsearch

# Connexion à ElasticSearch (en local)
es = Elasticsearch("http://localhost:9200")

# On lit le mapping qu'on a préparé
with open("create_index_reviews.json", encoding="utf-8") as f:
    mapping = json.load(f)

# On crée l'index s'il n'existe pas déjà
if not es.indices.exists(index="reviews"):
    es.indices.create(index="reviews", body=mapping)
    print("Index 'reviews' créé")
else:
    print("L'index 'reviews' existe déjà")

# On lit le fichier JSON des avis (issu du scraping étape 1)
with open("showroom_reviews.json", encoding="utf-8") as f:
    avis_list = json.load(f)

print(f"{len(avis_list)} avis à insérer...")

# On insère chaque avis dans l'index
for avis in avis_list:
    es.index(index="reviews", id=avis["review_id"], document=avis)

print("Tous les avis ont été insérés dans ElasticSearch !")
