// Client de l'API FastAPI (voir novatech/api/app.py).

export type Source = { id: string; title: string; type: "document" | "product" };

export type Handoff = {
  request_reference: string;
  agents_available_now: boolean;
  hours: string;
  contact: { phone: string; email: string };
};

export type AssistantReply = {
  text: string;
  sources: Source[];
  tools: string[];
  handoff: Handoff | null;
};

export type SourceDetail = { id: string; title: string; type: string; content: string };

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    const detail = typeof body.detail === "string" ? body.detail : "Requête invalide.";
    return new ApiError(detail, response.status);
  } catch {
    return new ApiError("Le service ne répond pas. Réessayez dans un instant.", response.status);
  }
}

export async function createConversation(): Promise<string> {
  const response = await fetch("/api/conversations", { method: "POST" });
  if (!response.ok) throw await readError(response);
  return (await response.json()).id;
}

export async function getSource(id: string): Promise<SourceDetail> {
  const response = await fetch(`/api/sources/${encodeURIComponent(id)}`);
  if (!response.ok) throw await readError(response);
  return response.json();
}

/** Envoie une question et lit le flux d'événements (Server-Sent Events) renvoyé par l'API. */
export async function sendQuestion(
  conversationId: string,
  question: string,
  onStep: (label: string) => void,
): Promise<AssistantReply> {
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok || !response.body) throw await readError(response);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    // Un événement se termine par une ligne vide.
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const eventType = /^event: (.+)$/m.exec(block)?.[1];
      const data = JSON.parse(/^data: (.+)$/m.exec(block)?.[1] ?? "{}");
      if (eventType === "tool") onStep(data.label);
      else if (eventType === "reply") return data as AssistantReply;
      else if (eventType === "error") throw new ApiError(data.message);
    }
  }
  throw new ApiError("La connexion a été interrompue. Réessayez.");
}
