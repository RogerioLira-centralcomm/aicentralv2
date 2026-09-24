import {defineConfig} from 'vite';
import {resolve} from 'node:path';
import {readFileSync, readdirSync, unlinkSync} from 'node:fs';

const outputDir = resolve('aicentralv2/static/cadu_workspace/conversations/react');

const pruneWorkspaceChunks = () => {
  let previous = '';
  return {
  name: 'prune-workspace-chunks',
  buildStart() {
    try {
      const entry = readFileSync(resolve(outputDir, 'app.js'), 'utf8');
      previous = entry.match(/\.\/assets\/(workspace-ui-[A-Za-z0-9_-]+\.js)/)?.[1] || '';
    } catch {
      previous = '';
    }
  },
  closeBundle() {
    const entry = readFileSync(resolve(outputDir, 'app.js'), 'utf8');
    const current = entry.match(/\.\/assets\/(workspace-ui-[A-Za-z0-9_-]+\.js)/)?.[1];
    if (!current) return;
    for (const filename of readdirSync(resolve(outputDir, 'assets'))) {
      // Keep both sides of the entry swap. deploy.sh can restore app.js after
      // a failed rollout, so the previous module must remain loadable too.
      if (filename.startsWith('workspace-ui-') && filename.endsWith('.js')
          && filename !== current && filename !== previous) {
        unlinkSync(resolve(outputDir, 'assets', filename));
      }
    }
  },
  };
};

export default defineConfig({
  plugins: [pruneWorkspaceChunks()],
  publicDir: false,
  build: {
    // The templates load workspace auxiliary assets from this directory
    // (catalog, dock, upload and reprocess styles/scripts). Vite must not
    // remove them before writing the React bundle.
    emptyOutDir: false,
    cssCodeSplit: false,
    outDir: outputDir,
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
