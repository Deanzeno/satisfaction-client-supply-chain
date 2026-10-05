"""
Script de scraping - Etape 1 - Source 1
Scrape les entreprises Trustpilot par categorie
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv, json, time

# Slugs valides sur Trustpilot (verifies)
CATEGORIES = [
    "atm",               # Banques / ATM       -> fonctionne (47 entreprises)
    "clothing_store",    # Boutiques vetements  -> e-commerce supply chain
    "courier_service",   # Livraison / Logistique
]

def creer_driver():
    options = Options()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=fr-FR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


def scraper_categorie(driver, nom_categorie):
    entreprises = []
    slugs_vus   = set()
    page        = 1
    total_pages = 1

    while page <= total_pages:
        url = f"https://www.trustpilot.com/categories/{nom_categorie}?page={page}"
        print(f"  Page {page}/{total_pages} : {url}")

        driver.get(url)
        time.sleep(3)

        soup       = BeautifulSoup(driver.page_source, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script_tag:
            print("  Pas de donnees, fin.")
            break

        try:
            data      = json.loads(script_tag.string)
            page_props = data["props"]["pageProps"]

            # Verification que la categorie existe bien
            if "businessUnits" not in page_props:
                print(f"  Categorie '{nom_categorie}' introuvable sur Trustpilot.")
                print(f"  Cles disponibles : {list(page_props.keys())}")
                break

            bu            = page_props["businessUnits"]
            business_list = bu["businesses"]
            total_pages   = bu.get("totalPages", 1)

        except (KeyError, TypeError, json.JSONDecodeError) as e:
            print(f"  Erreur structure : {e}, fin.")
            break

        if not business_list:
            print("  Plus d'entreprises.")
            break

        nouveaux = 0
        for business in business_list:
            try:
                if not isinstance(business, dict):
                    continue

                slug = business.get("identifyingName", "")
                nom  = business.get("displayName", "")

                if not slug or slug in slugs_vus:
                    continue

                slugs_vus.add(slug)
                nouveaux += 1

                score   = business.get("trustScore", 0)
                reviews = business.get("numberOfReviews", {})

                if isinstance(reviews, dict):
                    nb_avis    = reviews.get("total", 0)
                    five_star  = reviews.get("fiveStar", 0)
                    four_star  = reviews.get("fourStar", 0)
                    three_star = reviews.get("threeStar", 0)
                    two_star   = reviews.get("twoStar", 0)
                    one_star   = reviews.get("oneStar", 0)
                else:
                    nb_avis    = int(reviews) if reviews else 0
                    five_star  = four_star = three_star = two_star = one_star = 0

                total = nb_avis if nb_avis > 0 else 1

                entreprises.append({
                    "company_name":  nom,
                    "company_slug":  slug,
                    "categorie":     nom_categorie,
                    "trustscore":    score,
                    "nb_avis_total": nb_avis,
                    "pct_excellent": round(five_star  / total * 100, 1),
                    "pct_great":     round(four_star  / total * 100, 1),
                    "pct_average":   round(three_star / total * 100, 1),
                    "pct_poor":      round(two_star   / total * 100, 1),
                    "pct_bad":       round(one_star   / total * 100, 1),
                    "date_scraping": time.strftime("%Y-%m-%d %H:%M:%S"),
                })

            except Exception as e:
                print(f"  Erreur : {e}")
                continue

        print(f"  {nouveaux} nouvelles | Total cumule : {len(entreprises)}")

        if nouveaux == 0:
            print("  Aucune nouvelle entreprise, fin.")
            break

        page += 1
        time.sleep(2)

    return entreprises


# ── PROGRAMME PRINCIPAL ──────────────────────────────────────────────────────

driver          = creer_driver()
all_entreprises = []

try:
    for categorie in CATEGORIES:
        print(f"\nCategorie : {categorie}")
        print("-" * 50)
        resultats = scraper_categorie(driver, categorie)
        all_entreprises.extend(resultats)
        print(f"Total [{categorie}] : {len(resultats)} entreprises")
        time.sleep(3)
finally:
    driver.quit()

if all_entreprises:
    with open("companies_trustpilot.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_entreprises[0].keys())
        writer.writeheader()
        writer.writerows(all_entreprises)
    print(f"\nFini ! {len(all_entreprises)} entreprises dans companies_trustpilot.csv")
else:
    print("\nAucune entreprise recuperee.")
