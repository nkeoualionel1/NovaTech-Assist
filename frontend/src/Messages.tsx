import Markdown from "react-markdown";
import type { AssistantReply, Handoff } from "./api";

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="row row-user">
      <div className="bubble bubble-user">{text}</div>
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

export function AssistantBubble({
  reply,
  onOpenSource,
}: {
  reply: AssistantReply;
  onOpenSource: (id: string) => void;
}) {
  return (
    <div className="row">
      <Avatar />
      <div className="bubble bubble-assistant">
        <div className="markdown">
          {/* Le HTML brut n'est pas interprété par react-markdown : pas d'injection de script. */}
          <Markdown>{reply.text}</Markdown>
        </div>
        {reply.handoff && <HandoffCard handoff={reply.handoff} />}
        {reply.sources.length > 0 && (
          <div className="sources">
            <span className="sources-title">Sources</span>
            {reply.sources.map((s) => (
              <button key={s.id} className="source" onClick={() => onOpenSource(s.id)}>
                <span aria-hidden="true">{s.type === "product" ? "🛒" : "📄"}</span>
                {s.title}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HandoffCard({ handoff }: { handoff: Handoff }) {
  return (
    <div className="handoff">
      <strong>Demande transmise à un conseiller · {handoff.request_reference}</strong>
      <span>
        {handoff.agents_available_now
          ? "Les conseillers sont disponibles en ce moment."
          : "Les conseillers vous recontacteront dès la réouverture."}{" "}
        Horaires : {handoff.hours}.
      </span>
      <span>
        {handoff.contact.phone} · {handoff.contact.email}
      </span>
    </div>
  );
}

export function PendingBubble({ steps }: { steps: string[] }) {
  const visibleSteps = steps.length ? steps : ["Réflexion…"];
  return (
    <div className="row">
      <Avatar />
      <div className="bubble bubble-assistant pending" aria-label="Réponse en cours">
        {visibleSteps.map((step, i) => (
          <div key={i} className={i === visibleSteps.length - 1 ? "step active" : "step"}>
            <span className="indicator" aria-hidden="true" />
            {step}
          </div>
        ))}
      </div>
    </div>
  );
}
