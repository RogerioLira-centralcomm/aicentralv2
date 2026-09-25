import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: false,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_connect/react'),
    rollupOptions: {
      input: resolve('frontend/reports-v1/main.jsx'),
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
