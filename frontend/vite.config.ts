import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 3199,
    proxy: {
      "/api": "http://localhost:8199",
    },
  },
});
