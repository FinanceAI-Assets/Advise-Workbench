"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAuth } from "@/lib/auth-context";

type ModelSettings = {
  provider: string;
  model: string;
  api_key_configured: boolean;
  enabled: boolean;
};

export function ModelProviderSettings({ adminWorkspace }: { adminWorkspace: boolean }) {
  const { api, user } = useAuth();
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!user) return;
    void api("/api/settings/models")
      .then(async (res) => {
        const data = (await res.json().catch(() => ({}))) as ModelSettings & { detail?: string };
        if (!res.ok) throw new Error(data.detail || "Could not load model settings");
        setSettings(data);
        setModel(data.model);
      })
      .catch(setError);
  }, [api, user]);

  if (!user) return <PageSkeleton />;

  const canEdit = adminWorkspace && user.isAdmin;
  const inputDisabled = !canEdit;
  const title = "Settings";
  const breadcrumb = adminWorkspace ? "Admin console / Settings" : "User workspace / Settings";

  return (
    <PageFrame
      breadcrumb={breadcrumb}
      title={title}
      subtitle={
        adminWorkspace
          ? "Configure deployment-level model access for this workbench."
          : "Deployment-level model access is managed in the Admin console."
      }
      actions={
        canEdit ? (
          <Button type="button" onClick={() => setMessage("Draft updated. Apply changes in the backend deployment configuration, then restart the API.")}>
            Save settings
          </Button>
        ) : undefined
      }
    >
      <Card className="max-w-2xl space-y-5 p-5">
        <div>
          <h2 className="text-base font-semibold text-[var(--text-default)]">Model provider and API key</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            The API key is never returned to the browser. It is configured in the backend deployment environment.
          </p>
        </div>

        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Model
          <Input
            value={model}
            onChange={(event) => setModel(event.target.value)}
            placeholder={settings?.provider === "anthropic" ? "claude-sonnet-4-5" : "Model name"}
            disabled={inputDisabled}
          />
        </label>

        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          API key
          <Input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={
              inputDisabled
                ? "Managed by the administrator"
                : settings?.api_key_configured
                  ? "Configured · enter a replacement"
                  : "Paste API key"
            }
            autoComplete="new-password"
            disabled={inputDisabled}
          />
        </label>

        <div className="flex items-center gap-2 text-sm">
          <span
            className={`h-2 w-2 rounded-full ${settings?.enabled ? "bg-[var(--success)]" : "bg-[var(--error)]"}`}
            aria-hidden
          />
          {settings?.enabled ? "Provider ready" : "Provider not configured"}
        </div>
      </Card>

      <ErrorNote error={error} />
      {message ? <p className="text-sm text-[var(--accent-green-dark)]">{message}</p> : null}
    </PageFrame>
  );
}
