// Entrada de soporte: el superadministrador abre el portal «como el cliente» con un vale de un solo uso
// (https://<portal>:8444/?vale=…). El vale se canjea una vez y se quita de la barra de direcciones.
import { api, ficha } from './api.js';
import { el, aviso } from './ui.js';

const RE_VALE = /^[A-Za-z0-9_-]{32,128}$/;

/** Si la dirección trae un vale, lo canjea por una sesión de soporte. Devuelve un error para mostrar, o null. */
export async function canjearVale() {
  const parametros = new URLSearchParams(location.search);
  const vale = parametros.get('vale');
  if (vale === null) return null;
  // Fuera de la barra de direcciones (y del historial) antes de nada: vale una sola vez.
  history.replaceState(null, '', location.pathname + location.hash);
  if (!RE_VALE.test(vale)) return 'El enlace de soporte no es válido.';
  try {
    const r = await api.post('/acceso/soporte', { vale });
    ficha.guardar(r.token);
    return null;
  } catch (err) {
    return err.message || 'No se pudo abrir la sesión de soporte.';
  }
}

/** Franja fija bajo la barra: quién entra, en qué modo y hasta cuándo. */
export function franjaSoporte(soporte) {
  if (!soporte) return null;
  const hora = new Date(soporte.vence).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
  const modo = soporte.solo_lectura ? 'Sesión de soporte (solo lectura)' : 'Sesión de soporte (con acciones: cada cambio queda auditado)';
  return el('p', { clase: 'franja-soporte' + (soporte.solo_lectura ? '' : ' con-acciones'), role: 'status' },
    el('strong', null, modo), ` · ${soporte.superadmin} · hasta las ${hora}`);
}

/** Aviso en la pantalla de entrada si el vale no sirvió. */
export const avisoVale = (texto) => (texto ? aviso('error', texto) : null);
