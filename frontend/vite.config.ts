import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: '127.0.0.1', port: 3100, strictPort: true,
    // No VITE_ backend secrets. The target is server-only development configuration.
    proxy: { '/api/v1': { target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8100', changeOrigin: false } },
  },
});
