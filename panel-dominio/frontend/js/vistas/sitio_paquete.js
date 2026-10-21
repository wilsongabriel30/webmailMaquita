// Pestaña «Subir y migrar»: un paquete propio (.zip o .tar.gz) en un sitio vacío y, con el
// respaldo de su base (.sql o .sql.gz), la migración desde otro hospedaje.
import { api } from '../api.js';
import { el, aviso, casilla } from '../ui.js';
import { enRutaSitio, mensajes, unaVez } from './sitio_comun.js';

function resultado(r) {
  const m = r.migracion;
  const base = r.base_datos ? [
    { etiqueta: 'Servidor de la base', valor: r.bd_servidor || 'localhost' }, { etiqueta: 'Base de datos', valor: r.base_datos },
    { etiqueta: 'Usuario de la base', valor: r.bd_usuario }, { etiqueta: 'Contraseña de la base', valor: r.bd_clave, secreto: true },
  ] : [];
  if (m) {
    unaVez('Sitio migrado', [
      { etiqueta: 'Sitio', valor: r.url }, { etiqueta: 'Tablas importadas', valor: String(r.tablas ?? 0) },
      { etiqueta: 'Aplicación reconocida', valor: m.aplicacion === 'env' ? 'archivo .env' : m.aplicacion || 'no reconocida' },
      { etiqueta: 'Conexión a la base', valor: m.conexion === 'actualizada' ? 'actualizada sola' : 'ponla a mano con los datos de abajo' },
      m.direccion_anterior ? { etiqueta: 'Dirección anterior reemplazada', valor: `${m.direccion_anterior} (${m.reemplazos ?? 0} cambios)` } : {},
      ...base,
    ], `${m.aviso ? 'Aviso: ' + m.aviso + '. ' : ''}Las contraseñas de los usuarios del sitio siguen siendo las de antes. Apunta el DNS del dominio a este servidor y activa HTTPS. La contraseña de la base no se vuelve a mostrar.`);
    return;
  }
  unaVez('Paquete instalado', [{ etiqueta: 'Abre el sitio y sigue su instalador', valor: r.url }, { etiqueta: 'Carpeta pública', valor: r.raiz_web }, ...base],
    'Copia estos datos ahora: la contraseña de la base no se vuelve a mostrar. Al terminar el instalador, bórralo si la aplicación lo pide (por FTP).');
}

export function pestanaPaquete(ctx) {
  const { s, sitio, estado } = ctx;
  const max = estado.subida_max_mb || 512;
  const ruta = `/sitios/${enRutaSitio(sitio)}/paquete`;
  const msj = mensajes();
  const paquete = el('input', { type: 'file', id: 'paquete-archivo', accept: '.zip,.tar.gz,.tgz,application/zip,application/gzip' });
  const respaldo = el('input', { type: 'file', id: 'paquete-respaldo', accept: '.sql,.sql.gz,application/sql,application/gzip' });
  const conBd = casilla('Crear una base de datos para la aplicación', true);
  const avance = el('progress', { max: '100', value: '0', hidden: true, 'aria-label': 'Avance de la subida' });
  const subir = el('button', { clase: 'boton', type: 'submit' }, 'Subir e instalar');
  const pesa = (f) => f.size > max * 1048576;
  const enviar = async (e) => {
    e.preventDefault();
    const archivo = paquete.files[0], copia = respaldo.files[0];
    if (!archivo) { msj.error('Elige el paquete (.zip o .tar.gz).'); return; }
    if (pesa(archivo) || (copia && pesa(copia))) { msj.error(`Cada archivo puede pesar como máximo ${max} MB.`); return; }
    subir.disabled = true;
    avance.hidden = false;
    try {
      let nombreRespaldo = '';
      if (copia) {
        msj.espera('Subiendo el respaldo de la base…');
        nombreRespaldo = (await api.subirGrande(ruta + '/respaldo', copia, (p) => { avance.value = p; })).respaldo;
      }
      msj.espera('Subiendo el paquete…');
      const consulta = `?con_bd=${conBd.entrada.checked || copia ? 1 : 0}&nombre=${encodeURIComponent(archivo.name.slice(0, 120))}`
        + (nombreRespaldo ? '&respaldo=' + nombreRespaldo : '');
      const r = await api.subirGrande(ruta + consulta, archivo, (p) => {
        avance.value = p;
        if (p >= 100) msj.espera(copia ? 'Instalando y migrando la base. Puede tardar varios minutos; no cierres esta página.' : 'Instalando el paquete…');
      });
      msj.limpiar();
      resultado(r);
      ctx.recargar();
    } catch (err) { msj.error(err.message); }
    finally { subir.disabled = false; avance.hidden = true; avance.value = 0; }
  };
  return el('form', { alSubmit: enviar },
    el('h2', null, 'Subir un paquete o migrar un sitio'),
    s.app ? aviso('nota', 'Este sitio ya tiene una aplicación. El paquete solo se puede instalar en un sitio vacío.') : null,
    el('p', { clase: 'ayuda' }, `Tu propia aplicación o la copia de un sitio que tenías en otro hospedaje, hasta ${max} MB por archivo. Con una conexión lenta, la subida puede tardar: deja esta página abierta.`),
    el('label', { for: paquete.id }, 'Paquete (.zip o .tar.gz)'), paquete,
    el('label', { for: respaldo.id }, 'Respaldo de la base (opcional, .sql o .sql.gz): con él es una migración'), respaldo,
    conBd.nodo, avance, msj.nodo,
    el('div', { clase: 'pie-form' }, subir));
}
