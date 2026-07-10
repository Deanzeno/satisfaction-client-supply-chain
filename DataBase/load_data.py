"""
Script de chargement des données CSV dans la base PostgreSQL
Etape 2 - Organisation des données
"""
from pathlib import Path
import csv
import psycopg2

# Connexion à la base de données (à adapter avec vos identifiants)
conn = psycopg2.connect(
    host="localhost",
    database="satisfaction_client",
    user="postgres",
    password="postgres"
)
cur = conn.cursor()



# Racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Chemin vers le fichier CSV
csv_file = BASE_DIR / "Data" / "companies_trustpilot.csv"
# On lit le fichier CSV récolté à l'étape 1
with csv_file.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    lignes = list(reader)

print(f"{len(lignes)} lignes trouvées dans le CSV")

# Dictionnaire pour ne pas recréer une catégorie qui existe déjà
categories_deja_creees = {}

for ligne in lignes:

    nom_categorie = ligne["categorie"]

    # Si la catégorie n'existe pas encore en base, on la crée
    if nom_categorie not in categories_deja_creees:
        cur.execute(
            "INSERT INTO categorie (nom) VALUES (%s) RETURNING id",
            (nom_categorie,)
        )
        categorie_id = cur.fetchone()[0]
        categories_deja_creees[nom_categorie] = categorie_id
    else:
        categorie_id = categories_deja_creees[nom_categorie]

    # On insère l'entreprise
    cur.execute(
        "INSERT INTO entreprise (categorie_id, nom, slug) VALUES (%s, %s, %s) RETURNING id",
        (categorie_id, ligne["company_name"], ligne["company_slug"])
    )
    entreprise_id = cur.fetchone()[0]

    # On insère les statistiques de l'entreprise
    cur.execute(
        """
        INSERT INTO statistiques_avis
        (entreprise_id, trustscore, nb_avis_total, pct_excellent, pct_great,
         pct_average, pct_poor, pct_bad, date_scraping)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            entreprise_id,
            ligne["trustscore"],
            ligne["nb_avis_total"],
            ligne["pct_excellent"],
            ligne["pct_great"],
            ligne["pct_average"],
            ligne["pct_poor"],
            ligne["pct_bad"],
            ligne["date_scraping"],
        )
    )

# On valide les changements dans la base
conn.commit()

print("Chargement terminé !")
print(f"{len(categories_deja_creees)} catégories créées")
print(f"{len(lignes)} entreprises insérées")

cur.close()
conn.close()
