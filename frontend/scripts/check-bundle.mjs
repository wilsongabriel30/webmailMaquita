#!/usr/bin/env node
// ===========================================================================
// check-bundle.mjs — Guardia anti "X is not defined" en el bundle compilado.
//
// Detecta referencias que se USAN en el bundle pero NUNCA se definen (las que
// el empaquetador pudo haber eliminado por tree-shaking). Es exactamente la
// clase de fallo que rompio el correo: `useMessageLabels is not defined`.
//
// Metodo: parsea cada chunk con acorn, analiza ambitos con eslint-scope y
// reporta las referencias "globales" que no estan en la lista de globales
// reales del navegador/JS. Si encuentra alguna -> exit 1 (aborta el deploy).
//
// Uso: node scripts/check-bundle.mjs <dir-de-assets>
// ===========================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const acorn = require('acorn');
const eslintScope = require('eslint-scope');
const globals = require('globals');

const assetsDir = process.argv[2];
if (!assetsDir) { console.error('Uso: check-bundle.mjs <dir-assets>'); process.exit(2); }

// Lista blanca: globales reales del navegador + JS + algunos extra seguros.
const allow = new Set([
  ...Object.keys(globals.browser || {}),
  ...Object.keys(globals.builtin || {}),
  ...Object.keys(globals.es2021 || {}),
  ...Object.keys(globals.worker || {}),
  ...Object.keys(globals.serviceworker || {}),
  // Extra defensivos que algunas listas no incluyen:
  'globalThis', 'BigInt', 'WebAssembly', 'queueMicrotask', 'structuredClone',
  'reportError', 'import', 'process', 'require', 'module', 'exports',
  '__dirname', '__filename',
]);

const files = readdirSync(assetsDir).filter((f) => f.endsWith('.js'));
let problems = [];

for (const file of files) {
  const code = readFileSync(join(assetsDir, file), 'utf8');
  let ast;
  try {
    ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'module', allowHashBang: true, ranges: true });
  } catch (e) {
    problems.push(`${file}: error de sintaxis al parsear (${e.message})`);
    continue;
  }
  // Recolectar nombres protegidos por `typeof X` — esos NO revientan aunque
  // no esten definidos (typeof de un identificador inexistente es seguro).
  const typeofGuarded = new Set();
  (function walk(node) {
    if (!node || typeof node.type !== 'string') return;
    if (node.type === 'UnaryExpression' && node.operator === 'typeof'
        && node.argument && node.argument.type === 'Identifier') {
      typeofGuarded.add(node.argument.name);
    }
    for (const k in node) {
      if (k === 'range' || k === 'loc' || k === 'start' || k === 'end') continue;
      const v = node[k];
      if (Array.isArray(v)) { for (const c of v) walk(c); }
      else if (v && typeof v.type === 'string') walk(v);
    }
  })(ast);

  const sm = eslintScope.analyze(ast, { ecmaVersion: 2022, sourceType: 'module' });
  const globalScope = sm.globalScope;
  // `through` = referencias que no se resolvieron a ninguna declaracion (libres).
  const seen = new Set();
  for (const ref of globalScope.through) {
    const name = ref.identifier && ref.identifier.name;
    if (!name || allow.has(name) || seen.has(name) || typeofGuarded.has(name)) continue;
    // Solo nos importan las LECTURAS (un undefined que se invoca/lee revienta).
    if (ref.isWrite && ref.isWrite()) continue;
    seen.add(name);
    problems.push(`${file}: referencia no definida -> "${name}"`);
  }
}

if (problems.length) {
  console.error('\n❌ GUARDIA DE BUNDLE: referencias indefinidas detectadas (riesgo de "X is not defined"):');
  for (const p of problems) console.error('   - ' + p);
  console.error('\nDeploy ABORTADO. Revisa el tree-shaking / imports antes de publicar.\n');
  process.exit(1);
}
console.log(`✅ GUARDIA DE BUNDLE: ${files.length} chunks verificados, sin referencias indefinidas.`);
