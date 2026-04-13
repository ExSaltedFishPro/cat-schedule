/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TERM_START_DATES?: string;
  readonly VITE_DEFAULT_TERM_START_DATE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
