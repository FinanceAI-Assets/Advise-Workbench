// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { SlideDecision } from "@/hooks/useDeliverables";
import type { DeckDesignReview } from "@/hooks/usePhase5Review";

import { DeckDecisionButtons, type SlideReview, SlideReviewBar } from "./SlideDecision";

const SLIDES = [1, 2, 3].map((index) => ({ id: `s${index}`, index, title: `Slide ${index}` }));

/** Real decision state, so a click's effect shows up on the next render. */
function Harness({
  initial = {} as Record<number, SlideDecision>,
  onSelect = vi.fn(),
  designReview = null as DeckDesignReview | null,
}) {
  const [decisions, setDecisions] = useState(initial);
  const [index, setIndex] = useState(0);
  const decideAll = (numbers: number[], decision: SlideDecision | null) =>
    setDecisions((prev) => {
      const next = { ...prev };
      for (const n of numbers) {
        if (decision) next[n] = decision;
        else delete next[n];
      }
      return next;
    });
  const review: SlideReview = {
    decisionOf: (n) => decisions[n],
    onDecide: (n, d) => decideAll([n], d),
    onDecideAll: decideAll,
    locked: false,
    designReview,
  };
  return (
    <>
      <p data-testid="at">slide {index + 1}</p>
      <SlideReviewBar
        index={index}
        total={SLIDES.length}
        onSelect={(i) => {
          onSelect(i);
          setIndex(i);
        }}
        review={review}
      />
      <DeckDecisionButtons slides={SLIDES} review={review} />
    </>
  );
}

const deckButton = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}$`) });

describe("SlideReviewBar", () => {
  it("accepting a slide moves on to the next one", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Accept slide and go to the next one" }));
    expect(screen.getByTestId("at")).toHaveTextContent("slide 2");
    expect(screen.getByText(/1 accepted · 0 rejected/)).toBeInTheDocument();
  });

  it("rejecting a slide stays on it", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Reject slide" }));
    expect(screen.getByTestId("at")).toHaveTextContent("slide 1");
  });

  it("the arrows move between slides and stop at the ends", () => {
    render(<Harness />);
    expect(screen.getByRole("button", { name: "Previous slide" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next slide" }));
    fireEvent.click(screen.getByRole("button", { name: "Next slide" }));
    expect(screen.getByTestId("at")).toHaveTextContent("slide 3");
    expect(screen.getByRole("button", { name: "Next slide" })).toBeDisabled();
  });
});

describe("DeckDecisionButtons", () => {
  it("a rejected slide leaves only Reject PPT available", () => {
    render(<Harness initial={{ 2: "rejected" }} />);
    expect(deckButton("Accept PPT")).toBeDisabled();
    expect(deckButton("Reject PPT")).toBeEnabled();
  });

  it("asks for confirmation before applying, and Cancel changes nothing", () => {
    render(<Harness />);
    fireEvent.click(deckButton("Reject PPT"));
    expect(screen.getByRole("alertdialog", { name: "Reject the whole deck?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByText(/0 accepted · 0 rejected · 3 undecided/)).toBeInTheDocument();

    fireEvent.click(deckButton("Accept PPT"));
    fireEvent.click(screen.getAllByRole("button", { name: "Accept PPT" }).at(-1)!);
    expect(screen.getByText(/3 accepted · 0 rejected/)).toBeInTheDocument();
  });
});

const waitingReview = (over: Partial<DeckDesignReview> = {}): DeckDesignReview => ({
  artifactType: "pptx",
  waiting: true,
  regenerating: false,
  rebuildingSlides: [],
  approved: false,
  version: "v1",
  rejectBlocked: null,
  busy: false,
  error: null,
  approve: vi.fn().mockResolvedValue({}),
  reject: vi.fn().mockResolvedValue({}),
  ...over,
});

describe("DeckDecisionButtons in design review", () => {
  it("Accept PPT approves the run after confirmation", async () => {
    const design = waitingReview();
    render(<Harness designReview={design} />);
    fireEvent.click(deckButton("Accept PPT"));
    expect(screen.getByRole("alertdialog", { name: "Approve the deck?" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Accept PPT" }).at(-1)!);
    await waitFor(() => expect(screen.getByText(/3 accepted/)).toBeInTheDocument());
    expect(design.approve).toHaveBeenCalledOnce();
  });

  it("Reject PPT sends back only the rejected slides, with the feedback", async () => {
    const design = waitingReview();
    render(<Harness initial={{ 1: "accepted", 2: "rejected" }} designReview={design} />);
    fireEvent.click(deckButton("Reject PPT"));
    expect(screen.getByText(/Slides 2 will be regenerated; the other 2 are kept/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Bolder chart" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Reject PPT" }).at(-1)!);
    await waitFor(() => expect(design.reject).toHaveBeenCalledWith([2], "Bolder chart"));
    // The rebuilt slide's old decision is cleared; the accepted one stays.
    await waitFor(() => expect(screen.getByText(/1 accepted · 0 rejected/)).toBeInTheDocument());
  });

  it("with no slide rejected, Reject PPT rebuilds the whole deck", async () => {
    const design = waitingReview();
    render(<Harness designReview={design} />);
    fireEvent.click(deckButton("Reject PPT"));
    expect(screen.getByText(/The whole deck \(3 slides\) will be regenerated/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Reject PPT" }).at(-1)!);
    await waitFor(() => expect(design.reject).toHaveBeenCalledWith(null, ""));
  });

  it("both buttons wait while the deck is regenerating", () => {
    render(<Harness designReview={waitingReview({ regenerating: true, version: "v2" })} />);
    expect(deckButton("Accept PPT")).toBeDisabled();
    expect(deckButton("Reject PPT")).toBeDisabled();
  });

  it("a failed request leaves the decisions unchanged", async () => {
    const design = waitingReview({ approve: vi.fn().mockRejectedValue(new Error("409")) });
    render(<Harness designReview={design} />);
    fireEvent.click(deckButton("Accept PPT"));
    fireEvent.click(screen.getAllByRole("button", { name: "Accept PPT" }).at(-1)!);
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.getByText(/0 accepted · 0 rejected · 3 undecided/)).toBeInTheDocument();
  });
});
