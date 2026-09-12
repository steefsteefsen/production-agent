import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/mes": "http://localhost:8000",
      "/investigations": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
