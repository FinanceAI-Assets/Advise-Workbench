"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { ErrorNote, PageFrame } from "@/components/workbench/PageFrame";
import { type SearchHit, useSearchQuery } from "@/hooks/useWorkbench";

function Results({ title, hits }: { title: string; hits: SearchHit[] }) {
  if (hits.length === 0) return null;
  return (
    <Card className="space-y-2">
      <h2 className="text-base font-semibold text-[var(--text-default)]">
        {title} · {hits.length}
      </h2>
      <ul className="divide-y divide-[var(--surface-border)]">
        {hits.map((hit) => (
          <li key={hit.id} className="py-2">
            <Link href={hit.href} className="text-sm font-medium">
              {hit.title}
            </Link>
            <p className="text-xs text-[var(--text-muted)]">{hit.meta}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  // The header search box links here with ?q=…
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q") ?? "";
    setQuery(initial);
    setSubmitted(initial);
  }, []);

  const results = useSearchQuery(submitted);
  const data = results.data;
  const total = data ? data.engagements.length + data.practices.length + data.artifacts.length : 0;

  return (
    <PageFrame
      breadcrumb="User workspace / Header / Search"
      title="Search workbench"
      subtitle="Find engagements, approved practices and source-linked artifacts within your permissions."
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(query.trim());
        }}
        className="relative"
      >
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
        <Input
          aria-label="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, code or topic, then press Enter"
          className="pl-9"
        />
      </form>
      <ErrorNote error={results.error} />
      {submitted.length < 2 ? (
        <EmptyState title="Type at least two characters" description="Results only include content you are permitted to see." />
      ) : results.isPending ? (
        <p className="text-sm text-[var(--text-muted)]">Searching…</p>
      ) : total === 0 ? (
        <EmptyState title={`No results for “${submitted}”`} description="Try a different term." />
      ) : (
        <div className="space-y-4">
          <Results title="Engagements" hits={data?.engagements ?? []} />
          <Results title="Approved practices" hits={data?.practices ?? []} />
          <Results title="Artifacts" hits={data?.artifacts ?? []} />
        </div>
      )}
    </PageFrame>
  );
}
