// Correos de la cola de salida que no pueden salir: reconocerlos y recuperarlos.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esIlegible, aRedaccion, archivosDe, avisoDeRechazo } from '../src/lib/colaSalidaLegible.ts';

const base = { id: 'a', createdAt: 1, status: 'failed', retries: 1, subject: 'Hola', html_body: '<p>x</p>', text_body: '' } as const;

test('un registro que sigue cifrado, o sin destinatarios, es ilegible', () => {
  assert.equal(esIlegible({ id: 'a', sobre: { v: 1 } }), true);
  assert.equal(esIlegible({ ...base, to: [] }), true);
  assert.equal(esIlegible({ ...base, to: ['  '] }), true);
  assert.equal(esIlegible({ ...base }), true);
  assert.equal(esIlegible({ ...base, to: ['ana@example.org'] }), false);
});

test('un correo legible vuelve a la redacción con sus datos y su borrador', () => {
  const d = aRedaccion({ ...base, to: ['ana@example.org'], cc: [], in_reply_to: '<1@x>', draft_uid: 758 });
  assert.deepEqual(d.to, ['ana@example.org']);
  assert.equal(d.cc, undefined);
  assert.equal(d.subject, 'Hola');
  assert.equal(d.in_reply_to, '<1@x>');
  assert.equal(d.draft_uid, 758);
});

test('los adjuntos en cola se recuperan como archivos; uno dañado no rompe el resto', async () => {
  const archivos = archivosDe({ ...base, to: ['ana@example.org'], attachments: [
    { filename: 'nota.txt', content_b64: btoa('hola'), content_type: 'text/plain' },
    { filename: 'roto.bin', content_b64: '%%%', content_type: 'application/octet-stream' },
  ] });
  assert.equal(archivos.length, 1);
  assert.equal(archivos[0].file.name, 'nota.txt');
  assert.equal(await archivos[0].file.text(), 'hola');
});

test('el aviso de rechazo dice el asunto y la causa', () => {
  assert.equal(avisoDeRechazo('Vacaciones', 'Solicitud inválida.'), 'No se pudo enviar «Vacaciones»: Solicitud inválida. Está en la Bandeja de salida.');
  assert.equal(avisoDeRechazo('', ''), 'No se pudo enviar «(sin asunto)». Está en la Bandeja de salida.');
});
