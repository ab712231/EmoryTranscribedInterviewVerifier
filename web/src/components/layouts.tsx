import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import "./layouts.css";

function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} - Interview summary check`;
  }, [title]);
}

export function AuthLayout({
  title,
  lede,
  documentTitle,
  children,
}: {
  title: string;
  lede?: ReactNode;
  documentTitle?: string;
  children: ReactNode;
}) {
  useDocumentTitle(documentTitle ?? title);

  return (
    <div className="auth">
      <main className="auth__main" id="main">
        <div className="auth__card">
          <h1 className="auth__title">{title}</h1>
          {lede ? <div className="auth__lede">{lede}</div> : null}
          {children}
        </div>
      </main>
      <footer className="auth__footer">
        <p>
          <Link to="/privacy">How your information is used</Link>
        </p>
      </footer>
    </div>
  );
}

export function AppLayout({
  patientId,
  documentTitle,
  children,
}: {
  patientId?: string;
  documentTitle: string;
  children: ReactNode;
}) {
  useDocumentTitle(documentTitle);

  return (
    <div className="app">
      <a className="skipLink" href="#main">
        Skip to main content
      </a>
      <header className="app__bar">
        <div className="app__barInner">
          <p className="app__institution">Emory</p>
          {patientId ? (
            <p className="app__participant">
              Participant <span data-numeric>{patientId}</span>
            </p>
          ) : null}
        </div>
      </header>
      <main className="app__main" id="main">
        {children}
      </main>
      <footer className="app__foot">
        <p>
          Questions about this study? Contact the study team using the details in
          the email you received.
        </p>
        <p className="app__footLinks">
          <Link to="/privacy">How your information is used</Link>
        </p>
      </footer>
    </div>
  );
}
