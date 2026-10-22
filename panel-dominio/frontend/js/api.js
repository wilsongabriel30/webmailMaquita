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
  if (res.status === 401 && ruta !== '/acceso/entrar' && ruta !== '/acceso/soporte') {
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

/** Sube un archivo grande (o un texto) tal cual, con PUT, avisando del avance con alAvance(0..100).
 *  XMLHttpRequest y no fetch: fetch no informa de cuánto se ha enviado. */
function subirGrande(ruta, cuerpo, alAvance) {
  return new Promise((resolver, rechazar) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', '/api' + ruta);
    xhr.setRequestHeader('Authorization', 'Bearer ' + ficha.leer());
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    if (alAvance) xhr.upload.onprogress = (e) => { if (e.lengthComputable) alAvance(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => {
      let datos = {};
      try { datos = JSON.parse(xhr.responseText || '{}'); } catch { /* respuesta vacía o de nginx */ }
      if (xhr.status === 401) { ficha.borrar(); window.dispatchEvent(new Event('pd-sin-sesion')); rechazar(new Error('La sesión se cerró. Vuelve a entrar.')); return; }
      if (xhr.status >= 200 && xhr.status < 300) { resolver(datos); return; }
      rechazar(new Error(typeof datos.detail === 'string' ? datos.detail
        : xhr.status === 413 ? 'El archivo pesa demasiado para este servidor.' : 'No se pudo completar la subida'));
    };
    xhr.onerror = () => rechazar(new Error('Se cortó la conexión durante la subida. Inténtalo de nuevo.'));
    xhr.send(cuerpo);
  });
}

export const api = {
  imagen,
  subir,
  subirGrande,
  get: (r) => pedir('GET', r),
  post: (r, c) => pedir('POST', r, c || {}),
  put: (r, c) => pedir('PUT', r, c || {}),
  del: (r) => pedir('DELETE', r),
};

// Las direcciones van en la ruta: se codifica todo salvo la arroba, que el servidor espera tal cual.
export const enRuta = (direccion) => encodeURIComponent(direccion).replace(/%40/g, '@');
