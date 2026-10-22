// «Información del servidor»: lo que hace falta para configurar programas (FTP, correo, DNS) y saber qué ofrece el
// hospedaje. Solo lo tuyo y lo común: nada de otros dominios ni datos internos del servidor.
import { api } from '../api.js';
import { el } from '../ui.js';
import { megas } from './sitio_comun.js';

const fila = (etiqueta, ...valor) => el('li', null, el('span', null, etiqueta), el('strong', null, ...valor));
const codigo = (t) => el('code', null, String(t));

export async function vistaServidor() {
  const r = await api.get('/sitios/servidor');
  const php = r.php || {}, ftp = r.ftp, correo = r.correo || {}, rp = r.limites_php || {}, ra = r.limites_aplicaciones || {};
  const ns = Object.entries(r.servidores_de_nombres || {});
  const caja = (titulo, ...hijos) => el('section', { clase: 'caja', 'aria-label': titulo }, el('h2', null, titulo), el('ul', { clase: 'miembros' }, ...hijos));
  return el('div', null,
    el('p', { clase: 'migas' }, el('a', { href: '#sitios' }, 'Mi sitio web'), ' › Información del servidor'),
    el('h1', null, 'Información del servidor'),
    el('p', { clase: 'sub' }, 'Datos para configurar tus programas y saber qué ofrece el hospedaje.'),
    el('div', { clase: 'tarjetas' },
      caja('Servidor',
        fila('Nombre', codigo(r.servidor || '—')),
        fila('IP compartida', codigo(r.ip_compartida || 'pregúntala al administrador general')),
        ...ns.map(([d, lista]) => fila(`Servidores de nombres de ${d}`, ...lista.map((n, i) => [i ? ', ' : '', codigo(n)])))),
      caja('PHP',
        fila('Versiones instaladas', (php.instaladas || []).join(', ') || '—'),
        fila('De serie para sitios nuevos', php.de_serie || '—'),
        ...Object.entries(php.notas || {}).map(([v, n]) => fila(`PHP ${v}`, n)),
        fila('Memoria por proceso', megas(rp.memoria_mb)), fila('Subida máxima', megas(rp.subida_mb)),
        fila('Tiempo máximo', `${rp.tiempo_s || '—'} s`), fila('Procesos a la vez por sitio', String(rp.procesos || '—'))),
      caja('Archivos (FTP y SFTP)',
        fila('Servidor', codigo(r.servidor || '—')),
        ftp ? fila('FTP', `puerto ${ftp.puerto}${ftp.cifrado ? ', cifrado obligatorio (FTPS explícito)' : ''}`) : fila('FTP', 'no disponible'),
        ftp && ftp.pasivos ? fila('Puertos pasivos', ftp.pasivos) : null,
        fila('SFTP', `puerto ${(r.sftp || {}).puerto || 22}`),
        fila('Usuario', 'el de cada sitio (pestaña «FTP»)')),
      caja('Rutas de tus sitios',
        fila('Carpeta pública', codigo((r.rutas || {}).publica || '')),
        fila('Por SFTP', codigo((r.rutas || {}).por_sftp || '/publico')),
        fila('Temporales y registros de PHP', codigo((r.rutas || {}).temporal || '')),
        fila('Registros de nginx', codigo((r.rutas || {}).registros || ''))),
      caja('Correo',
        fila('Servidor', codigo(correo.servidor || '—')),
        correo.imap ? fila('IMAP (entrada)', `puerto ${correo.imap.puerto}, ${correo.imap.cifrado}`) : null,
        ...(correo.smtp || []).map(s => fila('SMTP (salida)', `puerto ${s.puerto}, ${s.cifrado}`)),
        fila('Usuario', correo.autenticacion || '')),
      caja('Límites de tu plan',
        ...Object.entries(r.cuotas || {}).map(([d, c]) => fila(d, `${c.max_sitios} sitio(s), ${megas(c.disco_mb)} de disco, ${megas(c.bases_mb)} de bases`)),
        fila('Aplicaciones Node.js y Python', `${megas(ra.memoria_mb)} de memoria, ${(ra.cpu_por_ciento || 0) / 100} núcleos`)),
      caja('DNS dinámico',
        fila('Dirección de actualización', codigo(`https://${location.hostname}${r.dns_dinamico || '/nic/update'}`)),
        fila('Protocolo', 'dyndns2 (ddclient, routers, inadyn)'),
        fila('Fichas', 'en la zona DNS de cada dominio'))));
}
