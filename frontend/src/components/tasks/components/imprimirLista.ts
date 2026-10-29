// «Imprimir esta lista» (como en To Do, F5): abre una ventana con las tareas de la lista (pendientes y completadas,
// con sus fechas e importancia) y lanza el diálogo de impresión del navegador.
import { api } from '../../../api/client';
import type { Task, TaskList } from '../types';
import { separarEmoji } from './nombreLista';

const escapar = (t: string) =>
  t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function fila(t: Task): string {
  const vence = t.due_date
    ? ` · Vence: ${new Date(t.due_date.slice(0, 10) + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}`
    : '';
  const nota = t.note ? `<div class="nota">${escapar(t.note)}</div>` : '';
  return `<li class="${t.completed ? 'hecha' : ''}"><span class="caja">${t.completed ? '☑' : '☐'}</span>
    <div><div class="titulo">${t.important ? '★ ' : ''}${escapar(t.title)}</div>
    <div class="meta">${t.pasos ? `Pasos: ${t.pasos_hechos || 0} de ${t.pasos}` : ''}${escapar(vence)}</div>${nota}</div></li>`;
}

export async function imprimirLista(lista: TaskList): Promise<void> {
  // La ventana se abre antes de pedir los datos: si no, el navegador la bloquea por no venir de un clic.
  const ventana = window.open('', '_blank', 'width=800,height=900');
  if (!ventana) throw new Error('El navegador bloqueó la ventana de impresión');
  const tareas = await api.get<Task[]>(`/tasks/lists/${lista.id}/tasks`);
  const { texto } = separarEmoji(lista.name);
  const pendientes = tareas.filter(t => !t.completed);
  const hechas = tareas.filter(t => t.completed);
  ventana.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${escapar(texto)}</title>
<style>body{font-family:'Segoe UI',system-ui,sans-serif;color:#323130;margin:32px}h1{font-size:22px;margin:0 0 4px}
.fecha{color:#605e5c;font-size:12px;margin-bottom:20px}h2{font-size:14px;color:#605e5c;margin:20px 0 8px}
ul{list-style:none;padding:0;margin:0}li{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #edebe9}
.caja{font-size:16px}.titulo{font-size:14px}.meta,.nota{font-size:12px;color:#605e5c}.nota{white-space:pre-wrap;margin-top:2px}
li.hecha .titulo{text-decoration:line-through;color:#a19f9d}</style></head><body>
<h1>${escapar(texto)}</h1><div class="fecha">Impreso el ${escapar(new Date().toLocaleString('es-ES'))}</div>
<ul>${pendientes.map(fila).join('') || '<li>No hay tareas pendientes.</li>'}</ul>
${hechas.length ? `<h2>Completadas (${hechas.length})</h2><ul>${hechas.map(fila).join('')}</ul>` : ''}
</body></html>`);
  ventana.document.close();
  ventana.focus();
  ventana.print();
}
