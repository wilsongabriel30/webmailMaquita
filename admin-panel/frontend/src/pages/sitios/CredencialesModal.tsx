import { useState } from "react";

export interface Credencial {
  etiqueta: string;
  valor: string;
  secreto?: boolean;
}

/* Muestra una sola vez las credenciales generadas (administrador de la aplicación, FTP). */
export function CredencialesModal({ titulo, items, nota, onCerrar }: { titulo: string; items: Credencial[]; nota?: string; onCerrar: () => void }) {
  const [copiado, setCopiado] = useState("");
  const copiar = (c: Credencial) => {
    navigator.clipboard?.writeText(c.valor).then(() => { setCopiado(c.etiqueta); setTimeout(() => setCopiado(""), 1500); });
  };
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-lg p-5 space-y-4">
        <h2 className="text-lg font-semibold text-ms-gray-130">{titulo}</h2>
        <table className="w-full text-sm">
          <tbody>
            {items.map((c) => (
              <tr key={c.etiqueta} className="border-b border-ms-gray-30 last:border-0">
                <td className="py-2 pr-3 text-ms-gray-90 whitespace-nowrap">{c.etiqueta}</td>
                <td className={`py-2 break-all ${c.secreto ? "font-mono" : ""}`}>{c.valor}</td>
                <td className="py-2 pl-2 text-right">
                  <button onClick={() => copiar(c)} className="text-ms-blue hover:underline text-xs">{copiado === c.etiqueta ? "Copiado" : "Copiar"}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {nota && <p className="text-xs text-ms-gray-90 bg-amber-50 border border-amber-200 rounded p-2">{nota}</p>}
        <div className="text-right">
          <button onClick={onCerrar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Ya los guardé</button>
        </div>
      </div>
    </div>
  );
}
