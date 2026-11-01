import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En développement, les appels /api sont relayés vers FastAPI (port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
