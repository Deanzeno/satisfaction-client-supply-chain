-- =====================================================
-- Jeu de données de test pour la CI GitLab (stage test)
-- Chargé après Etape 2/create_database.sql, avant pytest
-- Projet : Satisfaction Client Supply Chain
-- =====================================================

INSERT INTO categorie (nom) VALUES
    ('atm'),
    ('clothing_store'),
    ('courier_service');

INSERT INTO entreprise (categorie_id, nom, slug) VALUES
    ((SELECT id FROM categorie WHERE nom = 'atm'),             'ATM Test One',     'atm-test-one.com'),
    ((SELECT id FROM categorie WHERE nom = 'atm'),             'ATM Test Two',     'atm-test-two.com'),
    ((SELECT id FROM categorie WHERE nom = 'clothing_store'),  'Clothing Test',    'clothing-test.com'),
    ((SELECT id FROM categorie WHERE nom = 'courier_service'), 'Courier Test',     'courier-test.com');

-- Une ligne de statistiques par entreprise...
INSERT INTO statistiques_avis
    (entreprise_id, trustscore, nb_avis_total, pct_excellent, pct_great, pct_average, pct_poor, pct_bad, date_scraping)
VALUES
    ((SELECT id FROM entreprise WHERE slug = 'atm-test-one.com'),  2.1, 120, 10, 5, 5, 10, 70, '2026-07-02 12:00:00'),
    ((SELECT id FROM entreprise WHERE slug = 'atm-test-two.com'),  3.4,  45, 30, 20, 10, 10, 30, '2026-07-02 12:00:00'),
    ((SELECT id FROM entreprise WHERE slug = 'clothing-test.com'), 4.5, 900, 70, 15,  5,  5,  5, '2026-07-02 12:00:00'),
    ((SELECT id FROM entreprise WHERE slug = 'courier-test.com'),  1.8, 300,  5,  5, 10, 10, 70, '2026-07-02 12:00:00');

-- ...plus une 2e ligne plus récente pour la même entreprise (historique d'un 2e run du DAG) :
-- l'API ne doit compter cette entreprise qu'une fois et utiliser ce TrustScore à jour.
INSERT INTO statistiques_avis
    (entreprise_id, trustscore, nb_avis_total, pct_excellent, pct_great, pct_average, pct_poor, pct_bad, date_scraping)
VALUES
    ((SELECT id FROM entreprise WHERE slug = 'clothing-test.com'), 4.6, 950, 72, 14,  5,  5,  4, '2026-07-03 12:00:00');
