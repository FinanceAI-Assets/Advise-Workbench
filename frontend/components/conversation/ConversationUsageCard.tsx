"use client";

import { Activity } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { useConversationUsageQuery } from "@/hooks/useWorkbench";

const number = new Intl.NumberFormat();

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="font-medium tabular-nums text-[var(--text-default)]">{value}</span>
    </div>
  );
}

/** Tokens, estimated cost and model for the active conversation. Updates while Sheldon is replying. */
export function ConversationUsageCard({ pid, busy }: { pid: string; busy: boolean }) {
  const usage = useConversationUsageQuery(pid, busy);
  const data = usage.data;

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-semibold text-[var(--text-default)]">
          <Activity size={16} className="text-[var(--accent-green)]" aria-hidden />
          Usage &amp; cost
        </h2>
        {data?.live ? (
          <span className="flex items-center gap-1 text-xs font-medium text-[var(--accent-green-dark)]">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent-green)]" aria-hidden />
            Live
          </span>
        ) : null}
      </div>
      {!data ? (
        <p className="text-xs text-[var(--text-muted)]">{usage.isError ? "Usage is unavailable." : "Loading…"}</p>
      ) : (
        <>
          <Row label="Model" value={data.model} />
          <Row label="Input tokens" value={number.format(data.inputTokens)} />
          <Row label="Output tokens" value={number.format(data.outputTokens)} />
          {data.cacheReadTokens + data.cacheCreationTokens > 0 ? (
            <Row label="Cached tokens" value={number.format(data.cacheReadTokens + data.cacheCreationTokens)} />
          ) : null}
          <div className="border-t border-[var(--surface-border)] pt-3">
            <Row label="Total tokens" value={number.format(data.totalTokens)} />
            <Row label="Estimated cost" value={`$${data.costUsd.toFixed(4)}`} />
          </div>
          <p className="text-xs text-[var(--text-muted)]">
            This conversation · {data.replies} {data.replies === 1 ? "reply" : "replies"} · priced at $
            {data.pricing.inputPerMillion} in / ${data.pricing.outputPerMillion} out per million tokens.
          </p>
        </>
      )}
    </Card>
  );
}
