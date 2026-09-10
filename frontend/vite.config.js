import path from "node:path";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // shadcn components are copied in expecting the @/ alias.
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    // Proxy keeps the frontend origin-relative, so no CORS surprises in dev
    // and the same build works when served behind a single domain.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
