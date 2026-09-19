import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: true,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_workspace/conversations/react'),
    rollupOptions: {
      input: resolve('frontend/conversations-v2/main.jsx'),
      output: {
        entryFileNames: 'app.js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
