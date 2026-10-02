import {defineConfig} from 'vite';
import {resolve} from 'node:path';

// Shared Studio navbar island for the Jinja pages (Criar, Editar, Vídeo, Início, Analisar).
export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: true,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_studio/ui'),
    rollupOptions: {
      input: resolve('frontend/cadu-studio-ui/island.jsx'),
      output: {
        entryFileNames: 'navbar.js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'navbar.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
