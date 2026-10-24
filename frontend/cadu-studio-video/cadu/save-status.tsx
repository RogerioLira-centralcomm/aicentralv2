// Estado do salvamento no Studio, mostrado no cabeçalho do editor.
import { useSyncExternalStore } from "react";

export type SaveState =
	| { state: "idle" }
	| { state: "saving" }
	| { state: "saved"; revision: number }
	| { state: "conflict"; message: string }
	| { state: "error"; message: string };

let current: SaveState = { state: "idle" };
const listeners = new Set<() => void>();

export function notifySave(next: SaveState): void {
	current = next;
	for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
	listeners.add(listener);
	return () => listeners.delete(listener);
}

const LABELS: Record<SaveState["state"], string> = {
	idle: "",
	saving: "Salvando…",
	saved: "Salvo no Studio",
	conflict: "Alterado em outra aba",
	error: "Falha ao salvar",
};

export function SaveStatus() {
	const save = useSyncExternalStore(subscribe, () => current);
	if (save.state === "idle") return null;
	const tone = save.state === "conflict" || save.state === "error" ? "text-destructive" : "text-muted-foreground";
	const title = "message" in save ? save.message : save.state === "saved" ? `Revisão ${save.revision}` : undefined;
	return (
		<span className={`text-xs ${tone}`} title={title} role="status">
			{LABELS[save.state]}
		</span>
	);
}
