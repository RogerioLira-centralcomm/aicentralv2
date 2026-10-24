// Aba Áudio: sons da biblioteca do Studio (áudios da marca e efeitos CC0) no lugar da busca externa do OpenCut,
// que dependia de uma API que não existe aqui. "+" vincula o som ao projeto e coloca no playhead.
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { HugeiconsIcon } from "@hugeicons/react";
import { PauseIcon, PlayIcon, PlusSignIcon } from "@hugeicons/core-free-icons";
import { PanelView } from "@/components/editor/panels/assets/views/base-panel";
import { Button } from "@/components/ui/button";
import { useEditor } from "@/editor/use-editor";
import { buildElementFromMedia } from "@/timeline/element-utils";
import { mediaTimeFromSeconds } from "@/wasm";
import { caduFetch } from "./api";
import { boot } from "./config";
import { forgetMediaLinks } from "./storage";

type Sound = { ref: string; kind: string; name: string; duration?: number; source: string; preview_url?: string; category?: string };

const FILTERS = [
	{ key: "all", label: "Todos" },
	{ key: "brand", label: "Da marca" },
	{ key: "effect", label: "Efeitos" },
];

export function CaduSoundsView() {
	const editor = useEditor();
	const [items, setItems] = useState<Sound[] | null>(null);
	const [query, setQuery] = useState("");
	const [filter, setFilter] = useState("all");
	const [playing, setPlaying] = useState<string | null>(null);
	const [adding, setAdding] = useState<string | null>(null);
	const audio = useRef<HTMLAudioElement | null>(null);

	useEffect(() => {
		caduFetch<{ items: Sound[] }>("/library")
			.then((data) => setItems(data.items.filter((item) => item.kind === "audio")))
			.catch((error) => {
				toast.error("Sons indisponíveis", { description: error.message });
				setItems([]);
			});
		return () => audio.current?.pause();
	}, []);

	const visible = useMemo(() => {
		const words = query.trim().toLowerCase();
		return (items ?? []).filter((item) => {
			if (filter === "brand" && !item.ref.startsWith("sound:")) return false;
			if (filter === "effect" && !item.ref.startsWith("public-sound:")) return false;
			return !words || item.name.toLowerCase().includes(words);
		});
	}, [items, query, filter]);

	const toggle = (item: Sound) => {
		if (!item.preview_url) return;
		if (playing === item.ref) {
			audio.current?.pause();
			setPlaying(null);
			return;
		}
		audio.current?.pause();
		const player = new Audio(item.preview_url);
		player.onended = () => setPlaying(null);
		player.play().catch(() => setPlaying(null));
		audio.current = player;
		setPlaying(item.ref);
	};

	const add = async (item: Sound) => {
		const { projectId } = boot();
		setAdding(item.ref);
		try {
			const linked = await caduFetch<{ id: string; name: string; duration?: number }>(
				`/projects/${encodeURIComponent(projectId)}/media/link`,
				{ method: "POST", body: JSON.stringify({ ref: item.ref }) },
			);
			forgetMediaLinks(projectId);
			await editor.media.loadProjectMedia({ projectId });
			const element = buildElementFromMedia({
				mediaId: linked.id,
				mediaType: "audio",
				name: linked.name,
				duration: mediaTimeFromSeconds({ seconds: linked.duration || item.duration || 1 }),
				startTime: editor.playback.getCurrentTime(),
			});
			editor.timeline.insertElement({ element, placement: { mode: "auto", trackType: "audio" } });
		} catch (error) {
			toast.error("Não foi possível adicionar o som", { description: (error as Error).message });
		} finally {
			setAdding(null);
		}
	};

	return (
		<PanelView title="Áudio">
			<div className="flex flex-col gap-2 px-3 pb-3">
				<input
					className="bg-input border-border h-8 rounded-md border px-2 text-sm"
					placeholder="Buscar som…"
					value={query}
					onChange={(event) => setQuery(event.target.value)}
					aria-label="Buscar som"
				/>
				<div className="flex gap-1">
					{FILTERS.map((option) => (
						<Button
							key={option.key}
							size="sm"
							variant={filter === option.key ? "secondary" : "ghost"}
							className="h-7 px-2 text-xs"
							onClick={() => setFilter(option.key)}
						>
							{option.label}
						</Button>
					))}
				</div>
				<p className="text-muted-foreground text-xs">Para músicas da marca, use Importar na aba Mídia.</p>
				{items === null ? (
					<p className="text-muted-foreground text-sm">Carregando sons…</p>
				) : visible.length === 0 ? (
					<p className="text-muted-foreground text-sm">Nenhum som encontrado.</p>
				) : (
					<ul className="flex flex-col gap-1">
						{visible.map((item) => (
							<li key={item.ref} className="hover:bg-accent flex items-center gap-2 rounded-md px-1 py-1">
								<Button
									variant="ghost"
									size="icon"
									className="size-7 shrink-0"
									aria-label={playing === item.ref ? `Pausar ${item.name}` : `Ouvir ${item.name}`}
									onClick={() => toggle(item)}
									disabled={!item.preview_url}
								>
									<HugeiconsIcon icon={playing === item.ref ? PauseIcon : PlayIcon} className="size-4" />
								</Button>
								<div className="min-w-0 flex-1">
									<p className="truncate text-sm">{item.name}</p>
									<p className="text-muted-foreground truncate text-xs">
										{item.source}
										{item.duration ? ` · ${item.duration.toFixed(1)} s` : ""}
									</p>
								</div>
								<Button
									variant="ghost"
									size="icon"
									className="size-7 shrink-0"
									aria-label={`Adicionar ${item.name} no playhead`}
									disabled={adding !== null}
									onClick={() => add(item)}
								>
									<HugeiconsIcon icon={PlusSignIcon} className="size-4" />
								</Button>
							</li>
						))}
					</ul>
				)}
			</div>
		</PanelView>
	);
}
