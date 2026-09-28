// Llamadas al servidor. La ficha de sesión vive en sessionStorage: se borra al cerrar la pestaña.
const CLAVE = 'pd_ficha';

export const ficha = {
  leer: () => { try { return sessionStorage.getItem(CLAVE) || ''; } catch { return ''; } },
  guardar: (v) => { try { sessionStorage.setItem(CLAVE, v); } catch { /* sin almacenamiento */ } },
  borrar: () => { try { sessionStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ } },
};

async function pedir(metodo, ruta, cuerpo) {
  const cabeceras = { 'Content-Type': 'application/json' };
  if (ficha.leer()) cabeceras.Authorization = 'Bearer ' + ficha.leer();
  let res;
  try {
    res = await fetch('/api' + ruta, { method: metodo, headers: cabeceras, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  } catch {
    throw new Error('No hay conexión con el servidor. Inténtalo de nuevo.');
  }
  if (res.status === 401 && ruta !== '/acceso/entrar') {
    ficha.borrar();
    window.dispatchEvent(new Event('pd-sin-sesion'));
    throw new Error('La sesión se cerró. Vuelve a entrar.');
  }
  if (res.status === 429) throw new Error('Demasiados intentos. Espera un minuto.');
  const datos = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof datos.detail === 'string' ? datos.detail : 'No se pudo completar la operación');
  return datos;
}

async function imagen(ruta) {
  const res = await fetch('/api' + ruta, { headers: { Authorization: 'Bearer ' + ficha.leer() } });
  if (!res.ok) throw new Error('No se pudo cargar la imagen');
  return URL.createObjectURL(await res.blob());
}

async function subir(ruta, archivo) {
  let res;
  try {
    res = await fetch('/api' + ruta, { method: 'PUT', headers: { Authorization: 'Bearer ' + ficha.leer(), 'Content-Type': 'application/octet-stream' }, body: archivo });
  } catch {
    throw new Error('No hay conexión con el servidor. Inténtalo de nuevo.');
  }
  if (res.status === 413) throw new Error('La imagen pesa demasiado.');
  const datos = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof datos.detail === 'string' ? datos.detail : 'No se pudo subir la imagen');
  return datos;
}

export const api = {
  imagen,
  subir,
  get: (r) => pedir('GET', r),
  post: (r, c) => pedir('POST', r, c || {}),
  put: (r, c) => pedir('PUT', r, c || {}),
  del: (r) => pedir('DELETE', r),
};

// Las direcciones van en la ruta: se codifica todo salvo la arroba, que el servidor espera tal cual.
export const enRuta = (direccion) => encodeURIComponent(direccion).replace(/%40/g, '@');
