import { $ } from "./animate-utils.js";

export function showVideo(version) {
  const image = $("mcSwapImage");
  let video = $("mcSwapVideo");
  const host = document.querySelector(".mc-cadu-video-frame")
    || image?.parentElement
    || document.querySelector(".mc-trocr-frame");
  if (!video) {
    video = document.createElement("video");
    video.id = "mcSwapVideo";
    video.className = "h-full w-full object-contain";
    video.setAttribute("playsinline", "");
    video.setAttribute("controls", "");
    video.preload = "metadata";
    host?.appendChild(video);
  } else if (host && video.parentElement !== host) {
    host.appendChild(video);
  }
  const src = version?.video_url || "";
  if (!src || !video) {
    hideVideo();
    return false;
  }
  video.pause();
  video.src = src;
  video.poster = version.poster_url || version.image_url || version.image || "";
  video.muted = true;
  video.loop = true;
  video.controls = true;
  video.preload = "auto";
  video.removeAttribute("hidden");
  video.classList.remove("hidden");
  if (image) {
    image.classList.add("hidden");
    image.setAttribute("hidden", "");
  }
  const empty = $("mcVideoEmpty");
  if (empty) empty.hidden = true;
  video.load();
  video.play()?.catch(() => {});
  return true;
}

export function hideVideo() {
  const image = $("mcSwapImage");
  const video = $("mcSwapVideo");
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.load();
    video.classList.add("hidden");
    video.setAttribute("hidden", "");
  }
  if (image) {
    image.classList.remove("hidden");
    image.removeAttribute("hidden");
  }
  const empty = $("mcVideoEmpty");
  if (empty) empty.hidden = false;
}
