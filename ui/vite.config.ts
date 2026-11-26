import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// `npm run dev` proxies /api to a running `marcarr serve`; `npm run build`
// writes ui/dist, which the FastAPI app serves.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5470,
    proxy: { '/api': { target: process.env.MARCARR_API || 'http://127.0.0.1:7470', changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { environment: 'jsdom', globals: false },
});
