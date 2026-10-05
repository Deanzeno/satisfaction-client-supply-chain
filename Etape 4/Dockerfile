# Image Python officielle légère
FROM python:3.11-slim

# Répertoire de travail dans le conteneur
WORKDIR /app

# Copier les dépendances en premier (optimisation cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tous les fichiers de l'application
COPY . .

# Exposer le port 8000
EXPOSE 8000

# Lancer l'API avec uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
