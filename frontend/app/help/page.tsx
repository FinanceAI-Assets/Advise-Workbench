"use client";

import { Button } from "@/components/ui/Button";
import Link from "next/link";
import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { PageFrame } from "@/components/workbench/PageFrame";
import { HELP_ARTICLES, HELP_CATEGORIES, type HelpArticle } from "@/lib/helpArticles";

export default function HelpPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<HelpArticle["category"] | null>(null);
  const needle = query.trim().toLowerCase();
  const articles = HELP_ARTICLES.filter(
    (article) =>
      (!category || article.category === category) &&
      (!needle || `${article.title} ${article.summary} ${article.category}`.toLowerCase().includes(needle))
  );

  return (
    <PageFrame
      breadcrumb="User workspace / Side nav / Help & documentation"
      title="Help & documentation"
      subtitle="Guidance for evidence-led advisory work, secure collaboration and human review."
    >
      <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        Search guidance
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search articles, workflows or policy terms…" />
      </label>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" aria-label="Browse by workflow">
        {HELP_CATEGORIES.map((item) => {
          const count = HELP_ARTICLES.filter((article) => article.category === item.name).length;
          const active = category === item.name;
          return (
            <Button
              key={item.name}
              type="button"
              variant="ghost"
              aria-pressed={active}
              onClick={() => setCategory(active ? null : item.name)}
              className={`rounded-lg border bg-white p-4 text-left shadow-sm ${
                active ? "border-[var(--accent-green)]" : "border-[var(--surface-border)]"
              }`}
            >
              <p className="text-sm font-semibold text-[var(--text-default)]">{item.name}</p>
              <p className="text-xs text-[var(--text-muted)]">
                {count} article{count === 1 ? "" : "s"} · {item.blurb}
              </p>
            </Button>
          );
        })}
      </section>

      {articles.length === 0 ? (
        <EmptyState title="No articles match" description="Try a different term or clear the workflow filter." />
      ) : (
        <Card className="divide-y divide-[var(--surface-border)] p-0">
          {articles.map((article) => (
            <Link key={article.slug} href={`/help/${article.slug}`} className="block p-4 !no-underline hover:bg-[var(--surface-muted)]">
              <p className="text-sm font-semibold text-[var(--text-default)]">{article.title}</p>
              <p className="text-xs text-[var(--text-muted)]">
                {article.category} · {article.minutes} min read
              </p>
              <p className="mt-1 text-sm text-[var(--text-default)]">{article.summary}</p>
            </Link>
          ))}
        </Card>
      )}

      <Card>
        <p className="text-sm font-semibold text-[var(--text-default)]">Need help with an access boundary?</p>
        <p className="text-sm text-[var(--text-muted)]">
          Send the engagement ID and error reference to your workspace administrator. Do not attach client documents or
          restricted source excerpts.
        </p>
      </Card>
    </PageFrame>
  );
}
