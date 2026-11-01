import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { lireSource, type DetailSource } from "./api";

/** Panneau latéral qui affiche le document ou la fiche produit cité par l'assistant. */
export function PanneauSource({ id, fermer }: { id: string; fermer: () => void }) {
  const [source, setSource] = useState<DetailSource | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    setSource(null);
    setErreur(null);
    lireSource(id).then(setSource, (e: Error) => setErreur(e.message));
  }, [id]);

  useEffect(() => {
    const touche = (e: KeyboardEvent) => e.key === "Escape" && fermer();
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [fermer]);

  return (
    <div className="voile" onClick={fermer}>
      <aside
        className="panneau"
        role="dialog"
        aria-modal="true"
        aria-label="Source citée"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panneau-entete">
          <div>
            <span className="panneau-type">
              {source?.type === "produit" ? "Fiche produit" : "Document NovaTech"}
            </span>
            <h2>{source?.titre ?? "Chargement…"}</h2>
          </div>
          <button className="fermer" onClick={fermer} aria-label="Fermer" autoFocus>
            ×
          </button>
        </div>
        <div className="panneau-contenu texte">
          {erreur && <p role="alert">{erreur}</p>}
          {source && <Markdown>{source.contenu}</Markdown>}
        </div>
      </aside>
    </div>
  );
}
