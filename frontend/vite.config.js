import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // During development the Flask API runs on :8000; same-origin in production (Caddy).
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { sourcemap: false },
  test: { environment: "jsdom" },
});
