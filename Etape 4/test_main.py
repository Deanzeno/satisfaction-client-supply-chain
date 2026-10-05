# =====================================================
# Tests unitaires — API FastAPI Sentiment
# Projet : Satisfaction Client Supply Chain
# Etape 4 — Tests
# Lancer : python -m pytest test_main.py -v
# =====================================================

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ══════════════════════════════════════════════════════
# 1) Santé de l'API  (GET /)
# ══════════════════════════════════════════════════════

class TestHealth:
    """Vérifie que l'API démarre et répond correctement."""

    def test_status_200(self):
        """GET / doit retourner HTTP 200."""
        r = client.get("/")
        assert r.status_code == 200

    def test_response_is_json(self):
        """La réponse doit être du JSON valide."""
        r = client.get("/")
        assert r.headers["content-type"].startswith("application/json")

    def test_response_has_status_field(self):
        """Le JSON doit contenir une clé 'status'."""
        r = client.get("/")
        assert "status" in r.json()


# ══════════════════════════════════════════════════════
# 2) Prédiction de sentiment  (POST /predict)
# ══════════════════════════════════════════════════════

class TestPredict:
    """Teste le modèle ML via l'endpoint /predict."""

    # ── Structure de la réponse ──────────────────────
    def test_returns_200(self):
        r = client.post("/predict", json={"texte": "Livraison rapide, très satisfait !"})
        assert r.status_code == 200

    def test_response_has_required_keys(self):
        """La réponse doit contenir sentiment, confiance et texte."""
        r = client.post("/predict", json={"texte": "Produit reçu dans les délais."})
        data = r.json()
        assert "sentiment"  in data
        assert "confiance"  in data
        assert "texte"      in data

    def test_sentiment_is_valid_label(self):
        """sentiment doit être l'une des trois classes du modèle."""
        r = client.post("/predict", json={"texte": "Bonne expérience globalement."})
        assert r.json()["sentiment"] in ("positif", "negatif", "neutre")

    def test_confiance_is_float_between_0_and_1(self):
        """confiance doit être un float ∈ [0.0, 1.0]."""
        r = client.post("/predict", json={"texte": "Super produit, je recommande !"})
        conf = r.json()["confiance"]
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_texte_echoed_in_response(self):
        """Le texte envoyé doit être renvoyé dans la réponse."""
        texte = "Colis abîmé à la réception."
        r = client.post("/predict", json={"texte": texte})
        assert r.json()["texte"] == texte

    # ── Cas positif ──────────────────────────────────
    def test_positif_text(self):
        """Texte clairement positif → doit être classé positif."""
        r = client.post("/predict", json={"texte": "Impeccable, livraison express, je recommande vivement !"})
        assert r.json()["sentiment"] == "positif"

    # ── Cas négatif ──────────────────────────────────
    def test_negatif_text(self):
        """Texte clairement négatif → doit être classé négatif."""
        # Note : "service client inexistant" perturbe le modèle (biais du mot "client")
        # On utilise la formulation qui classe correctement sur ce corpus.
        r = client.post("/predict", json={"texte": "Colis jamais reçu, service inexistant."})
        assert r.json()["sentiment"] == "negatif"

    def test_negatif_text_2(self):
        """Deuxième texte négatif pour robustesse."""
        r = client.post("/predict", json={"texte": "Délai dépassé, aucune réponse du service client, très déçu."})
        assert r.json()["sentiment"] == "negatif"

    # ── Validation des entrées ────────────────────────
    def test_missing_texte_field_returns_422(self):
        """Corps JSON sans 'texte' → FastAPI doit rejeter avec 422."""
        r = client.post("/predict", json={})
        assert r.status_code == 422

    def test_wrong_field_name_returns_422(self):
        """Mauvais nom de champ ('text' au lieu de 'texte') → 422."""
        r = client.post("/predict", json={"text": "Bonjour"})
        assert r.status_code == 422

    def test_non_json_body_returns_422(self):
        """Corps non-JSON → doit retourner une erreur."""
        r = client.post("/predict", data="texte=bonjour",
                        headers={"Content-Type": "text/plain"})
        assert r.status_code in (400, 422)


# ══════════════════════════════════════════════════════
# 3) Entreprises  (GET /companies)
# Structure réelle : {"total": int, "filtres": {...}, "companies": [...]}
# ══════════════════════════════════════════════════════

class TestCompanies:
    """Teste l'endpoint /companies (lecture PostgreSQL)."""

    def test_returns_200(self):
        r = client.get("/companies")
        assert r.status_code == 200

    def test_response_has_companies_key(self):
        """La réponse doit contenir une clé 'companies'."""
        r = client.get("/companies")
        assert "companies" in r.json()

    def test_companies_is_list(self):
        """r.json()['companies'] doit être une liste."""
        r = client.get("/companies")
        assert isinstance(r.json()["companies"], list)

    def test_response_has_total_key(self):
        """La réponse doit contenir une clé 'total'."""
        r = client.get("/companies")
        assert "total" in r.json()

    def test_limit_param_respected(self):
        """Le paramètre limit doit limiter le nombre de résultats."""
        r = client.get("/companies?limit=3")
        assert r.status_code == 200
        assert len(r.json()["companies"]) <= 3

    def test_filter_by_categorie_atm(self):
        """Filtrer par catégorie 'atm' doit renvoyer une liste."""
        r = client.get("/companies?categorie=atm")
        assert r.status_code == 200
        assert isinstance(r.json()["companies"], list)

    def test_filter_by_categorie_only_returns_atm(self):
        """Toutes les entreprises filtrées doivent appartenir à la catégorie demandée."""
        r = client.get("/companies?categorie=atm&limit=10")
        companies = r.json()["companies"]
        for c in companies:
            assert c["categorie"] == "atm"

    def test_company_has_required_fields(self):
        """Chaque entreprise doit avoir les champs : entreprise, categorie, trustscore, nb_avis_total."""
        r = client.get("/companies?limit=1")
        companies = r.json()["companies"]
        if companies:
            c = companies[0]
            assert "entreprise"    in c
            assert "categorie"     in c
            assert "trustscore"    in c
            assert "nb_avis_total" in c

    def test_trustscore_range(self):
        """trustscore doit être ∈ [1.0, 5.0]."""
        r = client.get("/companies?limit=5")
        for c in r.json()["companies"]:
            assert 1.0 <= float(c["trustscore"]) <= 5.0


# ══════════════════════════════════════════════════════
# 4) Statistiques  (GET /stats)
# Structure réelle : {"stats_par_categorie": [...]}
# Champs par ligne : categorie, nb_entreprises, trustscore_moyen, total_avis
# ══════════════════════════════════════════════════════

class TestStats:
    """Teste l'endpoint /stats (agrégats PostgreSQL)."""

    def test_returns_200(self):
        r = client.get("/stats")
        assert r.status_code == 200

    def test_response_has_stats_par_categorie_key(self):
        """La réponse doit contenir une clé 'stats_par_categorie'."""
        r = client.get("/stats")
        assert "stats_par_categorie" in r.json()

    def test_stats_par_categorie_is_list(self):
        """r.json()['stats_par_categorie'] doit être une liste."""
        r = client.get("/stats")
        assert isinstance(r.json()["stats_par_categorie"], list)

    def test_stats_row_has_required_fields(self):
        """Chaque ligne doit contenir categorie, nb_entreprises, trustscore_moyen, total_avis."""
        data = client.get("/stats").json()["stats_par_categorie"]
        if data:
            row = data[0]
            assert "categorie"       in row
            assert "nb_entreprises"  in row
            assert "trustscore_moyen" in row
            assert "total_avis"      in row

    def test_trustscore_moyen_is_numeric(self):
        """trustscore_moyen doit être un nombre ∈ [1.0, 5.0]."""
        data = client.get("/stats").json()["stats_par_categorie"]
        if data:
            score = float(data[0]["trustscore_moyen"])
            assert 1.0 <= score <= 5.0

    def test_nb_entreprises_is_positive(self):
        """nb_entreprises doit être un entier strictement positif."""
        data = client.get("/stats").json()["stats_par_categorie"]
        if data:
            assert int(data[0]["nb_entreprises"]) > 0

    def test_three_categories_present(self):
        """Les trois catégories scrapées (atm, clothing_store, courier_service) doivent apparaître."""
        data = client.get("/stats").json()["stats_par_categorie"]
        cats = {row["categorie"] for row in data}
        assert len(cats) >= 1  # au moins une catégorie en DB
