const initialState = {
  creative: null,
  layers: [],
  assets: [],
  collections: [],
  scene: null,
  sceneVersion: 1,
  selectedLayerId: null,
  stageMode: "original",
  zoom: 1,
  activeTool: "select",
  job: null,
  dirty: false,
};

export function createStore(initialValue = initialState) {
  let state = structuredClone(initialValue);
  const listeners = new Set();

  return {
    getState() {
      return state;
    },

    setState(update) {
      state = typeof update === "function"
        ? { ...state, ...update(state) }
        : { ...state, ...update };
      listeners.forEach((listener) => listener(state));
    },

    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
