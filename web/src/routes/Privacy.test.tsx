import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Privacy } from "./Privacy";

function renderPage() {
  render(
    <MemoryRouter>
      <Privacy />
    </MemoryRouter>
  );
}

describe("Privacy notice", () => {
  it("gives every section a heading a participant can scan for", () => {
    renderPage();
    const headings = screen.getAllByRole("heading", { level: 2 });
    const text = headings.map((heading) => heading.textContent);

    expect(text).toEqual([
      "What this site holds about you",
      "What this site does not do",
      "Who can see your answers",
      "How the corrected wording is made",
      "How your information is protected",
      "How long it is kept",
      "Your choices",
      "Questions",
    ]);
  });

  it("has exactly one first-level heading", () => {
    renderPage();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("does not list a date of birth among the things it holds", () => {

    renderPage();
    const heading = screen.getByRole("heading", {
      name: "What this site holds about you",
      level: 2,
    });
    const section = heading.closest("section");
    expect(section?.textContent ?? "").not.toMatch(/date of birth|study PIN/i);
  });

  it("says plainly that no date of birth is collected", () => {
    renderPage();
    expect(screen.getByText(/does not ask for or keep your date of birth/i)).toBeInTheDocument();
  });

  it("describes the emailed code and that it is single-use", () => {
    renderPage();
    expect(screen.getByText(/code we email you at that moment/i)).toBeInTheDocument();
    expect(screen.getByText(/works once and only for a few minutes/i)).toBeInTheDocument();
  });

  it("says which data is sent to the AI and which is not", () => {

    renderPage();
    expect(
      screen.getByText(/single sentence you flagged and the note you wrote/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/are not sent/i)).toBeInTheDocument();
  });

  it("tells participants nothing is recorded before they approve it", () => {
    renderPage();
    expect(screen.getByText(/Nothing is recorded until you read/i)).toBeInTheDocument();
  });

  it("offers a way back to sign in", () => {
    renderPage();
    expect(screen.getByRole("link", { name: /back to sign in/i })).toHaveAttribute(
      "href",
      "/"
    );
  });

  it("does not name a participant, because it is served signed-out", () => {

    renderPage();
    expect(screen.queryByText(/^Participant/)).not.toBeInTheDocument();
  });
});
