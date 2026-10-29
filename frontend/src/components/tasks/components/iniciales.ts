// Iniciales y color de una persona para su círculo (asignados y miembros de una lista).
const COLORES = ['#0078d4', '#107c10', '#5c2d91', '#008272', '#ca5010', '#d13438', '#69797e', '#8764b8'];

export function iniciales(nombreOCorreo: string): string {
  const base = nombreOCorreo.includes('@') ? nombreOCorreo.split('@')[0].replace(/[._-]+/g, ' ') : nombreOCorreo;
  const partes = base.trim().split(/\s+/).filter(Boolean);
  return ((partes[0]?.[0] || '') + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase() || '?';
}

export function colorPersona(email: string): string {
  let h = 0;
  for (const c of email) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COLORES[h % COLORES.length];
}
