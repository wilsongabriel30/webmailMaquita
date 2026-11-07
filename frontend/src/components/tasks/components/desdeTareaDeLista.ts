// Datos de una tarea de lista para el cuadro único «Asignar tarea» (fase 2 de la unificación, 05/11/2026).
import type { DesdeTarea } from '../../tareas/AsignarTareaDialogo';
import type { Task } from '../types';

export function desdeTareaDeLista(task: Task): DesdeTarea {
  return {
    id: task.id,
    titulo: task.title,
    descripcion: task.note || task.description || '',
    plazo: task.due_date || null,
    asignados: task.asignados || [],
  };
}
