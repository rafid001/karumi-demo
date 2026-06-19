import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/ui/",
  server: {
    port: 5173,
    proxy: {
      "/crawl": "http://127.0.0.1:8000",
      "/graph": "http://127.0.0.1:8000",
      "/drift": "http://127.0.0.1:8000",
      "/heal": "http://127.0.0.1:8000",
      "/demo": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
      "/screenshots": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
