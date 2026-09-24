import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { Callout, Loading } from "../components/ui";
import { ApiError, loadSession, type VerificationSession } from "../lib/api";
import { useIdToken, useSession } from "../lib/session";

export function Done() {

  const { interviewId = "" } = useParams();
  const idToken = useIdToken();
  const { signOut } = useSession();
  const [session, setSession] = useState<VerificationSession>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    loadSession(idToken, interviewId)
      .then((result) => !cancelled && setSession(result))
      .catch((caught: unknown) => {
        if (cancelled) return;
        const apiError = caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
        if (apiError.isAuthFailure) signOut();
        setError(apiError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [idToken, signOut]);

  if (error) {
    return (
      <AppLayout documentTitle="Finished">
        <div className="panel">
          <h1 className="page__title">Something went wrong</h1>
          <p className="page__lede">{error}</p>
        </div>
      </AppLayout>
    );
  }

  if (!session) {
    return (
      <AppLayout documentTitle="Finished">
        <Loading label="Loading…" />
      </AppLayout>
    );
  }

  const submitted = session.status === "submitted";

  return (
    <AppLayout patientId={session.patientId} documentTitle="Finished">
      <div className="panel">
        <h1 className="page__title">
          {submitted ? "Thank you, you're all done" : "Nothing left to do right now"}
        </h1>
        <p className="page__lede">
          {submitted ? (
            <>
              Your corrected summary has been sent to the study team. You do not
              need to do anything else, and you can close this page.
            </>
          ) : (
            <>
              There is nothing waiting for you at the moment. The study team will
              email you if that changes.
            </>
          )}
        </p>

        {submitted ? (
          <Callout tone="success" title="What happens next">
            <p>
              The study team will use what you told us to understand how accurate
              these AI-written summaries are. If you spot something afterwards
              that you want to change, contact them using the details in your
              email. They can reopen it for you.
            </p>
          </Callout>
        ) : null}
      </div>
    </AppLayout>
  );
}
