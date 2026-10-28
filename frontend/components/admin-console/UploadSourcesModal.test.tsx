// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UploadSourcesModal } from "./UploadSourcesModal";

vi.mock("@/hooks/useAdminConsole", () => ({
  useLibraryUpload: () => ({ isPending: false, error: null, mutateAsync: vi.fn() }),
}));

const file = (name: string, size = 1024) => new File([new Uint8Array(size)], name, { lastModified: 1 });

function pick(...files: File[]) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("file input not rendered");
  fireEvent.change(input, { target: { files } });
}

describe("UploadSourcesModal", () => {
  it("accepts PowerPoint and Excel alongside PDF and Word", () => {
    render(<UploadSourcesModal onClose={() => {}} onUploaded={() => {}} />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).toHaveAttribute("accept", ".pdf,.docx,.pptx,.xlsx,.md,.txt");
    expect(input).toHaveAttribute("multiple");
  });

  it("adds files across several picks, skips duplicates and lets each be removed", () => {
    render(<UploadSourcesModal onClose={() => {}} onUploaded={() => {}} />);
    pick(file("deck.pptx"), file("model.xlsx"));
    pick(file("guide.pdf"), file("deck.pptx"));
    const list = screen.getByRole("list", { name: "Selected source files" });
    expect(list.querySelectorAll("li")).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: "Remove model.xlsx" }));
    expect(screen.queryByText("model.xlsx")).not.toBeInTheDocument();
    expect(screen.getByText("deck.pptx")).toBeInTheDocument();
  });

  it("takes several files dropped onto the box and counts them against the limit", () => {
    render(<UploadSourcesModal onClose={() => {}} onUploaded={() => {}} />);
    const dropZone = screen.getByText(/Drag and drop files here/).closest("[role=presentation]");
    if (!dropZone) throw new Error("drop zone not rendered");
    fireEvent.drop(dropZone, { dataTransfer: { files: [file("a.docx"), file("b.pptx"), file("c.xlsx")] } });
    expect(screen.getByText("3 of 10 files selected · extraction and validation start on upload")).toBeInTheDocument();
    expect(screen.getByText("c.xlsx")).toBeInTheDocument();
  });

  it("explains how to fix older Office formats instead of uploading them", () => {
    render(<UploadSourcesModal onClose={() => {}} onUploaded={() => {}} />);
    pick(file("legacy.ppt"));
    expect(screen.getByRole("alert")).toHaveTextContent("Save it as .pptx");
    expect(screen.queryByRole("list", { name: "Selected source files" })).not.toBeInTheDocument();
  });
});
