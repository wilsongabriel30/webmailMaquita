const DB_NAME = "maquita-mail-offline";
const DB_VERSION = 2;

export interface OfflineMessage {
  id: string; // folder:uid
  uid: number;
  folder: string;
  message_id: string | null;
  thread_id: string;
  from: string;
  to: string;
  cc?: string;
  subject: string;
  date: string | null;
  size: number;
  flags: string[];
  seen: boolean;
  flagged: boolean;
  snippet: string;
  has_attachments: boolean;
  importance: 'normal' | 'high' | 'low';
  // Full message fields (cached when user opens a message)
  html_body?: string;
  text_body?: string;
  attachments?: Array<{ filename: string; content_type: string; size: number; part_number: string; is_inline: boolean }>;
  references?: string;
  in_reply_to?: string;
  has_remote_images?: boolean;
  blocked_image_count?: number;
  cachedAt: number;
}

export interface OutboxEmail {
  id: string;
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  html_body: string;
  text_body: string;
  in_reply_to?: string;
  references?: string;
  attachments?: Array<{ filename: string; content_b64: string; content_type: string }>;
  request_read_receipt?: boolean;
  request_delivery_receipt?: boolean;
  createdAt: number;
  status: 'pending' | 'sending' | 'failed';
  error?: string;
  retries: number;
}

export interface OfflineAction {
  id: string;
  type: "markRead" | "markUnread" | "move" | "delete" | "flag" | "unflag";
  folder: string;
  uid: number;
  data?: Record<string, unknown>;
  createdAt: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      // Messages store
      if (!db.objectStoreNames.contains("messages")) {
        const msgStore = db.createObjectStore("messages", { keyPath: "id" });
        msgStore.createIndex("folder", "folder");
        msgStore.createIndex("cachedAt", "cachedAt");
      }
      // Actions queue
      if (!db.objectStoreNames.contains("actions")) {
        db.createObjectStore("actions", { keyPath: "id" });
      }
      // Folders cache
      if (!db.objectStoreNames.contains("folders")) {
        db.createObjectStore("folders", { keyPath: "name" });
      }
      // Outbox for offline-composed emails
      if (!db.objectStoreNames.contains("outbox")) {
        const outboxStore = db.createObjectStore("outbox", { keyPath: "id" });
        outboxStore.createIndex("status", "status");
        outboxStore.createIndex("createdAt", "createdAt");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// === MESSAGES ===

export async function cacheMessageList(folder: string, messages: OfflineMessage[]) {
  const db = await openDB();
  const tx = db.transaction("messages", "readwrite");
  const store = tx.objectStore("messages");
  for (const msg of messages) {
    const id = `${folder}:${msg.uid}`;
    // Preserve existing full body if we already have it
    const existing = await new Promise<OfflineMessage | undefined>((resolve) => {
      const req = store.get(id);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(undefined);
    });
    const record: OfflineMessage = {
      ...msg,
      id,
      folder,
      cachedAt: Date.now(),
    };
    // Keep full body from previous cache
    if (existing?.html_body && !msg.html_body) {
      record.html_body = existing.html_body;
      record.text_body = existing.text_body;
      record.attachments = existing.attachments;
      record.cc = existing.cc;
      record.references = existing.references;
      record.in_reply_to = existing.in_reply_to;
    }
    store.put(record);
  }
  // Limit total cache to 1000 messages
  const countReq = store.count();
  countReq.onsuccess = () => {
    if (countReq.result > 1000) {
      const idx = store.index("cachedAt");
      const cursor = idx.openCursor();
      let toDelete = countReq.result - 1000;
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

export async function cacheFullMessage(folder: string, msg: OfflineMessage) {
  const db = await openDB();
  const tx = db.transaction("messages", "readwrite");
  const store = tx.objectStore("messages");
  const id = `${folder}:${msg.uid}`;
  store.put({ ...msg, id, folder, cachedAt: Date.now() });
}

export async function getCachedMessages(folder: string): Promise<OfflineMessage[]> {
  const db = await openDB();
  const tx = db.transaction("messages", "readonly");
  const idx = tx.objectStore("messages").index("folder");
  return new Promise((resolve) => {
    const req = idx.getAll(IDBKeyRange.only(folder));
    req.onsuccess = () => {
      // Sort by date descending
      const msgs = req.result || [];
      msgs.sort((a: OfflineMessage, b: OfflineMessage) => {
        const da = a.date ? new Date(a.date).getTime() : 0;
        const db = b.date ? new Date(b.date).getTime() : 0;
        return db - da;
      });
      resolve(msgs);
    };
    req.onerror = () => resolve([]);
  });
}

export async function getCachedMessage(folder: string, uid: number): Promise<OfflineMessage | null> {
  const db = await openDB();
  const tx = db.transaction("messages", "readonly");
  const store = tx.objectStore("messages");
  return new Promise((resolve) => {
    const req = store.get(`${folder}:${uid}`);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => resolve(null);
  });
}

// === FOLDERS ===

export async function cacheFolders(folders: { name: string; unseen: number }[]) {
  const db = await openDB();
  const tx = db.transaction("folders", "readwrite");
  const store = tx.objectStore("folders");
  store.clear();
  for (const f of folders) {
    store.put(f);
  }
}

export async function getCachedFolders(): Promise<{ name: string; unseen: number }[]> {
  const db = await openDB();
  const tx = db.transaction("folders", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("folders").getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve([]);
  });
}

// === ACTIONS QUEUE ===

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

export async function removeActions(ids: string[]) {
  if (ids.length === 0) return;
  const db = await openDB();
  const tx = db.transaction("actions", "readwrite");
  const store = tx.objectStore("actions");
  for (const id of ids) store.delete(id);
  return new Promise<void>((resolve) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

// === OUTBOX ===

export async function addToOutbox(email: Omit<OutboxEmail, "id" | "createdAt" | "status" | "retries">): Promise<string> {
  const db = await openDB();
  const tx = db.transaction("outbox", "readwrite");
  const id = crypto.randomUUID();
  const record: OutboxEmail = {
    ...email,
    id,
    createdAt: Date.now(),
    status: 'pending',
    retries: 0,
  };
  tx.objectStore("outbox").put(record);
  return id;
}

export async function getOutboxEmails(): Promise<OutboxEmail[]> {
  const db = await openDB();
  const tx = db.transaction("outbox", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("outbox").getAll();
    req.onsuccess = () => {
      const emails = req.result || [];
      emails.sort((a: OutboxEmail, b: OutboxEmail) => a.createdAt - b.createdAt);
      resolve(emails);
    };
    req.onerror = () => resolve([]);
  });
}

export async function updateOutboxStatus(id: string, status: OutboxEmail['status'], error?: string) {
  const db = await openDB();
  const tx = db.transaction("outbox", "readwrite");
  const store = tx.objectStore("outbox");
  return new Promise<void>((resolve) => {
    const req = store.get(id);
    req.onsuccess = () => {
      if (req.result) {
        const updated = { ...req.result, status, error, retries: req.result.retries + (status === 'failed' ? 1 : 0) };
        store.put(updated);
      }
      resolve();
    };
    req.onerror = () => resolve();
  });
}

export async function removeFromOutbox(id: string) {
  const db = await openDB();
  const tx = db.transaction("outbox", "readwrite");
  tx.objectStore("outbox").delete(id);
}

export async function getOutboxCount(): Promise<number> {
  const db = await openDB();
  const tx = db.transaction("outbox", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("outbox").count();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(0);
  });
}
