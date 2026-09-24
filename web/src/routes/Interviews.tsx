import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { Button, Loading } from "../components/ui";
import { ApiError, loadInterviews, type InterviewSummary } from "../lib/api";
import { useIdToken, useSession } from "../lib/session";
import "./interviews.css";

export function formatInterviewDate(interviewId: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(interviewId);
  if (!match) return interviewId;

  const [, year, month, day] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (Number.isNaN(date.getTime())) return interviewId;

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function describe(interview: InterviewSummary): string {
  const { reviewed, total } = interview.progress;
  if (interview.status === "submitted") return "Checked and submitted";
  if (interview.status === "awaiting_approval") return "Waiting for you to approve it";
  if (reviewed === 0) return "Not started";
  if (reviewed >= total && total > 0) return "All answered, not yet approved";
  return `${reviewed} of ${total} checked`;
}

export function Interviews() {
  const idToken = useIdToken();
  const { signOut } = useSession();
  const navigate = useNavigate();

  const [interviews, setInterviews] = useState<InterviewSummary[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let cancelled = false;

    loadInterviews(idToken)
      .then((result) => {
        if (cancelled) return;

        if (result.pending.length === 1 && result.interviews.length === 1) {
          navigate(`/summary/${result.pending[0]}`, { replace: true });
          return;
        }
        setInterviews(result.interviews);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const apiError =
          caught instanceof ApiError ? caught : new ApiError(0, "Something went wrong.");
        if (apiError.isAuthFailure) signOut();
        setError(
          apiError.retryable
            ? "We could not load your summaries. Please try again."
            : apiError.message
        );
      });

    return () => {
      cancelled = true;
    };
  }, [idToken, navigate, signOut]);

  if (error) {
    return (
      <AppLayout documentTitle="Your summaries">
        <div className="panel">
          <h1 className="page__title">We could not load your summaries</h1>
          <p className="page__lede">{error}</p>
          <div className="actions">
            <Button onClick={() => window.location.reload()}>Try again</Button>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (!interviews) {
    return (
      <AppLayout documentTitle="Your summaries">
        <Loading label="Loading your summaries…" />
      </AppLayout>
    );
  }

  if (interviews.length === 0) {
    return (
      <AppLayout documentTitle="Your summaries">
        <div className="panel">
          <h1 className="page__title">Nothing to check yet</h1>
          <p className="page__lede">
            There is no summary ready for you at the moment. The study team will
            email you when there is.
          </p>
        </div>
      </AppLayout>
    );
  }

  const outstanding = interviews.filter((one) => one.status !== "submitted");

  return (
    <AppLayout documentTitle="Your summaries">
      <h1 className="page__title">Your interview summaries</h1>
      <p className="page__lede">
        {outstanding.length === 0 ? (
          <>You have checked all of these. Thank you.</>
        ) : (
          <>
            You have{" "}
            <strong data-numeric>{outstanding.length}</strong>{" "}
            {outstanding.length === 1 ? "summary" : "summaries"} left to check.
            Each one covers a different conversation, so please read them
            separately.
          </>
        )}
      </p>

      <ul className="interviews">
        {interviews.map((interview) => {
          const done = interview.status === "submitted";
          return (
            <li className="interview" key={interview.interviewId}>
              <div className="interview__detail">
                <p className="interview__date">
                  Interview on {formatInterviewDate(interview.interviewId)}
                </p>
                <p className="interview__state">{describe(interview)}</p>
              </div>
              {done ? (
                <span className="interview__done">Done</span>
              ) : (
                <Link
                  className="button button--primary"
                  to={`/summary/${interview.interviewId}`}
                >
                  {interview.progress.reviewed > 0 ? "Continue" : "Check this one"}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </AppLayout>
  );
}
