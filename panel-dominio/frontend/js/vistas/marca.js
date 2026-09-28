import { api } from '../api.js';
import { el, agregar, aviso, campo } from '../ui.js';

const CAMPOS = [
  ['org_name', 'Nombre de la organización', 'text'], ['org_slogan', 'Lema', 'text'],
  ['org_email', 'Correo de contacto', 'email'], ['org_phone', 'Teléfono', 'text'],
  ['org_website', 'Página web', 'url'], ['footer_text', 'Texto al pie', 'text'],
];

function imagen(empresa, tipo, titulo, maxKb, recargar) {
  const vista = el('div', { clase: 'vista-imagen' }, empresa[tipo] ? 'Cargando…' : 'Sin imagen propia: se usa la general.');
  if (empresa[tipo]) {
    api.imagen(`/marca/${empresa.dominio}/archivo/${tipo}`)
      .then(url => vista.replaceChildren(el('img', { src: url, alt: `${titulo} de ${empresa.dominio}` })))
      .catch(() => vista.replaceChildren('No se pudo mostrar la imagen.'));
  }
  const elegir = el('input', { type: 'file', accept: tipo === 'favicon' ? 'image/png,image/x-icon,image/webp' : 'image/png,image/jpeg,image/webp', id: `archivo-${tipo}-${empresa.dominio}` });
  elegir.addEventListener('change', async () => {
    const archivo = elegir.files[0];
    if (!archivo) return;
    if (archivo.size > maxKb * 1024) { recargar(null, `La imagen pesa ${Math.ceil(archivo.size / 1024)} KB; el máximo es ${maxKb} KB.`); return; }
    try { await api.subir(`/marca/${empresa.dominio}/archivo/${tipo}`, archivo); recargar(`${titulo} actualizado.`); }
    catch (e) { recargar(null, e.message); }
  });
  return el('div', { clase: 'imagen-marca' },
    el('label', { for: elegir.id }, titulo), vista, elegir,
    el('p', { clase: 'ayuda' }, `PNG, JPG o WebP${tipo === 'favicon' ? ' (o ICO)' : ''}, hasta ${maxKb} KB.`),
    empresa[tipo] ? el('button', { clase: 'enlace peligro', type: 'button', alClick: async () => {
      await api.del(`/marca/${empresa.dominio}/archivo/${tipo}`); recargar(`${titulo} quitado: vuelve a usarse el general.`);
    } }, `Quitar ${titulo.toLowerCase()}`) : null);
}

function tarjeta(empresa, maxKb, recargar) {
  const campos = CAMPOS.map(([clave, etiqueta, tipo]) => [clave, campo(etiqueta, { type: tipo, maxlength: 500, valor: empresa.marca[clave] || '' })]);
  const color = campo('Color principal', { type: 'color', valor: empresa.marca.primary_color || '#0f6cbd' });
  const usarColor = el('input', { type: 'checkbox', id: 'usar-color-' + empresa.dominio });
  usarColor.checked = !!empresa.marca.primary_color;
  const guardar = el('button', { clase: 'boton', type: 'submit' }, 'Guardar textos y color');
  return el('section', { clase: 'caja', 'aria-label': 'Marca de ' + empresa.dominio },
    el('h2', null, empresa.dominio),
    empresa.portales.length
      ? el('p', { clase: 'ayuda' }, 'Tu gente entra por: ', empresa.portales.map(p => p.host + (p.activo ? '' : ' (pausado)')).join(', '))
      : el('p', { clase: 'ayuda' }, 'Este dominio todavía no tiene una dirección de entrada propia; la marca se verá cuando el administrador general la publique.'),
    el('div', { clase: 'tarjetas' }, imagen(empresa, 'logo', 'Logo', maxKb, recargar), imagen(empresa, 'favicon', 'Icono', maxKb, recargar)),
    el('form', { alSubmit: async (e) => {
      e.preventDefault();
      guardar.disabled = true;
      const datos = Object.fromEntries(campos.map(([clave, c]) => [clave, c.entrada.value.trim()]));
      datos.primary_color = usarColor.checked ? color.entrada.value : '';
      try { await api.put('/marca/' + empresa.dominio, datos); recargar('Marca guardada.'); }
      catch (err) { recargar(null, err.message); }
    } },
      el('div', { clase: 'rejilla' }, campos.map(([, c]) => c.nodo), color.nodo),
      el('p', null, usarColor, ' ', el('label', { for: usarColor.id, clase: 'en-linea' }, 'Usar un color propio (si no, el general)')),
      el('p', { clase: 'ayuda' }, 'Lo que dejes vacío se hereda de la marca general del servidor.'),
      el('div', { clase: 'pie-form' }, guardar)));
}

export async function vistaMarca(sesion, mensaje, error) {
  const r = await api.get('/marca');
  const raiz = el('div');
  const recargar = async (bien, mal) => raiz.replaceWith(await vistaMarca(sesion, bien, mal));
  agregar(raiz,
    el('h1', null, 'Marca'),
    el('p', { clase: 'sub' }, 'Lo que ve tu gente en la pantalla de entrada del correo.'),
    mensaje ? aviso('ok', mensaje) : null, error ? aviso('error', error) : null,
    r.empresas.map(e => tarjeta(e, r.max_kb, recargar)));
  return raiz;
}
