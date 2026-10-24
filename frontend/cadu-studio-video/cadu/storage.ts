// Adaptadores que trocam IndexedDB/OPFS do OpenCut pelo Studio: o projeto é o projeto do Studio
// (com revisões) e cada mídia é um item da biblioteca da marca, enviado pelo upload validado no servidor.
import type { MediaAssetData, SerializedProject, StorageAdapter } from "@/services/storage/types";
import { caduFetch, CaduApiError } from "./api";
import { notifySave } from "./save-status";

const revisions = new Map<string, number>();
const saving = new Map<string, Promise<void>>();

type ProjectResponse = { revision: number; project: SerializedProject | null };

export class CaduProjectsAdapter implements StorageAdapter<SerializedProject> {
	async get(key: string): Promise<SerializedProject | null> {
		const data = await caduFetch<ProjectResponse>(`/projects/${encodeURIComponent(key)}`);
		revisions.set(key, data.revision);
		return data.project;
	}

	// Uma gravação por vez: duas em paralelo levariam a mesma revisão e a segunda viraria um falso conflito.
	async set({ key, value }: { key: string; value: SerializedProject }): Promise<void> {
		const previous = saving.get(key) ?? Promise.resolve();
		const next = previous.catch(() => undefined).then(() => this.save(key, value));
		saving.set(key, next);
		return next;
	}

	private async save(key: string, value: SerializedProject): Promise<void> {
		notifySave({ state: "saving" });
		try {
			const data = await caduFetch<{ revision: number }>(`/projects/${encodeURIComponent(key)}`, {
				method: "PUT",
				body: JSON.stringify({ expected_revision: revisions.get(key) ?? 0, project: value }),
			});
			revisions.set(key, data.revision);
			notifySave({ state: "saved", revision: data.revision });
		} catch (error) {
			const conflict = error instanceof CaduApiError && error.code === "revision_conflict";
			notifySave({ state: conflict ? "conflict" : "error", message: (error as Error).message });
			throw error;
		}
	}

	async remove(): Promise<void> {
		throw new Error("Projetos são excluídos pelo Studio.");
	}

	async list(): Promise<string[]> {
		const data = await caduFetch<{ items: { id: string }[] }>("/projects");
		return data.items.map((item) => item.id);
	}

	async clear(): Promise<void> {
		throw new Error("Projetos são excluídos pelo Studio.");
	}
}

export type CaduMediaLink = MediaAssetData & { ref: string; contentUrl: string; libraryKind: string };

// Arquivos enviados nesta aba ficam guardados até o servidor confirmar o vínculo,
// para o adaptador de metadados mandar os dois juntos (o OpenCut grava arquivo e metadados em duas chamadas).
const pendingFiles = new Map<string, File>();

export class CaduMediaFilesAdapter implements StorageAdapter<File> {
	constructor(private readonly projectId: string) {}

	async get(key: string): Promise<File | null> {
		const link = await mediaLink(this.projectId, key);
		if (!link) return null;
		const response = await fetch(link.contentUrl, { credentials: "same-origin" });
		if (!response.ok) return null;
		const blob = await response.blob();
		return new File([blob], link.name, { type: blob.type, lastModified: link.lastModified });
	}

	async set({ key, value }: { key: string; value: File }): Promise<void> {
		pendingFiles.set(key, value);
	}

	async remove(key: string): Promise<void> {
		pendingFiles.delete(key);
		await caduFetch(`/projects/${encodeURIComponent(this.projectId)}/media/${encodeURIComponent(key)}`, { method: "DELETE" });
		linkCache.delete(this.projectId);
	}

	async list(): Promise<string[]> {
		return (await mediaLinks(this.projectId)).map((link) => link.id);
	}

	async clear(): Promise<void> {
		for (const key of await this.list()) await this.remove(key);
	}
}

export class CaduMediaMetadataAdapter implements StorageAdapter<MediaAssetData> {
	constructor(private readonly projectId: string) {}

	async get(key: string): Promise<MediaAssetData | null> {
		return mediaLink(this.projectId, key);
	}

	async set({ key, value }: { key: string; value: MediaAssetData }): Promise<void> {
		const file = pendingFiles.get(key);
		if (!file) return; // vínculo vindo da biblioteca do Studio já existe no servidor
		const form = new FormData();
		form.set("asset_id", key);
		form.set("name", value.name);
		form.set("type", value.type);
		form.set("file", file, value.name);
		try {
			await caduFetch(`/projects/${encodeURIComponent(this.projectId)}/media`, { method: "POST", body: form });
		} finally {
			pendingFiles.delete(key);
			linkCache.delete(this.projectId);
		}
	}

	async remove(key: string): Promise<void> {
		await new CaduMediaFilesAdapter(this.projectId).remove(key);
	}

	async list(): Promise<string[]> {
		return (await mediaLinks(this.projectId)).map((link) => link.id);
	}

	async clear(): Promise<void> {
		await new CaduMediaFilesAdapter(this.projectId).clear();
	}
}

const linkCache = new Map<string, Promise<CaduMediaLink[]>>();

export function mediaLinks(projectId: string): Promise<CaduMediaLink[]> {
	let cached = linkCache.get(projectId);
	if (!cached) {
		cached = caduFetch<{ items: CaduMediaLink[] }>(`/projects/${encodeURIComponent(projectId)}/media`).then((data) => data.items);
		cached.catch(() => linkCache.delete(projectId));
		linkCache.set(projectId, cached);
	}
	return cached;
}

export function forgetMediaLinks(projectId: string): void {
	linkCache.delete(projectId);
}

async function mediaLink(projectId: string, id: string): Promise<CaduMediaLink | null> {
	return (await mediaLinks(projectId)).find((link) => link.id === id) ?? null;
}
