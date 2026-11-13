/**
 * Rótulo que separa, en los resultados de una búsqueda, las coincidencias exactas (arriba) de las
 * que solo coinciden en el contenido del correo (debajo). Dónde va lo decide lib/nivelesBusqueda.ts.
 * Si no hubo ninguna exacta lo dice y ofrece el «¿Quiso decir…?», por si fue un error de tecleo.
 */
import { QuisoDecir } from './QuisoDecir';

export function RotuloCoincidencias({ sinExactas, consulta }: { sinExactas: boolean; consulta: string }) {
  return (
    <div role="separator" aria-label="Coincidencias en el contenido del correo"
      className="px-4 py-1.5 text-[12px] font-semibold text-[#605e5c] bg-[#faf9f8] border-y border-[#e1dfdd] dark:bg-[#252423] dark:text-[#c8c6c4] dark:border-[#3b3a39]">
      {sinExactas && (
        <p className="font-normal text-[#323130] dark:text-[#e0e0e0]">
          No hay coincidencias exactas con lo que escribió.
        </p>
      )}
      {sinExactas && <QuisoDecir consulta={consulta} />}
      <p className={sinExactas ? 'mt-1' : undefined}>Coincidencias en el contenido del correo</p>
    </div>
  );
}
