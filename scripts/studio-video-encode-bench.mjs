// Mede, no Chromium desta máquina, captura de quadro e vazão do codificador H.264 em 1080p (editor de vídeo).
// Uso: node scripts/studio-video-encode-bench.mjs   (ARGS="--disable-gpu" para forçar software)
import { chromium } from "playwright";
const args = (process.env.ARGS || "").split(" ").filter(Boolean);
const browser = await chromium.launch({ args });
const page = await browser.newPage();
// WebCodecs só existe em contexto seguro: página HTTPS servida pelo próprio Playwright.
await page.route("https://bench.cadu.local/**", (route) => route.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><title>bench</title>" }));
await page.goto("https://bench.cadu.local/");
const result = await page.evaluate(async () => {
	const W = 1920, H = 1080, N = 120;
	const canvas = new OffscreenCanvas(W, H);
	const ctx = canvas.getContext("2d");
	const draw = (i) => { ctx.fillStyle = `hsl(${i * 3},70%,50%)`; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#fff"; ctx.font = "120px sans-serif"; ctx.fillText("Quadro " + i, 200 + i, 500); };
	// 1) captura do quadro
	let t = performance.now();
	for (let i = 0; i < N; i++) { draw(i); const f = new VideoFrame(canvas, { timestamp: i * 33333 }); f.close(); }
	const captureMs = (performance.now() - t) / N;
	const run = async (awaitEach, accel) => {
		const config = { codec: "avc1.640028", width: W, height: H, bitrate: 8e6, framerate: 30, hardwareAcceleration: accel };
		const support = await VideoEncoder.isConfigSupported(config);
		if (!support.supported) return { supported: false };
		let done = 0;
		const enc = new VideoEncoder({ output: () => { done++; }, error: (e) => console.error(e) });
		enc.configure(config);
		const start = performance.now();
		for (let i = 0; i < N; i++) {
			draw(i);
			const f = new VideoFrame(canvas, { timestamp: i * 33333 });
			enc.encode(f, { keyFrame: i % 60 === 0 }); f.close();
			if (awaitEach) await enc.flush();
			else while (enc.encodeQueueSize > 8) await new Promise((r) => setTimeout(r, 0));
		}
		await enc.flush();
		return { msPerFrame: +((performance.now() - start) / N).toFixed(1), frames: done };
	};
	const gl = new OffscreenCanvas(4, 4).getContext("webgl2");
	const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
	return {
		webgl: gl ? (info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : "indisponível",
		webgpu: !!(navigator.gpu && (await navigator.gpu.requestAdapter())),
		captureMs: +captureMs.toFixed(1), cores: navigator.hardwareConcurrency,
		pipelined_any: await run(false, "no-preference"),
		awaitEach_any: await run(true, "no-preference"),
		pipelined_software: await run(false, "prefer-software"),
	};
});
console.log(JSON.stringify(result));
await browser.close();
