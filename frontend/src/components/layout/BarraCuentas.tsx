// Barra de cuentas (como en Outlook): la cuenta de la persona y las que le asignaron, de su
// dominio o de otros. Al elegir una, el CORREO de esta pestaña pasa a esa cuenta (leer, enviar,
// firma, filtros); Drive, chat y calendario siguen siendo de la persona. Ver lib/cuentaActiva.ts.
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import type { Cuenta } from '../../lib/cuentas';
import { colorDeCuenta, cuentaActiva, elegirCuenta } from '../../lib/cuentaActiva';
import { activarAvisos, avisarCorreoNuevo, avisosActivos } from '../../lib/avisosOtrasCuentas';

const CADA_MS = 60000;

function iniciales(c: Cuenta): string {
  const base = c.nombre || c.email.split('@')[0];
  return base.split(/[\s.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

export function BarraCuentas() {
  const setCuentas = useMailStore((s) => s.setCuentas);
  const redacciones = useMailStore((s) => s.composeWindows.length);
  const [cuentas, setLista] = useState<Cuenta[]>([]);
  const [noLeidos, setNoLeidos] = useState<Record<string, number | null>>({});
  const [avisar, setAvisar] = useState(avisosActivos());
  const activa = cuentaActiva();
  // Conteo anterior, para detectar correo nuevo en las cuentas que no están abiertas.
  const previo = useRef<Record<string, number | null>>({});
  const listaRef = useRef<Cuenta[]>([]);

  useEffect(() => {
    api
      .get<{ cuentas: Cuenta[] }>('/mail/cuentas')
      .then((r) => {
        setLista(r.cuentas);
        setCuentas(r.cuentas);
      })
      .catch(() => {
        /* sin cuentas asignadas o servidor caído: no se muestra la barra */
      });
  }, [setCuentas]);

  useEffect(() => {
    if (cuentas.length < 2) return;
    const cargar = () =>
      api
        .get<{ no_leidos: Record<string, number | null> }>('/mail/cuentas/no-leidos')
        .then((r) => {
          const propiaAhora = listaRef.current.find((c) => c.propia)?.email || '';
          avisarCorreoNuevo(previo.current, r.no_leidos, listaRef.current, cuentaActiva() || propiaAhora, propiaAhora);
          previo.current = r.no_leidos;
          setNoLeidos(r.no_leidos);
        })
        .catch(() => {});
    cargar();
    const t = setInterval(cargar, CADA_MS);
    window.addEventListener('refresh-messages', cargar);
    window.addEventListener('refresh-cuentas', cargar);
    return () => {
      clearInterval(t);
      window.removeEventListener('refresh-messages', cargar);
      window.removeEventListener('refresh-cuentas', cargar);
    };
  }, [cuentas.length]);

  useEffect(() => {
    listaRef.current = cuentas;
  }, [cuentas]);
  const propia = cuentas.find((c) => c.propia);
  const emailActivo = activa || propia?.email || '';

  useEffect(() => {
    if (emailActivo) document.documentElement.style.setProperty('--cuenta-activa', colorDeCuenta(emailActivo));
  }, [emailActivo]);

  // Si esta pestaña quedó en una cuenta que ya no está en la lista, vuelve a la propia.
  useEffect(() => {
    if (propia && activa && !cuentas.some((c) => c.email.toLowerCase() === activa)) elegirCuenta(null, propia.email);
  }, [cuentas, propia, activa]);

  if (!propia || cuentas.length < 2) return null;

  const cambiar = (c: Cuenta) => {
    if (c.email.toLowerCase() === emailActivo.toLowerCase()) return;
    if (
      redacciones > 0 &&
      !window.confirm(
        'Tienes un correo en redacción. Si cambias de cuenta se cerrará; lo último guardado queda en Borradores de la cuenta actual. ¿Cambiar de cuenta?',
      )
    )
      return;
    elegirCuenta(c.email, propia.email);
  };

  const enOtra = activa ? cuentas.find((c) => c.email.toLowerCase() === activa) : undefined;

  return (
    <div
      className="px-2 pt-2 pb-1 border-b border-[#edebe9]"
      style={{ borderTop: `3px solid ${colorDeCuenta(emailActivo)}` }}
      data-prueba="barra-cuentas"
    >
      <div className="px-1 pb-1 flex items-center justify-between">
        <span className="text-[10px] font-semibold text-[#605e5c] uppercase tracking-wide">Cuentas</span>
        <button
          type="button"
          onClick={() => { activarAvisos(!avisar); setAvisar(!avisar); }}
          aria-pressed={avisar}
          data-prueba="avisos-otras-cuentas"
          title={avisar ? 'Avisa cuando llega correo a otra cuenta (clic para apagar)' : 'Avisos de otras cuentas apagados (clic para encender)'}
          className={`text-[12px] leading-none px-1 rounded ${avisar ? 'text-[#0078d4]' : 'text-[#a19f9d] line-through'}`}
        >
          🔔
        </button>
      </div>
      {cuentas.map((c) => {
        const esActiva = c.email.toLowerCase() === emailActivo.toLowerCase();
        const color = colorDeCuenta(c.email);
        const n = noLeidos[c.email];
        return (
          <button
            key={c.email}
            onClick={() => cambiar(c)}
            data-cuenta={c.email}
            aria-current={esActiva ? 'true' : undefined}
            title={
              esActiva
                ? `Cuenta activa: ${c.email}`
                : `Ver el correo de ${c.email}${c.propia ? ' (tu cuenta)' : c.puede_enviar ? ' (asignada)' : ' (asignada, solo lectura)'}`
            }
            className={`w-full flex items-center gap-2 px-2 py-[5px] rounded-sm text-left transition-colors ${esActiva ? 'bg-white shadow-sm' : 'hover:bg-[#f3f2f1]'}`}
            style={{ borderLeft: `3px solid ${esActiva ? color : 'transparent'}` }}
          >
            <span
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-semibold shrink-0"
              style={{ backgroundColor: color, opacity: esActiva ? 1 : 0.75 }}
            >
              {iniciales(c)}
            </span>
            <span className="min-w-0 flex-1">
              <span className={`block truncate text-[12px] ${esActiva ? 'font-semibold text-[#201f1e]' : 'text-[#323130]'}`}>
                {c.nombre || c.email.split('@')[0]}
              </span>
              <span className="block truncate text-[10px] text-[#605e5c]">
                {c.email}
                {!c.propia && !c.puede_enviar ? ' · solo lectura' : ''}
              </span>
            </span>
            {!!n && (
              <span className="text-[11px] font-semibold text-[#0078d4]" data-no-leidos={n}>
                {n}
              </span>
            )}
          </button>
        );
      })}
      {enOtra && (
        <div className="mt-1 mx-1 px-2 py-1 rounded-sm text-[11px] text-white" style={{ backgroundColor: colorDeCuenta(enOtra.email) }}>
          Trabajando como <b className="break-all">{enOtra.email}</b>
          <button onClick={() => cambiar(propia)} className="block underline mt-0.5">
            Volver a mi cuenta
          </button>
        </div>
      )}
    </div>
  );
}
