import { api } from '../api.js';
import { el, agregar, aviso, campo, casilla, ventana } from '../ui.js';

// Lista de sugerencias con las cuentas de los dominios propios: se escribe y se elige.
function sugerencias(id, cuentas) {
  return el('datalist', { id }, cuentas.filter(c => c.active).map(c => el('option', { value: c.username }, c.name || '')));
}

function asignar(cuentas, alTerminar, persona) {
  const quien = campo('Persona (su correo personal)', { type: 'email', required: true, maxlength: 255, autocomplete: 'off', list: 'pd-sug-personas', valor: persona || '' },
    'Quien va a ver la cuenta en su webmail.');
  const cual = campo('Cuenta que se le asigna', { type: 'email', required: true, maxlength: 255, autocomplete: 'off', list: 'pd-sug-cuentas' },
    'Por ejemplo ventas@ o la cuenta de alguien que salió.');
  const lectura = casilla('Solo lectura (puede leer, pero no enviar como esa cuenta)');
  ventana('Asignar cuenta', el('div', null, quien.nodo, cual.nodo, lectura.nodo,
    sugerencias('pd-sug-personas', cuentas), sugerencias('pd-sug-cuentas', cuentas)), 'Asignar', async () => {
    const r = await api.post('/asignaciones', { persona: quien.entrada.value, cuenta: cual.entrada.value, completo: !lectura.entrada.checked });
    alTerminar(`${r.cuenta} asignada a ${r.persona}. La verá en su webmail al volver a cargarlo.`);
  });
}

function fila(a, recargar) {
  return el('li', null,
    el('span', null, a.cuenta, a.nombre_cuenta ? el('span', { clase: 'ayuda' }, ' · ' + a.nombre_cuenta) : null, ' ',
      el('span', { clase: 'marca ' + (a.completo ? 'si' : 'aviso-marca') }, a.completo ? 'Completo' : 'Solo lectura')),
    el('span', null,
      el('button', { clase: 'enlace', 'aria-label': `${a.completo ? 'Dejar en solo lectura' : 'Dar acceso completo a'} ${a.cuenta} para ${a.persona}`, alClick: async () => {
        try { await api.put('/asignaciones/' + a.id, { completo: !a.completo }); recargar('Permiso cambiado.'); } catch (e) { recargar(e.message); }
      } }, a.completo ? 'Solo lectura' : 'Completo'),
      el('button', { clase: 'enlace peligro', 'aria-label': `Quitar ${a.cuenta} a ${a.persona}`, alClick: () => ventana('Quitar ' + a.cuenta,
        el('p', null, `${a.persona} deja de ver ${a.cuenta} en su webmail desde este momento. La cuenta y su correo no se tocan.`),
        'Quitar', async () => { await api.del('/asignaciones/' + a.id); recargar('Asignación quitada.'); }, true) }, 'Quitar')));
}

export async function vistaAsignaciones(sesion, mensaje) {
  const [asignaciones, cuentas] = await Promise.all([api.get('/asignaciones'), api.get('/cuentas')]);
  const raiz = el('div');
  const recargar = async (texto) => raiz.replaceWith(await vistaAsignaciones(sesion, texto));
  const porPersona = new Map();
  for (const a of asignaciones) {
    if (!porPersona.has(a.persona)) porPersona.set(a.persona, { nombre: a.nombre_persona, filas: [] });
    porPersona.get(a.persona).filas.push(a);
  }
  agregar(raiz,
    el('h1', null, 'Cuentas asignadas'),
    el('p', { clase: 'sub' }, 'Cuentas que una persona ve en su webmail, además de la suya, sin cerrar sesión ni abrir otra ventana.'
      + (sesion.dominios.length > 1 ? ' Puedes cruzar tus dominios: una cuenta de uno para una persona de otro.' : '')),
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('span', { clase: 'crece ayuda' }, porPersona.size === 1 ? '1 persona' : `${porPersona.size} personas`),
      el('button', { clase: 'boton', alClick: () => asignar(cuentas, recargar) }, 'Asignar cuenta')),
    porPersona.size ? [...porPersona].map(([persona, p]) => el('section', { clase: 'caja', 'aria-label': persona },
      el('div', { clase: 'fila' },
        el('div', { clase: 'crece' }, el('strong', null, persona), p.nombre ? el('div', { clase: 'ayuda' }, p.nombre) : null),
        el('button', { clase: 'enlace', alClick: () => asignar(cuentas, recargar, persona) }, 'Asignar otra')),
      el('ul', { clase: 'miembros' }, p.filas.map(a => fila(a, recargar)))))
      : el('p', { clase: 'caja vacio' }, 'Todavía nadie tiene cuentas asignadas.'));
  return raiz;
}
