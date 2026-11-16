// Cinta Ayuda: «Comentarios» necesita un destinatario y «Obtener diagnósticos» la versión real.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { elegirContacto } from '../src/lib/marca.ts';
import { lineaDeVersion } from '../src/lib/versionInstalada.ts';
import { versionInstalada } from '../complementos/version/index.ts';

test('el contacto es la primera dirección válida: administrador del dominio y, si no, la organización', () => {
  assert.equal(elegirContacto('admin@andes.example', 'info@andes.example'), 'admin@andes.example');
  assert.equal(elegirContacto(undefined, ' info@andes.example '), 'info@andes.example');
  assert.equal(elegirContacto('no es un correo', 'info@andes.example'), 'info@andes.example');
});

test('sin ninguna dirección configurada no hay contacto (el botón «Comentarios» no se muestra)', () => {
  assert.equal(elegirContacto(undefined, ''), '');
  assert.equal(elegirContacto('a@b', null), '');
});

test('los diagnósticos llevan la versión instalada y no un «v1.0» fijo', () => {
  assert.equal(lineaDeVersion('Correo', 'v1.21.1-48-gabc1234'), 'Correo v1.21.1-48-gabc1234');
  assert.equal(lineaDeVersion('Correo', ''), 'Correo (versión no disponible)');
});

test('la versión se toma de la variable indicada o de git; nunca texto arbitrario', () => {
  assert.equal(versionInstalada('.', { VERSION_INSTALADA: 'v2.0.0' }), 'v2.0.0');
  assert.equal(versionInstalada('.', { VERSION_INSTALADA: '<script>' }), '');
  assert.equal(versionInstalada('/', {}), '');
  assert.match(versionInstalada('.', {}), /^(v\d+\.\d+\.\d+(-\d+-g[0-9a-f]+)?|[0-9a-f]{7,})$/);
});
