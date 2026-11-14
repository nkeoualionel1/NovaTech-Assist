import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, createConversation, sendQuestion, type AssistantReply } from "./api";
import { AssistantBubble, PendingBubble, UserBubble } from "./Messages";
import { SourcePanel } from "./SourcePanel";
import { isWelcomeHidden, WelcomeDialog } from "./WelcomeDialog";

const MAX_MESSAGE_LENGTH = 2000;
const SUGGESTIONS = [
  "Livrez-vous en Belgique, et à partir de quel montant est-ce gratuit ?",
  "Le Ryzen 7 7800X3D est-il en stock ?",
  "Je cherche un portable léger pour mes études.",
  "Où en est ma commande ?",
];

type Exchange =
  | { role: "user"; text: string }
  | { role: "assistant"; reply: AssistantReply }
  | { role: "error"; text: string };

export default function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [draft, setDraft] = useState("");
  const [steps, setSteps] = useState<string[] | null>(null); // non nul = réponse en cours
  const [openSourceId, setOpenSourceId] = useState<string | null>(null);
  const [isWelcomeOpen, setIsWelcomeOpen] = useState(() => !isWelcomeHidden());
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const startConversation = useCallback(async () => {
    setExchanges([]);
    setOpenSourceId(null);
    try {
      setConversationId(await createConversation());
    } catch (e) {
      setExchanges([{ role: "error", text: (e as Error).message }]);
    }
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    startConversation();
  }, [startConversation]);

  // Curseur dans la zone de saisie dès qu'elle est utilisable et que l'accueil est fermé.
  useEffect(() => {
    if (conversationId && !isWelcomeOpen) inputRef.current?.focus();
  }, [conversationId, isWelcomeOpen]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [exchanges, steps]);

  async function submit(question: string) {
    question = question.trim();
    if (!question || steps !== null || !conversationId) return;
    setDraft("");
    setExchanges((ex) => [...ex, { role: "user", text: question }]);
    setSteps([]);
    try {
      let id = conversationId;
      let reply: AssistantReply;
      const onStep = (label: string) =>
        setSteps((current) => (current && current.at(-1) === label ? current : [...(current ?? []), label]));
      try {
        reply = await sendQuestion(id, question, onStep);
      } catch (e) {
        // Conversation expirée côté serveur : on en ouvre une nouvelle et on renvoie la question.
        if (!(e instanceof ApiError && e.status === 404)) throw e;
        id = await createConversation();
        setConversationId(id);
        reply = await sendQuestion(id, question, onStep);
      }
      setExchanges((ex) => [...ex, { role: "assistant", reply }]);
    } catch (e) {
      setExchanges((ex) => [...ex, { role: "error", text: (e as Error).message }]);
    } finally {
      setSteps(null);
      inputRef.current?.focus();
    }
  }

  const isPending = steps !== null;
  const isTooLong = draft.length > MAX_MESSAGE_LENGTH;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo" aria-hidden="true">N</span>
          <div>
            <h1>NovaTech Assist</h1>
            <p>Service client · réponses issues de notre documentation</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            className="button-icon"
            onClick={() => setIsWelcomeOpen(true)}
            aria-label="À propos de l'assistant"
            title="À propos de l'assistant"
          >
            ?
          </button>
          <button className="button-secondary" onClick={startConversation} disabled={isPending}>
            <span className="label-long">Nouvelle conversation</span>
            <span className="label-short">Nouvelle</span>
          </button>
        </div>
      </header>

      <main className="thread" aria-live="polite">
        <div className="column">
          {exchanges.length === 0 && (
            <section className="welcome">
              <h2>Bonjour, comment puis-je vous aider ?</h2>
              <p>
                Livraison, retours, garantie, choix d'un produit, compatibilité, dépannage ou suivi
                de commande : posez votre question.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => submit(s)} disabled={!conversationId}>
                    {s}
                  </button>
                ))}
              </div>
            </section>
          )}

          {exchanges.map((ex, i) =>
            ex.role === "user" ? (
              <UserBubble key={i} text={ex.text} />
            ) : ex.role === "assistant" ? (
              <AssistantBubble key={i} reply={ex.reply} onOpenSource={setOpenSourceId} />
            ) : (
              <div key={i} className="bubble-error" role="alert">
                {ex.text}
              </div>
            ),
          )}
          {isPending && <PendingBubble steps={steps} />}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="footer">
        <form
          className="column composer"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (!isTooLong) submit(draft);
          }}
        >
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(ev) => setDraft(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" && !ev.shiftKey) {
                ev.preventDefault();
                if (!isTooLong) submit(draft);
              }
            }}
            placeholder="Écrivez votre message…"
            rows={1}
            aria-label="Votre message"
            disabled={!conversationId}
          />
          <button type="submit" className="button-send" disabled={isPending || !draft.trim() || isTooLong}>
            Envoyer
          </button>
        </form>
        <p className="column notice">
          {isTooLong
            ? `Message trop long (${draft.length}/${MAX_MESSAGE_LENGTH} caractères).`
            : "Assistant IA : ne communiquez jamais vos coordonnées bancaires ni vos mots de passe."}
        </p>
      </footer>

      {openSourceId && <SourcePanel id={openSourceId} onClose={() => setOpenSourceId(null)} />}

      <WelcomeDialog open={isWelcomeOpen} onClose={() => setIsWelcomeOpen(false)} />
    </div>
  );
}
