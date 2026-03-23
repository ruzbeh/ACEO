import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  /** Same host the browser would use for the API when not using Vite (e.g. Docker publishes 8100). */
  const target =
    env.VITE_DEV_PROXY_TARGET ||
    env.AECO_BACKEND_URL ||
    'http://localhost:8000';

  const backendProxy = {
    '/api': {
      target,
      changeOrigin: true,
      ws: true,
    },
    '/health': {
      target,
      changeOrigin: true,
    },
  } as const;

  return {
    plugins: [react()],
    base: '/dashboard/',
    server: {
      port: 5173,
      proxy: { ...backendProxy },
    },
    preview: {
      port: 4173,
      proxy: { ...backendProxy },
    },
    build: {
      outDir: 'dist',
    },
  };
});
