-- =====================================================
-- Requêtes SQL pour vérifier que la base fonctionne
-- Etape 2 - Organisation des données
-- =====================================================

-- 1) Voir toutes les catégories
SELECT * FROM categorie;

-- 2) Voir toutes les entreprises avec le nom de leur catégorie
SELECT entreprise.nom, categorie.nom AS categorie
FROM entreprise
JOIN categorie ON entreprise.categorie_id = categorie.id;

-- 3) Voir les entreprises avec leur trustscore, triées du meilleur au pire
SELECT entreprise.nom, statistiques_avis.trustscore
FROM entreprise
JOIN statistiques_avis ON entreprise.id = statistiques_avis.entreprise_id
ORDER BY statistiques_avis.trustscore DESC;

-- 4) Le nombre d'entreprises par catégorie
SELECT categorie.nom, COUNT(entreprise.id) AS nb_entreprises
FROM categorie
JOIN entreprise ON entreprise.categorie_id = categorie.id
GROUP BY categorie.nom;

-- 5) Les entreprises avec un mauvais trustscore (moins de 2.5) -> clients insatisfaits
SELECT entreprise.nom, statistiques_avis.trustscore, statistiques_avis.pct_bad
FROM entreprise
JOIN statistiques_avis ON entreprise.id = statistiques_avis.entreprise_id
WHERE statistiques_avis.trustscore < 2.5
ORDER BY statistiques_avis.trustscore ASC;

-- 6) Trustscore moyen par catégorie
SELECT categorie.nom, AVG(statistiques_avis.trustscore) AS trustscore_moyen
FROM categorie
JOIN entreprise ON entreprise.categorie_id = categorie.id
JOIN statistiques_avis ON statistiques_avis.entreprise_id = entreprise.id
GROUP BY categorie.nom;
