"""
Rapport de mesure de la dérive des données (étape 4)
Projet : Supply Chain - Satisfaction des clients
Auteurs : Zineddine HAMZAOUI & Thomas PALISSIER

Question : les avis récents ressemblent-ils encore aux avis anciens,
et le modèle de sentiment déployé dans l'API reste-t-il fiable dessus ?

On compare deux périodes des 592 avis ShowroomPrivé :
  - référence : avis publiés jusqu'en 2021 inclus
  - actuel    : avis publiés à partir de 2022
et on mesure :
  1. la dérive des données   (notes, réponses de l'entreprise, longueur, vocabulaire)
  2. la dérive des prédictions du modèle de l'API
  3. l'effet sur la performance (modèle entraîné sur l'ancien, testé sur le récent)

Usage (depuis la racine du projet) :
    python "Etape 4/derive/rapport_derive.py"
Produit : Etape 4/derive/rapport_derive.html et Etape 4/derive/resultats_derive.json
"""

import base64
import io
import json
import os
import re
from datetime import date

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, "..", ".."))
AVIS = os.path.join(RACINE, "Etape 3", "showroom_reviews.json")
MODELE = os.path.join(RACINE, "Etape 4", "sentiment_model.pkl")
VECTORISEUR = os.path.join(RACINE, "Etape 4", "vectorizer.pkl")
ANNEE_COUPURE = 2022          # référence < 2022 <= actuel
CLASSES = ["negatif", "neutre", "positif"]
COULEUR_REF, COULEUR_ACT = "#2563eb", "#ea580c"

# Mots très fréquents en anglais et en français : un indicateur simple de la langue
MOTS_EN = {"the", "and", "is", "was", "it", "my", "i", "to", "of", "not", "very", "with", "for", "you", "they"}
MOTS_FR = {"le", "la", "les", "et", "est", "je", "de", "pas", "très", "pour", "avec", "une", "un", "des", "mon"}


# ---------------------------------------------------------------- outils
def etoiles_vers_sentiment(n):
    return "negatif" if n <= 2 else ("neutre" if n == 3 else "positif")


def langue(texte):
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", texte.lower())
    en = sum(m in MOTS_EN for m in mots)
    fr = sum(m in MOTS_FR for m in mots)
    if en == fr == 0:
        return "inconnue"
    return "anglais" if en > fr else "français"


def psi(ref, act, categories):
    """Population Stability Index : < 0,1 faible, 0,1 à 0,25 modérée, > 0,25 forte."""
    p = np.array([(ref == c).mean() for c in categories]) + 1e-4
    q = np.array([(act == c).mean() for c in categories]) + 1e-4
    return float(np.sum((q - p) * np.log(q / p)))


def niveau_psi(v):
    return "faible" if v < 0.1 else ("modérée" if v < 0.25 else "forte")


def chi2_p(ref, act, categories):
    table = np.array([[(ref == c).sum() for c in categories], [(act == c).sum() for c in categories]])
    table = table[:, table.sum(axis=0) > 0]
    return float(chi2_contingency(table)[1])


def image(fig):
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(tampon.getvalue()).decode()


def barres_comparees(titre, categories, ref_pct, act_pct, unite="% des avis"):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(categories))
    ax.bar(x - 0.2, ref_pct, 0.4, label=f"Référence (< {ANNEE_COUPURE})", color=COULEUR_REF)
    ax.bar(x + 0.2, act_pct, 0.4, label=f"Actuel (≥ {ANNEE_COUPURE})", color=COULEUR_ACT)
    ax.set_xticks(x, categories)
    ax.set_ylabel(unite)
    ax.set_title(titre, fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    return image(fig)


# ---------------------------------------------------------------- données
df = pd.DataFrame(json.load(open(AVIS, encoding="utf-8")))
df["annee"] = pd.to_datetime(df["date_avis"]).dt.year
df["sentiment"] = df["nb_etoiles"].apply(etoiles_vers_sentiment)
df["texte"] = (df["titre"].fillna("") + " " + df["contenu"].fillna("")).str.lower()
df["longueur"] = df["texte"].str.split().str.len()
df["langue"] = df["texte"].apply(langue)
df["periode"] = np.where(df["annee"] < ANNEE_COUPURE, "reference", "actuel")
ref, act = df[df.periode == "reference"], df[df.periode == "actuel"]

modele = joblib.load(MODELE)
vectoriseur = joblib.load(VECTORISEUR)
df["prediction"] = modele.predict(vectoriseur.transform(df["texte"]))
ref, act = df[df.periode == "reference"], df[df.periode == "actuel"]

# Vocabulaire : part des mots absents du vocabulaire appris par le TF-IDF
vocab = set(vectoriseur.vocabulary_)
def part_hors_vocab(textes):
    mots = [m for t in textes for m in re.findall(r"\w+", t)]
    return float(np.mean([m not in vocab for m in mots]))

# ---------------------------------------------------------------- 1. dérive des données
etoiles = [1, 2, 3, 4, 5]
r = {}
# Les notes sont comparées via les 3 classes de sentiment : la période de référence ne contient
# aucun avis 5 étoiles (artefact du filtre par étoiles de la collecte), un PSI sur les 5 notes
# mesurerait surtout cet artefact.
r["notes"] = {"psi": psi(ref.sentiment, act.sentiment, CLASSES), "p_chi2": chi2_p(ref.sentiment, act.sentiment, CLASSES),
              "moyenne_ref": float(ref.nb_etoiles.mean()), "moyenne_act": float(act.nb_etoiles.mean()),
              "positif_ref": float((ref.sentiment == "positif").mean()), "positif_act": float((act.sentiment == "positif").mean()),
              "cinq_etoiles_ref": int((ref.nb_etoiles == 5).sum()), "cinq_etoiles_act": int((act.nb_etoiles == 5).sum())}
r["reponse"] = {"taux_ref": float(ref.entreprise_repond.mean()), "taux_act": float(act.entreprise_repond.mean()),
                "p_chi2": chi2_p(ref.entreprise_repond, act.entreprise_repond, [True, False])}
ks = ks_2samp(ref.longueur, act.longueur)
r["longueur"] = {"mediane_ref": float(ref.longueur.median()), "mediane_act": float(act.longueur.median()),
                 "moyenne_ref": float(ref.longueur.mean()), "moyenne_act": float(act.longueur.mean()), "p_ks": float(ks.pvalue)}
langues = ["français", "anglais", "inconnue"]  # inconnue = texte trop court pour trancher
r["langue"] = {"psi": psi(ref.langue, act.langue, langues), "p_chi2": chi2_p(ref.langue, act.langue, langues),
               "anglais_ref": float((ref.langue == "anglais").mean()), "anglais_act": float((act.langue == "anglais").mean())}
r["vocabulaire"] = {"hors_vocab_ref": part_hors_vocab(ref.texte), "hors_vocab_act": part_hors_vocab(act.texte)}

# ---------------------------------------------------------------- 2. dérive des prédictions (modèle de l'API)
r["predictions"] = {"psi": psi(ref.prediction, act.prediction, CLASSES), "p_chi2": chi2_p(ref.prediction, act.prediction, CLASSES),
                    "positif_ref": float((ref.prediction == "positif").mean()), "positif_act": float((act.prediction == "positif").mean())}

# ---------------------------------------------------------------- 3. effet sur la performance
# Scénario de production : on entraîne sur l'ancien, on prédit le récent (même méthode que l'étape 3)
v_old = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
m_old = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
m_old.fit(v_old.fit_transform(ref.texte), ref.sentiment)
pred_act = m_old.predict(v_old.transform(act.texte))
pred_ref_cv = None
from sklearn.model_selection import cross_val_predict
pred_ref_cv = cross_val_predict(LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced"),
                                TfidfVectorizer(max_features=1000, ngram_range=(1, 2)).fit_transform(ref.texte),
                                ref.sentiment, cv=5)
r["performance"] = {
    "accuracy_ref_validation_croisee": float(accuracy_score(ref.sentiment, pred_ref_cv)),
    "accuracy_actuel": float(accuracy_score(act.sentiment, pred_act)),
    "f1_macro_ref": float(f1_score(ref.sentiment, pred_ref_cv, average="macro", zero_division=0)),
    "f1_macro_actuel": float(f1_score(act.sentiment, pred_act, average="macro", zero_division=0)),
    "reference_toujours_positif_ref": float((ref.sentiment == "positif").mean()),
    "reference_toujours_positif_actuel": float((act.sentiment == "positif").mean()),
}
perf_ = r["performance"]
perf_["avance_ref_points"] = 100 * (perf_["accuracy_ref_validation_croisee"] - perf_["reference_toujours_positif_ref"])
perf_["avance_act_points"] = 100 * (perf_["accuracy_actuel"] - perf_["reference_toujours_positif_actuel"])
r["effectifs"] = {"reference": int(len(ref)), "actuel": int(len(act)), "total": int(len(df))}

# ---------------------------------------------------------------- graphiques
pct = lambda s, cats: [100 * (s == c).mean() for c in cats]
g_notes = barres_comparees("Répartition des notes", [f"{e}★" for e in etoiles], pct(ref.nb_etoiles, etoiles), pct(act.nb_etoiles, etoiles))
g_pred = barres_comparees("Sentiment prédit par le modèle de l'API", CLASSES, pct(ref.prediction, CLASSES), pct(act.prediction, CLASSES))
g_langue = barres_comparees("Langue des avis", langues, pct(ref.langue, langues), pct(act.langue, langues))
par_an = df.groupby("annee").agg(n=("nb_etoiles", "size"), note=("nb_etoiles", "mean"), rep=("entreprise_repond", "mean"))
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.plot(par_an.index, par_an.note, marker="o", color="#0f172a")
ax.axvline(ANNEE_COUPURE - 0.5, color="#94a3b8", ls="--", lw=1)
ax.set_ylim(0.8, 5.2); ax.set_ylabel("note moyenne (★)")
ax.set_title("Note moyenne par année (pointillé : coupure)", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False)
g_annee = image(fig)

# ---------------------------------------------------------------- verdict
def oui(p):
    return p < 0.05
lignes = [
    ("Notes (classes de sentiment)", f"avis positifs {100*r['notes']['positif_ref']:.0f} % → {100*r['notes']['positif_act']:.0f} % (moyenne {r['notes']['moyenne_ref']:.1f}★ → {r['notes']['moyenne_act']:.1f}★)",
     f"PSI {r['notes']['psi']:.2f} ({niveau_psi(r['notes']['psi'])}), p = {r['notes']['p_chi2']:.3f}", oui(r['notes']['p_chi2'])),
    ("Réponses de l'entreprise", f"{100*r['reponse']['taux_ref']:.0f} % → {100*r['reponse']['taux_act']:.0f} %",
     f"p = {r['reponse']['p_chi2']:.1e}", oui(r['reponse']['p_chi2'])),
    ("Longueur des avis", f"moyenne {r['longueur']['moyenne_ref']:.0f} → {r['longueur']['moyenne_act']:.0f} mots (médiane {r['longueur']['mediane_ref']:.0f} → {r['longueur']['mediane_act']:.0f})",
     f"test KS, p = {r['longueur']['p_ks']:.3f}", oui(r['longueur']['p_ks'])),
    ("Langue", f"anglais {100*r['langue']['anglais_ref']:.0f} % → {100*r['langue']['anglais_act']:.0f} %",
     f"PSI {r['langue']['psi']:.2f} ({niveau_psi(r['langue']['psi'])}), p = {r['langue']['p_chi2']:.3f}", oui(r['langue']['p_chi2'])),
    ("Mots hors vocabulaire du modèle", f"{100*r['vocabulaire']['hors_vocab_ref']:.0f} % → {100*r['vocabulaire']['hors_vocab_act']:.0f} %",
     "part des mots que le TF-IDF ne connaît pas", r['vocabulaire']['hors_vocab_act'] - r['vocabulaire']['hors_vocab_ref'] > 0.05),
    ("Sentiment prédit (API)", f"positif {100*r['predictions']['positif_ref']:.0f} % → {100*r['predictions']['positif_act']:.0f} %",
     f"PSI {r['predictions']['psi']:.2f} ({niveau_psi(r['predictions']['psi'])}), p = {r['predictions']['p_chi2']:.3f}", oui(r['predictions']['p_chi2'])),
]
nb_derives = sum(1 for l in lignes if l[3])
perf = r["performance"]

lignes_html = "\n".join(
    f"<tr><td>{n}</td><td>{v}</td><td>{t}</td><td class='{'oui' if d else 'non'}'>{'Oui' if d else 'Non'}</td></tr>"
    for n, v, t, d in lignes)

html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport de dérive des données</title>
<style>
body{{font-family:Inter,Arial,sans-serif;color:#0f172a;max-width:920px;margin:40px auto;padding:0 20px;line-height:1.5}}
h1{{font-size:28px;margin-bottom:4px}} h2{{font-size:20px;margin-top:36px;border-bottom:2px solid #e2e8f0;padding-bottom:6px}}
.sous{{color:#64748b}} table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;padding:8px;border-bottom:1px solid #e2e8f0}}
th{{background:#f1f5f9}} .oui{{color:#b45309;font-weight:700}} .non{{color:#15803d;font-weight:700}}
.cartes{{display:flex;gap:16px;flex-wrap:wrap}} .carte{{flex:1;min-width:180px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px}}
.carte b{{font-size:26px;display:block}} img{{max-width:100%}} .grille{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.note{{background:#fff7ed;border-left:4px solid #ea580c;padding:10px 14px}}
</style></head><body>
<h1>Rapport de dérive des données</h1>
<p class="sous">Supply Chain – Satisfaction des clients · Zineddine HAMZAOUI &amp; Thomas PALISSIER · généré le {date.today().isoformat()} par <code>Etape 4/derive/rapport_derive.py</code></p>

<p><b>Conclusion : les données ont dérivé sur {nb_derives} indicateurs sur {len(lignes)}.</b>
Entraîné uniquement sur les avis anciens, le modèle obtient {100*perf['accuracy_actuel']:.1f} % d'accuracy sur les avis récents
({100*perf['accuracy_ref_validation_croisee']:.1f} % sur l'ancienne période), mais son avance sur la référence « toujours positif »
{'tombe' if perf['avance_act_points'] < perf['avance_ref_points'] else 'passe'} de {perf['avance_ref_points']:+.0f} à {perf['avance_act_points']:+.0f} points :
{'la dérive réduit la valeur ajoutée du modèle, il faut le réentraîner régulièrement sur des avis récents.' if perf['avance_act_points'] < perf['avance_ref_points'] else 'le modèle résiste pour l’instant à la dérive, mais il faut continuer à la surveiller.'}</p>

<div class="cartes">
<div class="carte"><span class="sous">Avis de référence (avant {ANNEE_COUPURE})</span><b>{r['effectifs']['reference']}</b></div>
<div class="carte"><span class="sous">Avis actuels ({ANNEE_COUPURE} et après)</span><b>{r['effectifs']['actuel']}</b></div>
<div class="carte"><span class="sous">Indicateurs en dérive</span><b>{nb_derives} / {len(lignes)}</b></div>
</div>

<h2>1. Méthode</h2>
<p>Les 592 avis ShowroomPrivé (2013 à 2026) sont coupés en deux périodes : une période de <b>référence</b> (avant {ANNEE_COUPURE}) et une période <b>actuelle</b> ({ANNEE_COUPURE} et après).
Une variable « dérive » quand sa distribution change de façon significative entre les deux : test du χ² pour les catégories, test de Kolmogorov-Smirnov pour la longueur
(seuil p &lt; 0,05), et PSI (Population Stability Index : &lt; 0,1 faible, 0,1 à 0,25 modérée, &gt; 0,25 forte). La langue est estimée par les mots outils les plus fréquents ; « inconnue » = avis trop courts pour trancher.</p>

<h2>2. Résultats par indicateur</h2>
<table><tr><th>Indicateur</th><th>Référence → actuel</th><th>Mesure</th><th>Dérive ?</th></tr>
{lignes_html}
</table>
<div class="grille">
<img src="data:image/png;base64,{g_annee}" alt="Note moyenne par année">
<img src="data:image/png;base64,{g_notes}" alt="Répartition des notes par période">
<img src="data:image/png;base64,{g_langue}" alt="Langue des avis par période">
<img src="data:image/png;base64,{g_pred}" alt="Sentiment prédit par période">
</div>

<h2>3. Effet sur le modèle</h2>
<p>Scénario de production : le modèle n'a appris que sur les avis anciens, puis il doit classer les avis récents (même méthode qu'à l'étape 3 : TF-IDF + régression logistique, classes pondérées).</p>
<table><tr><th>Mesure</th><th>Période de référence<br>(validation croisée 5 plis)</th><th>Période actuelle</th></tr>
<tr><td>Accuracy</td><td>{100*perf['accuracy_ref_validation_croisee']:.1f} %</td><td>{100*perf['accuracy_actuel']:.1f} %</td></tr>
<tr><td>F1 macro (3 classes)</td><td>{perf['f1_macro_ref']:.2f}</td><td>{perf['f1_macro_actuel']:.2f}</td></tr>
<tr><td>Référence « toujours positif »</td><td>{100*perf['reference_toujours_positif_ref']:.1f} %</td><td>{100*perf['reference_toujours_positif_actuel']:.1f} %</td></tr>
<tr><td><b>Avance du modèle sur cette référence</b></td><td><b>{perf['avance_ref_points']:+.1f} points</b></td><td><b>{perf['avance_act_points']:+.1f} points</b></td></tr>
</table>
<p>Lire l'accuracy seule serait trompeur : elle monte parce que les avis récents sont plus souvent positifs, donc plus faciles à « deviner ».
Ce qui compte est l'avance sur la référence, c'est-à-dire ce que le modèle apporte réellement.</p>

<h2>4. Interprétation</h2>
<ul>
<li><b>Le comportement de l'entreprise a changé</b> : ShowroomPrivé ne répondait à aucun avis avant 2021 et répond aujourd'hui à presque tous. C'est la dérive la plus nette.</li>
<li><b>Les notes ont changé</b> : la part d'avis positifs passe de {100*r['notes']['positif_ref']:.0f} % à {100*r['notes']['positif_act']:.0f} %, avec un creux en 2018–2021 (voir le graphique par année).</li>
<li><b>Le texte a changé</b> : les avis récents sont plus souvent en français ({100*(1-r['langue']['anglais_act']):.0f} % non anglais contre {100*(1-r['langue']['anglais_ref']):.0f} %) et leur longueur évolue ;
la part de mots inconnus du vocabulaire TF-IDF passe de {100*r['vocabulaire']['hors_vocab_ref']:.0f} % à {100*r['vocabulaire']['hors_vocab_act']:.0f} %.</li>
<li><b>Les prédictions suivent</b> : le modèle de l'API prédit « positif » pour {100*r['predictions']['positif_ref']:.0f} % des avis anciens et {100*r['predictions']['positif_act']:.0f} % des récents, ce qui est cohérent avec l'évolution réelle des notes.</li>
</ul>

<h2>5. Actions recommandées</h2>
<ul>
<li>Réentraîner le modèle sur une fenêtre glissante d'avis récents, par exemple chaque trimestre, et versionner le .pkl.</li>
<li>Relancer ce rapport à chaque nouvelle collecte d'avis, par exemple comme une tâche Airflow, et alerter si le PSI dépasse 0,25.</li>
<li>Suivre les entrées réelles de l'API : les logs de /predict permettront de mesurer la dérive sur ce que les utilisateurs envoient vraiment.</li>
</ul>
<p class="note"><b>Limite.</b> Les avis ont été collectés avec un filtre par nombre d'étoiles (10 pages par note, les plus récentes d'abord) : la période de référence
ne contient ainsi aucun avis 5★ ({r['notes']['cinq_etoiles_ref']} contre {r['notes']['cinq_etoiles_act']} dans la période actuelle), ce qui exagère l'écart entre les périodes.
C'est pourquoi les notes sont comparées par classe de sentiment, et les pourcentages sont à lire comme des ordres de grandeur. Les données entreprises ne sont pas analysées ici :
tant que Trustpilot bloque le scraping, toutes les exécutions rechargent le même CSV, donc il n'y a pas encore de dérive à mesurer.</p>
</body></html>"""

with open(os.path.join(ICI, "rapport_derive.html"), "w", encoding="utf-8") as f:
    f.write(html)
with open(os.path.join(ICI, "resultats_derive.json"), "w", encoding="utf-8") as f:
    json.dump(r, f, ensure_ascii=False, indent=2)

print(f"Rapport écrit : {os.path.join(ICI, 'rapport_derive.html')}")
print(f"Indicateurs en dérive : {nb_derives}/{len(lignes)}")
for n, v, t, d in lignes:
    print(f"  - {n:32s} {v:28s} {t:40s} dérive={'oui' if d else 'non'}")
print(f"Performance : {100*perf['accuracy_ref_validation_croisee']:.1f} % (référence, CV) -> {100*perf['accuracy_actuel']:.1f} % (actuel)")
print(f"Avance sur 'toujours positif' : {perf['avance_ref_points']:+.1f} -> {perf['avance_act_points']:+.1f} points")
