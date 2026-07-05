"""
Script pour créer l'index ElasticSearch "reviews"
et y insérer les avis récoltés à l'étape 1 (showroom_reviews.json)
"""

import json
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

info = es.info()
print(f"ElasticSearch connecté : version {info['version']['number']}")

# On supprime l'index s'il existe (pour repartir proprement)
if es.indices.exists(index="reviews"):
    es.indices.delete(index="reviews")
    print("Ancien index supprimé")

# On recrée l'index avec le bon mapping
with open("create_index_reviews.json", encoding="utf-8") as f:
    mapping = json.load(f)

es.indices.create(index="reviews", mappings=mapping["mappings"])
print("Index 'reviews' créé")

# On lit les avis
with open("showroom_reviews.json", encoding="utf-8") as f:
    avis_list = json.load(f)

print(f"{len(avis_list)} avis à insérer...")

# On insère chaque avis
for i, avis in enumerate(avis_list):
    # On corrige le format de date : espace -> T (format ISO requis par ElasticSearch)
    avis_propre = avis.copy()
    if avis_propre.get("date_scraping"):
        avis_propre["date_scraping"] = avis_propre["date_scraping"].replace(" ", "T")

    es.index(index="reviews", id=avis_propre["review_id"], document=avis_propre)

    if (i + 1) % 100 == 0:
        print(f"  {i + 1}/{len(avis_list)} insérés...")

print(f"Tous les {len(avis_list)} avis insérés dans ElasticSearch !")
