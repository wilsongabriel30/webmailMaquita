// Grupo «Párrafo» de la pestaña Mensaje de la cinta del redactor (como en Outlook):
// fila 1: viñetas, numeración, disminuir y aumentar sangría, estilos;
// fila 2: cita, alinear, espaciado, de izquierda a derecha y de derecha a izquierda.
import { useState, type MouseEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useEditorState, type Editor } from '@tiptap/react';
import { atributoDelBloque, INTERLINEADOS } from './formatoParrafo';

type Menu = { tipo: 'estilos' | 'alinear' | 'espaciado'; ancla: HTMLElement } | null;

const ICONO_ALINEAR: Record<string, string> = {
  left: 'M4 6h16M4 10h10M4 14h16M4 18h10',
  center: 'M4 6h16M7 10h10M4 14h16M7 18h10',
  right: 'M4 6h16M10 10h10M4 14h16M10 18h10',
  justify: 'M4 6h16M4 10h16M4 14h16M4 18h16',
};

function Icono({ d, s = 15 }: { d: string; s?: number }) {
  return (
    <svg className="shrink-0" style={{ width: s, height: s }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} />
    </svg>
  );
}

function Flecha() {
  return <svg className="w-[8px] h-[8px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 9l-7 7-7-7" /></svg>;
}

function Boton({ activo, alPulsar, titulo, children, conMenu }: {
  activo?: boolean; alPulsar: (e: MouseEvent<HTMLButtonElement>) => void; titulo: string; children: ReactNode; conMenu?: boolean;
}) {
  return (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={alPulsar} title={titulo} aria-label={titulo}
      aria-pressed={conMenu ? undefined : !!activo} aria-haspopup={conMenu ? 'menu' : undefined}
      className={`h-[22px] ${conMenu ? 'px-[3px] gap-[1px]' : 'w-[22px]'} rounded-[2px] flex items-center justify-center transition-colors ${
        activo ? 'bg-[#c7e0f4] text-[#0078d4]' : 'text-[#323130] hover:bg-[#e1dfdd]'
      }`}>
      {children}
    </button>
  );
}

function MenuFlotante({ ancla, ancho, alCerrar, children }: {
  ancla: HTMLElement; ancho: number; alCerrar: () => void; children: ReactNode;
}) {
  const r = ancla.getBoundingClientRect();
  const izquierda = Math.min(r?.left ?? 0, window.innerWidth - ancho - 8);
  return createPortal(
    <>
      <div className="fixed inset-0 z-[9998]" onClick={alCerrar} />
      <div role="menu" className="fixed bg-white rounded shadow-lg border border-[#edebe9] z-[9999] py-1"
        style={{ top: (r?.bottom ?? 0) + 4, left: Math.max(8, izquierda), width: ancho }}>
        {children}
      </div>
    </>,
    document.body,
  );
}

function Opcion({ alPulsar, marcada, children, className = '' }: {
  alPulsar: () => void; marcada?: boolean; children: ReactNode; className?: string;
}) {
  return (
    <button type="button" role="menuitem" onMouseDown={(e) => e.preventDefault()} onClick={alPulsar}
      className={`w-full flex items-center gap-2 text-left px-3 py-[5px] text-[13px] text-[#323130] hover:bg-[#f3f2f1] ${className}`}>
      <span className="w-[12px] text-[#0078d4] text-[12px] shrink-0">{marcada ? '✓' : ''}</span>
      <span className="flex-1">{children}</span>
    </button>
  );
}

const Separador = () => <div className="h-px bg-[#edebe9] my-1" />;

export function GrupoParrafo({ editor }: { editor: Editor }) {
  const [menu, setMenu] = useState<Menu>(null);
  const cadena = () => editor.chain().focus();
  const cerrar = () => setMenu(null);
  const alternar = (tipo: NonNullable<Menu>['tipo']) => (e: MouseEvent<HTMLButtonElement>) =>
    setMenu(menu?.tipo === tipo ? null : { tipo, ancla: e.currentTarget });

  // El editor no redibuja la cinta en cada cambio (TipTap 3): el estado de los botones se sigue aquí.
  const estado = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      vinetas: e.isActive('bulletList'),
      numeracion: e.isActive('orderedList'),
      cita: e.isActive('blockquote'),
      alineacion: (['center', 'right', 'justify'] as const).find((a) => e.isActive({ textAlign: a })) || 'left',
      interlineado: String(atributoDelBloque(e, 'interlineado') || '1.0'),
      espacioAntes: !!atributoDelBloque(e, 'espacioAntes'),
      espacioDespues: !!atributoDelBloque(e, 'espacioDespues'),
      derechaAIzquierda: atributoDelBloque(e, 'dir') === 'rtl',
    }),
  });
  const { alineacion, interlineado, espacioAntes, espacioDespues, derechaAIzquierda } = estado;

  const estilos: { etiqueta: string; activo: boolean; aplicar: () => void; clase: string }[] = [
    { etiqueta: 'Normal', activo: editor.isActive('paragraph') && !editor.isActive('blockquote') && !editor.isActive('codeBlock'),
      aplicar: () => cadena().setParagraph().run(), clase: 'text-[13px]' },
    { etiqueta: 'Título 1', activo: editor.isActive('heading', { level: 1 }), aplicar: () => cadena().setHeading({ level: 1 }).run(), clase: 'text-[20px] font-bold' },
    { etiqueta: 'Título 2', activo: editor.isActive('heading', { level: 2 }), aplicar: () => cadena().setHeading({ level: 2 }).run(), clase: 'text-[16px] font-bold' },
    { etiqueta: 'Título 3', activo: editor.isActive('heading', { level: 3 }), aplicar: () => cadena().setHeading({ level: 3 }).run(), clase: 'text-[14px] font-bold' },
    { etiqueta: 'Cita', activo: editor.isActive('blockquote'), aplicar: () => cadena().toggleBlockquote().run(), clase: 'text-[13px] italic text-[#605e5c]' },
    { etiqueta: 'Código', activo: editor.isActive('codeBlock'), aplicar: () => cadena().toggleCodeBlock().run(), clase: 'text-[12px] font-mono' },
  ];

  return (
    <div className="flex flex-col gap-[2px] py-[3px]">
      <div className="flex items-center gap-[1px]">
        <Boton titulo="Viñetas" activo={estado.vinetas} alPulsar={() => cadena().alternarLista('bulletList').run()}>
          <Icono d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
        </Boton>
        <Boton titulo="Numeración" activo={estado.numeracion} alPulsar={() => cadena().alternarLista('orderedList').run()}>
          <Icono d="M10 6h10M10 12h10M10 18h10M4 5h1v3M4 8h2M4 15.5c0-.8.7-1.3 1.2-1.3.6 0 1 .4 1 .9 0 .9-2.2 1.6-2.2 2.9h2.2" />
        </Boton>
        <Boton titulo="Disminuir sangría" alPulsar={() => cadena().disminuirSangria().run()}>
          <Icono d="M11 6h9M11 10h9M11 14h9M4 18h16M7 9l-3 3 3 3" />
        </Boton>
        <Boton titulo="Aumentar sangría" alPulsar={() => cadena().aumentarSangria().run()}>
          <Icono d="M11 6h9M11 10h9M11 14h9M4 18h16M4 9l3 3-3 3" />
        </Boton>
        <div>
          <Boton titulo="Estilos: da a tus mensajes un formato pulido" conMenu activo={menu?.tipo === 'estilos'} alPulsar={alternar('estilos')}>
            <span className="text-[12px] font-semibold leading-none">A</span>
            <Icono d="M14 19l6-6-2-2-6 6v2h2z" s={11} />
            <Flecha />
          </Boton>
        </div>
      </div>
      <div className="flex items-center gap-[1px]">
        <Boton titulo="Cita" activo={estado.cita} alPulsar={() => cadena().toggleBlockquote().run()}>
          <span className="text-[15px] font-serif font-bold leading-none mt-[5px]">&rdquo;</span>
        </Boton>
        <div>
          <Boton titulo="Alinear" conMenu activo={menu?.tipo === 'alinear'} alPulsar={alternar('alinear')}>
            <Icono d={ICONO_ALINEAR[alineacion]} />
            <Flecha />
          </Boton>
        </div>
        <div>
          <Boton titulo="Espaciado entre líneas y párrafos" conMenu activo={menu?.tipo === 'espaciado'} alPulsar={alternar('espaciado')}>
            <Icono d="M11 6h9M11 12h9M11 18h9M5 4v16M3 6l2-2 2 2M3 18l2 2 2-2" />
            <Flecha />
          </Boton>
        </div>
        <Boton titulo="De izquierda a derecha" activo={!derechaAIzquierda} alPulsar={() => cadena().establecerDireccion('ltr').run()}>
          <Icono d="M9 4h8M13 4v9M11 4a2.5 2.5 0 000 5h2M4 17h14M15 14l3 3-3 3" />
        </Boton>
        <Boton titulo="De derecha a izquierda" activo={derechaAIzquierda} alPulsar={() => cadena().establecerDireccion('rtl').run()}>
          <Icono d="M7 4h8M11 4v9M9 4a2.5 2.5 0 000 5h2M6 17h14M9 14l-3 3 3 3" />
        </Boton>
      </div>

      {menu?.tipo === 'estilos' && (
        <MenuFlotante ancla={menu.ancla} ancho={190} alCerrar={cerrar}>
          {estilos.map((e) => (
            <Opcion key={e.etiqueta} marcada={e.activo} className={e.clase} alPulsar={() => { e.aplicar(); cerrar(); }}>
              {e.etiqueta}
            </Opcion>
          ))}
        </MenuFlotante>
      )}
      {menu?.tipo === 'alinear' && (
        <MenuFlotante ancla={menu.ancla} ancho={210} alCerrar={cerrar}>
          {([['left', 'Alinear a la izquierda'], ['center', 'Centrar'], ['right', 'Alinear a la derecha'], ['justify', 'Justificar']] as const).map(([a, etiqueta]) => (
            <Opcion key={a} marcada={alineacion === a} alPulsar={() => { cadena().setTextAlign(a).run(); cerrar(); }}>
              <span className="flex items-center gap-2"><Icono d={ICONO_ALINEAR[a]} s={14} />{etiqueta}</span>
            </Opcion>
          ))}
        </MenuFlotante>
      )}
      {menu?.tipo === 'espaciado' && (
        <MenuFlotante ancla={menu.ancla} ancho={250} alCerrar={cerrar}>
          {INTERLINEADOS.map((v) => (
            <Opcion key={v} marcada={interlineado === v} alPulsar={() => { cadena().establecerInterlineado(v).run(); cerrar(); }}>
              {v.replace('.', ',')}
            </Opcion>
          ))}
          <Separador />
          <Opcion alPulsar={() => { cadena().alternarEspacioParrafo('antes').run(); cerrar(); }}>
            {espacioAntes ? 'Quitar espacio antes del párrafo' : 'Agregar espacio antes del párrafo'}
          </Opcion>
          <Opcion alPulsar={() => { cadena().alternarEspacioParrafo('despues').run(); cerrar(); }}>
            {espacioDespues ? 'Quitar espacio después del párrafo' : 'Agregar espacio después del párrafo'}
          </Opcion>
        </MenuFlotante>
      )}
    </div>
  );
}
