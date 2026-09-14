import { $ } from "./animate-utils.js";

export function showVideo(version) {
  const image = $("mcSwapImage");
  let video = $("mcSwapVideo");
  if (!video) {
    video = document.createElement("video");
    video.id = "mcSwapVideo";
    video.className = "hidden h-full w-full object-contain";
    video.setAttribute("playsinline", "");
    video.setAttribute("controls", "");
    video.preload = "metadata";
    image?.parentElement?.appendChild(video);
  }
  if (!version?.video_url) {
    hideVideo();
    return;
  }
  video.src = version.video_url;
  video.poster = version.poster_url || version.image || "";
  video.muted = true;
  video.loop = true;
  video.classList.remove("hidden");
  if (image) image.classList.add("hidden");
  video.play()?.catch(() => {});
}

export function hideVideo() {
  const image = $("mcSwapImage");
  const video = $("mcSwapVideo");
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.classList.add("hidden");
  }
  image?.classList.remove("hidden");
}
