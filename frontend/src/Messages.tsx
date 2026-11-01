import Markdown from "react-markdown";
import type { ReponseAssistant, Transfert } from "./api";

export function BulleClient({ texte }: { texte: string }) {
  return (
    <div className="ligne ligne-client">
      <div className="bulle bulle-client">{texte}</div>
    </div>
  );
}

function Avatar() {
  return (
    <span className="avatar" aria-hidden="true">
      N
    </span>
  );
}

export function BulleAssistant({
  reponse,
  ouvrirSource,
}: {
  reponse: ReponseAssistant;
  ouvrirSource: (id: string) => void;
}) {
  return (
    <div className="ligne">
      <Avatar />
      <div className="bulle bulle-assistant">
        <div className="texte">
          {/* Le HTML brut n'est pas interprété par react-markdown : pas d'injection de script. */}
          <Markdown>{reponse.texte}</Markdown>
        </div>
        {reponse.transfert && <CarteTransfert transfert={reponse.transfert} />}
        {reponse.sources.length > 0 && (
          <div className="sources">
            <span className="sources-titre">Sources</span>
            {reponse.sources.map((s) => (
              <button key={s.id} className="source" onClick={() => ouvrirSource(s.id)}>
                <span aria-hidden="true">{s.type === "produit" ? "🛒" : "📄"}</span>
                {s.titre}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CarteTransfert({ transfert }: { transfert: Transfert }) {
  return (
    <div className="transfert">
      <strong>Demande transmise à un conseiller · {transfert.reference_demande}</strong>
      <span>
        {transfert.conseillers_disponibles_maintenant
          ? "Les conseillers sont disponibles en ce moment."
          : "Les conseillers vous recontacteront dès la réouverture."}{" "}
        Horaires : {transfert.horaires}.
      </span>
      <span>
        {transfert.contact.telephone} · {transfert.contact.email}
      </span>
    </div>
  );
}

export function BulleAttente({ etapes }: { etapes: string[] }) {
  const liste = etapes.length ? etapes : ["Réflexion…"];
  return (
    <div className="ligne">
      <Avatar />
      <div className="bulle bulle-assistant attente" aria-label="Réponse en cours">
        {liste.map((etape, i) => (
          <div key={i} className={i === liste.length - 1 ? "etape active" : "etape"}>
            <span className="indicateur" aria-hidden="true" />
            {etape}
          </div>
        ))}
      </div>
    </div>
  );
}
