import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
// @ts-ignore
import sri from "vite-plugin-sri";

export default defineConfig({
  plugins: [react(), tailwindcss(), sri()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8001" },
  },
  build: {
    outDir: "dist",
  },
});
