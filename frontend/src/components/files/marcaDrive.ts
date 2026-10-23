import { useEffect, useState } from 'react';

/* Nombre visible del Drive (`drive_name`), el mismo que pinta el explorador del almacén.
   Lo sirve GET /api/almacen/marca (sin sesión, caché de 5 min). Se pide una sola vez por
   pestaña. Sin respuesta queda en null y los textos usan una forma neutra: nunca un
   nombre de marca escrito a mano. */

let nombre: string | null = null;
let peticion: Promise<string | null> | null = null;

function cargarNombreDrive(): Promise<string | null> {
  if (!peticion) {
    peticion = fetch('/api/almacen/marca')
      .then(r => (r.ok ? r.json() : {}))
      .then((b: { drive_name?: string }) => {
        nombre = (b.drive_name || '').trim() || null;
        return nombre;
      })
      .catch(() => nombre);
  }
  return peticion;
}

export function useNombreDrive(): string | null {
  const [valor, setValor] = useState(nombre);
  useEffect(() => {
    let vivo = true;
    cargarNombreDrive().then(n => { if (vivo) setValor(n); });
    return () => { vivo = false; };
  }, []);
  return valor;
}
