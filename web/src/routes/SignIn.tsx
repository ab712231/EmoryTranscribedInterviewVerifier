import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthLayout } from "../components/layouts";
import { Button, Callout, TextField } from "../components/ui";
import {
  CognitoError,
  requestSignInCode,
  submitSignInCode,
  type SignInChallenge,
} from "../lib/cognito";
import { useSession } from "../lib/session";

export function SignIn() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn } = useSession();

  const passed = (location.state as { challenge?: SignInChallenge } | null)?.challenge;
  const [challenge, setChallenge] = useState<SignInChallenge | undefined>(passed);

  const [code, setCode] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [spent, setSpent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);

  async function resend(username: string) {
    setFailure(undefined);
    setFieldError(undefined);
    setSpent(false);
    setCode("");
    setResending(true);

    try {
      setChallenge(await requestSignInCode(username));
    } catch {
      setFailure("We could not send a new code just now. Please try again in a moment.");
    }
    setResending(false);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setFailure(undefined);

    const typed = code.trim();
    if (!typed) {
      setFieldError("Enter the code from your email.");
      return;
    }
    if (!/^\d{6}$/.test(typed)) {
      setFieldError("The code is six digits.");
      return;
    }
    setFieldError(undefined);
    setBusy(true);

    try {
      signIn(await submitSignInCode(challenge, typed));
      navigate("/interviews", { replace: true });
    } catch (error) {
      setBusy(false);

      if (error instanceof CognitoError && error.code === "NetworkError") {
        setFailure("We could not reach the study server. Check your connection and try again.");
        return;
      }

      setSpent(true);
    }
  }

  if (!challenge) {
    return (
      <AuthLayout title="Start again from the beginning" documentTitle="Sign in">
        <Callout tone="info">
          <p>
            To check your summary, enter your email address and we will send you
            a new code.
          </p>
        </Callout>
        <div style={{ marginTop: "var(--s5)" }}>
          <Button full onClick={() => navigate("/")}>
            Enter my email address
          </Button>
        </div>
      </AuthLayout>
    );
  }

  if (challenge.throttled) {
    return (
      <AuthLayout title="Please wait before asking again" documentTitle="Sign in">
        <Callout tone="error" title="Too many codes have been asked for" role="alert">
          <p>
            Several sign-in codes have been requested for this email address
            recently. Wait fifteen minutes, then ask for another one. Codes you
            already received will not work now.
          </p>
        </Callout>
        <div style={{ marginTop: "var(--s5)" }}>
          <Button full onClick={() => navigate("/")}>
            Start again
          </Button>
        </div>
      </AuthLayout>
    );
  }

  if (spent) {
    return (
      <AuthLayout title="That code did not work" documentTitle="Sign in">
        <Callout tone="error" title="Codes can be used once" role="alert">
          <p>
            That is deliberate. It keeps your record safe if an email is
            forwarded or left open. A new code takes a moment to arrive.
          </p>
        </Callout>
        <div style={{ marginTop: "var(--s5)" }}>
          <Button
            full
            onClick={() => resend(challenge.username)}
            busy={resending}
            busyLabel="Sending…"
          >
            Email me a new code
          </Button>
        </div>
        <p style={{ marginTop: "var(--s5)" }}>
          <Link to="/">Use a different email address</Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Enter your code"
      documentTitle="Enter your code"
      lede={
        <p>
          We sent a six-digit code to{" "}
          <strong>{challenge.maskedEmail || "your email address"}</strong>. It
          may take a minute to arrive.
        </p>
      }
    >
      <form className="auth__form" onSubmit={onSubmit} noValidate>
        {failure ? (
          <Callout tone="error" title="Something went wrong" role="alert">
            {failure}
          </Callout>
        ) : null}

        <TextField
          label="Six-digit code"
          hint="From the email we just sent."
          type="text"
          name="code"
          autoComplete="one-time-code"
          inputMode="numeric"
          maxLength={6}
          autoFocus
          value={code}
          error={fieldError}
          onChange={(event) => setCode(event.target.value)}
        />

        <Button type="submit" full busy={busy} busyLabel="Checking…">
          Continue
        </Button>

        <p className="field__hint">
          No code yet? Check your spam folder, or ask for a new one.
        </p>

        <Button
          variant="quiet"
          full
          onClick={() => resend(challenge.username)}
          busy={resending}
          busyLabel="Sending…"
          disabled={busy}
        >
          Send me a new code
        </Button>
      </form>
    </AuthLayout>
  );
}
