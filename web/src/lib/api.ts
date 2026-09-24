import { API_BASE_URL } from "../config";

export type Verdict = "correct" | "incorrect" | "unsure";

export interface Statement {
  index: number;
  text: string;
  verdict: Verdict | null;
  note: string;
}

export interface Progress {
  reviewed: number;
  total: number;
}

export type SessionStatus = "in_progress" | "awaiting_approval" | "submitted";

export type InterviewStatus = SessionStatus | "not_started";

export interface InterviewSummary {
  interviewId: string;
  status: InterviewStatus;
  progress: Progress;
  submittedAt: string | null;
}

export interface InterviewList {
  patientId: string;
  interviews: InterviewSummary[];

  pending: string[];
}

export interface VerificationSession {
  patientId: string;
  interviewId: string;

  summary: string;
  status: SessionStatus;
  locked: boolean;
  statements: Statement[];
  progress: Progress;
}

export interface VerdictResult {
  patientId: string;
  interviewId: string;
  status: SessionStatus;
  progress: Progress;
  complete: boolean;
}

export interface DraftResult {
  patientId: string;
  interviewId: string;
  status: SessionStatus;
  original: string;
  proposed: string;
  rewrittenCount: number;

  removed: number[];

  notApplied: number[];
}

export interface SubmitResult {
  patientId: string;
  interviewId: string;
  status: SessionStatus;
  submittedAt?: string;
}

export class ApiError extends Error {
  readonly status: number;

  readonly retryable: boolean;

  constructor(status: number, message: string, retryable = false) {
    super(message);
    this.status = status;
    this.retryable = retryable;
    this.name = "ApiError";
  }

  get isAuthFailure(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }

  get isMissing(): boolean {
    return this.status === 404;
  }
}

async function request<T>(
  path: string,
  idToken: string,
  init?: { method?: string; body?: unknown }
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init?.method ?? "GET",
      headers: {

        authorization: `Bearer ${idToken}`,
        ...(init?.body ? { "content-type": "application/json" } : {}),
      },
      body: init?.body ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "We could not reach the study server.", true);
  }

  const text = await response.text();
  let payload: Record<string, unknown> = {};
  try {
    payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {

  }

  if (!response.ok) {
    const message =
      typeof payload["message"] === "string"
        ? payload["message"]
        : "Something went wrong on the study server.";
    const retryable = payload["retryable"] === true || response.status >= 500;
    throw new ApiError(response.status, message, retryable);
  }

  return payload as T;
}

export function loadInterviews(idToken: string): Promise<InterviewList> {
  return request<InterviewList>("/verification/interviews", idToken);
}

export function loadSession(
  idToken: string,
  interviewId: string
): Promise<VerificationSession> {
  return request<VerificationSession>(
    `/verification?interview=${encodeURIComponent(interviewId)}`,
    idToken
  );
}

export function recordVerdicts(
  idToken: string,
  interviewId: string,
  verdicts: { index: number; verdict: Verdict; note?: string }[]
): Promise<VerdictResult> {
  return request<VerdictResult>("/verification/verdicts", idToken, {
    method: "POST",
    body: { interviewId, verdicts },
  });
}

export function prepareDraft(
  idToken: string,
  interviewId: string
): Promise<DraftResult> {
  return request<DraftResult>("/verification/draft", idToken, {
    method: "POST",
    body: { interviewId },
  });
}

export function submitDecision(
  idToken: string,
  interviewId: string,
  decision: "approve" | "reject"
): Promise<SubmitResult> {
  return request<SubmitResult>("/verification/submit", idToken, {
    method: "POST",
    body: { interviewId, decision },
  });
}
