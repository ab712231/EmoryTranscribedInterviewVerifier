import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { Button, Callout, Loading } from "../components/ui";
import {
  ApiError,
  loadSession,
  prepareDraft,
  submitDecision,
  type DraftResult,
  type Statement,
} from "../lib/api";
import { alignDraft } from "../lib/align";
import { useIdToken, useSession } from "../lib/session";

export function Draft() {

  const { interviewId = "" } = useParams();
  const idToken = useIdToken();
  const { signOut } = useSession();
  const navigate = useNavigate();

  const [draft, setDraft] = useState<DraftResult>();
  const [statements, setStatements] = useState<Statement[]>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([loadSession(idToken, interviewId), prepareDraft(idToken, interviewId)])
      .then(([session, draftResult]) => {
        if (cancelled) return;
        if (session.locked) {
          navigate(`/done/${interviewId}`, { replace: true });
          return;
        }
        setStatements(session.statements);
        setDraft(draftResult);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const apiError = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
        if (apiError.isAuthFailure) signOut();
        if (apiError.isConflict) {
          navigate(`/review/${interviewId}`, { replace: true });
          return;
        }
        setError(
          apiError.retryable
            ? "We could not prepare your corrected version. Your answers are saved. Please try again."
            : apiError.message
        );
      });

    return () => {
      cancelled = true;
    };
  }, [idToken, navigate, signOut]);

  const segments = useMemo(() => {
    if (!draft || !statements) return [];
    return alignDraft(
      statements.map((statement) => statement.text),
      draft.proposed
    );
  }, [draft, statements]);

  async function decide(decision: "approve" | "reject") {
    setError(undefined);
    setBusy(decision);
    try {
      await submitDecision(idToken, interviewId, decision);
      navigate(decision === "approve" ? "/done" : "/review", { replace: true });
    } catch (caught) {
      const apiError = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
      if (apiError.isAuthFailure) signOut();
      if (apiError.isConflict) {
        navigate(`/done/${interviewId}`, { replace: true });
        return;
      }
      setBusy(null);
      setError(apiError.message);
    }
  }

  if (error && !draft) {
    return (
      <AppLayout documentTitle="Corrected version">
        <div className="panel">
          <h1 className="page__title">We could not prepare your corrected version</h1>
          <p className="page__lede">{error}</p>
          <div className="actions">
            <Button onClick={() => window.location.reload()}>Try again</Button>
            <Button variant="secondary" onClick={() => navigate(`/review/${interviewId}`)}>
              Back to my answers
            </Button>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (!draft || !statements) {
    return (
      <AppLayout documentTitle="Corrected version">
        <Loading label="Preparing your corrected version…" />
      </AppLayout>
    );
  }

  const changes = segments.filter((segment) => segment.changed);
  const kept = statements.filter((statement) =>
    (draft.notApplied ?? []).includes(statement.index)
  );

  const noteFor = (indices: number[]): string => {
    const notes: string[] = [];
    for (const index of indices) {
      const statement = statements.find((entry) => entry.index === index);
      const note = statement?.note.trim();
      if (note) {
        notes.push(note);
      }
    }
    return notes.join(" ");
  };

  return (
    <AppLayout patientId={draft.patientId} documentTitle="Corrected version">
      <p className="page__step">Step 3 of 3</p>
      <h1 className="page__title">Check the corrected version</h1>
      <p className="page__lede">
        {changes.length === 0 && kept.length > 0 ? (
          <>
            We could not make the corrections you asked for, so the summary is
            exactly as it was written. There is more about this below.
          </>
        ) : changes.length === 0 ? (
          <>
            You told us everything was right, so nothing has been changed. This
            is the summary exactly as it was written.
          </>
        ) : (
          <>
            We changed{" "}
            <strong data-numeric>{changes.length}</strong>{" "}
            {changes.length === 1 ? "sentence" : "sentences"} based on what you
            told us. Everything else is word for word as it was. Read it through.
            Nothing is recorded until you approve it.
          </>
        )}
      </p>

      <div className="panel">
        <p className="change__label">Your corrected summary</p>
        <p className="draft__body">
          {segments
            .filter((segment) => segment.after !== "")
            .map((segment, position, shown) => (
              <span
                key={position}
                className={`draft__sentence${segment.changed ? " draft__sentence--changed" : ""}`}
              >
                {segment.after}
                {position < shown.length - 1 ? " " : ""}
              </span>
            ))}
        </p>
      </div>

      {changes.length > 0 ? (
        <>
          <h2 className="page__title" style={{ fontSize: "var(--size-lg)", marginTop: "var(--s7)" }}>
            What changed
          </h2>
          <ol className="changeList">
            {changes.map((segment, position) => {
              const note = noteFor(segment.indices);
              return (
                <li className="change" key={position}>
                  <p className="change__label">
                    {segment.indices.length === 1 ? (
                      <>
                        Statement <span data-numeric>{(segment.indices[0] ?? 0) + 1}</span>
                      </>
                    ) : (
                      <>
                        Statements{" "}
                        <span data-numeric>
                          {segment.indices.map((index) => index + 1).join(" and ")}
                        </span>
                      </>
                    )}
                  </p>
                  <p className="change__was">{segment.before}</p>
                  {segment.after === "" ? (
                    <p className="change__removed">Removed from the summary</p>
                  ) : (
                    <p className="change__now">{segment.after}</p>
                  )}
                  {note ? (
                    <p className="change__note">
                      You told us: <q>{note}</q>
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      ) : null}

      {kept.length > 0 ? (
        <div style={{ marginTop: "var(--s7)" }}>
          <Callout
            tone="error"
            title={
              kept.length === 1
                ? "We could not make one of your corrections"
                : `We could not make ${kept.length} of your corrections`
            }
          >
            <p>
              {kept.length === 1 ? "This sentence is" : "These sentences are"} still
              exactly as they were written. To change them, go back and describe
              the correction a little differently, or say the sentence should be
              taken out. You can also approve the summary as it is.
            </p>
          </Callout>
          <ol className="changeList">
            {kept.map((statement) => (
              <li className="change" key={statement.index}>
                <p className="change__label">
                  Statement <span data-numeric>{statement.index + 1}</span>
                </p>
                <p className="change__kept">{statement.text}</p>
                {statement.note.trim() ? (
                  <p className="change__note">
                    You told us: <q>{statement.note.trim()}</q>
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {error ? (
        <div style={{ marginTop: "var(--s5)" }}>
          <Callout tone="error" title="We could not save that" role="alert">
            <p>{error}</p>
          </Callout>
        </div>
      ) : null}

      <div style={{ marginTop: "var(--s7)" }}>
        <Callout tone="info" title="Approving is final">
          <p>
            Once you approve, this version is recorded and you will not be able
            to change it here. If you need to fix something afterwards, contact
            the study team.
          </p>
        </Callout>
      </div>

      <div className="actions">
        <Button
          onClick={() => decide("approve")}
          busy={busy === "approve"}
          busyLabel="Submitting…"
          disabled={busy !== null}
        >
          Approve and submit
        </Button>
        <Button
          variant="secondary"
          onClick={() => decide("reject")}
          busy={busy === "reject"}
          busyLabel="Going back…"
          disabled={busy !== null}
        >
          Go back and change my answers
        </Button>
      </div>
    </AppLayout>
  );
}
