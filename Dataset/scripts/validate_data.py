"""Vérifie la cohérence de toutes les données du projet.

Usage : python scripts/validate_data.py
Code de sortie 0 si tout est valide, 1 sinon.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
erreurs, avertissements = [], []


def err(msg):
    erreurs.append(msg)


def lire_front_matter(path):
    texte = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", texte, re.S)
    if not m:
        err(f"{path.relative_to(ROOT)} : front-matter manquant")
        return {}, texte
    meta = dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l)
    return meta, texte[m.end():]


def valider_documents():
    ids = {}
    for path in sorted((DATA / "documents").rglob("*.md")):
        meta, corps = lire_front_matter(path)
        for champ in ("id", "titre", "type", "mise_a_jour"):
            if champ not in meta:
                err(f"{path.name} : champ '{champ}' absent du front-matter")
        if meta.get("id") and meta["id"] != path.stem:
            err(f"{path.name} : l'id '{meta['id']}' doit correspondre au nom du fichier")
        if meta.get("id") in ids:
            err(f"id de document en double : {meta['id']}")
        if len(corps.split()) < 150:
            avertissements.append(f"{path.name} : document court ({len(corps.split())} mots)")
        ids[meta.get("id")] = path
    return ids


def valider_catalogue():
    produits = json.loads((DATA / "catalogue" / "produits.json").read_text(encoding="utf-8"))
    skus = {}
    for p in produits:
        s = p["sku"]
        if s in skus:
            err(f"SKU en double : {s}")
        skus[s] = p
        if p["prix_ttc"] <= 0:
            err(f"{s} : prix invalide")
        if p["prix_barre"] is not None and p["prix_barre"] <= p["prix_ttc"]:
            err(f"{s} : le prix barré doit être supérieur au prix")
        if p["stock"] == 0 and not p["date_reapprovisionnement"]:
            err(f"{s} : rupture sans date de réapprovisionnement")
        if p["stock"] > 0 and p["date_reapprovisionnement"]:
            err(f"{s} : date de réapprovisionnement alors que le produit est en stock")
        if len(p["description"]) < 40:
            err(f"{s} : description trop courte")
    # Cohérence technique des composants
    for p in produits:
        c = p.get("compatibilite", {})
        if p["categorie"] == "Processeur":
            mobos = [m for m in produits if m["categorie"] == "Carte mère" and m["compatibilite"]["socket"] == c["socket"]]
            if not mobos:
                err(f"{p['sku']} : aucune carte mère au socket {c['socket']}")
            for m in mobos:
                if m["compatibilite"]["memoire"] not in c["memoire"]:
                    err(f"{p['sku']} / {m['sku']} : type de mémoire incohérent")
        if p["categorie"] == "Carte graphique":
            if not any(a["categorie"] == "Alimentation" and a["compatibilite"]["puissance_w"] >= c["alim_min_w"] for a in produits):
                err(f"{p['sku']} : aucune alimentation suffisante au catalogue")
    return skus


def valider_commandes(skus):
    clients = {c["client_id"]: c for c in json.loads((DATA / "commandes" / "clients.json").read_text(encoding="utf-8"))}
    commandes = json.loads((DATA / "commandes" / "commandes.json").read_text(encoding="utf-8"))
    numeros = set()
    for c in commandes:
        n = c["numero"]
        if n in numeros:
            err(f"numéro de commande en double : {n}")
        numeros.add(n)
        cli = clients.get(c["client_id"])
        if not cli:
            err(f"{n} : client inconnu {c['client_id']}")
        elif cli["email"] != c["email_client"]:
            err(f"{n} : e-mail différent de celui du client")
        st = 0
        for l in c["lignes"]:
            if l["sku"] not in skus:
                err(f"{n} : SKU inconnu {l['sku']}")
            elif skus[l["sku"]]["prix_ttc"] != l["prix_unitaire_ttc"]:
                err(f"{n} : prix de {l['sku']} différent du catalogue")
            st += l["prix_unitaire_ttc"] * l["quantite"]
        st += sum(s["prix_ttc"] for s in c["services"])
        if round(st, 2) != c["sous_total_ttc"]:
            err(f"{n} : sous-total incorrect")
        if round(c["sous_total_ttc"] + c["frais_livraison_ttc"], 2) != c["total_ttc"]:
            err(f"{n} : total incorrect")
        if c["statut"] in ("expediee", "en_cours_de_livraison", "livree") and c["mode_livraison"] != "retrait_showroom" and not c["numero_suivi"]:
            err(f"{n} : commande expédiée sans numéro de suivi")
        if c["statut"] in ("en_preparation", "en_assemblage", "en_attente_paiement") and c["numero_suivi"]:
            err(f"{n} : numéro de suivi sur une commande non expédiée")
        if c["statut"] == "livree" and not c["date_livraison"]:
            err(f"{n} : commande livrée sans date de livraison")
        if c["date_livraison"] and c["date_livraison"] < c["date_commande"][:10]:
            err(f"{n} : livrée avant d'être commandée")
        if c["moyen_paiement"] == "paiement_3x_4x" and not (150 <= c["sous_total_ttc"] <= 3000):
            err(f"{n} : paiement en plusieurs fois hors plafond")
        # frais de livraison France
        if c["adresse_livraison"] and c["adresse_livraison"]["pays"] == "France":
            regles = {"point_relais": (3.90, 49), "domicile_standard": (5.90, 99), "express_24h": (12.90, None), "rendez_vous": (19.90, 1500)}
            tarif, seuil = regles[c["mode_livraison"]]
            attendu = 0.0 if (seuil is not None and c["sous_total_ttc"] >= seuil) else tarif
            if c["frais_livraison_ttc"] != attendu:
                err(f"{n} : frais de livraison {c['frais_livraison_ttc']} au lieu de {attendu}")
    return numeros


def valider_tests(doc_ids, skus, numeros):
    tests = json.loads((ROOT / "evaluation" / "questions_test.json").read_text(encoding="utf-8"))
    for t in tests:
        for s in t["sources_attendues"]:
            if s.startswith("NT-"):
                if s not in skus:
                    err(f"{t['id']} : SKU inconnu {s}")
            elif s.startswith("CMD-"):
                if s not in numeros:
                    err(f"{t['id']} : commande inconnue {s}")
            elif s not in doc_ids:
                err(f"{t['id']} : document inconnu '{s}'")
        if not t["elements_cles"]:
            err(f"{t['id']} : aucun élément clé")
    return tests


def main():
    doc_ids = valider_documents()
    skus = valider_catalogue()
    numeros = valider_commandes(skus)
    tests = valider_tests(doc_ids, skus, numeros)
    print(f"Documents : {len(doc_ids)} | Produits : {len(skus)} | Commandes : {len(numeros)} | Questions de test : {len(tests)}")
    for a in avertissements:
        print("  avertissement :", a)
    if erreurs:
        print(f"\n{len(erreurs)} erreur(s) :")
        for e in erreurs:
            print("  -", e)
        sys.exit(1)
    print("✅ Toutes les données sont cohérentes.")


if __name__ == "__main__":
    main()
