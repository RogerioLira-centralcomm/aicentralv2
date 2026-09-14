export function $(id) {
  return document.getElementById(id);
}

export function csrf() {
  return document.getElementById("mcSwap")?.dataset?.csrf || "";
}

export function clock(seconds) {
  const value = Math.max(0, Math.floor(seconds || 0));
  const minutes = Math.floor(value / 60);
  const rest = String(value % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}
