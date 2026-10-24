// Modo usado pelo worker: abre o projeto, exporta com o mesmo renderizador da prévia e devolve os bytes ao script Node.
import { EditorCore } from "@/core";
import { initializeGpuRenderer, isGpuAvailable } from "@/services/renderer/gpu-renderer";
import { canEncodeAudio, canEncodeVideo } from "mediabunny";
import type { ExportOptions } from "@/export";
import { exportStats } from "@/services/renderer/scene-exporter";
import { boot } from "./config";

type RenderState = {
	status: "loading" | "rendering" | "done" | "error";
	progress: number;
	error?: string;
	gpu?: boolean;
	format?: ExportOptions["format"];
	timings?: Record<string, number>;
	stats?: typeof exportStats;
};

declare global {
	interface Window {
		__caduRender?: RenderState;
		__caduRenderChunk?: (index: number) => string;
		__caduRenderChunks?: number;
	}
}

const CHUNK = 4 * 1024 * 1024;

export async function runRenderMode(options: ExportOptions): Promise<void> {
	const state: RenderState = { status: "loading", progress: 0 };
	window.__caduRender = state;
	const marks: Record<string, number> = {};
	let last = performance.now();
	const mark = (name: string) => {
		const now = performance.now();
		marks[name] = Math.round(now - last);
		last = now;
	};
	try {
		await initializeGpuRenderer();
		mark("gpu");
		state.gpu = isGpuAvailable();
		const editor = EditorCore.getInstance();
		editor.renderer.setDegraded(!state.gpu);
		await editor.project.loadProject({ id: boot().projectId });
		mark("projeto_e_midias");
		editor.save.stop();
		// Chromium sem codecs proprietários (Linux) não codifica H.264/AAC: exporta WebM e o worker converte para MP4.
		const size = editor.project.getActive().settings.canvasSize;
		if (options.format === "mp4") {
			const [video, audio] = await Promise.all([
				canEncodeVideo("avc", { width: size.width, height: size.height }),
				canEncodeAudio("aac"),
			]);
			if (!video || !audio || window.CADU_VIDEO_EDITOR?.simulateNoH264) options = { ...options, format: "webm" };
		}
		state.format = options.format;
		state.status = "rendering";
		const unsubscribe = editor.project.subscribe?.(() => {
			state.progress = editor.project.getExportState().progress;
		});
		const result = await editor.project.export({ options });
		unsubscribe?.();
		mark("export");
		state.timings = marks;
		state.stats = { ...exportStats };
		if (!result.success || !result.buffer) throw new Error(result.error || "Exportação sem resultado.");
		const bytes = new Uint8Array(result.buffer);
		window.__caduRenderChunks = Math.ceil(bytes.length / CHUNK);
		window.__caduRenderChunk = (index) => {
			const slice = bytes.subarray(index * CHUNK, (index + 1) * CHUNK);
			let binary = "";
			for (let offset = 0; offset < slice.length; offset += 0x8000) {
				binary += String.fromCharCode(...slice.subarray(offset, offset + 0x8000));
			}
			return btoa(binary);
		};
		state.progress = 1;
		state.status = "done";
	} catch (error) {
		state.status = "error";
		state.error = error instanceof Error ? error.message : String(error);
	}
}
