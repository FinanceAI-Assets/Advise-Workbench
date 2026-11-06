// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourceUploadForm, type UploadTarget } from "./SourceUploadForm";

const mutateAsync = vi.fn();
vi.mock("@/hooks/useAdminConsole", () => ({
  useLibraryUpload: () => ({ isPending: false, error: null, mutateAsync }),
}));

const file = (name: string, size = 1024) => new File([new Uint8Array(size)], name, { lastModified: 1 });
const sources: UploadTarget = { kind: "source", practiceId: "lp-041", owner: "Maya Patel", classification: "Internal methods content", rights: "Advisory Methods" };
const version: UploadTarget = {
  kind: "version",
  practiceId: "lp-041",
  sourceId: "SRC-1",
  sourceName: "playbook.docx",
  owner: "Maya Patel",
  classification: "Confidential",
  rights: "Advisory Methods",
};

function pick(...files: File[]) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("file input not rendered");
  fireEvent.change(input, { target: { files } });
}

describe("SourceUploadForm", () => {
  beforeEach(() => mutateAsync.mockReset().mockResolvedValue({ jobs: [] }));

  it("accepts PowerPoint and Excel alongside PDF and Word, one file at a time by default", () => {
    render(<SourceUploadForm target={sources} onUploaded={() => {}} />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).toHaveAttribute("accept", ".pdf,.docx,.pptx,.xlsx,.md,.txt");
    expect(input).not.toHaveAttribute("multiple");
  });

  it("adds files across several picks when several are allowed, skips duplicates and lets each be removed", () => {
    render(<SourceUploadForm target={sources} maxFiles={10} onUploaded={() => {}} />);
    pick(file("deck.pptx"), file("model.xlsx"));
    pick(file("guide.pdf"), file("deck.pptx"));
    expect(screen.getByRole("list", { name: "Selected source files" }).querySelectorAll("li")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Remove model.xlsx" }));
    expect(screen.queryByText("model.xlsx")).not.toBeInTheDocument();
  });

  it("explains how to fix older Office formats instead of uploading them", () => {
    render(<SourceUploadForm target={sources} onUploaded={() => {}} />);
    pick(file("legacy.ppt"));
    expect(screen.getByRole("alert")).toHaveTextContent("Save it as .pptx");
    expect(screen.queryByRole("list", { name: "Selected source files" })).not.toBeInTheDocument();
  });

  it("adds several files to a practice as new sources", async () => {
    render(<SourceUploadForm target={sources} maxFiles={10} onUploaded={() => {}} />);
    pick(file("playbook.docx"), file("checklist.xlsx"));
    fireEvent.click(screen.getByRole("button", { name: "Upload and start extraction" }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    const form = mutateAsync.mock.calls[0][0] as FormData;
    expect(form.getAll("files")).toHaveLength(2);
    expect([form.get("practice_id"), form.get("source_id"), form.get("owner")]).toEqual(["lp-041", "new", "Maya Patel"]);
    expect(form.get("title")).toBeNull();
  });

  it("sends a new version to its practice and source with the practice's owner and rights", async () => {
    render(<SourceUploadForm target={version} onUploaded={() => {}} />);
    expect(screen.getByRole("heading", { name: "New version of playbook.docx" })).toBeInTheDocument();
    pick(file("playbook-v2.docx"));
    fireEvent.click(screen.getByRole("button", { name: "Upload and start extraction" }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    const form = mutateAsync.mock.calls[0][0] as FormData;
    expect([form.get("practice_id"), form.get("source_id"), form.get("classification"), form.get("rights")]).toEqual([
      "lp-041",
      "SRC-1",
      "Confidential",
      "Advisory Methods",
    ]);
    expect(form.get("title")).toBeNull();
  });
});
