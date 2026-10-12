"use client";

import { Plus, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ReleaseApprovalPanel, SkillDefinitionPanel, SkillRegistryList, TestResultsPanel } from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAdminSkillsManagementQuery } from "@/hooks/useAdminSkillsManagement";
import { useAuth } from "@/lib/auth-context";

export default function AdminConsoleSkillsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  const skills = useAdminSkillsManagementQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/console/skills");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (skills.isPending || !skills.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  const data = skills.data;
  const activeSkillId = activeId ?? data.definition.id;
  const showingSelected = activeSkillId === data.definition.id;

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        Admin console / Skills
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Versioned skill definitions</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Configure instructions and evidence contracts, test behavior, and require independent approval before publishing.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Plus size={16} aria-hidden />
            New skill
          </Button>
          <Button type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Save size={16} aria-hidden />
            Save candidate
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <Input placeholder="Search skills or definitions" className="min-w-[260px] flex-1" />
        <Select defaultValue="all" className="w-auto">
          <option value="all">Lifecycle: All</option>
          <option value="published">Lifecycle: Published</option>
          <option value="candidate">Lifecycle: Candidate</option>
        </Select>
        <span className="ml-auto text-xs text-[var(--text-muted)]">
          {data.publishedCount} published · {data.candidateCount} candidates
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr_320px]">
        <SkillRegistryList items={data.registry} activeId={activeSkillId} onSelect={setActiveId} />

        {showingSelected ? (
          <SkillDefinitionPanel skill={data.definition} />
        ) : (
          <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
            This skill&apos;s definition isn&apos;t wired up yet in this demo.
          </div>
        )}

        <div className="space-y-4">
          <TestResultsPanel results={data.testResults} />
          <ReleaseApprovalPanel approval={data.releaseApproval} />
        </div>
      </div>
    </main>
  );
}
