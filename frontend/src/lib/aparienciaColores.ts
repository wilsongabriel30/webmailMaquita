/**
 * Colores principales que la persona puede elegir en Configuración → Apariencia (13/11/2026).
 *
 * Cada color trae su familia completa de tonos (los mismos escalones que usa la compilación:
 * ver `complementos/acento/tonos.ts`). Todos los colores principales dan contraste suficiente
 * con texto blanco (nivel AA, 4,5:1 o más).
 *
 * «institucional» es el aspecto de siempre: con él no se define ninguna variable y la interfaz
 * usa los valores originales.
 */
export interface TonosAcento {
  /** Botones principales, enlaces, pestaña activa. */
  acento: string;
  /** Al pasar el ratón. */
  oscuro: string;
  /** Al pulsar; barra superior en tema oscuro. */
  masOscuro: string;
  profundo: string;
  /** Fondo de lo seleccionado. */
  claro: string;
  /** Fondo al pasar el ratón por una fila. */
  muyClaro: string;
  /** Borde de avisos y de lo seleccionado. */
  borde: string;
  /** Tema oscuro: botones y resaltados. */
  vivo: string;
  /** Tema oscuro: enlaces y textos de acento. */
  vivoClaro: string;
  /** Tema oscuro: fondo de lo seleccionado. */
  sombra: string;
  /** Tema oscuro: fondo al pasar el ratón por una fila. */
  sombraProfunda: string;
}

export interface ColorAcento {
  id: string;
  nombre: string;
  tonos: TonosAcento;
  /** Tema oscuro: color del texto y los trazos de acento (legible sobre fondo oscuro). */
  textoEnOscuro: string;
  /** Tema oscuro: texto de acento al pasar el ratón. */
  textoEnOscuroSuave: string;
}

export const ACENTO_INSTITUCIONAL = 'institucional';

export const COLORES_ACENTO: ColorAcento[] = [
  {
    id: 'institucional', nombre: 'Institucional (por defecto)',
    tonos: { acento: '#0078d4', oscuro: '#106ebe', masOscuro: '#005a9e', profundo: '#004578', claro: '#deecf9', muyClaro: '#eff6fc', borde: '#c7e0f4', vivo: '#0a84ff', vivoClaro: '#4da3e8', sombra: '#1a3a5c', sombraProfunda: '#1e3450' },
    textoEnOscuro: '#58a9e9', textoEnOscuroSuave: '#78b9ee',
  },
  {
    id: 'verde', nombre: 'Verde',
    tonos: { acento: '#2e7d32', oscuro: '#29702d', masOscuro: '#225e26', profundo: '#1a471d', claro: '#e4eee4', muyClaro: '#f1f7f2', borde: '#cde0ce', vivo: '#2e7d32', vivoClaro: '#75a978', sombra: '#233e25', sombraProfunda: '#223523' },
    textoEnOscuro: '#7bac7d', textoEnOscuroSuave: '#93bc96',
  },
  {
    id: 'turquesa', nombre: 'Turquesa',
    tonos: { acento: '#00797d', oscuro: '#006d70', masOscuro: '#005b5e', profundo: '#004547', claro: '#deeeee', muyClaro: '#eef6f7', borde: '#c2dfe0', vivo: '#00797d', vivoClaro: '#5ca9ac', sombra: '#143d3e', sombraProfunda: '#173435' },
    textoEnOscuro: '#63acaf', textoEnOscuroSuave: '#80bcbe',
  },
  {
    id: 'morado', nombre: 'Morado',
    tonos: { acento: '#6b4bb5', oscuro: '#6044a3', masOscuro: '#503888', profundo: '#3d2b67', claro: '#ece8f5', muyClaro: '#f5f3fa', borde: '#dbd4ed', vivo: '#6b4bb5', vivoClaro: '#a693d3', sombra: '#382d51', sombraProfunda: '#302942' },
    textoEnOscuro: '#a693d3', textoEnOscuroSuave: '#b6a6db',
  },
  {
    id: 'magenta', nombre: 'Magenta',
    tonos: { acento: '#b4257f', oscuro: '#a22172', masOscuro: '#871c5f', profundo: '#671548', claro: '#f5e3ee', muyClaro: '#faf1f7', borde: '#edcbe0', vivo: '#b4257f', vivoClaro: '#d483b6', sombra: '#51203f', sombraProfunda: '#422035' },
    textoEnOscuro: '#d483b6', textoEnOscuroSuave: '#dc99c3',
  },
  {
    id: 'rojo', nombre: 'Rojo',
    tonos: { acento: '#c2313f', oscuro: '#af2c39', masOscuro: '#92252f', profundo: '#6f1c24', claro: '#f7e4e6', muyClaro: '#fbf2f3', borde: '#f0ced1', vivo: '#c2313f', vivoClaro: '#da838c', sombra: '#562429', sombraProfunda: '#452326' },
    textoEnOscuro: '#da838c', textoEnOscuroSuave: '#e199a1',
  },
  {
    id: 'naranja', nombre: 'Naranja',
    tonos: { acento: '#b8500f', oscuro: '#a6480e', masOscuro: '#8a3c0b', profundo: '#692e09', claro: '#f6e8e0', muyClaro: '#faf4ef', borde: '#eed5c5', vivo: '#b8500f', vivoClaro: '#d18d63', sombra: '#522f19', sombraProfunda: '#432a1a' },
    textoEnOscuro: '#d39269', textoEnOscuroSuave: '#dba685',
  },
  {
    id: 'pizarra', nombre: 'Gris pizarra',
    tonos: { acento: '#475c7a', oscuro: '#40536e', masOscuro: '#35455c', profundo: '#283446', claro: '#e7eaee', muyClaro: '#f3f4f6', borde: '#d3d8df', vivo: '#475c7a', vivoClaro: '#919daf', sombra: '#2c333d', sombraProfunda: '#282d34' },
    textoEnOscuro: '#919daf', textoEnOscuroSuave: '#a5afbd',
  },
];

/** Escalón de la familia → nombre de su variable CSS (sin el sufijo «-trazo»). */
const VARIABLE: Record<keyof TonosAcento, string> = {
  acento: '--acento', oscuro: '--acento-oscuro', masOscuro: '--acento-mas-oscuro', profundo: '--acento-profundo',
  claro: '--acento-claro', muyClaro: '--acento-muy-claro', borde: '--acento-borde',
  vivo: '--acento-vivo', vivoClaro: '--acento-vivo-claro', sombra: '--acento-sombra', sombraProfunda: '--acento-sombra-profunda',
};

/** Todas las variables que puede definir un color (para poder quitarlas). */
export const VARIABLES_ACENTO: string[] = Object.values(VARIABLE).flatMap((v) => [v, v + '-trazo']);

export function colorAcento(id: string | null | undefined): ColorAcento {
  return COLORES_ACENTO.find((c) => c.id === id) ?? COLORES_ACENTO[0];
}

/**
 * Variables CSS de un color. Con el institucional no hay ninguna (se usan los valores originales).
 * En tema oscuro los trazos fuertes (texto, bordes, iconos) pasan a un tono claro para que se lean.
 */
export function variablesDeAcento(id: string, oscuro: boolean): Record<string, string> {
  const color = colorAcento(id);
  if (color.id === ACENTO_INSTITUCIONAL) return {};
  const salida: Record<string, string> = {};
  for (const escalon of Object.keys(VARIABLE) as (keyof TonosAcento)[]) {
    salida[VARIABLE[escalon]] = color.tonos[escalon];
    salida[VARIABLE[escalon] + '-trazo'] = color.tonos[escalon];
  }
  if (oscuro) {
    salida['--acento-trazo'] = color.textoEnOscuro;
    salida['--acento-oscuro-trazo'] = color.textoEnOscuroSuave;
    salida['--acento-mas-oscuro-trazo'] = color.textoEnOscuroSuave;
    salida['--acento-profundo-trazo'] = color.textoEnOscuroSuave;
  }
  return salida;
}
