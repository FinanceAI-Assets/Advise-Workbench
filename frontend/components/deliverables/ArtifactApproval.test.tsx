// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ArtifactDesignReview } from "@/hooks/usePhase5Review";

import { ArtifactApproval } from "./ArtifactApproval";

const design = (over: Partial<ArtifactDesignReview> = {}): ArtifactDesignReview => ({
  artifactType: "docx",
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

const button = (name: string) => screen.getAllByRole("button", { name }).at(-1)!;

describe("ArtifactApproval", () => {
  it("approves after confirmation", async () => {
    const d = design();
    render(<ArtifactApproval label="Document" design={d} />);
    fireEvent.click(button("Approve"));
    expect(screen.getByRole("alertdialog", { name: "Approve the document?" })).toBeInTheDocument();
    fireEvent.click(button("Approve"));
    await waitFor(() => expect(d.approve).toHaveBeenCalledOnce());
  });

  it("rejects the whole artifact with the feedback", async () => {
    const d = design();
    render(<ArtifactApproval label="Document" design={d} />);
    fireEvent.click(button("Reject"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Shorter summary" } });
    fireEvent.click(button("Reject"));
    await waitFor(() => expect(d.reject).toHaveBeenCalledWith(null, "Shorter summary"));
  });

  it("offers nothing to decide when the run has no review, or is regenerating", () => {
    const { rerender } = render(<ArtifactApproval label="Document" design={null} />);
    expect(button("Approve")).toBeDisabled();
    expect(screen.getByText(/no design review/)).toBeInTheDocument();
    rerender(<ArtifactApproval label="Document" design={design({ regenerating: true, version: "v2" })} />);
    expect(button("Approve")).toBeDisabled();
    expect(button("Reject")).toBeDisabled();
  });

  it("at the rejection limit only approval is possible", () => {
    render(<ArtifactApproval label="Document" design={design({ rejectBlocked: "Rejection limit reached" })} />);
    expect(button("Approve")).toBeEnabled();
    expect(button("Reject")).toBeDisabled();
  });
});
