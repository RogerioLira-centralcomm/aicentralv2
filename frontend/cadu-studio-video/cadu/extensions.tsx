// Extensões do servidor (manifesto em Python) e biblioteca do Studio, no cabeçalho do editor.
// Cada extensão devolve comandos que a Editor API aplica no projeto salvo; o editor recarrega a revisão nova.
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useEditor } from "@/editor/use-editor";
import { caduFetch } from "./api";
import { boot } from "./config";
import { forgetMediaLinks } from "./storage";

type ExtensionParam = {
	key: string;
	label: string;
	type: "text" | "number" | "select" | "color" | "media";
	default?: string | number;
	options?: { value: string; label: string }[];
	min?: number;
	max?: number;
	media_kind?: "video" | "audio" | "image";
};

type Extension = { id: string; name: string; description: string; group: string; params: ExtensionParam[] };

type LibraryItem = { ref: string; kind: "video" | "audio" | "image"; name: string; poster_url?: string; duration?: number; source: string };

const FLASH_KEY = "cadu-video-editor-flash";

// O OpenCut só carrega projeto antes de montar o editor; trocar a timeline com ele montado desmonta a árvore.
// Mudanças feitas no servidor recarregam a página e o aviso aparece depois.
export function reloadWithMessage(title: string, description?: string) {
	try {
		sessionStorage.setItem(FLASH_KEY, JSON.stringify({ title, description }));
	} catch {
		// sem sessionStorage o aviso some, a recarga continua
	}
	window.location.reload();
}

export function showPendingMessage() {
	try {
		const raw = sessionStorage.getItem(FLASH_KEY);
		if (!raw) return;
		sessionStorage.removeItem(FLASH_KEY);
		const { title, description } = JSON.parse(raw);
		toast.success(title, { description });
	} catch {
		// aviso perdido não impede abrir o editor
	}
}

export function ExtensionsMenu() {
	const editor = useEditor();
	const [extensions, setExtensions] = useState<Extension[]>([]);
	const [active, setActive] = useState<Extension | null>(null);
	const [libraryOpen, setLibraryOpen] = useState(false);

	useEffect(() => {
		caduFetch<{ items: Extension[] }>("/extensions")
			.then((data) => setExtensions(data.items))
			.catch((error) => toast.error("Extensões indisponíveis", { description: error.message }));
	}, []);

	const run = async (extension: Extension, params: Record<string, unknown>) => {
		const { projectId } = boot();
		await editor.save.flush();
		const result = await caduFetch<{ revision: number; summary: string }>(
			`/projects/${encodeURIComponent(projectId)}/extensions/${encodeURIComponent(extension.id)}/run`,
			{ method: "POST", body: JSON.stringify({ params }) },
		);
		reloadWithMessage(extension.name, result.summary);
	};

	const groups = [...new Set(extensions.map((item) => item.group))];
	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" size="sm">
						Cadu
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="z-100 w-64">
					<DropdownMenuItem onClick={() => setLibraryOpen(true)}>Biblioteca do Studio…</DropdownMenuItem>
					{groups.map((group) => (
						<div key={group}>
							<DropdownMenuSeparator />
							<DropdownMenuLabel>{group}</DropdownMenuLabel>
							{extensions
								.filter((item) => item.group === group)
								.map((item) => (
									<DropdownMenuItem key={item.id} onClick={() => setActive(item)}>
										{item.name}
									</DropdownMenuItem>
								))}
						</div>
					))}
				</DropdownMenuContent>
			</DropdownMenu>
			{active && <ExtensionDialog extension={active} onClose={() => setActive(null)} onRun={run} />}
			<LibraryDialog open={libraryOpen} onOpenChange={setLibraryOpen} />
		</>
	);
}

function ExtensionDialog({
	extension,
	onClose,
	onRun,
}: {
	extension: Extension;
	onClose: () => void;
	onRun: (extension: Extension, params: Record<string, unknown>) => Promise<void>;
}) {
	const editor = useEditor();
	const assets = useEditor((e) => e.media.getAssets());
	const [values, setValues] = useState<Record<string, unknown>>(() =>
		Object.fromEntries(extension.params.map((param) => [param.key, param.default ?? ""])),
	);
	const [busy, setBusy] = useState(false);

	const submit = async () => {
		setBusy(true);
		try {
			await onRun(extension, { ...values, playhead_seconds: editor.playback.getCurrentTime() / 120000 });
			onClose();
		} catch (error) {
			toast.error(extension.name, { description: (error as Error).message });
		} finally {
			setBusy(false);
		}
	};

	return (
		<Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{extension.name}</DialogTitle>
					<DialogDescription>{extension.description}</DialogDescription>
				</DialogHeader>
				<DialogBody className="flex flex-col gap-3">
					{extension.params.map((param) => (
						<label key={param.key} className="flex flex-col gap-1 text-sm">
							<span>{param.label}</span>
							{param.type === "select" || param.type === "media" ? (
								<select
									className="bg-background border-border h-9 rounded-md border px-2"
									value={String(values[param.key] ?? "")}
									onChange={(event) => setValues({ ...values, [param.key]: event.target.value })}
								>
									<option value="">Escolha…</option>
									{(param.type === "media"
										? assets
												.filter((asset) => !param.media_kind || asset.type === param.media_kind)
												.map((asset) => ({ value: asset.id, label: asset.name }))
										: (param.options ?? [])
									).map((option) => (
										<option key={option.value} value={option.value}>
											{option.label}
										</option>
									))}
								</select>
							) : (
								<input
									className="bg-background border-border h-9 rounded-md border px-2"
									type={param.type === "number" ? "number" : param.type === "color" ? "color" : "text"}
									min={param.min}
									max={param.max}
									value={String(values[param.key] ?? "")}
									onChange={(event) =>
										setValues({
											...values,
											[param.key]: param.type === "number" ? Number(event.target.value) : event.target.value,
										})
									}
								/>
							)}
						</label>
					))}
				</DialogBody>
				<DialogFooter>
					<Button variant="ghost" onClick={onClose} disabled={busy}>
						Cancelar
					</Button>
					<Button onClick={submit} disabled={busy}>
						{busy ? "Aplicando…" : "Aplicar"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}

function LibraryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
	const editor = useEditor();
	const [items, setItems] = useState<LibraryItem[] | null>(null);
	const [adding, setAdding] = useState<string | null>(null);

	useEffect(() => {
		if (!open) return;
		setItems(null);
		caduFetch<{ items: LibraryItem[] }>("/library")
			.then((data) => setItems(data.items))
			.catch((error) => {
				toast.error("Biblioteca indisponível", { description: error.message });
				setItems([]);
			});
	}, [open]);

	const add = async (item: LibraryItem) => {
		const { projectId } = boot();
		setAdding(item.ref);
		try {
			await caduFetch(`/projects/${encodeURIComponent(projectId)}/media/link`, {
				method: "POST",
				body: JSON.stringify({ ref: item.ref }),
			});
			forgetMediaLinks(projectId);
			await editor.media.loadProjectMedia({ projectId });
			toast.success("Adicionado às mídias do projeto", { description: item.name });
		} catch (error) {
			toast.error("Não foi possível adicionar", { description: (error as Error).message });
		} finally {
			setAdding(null);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-3xl">
				<DialogHeader>
					<DialogTitle>Biblioteca do Studio</DialogTitle>
					<DialogDescription>Vídeos, imagens e áudios desta marca, incluindo os gerados no Studio.</DialogDescription>
				</DialogHeader>
				<DialogBody>
					{items === null ? (
						<p className="text-muted-foreground text-sm">Carregando…</p>
					) : items.length === 0 ? (
						<p className="text-muted-foreground text-sm">Nenhuma mídia nesta marca ainda.</p>
					) : (
						<ul className="grid max-h-[60vh] grid-cols-3 gap-3 overflow-y-auto">
							{items.map((item) => (
								<li key={item.ref}>
									<button
										type="button"
										className="border-border hover:bg-accent flex w-full flex-col gap-1 rounded-md border p-2 text-left text-xs disabled:opacity-50"
										disabled={adding !== null}
										onClick={() => add(item)}
									>
										{item.poster_url ? (
											<img src={item.poster_url} alt="" className="aspect-video w-full rounded object-cover" />
										) : (
											<div className="bg-accent text-muted-foreground flex aspect-video w-full items-center justify-center rounded">
												{item.kind === "audio" ? "Áudio" : item.kind}
											</div>
										)}
										<span className="truncate font-medium">{item.name}</span>
										<span className="text-muted-foreground">
											{item.source}
											{item.duration ? ` · ${item.duration.toFixed(1)} s` : ""}
										</span>
									</button>
								</li>
							))}
						</ul>
					)}
				</DialogBody>
			</DialogContent>
		</Dialog>
	);
}
