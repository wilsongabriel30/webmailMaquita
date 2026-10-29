// Arrastrar tareas. Sobre otra tarea la coloca antes de ella (orden personalizado): solo en una lista de verdad
// (propia, compartida o «Tareas»), con el orden «personalizado» y en vista Lista. Hacia la barra lateral la mueve
// a otra lista, a «Mi día» o a «Importante» (ver arrastreTarea.ts); eso vale en cualquier vista.
import { useState, type DragEvent } from 'react';
import { api } from '../../../api/client';
import type { Task } from '../types';
import { marcarTarea } from '../components/arrastreTarea';

export function useArrastreTareas(listaId: string | null, tareas: Task[], setTasks: (t: Task[]) => void, alFallar: () => void) {
  const [arrastrada, setArrastrada] = useState<string | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);

  const soltarSobre = (destino: string) => {
    if (!listaId || !arrastrada || arrastrada === destino) return;
    const pendientes = tareas.filter(t => !t.completed && t.id !== arrastrada);
    const i = pendientes.findIndex(t => t.id === destino);
    const movida = tareas.find(t => t.id === arrastrada);
    if (i < 0 || !movida || movida.completed) return;
    pendientes.splice(i, 0, movida);
    const nuevas = [...pendientes, ...tareas.filter(t => t.completed)].map((t, pos) => ({ ...t, position: pos }));
    setTasks(nuevas);
    api.put(`/tasks/lists/${listaId}/orden`, { ids: nuevas.map(t => t.id) }).catch(alFallar);
  };

  const fin = () => { setArrastrada(null); setSobre(null); };

  return {
    sobre,
    props: (t: Task) => {
      // Las tareas de un correo marcado dependen de su lista: no se arrastran.
      if (t.correo) return {};
      const reordena = !!listaId && !t.completed;
      return {
        draggable: true,
        onDragStart: (e: DragEvent) => { marcarTarea(e, t.id); setArrastrada(t.id); },
        onDragOver: (e: DragEvent) => { if (reordena && arrastrada) { e.preventDefault(); setSobre(t.id); } },
        onDragLeave: () => setSobre(s => (s === t.id ? null : s)),
        onDrop: (e: DragEvent) => { if (reordena) { e.preventDefault(); soltarSobre(t.id); } fin(); },
        onDragEnd: fin,
      };
    },
  };
}
