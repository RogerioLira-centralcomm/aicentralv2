import { bindCompare, refreshCompareButton } from "./animate-compare.js";
import { bindDialog, openDialog } from "./animate-dialog.js";
import { hideVideo, showVideo } from "./animate-player.js";
import { startPoll } from "./animate-poller.js";
import { $ } from "./animate-utils.js";

function ids() {
  const root = document.getElementById("mcSwap");
  return {
    run_id: window.__trocrAnimate?.runId?.() || "",
    client_id: window.__trocrAnimate?.clientId?.() || "",
    base_id: window.__trocrAnimate?.baseId?.() || "",
    aspect_ratio: window.__trocrAnimate?.aspectRatio?.() || "16:9",
  };
}

document.addEventListener("DOMContentLoaded", () => {
  if (!$("mcTrocrAnimate")) return;
  bindDialog({ ids, aspectRatio: ids().aspect_ratio });
  bindCompare();
  refreshCompareButton();
  $("mcTrocrAnimateBtn")?.addEventListener("click", () => {
    document.dispatchEvent(new Event("trocr:animate-open"));
    openDialog({
      ids,
      aspectRatio: ids().aspect_ratio,
    });
  });
  document.addEventListener("trocr:version-selected", (event) => {
    const version = event.detail || {};
    if (version.media === "video" && version.video_url) showVideo(version);
    else hideVideo();
    refreshCompareButton();
  });
  document.addEventListener("trocr:animate-ready", (event) => {
    const version = event.detail?.version;
    if (version) showVideo(version);
    refreshCompareButton();
  });
  const pending = window.__trocrAnimate?.pendingJobId?.();
  if (pending) {
    startPoll(pending, (ready) => {
      document.dispatchEvent(new CustomEvent("trocr:animate-ready", { detail: ready }));
    });
  }
});
