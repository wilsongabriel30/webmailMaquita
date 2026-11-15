/**
 * Complemento de Vite: estilos en línea y atributos SVG que usan el azul de acento como texto fijo.
 *
 * Solo se cambia donde es seguro, es decir, donde el texto es con certeza un valor CSS:
 *   - propiedades de color dentro de `style={{ … }}` en JSX;
 *   - objetos declarados o convertidos como `CSSProperties`;
 *   - atributos `fill` / `stroke` / `stopColor` de JSX;
 *   - asignaciones directas `elemento.style.<propiedad de color> = '…'`.
 * Todo lo demás (colores que son datos: paletas, categorías, HTML de correos, impresión, `cssText`)
 * se deja como está, porque ahí una variable CSS rompería el dato.
 */
import { writeFileSync } from 'node:fs';
import ts from 'typescript';
import type { Plugin } from 'vite';
import { HAY_TONO, enGuiones, sustituirEnValor } from './tonos.ts';

const PROPIEDADES_DE_COLOR = /^(color|background|background-color|accent-color|caret-color|fill|stroke|box-shadow|text-decoration(-color)?|outline(-color)?|column-rule(-color)?|border(-(top|right|bottom|left|block|inline)(-(start|end))?)?(-color)?)$/;
const ATRIBUTOS_SVG = new Set(['fill', 'stroke', 'stopColor', 'floodColor']);
/** En tema oscuro, `dark-theme.css` aclaraba los fondos en línea de este color exacto. */
const FONDO_EXACTO = /^#0078d4$/i;

interface Cambio { inicio: number; fin: number; texto: string }
export interface Sustitucion { archivo: string; linea: number; propiedad: string; antes: string }

function analizar(codigo: string, ruta: string, informe: Sustitucion[]): Cambio[] {
  const fuente = ts.createSourceFile(ruta, codigo, ts.ScriptTarget.Latest, true, ruta.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const cambios = new Map<number, Cambio>();

  const literal = (nodo: ts.StringLiteral | ts.NoSubstitutionTemplateLiteral, propiedad: string) => {
    const antes = nodo.text;
    if (!HAY_TONO.test(antes)) return;
    const css = enGuiones(propiedad);
    const nuevo = css === 'background' && FONDO_EXACTO.test(antes.trim())
      ? 'var(--acento-fondo-linea, var(--acento, #0078d4))'
      : sustituirEnValor(antes, css);
    if (nuevo === antes) return;
    const inicio = nodo.getStart(fuente) + 1;
    const fin = nodo.getEnd() - 1;
    if (codigo.slice(inicio, fin) !== antes) return;   // con secuencias de escape no se toca
    cambios.set(inicio, { inicio, fin, texto: nuevo });
    informe.push({ archivo: ruta, linea: fuente.getLineAndCharacterOfPosition(inicio).line + 1, propiedad: css, antes });
  };

  const valor = (nodo: ts.Node | undefined, propiedad: string): void => {
    if (!nodo) return;
    if (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo)) literal(nodo, propiedad);
    else if (ts.isParenthesizedExpression(nodo)) valor(nodo.expression, propiedad);
    else if (ts.isJsxExpression(nodo)) valor(nodo.expression, propiedad);
    else if (ts.isConditionalExpression(nodo)) { valor(nodo.whenTrue, propiedad); valor(nodo.whenFalse, propiedad); }
    else if (ts.isBinaryExpression(nodo) && [ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.AmpersandAmpersandToken].includes(nodo.operatorToken.kind)) valor(nodo.right, propiedad);
  };

  const estilos = (nodo: ts.Node | undefined): void => {
    if (!nodo) return;
    if (ts.isParenthesizedExpression(nodo) || ts.isAsExpression(nodo) || ts.isSatisfiesExpression(nodo)) estilos(nodo.expression);
    else if (ts.isConditionalExpression(nodo)) { estilos(nodo.whenTrue); estilos(nodo.whenFalse); }
    else if (ts.isBinaryExpression(nodo)) { estilos(nodo.left); estilos(nodo.right); }
    else if (ts.isObjectLiteralExpression(nodo)) {
      for (const p of nodo.properties) {
        if (ts.isSpreadAssignment(p)) { estilos(p.expression); continue; }
        if (!ts.isPropertyAssignment(p)) continue;
        const nombre = ts.isIdentifier(p.name) || ts.isStringLiteral(p.name) ? p.name.text : '';
        let interior: ts.Expression = p.initializer;
        while (ts.isParenthesizedExpression(interior) || ts.isAsExpression(interior) || ts.isSatisfiesExpression(interior)) interior = interior.expression;
        if (ts.isObjectLiteralExpression(interior)) estilos(interior);
        else if (nombre && PROPIEDADES_DE_COLOR.test(enGuiones(nombre))) valor(p.initializer, nombre);
      }
    }
  };

  const esTipoDeEstilos = (tipo: ts.TypeNode | undefined) => !!tipo && tipo.getText(fuente).includes('CSSProperties');

  const visitar = (nodo: ts.Node): void => {
    if (ts.isJsxAttribute(nodo)) {
      const nombre = nodo.name.getText(fuente);
      if (nombre === 'style' && nodo.initializer && ts.isJsxExpression(nodo.initializer)) estilos(nodo.initializer.expression);
      else if (ATRIBUTOS_SVG.has(nombre)) valor(nodo.initializer, nombre === 'stopColor' || nombre === 'floodColor' ? 'fill' : nombre);
    } else if (ts.isVariableDeclaration(nodo) && esTipoDeEstilos(nodo.type)) estilos(nodo.initializer);
    else if ((ts.isAsExpression(nodo) || ts.isSatisfiesExpression(nodo)) && esTipoDeEstilos(nodo.type)) estilos(nodo.expression);
    else if (ts.isArrowFunction(nodo) && esTipoDeEstilos(nodo.type) && !ts.isBlock(nodo.body)) estilos(nodo.body);
    else if (ts.isBinaryExpression(nodo) && nodo.operatorToken.kind === ts.SyntaxKind.EqualsToken
      && ts.isPropertyAccessExpression(nodo.left) && ts.isPropertyAccessExpression(nodo.left.expression)
      && nodo.left.expression.name.text === 'style' && PROPIEDADES_DE_COLOR.test(enGuiones(nodo.left.name.text))) {
      // elemento.style.background = '#0078d4' (p. ej. al pasar el ratón)
      valor(nodo.right, nodo.left.name.text);
    } else if (ts.isReturnStatement(nodo) && nodo.expression) {
      let f: ts.Node | undefined = nodo.parent;
      while (f && !ts.isFunctionLike(f)) f = f.parent;
      if (f && ts.isFunctionLike(f) && esTipoDeEstilos(f.type)) estilos(nodo.expression);
    }
    ts.forEachChild(nodo, visitar);
  };
  visitar(fuente);
  return [...cambios.values()].sort((a, b) => b.inicio - a.inicio);
}

/** Aplica la sustitución a un archivo fuente. Devuelve null si no cambia nada. */
export function transformarFuente(codigo: string, ruta: string, informe: Sustitucion[] = []): string | null {
  if (!HAY_TONO.test(codigo)) return null;
  const cambios = analizar(codigo, ruta, informe);
  if (cambios.length === 0) return null;
  let salida = codigo;
  for (const c of cambios) salida = salida.slice(0, c.inicio) + c.texto + salida.slice(c.fin);
  return salida;
}

export function acentoEnLinea(): Plugin {
  const informe: Sustitucion[] = [];
  return {
    name: 'maquita-acento-en-linea',
    enforce: 'pre',
    transform(codigo: string, id: string) {
      const ruta = id.split('?')[0];
      if (!/\.tsx?$/.test(ruta) || !ruta.includes('/src/') || ruta.includes('/node_modules/')) return null;
      const salida = transformarFuente(codigo, ruta, informe);
      return salida === null ? null : { code: salida, map: null };
    },
    buildEnd() {
      if (informe.length === 0) return;
      const archivos = new Set(informe.map((s) => s.archivo)).size;
      console.log(`\n[acento] ${informe.length} colores en línea pasados a variable en ${archivos} archivos`);
      // Detalle opcional para revisar qué se tocó: ACENTO_INFORME=/ruta/informe.json npm run build
      const destino = process.env.ACENTO_INFORME;
      if (destino) writeFileSync(destino, JSON.stringify(informe, null, 1));
    },
  };
}
