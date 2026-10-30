"""Génère des clients et des commandes fictifs pour NovaTech Informatique.

Sorties :
  data/commandes/clients.json
  data/commandes/commandes.json

Les données sont reproductibles (graine aléatoire fixe) et cohérentes avec :
  - le catalogue (data/catalogue/produits.json) ;
  - la politique de livraison (data/documents/livraison.md) : tarifs, seuils de gratuité, délais ;
  - la date de référence du projet (DATE_REF).
Toutes les données personnelles sont fictives (e-mails en @example.com).
"""

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "catalogue" / "produits.json"
OUT_DIR = ROOT / "data" / "commandes"

SEED = 42
DATE_REF = date(2026, 10, 30)          # "aujourd'hui" pour le jeu de données (il est midi :
                                       # les expéditions de 16h du jour n'ont pas encore eu lieu)
DEBUT = date(2026, 8, 25)              # première commande
NB_CLIENTS = 120
NB_COMMANDES = 200
FERIES = {date(2026, 11, 1), date(2026, 11, 11), date(2026, 8, 15)}

PRENOMS = ["Camille", "Léa", "Manon", "Chloé", "Emma", "Inès", "Sarah", "Jade", "Louise", "Lina", "Zoé", "Clara",
           "Nina", "Alice", "Ambre", "Yasmine", "Fatou", "Aïcha", "Mélanie", "Sophie", "Lucas", "Hugo", "Louis",
           "Nathan", "Gabriel", "Arthur", "Jules", "Adam", "Mohamed", "Rayan", "Théo", "Noah", "Ethan", "Paul",
           "Maxime", "Thomas", "Kevin", "Antoine", "Julien", "Moussa", "Karim", "Yanis", "Romain", "Nicolas",
           "Olivier", "David", "Samuel", "Bastien", "Clément", "Mathis"]
NOMS = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
        "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
        "Morel", "Girard", "André", "Mercier", "Dupont", "Lambert", "Bonnet", "François", "Martinez", "Legrand",
        "Garnier", "Faure", "Rousseau", "Blanc", "Guerin", "Muller", "Henry", "Roussel", "Nicolas", "Perrin",
        "Diallo", "Traoré", "Benali", "Nguyen", "Mbemba", "Kouassi", "Haddad", "Lopez", "Fontaine", "Chevalier"]
VILLES = [  # (ville, code postal, pays)
    ("Lyon", "69003", "France"), ("Lyon", "69007", "France"), ("Villeurbanne", "69100", "France"),
    ("Paris", "75011", "France"), ("Paris", "75015", "France"), ("Marseille", "13008", "France"),
    ("Toulouse", "31000", "France"), ("Nantes", "44000", "France"), ("Lille", "59000", "France"),
    ("Bordeaux", "33000", "France"), ("Strasbourg", "67000", "France"), ("Montpellier", "34000", "France"),
    ("Rennes", "35000", "France"), ("Grenoble", "38000", "France"), ("Nice", "06000", "France"),
    ("Dijon", "21000", "France"), ("Saint-Étienne", "42000", "France"), ("Clermont-Ferrand", "63000", "France"),
    ("Ajaccio", "20000", "France"), ("Bruxelles", "1000", "Belgique"), ("Liège", "4000", "Belgique"),
    ("Luxembourg", "L-1009", "Luxembourg"),
]

# Modes de livraison (cf. livraison.md)
MODES_FR = {
    "retrait_showroom": {"libelle": "Retrait au showroom de Lyon 7e", "tarif": 0.0, "gratuit_des": 0, "transporteur": "NovaTech", "delai": (0, 0)},
    "point_relais": {"libelle": "Point relais", "tarif": 3.90, "gratuit_des": 49, "transporteur": "Mondial Relay", "delai": (3, 5)},
    "domicile_standard": {"libelle": "Domicile standard", "tarif": 5.90, "gratuit_des": 99, "transporteur": "Colissimo", "delai": (2, 4)},
    "express_24h": {"libelle": "Express 24h", "tarif": 12.90, "gratuit_des": None, "transporteur": "Chronopost", "delai": (1, 1)},
    "rendez_vous": {"libelle": "Livraison sur rendez-vous", "tarif": 19.90, "gratuit_des": 1500, "transporteur": "NovaLog", "delai": (3, 6)},
}
MODES_BL = {
    "domicile_standard": {"libelle": "Domicile standard", "tarif": 9.90, "gratuit_des": 150, "transporteur": "bpost", "delai": (3, 6)},
    "point_relais": {"libelle": "Point relais", "tarif": 5.90, "gratuit_des": 99, "transporteur": "Mondial Relay", "delai": (4, 6)},
}
PAIEMENTS = [("carte_bancaire", 55), ("paypal", 18), ("apple_pay", 7), ("google_pay", 4), ("paiement_3x_4x", 10), ("virement", 6)]

STATUTS_LIBELLES = {
    "en_attente_paiement": "En attente de paiement (virement)",
    "en_preparation": "En préparation",
    "en_assemblage": "En assemblage en atelier",
    "expediee": "Expédiée",
    "en_cours_de_livraison": "En cours de livraison",
    "disponible_retrait": "Disponible au retrait",
    "livree": "Livrée",
    "annulee": "Annulée",
    "retour_en_cours": "Retour en cours",
    "retour_rembourse": "Retour remboursé",
}

rnd = random.Random(SEED)


def jours_ouvres(d, n):
    """Ajoute n jours ouvrés (lun-ven hors fériés) à la date d."""
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in FERIES:
            n -= 1
    return d


def prochain_jour_ouvre(d):
    while d.weekday() >= 5 or d in FERIES:
        d += timedelta(days=1)
    return d


def choix_pondere(options):
    total = sum(w for _, w in options)
    r = rnd.uniform(0, total)
    acc = 0
    for v, w in options:
        acc += w
        if r <= acc:
            return v
    return options[-1][0]


def sans_accents(s):
    table = str.maketrans("éèêëàâäîïôöùûüçÉÈÊÀÂÎÔÙÛÇ", "eeeeaaaiioouuucEEEAAIOUUC")
    return s.translate(table).lower().replace(" ", "").replace("'", "")


def generer_clients():
    clients, emails = [], set()
    for i in range(1, NB_CLIENTS + 1):
        prenom, nom = rnd.choice(PRENOMS), rnd.choice(NOMS)
        email = f"{sans_accents(prenom)}.{sans_accents(nom)}@example.com"
        k = 2
        while email in emails:
            email = f"{sans_accents(prenom)}.{sans_accents(nom)}{k}@example.com"
            k += 1
        emails.add(email)
        ville, cp, pays = rnd.choices(VILLES, weights=[8, 6, 4, 9, 7, 6, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 1, 3, 2, 2])[0]
        clients.append({
            "client_id": f"CLI-{i:04d}",
            "prenom": prenom,
            "nom": nom,
            "email": email,
            "telephone": f"06 00 00 {rnd.randint(10, 99)} {rnd.randint(10, 99)}",
            "ville": ville,
            "code_postal": cp,
            "pays": pays,
            "date_inscription": (date(2023, 1, 1) + timedelta(days=rnd.randint(0, 1330))).isoformat(),
            "etudiant_verifie": rnd.random() < 0.12,
            "points_fidelite": 0,
        })
    return clients


def panier(produits_par_cat):
    """Compose un panier réaliste à partir de profils d'achat."""
    profil = choix_pondere([("portable", 26), ("fixe", 9), ("ecran", 14), ("upgrade", 14), ("config_pc", 8),
                            ("peripheriques", 17), ("stockage", 8), ("reseau", 4)])
    lignes = []

    def pick(cat, filtre=None):
        candidats = [p for p in produits_par_cat[cat] if (filtre is None or filtre(p))]
        return rnd.choice(candidats)

    if profil == "portable":
        lignes.append((pick("PC portable"), 1))
        if rnd.random() < 0.45:
            lignes.append((pick("Périphérique", lambda p: p["sous_categorie"] in ("Souris", "Casque")), 1))
    elif profil == "fixe":
        lignes.append((pick("PC fixe"), 1))
        if rnd.random() < 0.6:
            lignes.append((pick("Écran"), 1))
        if rnd.random() < 0.5:
            lignes.append((pick("Périphérique", lambda p: p["sous_categorie"] in ("Clavier", "Souris")), 1))
    elif profil == "ecran":
        lignes.append((pick("Écran"), 2 if rnd.random() < 0.15 else 1))
    elif profil == "upgrade":
        cat = rnd.choice(["Mémoire RAM", "Carte graphique", "Stockage", "Processeur"])
        lignes.append((pick(cat), 1))
        if cat == "Carte graphique" and rnd.random() < 0.35:
            lignes.append((pick("Alimentation"), 1))
    elif profil == "config_pc":
        # Configuration cohérente : AM5 ou LGA1700 DDR5
        if rnd.random() < 0.5:
            cpu = pick("Processeur", lambda p: p["compatibilite"]["socket"] == "AM5")
            mob = pick("Carte mère", lambda p: p["compatibilite"]["socket"] == "AM5" and p["compatibilite"]["format"] != "mini-ITX")
        else:
            cpu = pick("Processeur", lambda p: p["compatibilite"]["socket"] == "LGA1700")
            mob = pick("Carte mère", lambda p: p["compatibilite"]["socket"] == "LGA1700" and p["compatibilite"]["memoire"] == "DDR5")
        ram = pick("Mémoire RAM", lambda p: p["compatibilite"] == {"type": "DDR5", "format": "DIMM"})
        gpu = pick("Carte graphique", lambda p: p["compatibilite"]["alim_min_w"] <= 750)
        psu = pick("Alimentation", lambda p: p["compatibilite"]["format"] == "ATX"
                   and p["compatibilite"]["puissance_w"] >= gpu["compatibilite"]["alim_min_w"])
        case = pick("Boîtier", lambda p: mob["compatibilite"]["format"] in p["compatibilite"]["cartes_meres"]
                    and p["compatibilite"]["gpu_max_mm"] >= gpu["compatibilite"]["longueur_mm"]
                    and p["compatibilite"]["alim"] == "ATX")
        sto = pick("Stockage", lambda p: p["compatibilite"].get("format") == "M.2 2280" if p.get("compatibilite") else False)
        lignes += [(cpu, 1), (mob, 1), (ram, 1), (gpu, 1), (psu, 1), (case, 1), (sto, 1)]
        if not cpu["compatibilite"]["ventirad_inclus"]:
            lignes.append((pick("Refroidissement", lambda p: p["sku"] in ("NT-COO-001", "NT-COO-003", "NT-COO-004")), 1))
    elif profil == "peripheriques":
        for _ in range(rnd.choice([1, 1, 2, 3])):
            lignes.append((pick("Périphérique"), 1))
    elif profil == "stockage":
        lignes.append((pick("Stockage"), rnd.choice([1, 1, 2])))
    elif profil == "reseau":
        lignes.append((pick("Réseau"), 1))

    # fusion des doublons
    fusion = {}
    for prod, q in lignes:
        if prod["sku"] in fusion:
            fusion[prod["sku"]][1] += q
        else:
            fusion[prod["sku"]] = [prod, q]
    return profil, list(fusion.values())


def choisir_mode(client, lignes, sous_total):
    pays = client["pays"]
    volumineux = any(p["categorie"] == "PC fixe" or (p["categorie"] == "Écran" and p["caracteristiques"]["taille"].startswith(("34", "49")))
                     for p, _ in lignes)
    poids = sum((p.get("poids_kg") or 1.0) * q for p, q in lignes)
    if pays != "France":
        options = [("domicile_standard", 70)] + ([] if volumineux else [("point_relais", 30)])
        return choix_pondere(options)
    if poids > 30:
        return "rendez_vous"
    options = [("domicile_standard", 45), ("express_24h", 12)]
    if not volumineux:
        options.append(("point_relais", 25))
    if client["ville"] in ("Lyon", "Villeurbanne"):
        options.append(("retrait_showroom", 30))
    if client["code_postal"].startswith("20"):  # Corse : standard uniquement
        options = [("domicile_standard", 1)]
    return choix_pondere(options)


def frais(mode, pays, sous_total):
    m = (MODES_FR if pays == "France" else MODES_BL)[mode]
    if m["gratuit_des"] is not None and sous_total >= m["gratuit_des"]:
        return 0.0
    return m["tarif"]


def numero_suivi(transporteur):
    if transporteur == "Colissimo":
        return f"6A{rnd.randint(10**10, 10**11 - 1)}"
    if transporteur == "Chronopost":
        return f"XY{rnd.randint(10**8, 10**9 - 1)}FR"
    if transporteur == "Mondial Relay":
        return f"{rnd.randint(10**7, 10**8 - 1)}"
    if transporteur == "bpost":
        return f"3232{rnd.randint(10**11, 10**12 - 1)}"
    if transporteur == "NovaLog":
        return f"NL-{rnd.randint(100000, 999999)}"
    return None


def generer_commandes(clients, produits):
    par_cat = {}
    for p in produits:
        par_cat.setdefault(p["categorie"], []).append(p)
    # Produits achetables : en stock aujourd'hui OU commandés avant la rupture (on les garde tous)
    commandes = []
    jours = (DATE_REF - DEBUT).days
    # dates triées : plus de commandes récentes, et quelques-unes "aujourd'hui"
    nb_recentes = 34  # commandes des 7 derniers jours, pour avoir des statuts "en cours"
    anciennes = [DEBUT + timedelta(days=int(rnd.triangular(0, jours - 7, (jours - 7) * 0.8)))
                 for _ in range(NB_COMMANDES - nb_recentes)]
    recentes = [DATE_REF - timedelta(days=rnd.randint(0, 6)) for _ in range(nb_recentes)]
    dates = sorted(anciennes + recentes)
    clients_actifs = rnd.sample(clients, 95)
    fideles = rnd.sample(clients_actifs, 25)

    for i, d in enumerate(dates):
        num = f"CMD-{20001 + i}"
        client = rnd.choice(fideles) if rnd.random() < 0.35 else rnd.choice(clients_actifs)
        profil, lignes = panier(par_cat)
        sous_total = round(sum(p["prix_ttc"] * q for p, q in lignes), 2)
        service_montage = profil == "config_pc" and rnd.random() < 0.7
        if service_montage:
            sous_total = round(sous_total + 49, 2)
        mode = choisir_mode(client, lignes, sous_total)
        m = (MODES_FR if client["pays"] == "France" else MODES_BL)[mode]
        fdp = frais(mode, client["pays"], sous_total)
        paiement = choix_pondere(PAIEMENTS)
        if paiement == "paiement_3x_4x" and not (150 <= sous_total <= 3000):
            paiement = "carte_bancaire"

        heure = rnd.randint(7, 11) if d == DATE_REF else rnd.randint(7, 23)
        dt_cmd = datetime(d.year, d.month, d.day, heure, rnd.randint(0, 59))
        assemblage = service_montage or any(p["categorie"] == "PC fixe" for p, _ in lignes)

        # ---- chronologie
        historique = []
        statut = None
        date_paiement = d if paiement != "virement" else d + timedelta(days=rnd.randint(1, 3))
        historique.append({"date": dt_cmd.isoformat(timespec="minutes"), "statut": "commande_validee"})
        if paiement == "virement":
            if date_paiement > DATE_REF:
                statut = "en_attente_paiement"
            else:
                historique.append({"date": f"{date_paiement.isoformat()}T10:00", "statut": "paiement_recu"})

        annule = statut is None and rnd.random() < 0.04
        depart = date_paiement if (paiement != "virement" and heure < 14) else jours_ouvres(date_paiement, 1)
        depart = prochain_jour_ouvre(depart)
        if assemblage:
            fin_assemblage = jours_ouvres(depart, rnd.randint(3, 5))
            historique.append({"date": f"{depart.isoformat()}T09:00", "statut": "en_assemblage"})
            date_exp = fin_assemblage
        else:
            date_exp = depart

        date_exp_reelle = date_exp_estimee = None
        date_livraison_estimee = date_livraison = None
        if mode == "retrait_showroom":
            date_livraison_estimee = date_exp
        else:
            dmin, dmax = m["delai"]
            if client["code_postal"].startswith("20"):
                dmin, dmax = 4, 7
            date_livraison_estimee = jours_ouvres(date_exp, dmax) if dmax else date_exp
            date_reelle = jours_ouvres(date_exp, rnd.randint(dmin, dmax)) if dmax else date_exp

        if statut is None:
            if annule and date_exp > d:
                statut = "annulee"
                historique.append({"date": f"{min(d + timedelta(days=1), DATE_REF).isoformat()}T11:30", "statut": "annulee"})
            elif date_exp >= DATE_REF:
                statut = "en_assemblage" if assemblage else "en_preparation"
                if not assemblage:
                    historique.append({"date": f"{min(depart, DATE_REF).isoformat()}T09:00", "statut": "en_preparation"})
            else:
                historique.append({"date": f"{date_exp.isoformat()}T16:00", "statut": "expediee" if mode != "retrait_showroom" else "disponible_retrait"})
                date_exp_reelle = date_exp
                if mode == "retrait_showroom":
                    retrait = date_exp + timedelta(days=rnd.randint(0, 4))
                    if retrait > DATE_REF:
                        statut = "disponible_retrait"
                    else:
                        statut = "livree"
                        date_livraison = retrait
                        historique.append({"date": f"{retrait.isoformat()}T17:00", "statut": "livree"})
                elif date_reelle >= DATE_REF:
                    statut = "en_cours_de_livraison" if (date_reelle - DATE_REF).days == 0 else "expediee"
                    if statut == "en_cours_de_livraison":
                        historique.append({"date": f"{DATE_REF.isoformat()}T07:30", "statut": "en_cours_de_livraison"})
                else:
                    statut = "livree"
                    date_livraison = date_reelle
                    historique.append({"date": f"{date_reelle.isoformat()}T12:00", "statut": "livree"})

        # retours sur une partie des commandes livrées depuis plus de 5 jours
        retour = None
        if statut == "livree" and (DATE_REF - date_livraison).days >= 5 and rnd.random() < 0.08:
            date_dem = date_livraison + timedelta(days=rnd.randint(2, 12))
            motif = rnd.choice(["changement d'avis", "produit défectueux", "ne correspond pas à mes attentes", "erreur de commande"])
            prod_ret = rnd.choice(lignes)[0]
            gratuit = motif == "produit défectueux"
            retour = {"numero_rma": f"RMA-{rnd.randint(10000, 99999)}", "date_demande": date_dem.isoformat(),
                      "sku": prod_ret["sku"], "motif": motif, "frais_retour": 0.0 if gratuit else (6.90 if client["pays"] == "France" else 12.90)}
            historique.append({"date": f"{date_dem.isoformat()}T15:00", "statut": "retour_en_cours"})
            if date_dem + timedelta(days=9) <= DATE_REF:
                statut = "retour_rembourse"
                montant = round(prod_ret["prix_ttc"] - retour["frais_retour"], 2)
                retour["montant_rembourse"] = montant
                retour["date_remboursement"] = (date_dem + timedelta(days=9)).isoformat()
                historique.append({"date": f"{retour['date_remboursement']}T10:00", "statut": "retour_rembourse"})
            else:
                statut = "retour_en_cours"

        transporteur = m["transporteur"] if mode != "retrait_showroom" else None
        suivi = numero_suivi(transporteur) if transporteur and date_exp_reelle else None

        cmd = {
            "numero": num,
            "client_id": client["client_id"],
            "email_client": client["email"],
            "date_commande": dt_cmd.isoformat(timespec="minutes"),
            "statut": statut,
            "statut_libelle": STATUTS_LIBELLES[statut],
            "lignes": [{"sku": p["sku"], "nom": p["nom"], "quantite": q, "prix_unitaire_ttc": p["prix_ttc"],
                        "total_ligne_ttc": round(p["prix_ttc"] * q, 2)} for p, q in lignes],
            "services": [{"code": "MONTAGE_PC", "libelle": "Montage et tests en atelier", "prix_ttc": 49.0}] if service_montage else [],
            "sous_total_ttc": sous_total,
            "mode_livraison": mode,
            "mode_livraison_libelle": m["libelle"],
            "frais_livraison_ttc": fdp,
            "total_ttc": round(sous_total + fdp, 2),
            "moyen_paiement": paiement,
            "adresse_livraison": None if mode == "retrait_showroom" else {"ville": client["ville"], "code_postal": client["code_postal"], "pays": client["pays"]},
            "transporteur": transporteur,
            "numero_suivi": suivi,
            "date_expedition": date_exp_reelle.isoformat() if date_exp_reelle else None,
            "date_livraison_estimee": date_livraison_estimee.isoformat() if statut not in ("annulee", "en_attente_paiement") else None,
            "date_livraison": date_livraison.isoformat() if date_livraison else None,
            "retour": retour,
            "historique": historique,
        }
        commandes.append(cmd)

        if statut in ("livree", "retour_en_cours", "retour_rembourse"):
            client["points_fidelite"] += int(sum(p["prix_ttc"] * q for p, q in lignes))
    return commandes


def main():
    produits = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    clients = generer_clients()
    commandes = generer_commandes(clients, produits)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "clients.json").write_text(json.dumps(clients, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "commandes.json").write_text(json.dumps(commandes, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = {}
    for c in commandes:
        stats[c["statut"]] = stats.get(c["statut"], 0) + 1
    print(f"{len(clients)} clients et {len(commandes)} commandes générés dans {OUT_DIR.relative_to(ROOT)}")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  - {k}: {v}")


if __name__ == "__main__":
    main()
