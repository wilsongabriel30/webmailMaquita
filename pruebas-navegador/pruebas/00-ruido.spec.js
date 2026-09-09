// Qué se aparta como ruido conocido y qué NO. Sin navegador: comprueba el separador a secas.
//
// Existe por una lección cara: un filtro de ruido demasiado ancho esconde los fallos de verdad,
// y uno demasiado estrecho hace fallar recorridos por cosas que son de diseño. Aquí se fija la
// frontera para que no se mueva sola.
const { test, expect } = require('@playwright/test');
const { separarRuido } = require('./apoyo');

test('aparta el ruido conocido del chat en otra máquina', () => {
  const { reales, ruido } = separarRuido([
    '404 GET /api/chat/conversations',
    '401 GET /sso/entrar',
    '401 GET /api/chat/mensajes',
  ]);
  expect(reales).toEqual([]);
  expect(ruido).toHaveLength(3);
});

test('el 404 del contador solo se perdona una vez', () => {
  const { reales } = separarRuido([
    '404 GET /api/chat/conversations',
    '404 GET /api/chat/conversations',
  ]);
  // La carrera de arranque ocurre una vez; repetida ya es un fallo y tiene que verse.
  expect(reales).toEqual(['404 GET /api/chat/conversations']);
});

test('no aparta fallos de verdad', () => {
  const fallos = [
    '500 GET /api/mail/folders',
    '404 GET /api/chat/otra-cosa',
    '403 POST /api/mail/send',
  ];
  const { reales, ruido } = separarRuido(fallos);
  expect(reales).toEqual(fallos);
  expect(ruido).toEqual([]);
});
