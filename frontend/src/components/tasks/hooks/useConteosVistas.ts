// Números de la barra lateral de Tareas: pendientes de cada vista (como en Outlook).
// Las vistas de la base de datos se cuentan en una sola petición y se recargan tras cada cambio;
// el correo marcado se cuenta aparte (va al buzón), solo al abrir Tareas y al entrar en esa vista.
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../api/client';

const pedirConteos = () => api.get<Record<string, number>>('/tasks/views/counts');
const pedirMarcados = () => api.get<{ flagged: number }>('/tasks/views/flagged/count');

export function useConteosVistas(activeView: string) {
  const [conteos, setConteos] = useState<Record<string, number>>({});
  const [marcados, setMarcados] = useState<number | null>(null);

  // Tras cada cambio en una tarea (sin números si falla: la barra lateral funciona igual).
  const recargarConteos = useCallback(() => pedirConteos().then(setConteos).catch(() => {}), []);

  useEffect(() => {
    let vigente = true;
    pedirConteos().then(c => { if (vigente) setConteos(c); }).catch(() => {});
    return () => { vigente = false; };
  }, []);

  const marcadosPedidos = useRef(false);
  useEffect(() => {
    if (marcadosPedidos.current && activeView !== 'flagged') return;
    marcadosPedidos.current = true;
    let vigente = true;
    pedirMarcados().then(r => { if (vigente) setMarcados(r.flagged); }).catch(() => {});
    return () => { vigente = false; };
  }, [activeView]);

  return {
    conteos: marcados === null ? conteos : { ...conteos, flagged: marcados },
    recargarConteos,
  };
}
