// Dados que a página Flask injeta em window.CADU_VIDEO_EDITOR (marca, projeto, CSRF, rotas).
export interface CaduEditorBoot {
	clientId: number;
	projectId: string;
	projectName?: string;
	apiRoot: string;
	csrfToken: string;
	exitUrl: string;
	editorUrl: string;
	renderMode?: boolean;
	renderOptions?: import("@/export").ExportOptions;
	/** Só para o teste de render: simula Chromium sem H.264/AAC. */
	simulateNoH264?: boolean;
}

declare global {
	interface Window {
		CADU_VIDEO_EDITOR?: CaduEditorBoot;
	}
}

export function boot(): CaduEditorBoot {
	const data = window.CADU_VIDEO_EDITOR;
	if (!data || !data.clientId) throw new Error("Editor sem marca: abra pelo Studio.");
	return data;
}

export function studioExitUrl(): string {
	return window.CADU_VIDEO_EDITOR?.exitUrl || "/studio";
}

export function studioEditorUrl(projectId: string): string {
	const base = window.CADU_VIDEO_EDITOR?.editorUrl || "/studio/video/editor";
	const url = new URL(base, window.location.origin);
	url.searchParams.set("project", projectId);
	url.searchParams.set("client_id", String(window.CADU_VIDEO_EDITOR?.clientId || ""));
	return url.pathname + url.search;
}
