// Render do editor de vídeo no worker: abre o editor compilado no Chromium headless,
// entrega projeto e mídias direto do disco (sem HTTP para o app nem login) e grava o arquivo exportado.
// Uso: node scripts/studio-video-render.mjs <job.json>
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const ORIGIN = "https://render.cadu.local";
const API = "/api/format-lab/studio/video-editor";
const TYPES = { ".js": "text/javascript", ".css": "text/css", ".wasm": "application/wasm", ".json": "application/json",
	".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".html": "text/html" };

const job = JSON.parse(await readFile(process.argv[2], "utf8"));
const media = new Map(job.media.map((item) => [item.id, item]));
const boot = { clientId: 1, projectId: job.project_id, apiRoot: "/api", csrfToken: "render", exitUrl: "/", editorUrl: "/",
	renderMode: true, renderOptions: job.options, simulateNoH264: process.env.CADU_RENDER_SIMULATE_NO_H264 === "1" };
const html = `<!doctype html><html class="dark"><head><meta charset="utf-8">
<link rel="stylesheet" href="/static/cadu_studio/video_editor/app.css">
<script>window.CADU_VIDEO_EDITOR=${JSON.stringify(boot)};</script></head>
<body><div id="cadu-video-editor"></div><script type="module" src="/static/cadu_studio/video_editor/app.js"></script></body></html>`;

const json = (data) => ({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data }) });

async function serveStatic(route, pathname) {
	const relative = normalize(pathname.replace("/static/cadu_studio/video_editor/", ""));
	if (relative.startsWith("..")) return route.abort();
	try {
		const body = await readFile(join(job.static, relative));
		return route.fulfill({ status: 200, body, contentType: TYPES[extname(relative)] || "application/octet-stream" });
	} catch {
		return route.fulfill({ status: 404, body: "" });
	}
}

// Sem GPU o Chromium headless compõe por software (SwiftShader): ~87 ms/quadro em 1080p contra ~13 ms com GPU.
// CADU_RENDER_GPU=metal|vulkan|gl liga a GPU da máquina; CADU_RENDER_ARGS substitui tudo (testes).
// Forçar --use-angle=swiftshader gera quadros pretos.
const GPU_ARGS = {
	metal: ["--headless=new", "--enable-gpu", "--use-angle=metal", "--enable-unsafe-webgpu"],
	vulkan: ["--headless=new", "--enable-gpu", "--use-angle=vulkan", "--enable-features=Vulkan", "--enable-unsafe-webgpu"],
	gl: ["--headless=new", "--enable-gpu", "--use-angle=gl"],
};
const launchArgs = process.env.CADU_RENDER_ARGS
	? process.env.CADU_RENDER_ARGS.split(" ").filter(Boolean)
	: [...(GPU_ARGS[process.env.CADU_RENDER_GPU] || []), "--autoplay-policy=no-user-gesture-required"];
const browser = await chromium.launch({ channel: process.env.CADU_RENDER_CHANNEL || undefined, args: launchArgs });
let failed = false;
try {
	const page = await browser.newPage();
	page.on("console", (message) => ["error", "warning"].includes(message.type()) && console.error(`[page:${message.type()}]`, message.text()));
	page.on("pageerror", (error) => console.error("[page]", error.message));
	await page.route("**/*", async (route) => {
		const url = new URL(route.request().url());
		if (url.origin !== ORIGIN) {
			// Fontes do Google usadas pela tipografia do projeto; o resto da internet fica bloqueado.
			return url.hostname === "fonts.gstatic.com" || url.hostname === "fonts.googleapis.com" ? route.continue() : route.abort();
		}
		if (url.pathname === "/render.html") return route.fulfill({ status: 200, contentType: "text/html", body: html });
		if (url.pathname.startsWith("/static/cadu_studio/video_editor/")) return serveStatic(route, url.pathname);
		if (url.pathname.startsWith("/media/")) {
			const item = media.get(decodeURIComponent(url.pathname.slice(7)));
			if (!item) return route.fulfill({ status: 404, body: "" });
			return route.fulfill({ status: 200, body: await readFile(item.path), contentType: item.mime });
		}
		const projectPath = `${API}/projects/${job.project_id}`;
		if (url.pathname === projectPath && route.request().method() === "GET") return route.fulfill(json({ revision: job.revision, project: job.timeline }));
		if (url.pathname === projectPath) return route.fulfill(json({ revision: job.revision }));
		if (url.pathname === `${projectPath}/media`) {
			return route.fulfill(json({ items: job.media.map((item) => ({ ...item.meta, contentUrl: `${ORIGIN}/media/${encodeURIComponent(item.id)}` })) }));
		}
		return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ success: false, error: "fora do render" }) });
	});
	const startedAt = Date.now();
	await page.goto(`${ORIGIN}/render.html`);
	const pageMs = Date.now() - startedAt;
	const handle = await page.waitForFunction(() => {
		const state = window.__caduRender;
		return state && (state.status === "done" || state.status === "error") ? state : null;
	}, null, { timeout: (job.timeout_seconds || 840) * 1000, polling: 500 });
	const state = await handle.jsonValue();
	if (state.status === "error") throw new Error(`render: ${state.error}`);
	const chunks = await page.evaluate(() => window.__caduRenderChunks);
	const parts = [];
	for (let index = 0; index < chunks; index += 1) {
		parts.push(Buffer.from(await page.evaluate((i) => window.__caduRenderChunk(i), index), "base64"));
	}
	await writeFile(job.output, Buffer.concat(parts));
	// Última linha da saída: o worker lê o formato real (WebM quando o Chromium não codifica H.264).
	console.log(JSON.stringify({ ok: true, gpu: state.gpu, format: state.format, bytes: parts.reduce((sum, part) => sum + part.length, 0),
		page_ms: pageMs, total_ms: Date.now() - startedAt, timings: state.timings, stats: state.stats }));
} catch (error) {
	failed = true;
	console.error(error.message);
} finally {
	await browser.close();
}
process.exit(failed ? 1 : 0);
