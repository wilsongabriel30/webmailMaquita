// Cache de SOLO LECTURA de la vista «Tareas» (T-118).
//
// Objetivo: abrir «Tareas» SIN internet y ver las tareas de las listas/vistas que ya se
// habían abierto con conexión. No se crea, edita ni completa offline (eso necesita red).
//
// Reutiliza la MISMA IndexedDB del correo (almacén «tareas», ver offlineStore.ts) a través de
// openDB(); aquí solo vive la lógica propia de tareas para no engordar offlineStore.ts.
import { openDB } from './offlineStore';
import type { Task, TaskList, TaskGroup } from '../components/tasks/types';

const STORE = 'tareas';
// Tope global de tareas cacheadas: se guardan las de las listas/vistas abiertas, hasta este número.
const TOPE_TAREAS = 500;

interface Registro {
  clave: string;      // 'tasks:<vista|lista>' para tareas; 'meta:lists' / 'meta:groups' para la barra.
  datos: unknown;
  cachedAt: number;
}

function leer(clave: string): Promise<Registro | undefined> {
  return openDB().then(db => new Promise<Registro | undefined>((res, rej) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(clave);
    req.onsuccess = () => res(req.result as Registro | undefined);
    req.onerror = () => rej(req.error);
  }));
}

function escribir(reg: Registro): Promise<void> {
  return openDB().then(db => new Promise<void>((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(reg);
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
  }));
}

// Deja la cache de tareas (claves 'tasks:*') dentro del tope: si se pasa, borra las más viejas.
async function podar(): Promise<void> {
  const db = await openDB();
  const regs: Registro[] = await new Promise((res, rej) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => res((req.result as Registro[]) || []);
    req.onerror = () => rej(req.error);
  });
  const deTareas = regs
    .filter(r => r.clave.startsWith('tasks:'))
    .sort((a, b) => b.cachedAt - a.cachedAt); // más reciente primero
  let total = 0;
  const borrar: string[] = [];
  for (const r of deTareas) {
    const n = Array.isArray(r.datos) ? r.datos.length : 0;
    if (total + n > TOPE_TAREAS) borrar.push(r.clave);
    else total += n;
  }
  if (!borrar.length) return;
  await new Promise<void>((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    const st = tx.objectStore(STORE);
    borrar.forEach(c => st.delete(c));
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
  });
}

// === TAREAS por vista/lista ===

/** Guarda (online) las tareas de una vista/lista abierta. `clave` = activeView o '<vista>|<busqueda>'. */
export async function guardarTareasCache(clave: string, datos: Task[]): Promise<void> {
  try {
    await escribir({ clave: `tasks:${clave}`, datos, cachedAt: Date.now() });
    await podar();
  } catch { /* la cache es un extra: si falla, no se rompe la app */ }
}

/** Lee las tareas cacheadas de una vista/lista (offline). null si no hay copia. */
export async function leerTareasCache(clave: string): Promise<Task[] | null> {
  try {
    const r = await leer(`tasks:${clave}`);
    return r && Array.isArray(r.datos) ? (r.datos as Task[]) : null;
  } catch { return null; }
}

// === LISTAS y GRUPOS de la barra lateral ===

export async function guardarListasCache(listas: TaskList[], grupos: TaskGroup[]): Promise<void> {
  try {
    await escribir({ clave: 'meta:lists', datos: listas, cachedAt: Date.now() });
    await escribir({ clave: 'meta:groups', datos: grupos, cachedAt: Date.now() });
  } catch { /* extra */ }
}

export async function leerListasCache(): Promise<{ listas: TaskList[]; grupos: TaskGroup[] } | null> {
  try {
    const [l, g] = await Promise.all([leer('meta:lists'), leer('meta:groups')]);
    if (!l && !g) return null;
    return {
      listas: l && Array.isArray(l.datos) ? (l.datos as TaskList[]) : [],
      grupos: g && Array.isArray(g.datos) ? (g.datos as TaskGroup[]) : [],
    };
  } catch { return null; }
}
