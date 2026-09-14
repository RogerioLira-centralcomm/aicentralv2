import { $ } from "./animate-utils.js";

export function showVideo(version) {
  const image = $("mcSwapImage");
  let video = $("mcSwapVideo");
  const host = image?.parentElement || document.querySelector(".mc-trocr-frame");
  if (!video) {
    video = document.createElement("video");
    video.id = "mcSwapVideo";
    video.className = "hidden h-full w-full object-contain";
    video.setAttribute("playsinline", "");
    video.setAttribute("controls", "");
    video.preload = "metadata";
    host?.appendChild(video);
  } else if (host && video.parentElement !== host) {
    host.appendChild(video);
  }
  if (!version?.video_url) {
    hideVideo();
    return;
  }
  video.src = version.video_url;
  video.poster = version.poster_url || version.image || "";
  video.muted = true;
  video.loop = true;
  video.removeAttribute("hidden");
  video.classList.remove("hidden");
  if (image) {
    image.classList.add("hidden");
    image.setAttribute("hidden", "");
  }
  video.play()?.catch(() => {});
}

export function hideVideo() {
  const image = $("mcSwapImage");
  const video = $("mcSwapVideo");
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.classList.add("hidden");
    video.setAttribute("hidden", "");
  }
  if (image) {
    image.classList.remove("hidden");
    image.removeAttribute("hidden");
  }
}
