// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RegeneratingNotice } from "./RegeneratingNotice";

describe("RegeneratingNotice", () => {
  it("names the slides being rebuilt and how many are kept", () => {
    render(<RegeneratingNotice label="deck" version="v2" rebuildingSlides={[3, 4]} totalSlides={9} />);
    expect(screen.getByRole("status")).toHaveTextContent("Regenerating the deck as v2");
    expect(screen.getByText(/Rebuilding slides 3, 4; the other 7 stay as they are/)).toBeInTheDocument();
  });

  it("says the whole artifact is rebuilt when no slides are named", () => {
    render(<RegeneratingNotice label="document" version="v3" />);
    expect(screen.getByText(/Rebuilding the whole document with your feedback/)).toBeInTheDocument();
  });
});
