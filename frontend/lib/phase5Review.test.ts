import { describe, expect, it } from "vitest";

import { buildDeckRejection } from "./phase5Review";

describe("buildDeckRejection", () => {
  it("regenerates the chosen slides and keeps the rest", () => {
    expect(buildDeckRejection(7, [4, 2, 2], " Improve design ")).toEqual({
      artifact_type: "pptx",
      rejected_slides: [2, 4],
      approved_slides: [1, 3, 5, 6, 7],
      user_feedback: "Improve design",
    });
  });

  it("regenerates the whole deck when no slide or every slide is chosen", () => {
    const none = buildDeckRejection(3, [], "");
    expect(none).toEqual({ artifact_type: "pptx", rejected_slides: null, approved_slides: null, user_feedback: undefined });
    expect(buildDeckRejection(3, [1, 2, 3], "").rejected_slides).toBeNull();
  });

  it("ignores slide numbers outside the deck", () => {
    expect(buildDeckRejection(3, [0, 2, 9], "").rejected_slides).toEqual([2]);
  });
});
