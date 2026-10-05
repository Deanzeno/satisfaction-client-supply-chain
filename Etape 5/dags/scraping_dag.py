"""
DAG Airflow — Scraping journalier Trustpilot
Supply Chain — Satisfaction des clients
Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER

Pipeline quotidien (06h00) :
    t1_scraper_trustpilot → t2_charger_postgres → t3_scorer_sentiment → t4_sync_elasticsearch

Schéma PostgreSQL (base : satisfaction_client) :
    - categorie(id, nom)
    - entreprise(id, categorie_id, nom, slug)
    - statistiques_avis(id, entreprise_id, trustscore, nb_avis_total,
                        pct_excellent, pct_great, pct_average, pct_poor,
                        pct_bad, date_scraping)
"""

from datetime import datetime, timedelta
import json
import os
import time
import urllib.request
import urllib.error

import psycopg2
import joblib
import requests
from bs4 import BeautifulSoup

from airflow import DAG
from airflow.operators.python import PythonOperator

# ═══════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════

DEFAULT_ARGS = {
    "owner":           "datascientest",
    "retries":         2,
    "retry_delay":     timedelta(minutes=5),
    "depends_on_past": False,
    "email_on_failure": False,
}

# Catégories Trustpilot à scraper (vérifiées sur le site)
CATEGORIES = ["atm", "clothing_store", "courier_service"]
# Nombre de pages par catégorie (max 5 pour ne pas surcharger Trustpilot)
PAGES_PAR_CATEGORIE = 3

# Configuration PostgreSQL — via variables d'environnement Docker Compose
POSTGRES_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "postgres"),
    "port":     int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname":   os.getenv("POSTGRES_DB", "satisfaction_client"),
    "user":     os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# ElasticSearch — index dédié Étape 5
ES_HOST  = os.getenv("ES_HOST", "http://elasticsearch:9200")
ES_INDEX = "companies_supply_chain"

# Modèles ML — montés en volume dans le conteneur Airflow
MODEL_PATH = os.getenv("MODEL_PATH", "/opt/airflow/models/sentiment_model.pkl")
VEC_PATH   = os.getenv("VEC_PATH",   "/opt/airflow/models/vectorizer.pkl")

# En-têtes HTTP pour éviter le blocage par Trustpilot
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Textes synthétiques associés à chaque classe de sentiment
# → utilisés pour appliquer le modèle ML sur des données agrégées
TEXTES_PAR_SENTIMENT = {
    "positif": "livraison rapide excellent service impeccable très satisfait je recommande",
    "negatif": "colis perdu service inexistant délai dépassé très déçu mauvaise expérience",
    "neutre":  "service correct délai raisonnable rien à signaler commande conforme attendue",
}


# ═══════════════════════════════════════════════════════
# Tâche 1 : Scraping Trustpilot
# ═══════════════════════════════════════════════════════

def scraper_trustpilot(**context):
    """
    Scrape les pages de catégories Trustpilot via requests + BeautifulSoup.
    Utilise le JSON embarqué dans les balises <script id="__NEXT_DATA__">
    comme dans les scrapers manuels de l'Étape 1.

    Les données sont poussées dans XCom (clé : 'companies').
    Retourne le nombre total d'entreprises récupérées.
    """
    all_companies = []
    slugs_vus     = set()

    for categorie in CATEGORIES:
        print(f"\n── Catégorie : {categorie} ──")

        for page_num in range(1, PAGES_PAR_CATEGORIE + 1):
            url = f"https://www.trustpilot.com/categories/{categorie}?page={page_num}"

            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)

                if resp.status_code != 200:
                    print(f"  Page {page_num} : HTTP {resp.status_code}, ignorée.")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

                if not script_tag:
                    print(f"  Page {page_num} : pas de données JSON, fin de la catégorie.")
                    break

                data       = json.loads(script_tag.string)
                page_props = data.get("props", {}).get("pageProps", {})

                if "businessUnits" not in page_props:
                    print(f"  Page {page_num} : catégorie introuvable sur Trustpilot.")
                    break

                bu            = page_props["businessUnits"]
                business_list = bu.get("businesses", [])
                total_pages   = bu.get("totalPages", 1)

                if not business_list:
                    print(f"  Page {page_num} : plus d'entreprises.")
                    break

                nouveaux = 0
                for biz in business_list:
                    if not isinstance(biz, dict):
                        continue

                    slug = biz.get("identifyingName", "")
                    nom  = biz.get("displayName", "")

                    if not slug or slug in slugs_vus:
                        continue

                    slugs_vus.add(slug)

                    # Extraction du score et des statistiques
                    score   = float(biz.get("trustScore", 0) or 0)
                    reviews = biz.get("numberOfReviews", {})

                    if isinstance(reviews, dict):
                        nb_avis    = int(reviews.get("total", 0) or 0)
                        five_star  = int(reviews.get("fiveStar", 0) or 0)
                        four_star  = int(reviews.get("fourStar", 0) or 0)
                        three_star = int(reviews.get("threeStar", 0) or 0)
                        two_star   = int(reviews.get("twoStar", 0) or 0)
                        one_star   = int(reviews.get("oneStar", 0) or 0)
                    else:
                        nb_avis    = int(reviews or 0)
                        five_star  = four_star = three_star = two_star = one_star = 0

                    total = nb_avis if nb_avis > 0 else 1

                    all_companies.append({
                        "company_name":  nom,
                        "company_slug":  slug,
                        "categorie":     categorie,
                        "trustscore":    score,
                        "nb_avis_total": nb_avis,
                        "pct_excellent": round(five_star  / total * 100, 1),
                        "pct_great":     round(four_star  / total * 100, 1),
                        "pct_average":   round(three_star / total * 100, 1),
                        "pct_poor":      round(two_star   / total * 100, 1),
                        "pct_bad":       round(one_star   / total * 100, 1),
                        "date_scraping": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    nouveaux += 1

                print(f"  Page {page_num}/{total_pages} : {nouveaux} nouvelles | Total : {len(all_companies)}")

                if page_num >= total_pages:
                    break

                time.sleep(2)   # pause pour ne pas surcharger Trustpilot

            except Exception as e:
                print(f"  Erreur page {page_num} ({url}) : {e}")
                time.sleep(3)
                continue

    print(f"\n[scraper_trustpilot] ✅ {len(all_companies)} entreprises récupérées au total")
    context["ti"].xcom_push(key="companies", value=all_companies)
    return len(all_companies)


# ═══════════════════════════════════════════════════════
# Tâche 2 : Chargement PostgreSQL
# ═══════════════════════════════════════════════════════

def charger_postgres(**context):
    """
    Charge les données scrapées dans PostgreSQL en respectant le schéma :
        categorie → entreprise → statistiques_avis

    Stratégie :
    - categorie  : SELECT d'abord, INSERT seulement si elle n'existe pas
    - entreprise : SELECT d'abord sur le slug, INSERT seulement si nouvelle
    - statistiques_avis : INSERT à chaque exécution (historique des scraping)

    Retourne le nombre de lignes insérées dans statistiques_avis.
    """
    companies = context["ti"].xcom_pull(task_ids="scraper_trustpilot", key="companies")

    if not companies:
        print("[charger_postgres] Aucune donnée à charger.")
        return 0

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cur  = conn.cursor()

    categories_cache  = {}  # nom → id
    entreprises_cache = {}  # slug → id
    nb_stats          = 0

    for company in companies:
        cat_nom  = company["categorie"]
        ent_nom  = company["company_name"]
        ent_slug = company["company_slug"]

        # ── 1. Catégorie : récupérer ou créer ─────────────────────────
        if cat_nom not in categories_cache:
            cur.execute("SELECT id FROM categorie WHERE nom = %s", (cat_nom,))
            row = cur.fetchone()
            if row:
                categories_cache[cat_nom] = row[0]
            else:
                cur.execute(
                    "INSERT INTO categorie (nom) VALUES (%s) RETURNING id",
                    (cat_nom,)
                )
                categories_cache[cat_nom] = cur.fetchone()[0]
                print(f"  [postgres] Nouvelle catégorie : {cat_nom}")

        cat_id = categories_cache[cat_nom]

        # ── 2. Entreprise : récupérer ou créer ────────────────────────
        if ent_slug not in entreprises_cache:
            cur.execute("SELECT id FROM entreprise WHERE slug = %s", (ent_slug,))
            row = cur.fetchone()
            if row:
                entreprises_cache[ent_slug] = row[0]
            else:
                cur.execute(
                    "INSERT INTO entreprise (categorie_id, nom, slug) VALUES (%s, %s, %s) RETURNING id",
                    (cat_id, ent_nom, ent_slug)
                )
                entreprises_cache[ent_slug] = cur.fetchone()[0]
                print(f"  [postgres] Nouvelle entreprise : {ent_nom} ({ent_slug})")

        ent_id = entreprises_cache[ent_slug]

        # ── 3. Statistiques : toujours insérer (historique) ───────────
        cur.execute(
            """
            INSERT INTO statistiques_avis
                (entreprise_id, trustscore, nb_avis_total,
                 pct_excellent, pct_great, pct_average, pct_poor, pct_bad,
                 date_scraping)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ent_id,
                company["trustscore"],
                company["nb_avis_total"],
                company["pct_excellent"],
                company["pct_great"],
                company["pct_average"],
                company["pct_poor"],
                company["pct_bad"],
                company["date_scraping"],
            )
        )
        nb_stats += 1

    conn.commit()
    cur.close()
    conn.close()

    print(
        f"\n[charger_postgres] ✅ "
        f"{len(categories_cache)} catégories, "
        f"{len(entreprises_cache)} entreprises, "
        f"{nb_stats} lignes dans statistiques_avis"
    )
    return nb_stats


# ═══════════════════════════════════════════════════════
# Tâche 3 : Scoring Sentiment ML
# ═══════════════════════════════════════════════════════

def scorer_sentiment(**context):
    """
    Applique le modèle ML (Étape 3) pour attribuer un sentiment à chaque entreprise.

    Méthode :
      - Le modèle a été entraîné sur des textes d'avis (ShowroomPrivé)
      - Pour des données agrégées (trustscore + %) on utilise un texte
        synthétique représentatif du niveau de satisfaction :
          · trustscore ≥ 4.0 et pct_bad < 10 → texte "positif"
          · trustscore < 2.5 ou pct_bad > 40  → texte "negatif"
          · sinon                              → texte "neutre"
      - Le modèle prédit la classe et la confiance associée

    Les résultats sont poussés dans XCom (clé : 'sentiment_scores')
    sous la forme {slug: {"sentiment": str, "confiance": float}}.
    """
    companies = context["ti"].xcom_pull(task_ids="scraper_trustpilot", key="companies")

    if not companies:
        print("[scorer_sentiment] Aucune donnée à scorer.")
        context["ti"].xcom_push(key="sentiment_scores", value={})
        return 0

    # Chargement du modèle ML
    try:
        modele     = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VEC_PATH)
        print(f"[scorer_sentiment] ✅ Modèle chargé depuis {MODEL_PATH}")
    except Exception as e:
        print(f"[scorer_sentiment] ⚠️  Modèle non chargé ({e}) — scores ignorés.")
        context["ti"].xcom_push(key="sentiment_scores", value={})
        return 0

    def choisir_texte(company: dict) -> str:
        """Sélectionne le texte type selon le trustscore et le pct_bad."""
        score   = company.get("trustscore", 0)
        pct_bad = company.get("pct_bad", 0)
        if score >= 4.0 and pct_bad < 10:
            return TEXTES_PAR_SENTIMENT["positif"]
        elif score < 2.5 or pct_bad > 40:
            return TEXTES_PAR_SENTIMENT["negatif"]
        else:
            return TEXTES_PAR_SENTIMENT["neutre"]

    sentiment_scores = {}
    nb_positif = nb_negatif = nb_neutre = 0

    for company in companies:
        slug  = company["company_slug"]
        texte = choisir_texte(company)

        X     = vectorizer.transform([texte])
        label = modele.predict(X)[0]
        proba = modele.predict_proba(X)[0]

        sentiment_scores[slug] = {
            "sentiment": label,
            "confiance": round(float(max(proba)), 4),
        }

        if   label == "positif": nb_positif += 1
        elif label == "negatif": nb_negatif += 1
        else:                    nb_neutre  += 1

    print(
        f"\n[scorer_sentiment] ✅ {len(sentiment_scores)} entreprises scorées : "
        f"positif={nb_positif}, negatif={nb_negatif}, neutre={nb_neutre}"
    )
    context["ti"].xcom_push(key="sentiment_scores", value=sentiment_scores)
    return len(sentiment_scores)


# ═══════════════════════════════════════════════════════
# Tâche 4 : Synchronisation ElasticSearch
# ═══════════════════════════════════════════════════════

def sync_elasticsearch(**context):
    """
    Synchronise les données entreprises + sentiment vers ElasticSearch.
    Index cible : companies_supply_chain

    Chaque document ES est identifié par le slug de l'entreprise.
    Les données incluent : stats Trustpilot + sentiment ML + date.
    """
    companies        = context["ti"].xcom_pull(task_ids="scraper_trustpilot", key="companies")
    sentiment_scores = context["ti"].xcom_pull(task_ids="scorer_sentiment",   key="sentiment_scores") or {}

    if not companies:
        print("[sync_elasticsearch] Aucune donnée à synchroniser.")
        return 0

    # ── Créer l'index ES si nécessaire ────────────────────────────────
    mapping = {
        "mappings": {
            "properties": {
                "company_name":  {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
                "company_slug":  {"type": "keyword"},
                "categorie":     {"type": "keyword"},
                "trustscore":    {"type": "float"},
                "nb_avis_total": {"type": "integer"},
                "pct_excellent": {"type": "float"},
                "pct_great":     {"type": "float"},
                "pct_average":   {"type": "float"},
                "pct_poor":      {"type": "float"},
                "pct_bad":       {"type": "float"},
                "sentiment":     {"type": "keyword"},
                "confiance":     {"type": "float"},
                "date_scraping": {
                    "type":   "date",
                    "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                },
            }
        }
    }

    try:
        req = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX}",
            method="PUT",
            data=json.dumps(mapping).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"[sync_elasticsearch] Index '{ES_INDEX}' créé.")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Index déjà existant (resource_already_exists_exception)
            pass
        else:
            print(f"[sync_elasticsearch] ⚠️  Erreur création index : {e}")
    except Exception as e:
        print(f"[sync_elasticsearch] ⚠️  Impossible de créer l'index : {e}")

    # ── Indexer chaque entreprise ──────────────────────────────────────
    nb_ok    = 0
    nb_erreur = 0

    for company in companies:
        slug   = company["company_slug"]
        scores = sentiment_scores.get(slug, {"sentiment": "neutre", "confiance": 0.0})

        document = {
            "company_name":  company["company_name"],
            "company_slug":  slug,
            "categorie":     company["categorie"],
            "trustscore":    company["trustscore"],
            "nb_avis_total": company["nb_avis_total"],
            "pct_excellent": company["pct_excellent"],
            "pct_great":     company["pct_great"],
            "pct_average":   company["pct_average"],
            "pct_poor":      company["pct_poor"],
            "pct_bad":       company["pct_bad"],
            "sentiment":     scores["sentiment"],
            "confiance":     scores["confiance"],
            "date_scraping": company["date_scraping"],
        }

        try:
            req = urllib.request.Request(
                f"{ES_HOST}/{ES_INDEX}/_doc/{slug}",
                method="PUT",
                data=json.dumps(document).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            nb_ok += 1
        except Exception as e:
            print(f"  [ES] Erreur pour {slug} : {e}")
            nb_erreur += 1

    print(
        f"\n[sync_elasticsearch] ✅ {nb_ok}/{len(companies)} documents indexés dans '{ES_INDEX}'"
        + (f" ({nb_erreur} erreurs)" if nb_erreur else "")
    )
    return nb_ok


# ═══════════════════════════════════════════════════════
# Définition du DAG
# ═══════════════════════════════════════════════════════

with DAG(
    dag_id="scraping_journalier_trustpilot",
    description=(
        "Pipeline quotidien : scraping Trustpilot → PostgreSQL "
        "→ scoring sentiment ML → synchronisation ElasticSearch"
    ),
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 6 * * *",   # Tous les jours à 06h00 UTC
    catchup=False,
    tags=["supply-chain", "trustpilot", "ml", "etape5"],
) as dag:

    t1_scraper = PythonOperator(
        task_id="scraper_trustpilot",
        python_callable=scraper_trustpilot,
    )

    t2_charger = PythonOperator(
        task_id="charger_postgres",
        python_callable=charger_postgres,
    )

    t3_scorer = PythonOperator(
        task_id="scorer_sentiment",
        python_callable=scorer_sentiment,
    )

    t4_sync = PythonOperator(
        task_id="sync_elasticsearch",
        python_callable=sync_elasticsearch,
    )

    # ── Enchaînement des tâches ────────────────────────────────────────
    t1_scraper >> t2_charger >> t3_scorer >> t4_sync
