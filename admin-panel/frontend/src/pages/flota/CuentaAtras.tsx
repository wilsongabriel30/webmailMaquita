import { useEffect, useState } from "react";

// Cuenta atrás en vivo hasta el cierre automático del túnel. Avisa una vez al llegar a cero.

export function CuentaAtras({ hasta, onFin }: { hasta: string; onFin?: () => void }) {
  const fin = new Date(hasta).getTime();
  const [ahora, setAhora] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const quedan = Math.max(0, Math.round((fin - ahora) / 1000));
  useEffect(() => { if (quedan === 0) onFin?.(); }, [quedan === 0]);
  const h = Math.floor(quedan / 3600), m = Math.floor((quedan % 3600) / 60), s = quedan % 60;
  const dos = (n: number) => String(n).padStart(2, "0");
  return <span className="font-mono tabular-nums">{h ? `${h}:${dos(m)}:${dos(s)}` : `${dos(m)}:${dos(s)}`}</span>;
}
