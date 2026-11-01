import { useCallback, useEffect, useRef, useState } from "react";
import { creerConversation, envoyerQuestion, ErreurApi, type ReponseAssistant } from "./api";
import { BulleAssistant, BulleAttente, BulleClient } from "./Messages";
import { PanneauSource } from "./PanneauSource";

const LONGUEUR_MAX = 2000;
const SUGGESTIONS = [
  "Livrez-vous en Belgique, et à partir de quel montant est-ce gratuit ?",
  "Le Ryzen 7 7800X3D est-il en stock ?",
  "Je cherche un portable léger pour mes études.",
  "Où en est ma commande ?",
];

type Echange =
  | { role: "client"; texte: string }
  | { role: "assistant"; reponse: ReponseAssistant }
  | { role: "erreur"; texte: string };

export default function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [echanges, setEchanges] = useState<Echange[]>([]);
  const [saisie, setSaisie] = useState("");
  const [etapes, setEtapes] = useState<string[] | null>(null); // non nul = réponse en cours
  const [sourceOuverte, setSourceOuverte] = useState<string | null>(null);
  const finRef = useRef<HTMLDivElement>(null);
  const saisieRef = useRef<HTMLTextAreaElement>(null);

  const demarrer = useCallback(async () => {
    setEchanges([]);
    setSourceOuverte(null);
    try {
      setConversationId(await creerConversation());
    } catch (e) {
      setEchanges([{ role: "erreur", texte: (e as Error).message }]);
    }
    saisieRef.current?.focus();
  }, []);

  useEffect(() => {
    demarrer();
  }, [demarrer]);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [echanges, etapes]);

  async function envoyer(question: string) {
    question = question.trim();
    if (!question || etapes !== null || !conversationId) return;
    setSaisie("");
    setEchanges((e) => [...e, { role: "client", texte: question }]);
    setEtapes([]);
    try {
      let id = conversationId;
      let reponse: ReponseAssistant;
      const surEtape = (libelle: string) =>
        setEtapes((et) => (et && et.at(-1) === libelle ? et : [...(et ?? []), libelle]));
      try {
        reponse = await envoyerQuestion(id, question, surEtape);
      } catch (e) {
        // Conversation expirée côté serveur : on en ouvre une nouvelle et on renvoie la question.
        if (!(e instanceof ErreurApi && e.statut === 404)) throw e;
        id = await creerConversation();
        setConversationId(id);
        reponse = await envoyerQuestion(id, question, surEtape);
      }
      setEchanges((e) => [...e, { role: "assistant", reponse }]);
    } catch (e) {
      setEchanges((ech) => [...ech, { role: "erreur", texte: (e as Error).message }]);
    } finally {
      setEtapes(null);
      saisieRef.current?.focus();
    }
  }

  const enCours = etapes !== null;
  const trop = saisie.length > LONGUEUR_MAX;

  return (
    <div className="app">
      <header className="entete">
        <div className="marque">
          <span className="logo" aria-hidden="true">N</span>
          <div>
            <h1>NovaTech Assist</h1>
            <p>Service client · réponses issues de notre documentation</p>
          </div>
        </div>
        <button className="bouton-secondaire" onClick={demarrer} disabled={enCours}>
          <span className="libelle-long">Nouvelle conversation</span>
          <span className="libelle-court">Nouvelle</span>
        </button>
      </header>

      <main className="fil" aria-live="polite">
        <div className="colonne">
          {echanges.length === 0 && (
            <section className="accueil">
              <h2>Bonjour, comment puis-je vous aider ?</h2>
              <p>
                Livraison, retours, garantie, choix d'un produit, compatibilité, dépannage ou suivi
                de commande : posez votre question.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => envoyer(s)} disabled={!conversationId}>
                    {s}
                  </button>
                ))}
              </div>
            </section>
          )}

          {echanges.map((e, i) =>
            e.role === "client" ? (
              <BulleClient key={i} texte={e.texte} />
            ) : e.role === "assistant" ? (
              <BulleAssistant key={i} reponse={e.reponse} ouvrirSource={setSourceOuverte} />
            ) : (
              <div key={i} className="bulle-erreur" role="alert">
                {e.texte}
              </div>
            ),
          )}
          {enCours && <BulleAttente etapes={etapes} />}
          <div ref={finRef} />
        </div>
      </main>

      <footer className="pied">
        <form
          className="colonne zone-saisie"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (!trop) envoyer(saisie);
          }}
        >
          <textarea
            ref={saisieRef}
            value={saisie}
            onChange={(ev) => setSaisie(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" && !ev.shiftKey) {
                ev.preventDefault();
                if (!trop) envoyer(saisie);
              }
            }}
            placeholder="Écrivez votre message…"
            rows={1}
            aria-label="Votre message"
            disabled={!conversationId}
          />
          <button type="submit" className="bouton-envoyer" disabled={enCours || !saisie.trim() || trop}>
            Envoyer
          </button>
        </form>
        <p className="colonne mention">
          {trop
            ? `Message trop long (${saisie.length}/${LONGUEUR_MAX} caractères).`
            : "Assistant IA : ne communiquez jamais vos coordonnées bancaires ni vos mots de passe."}
        </p>
      </footer>

      {sourceOuverte && (
        <PanneauSource id={sourceOuverte} fermer={() => setSourceOuverte(null)} />
      )}
    </div>
  );
}
