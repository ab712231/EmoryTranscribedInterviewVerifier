import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthLayout } from "./components/layouts";
import { Button, Callout } from "./components/ui";
import { useSession } from "./lib/session";
import { Privacy } from "./routes/Privacy";
import { Done } from "./routes/Done";
import { Draft } from "./routes/Draft";
import { Interviews } from "./routes/Interviews";
import { RequestLink } from "./routes/RequestLink";
import { Review } from "./routes/Review";
import { SignIn } from "./routes/SignIn";
import { Summary } from "./routes/Summary";
import type { ReactNode } from "react";

function RequireSession({ children }: { children: ReactNode }) {
  const { idToken } = useSession();
  const location = useLocation();

  if (!idToken) {
    const returning = !location.pathname.startsWith("/summary");
    return (
      <AuthLayout title="Your sign-in has ended" documentTitle="Sign in again">
        <Callout tone="info">
          <p>
            For safety, this page signs you out after a while and when you close
            the tab.{" "}
            {returning ? "Everything you answered was saved as you went." : null}
          </p>
        </Callout>
        <div style={{ marginTop: "var(--s5)" }}>
          <Button full onClick={() => window.location.assign("/")}>
            Email me a new sign-in link
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<RequestLink />} />
      <Route path="/check-email" element={<Navigate to="/" replace />} />
      <Route path="/signin" element={<SignIn />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route
        path="/interviews"
        element={
          <RequireSession>
            <Interviews />
          </RequireSession>
        }
      />
      <Route
        path="/summary/:interviewId"
        element={
          <RequireSession>
            <Summary />
          </RequireSession>
        }
      />
      <Route
        path="/review/:interviewId"
        element={
          <RequireSession>
            <Review />
          </RequireSession>
        }
      />
      <Route
        path="/draft/:interviewId"
        element={
          <RequireSession>
            <Draft />
          </RequireSession>
        }
      />
      <Route
        path="/done/:interviewId"
        element={
          <RequireSession>
            <Done />
          </RequireSession>
        }
      />

      <Route path="/summary" element={<Navigate to="/interviews" replace />} />
      <Route path="/review" element={<Navigate to="/interviews" replace />} />
      <Route path="/draft" element={<Navigate to="/interviews" replace />} />
      <Route path="/done" element={<Navigate to="/interviews" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
