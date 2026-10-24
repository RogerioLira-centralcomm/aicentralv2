// Substitui next/navigation. Rotas do OpenCut (/projects, /editor/:id) voltam para o Studio.
import { studioExitUrl, studioEditorUrl } from "../cadu/config";

function resolve(path: string): string {
	const match = path.match(/^\/editor\/([^/?#]+)/);
	if (match) return studioEditorUrl(match[1]);
	if (path === "/" || path.startsWith("/projects")) return studioExitUrl();
	return path;
}

export function useRouter() {
	return {
		push: (path: string) => window.location.assign(resolve(path)),
		replace: (path: string) => window.location.replace(resolve(path)),
		back: () => window.history.back(),
		refresh: () => window.location.reload(),
		prefetch: () => undefined,
	};
}

export function useParams<T = Record<string, string>>(): T {
	return {} as T;
}

export function usePathname(): string {
	return window.location.pathname;
}

export function useSearchParams(): URLSearchParams {
	return new URLSearchParams(window.location.search);
}
