const root = () => document.getElementById("mcCv2App");

export function emit(name, detail) {
  root()?.dispatchEvent(new CustomEvent(name, { detail, bubbles: true }));
}

export function on(name, handler) {
  const node = root();
  if (!node) return () => {};
  node.addEventListener(name, handler);
  return () => node.removeEventListener(name, handler);
}
