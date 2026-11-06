/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Source maps are never published (research R1).
    sourcemap: false,
  },
  server: {
    port: 5173,
    // /auth.json and /cognito: the local fake sign-in (python -m staysharp.local with FAKE_COGNITO=1).
    proxy: {
      "/api": "http://localhost:3001",
      "/auth.json": "http://localhost:3001",
      "/cognito": "http://localhost:3001",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}", "tests/unit/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/unit/setup.ts"],
  },
});
