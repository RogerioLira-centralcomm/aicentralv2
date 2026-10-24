// Aba Texto: títulos prontos nas cores e na fonte da marca, com tamanho proporcional ao formato do quadro.
import { useEffect, useState } from "react";
import { PanelView } from "@/components/editor/panels/assets/views/base-panel";
import { useEditor } from "@/editor/use-editor";
import { DEFAULTS } from "@/timeline/defaults";
import { buildTextElement } from "@/timeline/element-utils";
import { mediaTimeFromSeconds, type MediaTime } from "@/wasm";
import { caduFetch } from "./api";

type Brand = { name: string; primary: string; secondary: string; font: string; configured: boolean };

const FONT_SIZE_REFERENCE = 90; // OpenCut: pixels = fontSize × altura do quadro / 90

type Preset = {
	id: string;
	label: string;
	sample: string;
	// Tamanho da letra como fração do lado menor do quadro; y como fração da altura (0 topo, 1 base).
	size: number;
	y: number;
	bold?: boolean;
	align?: "left" | "center";
	style: (brand: Brand) => { color: string; background?: string };
};

function ink(background: string): string {
	const [r, g, b] = [1, 3, 5].map((i) => parseInt(background.slice(i, i + 2), 16) / 255);
	return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 ? "#111111" : "#ffffff";
}

const PRESETS: Preset[] = [
	{ id: "title", label: "Título", sample: "Seu título aqui", size: 0.085, y: 0.2, bold: true, style: () => ({ color: "#ffffff" }) },
	{ id: "title-box", label: "Título com caixa", sample: "Novidade", size: 0.075, y: 0.2, bold: true,
		style: (brand) => ({ color: ink(brand.primary), background: brand.primary }) },
	{ id: "subtitle", label: "Subtítulo", sample: "Texto de apoio curto", size: 0.05, y: 0.28, style: () => ({ color: "#e6e8ec" }) },
	{ id: "cta", label: "Chamada (CTA)", sample: "Saiba mais", size: 0.06, y: 0.72, bold: true,
		style: (brand) => ({ color: ink(brand.secondary), background: brand.secondary }) },
	{ id: "lower-third", label: "Nome e cargo", sample: "Nome Sobrenome", size: 0.045, y: 0.68, align: "left", bold: true,
		style: (brand) => ({ color: ink(brand.primary), background: brand.primary }) },
	{ id: "highlight", label: "Destaque", sample: "50% OFF", size: 0.11, y: 0.5, bold: true, style: (brand) => ({ color: brand.secondary }) },
	{ id: "caption", label: "Legenda", sample: "Frase falada no vídeo", size: 0.045, y: 0.66, bold: true,
		style: () => ({ color: "#ffffff", background: "#000000" }) },
];

export function CaduTextView() {
	const editor = useEditor();
	const [brand, setBrand] = useState<Brand>({ name: "", primary: "#1dbf73", secondary: "#4c8dff", font: "", configured: false });

	useEffect(() => {
		caduFetch<Brand>("/brand").then(setBrand).catch(() => undefined);
	}, []);

	const add = (preset: Preset, currentTime: MediaTime) => {
		const project = editor.project.getActive();
		const { width, height } = project.settings.canvasSize;
		const pixels = preset.size * Math.min(width, height);
		const { color, background } = preset.style(brand);
		const left = preset.align === "left";
		const element = buildTextElement({
			raw: {
				...DEFAULTS.text.element,
				name: preset.label,
				duration: mediaTimeFromSeconds({ seconds: 3 }),
				params: {
					...DEFAULTS.text.element.params,
					content: preset.sample,
					fontSize: Math.round((pixels * FONT_SIZE_REFERENCE * 100) / height) / 100,
					fontFamily: brand.font || "Arial",
					fontWeight: preset.bold ? "bold" : "normal",
					color,
					textAlign: left ? "left" : "center",
					"background.enabled": Boolean(background),
					"background.color": background ?? "#000000",
					"background.cornerRadius": background ? Math.round(pixels * 0.25) : 0,
					"background.paddingX": Math.round(pixels * 0.45),
					"background.paddingY": Math.round(pixels * 0.25),
					// Nome e cargo: caixa deslocada para a esquerda, como um lower third.
					"transform.positionX": left ? -0.2 * width : 0,
					"transform.positionY": (preset.y - 0.5) * height,
				},
			},
			startTime: currentTime,
		});
		editor.timeline.insertElement({ element, placement: { mode: "auto", trackType: "text" } });
	};

	return (
		<PanelView title="Texto">
			<div className="flex flex-col gap-2 px-3 pb-3">
				<p className="text-muted-foreground text-xs">
					{brand.configured ? `Nas cores de ${brand.name || "sua marca"}.` : "Cores padrão do Studio (marca sem cores cadastradas)."} Clique para pôr no playhead.
				</p>
				<div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
					{PRESETS.map((preset) => {
						const { color, background } = preset.style(brand);
						return (
							<button
								key={preset.id}
								type="button"
								className="border-border hover:border-primary flex aspect-video flex-col items-center justify-center gap-1 rounded-md border bg-[#16181d] p-2 text-center transition-colors"
								onClick={() => add(preset, editor.playback.getCurrentTime())}
								aria-label={`Adicionar ${preset.label}`}
							>
								<span
									className="line-clamp-2 max-w-full rounded px-1.5 text-[11px] leading-tight break-words"
									style={{ color, background, fontWeight: preset.bold ? 700 : 400, fontFamily: brand.font || undefined }}
								>
									{preset.sample}
								</span>
								<span className="text-muted-foreground text-[10px]">{preset.label}</span>
							</button>
						);
					})}
				</div>
			</div>
		</PanelView>
	);
}
