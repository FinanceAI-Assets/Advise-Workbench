/**
 * Talk to Sheldon without holding one long request open.
 *
 * The backend answers in the background and returns a turn id; this polls the turn until the
 * reply is ready, so a slow reply no longer hits the request timeout.
 */

type Api = (path: string, init?: RequestInit) => Promise<Response>;

export type ConversationSendResult = { ok: boolean; data: Record<string, unknown> };

const POLL_MS = 1500;
const GIVE_UP_MS = 15 * 60 * 1000;
const MAX_POLL_ERRORS = 5;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Chat message to Sheldon. */
export function sendConversationMessage(
  api: Api,
  pid: string,
  content: string,
  onPhase?: (label: string) => void,
  pollMs: number = POLL_MS,
): Promise<ConversationSendResult> {
  return postConversationInBackground(api, pid, "messages", { content }, onPhase, pollMs);
}

/** POST to a conversation endpoint ("messages", "decisions" or "outline") and poll for the result. */
export async function postConversationInBackground(
  api: Api,
  pid: string,
  endpoint: "messages" | "decisions" | "outline",
  body: unknown,
  onPhase?: (label: string) => void,
  pollMs: number = POLL_MS,
): Promise<ConversationSendResult> {
  const base = `/api/projects/${encodeURIComponent(pid)}/conversation`;
  const started = await api(`${base}/${endpoint}?background=true`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const first = ((await started.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
  // No turn id: an error, or a backend that answered directly.
  if (!started.ok || typeof first.turn_id !== "string") return { ok: started.ok, data: first };
  if (typeof first.phase_label === "string") onPhase?.(first.phase_label);

  const deadline = Date.now() + GIVE_UP_MS;
  let errors = 0;
  while (Date.now() < deadline) {
    await sleep(pollMs);
    let turn: Record<string, unknown>;
    try {
      const res = await api(`${base}/turns/${encodeURIComponent(first.turn_id)}`);
      turn = ((await res.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
      if (!res.ok) return { ok: false, data: turn };
      errors = 0;
    } catch (err) {
      errors += 1;
      if (errors >= MAX_POLL_ERRORS) throw err;
      continue;
    }
    if (typeof turn.phase_label === "string") onPhase?.(turn.phase_label);
    if (turn.status !== "running") {
      const data = turn.response && typeof turn.response === "object" ? (turn.response as Record<string, unknown>) : {};
      return { ok: turn.status === "done", data };
    }
  }
  return { ok: false, data: { detail: "Sheldon is taking too long to reply. Refresh the page to see whether the reply arrived." } };
}
