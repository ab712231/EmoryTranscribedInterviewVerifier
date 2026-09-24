interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_COGNITO_CLIENT_ID: string;
  readonly VITE_COGNITO_REGION: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
