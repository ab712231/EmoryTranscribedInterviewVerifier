function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `${name} is not set. From the repository root run ` +
        `python scripts/deployment/web_env.py --env dev to write web/.env.local.`
    );
  }
  return value;
}

export const API_BASE_URL = required("VITE_API_BASE_URL", import.meta.env.VITE_API_BASE_URL);
export const COGNITO_CLIENT_ID = required("VITE_COGNITO_CLIENT_ID", import.meta.env.VITE_COGNITO_CLIENT_ID);
export const COGNITO_REGION = required("VITE_COGNITO_REGION", import.meta.env.VITE_COGNITO_REGION);
