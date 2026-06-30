-- =====================================================
-- Création de la base de données relationnelle
-- Projet : Satisfaction Client Supply Chain - Trustpilot
-- Etape 2 - Organisation des données
-- =====================================================

-- On supprime les tables si elles existent déjà (pratique pour relancer le script)
DROP TABLE IF EXISTS statistiques_avis;
DROP TABLE IF EXISTS entreprise;
DROP TABLE IF EXISTS categorie;

-- Table 1 : les catégories Trustpilot (ex: atm, online_shopping, logistics)
CREATE TABLE categorie (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL
);

-- Table 2 : les entreprises (une entreprise appartient à une catégorie)
CREATE TABLE entreprise (
    id SERIAL PRIMARY KEY,
    categorie_id INTEGER NOT NULL REFERENCES categorie(id),
    nom VARCHAR(150) NOT NULL,
    slug VARCHAR(150) NOT NULL
);

-- Table 3 : les statistiques d'avis de chaque entreprise
-- (une entreprise a une seule ligne de stats, mise à jour à chaque scraping)
CREATE TABLE statistiques_avis (
    id SERIAL PRIMARY KEY,
    entreprise_id INTEGER NOT NULL REFERENCES entreprise(id),
    trustscore FLOAT,
    nb_avis_total INTEGER,
    pct_excellent FLOAT,
    pct_great FLOAT,
    pct_average FLOAT,
    pct_poor FLOAT,
    pct_bad FLOAT,
    date_scraping TIMESTAMP
);

-- Fin du script
