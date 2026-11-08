"""
Initialisation automatique d'ElasticSearch et de Kibana (conteneur kibana-init).

Lancé une fois à chaque `docker-compose up`, puis le conteneur s'arrête.
Il ne fait que ce qui manque, donc il ne touche jamais à des données déjà là :

1. Index "reviews" : s'il est absent ou vide, il est créé avec le mapping de
   l'étape 2 (create_index_reviews.json) et rempli avec les 592 avis
   (showroom_reviews.json).
2. Dashboards Kibana : s'ils sont absents, ils sont importés depuis
   kibana_saved_objects.ndjson (dashboards, visualisations et data views).

Bibliothèque standard Python uniquement : aucune dépendance à installer.
Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

ES = os.getenv("ES_URL", "http://elasticsearch:9200")
KIBANA = os.getenv("KIBANA_URL", "http://kibana:5601")
DONNEES = os.getenv("DATA_DIR", "/data")
DELAI_MAX = int(os.getenv("INIT_TIMEOUT", "600"))  # secondes
DASHBOARDS = ["sc-dashboard", "sc-logs-dashboard"]


def http(methode, url, corps=None, entetes=None):
    """Renvoie (code HTTP, contenu) sans lever d'exception sur 4xx/5xx."""
    req = urllib.request.Request(url, data=corps, headers=entetes or {}, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=60) as rep:
            return rep.status, rep.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return 0, b""


def attendre(nom, test):
    debut = time.time()
    while time.time() - debut < DELAI_MAX:
        if test():
            print(f"{nom} est prêt ({int(time.time() - debut)} s)", flush=True)
            return
        time.sleep(5)
    sys.exit(f"ERREUR : {nom} ne répond pas après {DELAI_MAX} s")


def es_pret():
    code, contenu = http("GET", f"{ES}/_cluster/health")
    return code == 200 and json.loads(contenu).get("status") in ("green", "yellow")


def kibana_pret():
    code, contenu = http("GET", f"{KIBANA}/api/status")
    if code != 200:
        return False
    statut = json.loads(contenu).get("status", {})
    return statut.get("overall", {}).get("level") == "available"


def charger_avis():
    code, contenu = http("GET", f"{ES}/reviews/_count")
    if code == 200 and json.loads(contenu).get("count", 0) > 0:
        print(f"Index reviews : déjà rempli ({json.loads(contenu)['count']} avis), rien à faire")
        return
    if code == 404:
        with open(os.path.join(DONNEES, "create_index_reviews.json"), encoding="utf-8") as f:
            mapping = json.load(f)["mappings"]
        corps = json.dumps({"settings": {"number_of_shards": 1, "number_of_replicas": 0},
                            "mappings": mapping}).encode()
        code, contenu = http("PUT", f"{ES}/reviews", corps, {"Content-Type": "application/json"})
        if code != 200:
            sys.exit(f"ERREUR création de l'index reviews : {code} {contenu[:300]}")
        print("Index reviews : créé avec le mapping de l'étape 2")

    with open(os.path.join(DONNEES, "showroom_reviews.json"), encoding="utf-8") as f:
        avis = json.load(f)
    lignes = []
    for a in avis:
        doc = dict(a)
        if doc.get("date_scraping"):  # format ISO attendu par ElasticSearch
            doc["date_scraping"] = doc["date_scraping"].replace(" ", "T")
        lignes.append(json.dumps({"index": {"_id": doc["review_id"]}}))
        lignes.append(json.dumps(doc, ensure_ascii=False))
    corps = ("\n".join(lignes) + "\n").encode("utf-8")
    code, contenu = http("POST", f"{ES}/reviews/_bulk?refresh=true", corps,
                         {"Content-Type": "application/x-ndjson"})
    resultat = json.loads(contenu) if contenu else {}
    if code != 200 or resultat.get("errors"):
        sys.exit(f"ERREUR chargement des avis : {code} {contenu[:300]}")
    print(f"Index reviews : {len(resultat['items'])} avis chargés")


def importer_dashboards():
    manquants = [d for d in DASHBOARDS
                 if http("GET", f"{KIBANA}/api/saved_objects/dashboard/{d}")[0] != 200]
    if not manquants:
        print("Dashboards Kibana : déjà présents, rien à faire")
        return
    with open(os.path.join(DONNEES, "kibana_saved_objects.ndjson"), "rb") as f:
        contenu = f.read()
    frontiere = uuid.uuid4().hex
    corps = (f"--{frontiere}\r\n"
             'Content-Disposition: form-data; name="file"; filename="export.ndjson"\r\n'
             "Content-Type: application/ndjson\r\n\r\n").encode() + contenu + \
        f"\r\n--{frontiere}--\r\n".encode()
    code, rep = http("POST", f"{KIBANA}/api/saved_objects/_import?overwrite=true", corps,
                     {"kbn-xsrf": "true", "Content-Type": f"multipart/form-data; boundary={frontiere}"})
    resultat = json.loads(rep) if rep else {}
    if code != 200 or not resultat.get("success"):
        sys.exit(f"ERREUR import Kibana : {code} {rep[:500]}")
    print(f"Dashboards Kibana : {resultat.get('successCount')} objets importés "
          f"(manquaient : {', '.join(manquants)})")


if __name__ == "__main__":
    attendre("ElasticSearch", es_pret)
    charger_avis()
    attendre("Kibana", kibana_pret)
    importer_dashboards()
    print("Initialisation terminée", flush=True)
