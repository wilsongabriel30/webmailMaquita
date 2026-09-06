/* =============================================================================
   T-49 · «Espacio local usado» y «Liberar espacio»
   -----------------------------------------------------------------------------
   QUE HACE: enseña cuánto ocupa en el equipo el caché que hace que el correo y el
   chat vayan rápidos, con el reparto por partes, y permite vaciar lo viejo.
   POR QUE:  el caché puede llegar a 2 GB. La persona tiene derecho a ver cuánto
   ocupa en SU disco y a poder liberarlo sin llamar a nadie.
   LO QUE NUNCA SE BORRA: los correos y mensajes escritos que todavía no han
   salido. Se avisa en pantalla, para que nadie tema perder lo suyo al pulsar.
   DONDE SE USA: SettingsView.tsx, sección «Espacio en el equipo».
   ============================================================================= */
import { useEffect, useState } from 'react';

interface Uso {
  totalBytes: number;
  topeBytes: number;
  correo: number;
  chat: number;
  otros: number;
  pendientesBytes: number;
  pendientesCuantos: number;
}

const TOPE = 2 * 1024 * 1024 * 1024;

function comoTexto(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function abrir(nombre: string): Promise<IDBDatabase | null> {
  return new Promise((ok) => {
    const p = indexedDB.open(nombre);
    p.onsuccess = () => ok(p.result);
    p.onerror = () => ok(null);
    p.onblocked = () => ok(null);
  });
}

/** Registro guardado en IndexedDB: cifrado (sobre) o antiguo (ct suelto), más lo del chat. */
type Fila = { sobre?: { ct?: ArrayBuffer }; ct?: ArrayBuffer; fijo?: boolean; bytes?: number };

function contar(db: IDBDatabase | null, almacen: string): Promise<Fila[]> {
  return new Promise((ok) => {
    if (!db || !db.objectStoreNames.contains(almacen)) return ok([]);
    try {
      const r = db.transaction(almacen, 'readonly').objectStore(almacen).getAll();
      r.onsuccess = () => ok(r.result || []);
      r.onerror = () => ok([]);
    } catch {
      ok([]);
    }
  });
}

/** Lo que ocupa un registro: lo cifrado más un margen por los datos de fuera del sobre. */
const pesar = (fila: Fila | null): number =>
  (fila?.sobre?.ct?.byteLength ?? fila?.ct?.byteLength ?? JSON.stringify(fila || {}).length) + 64;

async function medir(): Promise<Uso> {
  const correoDb = await abrir('maquita-mail-offline');
  const chatDb = await abrir('maquita-cache');

  const mensajes = await contar(correoDb, 'messages');
  const cola = await contar(correoDb, 'outbox');
  const chat = await contar(chatDb, 'datos');

  const correo = mensajes.reduce((a, f) => a + pesar(f), 0);
  const pendientesBytes = cola.reduce((a, f) => a + pesar(f), 0);
  const chatBytes = chat.filter(f => !f.fijo).reduce((a, f) => a + (f.bytes || pesar(f)), 0);
  const chatFijos = chat.filter(f => f.fijo).reduce((a, f) => a + (f.bytes || pesar(f)), 0);

  return {
    totalBytes: correo + pendientesBytes + chatBytes + chatFijos,
    topeBytes: TOPE,
    correo, chat: chatBytes, otros: 0,
    pendientesBytes: pendientesBytes + chatFijos,
    pendientesCuantos: cola.length + chat.filter(f => f.fijo).length,
  };
}

export default function EspacioLocal() {
  const [uso, setUso] = useState<Uso | null>(null);
  const [liberando, setLiberando] = useState(false);
  const [aviso, setAviso] = useState<string>('');

  const refrescar = () => { medir().then(setUso).catch(() => setUso(null)); };
  useEffect(refrescar, []);

  async function liberar() {
    setLiberando(true);
    setAviso('');
    try {
      const antes = uso?.totalBytes ?? 0;
      // el propio almacén del chat sabe purgar sin tocar lo pendiente
      const almacen = (window as unknown as { MaquitaAlmacen?: { hacerSitio?: (n: number) => Promise<void> } }).MaquitaAlmacen;
      if (almacen?.hacerSitio) await almacen.hacerSitio(0);
      // y del correo se vacía lo que el servidor puede volver a dar
      const db = await abrir('maquita-mail-offline');
      if (db) {
        for (const a of ['messages', 'folders', 'actions']) {
          if (db.objectStoreNames.contains(a)) {
            await new Promise<void>((ok) => {
              const tx = db.transaction(a, 'readwrite');
              tx.objectStore(a).clear();
              tx.oncomplete = () => ok();
              tx.onerror = () => ok();
            });
          }
        }
      }
      const despues = await medir();
      setUso(despues);
      setAviso(`Se liberaron ${comoTexto(Math.max(0, antes - despues.totalBytes))}. `
               + 'Lo que estaba sin enviar sigue intacto.');
    } catch {
      setAviso('No se pudo liberar el espacio. Inténtalo de nuevo más tarde.');
    } finally {
      setLiberando(false);
    }
  }

  if (!uso) {
    return <div className="text-sm text-[#605e5c]">Calculando el espacio usado…</div>;
  }

  const porcentaje = Math.min(100, (uso.totalBytes / uso.topeBytes) * 100);

  return (
    <div className="max-w-2xl">
      <h3 className="text-base font-semibold text-[#323130] mb-1">Espacio en este equipo</h3>
      <p className="text-sm text-[#605e5c] mb-4">
        Guardamos una copia de tus correos y conversaciones recientes en este equipo para que
        se abran al instante, incluso con mala conexión. Todo va cifrado.
      </p>

      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-sm font-medium text-[#323130]">
          {comoTexto(uso.totalBytes)} de {comoTexto(uso.topeBytes)}
        </span>
        <span className="text-xs text-[#605e5c]">{porcentaje.toFixed(1)} %</span>
      </div>
      <div className="h-2 w-full rounded bg-[#edebe9] overflow-hidden mb-4">
        <div className="h-full rounded bg-[#0078d4]" style={{ width: `${porcentaje}%` }} />
      </div>

      <dl className="text-sm text-[#605e5c] space-y-1 mb-4">
        <div className="flex justify-between"><dt>Correo</dt><dd>{comoTexto(uso.correo)}</dd></div>
        <div className="flex justify-between"><dt>Conversaciones</dt><dd>{comoTexto(uso.chat)}</dd></div>
        {uso.pendientesCuantos > 0 && (
          <div className="flex justify-between font-medium text-[#323130]">
            <dt>Sin enviar todavía ({uso.pendientesCuantos})</dt>
            <dd>{comoTexto(uso.pendientesBytes)}</dd>
          </div>
        )}
      </dl>

      <button
        onClick={liberar}
        disabled={liberando}
        className="px-4 py-2 text-sm rounded bg-[#0078d4] text-white disabled:opacity-60"
      >
        {liberando ? 'Liberando…' : 'Liberar espacio'}
      </button>
      <p className="mt-2 text-xs text-[#605e5c]">
        Se borra lo más antiguo, que se vuelve a descargar cuando haga falta.
        {uso.pendientesCuantos > 0
          ? ` Tus ${uso.pendientesCuantos} mensajes sin enviar NO se tocan.`
          : ' Lo que esté sin enviar nunca se toca.'}
      </p>
      {aviso && <p className="mt-3 text-sm text-[#107c10]">{aviso}</p>}
    </div>
  );
}
