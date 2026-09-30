import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  // Untitled UI includes TSX modules without a React binding. The automatic
  // runtime keeps those components renderable alongside our existing imports.
  esbuild: {jsx: 'automatic'},
  // Source files are bundled directly; there are no source maps to report
  // errors against, and enabling the lookup only produces misleading warnings.
  build: {
    sourcemap: false,
    emptyOutDir: false,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_connect/react'),
    rollupOptions: {
      input: resolve('frontend/reports-v1/main.jsx'),
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]',
        manualChunks(id) {
          if (id.includes('/node_modules/react/') || id.includes('/node_modules/react-dom/') || id.includes('/node_modules/scheduler/')) return 'react-vendor';
        },
      },
    },
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
});
