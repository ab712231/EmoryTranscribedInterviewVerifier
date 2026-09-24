import { describe, expect, it } from "vitest";
import { formatInterviewDate } from "./Interviews";

describe("formatInterviewDate", () => {
  it("renders an interview id as a date a person would say out loud", () => {

    const rendered = formatInterviewDate("2026-03-04");
    expect(rendered).toContain("2026");
    expect(rendered).toContain("March");
    expect(rendered).toContain("4");
  });

  it("reads the date as written rather than shifting it by a timezone", () => {

    expect(formatInterviewDate("2026-01-01")).toContain("2026");
    expect(formatInterviewDate("2026-01-01")).toContain("1");
    expect(formatInterviewDate("2026-01-01")).not.toContain("2025");
  });

  it("keeps the same-day suffix from changing the date shown", () => {

    expect(formatInterviewDate("2026-03-04-2")).toBe(formatInterviewDate("2026-03-04"));
  });

  it("falls back to the raw id rather than rendering Invalid Date", () => {
    expect(formatInterviewDate("not-a-date")).toBe("not-a-date");
    expect(formatInterviewDate("")).toBe("");
  });
});
