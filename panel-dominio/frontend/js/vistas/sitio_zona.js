// Registros DNS de la zona de un dominio, cuando la sirve este servidor. Los del correo y los
// servidores de nombres se ven en solo lectura.
import { api } from '../api.js';
import { el, agregar, aviso, campo, lista, ventana } from '../ui.js';
import { confirmar, hacer, mensajes } from './sitio_comun.js';
import { seccionDdns } from './sitio_ddns.js';

const TIPOS = ['A', 'AAAA', 'CNAME', 'TXT', 'CAA', 'SRV'];
const AYUDA_VALOR = { A: 'Dirección IPv4, p. ej. 192.0.2.10', AAAA: 'Dirección IPv6', CNAME: 'Nombre de destino, p. ej. otro.example.org',
  TXT: 'Texto, p. ej. google-site-verification=…', CAA: 'p. ej. issue letsencrypt.org', SRV: '«peso puerto destino», p. ej. 1 443 servidor' };

function formulario(dominio, registro, alGuardar) {
  const nombre = campo('Nombre', { type: 'text', maxlength: 253, valor: registro ? registro.nombre : '' }, '«@» es el propio dominio; «www» es www.' + dominio);
  const tipo = lista('Tipo', TIPOS.map(t => ({ valor: t, texto: t })));
  tipo.entrada.value = registro ? registro.tipo : 'A';
  const valor = campo('Valor', { type: 'text', maxlength: 2048, valor: registro ? registro.valor : '' });
  const ttl = campo('TTL (segundos)', { type: 'number', min: 60, max: 86400, valor: String(registro ? registro.ttl : 3600) });
  const prioridad = campo('Prioridad', { type: 'number', min: 0, max: 65535, valor: registro && registro.prioridad !== null ? String(registro.prioridad) : '' });
  const pista = el('p', { clase: 'ayuda' });
  const ajustar = () => { pista.textContent = AYUDA_VALOR[tipo.entrada.value] || ''; prioridad.nodo.hidden = tipo.entrada.value !== 'SRV'; };
  tipo.entrada.addEventListener('change', ajustar);
  ajustar();
  ventana(registro ? 'Cambiar registro' : 'Nuevo registro', el('div', null, nombre.nodo, tipo.nodo, valor.nodo, pista, ttl.nodo, prioridad.nodo),
    'Guardar', () => alGuardar({ nombre: nombre.entrada.value.trim() || '@', tipo: tipo.entrada.value, valor: valor.entrada.value.trim(),
      ttl: Number(ttl.entrada.value) || 3600, prioridad: tipo.entrada.value === 'SRV' && prioridad.entrada.value !== '' ? Number(prioridad.entrada.value) : null }));
}

export async function vistaZona(dominio, mensaje) {
  const ruta = '/sitios/dns/' + encodeURIComponent(dominio);
  const r = await api.get(ruta);
  const raiz = el('div');
  const recargar = async (texto) => raiz.replaceWith(await vistaZona(dominio, texto));
  const msj = mensajes();
  const registros = r.registros || [];
  const filas = registros.map(x => el('tr', null,
    el('td', null, el('code', null, x.nombre)), el('td', null, x.tipo),
    el('td', null, el('code', null, (x.prioridad !== null && x.prioridad !== undefined ? x.prioridad + ' ' : '') + x.valor)),
    el('td', null, x.ttl),
    el('td', { clase: 'acciones' }, x.protegido ? el('span', { clase: 'marca aviso-marca', title: 'Registro del correo o de los servidores de nombres' }, 'Protegido') : [
      el('button', { clase: 'enlace', type: 'button', alClick: () => formulario(dominio, x, async (reg) => { await api.put(`${ruta}/${encodeURIComponent(x.id)}`, { registro: reg }); recargar('Registro cambiado.'); }) }, 'Cambiar'),
      (() => {
        const b = el('button', { clase: 'enlace peligro', type: 'button' }, 'Borrar');
        b.addEventListener('click', async () => {
          if (!await confirmar('Borrar registro', `¿Borrar ${x.tipo} ${x.nombre}? Lo que dependa de él deja de encontrarse.`, 'Borrar', true)) return;
          if (await hacer(msj, b, 'Borrando…', () => api.del(`${ruta}/${encodeURIComponent(x.id)}`))) recargar('Registro borrado.');
        });
        return b;
      })()])));
  agregar(raiz,
    el('p', { clase: 'migas' }, el('a', { href: '#sitios' }, 'Mi sitio web'), ' › DNS de ', dominio),
    el('h1', null, 'Zona DNS de ' + dominio),
    el('p', { clase: 'sub' }, 'Los nombres de tu dominio que sirve este servidor: a dónde apunta tu sitio, verificaciones de servicios, subdominios…'),
    aviso('nota', 'Los registros marcados «Protegido» (MX, SPF, DKIM, DMARC, MTA-STS, TLSA, autoconfiguración y servidores de nombres) se ven pero no se cambian desde aquí: un error en ellos deja sin correo a todo el dominio o lo saca de internet. Si necesitas cambiar uno, pídelo al administrador general.'),
    mensaje ? aviso('ok', mensaje) : null, msj.nodo,
    el('div', { clase: 'fila' }, el('span', { clase: 'crece ayuda' }, `${registros.length} registros`),
      el('button', { clase: 'boton', type: 'button', alClick: () => formulario(dominio, null, async (reg) => { await api.post(ruta, { registro: reg }); recargar('Registro agregado. Los cambios tardan en verse en internet lo que diga su TTL.'); }) }, 'Nuevo registro')),
    el('div', { clase: 'caja tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Nombre', 'Tipo', 'Valor', 'TTL', ''].map(t => el('th', null, t)))),
      el('tbody', null, filas.length ? filas : el('tr', null, el('td', { colspan: '5', clase: 'vacio' }, 'La zona no tiene registros.'))))),
    await seccionDdns(dominio));
  return raiz;
}
