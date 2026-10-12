"use client";

import { Bookmark, Check, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PracticeCard, PracticeDetailPanel, TaxonomyPanel } from "@/components/lp-library";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { NoticeCard } from "@/components/ui/NoticeCard";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useLpLibraryQuery } from "@/hooks/useLpLibrary";
import { useAuth } from "@/lib/auth-context";

export default function LPLibraryPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
  const [activePracticeId, setActivePracticeId] = useState<string | null>(null);

  const library = useLpLibraryQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/lp-library");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (library.isPending || !library.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <div className="grid gap-4 lg:grid-cols-[260px_1fr_340px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    );
  }

  const data = library.data;
  const activeCategory = activeCategoryId ?? data.activeCategoryId;
  const activePractice = activePracticeId ?? data.cards[0]?.id ?? "";
  const practiceDetail = data.practices[activePractice];

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        User workspace / Leading Practice Library
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Leading Practice Library</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Reusable, approved guidance with versioned provenance. Add the right practice to your engagement—not an unverified
            answer.
          </p>
        </div>
        <Button variant="secondary" type="button" className="flex shrink-0 items-center gap-2">
          <Bookmark size={16} aria-hidden />
          My saved practices
        </Button>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[260px] flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            aria-hidden
          />
          <Input defaultValue="operating model" placeholder="Search: operating model" className="pl-9" />
        </div>
        <Select defaultValue="all" className="w-auto">
          <option value="all">Maturity: All</option>
          <option value="managed">Maturity: Managed</option>
          <option value="optimized">Maturity: Optimized</option>
        </Select>
        <Button variant="secondary" type="button" className="flex items-center gap-2">
          <Check size={16} aria-hidden />
          Approved only
        </Button>
        <Select defaultValue="relevance" className="w-auto">
          <option value="relevance">Sort: Relevance</option>
          <option value="recent">Sort: Most recent</option>
        </Select>
        <span className="ml-auto text-xs text-[var(--text-muted)]">{data.matchingCount} matching practices</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr_340px]">
        <TaxonomyPanel categories={data.categories} activeId={activeCategory} onSelect={setActiveCategoryId} />

        <div className="space-y-3">
          <div className="space-y-3">
            {data.cards.map((card) => (
              <PracticeCard
                key={card.id}
                practice={card}
                active={card.id === activePractice}
                onSelect={() => setActivePracticeId(card.id)}
              />
            ))}
          </div>
          <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
            <span>
              Showing {data.cards.length} of {data.cards.length} matches
            </span>
            <Button variant="secondary" type="button" className="text-sm">
              Clear filters
            </Button>
          </div>
        </div>

        {practiceDetail ? (
          <PracticeDetailPanel practice={practiceDetail} />
        ) : (
          <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
            This practice preview isn&apos;t wired up yet in this demo.
          </div>
        )}
      </div>

      <NoticeCard
        icon={<Check size={18} aria-hidden />}
        title="Use with context, not as a prescription"
        description="Practice recommendations are illustrative. Validate applicability against engagement evidence and sponsor objectives."
      />

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>Illustrative content only · No real client or confidential information</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}
