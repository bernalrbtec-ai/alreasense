/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CHAT_UI_V2?: string;
  readonly VITE_CHAT_HUB_UI?: string;
  readonly VITE_CHAT_HUB_GROUPING?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
