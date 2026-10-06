import { describe, expect, it, vi } from "vitest";

import { sendConversationMessage } from "./conversationTurn";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("sendConversationMessage", () => {
  it("starts a background turn and polls until the reply is ready", async () => {
    const api = vi
      .fn()
      .mockResolvedValueOnce(json({ turn_id: "t_1", status: "running", phase_label: "Starting" }))
      .mockResolvedValueOnce(json({ turn_id: "t_1", status: "running", phase_label: "Writing the reply" }))
      .mockResolvedValueOnce(json({ turn_id: "t_1", status: "done", response: { conversation_id: "c1", messages: [] } }));
    const phases: string[] = [];
    const out = await sendConversationMessage(api, "p 1", "hello", (p) => phases.push(p), 1);
    expect(out).toEqual({ ok: true, data: { conversation_id: "c1", messages: [] } });
    expect(phases).toEqual(["Starting", "Writing the reply"]);
    expect(api.mock.calls[0][0]).toBe("/api/projects/p%201/conversation/messages?background=true");
    expect(api.mock.calls[1][0]).toBe("/api/projects/p%201/conversation/turns/t_1");
  });

  it("returns the error body of a failed turn", async () => {
    const api = vi
      .fn()
      .mockResolvedValueOnce(json({ turn_id: "t_2", status: "running" }))
      .mockResolvedValueOnce(json({ turn_id: "t_2", status: "failed", response: { detail: "plan_required" } }));
    expect(await sendConversationMessage(api, "p", "go", undefined, 1)).toEqual({ ok: false, data: { detail: "plan_required" } });
  });

  it("returns a rejected message without polling", async () => {
    const api = vi.fn().mockResolvedValueOnce(json({ detail: "content must not be empty" }, 400));
    expect(await sendConversationMessage(api, "p", " ", undefined, 1)).toEqual({
      ok: false,
      data: { detail: "content must not be empty" },
    });
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("survives a dropped poll", async () => {
    const api = vi
      .fn()
      .mockResolvedValueOnce(json({ turn_id: "t_3", status: "running" }))
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(json({ turn_id: "t_3", status: "done", response: { messages: [] } }));
    expect((await sendConversationMessage(api, "p", "hi", undefined, 1)).ok).toBe(true);
  });
});
