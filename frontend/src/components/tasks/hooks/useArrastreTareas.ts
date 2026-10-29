// Orden personalizado de Tareas: arrastrar una tarea pendiente sobre otra la coloca antes de ella.
// Solo en una lista de verdad (propia, compartida o «Tareas»), con el orden «personalizado» y en vista Lista.
import { useState, type DragEvent } from 'react';
import { api } from '../../../api/client';
import type { Task } from '../types';

export function useArrastreTareas(listaId: string | null, tareas: Task[], setTasks: (t: Task[]) => void, alFallar: () => void) {
  const [arrastrada, setArrastrada] = useState<string | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);

  const soltarSobre = (destino: string) => {
    if (!listaId || !arrastrada || arrastrada === destino) return;
    const pendientes = tareas.filter(t => !t.completed && t.id !== arrastrada);
    const i = pendientes.findIndex(t => t.id === destino);
    const movida = tareas.find(t => t.id === arrastrada);
    if (i < 0 || !movida) return;
    pendientes.splice(i, 0, movida);
    const nuevas = [...pendientes, ...tareas.filter(t => t.completed)].map((t, pos) => ({ ...t, position: pos }));
    setTasks(nuevas);
    api.put(`/tasks/lists/${listaId}/orden`, { ids: nuevas.map(t => t.id) }).catch(alFallar);
  };

  return {
    sobre,
    props: (t: Task) => (!listaId || t.completed ? {} : {
      draggable: true,
      onDragStart: (e: DragEvent) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', t.id); setArrastrada(t.id); },
      onDragOver: (e: DragEvent) => { if (arrastrada) { e.preventDefault(); setSobre(t.id); } },
      onDragLeave: () => setSobre(s => (s === t.id ? null : s)),
      onDrop: (e: DragEvent) => { e.preventDefault(); soltarSobre(t.id); setArrastrada(null); setSobre(null); },
      onDragEnd: () => { setArrastrada(null); setSobre(null); },
    }),
  };
}
