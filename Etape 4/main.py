"""
API FastAPI - Projet Supply Chain Satisfaction des clients
Etape 4 - Mise en production

Endpoints :
    GET  /            → vérifier que l'API tourne
    POST /predict     → prédire le sentiment d'un avis client
    GET  /companies   → récupérer les entreprises depuis PostgreSQL
    GET  /stats       → statistiques globales
"""

import os
import joblib
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# ── Initialisation de l'API ────────────────────────────────────────────────────
app = FastAPI(
    title="API Satisfaction Client - Supply Chain",
    description="API pour analyser le sentiment des avis clients Trustpilot",
    version="1.0.0"
)

# Autoriser les requêtes depuis le navigateur (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Chargement du modèle ML ───────────────────────────────────────────────────
# On charge le modèle et le vectorizer sauvegardés à l'étape 3
try:
    modele     = joblib.load("sentiment_model.pkl")
    vectorizer = joblib.load("vectorizer.pkl")
    print("✅ Modèle ML chargé avec succès")
except FileNotFoundError:
    print("❌ Fichiers .pkl non trouvés — placez sentiment_model.pkl et vectorizer.pkl ici")
    modele     = None
    vectorizer = None


# ── Connexion PostgreSQL ──────────────────────────────────────────────────────
def get_db_connection():
    """Crée une connexion à la base PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "satisfaction_client"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )


# ── Modèles de données (Pydantic) ─────────────────────────────────────────────
class PredictRequest(BaseModel):
    texte: str  # Le texte de l'avis à analyser

class PredictResponse(BaseModel):
    texte: str
    sentiment: str   # positif / neutre / negatif
    confiance: float # probabilité de la prédiction (entre 0 et 1)


# ── ENDPOINT 1 : Health check ─────────────────────────────────────────────────
@app.get("/", summary="Vérifier que l'API tourne")
def root():
    """Endpoint de vérification — retourne le statut de l'API."""
    return {
        "status": "ok",
        "message": "API Satisfaction Client opérationnelle",
        "version": "1.0.0",
        "modele_charge": modele is not None,
        "endpoints": ["/predict", "/companies", "/stats"]
    }


# ── ENDPOINT 2 : Prédiction du sentiment ─────────────────────────────────────
@app.post("/predict", response_model=PredictResponse, summary="Prédire le sentiment d'un avis")
def predict_sentiment(request: PredictRequest):
    """
    Analyse le sentiment d'un texte d'avis client.

    - **texte** : le texte de l'avis à analyser

    Retourne :
    - **sentiment** : positif / neutre / negatif
    - **confiance** : probabilité de la prédiction (entre 0 et 1)
    """
    if modele is None or vectorizer is None:
        raise HTTPException(
            status_code=503,
            detail="Modèle ML non disponible. Vérifiez que les fichiers .pkl sont présents."
        )

    if not request.texte.strip():
        raise HTTPException(
            status_code=400,
            detail="Le texte de l'avis ne peut pas être vide."
        )

    # Transformation du texte avec TF-IDF
    texte_vectorise = vectorizer.transform([request.texte.lower()])

    # Prédiction du sentiment
    sentiment = modele.predict(texte_vectorise)[0]

    # Probabilité de la prédiction (confiance)
    probas     = modele.predict_proba(texte_vectorise)[0]
    confiance  = round(float(max(probas)), 2)

    return PredictResponse(
        texte=request.texte,
        sentiment=sentiment,
        confiance=confiance
    )


# ── ENDPOINT 3 : Liste des entreprises ───────────────────────────────────────
@app.get("/companies", summary="Récupérer les entreprises depuis PostgreSQL")
def get_companies(
    categorie: str = None,
    limit: int = 20,
    min_score: float = None
):
    """
    Récupère les entreprises stockées dans PostgreSQL.

    Paramètres optionnels :
    - **categorie** : filtrer par catégorie (atm, clothing_store, courier_service)
    - **limit** : nombre maximum de résultats (défaut : 20)
    - **min_score** : trustscore minimum (ex: 3.5)
    """
    try:
        conn = get_db_connection()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Construction de la requête SQL avec filtres optionnels
        query  = """
            SELECT
                e.nom          AS entreprise,
                c.nom          AS categorie,
                s.trustscore,
                s.nb_avis_total,
                s.pct_excellent,
                s.pct_bad
            FROM entreprise e
            JOIN categorie c           ON e.categorie_id     = c.id
            JOIN statistiques_avis s   ON s.entreprise_id    = e.id
            WHERE 1=1
        """
        params = []

        if categorie:
            query += " AND c.nom = %s"
            params.append(categorie)

        if min_score is not None:
            query += " AND s.trustscore >= %s"
            params.append(min_score)

        query += " ORDER BY s.trustscore DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        resultats = cur.fetchall()

        cur.close()
        conn.close()

        return {
            "total": len(resultats),
            "filtres": {
                "categorie": categorie,
                "min_score": min_score,
                "limit": limit
            },
            "companies": [dict(r) for r in resultats]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur base de données : {str(e)}"
        )


# ── ENDPOINT 4 : Statistiques globales ───────────────────────────────────────
@app.get("/stats", summary="Statistiques globales par catégorie")
def get_stats():
    """
    Retourne les statistiques globales de toutes les entreprises
    groupées par catégorie.
    """
    try:
        conn = get_db_connection()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                c.nom                            AS categorie,
                COUNT(e.id)                      AS nb_entreprises,
                ROUND(AVG(s.trustscore)::numeric, 2) AS trustscore_moyen,
                SUM(s.nb_avis_total)             AS total_avis
            FROM categorie c
            JOIN entreprise e        ON e.categorie_id   = c.id
            JOIN statistiques_avis s ON s.entreprise_id  = e.id
            GROUP BY c.nom
            ORDER BY trustscore_moyen DESC
        """)

        stats = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "stats_par_categorie": [dict(s) for s in stats]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur base de données : {str(e)}"
        )
