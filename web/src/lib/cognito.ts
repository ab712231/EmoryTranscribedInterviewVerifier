import { COGNITO_CLIENT_ID, COGNITO_REGION } from "../config";

const ENDPOINT = `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`;
const TARGET = "AWSCognitoIdentityProviderService";

export interface CognitoTokens {
  idToken: string;
  accessToken: string;
  expiresAt: number;
}

export interface SignInChallenge {
  session: string;
  username: string;

  maskedEmail: string;

  throttled: boolean;
}

export class CognitoError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "CognitoError";
  }
}

async function call(action: string, body: unknown): Promise<Record<string, unknown>> {
  let response: Response;
  try {
    response = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "content-type": "application/x-amz-json-1.1",
        "x-amz-target": `${TARGET}.${action}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new CognitoError("NetworkError", "We could not reach the sign-in service.");
  }

  const text = await response.text();
  const payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};

  if (!response.ok) {

    const raw = typeof payload["__type"] === "string" ? payload["__type"] : "UnknownError";
    const code = raw.split("#").pop() ?? "UnknownError";
    const message =
      typeof payload["message"] === "string" ? payload["message"] : response.statusText;
    throw new CognitoError(code, message);
  }

  return payload;
}

export async function requestSignInCode(username: string): Promise<SignInChallenge> {
  const result = await call("InitiateAuth", {
    AuthFlow: "CUSTOM_AUTH",
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: { USERNAME: username },
  });

  const session = result["Session"];
  if (typeof session !== "string") {
    throw new CognitoError("NoSession", "The sign-in service did not start a session.");
  }

  const parameters = (result["ChallengeParameters"] ?? {}) as Record<string, unknown>;
  const maskedEmail = typeof parameters["email"] === "string" ? parameters["email"] : "";
  const throttled = parameters["throttled"] === "true";

  return { session, username, maskedEmail, throttled };
}

export async function submitSignInCode(
  challenge: SignInChallenge,
  code: string
): Promise<CognitoTokens> {
  const result = await call("RespondToAuthChallenge", {
    ChallengeName: "CUSTOM_CHALLENGE",
    ClientId: COGNITO_CLIENT_ID,
    Session: challenge.session,
    ChallengeResponses: { USERNAME: challenge.username, ANSWER: code },
  });

  const auth = result["AuthenticationResult"] as Record<string, unknown> | undefined;
  const idToken = auth?.["IdToken"];
  const accessToken = auth?.["AccessToken"];
  const expiresIn = auth?.["ExpiresIn"];

  if (typeof idToken !== "string" || typeof accessToken !== "string") {

    throw new CognitoError("NoTokens", "That code did not match.");
  }

  return {
    idToken,
    accessToken,
    expiresAt: Date.now() + (typeof expiresIn === "number" ? expiresIn : 3600) * 1000,
  };
}
