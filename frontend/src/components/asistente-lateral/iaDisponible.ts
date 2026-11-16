/**
 * ¿Tiene esta instalación una IA configurada? Sin ella el asistente no se enseña: antes el botón seguía
 * visible y cada acción terminaba en un error del servidor de IA (informe de Andes, 15/11/2026).
 *
 * Se pregunta una vez por sesión de navegador. Solo se oculta ante un «no» explícito del servidor: si la
 * consulta falla o el servidor todavía no conoce la ruta (interfaz publicada antes que el servidor), el
 * asistente se queda como estaba.
 */
import { useEffect, useState } from 'react';

let conocido: boolean | null = null;
let peticion: Promise<boolean> | null = null;

function preguntar(): Promise<boolean> {
  if (!peticion) {
    peticion = fetch('/api/ai/disponible', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { disponible?: boolean } | null) => {
        conocido = !(d && d.disponible === false);
        return conocido;
      })
      .catch(() => { conocido = true; return true; });
  }
  return peticion;
}

/** El aviso único de cualquier función de IA cuando la instalación no tiene IA configurada. */
export const AVISO_SIN_IA = 'El asistente de IA no está configurado en esta instalación. Consulte con su administrador.';

/** Para manejadores (fuera de un componente): la misma consulta de la sesión, sin repetir la petición. */
export function hayIA(): Promise<boolean> {
  return preguntar();
}

/** null mientras no se sabe; después, si hay IA. */
export function useIADisponible(): boolean | null {
  const [valor, setValor] = useState<boolean | null>(conocido);
  useEffect(() => {
    let vivo = true;
    preguntar().then((v) => { if (vivo) setValor(v); });
    return () => { vivo = false; };
  }, []);
  return valor;
}
