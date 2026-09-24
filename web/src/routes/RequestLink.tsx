import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AuthLayout } from "../components/layouts";
import { Button, Callout, TextField } from "../components/ui";
import { CognitoError, requestSignInCode } from "../lib/cognito";

export function RequestLink() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFailure(undefined);

    const trimmed = email.trim();
    if (!trimmed) {
      setFieldError("Enter the email address the study team wrote to.");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmed)) {
      setFieldError("That does not look like an email address.");
      return;
    }
    setFieldError(undefined);
    setBusy(true);

    try {
      const challenge = await requestSignInCode(trimmed);

      navigate("/signin", { state: { challenge } });
    } catch (error) {

      if (error instanceof CognitoError && error.code === "UserNotFoundException") {
        navigate("/signin", {
          state: {
            challenge: {
              session: "",
              username: trimmed,
              maskedEmail: "",
              throttled: false,
            },
          },
        });
        return;
      }
      setFailure(
        error instanceof CognitoError && error.code === "NetworkError"
          ? "We could not reach the study server. Check your connection and try again."
          : "We could not send your code just now. Please try again in a moment."
      );
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Check your interview summary"
      documentTitle="Sign in"
      lede={
        <p>
          A summary of your recent interview at Emory was
          written with the help of AI. We need you to tell us whether it got
          things right.
        </p>
      }
    >
      <form className="auth__form" onSubmit={onSubmit} noValidate>
        {failure ? (
          <Callout tone="error" title="We could not send your code" role="alert">
            {failure}
          </Callout>
        ) : null}

        <TextField
          label="Your email address"
          hint="Use the address the study team wrote to."
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          autoFocus
          value={email}
          error={fieldError}
          onChange={(event) => setEmail(event.target.value)}
        />

        <Button type="submit" full busy={busy} busyLabel="Sending…">
          Email me a sign-in code
        </Button>

        <p className="field__hint">
          We will email you a short code to type on the next screen. There is no
          password to remember.
        </p>
      </form>
    </AuthLayout>
  );
}
