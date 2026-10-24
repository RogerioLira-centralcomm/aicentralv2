import { defineConfig } from "vite";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import wasm from "vite-plugin-wasm";

const here = import.meta.dirname;
const out = resolve(here, "../../aicentralv2/static/cadu_studio/video_editor");

export default defineConfig({
	root: here,
	base: "/static/cadu_studio/video_editor/",
	publicDir: resolve(here, "public"),
	plugins: [react(), tailwindcss(), wasm()],
	resolve: {
		alias: [
			{ find: /^@\/(.*)$/, replacement: resolve(here, "opencut/$1") },
			{ find: "next/image", replacement: resolve(here, "shims/next-image.tsx") },
			{ find: "next/link", replacement: resolve(here, "shims/next-link.tsx") },
			{ find: "next/navigation", replacement: resolve(here, "shims/next-navigation.ts") },
			{ find: "next-themes", replacement: resolve(here, "shims/next-themes.tsx") },
		],
	},
	define: { "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV || "production") },
	worker: { format: "es", plugins: () => [wasm()] },
	build: {
		outDir: out,
		emptyOutDir: true,
		target: "es2022",
		cssCodeSplit: false,
		chunkSizeWarningLimit: 4000,
		rollupOptions: {
			input: resolve(here, "cadu/main.tsx"),
			output: {
				entryFileNames: "app.js",
				chunkFileNames: "chunks/[name]-[hash].js",
				assetFileNames: (asset) => (asset.names?.[0]?.endsWith(".css") ? "app.css" : "assets/[name]-[hash][extname]"),
			},
		},
	},
});
