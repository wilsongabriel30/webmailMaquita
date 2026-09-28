import { api } from '../api.js';
import { el, agregar, aviso } from '../ui.js';

const NOMBRES = { mx: 'MX — servidor de correo', spf: 'SPF — quién puede enviar en tu nombre', dkim: 'DKIM — firma de tus mensajes', dmarc: 'DMARC — qué hacer con los falsos' };

export async function vistaDns(sesion) {
  const raiz = el('div');
  agregar(raiz, el('h1', null, 'Verificación DNS'),
    el('p', { clase: 'sub' }, 'Cómo ve el resto del mundo a tu dominio, consultado fuera de esta red. Si algo falla, tu correo puede acabar en no deseado.'));
  for (const dominio of sesion.dominios) {
    const caja = el('section', { clase: 'caja', 'aria-label': 'DNS de ' + dominio }, el('h2', null, dominio), el('p', { clase: 'cargando' }, 'Consultando…'));
    raiz.append(caja);
    api.get('/dns/' + dominio).then(r => caja.replaceChildren(el('h2', null, dominio),
      el('ul', { clase: 'miembros' }, Object.keys(NOMBRES).map(k => el('li', null,
        el('div', null, el('strong', null, NOMBRES[k]), el('div', { clase: 'ayuda' }, r[k].mensaje),
          r[k].registros.map(x => el('code', { clase: 'registro' }, x))),
        el('span', { clase: 'marca ' + (r[k].bien === null ? 'aviso-marca' : r[k].bien ? 'si' : 'no') }, r[k].bien === null ? 'Sin dato' : r[k].bien ? 'Bien' : 'Revisar')))),
      r.existe === false ? aviso('error', 'Este dominio no existe en internet: no está registrado o venció. Hay que registrarlo (o renovarlo) antes de poder recibir correo de fuera.') : null,
      r.consultado === false ? aviso('nota', 'No se pudo consultar ahora. Inténtalo de nuevo en unos minutos.') : null))
      .catch(e => caja.replaceChildren(el('h2', null, dominio), aviso('error', e.message)));
  }
  return raiz;
}
