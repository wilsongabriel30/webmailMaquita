// Formato de párrafo del redactor (grupo «Párrafo» de la cinta): sangría, interlineado, espacio antes y
// después del párrafo y dirección del texto (izquierda a derecha / derecha a izquierda).
// Todo se guarda como estilo en línea o atributo `dir`, que es lo que respetan los clientes de correo
// (Outlook, Gmail, móviles): el correo recibido se ve igual que en el redactor.
import { Extension, type CommandProps } from '@tiptap/core';
import type { Node as NodoPM } from '@tiptap/pm/model';
import type { EditorState } from '@tiptap/pm/state';

const BLOQUES = ['paragraph', 'heading'];
const BLOQUES_CON_DIRECCION = [...BLOQUES, 'blockquote', 'bulletList', 'orderedList', 'listItem'];

export const PASO_SANGRIA_PX = 40;
export const MAX_SANGRIA = 10;
export const ESPACIO_PARRAFO_PX = 12;
export const INTERLINEADOS = ['1.0', '1.15', '1.5', '2.0', '2.5', '3.0'];

export type Direccion = 'ltr' | 'rtl';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    formatoParrafo: {
      /** Aumenta la sangría: en una lista baja un nivel; en un párrafo lo desplaza 40 px. */
      aumentarSangria: () => ReturnType;
      /** Disminuye la sangría: en una lista sube un nivel; en un párrafo lo acerca al margen. */
      disminuirSangria: () => ReturnType;
      /** Interlineado del párrafo ('1.0', '1.5'…); null vuelve al normal. */
      establecerInterlineado: (valor: string | null) => ReturnType;
      /** Pone o quita el espacio antes o después del párrafo. */
      alternarEspacioParrafo: (lado: 'antes' | 'despues') => ReturnType;
      /** Dirección del texto del párrafo: de izquierda a derecha o de derecha a izquierda. */
      establecerDireccion: (direccion: Direccion) => ReturnType;
    };
  }
}

function pixeles(valor: string): number {
  const n = parseFloat(valor || '');
  return Number.isFinite(n) ? n : 0;
}

/** Recorre los bloques de la selección y les cambia atributos con `cambio`. */
function cambiarBloques(
  tipos: string[],
  cambio: (nodo: NodoPM) => Record<string, unknown> | null,
) {
  return ({ tr, state, dispatch }: CommandProps) => {
    const { from, to } = state.selection;
    let hubo = false;
    tr.doc.nodesBetween(from, to, (nodo: NodoPM, pos: number) => {
      if (!tipos.includes(nodo.type.name)) return;
      const nuevos = cambio(nodo);
      if (!nuevos) return;
      hubo = true;
      if (dispatch) tr.setNodeMarkup(pos, undefined, { ...nodo.attrs, ...nuevos });
    });
    return hubo;
  };
}

function sangriaPara(delta: number) {
  return cambiarBloques(BLOQUES, (nodo) => {
    const actual = Number(nodo.attrs.sangria) || 0;
    const nueva = Math.min(MAX_SANGRIA, Math.max(0, actual + delta));
    return nueva === actual ? null : { sangria: nueva || null };
  });
}

export const FormatoParrafo = Extension.create({
  name: 'formatoParrafo',

  addGlobalAttributes() {
    return [
      {
        types: BLOQUES,
        attributes: {
          sangria: {
            default: null,
            parseHTML: (el) => {
              const px = pixeles(el.getAttribute('dir') === 'rtl' ? el.style.marginRight : el.style.marginLeft);
              const niveles = Math.round(px / PASO_SANGRIA_PX);
              return niveles > 0 ? Math.min(MAX_SANGRIA, niveles) : null;
            },
            renderHTML: (attrs) => {
              if (!attrs.sangria) return {};
              const lado = attrs.dir === 'rtl' ? 'margin-right' : 'margin-left';
              return { style: `${lado}: ${attrs.sangria * PASO_SANGRIA_PX}px` };
            },
          },
          interlineado: {
            default: null,
            parseHTML: (el) => {
              const v = el.style.lineHeight;
              if (!v || !/^\d+(\.\d+)?$/.test(v)) return null;
              // «2» y «2.0» son lo mismo: se guarda como en el menú para que quede marcado.
              return INTERLINEADOS.find((i) => Number(i) === Number(v)) ?? v;
            },
            renderHTML: (attrs) => (attrs.interlineado ? { style: `line-height: ${attrs.interlineado}` } : {}),
          },
          espacioAntes: {
            default: null,
            parseHTML: (el) => (pixeles(el.style.marginTop) > 0 ? true : null),
            renderHTML: (attrs) => (attrs.espacioAntes ? { style: `margin-top: ${ESPACIO_PARRAFO_PX}px` } : {}),
          },
          espacioDespues: {
            default: null,
            parseHTML: (el) => (pixeles(el.style.marginBottom) > 0 ? true : null),
            renderHTML: (attrs) => (attrs.espacioDespues ? { style: `margin-bottom: ${ESPACIO_PARRAFO_PX}px` } : {}),
          },
        },
      },
      {
        types: BLOQUES_CON_DIRECCION,
        attributes: {
          dir: {
            default: null,
            parseHTML: (el) => (el.getAttribute('dir') === 'rtl' ? 'rtl' : null),
            renderHTML: (attrs) => (attrs.dir === 'rtl' ? { dir: 'rtl' } : {}),
          },
        },
      },
    ];
  },

  addCommands() {
    return {
      aumentarSangria: () => (props) => {
        if (props.editor.isActive('listItem')) return props.commands.sinkListItem('listItem');
        return sangriaPara(1)(props);
      },
      disminuirSangria: () => (props) => {
        if (props.editor.isActive('listItem')) return props.commands.liftListItem('listItem');
        return sangriaPara(-1)(props);
      },
      establecerInterlineado: (valor) =>
        cambiarBloques(BLOQUES, () => ({ interlineado: valor && valor !== '1.0' ? valor : null })),
      alternarEspacioParrafo: (lado) => {
        const attr = lado === 'antes' ? 'espacioAntes' : 'espacioDespues';
        return (props) => {
          // Si algún bloque de la selección no lo tiene, se pone en todos; si todos lo tienen, se quita.
          let todos = true;
          props.state.doc.nodesBetween(props.state.selection.from, props.state.selection.to, (n: NodoPM) => {
            if (BLOQUES.includes(n.type.name) && !n.attrs[attr]) todos = false;
          });
          return cambiarBloques(BLOQUES, () => ({ [attr]: todos ? null : true }))(props);
        };
      },
      // Como en Outlook, al cambiar de dirección el texto pasa al otro margen: se quita la alineación
      // izquierda/derecha que tuviera (la natural de la dirección manda); centrado y justificado se respetan.
      establecerDireccion: (direccion) =>
        cambiarBloques(BLOQUES_CON_DIRECCION, (nodo) => ({
          dir: direccion === 'rtl' ? 'rtl' : null,
          ...(nodo.attrs.textAlign === 'left' || nodo.attrs.textAlign === 'right' ? { textAlign: null } : {}),
        })),
    };
  },
});

/** Valor del atributo en el bloque donde está el cursor (para marcar botones y menús). */
export function atributoDelBloque(editor: { state: EditorState }, attr: string): unknown {
  const { $from } = editor.state.selection;
  for (let d = $from.depth; d > 0; d--) {
    const nodo = $from.node(d);
    if (attr in nodo.attrs) return nodo.attrs[attr];
  }
  return null;
}
