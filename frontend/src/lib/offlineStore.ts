import { cifrar, descifrar, esPaquete } from "./cifradoLocal";

// T-49: lo que se guarda en el equipo va cifrado. Estas dos ayudas envuelven y
// desenvuelven el contenido; el resto del archivo sigue trabajando igual que antes.
async function meterEnSobre<T extends Record<string, any>>(
  registro: T, campos: string[]): Promise<any> {
  const contenido: Record<string, any> = {};
  const fuera: Record<string, any> = {};
  for (const [k, v] of Object.entries(registro)) {
    if (campos.includes(k)) contenido[k] = v; else fuera[k] = v;
  }
  return { ...fuera, sobre: await cifrar(contenido) };
}

async function abrirSobre<T = any>(registro: any): Promise<T | null> {
  if (!registro) return null;
  if (!esPaquete(registro.sobre)) return registro as T;   // guardado antes de cifrar
  const dentro = await descifrar<Record<string, any>>(registro.sobre);
  if (!dentro) return null;      // no se pudo abrir: como si no estuviera
  const { sobre, ...fuera } = registro;
  return { ...fuera, ...dentro } as T;
}

// El contenido de un correo: todo lo que no hace falta para ordenarlo o contarlo.
const CAMPOS_CORREO = ["from", "to", "cc", "bcc", "subject", "html_body",
                       "text_body", "attachments", "references", "in_reply_to",
                       "preview", "snippet"];

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
  // Se prepara TODO antes de abrir la transaccion de escritura: cifrar exige esperar, y
  // una transaccion de IndexedDB no sobrevive a una espera (ver la nota de addToOutbox).
  const preparados: any[] = [];
  const lectura = db.transaction("messages", "readonly");
  const store = lectura.objectStore("messages");
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
    const anterior = await abrirSobre<OfflineMessage>(existing);
    if (anterior?.html_body && !msg.html_body) {
      record.html_body = anterior.html_body;
      record.text_body = anterior.text_body;
      record.attachments = anterior.attachments;
      record.cc = anterior.cc;
      record.references = anterior.references;
      record.in_reply_to = anterior.in_reply_to;
    }
    preparados.push(await meterEnSobre(record, CAMPOS_CORREO));
  }

  // ahora si: una sola transaccion de escritura, sin esperas por medio
  const escritura = db.transaction("messages", "readwrite");
  const destino = escritura.objectStore("messages");
  for (const p of preparados) destino.put(p);
  await new Promise<void>((ok) => {
    escritura.oncomplete = () => ok();
    escritura.onerror = () => ok();
    escritura.onabort = () => ok();
  });

  const limpieza = db.transaction("messages", "readwrite");
  const store2 = limpieza.objectStore("messages");
  // Limit total cache to 1000 messages
  const countReq = store2.count();
  countReq.onsuccess = () => {
    if (countReq.result > 1000) {
      const idx = store2.index("cachedAt");
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
  // cifrar primero, guardar despues (ver la nota de addToOutbox)
  const guardable = await meterEnSobre({ ...msg, id, folder, cachedAt: Date.now() },
                                       CAMPOS_CORREO);
  store.put(guardable);
}

export async function getCachedMessages(folder: string): Promise<OfflineMessage[]> {
  const db = await openDB();
  const tx = db.transaction("messages", "readonly");
  const idx = tx.objectStore("messages").index("folder");
  return new Promise((resolve) => {
    const req = idx.getAll(IDBKeyRange.only(folder));
    req.onsuccess = async () => {
      // Sort by date descending
      const crudos = req.result || [];
      const msgs = (await Promise.all(crudos.map((c: any) => abrirSobre<OfflineMessage>(c))))
        .filter(Boolean) as OfflineMessage[];
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
    // T-49: se abre el sobre antes de devolverlo
    req.onsuccess = async () => resolve(await abrirSobre<OfflineMessage>(req.result));
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
  const id = crypto.randomUUID();
  const record: OutboxEmail = {
    ...email,
    id,
    createdAt: Date.now(),
    status: 'pending',
    retries: 0,
  };
  // T-49: el contenido del correo va cifrado; fuera quedan solo los datos que hacen
  // falta para manejar la cola (id, fecha, estado, reintentos) sin abrirlo.
  //
  // OJO: el cifrado se hace ANTES de abrir la transacción. Una transacción de IndexedDB
  // se cierra sola en cuanto el hilo queda libre, así que un `await` dentro la invalida y
  // el guardado se pierde EN SILENCIO. Aquí eso significaría perder un correo que la
  // persona acaba de escribir sin conexión.
  const guardable = await meterEnSobre(record, CAMPOS_CORREO);
  await new Promise<void>((ok) => {
    const tx = db.transaction("outbox", "readwrite");
    tx.objectStore("outbox").put(guardable);
    tx.oncomplete = () => ok();
    tx.onerror = () => ok();
    tx.onabort = () => ok();
  });
  return id;
}

export async function getOutboxEmails(): Promise<OutboxEmail[]> {
  const db = await openDB();
  const tx = db.transaction("outbox", "readonly");
  return new Promise((resolve) => {
    const req = tx.objectStore("outbox").getAll();
    req.onsuccess = async () => {
      // T-49: se abre el sobre de cada uno. Si alguno no se pudiera descifrar NO se
      // descarta en silencio: se deja pasar tal cual, porque un correo pendiente vale
      // mas que la pulcritud del formato, y asi al menos se puede reintentar o rescatar.
      const crudos = req.result || [];
      const emails: OutboxEmail[] = [];
      for (const c of crudos) {
        const abierto = await abrirSobre<OutboxEmail>(c);
        emails.push(abierto || c);
      }
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
        // se cambian solo los datos de fuera del sobre: el contenido cifrado no se toca
        const updated = { ...req.result, status, error,
                          retries: (req.result.retries || 0) + (status === 'failed' ? 1 : 0) };
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
