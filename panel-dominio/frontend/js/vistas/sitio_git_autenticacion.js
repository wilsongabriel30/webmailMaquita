// «Autenticación» de git del sitio (repositorios privados): la usan la pestaña «Git» del sitio PHP y la de las
// aplicaciones Node.js, Python y estáticas. El secreto se envía una vez y no se vuelve a mostrar: el servidor solo
// devuelve el método, la huella de la clave o los últimos caracteres del token y la fecha.
import { api } from '../api.js';
import { el, campo, lista } from '../ui.js';
import { copiar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';

// La recomendada primero; cada una con su ayuda breve (dónde se crea).
export const METODOS = [
  { valor: 'clave-generada', texto: 'Clave de despliegue (recomendada)',
    ayuda: 'El servidor crea una clave solo para este sitio: la privada nunca sale de él. Sirve solo para este repositorio, en solo lectura, y se revoca en GitHub sin afectar nada más. Usa la dirección SSH (git@github.com:organizacion/repo.git).' },
  { valor: 'clave-propia', texto: 'Clave SSH propia',
    ayuda: 'Pega una clave privada SSH (ed25519, ECDSA o RSA de 3072 bits o más) sin frase de paso, creada solo para este repositorio: nunca la de tu cuenta personal. Usa la dirección SSH.' },
  { valor: 'token-https', texto: 'Token de acceso (HTTPS)',
    ayuda: 'GitHub: Settings → Developer settings → Fine-grained tokens, solo este repositorio, «Contents: Read-only» y con caducidad. GitLab: Settings → Repository → Deploy tokens (read_repository). Gitea y Forgejo: Configuración → Aplicaciones (read:repository). Bitbucket: Repository settings → Access tokens (Read). Usa la dirección https://.' },
  { valor: 'usuario-contrasena', texto: 'Usuario y contraseña (HTTPS)',
    ayuda: 'Solo para servidores de git propios que no admitan claves ni tokens, con una cuenta que únicamente pueda leer este repositorio. Usa la dirección https://.' },
  { valor: 'ninguna', texto: 'Ninguna (repositorio público)', ayuda: 'Repositorio público por https://: no hace falta credencial.' },
];
const nombre = (m) => (METODOS.find(x => x.valor === m) || {}).texto || m;

function resumen(a) {
  if (!a.configurada) return 'Sin credencial guardada.';
  return ['Configurada', nombre(a.metodo), a.tipo_clave, a.huella, a.usuario ? 'usuario ' + a.usuario : null,
    a.final ? '…' + a.final : null, a.fecha].filter(Boolean).join(' · ');
}

/** Caja «Autenticación». `repo()` devuelve la dirección del repositorio escrita en el formulario (para probar). */
export async function cajaAutenticacion(ctx, repo) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/git/credencial`;
  const caja = el('div', { clase: 'caja' });
  const msj = mensajes();
  const pintar = (a, texto) => {
    const metodo = lista('Autenticación', METODOS);
    metodo.entrada.value = a.metodo;
    const ayuda = el('p', { clase: 'ayuda' });
    const clave = el('textarea', { rows: '4', 'aria-label': 'Clave privada SSH', autocomplete: 'off', spellcheck: 'false',
      placeholder: '-----BEGIN OPENSSH PRIVATE KEY-----' });
    const usuario = campo('Usuario', { type: 'text', maxlength: 100, autocomplete: 'off' });
    const token = campo('Token', { type: 'password', maxlength: 512, autocomplete: 'new-password' });
    const contrasena = campo('Contraseña', { type: 'password', maxlength: 512, autocomplete: 'new-password' });
    const publica = a.metodo === 'clave-generada' && a.clave_publica ? (() => {
      const copia = el('button', { clase: 'enlace', type: 'button', alClick: () => copiar(a.clave_publica, copia) }, 'Copiar');
      return el('div', null,
        el('p', { clase: 'ayuda' }, 'En GitHub: Settings → Deploy keys → Add deploy key, pega esta clave y deja SIN marcar «Allow write access». En GitLab: Settings → Repository → Deploy keys.'),
        el('pre', { clase: 'salida' }, a.clave_publica), copia);
    })() : null;
    const guardar = el('button', { clase: 'boton', type: 'button' });
    const borrar = a.configurada ? el('button', { clase: 'enlace peligro', type: 'button' }, 'Borrar la credencial') : null;
    const ajustar = () => {
      const m = metodo.entrada.value;
      ayuda.textContent = (METODOS.find(x => x.valor === m) || {}).ayuda || '';
      clave.hidden = m !== 'clave-propia';
      usuario.nodo.hidden = !['token-https', 'usuario-contrasena'].includes(m);
      usuario.entrada.placeholder = m === 'token-https' ? 'opcional en GitHub, GitLab y Bitbucket' : '';
      token.nodo.hidden = m !== 'token-https';
      contrasena.nodo.hidden = m !== 'usuario-contrasena';
      if (publica) publica.hidden = m !== 'clave-generada';
      const misma = m === a.metodo && a.configurada;
      guardar.textContent = m === 'clave-generada' ? (misma ? 'Clave nueva' : 'Generar la clave') : m === 'ninguna' ? 'Usar sin credencial' : 'Probar y guardar';
      for (const c of [token.entrada, contrasena.entrada]) c.placeholder = misma ? '•••••• (guardada)' : '';
    };
    metodo.entrada.addEventListener('change', ajustar);
    guardar.addEventListener('click', async () => {
      const m = metodo.entrada.value;
      const datos = { metodo: m, repo: (repo() || '').trim(), regenerar: m === 'clave-generada' && m === a.metodo && a.configurada };
      if (m === 'clave-propia') datos.clave_privada = clave.value;
      if (m === 'token-https' || m === 'usuario-contrasena') datos.usuario = usuario.entrada.value.trim();
      if (m === 'token-https') datos.token = token.entrada.value.trim();
      if (m === 'usuario-contrasena') datos.contrasena = contrasena.entrada.value;
      const r = await hacer(msj, guardar, 'Comprobando con el servidor de git…', () => api.put(ruta, datos));
      if (r) pintar(r, r.prueba && !r.prueba.ok ? `Guardada, pero la prueba falló: ${r.prueba.error}`
        : m === 'clave-generada' ? 'Clave lista: añádela en el repositorio.' : 'Credencial comprobada y guardada.');
    });
    if (borrar) borrar.addEventListener('click', async () => {
      const r = await hacer(msj, borrar, 'Borrando…', () => api.del(ruta));
      if (r) pintar(r, 'Credencial borrada.');
    });
    ajustar();
    caja.replaceChildren(el('h3', null, 'Autenticación del repositorio'), el('p', { clase: 'ayuda' }, resumen(a)),
      metodo.nodo, ayuda, clave, el('div', { clase: 'rejilla' }, usuario.nodo, token.nodo, contrasena.nodo), publica,
      el('div', { clase: 'fila' }, guardar, borrar), msj.nodo);
    if (texto) msj.ok(texto);
  };
  pintar(await api.get(ruta));
  return caja;
}
