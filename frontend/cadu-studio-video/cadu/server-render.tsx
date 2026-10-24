// Render final no servidor: grava a timeline, pede o render da revisão salva e acompanha a tarefa do Studio.
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useEditor } from "@/editor/use-editor";
import { caduFetch } from "./api";
import { boot } from "./config";

type Task = { id: string; status: "queued" | "processing" | "ready" | "failed"; stage?: string; error?: string; result?: { url: string } };

async function taskStatus(id: string): Promise<Task> {
	const { apiRoot, clientId } = boot();
	const response = await fetch(`${apiRoot}/format-lab/studio/tasks/${id}?client_id=${clientId}`, { credentials: "same-origin" });
	const payload = await response.json();
	if (!response.ok || !payload.success) throw new Error(payload.error || "Tarefa indisponível.");
	return payload.data;
}

export function ServerRenderButton() {
	const editor = useEditor();
	const [task, setTask] = useState<Task | null>(null);
	const [startedAt, setStartedAt] = useState(0);
	const [, tick] = useState(0);
	const timer = useRef<number | null>(null);

	useEffect(() => () => void (timer.current && window.clearTimeout(timer.current)), []);

	const poll = (id: string) => {
		timer.current = window.setTimeout(async () => {
			try {
				const next = await taskStatus(id);
				setTask(next);
				tick((value) => value + 1);
				if (next.status === "ready" && next.result) {
					window.location.assign(next.result.url);
					toast.success("Vídeo renderizado no servidor");
				} else if (next.status === "failed") {
					toast.error("Render falhou", { description: next.error });
				} else {
					poll(id);
				}
			} catch (error) {
				toast.error("Render indisponível", { description: (error as Error).message });
				setTask(null);
			}
		}, 1500);
	};

	const start = async () => {
		try {
			await editor.save.flush();
			const { projectId } = boot();
			const created = await caduFetch<Task>(`/projects/${encodeURIComponent(projectId)}/renders`, {
				method: "POST",
				body: JSON.stringify({ format: "mp4", quality: "high" }),
			});
			setTask(created);
			setStartedAt(Date.now());
			poll(created.id);
		} catch (error) {
			toast.error("Não foi possível iniciar o render", { description: (error as Error).message });
		}
	};

	const busy = task !== null && (task.status === "queued" || task.status === "processing");
	const seconds = busy ? Math.floor((Date.now() - startedAt) / 1000) : 0;
	return (
		<Button variant="secondary" size="sm" onClick={start} disabled={busy} aria-busy={busy}>
			{busy ? `${task?.stage || "Na fila"} · ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}` : "Renderizar no servidor"}
		</Button>
	);
}
