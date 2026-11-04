import { useState } from 'react';
import { getFolderDisplayName } from '../../folders';
import type { Folder } from '../../types';

/* Opciones «Recuperar» y «Mover a…» del menú «Más acciones» de la barra móvil.
   En la Papelera, «Recuperar» devuelve el mensaje a la Bandeja de entrada.
   Equipo de Tecnología Maquita. */

const ICONO_MOVER = 'M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776';
const ICONO_RECUPERAR = 'M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3';

const claseOpcion = 'w-full text-left px-4 py-3 text-[14px] flex items-center gap-3 hover:bg-[#f3f2f1] active:bg-[#e1dfdd] text-[#323130]';

function Icono({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
  );
}

export function AccionesMoverMovil({ carpetaActual, carpetas, hayMensaje, onMover, onCerrar }: {
  carpetaActual: string;
  carpetas: (Folder | string)[];
  hayMensaje: boolean;
  onMover: (carpeta: string, aviso?: string) => void;
  onCerrar: () => void;
}) {
  const [listaAbierta, setListaAbierta] = useState(false);
  if (!hayMensaje) return null;
  const enPapelera = carpetaActual === 'Trash';
  const destinos = (carpetas || [])
    .map(f => (typeof f === 'string' ? f : f.name))
    .filter(n => n && n !== carpetaActual);

  return (
    <>
      {enPapelera && (
        <button type="button" className={claseOpcion}
          onClick={() => { onMover('INBOX', 'Recuperado en la Bandeja de entrada'); onCerrar(); }}>
          <Icono d={ICONO_RECUPERAR} />
          Recuperar a la Bandeja de entrada
        </button>
      )}
      <button type="button" className={claseOpcion} aria-expanded={listaAbierta}
        aria-controls="lista-mover-movil" onClick={() => setListaAbierta(v => !v)}>
        <Icono d={ICONO_MOVER} />
        <span className="flex-1">Mover a…</span>
        <span aria-hidden="true">{listaAbierta ? '▴' : '▾'}</span>
      </button>
      {listaAbierta && (
        <div id="lista-mover-movil" role="group" aria-label="Elegir carpeta de destino"
          className="max-h-[45vh] overflow-y-auto bg-[#faf9f8] border-y border-[#edebe9]">
          {destinos.map(nombre => (
            <button key={nombre} type="button" className={`${claseOpcion} pl-10`}
              onClick={() => { onMover(nombre); onCerrar(); }}>
              {getFolderDisplayName(nombre)}
            </button>
          ))}
        </div>
      )}
      <div className="h-px bg-[#edebe9] my-1" />
    </>
  );
}
