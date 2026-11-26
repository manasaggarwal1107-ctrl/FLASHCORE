/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_APP_ENV?: string;
  readonly VITE_API_TIMEOUT_MS?: string;
  readonly VITE_DEV_PROXY_TARGET?: string;
  readonly VITE_IDEMPOTENCY_HEADER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
