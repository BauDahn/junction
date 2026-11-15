type ContextChangedListener = () => void;

const listeners = new Set<ContextChangedListener>();

export function emitContextChanged() {
  listeners.forEach((listener) => listener());
}

export function onContextChanged(cb: ContextChangedListener) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}
