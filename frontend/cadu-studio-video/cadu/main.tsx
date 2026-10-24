import { createRoot } from "react-dom/client";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import Editor from "@/app/editor/[project_id]/page";
import { boot } from "./config";
import { runRenderMode } from "./render-mode";
import { showPendingMessage } from "./extensions";
import "./styles.css";

document.documentElement.classList.add("dark");

const config = window.CADU_VIDEO_EDITOR;
const root = document.getElementById("cadu-video-editor");
if (config?.renderMode) {
	void runRenderMode(config.renderOptions ?? { format: "mp4", quality: "high", includeAudio: true });
} else if (root) {
	boot();
	createRoot(root).render(
		<TooltipProvider>
			<Editor />
			<Toaster />
		</TooltipProvider>,
	);
	window.setTimeout(showPendingMessage, 1500);
}
