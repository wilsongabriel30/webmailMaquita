/**
 * Complemento de PostCSS: en TODO el CSS que genera la compilación (Tailwind y hojas propias),
 * cada tono de la familia del acento pasa a `var(--acento-…, <valor original>)`.
 * Solo se tocan los valores de las declaraciones; los selectores quedan igual.
 */
import type { Declaration, Plugin } from 'postcss';
import { HAY_TONO, sustituirEnValor } from './tonos.ts';

export function acentoEnCss(): Plugin {
  return {
    postcssPlugin: 'maquita-acento-css',
    Declaration(decl: Declaration) {
      if (decl.prop.startsWith('--acento')) return;
      if (!HAY_TONO.test(decl.value)) return;
      const nuevo = sustituirEnValor(decl.value, decl.prop);
      if (nuevo !== decl.value) decl.value = nuevo;
    },
  };
}
