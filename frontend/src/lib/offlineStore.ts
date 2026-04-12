const DB_NAME = "maquita-mail-offline";
const DB_VERSION = 1;

export interface OfflineMessage {
  id: string;
  folder: string;
  from: string;
  to: string;
  subject: string;
  date: string;
  body: string;
  flags: string[];
  cachedAt: number;
}

export interface OfflineAction {
  id: string;
  type: "markRead" | "markUnread" | "move" | "delete" | "flag";
  messageId: string;
  data?: Record<string, unknown>;
  createdAt: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains("messages")) {
        const msgStore = db.createObjectStore("messages", { keyPath: "id" });
        msgStore.createIndex("folder", "folder");
        msgStore.createIndex("cachedAt", "cachedAt");
      }
      if (!db.objectStoreNames.contains("actions")) {
        db.createObjectStore("actions", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("folders")) {
        db.createObjectStore("folders", { keyPath: "name" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function cacheMessages(folder: string, messages: OfflineMessage[]) {
  const db = await openDB();
  const tx = db.transaction("messages", "readwrite");
  const store = tx.objectStore("messages");
  for (const msg of messages) {
    msg.cachedAt = Date.now();
    msg.folder = folder;
    store.put(msg);
  }
  const countReq = store.count();
  countReq.onsuccess = () => {
    if (countReq.result > 500) {
      const idx = store.index("cachedAt");
      const cursor = idx.openCursor();
      let toDelete = countReq.result - 500;
      cursor.onsuccess = (e) => {
        const c = (e.target as IDBRequest).result;
        if (c && toDelete > 0) {
          c.delete();
          toDelete--;
          c.continue();
        }
      };
    }
  };
}

export async function getCachedMessages(folder: string): Promise<OfflineMessage[]> {
  const db = await openDB();
  const tx = db.transaction("messages", "readonly");
  const idx = tx.objectStore("messages").index("folder");
  return new Promise((resolve) => {
    const req = idx.getAll(IDBKeyRange.only(folder));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve([]);
  });
}

export async function queueAction(action: Omit<OfflineAction, "id" | "createdAt">) {
  const db = await openDB();
  const tx = db.transaction("actions", "readwrite");
  tx.objectStore("actions").put({
    ...action,
    id: crypto.randomUUID(),
    createdAt: Date.now()
  });
}

export async function getPendingActions(): Promise<OfflineAction[]> {
  const db = await openDB();
  const tx = db.transaction("actions", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("actions").getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve([]);
  });
}

export async function clearActions() {
  const db = await openDB();
  const tx = db.transaction("actions", "readwrite");
  tx.objectStore("actions").clear();
}

export async function cacheFolders(folders: { name: string }[]) {
  const db = await openDB();
  const tx = db.transaction("folders", "readwrite");
  const store = tx.objectStore("folders");
  store.clear();
  for (const f of folders) {
    store.put(f);
  }
}

export async function getCachedFolders(): Promise<{ name: string }[]> {
  const db = await openDB();
  const tx = db.transaction("folders", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("folders").getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve([]);
  });
}
