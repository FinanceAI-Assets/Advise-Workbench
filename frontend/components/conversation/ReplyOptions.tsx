import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

// Choices Sheldon offers inside a reply. The message metadata (`kind`) says which:
// a storyline approach to pick, a slide to agree or change, or the agreed structure to build.
// Picking one sends the same reply the user would otherwise type.

type Arc = { arc_key: string; name: string; reasoning: string; lp_evidence?: string; is_recommended?: boolean };
type Slide = {
  slide_num: number;
  title: string;
  slide_type: string;
  slide_type_label?: string;
  key_message: string;
  evidence_source?: string;
  sheldon_view?: string;
};
type OutlineSlide = { slide_num: number; title: string; key_message?: string };

export type ReplyHandlers = {
  /** Send a reply now. Absent on older messages, whose choices are shown but can no longer be picked. */
  onReply?: (text: string) => void;
  /** Put text in the message box for the user to finish. */
  onDraft?: (text: string) => void;
};

export function hasReplyOptions(metadata: Record<string, unknown> | undefined): boolean {
  const kind = metadata?.kind;
  return (
    (kind === "arc_proposal" && Array.isArray(metadata?.arcs)) ||
    (kind === "slide_proposal" && Boolean(metadata?.slide)) ||
    (kind === "structure_summary" && Array.isArray(metadata?.slides))
  );
}

export function ReplyOptions({ metadata, onReply, onDraft }: { metadata: Record<string, unknown> } & ReplyHandlers) {
  const closed = !onReply;

  if (metadata.kind === "arc_proposal") {
    return (
      <div className="mt-3 space-y-2">
        {(metadata.arcs as Arc[]).map((arc) => (
          <div
            key={arc.arc_key}
            className={cn(
              "rounded-lg border p-3",
              arc.is_recommended ? "border-[var(--accent-green)] bg-[#EFF6E6]" : "border-[var(--surface-border)] bg-white"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[var(--text-default)]">
                  {arc.name}
                  {arc.is_recommended ? (
                    <span className="ml-2 rounded bg-[var(--accent-green)] px-1.5 py-0.5 text-2xs font-medium text-white">
                      Recommended
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">{arc.reasoning}</p>
                {arc.lp_evidence ? (
                  <p className="mt-1 text-xs italic text-[var(--text-muted)]">Practice: {arc.lp_evidence}</p>
                ) : null}
              </div>
              <Button
                type="button"
                variant={arc.is_recommended ? "primary" : "secondary"}
                disabled={closed}
                className="shrink-0 px-3 py-1.5 text-xs"
                onClick={() => onReply?.(`I'd like to go with ${arc.arc_key}`)}
              >
                Use this
              </Button>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (metadata.kind === "slide_proposal") {
    const slide = metadata.slide as Slide;
    return (
      <div className="mt-3 rounded-lg border border-[var(--surface-border)] bg-white p-3">
        <p className="text-xs text-[var(--text-muted)]">
          <span className="mr-2 rounded bg-[var(--surface-muted)] px-2 py-0.5 font-semibold text-[var(--text-default)]">
            Slide {slide.slide_num}
          </span>
          {slide.slide_type_label || slide.slide_type}
        </p>
        <p className="mt-2 text-sm font-semibold text-[var(--text-default)]">{slide.title}</p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          <span className="font-medium">Key message:</span> {slide.key_message}
        </p>
        {slide.evidence_source ? (
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            <span className="font-medium">Evidence:</span> {slide.evidence_source}
          </p>
        ) : null}
        {slide.sheldon_view ? <p className="mt-1 text-xs italic text-[var(--text-muted)]">{slide.sheldon_view}</p> : null}
        <div className="mt-3 flex gap-2">
          <Button type="button" disabled={closed} className="px-3 py-1.5 text-xs" onClick={() => onReply?.("Agree")}>
            Agree
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={closed}
            className="px-3 py-1.5 text-xs"
            onClick={() => onDraft?.(`Modify slide ${slide.slide_num}: `)}
          >
            Modify
          </Button>
        </div>
      </div>
    );
  }

  const slides = metadata.slides as OutlineSlide[];
  return (
    <div className="mt-3 rounded-lg border border-[var(--accent-green)] bg-[#EFF6E6] p-3">
      <p className="text-sm font-semibold text-[var(--text-default)]">Agreed deck structure</p>
      <ol className="mt-2 space-y-1">
        {slides.map((slide, i) => (
          <li key={`${slide.slide_num}-${i}`} className="text-xs text-[var(--text-muted)]">
            <span className="font-semibold text-[var(--text-default)]">
              {slide.slide_num}. {slide.title}
            </span>
            {slide.key_message ? ` — ${slide.key_message}` : ""}
          </li>
        ))}
      </ol>
      <Button type="button" disabled={closed} className="mt-3 w-full justify-center text-sm" onClick={() => onReply?.("Build it")}>
        Build the deck
      </Button>
    </div>
  );
}
