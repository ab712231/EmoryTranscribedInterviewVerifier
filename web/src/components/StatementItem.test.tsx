import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { StatementItem } from "./StatementItem";

const TEXT = "They reported occasional difficulty recalling recent conversations.";

function setup(overrides: Partial<Parameters<typeof StatementItem>[0]> = {}) {
  const onVerdictChange = vi.fn();
  const onNoteChange = vi.fn();
  render(
    <ul>
      <StatementItem
        index={1}
        total={6}
        text={TEXT}
        verdict={null}
        note=""
        onVerdictChange={onVerdictChange}
        onNoteChange={onNoteChange}
        {...overrides}
      />
    </ul>
  );
  return { onVerdictChange, onNoteChange };
}

describe("StatementItem", () => {
  it("offers the three answers in plain language, not the study's vocabulary", () => {
    setup();

    expect(screen.getByRole("radio", { name: "Yes, that's right" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "No, that's not right" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "I'm not sure" })).toBeInTheDocument();

    expect(screen.queryByText(/incorrect/i)).not.toBeInTheDocument();
  });

  it("groups the answers so assistive technology reads the sentence as the question", () => {
    setup();

    expect(screen.getByRole("group", { name: `Is this right? ${TEXT}` })).toBeInTheDocument();
  });

  it("shows the statement's position in the set", () => {
    setup();

    expect(screen.getByText(/Statement/)).toHaveTextContent("Statement 2 of 6");
  });

  it("reports an unanswered statement as unanswered rather than leaving it blank", () => {
    setup();

    expect(screen.getByText("Not answered yet")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveAttribute("data-answered", "false");
  });

  it("marks an answered statement as settled", () => {
    setup({ verdict: "correct" });

    expect(screen.getByText("Marked right")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveAttribute("data-answered", "true");
  });

  it("reflects the recorded verdict in the radio group", () => {
    setup({ verdict: "unsure" });

    expect(screen.getByRole("radio", { name: "I'm not sure" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Yes, that's right" })).not.toBeChecked();
  });

  it("reports the verdict when an answer is chosen", async () => {
    const user = userEvent.setup();
    const { onVerdictChange } = setup();

    await user.click(screen.getByRole("radio", { name: "No, that's not right" }));

    expect(onVerdictChange).toHaveBeenCalledWith("incorrect");
  });

  it("keeps the note closed until the participant says something is wrong", () => {
    setup({ verdict: "correct" });

    expect(screen.getByText("What should it say instead?").closest(".note")).toHaveAttribute(
      "data-open",
      "false"
    );
  });

  it("opens the note when a statement is marked not right", () => {
    setup({ verdict: "incorrect" });

    expect(screen.getByText("What should it say instead?").closest(".note")).toHaveAttribute(
      "data-open",
      "true"
    );
  });

  it("shows the participant's note back to them exactly as typed", () => {
    const note = "  It was TWO years -- not six months.  ";
    setup({ verdict: "incorrect", note });

    expect(screen.getByLabelText(/What should it say instead/)).toHaveValue(note);
  });

  it("reports note changes verbatim, without trimming", async () => {

    function Harness() {
      const [note, setNote] = useState("");
      return (
        <ul>
          <StatementItem
            index={0}
            total={1}
            text={TEXT}
            verdict="incorrect"
            note={note}
            onVerdictChange={() => {}}
            onNoteChange={setNote}
          />
        </ul>
      );
    }

    const user = userEvent.setup();
    render(<Harness />);
    const field = screen.getByLabelText(/What should it say instead/);

    await user.type(field, "no  IT WAS two years. ");

    expect(field).toHaveValue("no  IT WAS two years. ");
  });

  it("tells the participant the note does not need to be perfect", () => {
    setup({ verdict: "incorrect" });

    expect(screen.getByText(/doesn't need to be perfect/i)).toBeInTheDocument();
  });

  it("locks every control on a submitted record", () => {
    setup({ verdict: "correct", disabled: true });

    screen.getAllByRole("radio").forEach((radio) => expect(radio).toBeDisabled());
    expect(screen.getByLabelText(/What should it say instead/)).toBeDisabled();
  });

  it("renders the statement text itself, verbatim", () => {
    setup();

    expect(screen.getByText(TEXT)).toBeInTheDocument();
  });
});
