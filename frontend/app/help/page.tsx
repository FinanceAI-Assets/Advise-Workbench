"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageFrame } from "@/components/workbench/PageFrame";
import { HELP_ARTICLES, HELP_CATEGORIES, type HelpArticle } from "@/lib/helpArticles";

const RECOMMENDED_SLUGS = [
  "resolve-an-unsupported-claim",
  "why-is-export-locked",
  "invite-an-engagement-contributor",
  "trace-a-citation-back-to-its-source",
];

export default function HelpPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<HelpArticle["category"] | null>(null);
  const needle = query.trim().toLowerCase();

  const articles = useMemo(() => {
    const filtered = HELP_ARTICLES.filter(
      (article) =>
        (!category || article.category === category) &&
        (!needle ||
          `${article.title} ${article.summary} ${article.category}`.toLowerCase().includes(needle))
    );
    if (needle || category) return filtered;
    return RECOMMENDED_SLUGS.map((slug) => HELP_ARTICLES.find((article) => article.slug === slug)).filter(
      (article): article is HelpArticle => Boolean(article)
    );
  }, [category, needle]);

  return (
    <PageFrame
      breadcrumb="User workspace / Side nav / Help & documentation"
      title="Help & documentation"
      subtitle="Guidance for evidence-led advisory work, secure collaboration and human review."
      actions={
        <a href="mailto:workbench-support@example.com" className="!no-underline">
          <Button type="button" variant="secondary">
            Contact support
          </Button>
        </a>
      }
    >
      <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        Search guidance
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search articles, workflows or policy terms…"
          aria-label="Search guidance"
        />
      </label>

      <section className="grid gap-4 lg:grid-cols-[262px_minmax(0,1fr)]" aria-label="Help guidance">
        <Card className="h-fit p-4">
          <h2 className="text-base font-medium text-[var(--text-default)]">Browse by workflow</h2>
          <div className="mt-3 grid gap-1">
            {HELP_CATEGORIES.map((item) => {
              const count = HELP_ARTICLES.filter((article) => article.category === item.name).length;
              const active = category === item.name;
              return (
                <button
                  key={item.name}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setCategory(active ? null : item.name)}
                  className={`rounded-md p-2 text-left transition hover:bg-[var(--surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-blue)] ${
                    active ? "bg-[var(--surface-muted)]" : ""
                  }`}
                >
                  <span className="block text-sm font-semibold text-[var(--text-default)]">{item.name}</span>
                  <span className="mt-0.5 block text-xs text-[var(--text-muted)]">
                    {count} articles · {item.blurb}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-base font-medium text-[var(--text-default)]">
              {needle || category ? "Guidance results" : "Recommended for Northstar"}
            </h2>
            {!needle && !category ? (
              <span className="text-xs text-[var(--text-muted)]">· Contextual guidance</span>
            ) : null}
          </div>

          {articles.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="No articles match"
                description="Try a different term or clear the workflow filter."
              />
            </div>
          ) : (
            <div className="mt-3 divide-y divide-[var(--surface-border)]">
              {articles.map((article, index) => (
                <Link
                  key={article.slug}
                  href={`/help/${article.slug}`}
                  className="block py-2.5 !no-underline first:pt-0 last:pb-0 hover:bg-[var(--surface-muted)]"
                >
                  <p className="text-sm font-semibold text-[var(--text-default)]">
                    {article.title}
                    {!needle && !category && index === 0 ? (
                      <span className="ml-2 text-xs font-medium text-[var(--accent-green-dark)]">
                        Recommended
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                    {article.category} · {article.minutes} min read
                  </p>
                  <p className="mt-1 text-sm leading-5 text-[var(--text-default)]">{article.summary}</p>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </section>

      <Card className="border-0 bg-transparent p-2 shadow-none">
        <p className="text-sm font-semibold text-[var(--text-default)]">
          Need help with an access boundary?
        </p>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Send the engagement ID and error reference to support. Do not attach client documents or
          restricted source excerpts.
        </p>
      </Card>
    </PageFrame>
  );
}
