import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { StatementItem } from "../components/StatementItem";
import { Button, Callout, Loading } from "../components/ui";
import { CheckIcon } from "../components/Icon";
import {
  ApiError,
  loadSession,
  prepareDraft,
  recordVerdicts,
  type Statement,
  type Verdict,
} from "../lib/api";
import { useIdToken, useSession } from "../lib/session";

const SAVE_DELAY = 900;

type SaveState = "idle" | "saving" | "saved" | "failed";

export function Review() {

  const { interviewId = "" } = useParams();
  const idToken = useIdToken();
  const { signOut } = useSession();
  const navigate = useNavigate();

  const [statements, setStatements] = useState<Statement[]>();
  const [patientId, setPatientId] = useState<string>();
  const [loadError, setLoadError] = useState<ApiError>();

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [draftError, setDraftError] = useState<string>();
  const [preparing, setPreparing] = useState(false);
  const [showIncomplete, setShowIncomplete] = useState(false);

  const dirty = useRef<Set<number>>(new Set());
  const timer = useRef<number>();
  const latest = useRef<Statement[]>([]);

  useEffect(() => {
    latest.current = statements ?? [];
  }, [statements]);

  useEffect(() => {
    let cancelled = false;
    loadSession(idToken, interviewId)
      .then((session) => {
        if (cancelled) return;
        if (session.locked) {
          navigate(`/done/${interviewId}`, { replace: true });
          return;
        }
        setStatements(session.statements);
        setPatientId(session.patientId);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const error = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
        if (error.isAuthFailure) signOut();
        setLoadError(error);
      });
    return () => {
      cancelled = true;
    };
  }, [idToken, navigate, signOut]);

  const flush = useCallback(async (): Promise<boolean> => {
    if (dirty.current.size === 0) return true;

    const pending = [...dirty.current];

    const payload = [];
    for (const index of pending) {
      const statement = latest.current.find((entry) => entry.index === index);
      if (!statement || statement.verdict === null) {
        continue;
      }
      payload.push({
        index: statement.index,
        verdict: statement.verdict as Verdict,
        note: statement.note,
      });
    }

    if (payload.length === 0) return true;

    setSaveState("saving");
    try {
      await recordVerdicts(idToken, interviewId, payload);
      payload.forEach((entry) => dirty.current.delete(entry.index));
      setSaveState("saved");
      return true;
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError(0, "Save failed.");
      if (error.isAuthFailure) signOut();
      if (error.isConflict) {
        navigate(`/done/${interviewId}`, { replace: true });
        return false;
      }
      setSaveState("failed");
      return false;
    }
  }, [idToken, navigate, signOut]);

  const scheduleSave = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), SAVE_DELAY);
  }, [flush]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function update(index: number, patch: Partial<Statement>) {
    setStatements((current) =>
      current?.map((statement) =>
        statement.index === index ? { ...statement, ...patch } : statement
      )
    );
    dirty.current.add(index);
    setSaveState("idle");
    scheduleSave();
  }

  async function onContinue() {
    setDraftError(undefined);
    const remaining = (statements ?? []).filter((statement) => statement.verdict === null);
    if (remaining.length > 0) {
      setShowIncomplete(true);
      const first = document.querySelector<HTMLElement>(
        `[data-answered="false"] input[type="radio"]`
      );
      first?.focus();
      first?.closest(".statement")?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }

    setPreparing(true);
    window.clearTimeout(timer.current);
    const saved = await flush();
    if (!saved) {
      setPreparing(false);
      setDraftError("We could not save your last answer. Check your connection and try again.");
      return;
    }

    try {
      await prepareDraft(idToken, interviewId);
      navigate(`/draft/${interviewId}`);
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
      if (error.isAuthFailure) signOut();
      setPreparing(false);
      setDraftError(
        error.retryable
          ? "We could not prepare your corrected version just now. Your answers are saved. Please try again."
          : error.message
      );
    }
  }

  if (loadError) {
    return (
      <AppLayout documentTitle="Check your summary">
        <div className="panel">
          <h1 className="page__title">We could not load your summary</h1>
          <p className="page__lede">{loadError.message}</p>
          <Button onClick={() => window.location.reload()}>Try again</Button>
        </div>
      </AppLayout>
    );
  }

  if (!statements) {
    return (
      <AppLayout documentTitle="Check your summary">
        <Loading label="Loading your summary…" />
      </AppLayout>
    );
  }

  const answered = statements.filter((statement) => statement.verdict !== null).length;
  const total = statements.length;
  const remaining = total - answered;
  const complete = remaining === 0 && total > 0;

  return (
    <AppLayout patientId={patientId} documentTitle="Check your summary">
      <p className="page__step">Step 2 of 3</p>
      <h1 className="page__title">Check each statement</h1>
      <p className="page__lede">
        Tell us whether each sentence is right. If something is wrong, say what
        it should say instead. You can stop and come back. Your answers are
        saved as you go.
      </p>

      <div className="progress">
        <p className="progress__count">
          <span data-numeric>{answered}</span> of <span data-numeric>{total}</span>{" "}
          answered
        </p>
        <div
          className="progress__track"
          role="progressbar"
          aria-valuenow={answered}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-label="Statements answered"
        >
          <div
            className="progress__fill"
            style={{ transform: `scaleX(${total ? answered / total : 0})` }}
          />
        </div>
        <p className="progress__remaining" role="status">
          {saveState === "saving"
            ? "Saving…"
            : saveState === "failed"
              ? "Not saved, trying again"
              : saveState === "saved"
                ? "Saved"
                : complete
                  ? "All answered"
                  : `${remaining} left`}
        </p>
      </div>

      {showIncomplete && !complete ? (
        <div style={{ marginBottom: "var(--s5)" }}>
          <Callout tone="error" title="Some statements still need an answer" role="alert">
            <p>
              Please answer all <strong data-numeric>{total}</strong> statements
              before continuing. We have taken you to the first one still open.
            </p>
          </Callout>
        </div>
      ) : null}

      {saveState === "failed" ? (
        <div style={{ marginBottom: "var(--s5)" }}>
          <Callout tone="error" title="Your last answer did not save" role="alert">
            <p>
              Check your connection. Nothing you have already saved is lost.
            </p>
          </Callout>
        </div>
      ) : null}

      <ol className="statements">
        {statements.map((statement) => (
          <StatementItem
            key={statement.index}
            index={statement.index}
            total={total}
            text={statement.text}
            verdict={statement.verdict}
            note={statement.note}
            onVerdictChange={(verdict) => update(statement.index, { verdict })}
            onNoteChange={(note) => update(statement.index, { note })}
          />
        ))}
      </ol>

      {draftError ? (
        <div style={{ marginTop: "var(--s5)" }}>
          <Callout tone="error" title="We could not continue" role="alert">
            <p>{draftError}</p>
          </Callout>
        </div>
      ) : null}

      <div className="actions">
        <Button onClick={onContinue} busy={preparing} busyLabel="Preparing…">
          {complete ? "See the corrected version" : "Continue"}
        </Button>
        {complete ? (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--s2)",
              color: "var(--ok)",
              fontSize: "var(--size-sm)",
              fontWeight: 600,
            }}
          >
            <CheckIcon size={18} />
            Everything answered
          </span>
        ) : null}
      </div>
    </AppLayout>
  );
}
