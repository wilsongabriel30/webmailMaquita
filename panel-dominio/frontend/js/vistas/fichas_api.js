// «Mi cuenta» → Fichas de API (v1.11): llaves para usar el portal desde programas propios, con alcance y
// caducidad. Se muestran una sola vez al crearlas; se pueden revocar en cualquier momento.
import { api } from '../api.js';
import { el, aviso, campo, casilla } from '../ui.js';
import { confirmar, hacer, mensajes, unaVez } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

const fecha = (iso) => (iso ? new Date(iso).toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' }) : '—');

export function vistaFichasApi() {
  const caja = el('div', { clase: 'caja' }, el('h1', null, 'Fichas de API'), el('p', { clase: 'cargando' }, 'Cargando…'));
  const msj = mensajes();
  const pintar = (datos) => {
    const areas = datos.areas || {};
    const nombreAlcance = (a) => (a === 'lectura' ? 'Ver (lectura)' : 'Cambiar: ' + (areas[a] || a));
    const nombre = campo('Nombre', { type: 'text', maxlength: 80, required: true, placeholder: 'Copias nocturnas' }, 'Para reconocerla en esta lista.');
    const dias = campo('Caduca en (días)', { type: 'number', min: 1, max: datos.dias_maximos || 365, required: true, valor: '90' });
    const codigo = campo('Código del segundo factor', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 7,
      pattern: '[0-9 ]{6,7}' }, 'Uno nuevo de tu aplicación de códigos.');
    const alcances = [['lectura', casilla(nombreAlcance('lectura'), true)],
      ...Object.keys(areas).map(a => [a, casilla(nombreAlcance(a), false)])];
    const crear = boton('Crear la ficha', 'boton', null, 'submit');
    poner(caja, el('h1', null, 'Fichas de API'),
      el('p', { clase: 'ayuda' }, 'Una ficha deja a un programa usar este portal en tu nombre (cabecera «Authorization: Bearer …»), solo para lo que elijas ',
        'y hasta que caduque. Con una ficha no se puede cambiar tu contraseña ni el segundo factor, ni crear otras fichas. Todo lo que haga queda en la auditoría.'),
      (datos.fichas || []).length ? el('ul', { clase: 'miembros' }, datos.fichas.map(f => el('li', null,
        el('div', null, el('strong', null, f.nombre), ' ', el('code', null, f.prefijo + '…'),
          f.revocada ? el('span', { clase: 'marca no' }, 'revocada') : null,
          el('div', { clase: 'ayuda' }, (f.alcances || []).map(nombreAlcance).join(' · ')),
          el('div', { clase: 'ayuda' }, `Creada ${fecha(f.creada)} · vence ${fecha(f.vence)} · último uso ${fecha(f.ultimo_uso)}`)),
        f.revocada ? null : boton('Revocar', 'enlace peligro', async (b) => {
          if (!await confirmar('Revocar la ficha', `«${f.nombre}» dejará de funcionar al instante.`, 'Revocar', true)) return;
          const r = await hacer(msj, b, 'Revocando…', () => api.del(`/fichas/${encodeURIComponent(f.id)}`));
          if (r) { cargar(); msj.ok('Ficha revocada.'); }
        })))) : el('p', { clase: 'ayuda' }, 'Ninguna.'),
      el('h2', null, 'Nueva ficha'),
      el('form', { alSubmit: async (e) => {
        e.preventDefault();
        const elegidos = alcances.filter(([, c]) => c.entrada.checked).map(([a]) => a);
        if (!elegidos.length) { msj.error('Elige al menos un alcance.'); return; }
        const r = await hacer(msj, crear, 'Creando la ficha…', () => api.post('/fichas', {
          nombre: nombre.entrada.value.trim(), alcances: elegidos, dias: Number(dias.entrada.value), codigo: codigo.entrada.value.replace(/\s/g, '') }));
        codigo.entrada.value = '';
        if (!r) return;
        unaVez('Ficha de API creada', [{ etiqueta: r.nombre, valor: r.ficha, secreto: true }, { etiqueta: 'Vence', valor: fecha(r.vence) }],
          r.aviso || 'Cópiala ahora: no se vuelve a mostrar.');
        cargar();
      } }, el('div', { clase: 'rejilla' }, nombre.nodo, dias.nodo, codigo.nodo),
      el('fieldset', null, el('legend', null, 'Alcance'), alcances.map(([, c]) => c.nodo)),
      el('div', { clase: 'pie-form' }, crear)),
      msj.nodo);
  };
  const cargar = () => api.get('/fichas').then(pintar).catch((e) => poner(caja, el('h1', null, 'Fichas de API'), aviso('error', e.message)));
  cargar();
  return caja;
}
