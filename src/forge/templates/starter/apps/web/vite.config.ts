import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const appDirectory = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  root: appDirectory,
  plugins: [react({ babel: { plugins: ['babel-plugin-react-compiler'] } }), tailwindcss()],
  resolve: {
    conditions: ['@app/source', 'module', 'browser', 'development|production'],
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { host: '0.0.0.0', port: 3000, strictPort: true },
  build: { outDir: 'dist', emptyOutDir: true },
});
