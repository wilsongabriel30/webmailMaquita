// Formato de párrafo del redactor (grupo «Párrafo» de la cinta): sangría, interlineado, espacio antes y
// después del párrafo y dirección del texto (izquierda a derecha / derecha a izquierda).
// Todo se guarda como estilo en línea o atributo `dir`, que es lo que respetan los clientes de correo
// (Outlook, Gmail, móviles): el correo recibido se ve igual que en el redactor.
import { Extension, type CommandProps } from '@tiptap/core';
import type { Node as NodoPM, ResolvedPos } from '@tiptap/pm/model';
import { Plugin, PluginKey, type EditorState } from '@tiptap/pm/state';

const BLOQUES = ['paragraph', 'heading'];
const LISTAS = ['bulletList', 'orderedList'];
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
      /** Pone, cambia o quita viñetas/numeración conservando la sangría (la lista entera se mueve). */
      alternarLista: (tipo: 'bulletList' | 'orderedList') => ReturnType;
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

/** La lista más externa que contiene la posición (la que se desplaza entera con la sangría). */
function listaExterna($pos: ResolvedPos): { pos: number; nodo: NodoPM } | null {
  for (let d = 1; d <= $pos.depth; d++) {
    const nodo = $pos.node(d);
    if (LISTAS.includes(nodo.type.name)) return { pos: $pos.before(d), nodo };
  }
  return null;
}

/** Cambia la sangría de la lista entera donde está el cursor (como Outlook con el primer elemento). */
function sangriaDeLista(delta: number) {
  return ({ tr, state, dispatch }: CommandProps) => {
    const lista = listaExterna(state.selection.$from);
    if (!lista) return false;
    const actual = Number(lista.nodo.attrs.sangria) || 0;
    const nueva = Math.min(MAX_SANGRIA, Math.max(0, actual + delta));
    if (nueva === actual) return false;
    if (dispatch) tr.setNodeMarkup(lista.pos, undefined, { ...lista.nodo.attrs, sangria: nueva || null });
    return true;
  };
}

/** Listas externas que toca la selección (la del cursor y las que quedan dentro de lo seleccionado). */
function listasEnSeleccion(doc: NodoPM, desde: number, hasta: number): { pos: number; nodo: NodoPM }[] {
  const listas = new Map<number, NodoPM>();
  const delCursor = listaExterna(doc.resolve(desde));
  if (delCursor) listas.set(delCursor.pos, delCursor.nodo);
  doc.nodesBetween(desde, hasta, (nodo, pos) => {
    if (LISTAS.includes(nodo.type.name)) { listas.set(pos, nodo); return false; }
    return true;
  });
  return [...listas].map(([pos, nodo]) => ({ pos, nodo }));
}

/** Sangría que tiene la lista externa del cursor o de la selección (0 si no hay lista). */
function sangriaListaActual(state: EditorState): number {
  const { from, to } = state.selection;
  return Math.max(0, ...listasEnSeleccion(state.doc, from, to).map((l) => Number(l.nodo.attrs.sangria) || 0));
}

/** Profundidad de anidamiento de la lista en el cursor (1 = elemento de primer nivel). */
function nivelDeLista($pos: ResolvedPos): number {
  let niveles = 0;
  for (let d = 1; d <= $pos.depth; d++) if (LISTAS.includes($pos.node(d).type.name)) niveles++;
  return niveles;
}

function sangriaPara(delta: number) {
  return cambiarBloques(BLOQUES, (nodo) => {
    const actual = Number(nodo.attrs.sangria) || 0;
    const nueva = Math.min(MAX_SANGRIA, Math.max(0, actual + delta));
    return nueva === actual ? null : { sangria: nueva || null };
  });
}

const ATRIBUTO_SANGRIA = {
  default: null,
  parseHTML: (el: HTMLElement) => {
    const px = pixeles(el.getAttribute('dir') === 'rtl' ? el.style.marginRight : el.style.marginLeft);
    const niveles = Math.round(px / PASO_SANGRIA_PX);
    return niveles > 0 ? Math.min(MAX_SANGRIA, niveles) : null;
  },
  renderHTML: (attrs: Record<string, unknown>) => {
    if (!attrs.sangria) return {};
    const lado = attrs.dir === 'rtl' ? 'margin-right' : 'margin-left';
    return { style: `${lado}: ${Number(attrs.sangria) * PASO_SANGRIA_PX}px` };
  },
};

export const FormatoParrafo = Extension.create({
  name: 'formatoParrafo',

  addGlobalAttributes() {
    return [
      {
        types: BLOQUES,
        attributes: {
          sangria: ATRIBUTO_SANGRIA,
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
      // En una lista la sangría la lleva la lista entera: así la viñeta o el número se mueven con el texto.
      { types: LISTAS, attributes: { sangria: ATRIBUTO_SANGRIA } },
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

  // Si un párrafo con sangría entra en una lista (botón, numeración, «- » al escribir, pegar…), su sangría
  // pasa a la lista externa: si se quedara en el párrafo, el texto se iría a la derecha y la viñeta no.
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('sangriaEnListas'),
        appendTransaction: (transacciones, _anterior, estado) => {
          if (!transacciones.some((t) => t.docChanged)) return null;
          const listas = new Map<number, number>();
          const parrafos: number[] = [];
          estado.doc.descendants((nodo, pos, padre) => {
            if (!BLOQUES.includes(nodo.type.name) || !nodo.attrs.sangria || padre?.type.name !== 'listItem') return;
            parrafos.push(pos);
            const lista = listaExterna(estado.doc.resolve(pos));
            if (lista) listas.set(lista.pos, Math.max(listas.get(lista.pos) || 0, Number(nodo.attrs.sangria)));
          });
          if (!parrafos.length) return null;
          const tr = estado.tr;
          for (const pos of parrafos) {
            const nodo = tr.doc.nodeAt(pos);
            if (nodo) tr.setNodeMarkup(pos, undefined, { ...nodo.attrs, sangria: null });
          }
          for (const [pos, sangria] of listas) {
            const nodo = tr.doc.nodeAt(pos);
            if (nodo && !nodo.attrs.sangria) tr.setNodeMarkup(pos, undefined, { ...nodo.attrs, sangria });
          }
          return tr;
        },
      }),
    ];
  },

  addCommands() {
    return {
      // En una lista: anida el elemento si se puede; si no (primer elemento), desplaza la lista entera.
      aumentarSangria: () => (props) => {
        if (props.editor.isActive('listItem')) {
          if (props.editor.can().sinkListItem('listItem')) return props.commands.sinkListItem('listItem');
          return sangriaDeLista(1)(props);
        }
        return sangriaPara(1)(props);
      },
      // En una lista de primer nivel con sangría, primero acerca la lista al margen; después saca el elemento.
      disminuirSangria: () => (props) => {
        if (props.editor.isActive('listItem')) {
          if (nivelDeLista(props.state.selection.$from) === 1 && sangriaListaActual(props.state) > 0) {
            return sangriaDeLista(-1)(props);
          }
          return props.commands.liftListItem('listItem');
        }
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
      alternarLista: (tipo) => ({ state, commands }) => {
        const previa = sangriaListaActual(state);
        const hecho = tipo === 'bulletList' ? commands.toggleBulletList() : commands.toggleOrderedList();
        if (!hecho || !previa) return hecho;
        // Tras el cambio: si sigue en lista (viñetas ⇄ numeración), la lista nueva hereda la sangría;
        // si se quitó la lista, los párrafos se quedan donde estaba el texto.
        return commands.command(({ tr, dispatch }) => {
          const listas = listasEnSeleccion(tr.doc, tr.selection.from, tr.selection.to);
          if (dispatch) {
            if (listas.length) {
              for (const l of listas) {
                if (!l.nodo.attrs.sangria) tr.setNodeMarkup(l.pos, undefined, { ...l.nodo.attrs, sangria: previa });
              }
            } else {
              tr.doc.nodesBetween(tr.selection.from, tr.selection.to, (nodo, pos) => {
                if (BLOQUES.includes(nodo.type.name) && !nodo.attrs.sangria) {
                  tr.setNodeMarkup(pos, undefined, { ...nodo.attrs, sangria: previa });
                }
              });
            }
          }
          return true;
        });
      },
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
