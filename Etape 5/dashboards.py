"""
Sauvegarde et restauration des dashboards Kibana et Grafana du projet.

  python "Etape 5/dashboards.py" export   -> écrit les fichiers dans le dépôt
  python "Etape 5/dashboards.py" import   -> recharge les dashboards Kibana

- Kibana : les 2 dashboards (Satisfaction des clients, Logs de l'API) avec leurs
  visualisations et leurs data views -> Etape 2/kibana_saved_objects.ndjson
- Grafana : le dashboard "Supply Chain — Monitoring API" ->
  Etape 5/monitoring/grafana/provisioning/dashboards/supply-chain-api.json
  (chargé automatiquement par Grafana au démarrage, rien à importer)

Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER
"""
import base64
import json
import os
import sys
import urllib.request
import uuid

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIBANA = os.getenv("KIBANA_URL", "http://localhost:5601")
GRAFANA = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_AUTH = (os.getenv("GF_USER", "admin"), os.getenv("GF_PASSWORD", "admin123"))

FICHIER_KIBANA = os.path.join(RACINE, "Etape 2", "kibana_saved_objects.ndjson")
FICHIER_GRAFANA = os.path.join(RACINE, "Etape 5", "monitoring", "grafana", "provisioning",
                               "dashboards", "supply-chain-api.json")
DASHBOARDS_KIBANA = ["sc-dashboard", "sc-logs-dashboard"]
UID_GRAFANA = "supply-chain-api"


def requete(url, data=None, headers=None, methode=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=methode)
    with urllib.request.urlopen(req, timeout=60) as rep:
        return rep.read()


def exporter():
    corps = json.dumps({
        "objects": [{"type": "dashboard", "id": i} for i in DASHBOARDS_KIBANA],
        "includeReferencesDeep": True,
        "excludeExportDetails": True,
    }).encode()
    ndjson = requete(f"{KIBANA}/api/saved_objects/_export", corps,
                     {"kbn-xsrf": "true", "Content-Type": "application/json"}, "POST")
    with open(FICHIER_KIBANA, "wb") as f:
        f.write(ndjson)
    nb = len(ndjson.decode().strip().splitlines())
    print(f"Kibana  : {nb} objets -> {os.path.relpath(FICHIER_KIBANA, RACINE)}")

    jeton = base64.b64encode(":".join(GRAFANA_AUTH).encode()).decode()
    rep = json.loads(requete(f"{GRAFANA}/api/dashboards/uid/{UID_GRAFANA}",
                             headers={"Authorization": f"Basic {jeton}"}))
    dashboard = rep["dashboard"]
    dashboard["id"] = None  # Grafana attribue l'id à l'import
    os.makedirs(os.path.dirname(FICHIER_GRAFANA), exist_ok=True)
    with open(FICHIER_GRAFANA, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    print(f"Grafana : {len(dashboard.get('panels', []))} panneaux -> "
          f"{os.path.relpath(FICHIER_GRAFANA, RACINE)}")


def importer():
    with open(FICHIER_KIBANA, "rb") as f:
        contenu = f.read()
    frontiere = uuid.uuid4().hex
    corps = (f"--{frontiere}\r\n"
             f'Content-Disposition: form-data; name="file"; filename="export.ndjson"\r\n'
             f"Content-Type: application/ndjson\r\n\r\n").encode() + contenu + \
        f"\r\n--{frontiere}--\r\n".encode()
    rep = json.loads(requete(f"{KIBANA}/api/saved_objects/_import?overwrite=true", corps,
                             {"kbn-xsrf": "true",
                              "Content-Type": f"multipart/form-data; boundary={frontiere}"}, "POST"))
    print(f"Kibana  : import {'réussi' if rep.get('success') else 'avec erreurs'}, "
          f"{rep.get('successCount', 0)} objets")
    if rep.get("errors"):
        print(json.dumps(rep["errors"], ensure_ascii=False, indent=2))
    print("Grafana : rien à faire, le dashboard est chargé au démarrage du conteneur.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "export":
        exporter()
    elif action == "import":
        importer()
    else:
        print(__doc__)
