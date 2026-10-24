// Cabeçalho do editor no Studio: volta ao Studio, nome do projeto, atalhos e exportação.
import { useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowLeft01Icon, CommandIcon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { ShortcutsDialog } from "@/actions/components/shortcuts-dialog";
import { useEditor } from "@/editor/use-editor";
import { ExportButton } from "@/components/editor/export-button";
import { studioExitUrl } from "./config";
import { SaveStatus } from "./save-status";
import { ServerRenderButton } from "./server-render";
import { ExtensionsMenu } from "./extensions";

export function CaduEditorHeader() {
	const editor = useEditor();
	const project = useEditor((e) => e.project.getActiveOrNull());
	const [shortcutsOpen, setShortcutsOpen] = useState(false);
	const [leaving, setLeaving] = useState(false);

	const leave = async () => {
		if (leaving) return;
		setLeaving(true);
		try {
			await editor.project.prepareExit();
		} finally {
			window.location.assign(studioExitUrl());
		}
	};

	return (
		<header className="bg-background flex h-[3.4rem] items-center justify-between px-3 pt-0.5">
			<div className="flex min-w-0 items-center gap-2">
				<Button variant="ghost" size="sm" onClick={leave} disabled={leaving}>
					<HugeiconsIcon icon={ArrowLeft01Icon} className="size-4" />
					Studio
				</Button>
				<span className="truncate text-sm font-medium">{project?.metadata.name || "Projeto"}</span>
				<SaveStatus />
			</div>
			<nav className="flex items-center gap-2">
				<ExtensionsMenu />
				<Button variant="ghost" size="icon" aria-label="Atalhos" onClick={() => setShortcutsOpen(true)}>
					<HugeiconsIcon icon={CommandIcon} className="size-4" />
				</Button>
				<ServerRenderButton />
				<ExportButton />
			</nav>
			<ShortcutsDialog isOpen={shortcutsOpen} onOpenChange={setShortcutsOpen} />
		</header>
	);
}
