import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 3000,
      strictPort: true,
      allowedHosts: true,
      // Disable HMR over the public preview ingress: WebSocket can't tunnel cleanly,
      // and Vite's failed reconnects trigger full-page reloads in a loop.
      hmr: false,
      watch: { usePolling: false },
    },
    define: {
      "import.meta.env.REACT_APP_BACKEND_URL": JSON.stringify(
        env.REACT_APP_BACKEND_URL || ""
      ),
    },
  };
});
