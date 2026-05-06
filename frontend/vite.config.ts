import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("/react/") || id.includes("/react-dom/")) return "vendor-react";
          if (id.includes("/react-router") || id.includes("/@remix-run/")) return "vendor-router";
          if (id.includes("/@radix-ui/")) return "vendor-radix";
          if (id.includes("/lucide-react/")) return "vendor-icons";
          if (id.includes("/cos-js-sdk-v5/")) return "vendor-cos";
          if (id.includes("/axios/")) return "vendor-api";
          return undefined;
        },
      },
    },
  },
});
