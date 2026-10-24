// Exportação no navegador (GPU de quem edita) e envio do arquivo para a biblioteca da marca no Studio.
// O render no servidor continua existindo só para automação (agente, lote); não aparece aqui.
import { useRef, useState } from "react";
import { canEncodeAudio, canEncodeVideo } from "mediabunny";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { useEditor } from "@/editor/use-editor";
import type { ExportFormat, ExportQuality } from "@/export";
import { editorUrl } from "./api";
import { boot } from "./config";

type Step =
	| { kind: "idle" }
	| { kind: "exporting"; progress: number }
	| { kind: "uploading"; progress: number }
	| { kind: "converting" }
	| { kind: "done"; name: string; savedAs: string }
	| { kind: "error"; message: string };

// "Alta" usa very_high: em 1080p fica acima de 5 Mb/s mesmo no codificador por hardware do navegador.
const QUALITIES: { value: ExportQuality; label: string }[] = [
	{ value: "very_high", label: "Alta (recomendada para redes)" },
	{ value: "high", label: "Média (arquivo menor)" },
	{ value: "medium", label: "Rascunho" },
];

async function pickFormat(width: number, height: number): Promise<ExportFormat> {
	const [video, audio] = await Promise.all([canEncodeVideo("avc", { width, height }), canEncodeAudio("aac")]);
	return video && audio ? "mp4" : "webm";
}

function upload(blob: Blob, name: string, onProgress: (value: number) => void): Promise<{ status: string; task_id?: string }> {
	const { projectId, csrfToken } = boot();
	return new Promise((resolve, reject) => {
		const form = new FormData();
		form.set("name", name);
		form.set("file", blob, name);
		const request = new XMLHttpRequest();
		request.open("POST", editorUrl(`/projects/${encodeURIComponent(projectId)}/exports`));
		request.setRequestHeader("X-Trocr-CSRF-Token", csrfToken);
		request.upload.onprogress = (event) => event.lengthComputable && onProgress(event.loaded / event.total);
		request.onload = () => {
			const payload = (() => {
				try {
					return JSON.parse(request.responseText);
				} catch {
					return null;
				}
			})();
			if (request.status >= 200 && request.status < 300 && payload?.success) resolve(payload.data);
			else reject(new Error(payload?.error || `Falha ao enviar (${request.status}).`));
		};
		request.onerror = () => reject(new Error("Conexão perdida durante o envio."));
		request.send(form);
	});
}

async function waitConversion(taskId: string): Promise<void> {
	const { apiRoot, clientId } = boot();
	const deadline = Date.now() + 20 * 60 * 1000;
	while (Date.now() < deadline) {
		await new Promise((resolve) => setTimeout(resolve, 2000));
		const response = await fetch(`${apiRoot}/format-lab/studio/tasks/${taskId}?client_id=${clientId}`, { credentials: "same-origin" });
		const payload = await response.json();
		if (!response.ok || !payload.success) throw new Error(payload.error || "Conversão indisponível.");
		if (payload.data.status === "ready") return;
		if (payload.data.status === "failed") throw new Error(payload.data.error || "A conversão falhou.");
	}
	throw new Error("A conversão passou de 20 minutos; confira a biblioteca mais tarde.");
}

function safeName(name: string): string {
	return (name || "video").replace(/[\\/:*?"<>|]+/g, " ").trim().slice(0, 100) || "video";
}

export function BrowserExportButton() {
	const editor = useEditor();
	const project = useEditor((e) => e.project.getActiveOrNull());
	const [open, setOpen] = useState(false);
	const [quality, setQuality] = useState<ExportQuality>("very_high");
	const [step, setStep] = useState<Step>({ kind: "idle" });
	const result = useRef<{ blob: Blob; name: string } | null>(null);
	const busy = step.kind === "exporting" || step.kind === "uploading" || step.kind === "converting";

	const start = async () => {
		if (!project) return;
		result.current = null;
		try {
			await editor.save.flush();
			const size = project.settings.canvasSize;
			const format = await pickFormat(size.width, size.height);
			setStep({ kind: "exporting", progress: 0 });
			const unsubscribe = editor.project.subscribe(() => {
				const state = editor.project.getExportState();
				if (state.isExporting) setStep({ kind: "exporting", progress: state.progress });
			});
			const exported = await editor.project.export({ options: { format, quality, includeAudio: true } }).finally(unsubscribe);
			if (exported.cancelled) {
				setStep({ kind: "idle" });
				return;
			}
			if (!exported.success || !exported.buffer) throw new Error(exported.error || "O navegador não conseguiu exportar.");
			const name = `${safeName(project.metadata.name)}.${format}`;
			const blob = new Blob([exported.buffer], { type: `video/${format}` });
			result.current = { blob, name };
			setStep({ kind: "uploading", progress: 0 });
			const saved = await upload(blob, name, (progress) => setStep({ kind: "uploading", progress }));
			if (saved.status === "queued" && saved.task_id) {
				setStep({ kind: "converting" });
				await waitConversion(saved.task_id);
			}
			setStep({ kind: "done", name, savedAs: format === "mp4" ? "MP4" : "MP4 (convertido no servidor)" });
		} catch (error) {
			setStep({ kind: "error", message: error instanceof Error ? error.message : String(error) });
		}
	};

	const download = () => {
		if (!result.current) return;
		const url = URL.createObjectURL(result.current.blob);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = result.current.name;
		anchor.click();
		setTimeout(() => URL.revokeObjectURL(url), 10_000);
	};

	const close = (next: boolean) => {
		if (busy && !next) {
			if (step.kind === "exporting") editor.project.cancelExport();
			else return toast.info("O envio continua; aguarde terminar.");
		}
		setOpen(next);
		if (!next && !busy) setStep({ kind: "idle" });
	};

	return (
		<>
			<Button size="sm" onClick={() => setOpen(true)} disabled={!project}>
				Exportar
			</Button>
			<Dialog open={open} onOpenChange={close}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Exportar vídeo</DialogTitle>
						<DialogDescription>
							O vídeo é gerado neste computador e salvo na biblioteca da marca no Studio.
						</DialogDescription>
					</DialogHeader>
					<DialogBody className="flex flex-col gap-4">
						{step.kind === "idle" || step.kind === "error" ? (
							<label className="flex flex-col gap-1 text-sm">
								<span>Qualidade</span>
								<select
									className="bg-background border-border h-9 rounded-md border px-2"
									value={quality}
									onChange={(event) => setQuality(event.target.value as ExportQuality)}
								>
									{QUALITIES.map((option) => (
										<option key={option.value} value={option.value}>
											{option.label}
										</option>
									))}
								</select>
							</label>
						) : null}
						{step.kind === "exporting" && <StepProgress label="Gerando o vídeo neste computador" value={step.progress} />}
						{step.kind === "uploading" && <StepProgress label="Salvando na biblioteca do Studio" value={step.progress} />}
						{step.kind === "converting" && <StepProgress label="Convertendo para MP4 no servidor" />}
						{step.kind === "done" && (
							<p className="text-sm" role="status">
								Pronto: <strong>{step.name}</strong> está na biblioteca da marca ({step.savedAs}).
							</p>
						)}
						{step.kind === "error" && (
							<p className="text-destructive text-sm" role="alert">
								{step.message}
							</p>
						)}
					</DialogBody>
					<DialogFooter>
						{step.kind === "done" ? (
							<>
								<Button variant="ghost" onClick={() => close(false)}>
									Fechar
								</Button>
								<Button onClick={download}>Baixar arquivo</Button>
							</>
						) : (
							<>
								<Button variant="ghost" onClick={() => close(false)}>
									{step.kind === "exporting" ? "Cancelar" : "Fechar"}
								</Button>
								<Button onClick={start} disabled={busy}>
									{busy ? "Exportando…" : step.kind === "error" ? "Tentar de novo" : "Exportar"}
								</Button>
							</>
						)}
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</>
	);
}

function StepProgress({ label, value }: { label: string; value?: number }) {
	return (
		<div className="flex flex-col gap-2 text-sm" aria-busy="true">
			<span>
				{label}
				{value !== undefined ? ` · ${Math.round(value * 100)}%` : "…"}
			</span>
			<Progress value={value !== undefined ? value * 100 : undefined} />
		</div>
	);
}
