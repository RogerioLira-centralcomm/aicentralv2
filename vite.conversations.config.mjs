import {defineConfig} from 'vite';
import {resolve} from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    // The templates load workspace auxiliary assets from this directory
    // (catalog, dock, upload and reprocess styles/scripts). Vite must not
    // remove them before writing the React bundle.
    emptyOutDir: false,
    cssCodeSplit: false,
    outDir: resolve('aicentralv2/static/cadu_workspace/conversations/react'),
    rollupOptions: {
      input: resolve('frontend/conversations-v2/main.jsx'),
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: asset => asset.name?.endsWith('.css') ? 'app.css' : 'assets/[name]-[hash][extname]',
        manualChunks(id) {
          if (id.includes('/node_modules/react/') || id.includes('/node_modules/react-dom/') || id.includes('/node_modules/scheduler/')) return 'react-vendor';
          if (id.includes('/frontend/cadu-design-system/')) return 'workspace-ui';
          return undefined;
        },
      },
    },
  },
});
