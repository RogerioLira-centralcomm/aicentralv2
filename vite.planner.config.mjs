import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: false,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_planner/react'),
    rollupOptions: {
      input: resolve('frontend/planner/main.jsx'),
      output: {entryFileNames: 'app.js', chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]' },
    },
  },
});
