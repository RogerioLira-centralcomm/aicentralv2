// Chamadas à Editor API do Studio (Flask). Mesma sessão, CSRF e escopo de marca do restante do Studio.
import { boot } from "./config";

export class CaduApiError extends Error {
	constructor(
		message: string,
		readonly status: number,
		readonly code?: string,
	) {
		super(message);
	}
}

export function editorUrl(path: string, params: Record<string, string> = {}): string {
	const { apiRoot, clientId } = boot();
	const url = new URL(`${apiRoot}/format-lab/studio/video-editor${path}`, window.location.origin);
	url.searchParams.set("client_id", String(clientId));
	for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
	return url.pathname + url.search;
}

export async function caduFetch<T>(path: string, init: RequestInit = {}, params?: Record<string, string>): Promise<T> {
	const { csrfToken } = boot();
	const headers = new Headers(init.headers);
	headers.set("X-Trocr-CSRF-Token", csrfToken);
	if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
	const response = await fetch(editorUrl(path, params), { ...init, headers, credentials: "same-origin" });
	const payload = await response.json().catch(() => null);
	if (!response.ok || !payload?.success) {
		throw new CaduApiError(payload?.error || `Falha na Editor API (${response.status}).`, response.status, payload?.code);
	}
	return payload.data as T;
}
