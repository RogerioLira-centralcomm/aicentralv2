import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: true,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_auth'),
    rollupOptions: {
      input: resolve('frontend/cadu-design-system/auth/main.jsx'),
      output: {
        entryFileNames: 'app.js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
