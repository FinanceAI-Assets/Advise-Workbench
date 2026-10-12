"use client";

import { History, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SkillCardTile, SkillDetailPanel } from "@/components/skills";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useSkillsCatalogQuery } from "@/hooks/useSkillsCatalog";
import { useAuth } from "@/lib/auth-context";

export default function AdminSkillsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [activeSkillId, setActiveSkillId] = useState<string | null>(null);

  const catalog = useSkillsCatalogQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/skills");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (catalog.isPending || !catalog.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    );
  }

  const data = catalog.data;
  const activeSkillCardId = activeSkillId ?? data.cards[0]?.id ?? "";
  const activeSkill = data.skills[activeSkillCardId];

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        User workspace / Skills
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Expert workflows, repeatable outputs</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Skills guide the conversation with defined inputs, evidence policies and review-ready artifact formats.
          </p>
        </div>
        <Button variant="secondary" type="button" className="flex shrink-0 items-center gap-2">
          <History size={16} aria-hidden />
          Skill run history
        </Button>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[260px] flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            aria-hidden
          />
          <Input placeholder="Search skills by task or output" className="pl-9" />
        </div>
        <Select defaultValue="all" className="w-auto">
          <option value="all">Category: All</option>
          <option value="transformation">Category: Transformation</option>
        </Select>
        <Select defaultValue="all" className="w-auto">
          <option value="all">Output: All</option>
          <option value="pptx">Output: PPTX</option>
          <option value="docx">Output: DOCX</option>
        </Select>
        <span className="ml-auto text-xs text-[var(--text-muted)]">{data.totalPublished} published skills available</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="grid gap-4 sm:grid-cols-2">
          {data.cards.map((card) => (
            <SkillCardTile
              key={card.id}
              skill={card}
              active={card.id === activeSkillCardId}
              onSelect={() => setActiveSkillId(card.id)}
            />
          ))}
        </div>

        {activeSkill ? (
          <SkillDetailPanel skill={activeSkill} />
        ) : (
          <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
            This skill preview isn&apos;t wired up yet in this demo.
          </div>
        )}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>Illustrative content only · No real client or confidential information</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}
