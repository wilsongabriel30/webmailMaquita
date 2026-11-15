/**
 * Nota sobre la lista de «todas las carpetas»: hay correos que están en más de una carpeta y se
 * muestran una sola vez (lib/copiasEnTodo.ts). Sin la nota, quien busca la copia de «Enviados»
 * no sabría por qué ve una sola fila.
 */
export function AvisoCopiasOcultas({ n }: { n: number }) {
  if (n <= 0) return null;
  return (
    <div data-copias-ocultas role="note" style={{ padding: '6px 14px', fontSize: 12, color: '#605e5c', background: '#faf9f8', borderBottom: '1px solid #edebe9' }}>
      {n === 1
        ? 'Un correo de esta lista está en más de una carpeta (por ejemplo, en la Bandeja de entrada y en Enviados): se muestra una sola vez.'
        : `${n} copias de correos de esta lista están además en otra carpeta (por ejemplo, en la Bandeja de entrada y en Enviados): cada correo se muestra una sola vez.`}
    </div>
  );
}
