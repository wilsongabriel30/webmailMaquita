/**
 * elegirPegado.ts — «¿Pegar como tabla o como imagen?» (05/11/2026).
 *
 * Al copiar celdas de Excel / Hojas de cálculo / Word, el portapapeles trae el cuadro como
 * tabla HTML y, además, como imagen. Unas personas quieren la tabla (editable, ocupa poco)
 * y otras la imagen (idéntica a la hoja). Se pregunta con dos botones; vale para Ctrl+V y
 * para clic derecho → Pegar (los dos disparan el mismo evento de pegado).
 */
export type OpcionPegado = 'tabla' | 'imagen';

const ID = 'maquita-elegir-pegado';

export function preguntarTablaOImagen(ancla: HTMLElement, alElegir: (opcion: OpcionPegado) => void): void {
  document.getElementById(ID)?.remove();
  const caja = document.createElement('div');
  caja.id = ID;
  caja.setAttribute('role', 'dialog');
  caja.setAttribute('aria-label', 'Cómo pegar el cuadro');
  const r = ancla.getBoundingClientRect();
  const arriba = Math.max(8, Math.min(window.innerHeight - 70, r.top + 8));
  const izquierda = Math.max(8, Math.min(window.innerWidth - 420, r.left + 8));
  caja.style.cssText = `position:fixed;top:${arriba}px;left:${izquierda}px;z-index:10000;background:#fff;border:1px solid #c8c6c4;` +
    'border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.18);padding:10px 12px;font:13px Calibri,"Segoe UI",sans-serif;color:#323130;' +
    'display:flex;align-items:center;gap:8px;max-width:400px';
  const texto = document.createElement('span');
  texto.textContent = 'Copiaste un cuadro. ¿Cómo lo pegamos?';
  const boton = (etiqueta: string, opcion: OpcionPegado, principal: boolean) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = etiqueta;
    b.style.cssText = principal
      ? 'padding:5px 12px;border-radius:4px;border:1px solid #0078d4;background:#0078d4;color:#fff;cursor:pointer;font:inherit'
      : 'padding:5px 12px;border-radius:4px;border:1px solid #8a8886;background:#fff;color:#323130;cursor:pointer;font:inherit';
    b.onclick = () => { cerrar(); alElegir(opcion); };
    return b;
  };
  const cerrarBtn = document.createElement('button');
  cerrarBtn.type = 'button';
  cerrarBtn.setAttribute('aria-label', 'Cancelar');
  cerrarBtn.title = 'Cancelar (Esc)';
  cerrarBtn.textContent = '×';
  cerrarBtn.style.cssText = 'border:none;background:none;color:#605e5c;font-size:16px;cursor:pointer;padding:0 2px';
  const conTecla = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); cerrar(); } };
  const temporizador = window.setTimeout(cerrar, 30000);
  function cerrar() {
    window.clearTimeout(temporizador);
    document.removeEventListener('keydown', conTecla, true);
    caja.remove();
  }
  cerrarBtn.onclick = cerrar;
  document.addEventListener('keydown', conTecla, true);
  caja.append(texto, boton('Como tabla', 'tabla', true), boton('Como imagen', 'imagen', false), cerrarBtn);
  document.body.appendChild(caja);
  (caja.querySelector('button') as HTMLButtonElement | null)?.focus();
}
