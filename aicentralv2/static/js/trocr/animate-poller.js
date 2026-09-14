import { getAnimate } from "./animate-api.js";
import { animateState } from "./animate-store.js";
import { $, clock } from "./animate-utils.js";

export function startPoll(jobId, onDone, onFail) {
  stopPoll();
  animateState.jobId = jobId;
  animateState.startedAt = Date.now();
  const tick = async () => {
    try {
      const job = await getAnimate(jobId);
      paintProgress(job);
      document.dispatchEvent(new CustomEvent("trocr:animate-progress", { detail: job }));
      if (job.status === "ready") {
        stopPoll();
        onDone?.(job);
        return;
      }
      if (["failed", "cancelled", "expired"].includes(job.status)) {
        stopPoll();
        setPollStatus(job.error || job.message || "A animação falhou.");
        onFail?.(job);
      }
    } catch (error) {
      setPollStatus(error.message);
    }
  };
  tick();
  animateState.timer = window.setInterval(tick, 4000);
  animateState.clock = window.setInterval(() => {
    if ($("mcAnimateClock")) {
      $("mcAnimateClock").textContent = clock((Date.now() - animateState.startedAt) / 1000);
    }
  }, 500);
}

export function stopPoll() {
  window.clearInterval(animateState.timer);
  window.clearInterval(animateState.clock);
  animateState.timer = null;
  animateState.clock = null;
}

function setPollStatus(message) {
  if ($("mcAnimateStatus")) $("mcAnimateStatus").textContent = message || "";
}

function paintProgress(job) {
  setPollStatus(job.message || job.stage || "");
  const list = $("mcAnimateSteps");
  if (!list) return;
  list.hidden = false;
  const known = job.ui_stages || [];
  list.innerHTML = known.map((item) => {
    const done = (job.stages || []).some((row) => row.id === item.id);
    const current = job.stage === item.id;
    return `<li class="${current ? "is-current" : ""}">${done || current ? "●" : "○"} ${item.label}</li>`;
  }).join("");
}
