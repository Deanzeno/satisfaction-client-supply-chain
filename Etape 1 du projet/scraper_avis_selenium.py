"""
Script de scraping - Etape 1 - Source 2
Recupere les avis ShowroomPrive par filtre d'etoiles
Astuce : 10 pages x 5 etoiles = ~1000 avis sans connexion
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json, time

COMPANY_SLUG   = "showroomprive.com"
PAGES_PAR_STAR = 10   # 10 pages par filtre = restera sous la limite
ETOILES        = [1, 2, 3, 4, 5]

def creer_driver():
    options = Options()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=fr-FR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def scraper_page_avis(driver, slug, page_num, stars):
    # On filtre par nombre d'etoiles dans l'URL
    url = f"https://www.trustpilot.com/review/{slug}?stars={stars}&page={page_num}"
    driver.get(url)
    time.sleep(4)

    # Si Trustpilot redirige vers login -> on s'arrete
    if "login" in driver.current_url.lower():
        return "LOGIN"

    soup       = BeautifulSoup(driver.page_source, "html.parser")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script_tag:
        return None

    try:
        data         = json.loads(script_tag.string)
        page_props   = data["props"]["pageProps"]
        if "reviews" not in page_props:
            return None
        reviews_data = page_props["reviews"]
    except (KeyError, TypeError):
        return None

    if not reviews_data:
        return []

    avis_page = []
    for review in reviews_data:
        try:
            reply = review.get("reply", None)
            avis_page.append({
                "review_id":          f"tp-{review.get('id', '')}",
                "company_name":       "ShowroomPrivé",
                "company_slug":       slug,
                "author":             review.get("consumer", {}).get("displayName", "Anonyme"),
                "date_avis":          review.get("dates", {}).get("publishedDate", "")[:10],
                "nb_etoiles":         review.get("rating", 0),
                "titre":              review.get("title", ""),
                "contenu":            review.get("text", ""),
                "entreprise_repond":  reply is not None,
                "reponse_entreprise": reply.get("message", "") if reply else None,
                "date_scraping":      time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            continue

    return avis_page


# ── PROGRAMME PRINCIPAL ──────────────────────────────────────────────────────

print(f"Scraping : {COMPANY_SLUG}")
print(f"Strategie : {PAGES_PAR_STAR} pages x {len(ETOILES)} etoiles = ~{PAGES_PAR_STAR * len(ETOILES) * 20} avis\n")

driver        = creer_driver()
tous_les_avis = []
ids_vus       = set()  # evite les doublons

try:
    for stars in ETOILES:
        print(f"\n--- Avis {stars} etoile(s) ---")

        for page in range(1, PAGES_PAR_STAR + 1):
            print(f"  Page {page}/{PAGES_PAR_STAR}... ", end="", flush=True)

            avis = scraper_page_avis(driver, COMPANY_SLUG, page, stars)

            if avis == "LOGIN":
                print("Limite atteinte, on passe a l'etoile suivante.")
                break

            if avis is None:
                print("Erreur, page ignoree.")
                time.sleep(3)
                continue

            if len(avis) == 0:
                print("Plus d'avis pour ce filtre.")
                break

            # On ajoute seulement les avis pas encore vus
            nouveaux = 0
            for a in avis:
                if a["review_id"] not in ids_vus:
                    ids_vus.add(a["review_id"])
                    tous_les_avis.append(a)
                    nouveaux += 1

            print(f"{nouveaux} nouveaux | Total : {len(tous_les_avis)}")
            time.sleep(3)

        # Sauvegarde apres chaque categorie d'etoiles
        with open("showroom_reviews.json", "w", encoding="utf-8") as f:
            json.dump(tous_les_avis, f, ensure_ascii=False, indent=2)
        print(f"  >>> Sauvegarde : {len(tous_les_avis)} avis")
        time.sleep(5)

finally:
    driver.quit()

with open("showroom_reviews.json", "w", encoding="utf-8") as f:
    json.dump(tous_les_avis, f, ensure_ascii=False, indent=2)

print(f"\nFini ! {len(tous_les_avis)} avis dans showroom_reviews.json")
