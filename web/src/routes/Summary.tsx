import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { Button, Callout, Loading } from "../components/ui";
import { ApiError, loadSession, type VerificationSession } from "../lib/api";
import { useIdToken, useSession } from "../lib/session";

export function Summary() {

  const { interviewId = "" } = useParams();
  const idToken = useIdToken();
  const { signOut } = useSession();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<string>();
  const [session, setSession] = useState<VerificationSession>();
  const [error, setError] = useState<ApiError>();

  useEffect(() => {
    let cancelled = false;

    loadSession(idToken, interviewId)
      .then((sessionResult) => {
        if (cancelled) return;
        if (sessionResult.locked) {
          navigate(`/done/${interviewId}`, { replace: true });
          return;
        }
        setSummary(sessionResult.summary);
        setSession(sessionResult);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const apiError = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
        if (apiError.isAuthFailure) signOut();
        setError(apiError);
      });

    return () => {
      cancelled = true;
    };
  }, [idToken, navigate, signOut]);

  if (error) {
    return (
      <AppLayout documentTitle="Your summary">
        <div className="panel">
          {error.isMissing ? (
            <>
              <h1 className="page__title">Your summary is not ready yet</h1>
              <p className="page__lede">
                Nothing has been written up for you so far. The study team will
                email you when there is something to check.
              </p>
            </>
          ) : (
            <>
              <h1 className="page__title">We could not load your summary</h1>
              <p className="page__lede">{error.message}</p>
              <Button onClick={() => window.location.reload()}>Try again</Button>
            </>
          )}
        </div>
      </AppLayout>
    );
  }

  if (!summary || !session) {
    return (
      <AppLayout documentTitle="Your summary">
        <Loading label="Loading your summary…" />
      </AppLayout>
    );
  }

  const started = session.progress.reviewed > 0;

  return (
    <AppLayout patientId={session.patientId} documentTitle="Your summary">
      <p className="page__step">Step 1 of 3</p>
      <h1 className="page__title">Read your interview summary</h1>
      <p className="page__lede">
        This was written with the help of AI after your interview. Read it
        through once. On the next screen we will ask you about it one sentence
        at a time.
      </p>

      <div className="panel">
        <div className="prose">
          {summary
            .split(/\n\s*\n/)
            .filter((paragraph) => paragraph.trim())
            .map((paragraph, index) => (
              <p key={index}>{paragraph.trim()}</p>
            ))}
        </div>
      </div>

      {started ? (
        <div style={{ marginTop: "var(--s5)" }}>
          <Callout tone="info" title="You have already started">
            <p>
              You answered{" "}
              <strong data-numeric>{session.progress.reviewed}</strong> of{" "}
              <strong data-numeric>{session.progress.total}</strong> statements.
              Your answers were saved.
            </p>
          </Callout>
        </div>
      ) : null}

      <div className="actions">
        <Button onClick={() => navigate(`/review/${interviewId}`)}>
          {started ? "Continue checking it" : "Start checking it"}
        </Button>
      </div>
    </AppLayout>
  );
}
