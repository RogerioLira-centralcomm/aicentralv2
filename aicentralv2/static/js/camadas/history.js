import { cloneLayers } from "./utils.js";

export function createHistory(store) {
  const past = [];
  const future = [];

  function snapshot() {
    const state = store.getState();
    return {
      layers: cloneLayers(state.layers),
      scene: state.scene ? JSON.parse(JSON.stringify(state.scene)) : null,
      selectedLayerId: state.selectedLayerId,
    };
  }

  return {
    push() {
      past.push(snapshot());
      if (past.length > 40) past.shift();
      future.length = 0;
      store.setState({ dirty: true });
    },

    undo() {
      if (!past.length) return;
      future.push(snapshot());
      store.setState(past.pop());
    },

    redo() {
      if (!future.length) return;
      past.push(snapshot());
      store.setState(future.pop());
    },
  };
}
