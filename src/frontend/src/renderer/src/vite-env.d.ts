/// <reference types="vite/client" />

// Ambient module declarations for static asset imports handled by Vite.
declare module '*.svg' {
  const src: string
  export default src
}
