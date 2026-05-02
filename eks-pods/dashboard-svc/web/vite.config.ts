import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In production, FastAPI mounts dist/ at /. In dev, vite proxies /dashboard and /ws to local FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/dashboard': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':        { target: 'ws://localhost:8000',  ws: true },
      '/health':    { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
