"use client";

import { Download, Send } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { DeliverablesDetail, DocSection } from "@/types/api";

export const SECTIONS_PER_PAGE = 2;

/** Group the document's sections into reading pages. */
export function toPages(sections: DocSection[]): DocSection[][] {
  const pages: DocSection[][] = [];
  for (let i = 0; i < sections.length; i += SECTIONS_PER_PAGE) pages.push(sections.slice(i, i + SECTIONS_PER_PAGE));
  return pages.length ? pages : [[]];
}

/** Word tab, left column: the section headings, each pointing at the page it starts on. */
export function DocumentOutline({
  sections,
  page,
  onSelectPage,
}: {
  sections: DocSection[];
  page: number;
  onSelectPage: (page: number) => void;
}) {
  return (
    <Card className="space-y-2">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Document outline</h2>
      <ol className="space-y-1">
        {sections.map((section, i) => {
          const sectionPage = Math.floor(i / SECTIONS_PER_PAGE);
          const active = sectionPage === page;
          return (
            <li key={`${section.heading}-${i}`}>
              <button
                type="button"
                onClick={() => onSelectPage(sectionPage)}
                className={cn(
                  "w-full rounded-md border-l-2 px-2 py-2 text-left transition",
                  active ? "border-l-[var(--accent-green)] bg-[#EFF6E6]" : "border-l-transparent hover:bg-[var(--surface-muted)]"
                )}
              >
                <span className="block text-sm font-semibold text-[var(--text-default)]">
                  {i + 1}. {section.heading}
                </span>
                <span className="block text-xs text-[var(--text-muted)]">
                  Page {sectionPage + 1}
                  {active ? " · Selected" : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

/** Word tab, main column: one page of the document at a time, with review and download actions. */
export function WordDocumentReader({
  docx,
  page,
  onPageChange,
  assumption,
  reviewLabel,
  onReview,
  onDownload,
}: {
  docx: DeliverablesDetail["docx"];
  page: number;
  onPageChange: (page: number) => void;
  // Shown under the page when claims in the run still lack a source.
  assumption?: { title: string; description: string } | null;
  reviewLabel: string;
  onReview: () => void;
  onDownload?: () => void;
}) {
  const pages = toPages(docx.preview.sections);
  const current = pages[Math.min(page, pages.length - 1)];
  const first = page * SECTIONS_PER_PAGE;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-base font-semibold text-[var(--text-default)]">
          Page {page + 1} of {pages.length}
        </h2>
        <span className="text-xs text-[var(--text-muted)]">{docx.preview.footerMeta}</span>
      </div>

      <article className="space-y-4">
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{docx.preview.breadcrumb}</p>
        <h3 className="text-2xl font-semibold text-[var(--text-default)]">{docx.preview.title}</h3>
        <p className="text-xs text-[var(--text-muted)]">{docx.preview.meta}</p>
        {current.map((section, i) => (
          <section key={`${section.heading}-${i}`} className="space-y-2">
            <h4 className="text-lg font-semibold text-[var(--text-default)]">
              {first + i + 1}. {section.heading}
            </h4>
            <p className="whitespace-pre-line text-sm leading-relaxed text-[var(--text-default)]">{section.body}</p>
          </section>
        ))}
      </article>

      {assumption ? (
        <div className="rounded-lg border border-[#F3E2C0] bg-[#FCF3E2] p-3">
          <p className="text-sm font-semibold text-[#8C5B12]">{assumption.title}</p>
          <p className="text-xs text-[#8C5B12]">{assumption.description}</p>
        </div>
      ) : null}
      <p className="text-xs text-[var(--text-muted)]">{docx.citationSummary}</p>

      <div className="flex flex-wrap gap-2 border-t border-[var(--surface-border)] pt-4">
        {page > 0 ? (
          <Button variant="secondary" type="button" onClick={() => onPageChange(page - 1)}>
            ← Previous page
          </Button>
        ) : null}
        {page < pages.length - 1 ? (
          <Button variant="secondary" type="button" onClick={() => onPageChange(page + 1)}>
            Next page →
          </Button>
        ) : null}
        <Button type="button" className="flex items-center gap-2" onClick={onReview}>
          <Send size={16} aria-hidden />
          {reviewLabel}
        </Button>
        <Button
          variant="secondary"
          type="button"
          disabled={!onDownload}
          onClick={onDownload}
          title={onDownload ? undefined : "Available after independent approval"}
          className="flex items-center gap-2"
        >
          <Download size={16} aria-hidden />
          Download DOCX
        </Button>
      </div>
    </Card>
  );
}
