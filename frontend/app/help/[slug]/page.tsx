"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageFrame } from "@/components/workbench/PageFrame";
import { findHelpArticle } from "@/lib/helpArticles";

export default function HelpArticlePage() {
  const params = useParams();
  const slug = typeof params.slug === "string" ? params.slug : "";
  const article = findHelpArticle(slug);

  if (!article) {
    return (
      <main className="space-y-4">
        <EmptyState title="Article not found">
          <Link href="/help">
            <Button variant="secondary">Back to help</Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  return (
    <PageFrame
      breadcrumb={
        <>
          User workspace / <Link href="/help">Help &amp; documentation</Link> / Article
        </>
      }
      title={article.title}
      subtitle={`${article.category} · ${article.minutes} min read`}
      actions={
        article.action ? (
          <Link href={article.action.href} className="!no-underline">
            <Button>{article.action.label}</Button>
          </Link>
        ) : undefined
      }
    >
      <section className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        <Card className="h-fit space-y-2">
          <h2 className="text-base font-semibold text-[var(--text-default)]">In this article</h2>
          <ol className="space-y-1 text-sm text-[var(--text-muted)]">
            {article.steps.map((step) => (
              <li key={step.heading}>{step.heading}</li>
            ))}
          </ol>
        </Card>
        <div className="space-y-4">
          <Card>
            <p className="text-sm text-[var(--text-default)]">{article.summary}</p>
          </Card>
          {article.steps.map((step) => (
            <Card key={step.heading} className="space-y-1">
              <h2 className="text-base font-semibold text-[var(--text-default)]">{step.heading}</h2>
              <p className="text-sm text-[var(--text-default)]">{step.body}</p>
            </Card>
          ))}
          {article.note ? (
            <p className="rounded-md border border-[#F3E2C0] bg-[#FCF3E2] px-3 py-2 text-sm text-[#8C5B12]">
              <span className="block font-semibold">{article.note.title}</span>
              {article.note.body}
            </p>
          ) : null}
        </div>
      </section>
    </PageFrame>
  );
}
