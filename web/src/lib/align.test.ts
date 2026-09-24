import { describe, expect, it } from "vitest";
import { alignDraft } from "./align";

const A = "The patient reported difficulty sleeping.";
const B = "They described low mood over the past two weeks.";
const C = "No changes to medication were discussed.";

describe("alignDraft", () => {
  it("marks nothing as changed when the draft equals the original", () => {
    const proposed = [A, B, C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments).toHaveLength(3);
    expect(segments.every((segment) => !segment.changed)).toBe(true);
    expect(segments.map((segment) => segment.after)).toEqual([A, B, C]);
  });

  it("finds a single rewritten sentence between two unchanged ones", () => {
    const rewritten = "They described anxiety over the past three weeks.";
    const proposed = [A, rewritten, C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments.map((segment) => segment.changed)).toEqual([false, true, false]);
    expect(segments[1]).toMatchObject({ indices: [1], before: B, after: rewritten });
  });

  it("finds a rewrite in the first position", () => {
    const rewritten = "The patient reported sleeping well.";
    const proposed = [rewritten, B, C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments[0]).toMatchObject({ indices: [0], after: rewritten, changed: true });
    expect(segments[1]?.changed).toBe(false);
  });

  it("finds a rewrite in the last position", () => {
    const rewritten = "A medication change was discussed.";
    const proposed = [A, B, rewritten].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments[2]).toMatchObject({ indices: [2], after: rewritten, changed: true });
  });

  it("reports consecutive rewrites as one block rather than guessing the boundary", () => {
    const proposed = [A, "They described anxiety. It lasted three weeks."].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments).toHaveLength(2);
    expect(segments[1]).toMatchObject({
      indices: [1, 2],
      before: `${B} ${C}`,
      changed: true,
    });
    expect(segments[1]?.after).toBe("They described anxiety. It lasted three weeks.");
  });

  it("treats a statement the model declined to rewrite as unchanged", () => {

    const proposed = [A, B, C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments.filter((segment) => segment.changed)).toHaveLength(0);
  });

  it("reassembles to exactly the proposed text", () => {
    const rewritten = "They described anxiety over the past three weeks.";
    const proposed = [A, rewritten, C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments.map((segment) => segment.after).join(" ")).toBe(proposed);
  });

  it("preserves every statement index exactly once", () => {
    const proposed = [A, "Something else entirely.", C].join(" ");

    const segments = alignDraft([A, B, C], proposed);

    expect(segments.flatMap((segment) => segment.indices)).toEqual([0, 1, 2]);
  });

  it("handles a single statement", () => {
    expect(alignDraft([A], A)).toEqual([
      { indices: [0], before: A, after: A, changed: false },
    ]);
  });

  it("handles an empty statement list", () => {
    expect(alignDraft([], "")).toEqual([]);
  });

  it("does not mistake a repeated sentence for a rewrite", () => {
    const proposed = [A, A].join(" ");

    const segments = alignDraft([A, A], proposed);

    expect(segments.every((segment) => !segment.changed)).toBe(true);
  });

  it("reports a removed middle sentence as a change with nothing after it", () => {
    const segments = alignDraft([A, B, C], [A, C].join(" "));

    expect(segments.map((segment) => segment.changed)).toEqual([false, true, false]);
    expect(segments[1]).toMatchObject({ indices: [1], before: B, after: "" });
  });
});
