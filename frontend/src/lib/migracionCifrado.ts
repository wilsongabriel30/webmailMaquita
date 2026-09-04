/* =============================================================================
   T-49 · Pasar a cifrado lo que ya está guardado en el equipo
   -----------------------------------------------------------------------------
   QUE HACE: al arrancar, deja el caché del correo cifrado. Con dos criterios
   distintos según lo que haya en juego:

     · messages, folders y actions -> SE BORRAN y se vuelven a llenar cifrados.
       Son copias de lo que está en el servidor: se recuperan solos. Migrarlos uno
       a uno dejaría, durante el proceso, contenido en claro y cifrado conviviendo.

     · outbox -> SE MIGRA UNO A UNO. Ahí hay correos que la persona escribió y que
       TODAVÍA NO HAN SALIDO. No están en ninguna otra parte: si se pierden, se
       perdieron. Cada uno se cifra, se comprueba que se puede volver a leer, y
       SOLO ENTONCES se reemplaza el original.

   REGLA QUE MANDA SOBRE TODO: si un correo del outbox no se puede cifrar, SE DEJA
   COMO ESTÁ. Un correo sin enviar que se pierde es mucho peor que un correo sin
   cifrar. Se anota para reintentarlo la próxima vez.
   ============================================================================= */

import { cifrar, descifrar, esPaquete } from './cifradoLocal';

const DB_NAME = 'maquita-mail-offline';
const MARCA = 'maquita:cache-cifrado:v1';

function abrir(): Promise<IDBDatabase> {
  return new Promise((ok, mal) => {
    const p = indexedDB.open(DB_NAME);
    p.onsuccess = () => ok(p.result);
    p.onerror = () => mal(p.error);
  });
}

function pedir<T>(r: IDBRequest<T>): Promise<T> {
  return new Promise((ok, mal) => {
    r.onsuccess = () => ok(r.result);
    r.onerror = () => mal(r.error);
  });
}

/** Vacía un almacén. Se usa solo con lo que el servidor puede volver a dar. */
async function vaciar(db: IDBDatabase, nombre: string): Promise<number> {
  if (!db.objectStoreNames.contains(nombre)) return 0;
  const tx = db.transaction(nombre, 'readwrite');
  const s = tx.objectStore(nombre);
  const cuantos = await pedir(s.count());
  s.clear();
  return cuantos;
}

/**
 * Migra los correos pendientes de enviar, de uno en uno y comprobando cada paso.
 * Devuelve cuántos se cifraron y cuántos se dejaron intactos por precaución.
 */
async function migrarOutbox(db: IDBDatabase): Promise<{ cifrados: number; intactos: number }> {
  if (!db.objectStoreNames.contains('outbox')) return { cifrados: 0, intactos: 0 };
  const todos = await pedir(db.transaction('outbox', 'readonly').objectStore('outbox').getAll());
  let cifrados = 0;
  let intactos = 0;

  for (const correo of todos || []) {
    // lo que ya está cifrado se deja en paz
    if (esPaquete((correo as any).sobre)) continue;
    try {
      // se guarda cifrado TODO lo que es contenido; fuera quedan solo los datos
      // que hacen falta para manejar la cola sin abrir el correo
      const sobre = await cifrar({
        to: correo.to, cc: correo.cc, bcc: correo.bcc,
        subject: correo.subject, html_body: correo.html_body, text_body: correo.text_body,
        in_reply_to: correo.in_reply_to, references: correo.references,
        attachments: correo.attachments,
        request_read_receipt: correo.request_read_receipt,
        request_delivery_receipt: correo.request_delivery_receipt,
      });

      // COMPROBACIÓN antes de tocar el original: si no se puede volver a leer, no se toca
      const prueba: any = await descifrar(sobre);
      if (!prueba || prueba.subject !== correo.subject || prueba.html_body !== correo.html_body) {
        intactos++;
        console.warn('T-49: un correo pendiente no supero la comprobacion; se deja como estaba');
        continue;
      }

      const nuevo = {
        id: correo.id,
        createdAt: correo.createdAt,
        status: correo.status,
        retries: correo.retries,
        error: correo.error,
        sobre,                       // aquí va todo el contenido, cifrado
      };
      await pedir(db.transaction('outbox', 'readwrite').objectStore('outbox').put(nuevo) as any);
      cifrados++;
    } catch (e) {
      // Un correo sin enviar que se pierde es peor que un correo sin cifrar.
      intactos++;
      console.warn('T-49: no se pudo cifrar un correo pendiente; se deja intacto', e);
    }
  }
  return { cifrados, intactos };
}

const MARCA_LIMPIEZA = 'maquita:cache-limpieza-pendiente';

/**
 * Borra la base entera y la deja recrearse limpia, para que no quede rastro de lo que
 * antes se guardaba en claro. SOLO se hace con la cola de envío vacía.
 */
export async function limpiarRestos(): Promise<'hecha' | 'aplazada' | 'no-hacia-falta'> {
  if (!localStorage.getItem(MARCA_LIMPIEZA)) return 'no-hacia-falta';
  try {
    const db = await abrir();
    const pendientes = db.objectStoreNames.contains('outbox')
      ? await pedir(db.transaction('outbox', 'readonly').objectStore('outbox').count())
      : 0;
    if (pendientes > 0) {
      // hay correos sin enviar: no se arriesga nada. Se hará cuando la cola se vacíe.
      return 'aplazada';
    }
    db.close();
    await new Promise<void>((ok) => {
      const p = indexedDB.deleteDatabase(DB_NAME);
      p.onsuccess = () => ok();
      p.onerror = () => ok();
      p.onblocked = () => ok();
    });
    localStorage.removeItem(MARCA_LIMPIEZA);
    console.info('T-49: base del correo recreada; sin restos de lo guardado en claro');
    return 'hecha';
  } catch (e) {
    console.warn('T-49: no se pudo limpiar los restos; se reintentara', e);
    return 'aplazada';
  }
}

/** Se ejecuta una sola vez por equipo. Devuelve el resumen, para poder contarlo. */
export async function migrarCacheACifrado(): Promise<{
  yaEstaba: boolean; borrados: number; cifrados: number; intactos: number;
}> {
  if (localStorage.getItem(MARCA)) {
    return { yaEstaba: true, borrados: 0, cifrados: 0, intactos: 0 };
  }
  try {
    const db = await abrir();

    // 1) lo que el servidor puede volver a dar: fuera, y se rellena cifrado con el uso
    let borrados = 0;
    for (const almacen of ['messages', 'folders', 'actions']) {
      borrados += await vaciar(db, almacen);
    }

    // 2) lo que solo existe aquí: uno a uno y con red de seguridad
    const { cifrados, intactos } = await migrarOutbox(db);

    // solo se da por hecha si NO quedó nada a medias
    if (intactos === 0) localStorage.setItem(MARCA, new Date().toISOString());
    // queda apuntado que el archivo aún guarda la historia de lo que estaba en claro
    if (borrados > 0 || cifrados > 0) localStorage.setItem(MARCA_LIMPIEZA, '1');
    await limpiarRestos();
    console.info('T-49: cache del correo pasado a cifrado — %d descartados, %d pendientes '
                 + 'cifrados, %d intactos por precaucion', borrados, cifrados, intactos);
    return { yaEstaba: false, borrados, cifrados, intactos };
  } catch (e) {
    console.warn('T-49: no se pudo migrar el cache del correo; se reintentara', e);
    return { yaEstaba: false, borrados: 0, cifrados: 0, intactos: 0 };
  }
}
