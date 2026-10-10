import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Zugriff auch vom Handy aus dem gleichen WLAN: host "0.0.0.0" statt nur
// "localhost". /api wird automatisch an das lokale Backend weitergereicht.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
