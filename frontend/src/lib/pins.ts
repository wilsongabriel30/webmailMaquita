// Mensajes fijados con chincheta. Preferencia local del usuario (por dispositivo):
// los fijados se muestran al inicio de la lista. La clave es folder:uid.
const KEY = 'maquita_pinned_msgs';

export function pinKey(folder: string, uid: number): string {
  return `${folder}:${uid}`;
}

export function getPinnedSet(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
  } catch {
    return new Set();
  }
}

export function isPinned(folder: string, uid: number): boolean {
  return getPinnedSet().has(pinKey(folder, uid));
}

// Alterna el pin de uno o varios mensajes. Devuelve true si quedaron fijados.
export function togglePins(folder: string, uids: number[]): boolean {
  const set = getPinnedSet();
  // Si alguno NO esta fijado, fijamos todos; si todos estan fijados, los soltamos.
  const anyUnpinned = uids.some((u) => !set.has(pinKey(folder, u)));
  uids.forEach((u) => {
    const k = pinKey(folder, u);
    if (anyUnpinned) set.add(k); else set.delete(k);
  });
  localStorage.setItem(KEY, JSON.stringify([...set]));
  window.dispatchEvent(new CustomEvent('pins-changed'));
  return anyUnpinned;
}
