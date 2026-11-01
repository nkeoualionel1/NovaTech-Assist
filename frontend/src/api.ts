// Client de l'API FastAPI (voir novatech/api/app.py).

export type Source = { id: string; titre: string; type: "document" | "produit" };

export type Transfert = {
  reference_demande: string;
  conseillers_disponibles_maintenant: boolean;
  horaires: string;
  contact: { telephone: string; email: string };
};

export type ReponseAssistant = {
  texte: string;
  sources: Source[];
  outils: string[];
  transfert: Transfert | null;
};

export type DetailSource = { id: string; titre: string; type: string; contenu: string };

export class ErreurApi extends Error {
  constructor(message: string, public statut?: number) {
    super(message);
  }
}

async function lireErreur(reponse: Response): Promise<ErreurApi> {
  try {
    const corps = await reponse.json();
    const detail = typeof corps.detail === "string" ? corps.detail : "Requête invalide.";
    return new ErreurApi(detail, reponse.status);
  } catch {
    return new ErreurApi("Le service ne répond pas. Réessayez dans un instant.", reponse.status);
  }
}

export async function creerConversation(): Promise<string> {
  const reponse = await fetch("/api/conversations", { method: "POST" });
  if (!reponse.ok) throw await lireErreur(reponse);
  return (await reponse.json()).id;
}

export async function lireSource(id: string): Promise<DetailSource> {
  const reponse = await fetch(`/api/sources/${encodeURIComponent(id)}`);
  if (!reponse.ok) throw await lireErreur(reponse);
  return reponse.json();
}

/** Envoie une question et lit le flux d'événements (Server-Sent Events) renvoyé par l'API. */
export async function envoyerQuestion(
  conversationId: string,
  question: string,
  surEtape: (libelle: string) => void,
): Promise<ReponseAssistant> {
  const reponse = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!reponse.ok || !reponse.body) throw await lireErreur(reponse);

  const lecteur = reponse.body.pipeThrough(new TextDecoderStream()).getReader();
  let tampon = "";
  for (;;) {
    const { value, done } = await lecteur.read();
    if (done) break;
    tampon += value;
    // Un événement se termine par une ligne vide.
    let fin: number;
    while ((fin = tampon.indexOf("\n\n")) >= 0) {
      const bloc = tampon.slice(0, fin);
      tampon = tampon.slice(fin + 2);
      const type = /^event: (.+)$/m.exec(bloc)?.[1];
      const donnees = JSON.parse(/^data: (.+)$/m.exec(bloc)?.[1] ?? "{}");
      if (type === "outil") surEtape(donnees.libelle);
      else if (type === "reponse") return donnees as ReponseAssistant;
      else if (type === "erreur") throw new ErreurApi(donnees.message);
    }
  }
  throw new ErreurApi("La connexion a été interrompue. Réessayez.");
}
