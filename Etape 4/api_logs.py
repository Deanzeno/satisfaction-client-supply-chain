"""
Journalisation des appels de l'API (logs API) — Étape 5, monitoring
Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER

Chaque requête produit une ligne de log JSON :
  - toujours écrite sur la sortie standard  -> visible avec `docker logs <conteneur api>`
  - et, si ES_LOGS_URL est défini, envoyée dans l'index ElasticSearch "api-logs"
    -> consultable dans Kibana

L'envoi vers ElasticSearch se fait en arrière-plan (thread + file d'attente) :
une API lente ou indisponible côté ElasticSearch ne ralentit ni ne casse jamais l'API.
GET /metrics n'est pas journalisé (Prometheus l'appelle toutes les 15 secondes).
"""

import json
import logging
import os
import queue
import threading
import time
import urllib.request
from datetime import datetime, timezone

INDEX = "api-logs"
ES_LOGS_URL = os.getenv("ES_LOGS_URL", "").rstrip("/")   # ex. http://elasticsearch:9200 ; vide = pas d'envoi
CHEMINS_IGNORES = {"/metrics"}
LONGUEUR_MAX_TEXTE = 500                                   # on garde le début du texte envoyé à /predict

MAPPING = {
    "settings": {"number_of_replicas": 0},
    "mappings": {"properties": {
        "@timestamp": {"type": "date"},
        "methode": {"type": "keyword"},
        "chemin": {"type": "keyword"},
        "statut": {"type": "integer"},
        "classe_statut": {"type": "keyword"},
        "duree_ms": {"type": "float"},
        "sentiment": {"type": "keyword"},
        "confiance": {"type": "float"},
        "longueur_texte": {"type": "integer"},
        "texte": {"type": "text"},
        "erreur": {"type": "keyword"},
    }},
}

logger = logging.getLogger("api")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

_file = queue.Queue(maxsize=10_000)
_envoyes = {"ok": 0, "echecs": 0}


def _post(url, corps, methode="POST"):
    req = urllib.request.Request(url, data=json.dumps(corps).encode("utf-8"), method=methode,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2) as rep:
        return rep.status


def _travailleur():
    """Thread d'arrière-plan : crée l'index si besoin, puis envoie les logs un par un."""
    index_pret = False
    while True:
        doc = _file.get()
        try:
            if not index_pret:
                try:
                    _post(f"{ES_LOGS_URL}/{INDEX}", MAPPING, methode="PUT")
                except Exception:
                    pass  # l'index existe déjà (400) ou ES pas encore prêt : on tente quand même l'envoi
                index_pret = True
            _post(f"{ES_LOGS_URL}/{INDEX}/_doc", doc)
            _envoyes["ok"] += 1
        except Exception:
            _envoyes["echecs"] += 1
            index_pret = False  # on retentera la création de l'index au prochain log
        finally:
            _file.task_done()


if ES_LOGS_URL:
    threading.Thread(target=_travailleur, daemon=True, name="api-logs").start()


def journaliser(doc):
    """Écrit le log sur stdout et le met en file pour ElasticSearch (sans jamais lever d'erreur)."""
    try:
        logger.info(json.dumps(doc, ensure_ascii=False))
        if ES_LOGS_URL:
            _file.put_nowait(doc)
    except Exception:
        pass


async def middleware_logs(request, call_next):
    """Middleware FastAPI : mesure chaque requête et la journalise."""
    if request.url.path in CHEMINS_IGNORES:
        return await call_next(request)
    debut = time.perf_counter()
    statut, erreur = 500, None
    try:
        reponse = await call_next(request)
        statut = reponse.status_code
        return reponse
    except Exception as e:
        erreur = type(e).__name__
        raise
    finally:
        doc = {
            "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "methode": request.method,
            "chemin": request.url.path,
            "statut": statut,
            "classe_statut": f"{statut // 100}xx",
            "duree_ms": round((time.perf_counter() - debut) * 1000, 2),
        }
        if erreur:
            doc["erreur"] = erreur
        # Informations ajoutées par /predict (voir main.py)
        extra = getattr(request.state, "log_extra", None)
        if extra:
            doc.update(extra)
        journaliser(doc)


def infos_prediction(texte, sentiment, confiance):
    """Champs ajoutés au log d'un appel à /predict : utiles pour suivre la dérive des entrées."""
    return {
        "sentiment": sentiment,
        "confiance": confiance,
        "longueur_texte": len(texte.split()),
        "texte": texte[:LONGUEUR_MAX_TEXTE],
    }
