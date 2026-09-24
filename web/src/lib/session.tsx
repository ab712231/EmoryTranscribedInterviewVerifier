import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { CognitoTokens } from "./cognito";

const STORAGE_KEY = "portal.session";

interface StoredSession {
  idToken: string;
  expiresAt: number;
}

function read(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (typeof parsed.idToken !== "string" || typeof parsed.expiresAt !== "number") {
      return null;
    }
    if (parsed.expiresAt <= Date.now()) return null;
    return parsed;
  } catch {

    return null;
  }
}

function write(value: StoredSession | null): void {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {

  }
}

interface SessionValue {
  idToken: string | null;
  signIn: (tokens: CognitoTokens) => void;
  signOut: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => read());

  const signIn = useCallback((tokens: CognitoTokens) => {
    const next = { idToken: tokens.idToken, expiresAt: tokens.expiresAt };
    write(next);
    setSession(next);
  }, []);

  const signOut = useCallback(() => {
    write(null);
    setSession(null);
  }, []);

  useEffect(() => {
    if (!session) return;
    const remaining = session.expiresAt - Date.now();
    if (remaining <= 0) {
      signOut();
      return;
    }
    const timer = window.setTimeout(signOut, remaining);
    return () => window.clearTimeout(timer);
  }, [session, signOut]);

  const value = useMemo<SessionValue>(
    () => ({ idToken: session?.idToken ?? null, signIn, signOut }),
    [session, signIn, signOut]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

export function useIdToken(): string {
  const { idToken } = useSession();
  if (!idToken) throw new Error("This screen requires a signed-in participant");
  return idToken;
}
