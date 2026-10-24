// Legendas pelo Whisper do worker, no lugar do modelo ONNX que o OpenCut baixava para o navegador.
import type { TranscriptionResult } from "@/transcription/types";
import { caduFetch } from "./api";
import { boot } from "./config";

type Task = {
	status: "queued" | "processing" | "ready" | "failed";
	stage?: string;
	error?: string;
	result?: { captions: { start: number; end: number; text: string }[]; language: string };
};

export async function transcribeOnServer({
	audioBlob,
	language,
	onStep,
}: {
	audioBlob: Blob;
	language?: string;
	onStep: (step: string) => void;
}): Promise<TranscriptionResult> {
	const { apiRoot, clientId, projectId } = boot();
	const form = new FormData();
	form.set("file", audioBlob, "timeline.wav");
	if (language) form.set("language", language);
	onStep("Enviando áudio…");
	const created = await caduFetch<{ id: string }>(`/projects/${encodeURIComponent(projectId)}/transcriptions`, {
		method: "POST",
		body: form,
	});
	for (;;) {
		await new Promise((resolve) => setTimeout(resolve, 1500));
		const response = await fetch(`${apiRoot}/format-lab/studio/tasks/${created.id}?client_id=${clientId}`, { credentials: "same-origin" });
		const payload = await response.json();
		if (!response.ok || !payload.success) throw new Error(payload.error || "Transcrição indisponível.");
		const task: Task = payload.data;
		if (task.status === "failed") throw new Error(task.error || "A transcrição falhou.");
		if (task.status === "ready" && task.result) {
			const segments = task.result.captions.map(({ start, end, text }) => ({ start, end, text }));
			return { text: segments.map((segment) => segment.text).join(" "), segments, language: task.result.language };
		}
		onStep(task.status === "queued" ? "Na fila…" : "Transcrevendo no servidor…");
	}
}
