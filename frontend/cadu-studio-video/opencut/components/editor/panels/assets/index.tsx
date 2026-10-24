"use client";

import { Separator } from "@/components/ui/separator";
import { type Tab, useAssetsPanelStore } from "@/components/editor/panels/assets/assets-panel-store";
import { TabBar } from "./tabbar";
import { Captions } from "@/subtitles/components/assets-view";
import { MediaView } from "./views/assets";
import { SettingsView } from "./views/settings";
import { CaduSoundsView } from "../../../../../cadu/sounds-view";
import { CaduTextView } from "../../../../../cadu/titles-view";
import { EffectsView } from "@/effects/components/assets-view";

export function AssetsPanel() {
	const { activeTab } = useAssetsPanelStore();

	// Cadu: Áudio e Texto com sons e títulos do Studio; abas vazias do OpenCut removidas.
	const viewMap: Record<Tab, React.ReactNode> = {
		media: <MediaView />,
		sounds: <CaduSoundsView />,
		text: <CaduTextView />,
		effects: <EffectsView />,
		captions: <Captions />,
		settings: <SettingsView />,
	};

	return (
		<div className="panel bg-background flex h-full rounded-sm border overflow-hidden">
			<TabBar />
			<Separator orientation="vertical" />
			<div className="flex-1 overflow-hidden">{viewMap[activeTab]}</div>
		</div>
	);
}
