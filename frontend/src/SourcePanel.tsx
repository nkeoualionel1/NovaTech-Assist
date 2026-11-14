import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { getSource, type SourceDetail } from "./api";

/** Panneau latéral qui affiche le document ou la fiche produit cité par l'assistant. */
export function SourcePanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSource(null);
    setError(null);
    getSource(id).then(setSource, (e: Error) => setError(e.message));
  }, [id]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <aside
        className="panel"
        role="dialog"
        aria-modal="true"
        aria-label="Source citée"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-header">
          <div>
            <span className="panel-kind">
              {source?.type === "product" ? "Fiche produit" : "Document NovaTech"}
            </span>
            <h2>{source?.title ?? "Chargement…"}</h2>
          </div>
          <button className="close" onClick={onClose} aria-label="Fermer" autoFocus>
            ×
          </button>
        </div>
        <div className="panel-content markdown">
          {error && <p role="alert">{error}</p>}
          {source && <Markdown>{source.content}</Markdown>}
        </div>
      </aside>
    </div>
  );
}
