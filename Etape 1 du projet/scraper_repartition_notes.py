"""
Script de scraping - Etape 1 - Complément : répartition des notes par entreprise
Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER

Les pages catégories de Trustpilot ne donnent que le TrustScore et le nombre d'avis :
les colonnes pct_excellent ... pct_bad du CSV étaient donc à 0.
Ce script ouvre la page de chaque entreprise (https://www.trustpilot.com/review/<slug>),
lit la répartition des notes (5★ à 1★) et remplit ces colonnes en pourcentage.

Il met à jour les deux CSV du projet :
  - Etape 1 du projet/companies_trustpilot.csv
  - Etape 5/dags/companies_trustpilot.csv   (lu par le DAG Airflow -> PostgreSQL, ElasticSearch, API)

Usage (Windows, depuis la racine du projet, Chrome installé) :
    python "Etape 1 du projet/scraper_repartition_notes.py"              # 100 entreprises les plus commentées
    python "Etape 1 du projet/scraper_repartition_notes.py" --max 20     # test rapide
    python "Etape 1 du projet/scraper_repartition_notes.py" --tous       # les 10 664 (plusieurs heures)
Le script reprend où il s'était arrêté (fichier repartition_notes.csv) et sauvegarde toutes les 10 entreprises.
"""

import argparse
import csv
import json
import os
import re
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, ".."))
CSV_ETAPE1 = os.path.join(ICI, "companies_trustpilot.csv")
CSV_DAG = os.path.join(RACINE, "Etape 5", "dags", "companies_trustpilot.csv")
RESULTATS = os.path.join(ICI, "repartition_notes.csv")
COLONNES = ["pct_excellent", "pct_great", "pct_average", "pct_poor", "pct_bad"]   # 5★, 4★, 3★, 2★, 1★

# Noms possibles des compteurs par étoile dans le JSON __NEXT_DATA__ de Trustpilot
CLES_ETOILES = {
    5: ["fiveStar", "fiveStars", "five"],
    4: ["fourStar", "fourStars", "four"],
    3: ["threeStar", "threeStars", "three"],
    2: ["twoStar", "twoStars", "two"],
    1: ["oneStar", "oneStars", "one"],
}


# ---------------------------------------------------------------- extraction (testable sans navigateur)
def _compteurs(d):
    """Si le dict contient un compteur pour chacune des 5 étoiles, renvoie {5: n5, ..., 1: n1}."""
    res = {}
    for etoile, cles in CLES_ETOILES.items():
        for c in cles:
            if c in d and isinstance(d[c], (int, float)):
                res[etoile] = float(d[c])
                break
        else:
            return None
    return res


def chercher_repartition(objet):
    """Parcourt récursivement le JSON et renvoie le premier jeu de compteurs 5★..1★ trouvé."""
    if isinstance(objet, dict):
        trouve = _compteurs(objet)
        if trouve and sum(trouve.values()) > 0:
            return trouve
        for v in objet.values():
            r = chercher_repartition(v)
            if r:
                return r
    elif isinstance(objet, list):
        for v in objet:
            r = chercher_repartition(v)
            if r:
                return r
    return None


def depuis_texte(texte):
    """Plan B : lit les pourcentages affichés sur la page, ex. '5-star 39%' ou '5 étoiles 39 %'."""
    res = {}
    for etoile in range(1, 6):
        m = re.search(rf"{etoile}\s*(?:-?\s*star|étoiles?)\D{{0,20}}?(\d{{1,3}})\s*%", texte, re.I)
        if not m:
            return None
        res[etoile] = float(m.group(1))
    return res if 90 <= sum(res.values()) <= 110 else None


def en_pourcentages(compteurs):
    total = sum(compteurs.values())
    return {col: round(100 * compteurs[e] / total, 1) for col, e in zip(COLONNES, [5, 4, 3, 2, 1])}


def extraire(page_source):
    """Renvoie (pourcentages, méthode) depuis le HTML d'une page entreprise, ou (None, raison)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_source, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            unite = data.get("props", {}).get("pageProps", {}).get("businessUnit", data)
            compteurs = chercher_repartition(unite) or chercher_repartition(data)
            if compteurs:
                return en_pourcentages(compteurs), "json"
        except ValueError:
            pass
    texte = re.sub(r"<[^>]+>", " ", page_source)
    pct = depuis_texte(texte)
    if pct:
        return en_pourcentages(pct), "texte"
    return None, "répartition introuvable"


# ---------------------------------------------------------------- navigateur (même réglages qu'à l'étape 1)
def creer_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    options = Options()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=fr-FR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# ---------------------------------------------------------------- fichiers
def lire_csv(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ecrire_csv(chemin, lignes):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)


def charger_resultats():
    if not os.path.exists(RESULTATS):
        return {}
    return {r["company_slug"]: r for r in lire_csv(RESULTATS)}


def sauver_resultats(resultats):
    if resultats:
        ecrire_csv(RESULTATS, list(resultats.values()))


def fusionner_dans_les_csv(resultats):
    """Recopie les pourcentages trouvés dans les deux CSV du projet (les autres lignes ne bougent pas)."""
    for chemin in (CSV_ETAPE1, CSV_DAG):
        if not os.path.exists(chemin):
            continue
        lignes = lire_csv(chemin)
        maj = 0
        for ligne in lignes:
            r = resultats.get(ligne["company_slug"])
            if r and r.get("statut") == "ok":
                for col in COLONNES:
                    ligne[col] = r[col]
                maj += 1
        ecrire_csv(chemin, lignes)
        print(f"  {os.path.relpath(chemin, RACINE)} : {maj} lignes mises à jour")


# ---------------------------------------------------------------- programme principal
def main():
    p = argparse.ArgumentParser(description="Répartition des notes par entreprise Trustpilot")
    p.add_argument("--max", type=int, default=100, help="nombre d'entreprises (les plus commentées d'abord)")
    p.add_argument("--tous", action="store_true", help="traiter toutes les entreprises du CSV")
    p.add_argument("--pause", type=float, default=4.0, help="secondes d'attente entre deux pages")
    args = p.parse_args()

    entreprises = {}
    for ligne in lire_csv(CSV_ETAPE1):            # une entrée par slug (certaines sont dans 2 catégories)
        entreprises.setdefault(ligne["company_slug"], ligne)
    a_faire = sorted(entreprises.values(), key=lambda l: -float(l["nb_avis_total"] or 0))
    if not args.tous:
        a_faire = a_faire[: args.max]

    resultats = charger_resultats()
    a_faire = [e for e in a_faire if resultats.get(e["company_slug"], {}).get("statut") != "ok"]
    print(f"{len(a_faire)} entreprises à traiter ({len(resultats)} déjà en mémoire)")
    if not a_faire:
        fusionner_dans_les_csv(resultats)
        return

    driver = creer_driver()
    bloques = 0
    try:
        for i, e in enumerate(a_faire, 1):
            slug = e["company_slug"]
            driver.get(f"https://www.trustpilot.com/review/{slug}")
            time.sleep(args.pause)
            page = driver.page_source
            if "login" in driver.current_url.lower() or "Access denied" in page or "403" in driver.title:
                bloques += 1
                pct, statut = None, "bloqué"
            else:
                pct, statut = extraire(page)
            ligne = {"company_slug": slug, "statut": "ok" if pct else statut}
            ligne.update(pct or {c: "" for c in COLONNES})
            resultats[slug] = ligne
            print(f"[{i}/{len(a_faire)}] {slug:40s} {ligne['statut']:22s} {pct or ''}")
            if i % 10 == 0:
                sauver_resultats(resultats)
            if bloques >= 5 and bloques == i:
                print("Trustpilot bloque les 5 premières pages : arrêt. Réessaie plus tard ou avec --pause 8.")
                break
    finally:
        driver.quit()
        sauver_resultats(resultats)

    ok = sum(1 for r in resultats.values() if r["statut"] == "ok")
    print(f"\nRépartition trouvée pour {ok} entreprises. Mise à jour des CSV :")
    fusionner_dans_les_csv(resultats)
    print("Relance le DAG dans Airflow pour propager les pourcentages vers PostgreSQL, ElasticSearch et l'API.")


if __name__ == "__main__":
    main()
