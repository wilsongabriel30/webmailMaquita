import { el } from '../ui.js';
import { vistaFichasApi } from './fichas_api.js';
import { vistaMiClave } from './mi_clave.js';
import { vistaSegundoFactor } from './segundo_factor.js';

export async function vistaMiCuenta(alCambiar) {
  return el('div', null, vistaMiClave(false), await vistaSegundoFactor(false, alCambiar), vistaFichasApi());
}
