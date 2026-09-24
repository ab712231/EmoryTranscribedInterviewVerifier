import { useId } from "react";
import type { Verdict } from "../lib/api";
import { CheckIcon, CrossIcon, QuestionIcon } from "./Icon";
import { TextArea } from "./ui";
import "./statement.css";

const OPTIONS: { value: Verdict; label: string; className: string }[] = [
  { value: "correct", label: "Yes, that's right", className: "choice--correct" },
  { value: "incorrect", label: "No, that's not right", className: "choice--incorrect" },
  { value: "unsure", label: "I'm not sure", className: "choice--unsure" },
];

const MARKERS: Record<Verdict, { label: string; className: string; Icon: typeof CheckIcon }> = {
  correct: { label: "Marked right", className: "statement__marker--correct", Icon: CheckIcon },
  incorrect: { label: "Marked not right", className: "statement__marker--incorrect", Icon: CrossIcon },
  unsure: { label: "Not sure", className: "statement__marker--unsure", Icon: QuestionIcon },
};

export interface StatementItemProps {
  index: number;
  total: number;
  text: string;
  verdict: Verdict | null;
  note: string;
  disabled?: boolean;
  onVerdictChange: (verdict: Verdict) => void;
  onNoteChange: (note: string) => void;
}

export function StatementItem({
  index,
  total,
  text,
  verdict,
  note,
  disabled = false,
  onVerdictChange,
  onNoteChange,
}: StatementItemProps) {
  const groupName = useId();
  const answered = verdict !== null;
  const marker = verdict ? MARKERS[verdict] : null;

  return (
    <li className="statement" data-answered={answered}>
      <div className="statement__head">
        <p className="statement__index">
          Statement <span data-numeric>{index + 1}</span> of{" "}
          <span data-numeric>{total}</span>
        </p>
        {marker ? (
          <p className={`statement__marker ${marker.className}`}>
            <marker.Icon size={16} />
            {marker.label}
          </p>
        ) : (
          <p className="statement__marker">Not answered yet</p>
        )}
      </div>

      <fieldset className="choices">
        <legend className="visuallyHidden">
          Is this right? {text}
        </legend>

        <p className="statement__text">{text}</p>

        <p className="choices__legend" aria-hidden="true">
          Is this right?
        </p>

        <div className="choices__options">
          {OPTIONS.map((option) => (
            <label key={option.value} className={`choice ${option.className}`}>
              <input
                className="choice__input"
                type="radio"
                name={groupName}
                value={option.value}
                checked={verdict === option.value}
                disabled={disabled}
                onChange={() => onVerdictChange(option.value)}
              />
              <span className="choice__label">{option.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="note" data-open={verdict === "incorrect"}>
        <div className="note__inner">
          <div className="note__spacer">
            <TextArea
              label="What should it say instead?"
              hint="Tell us in your own words. It doesn't need to be perfect. We just need to know what was wrong."
              value={note}
              disabled={disabled}
              maxLength={2000}
              onChange={(event) => onNoteChange(event.target.value)}
            />
          </div>
        </div>
      </div>
    </li>
  );
}
