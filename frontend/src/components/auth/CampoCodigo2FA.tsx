/**
 * Casilla del código de verificación en dos pasos (09/11/2026).
 *
 * Antes era una sola casilla que aceptaba letras, números y guiones (para los códigos de respaldo) y, al
 * escribir un punto u otro signo, se veía dibujado un instante antes de quitarse. Ahora hay dos modos claros:
 *  - Código de la app: SOLO 6 dígitos (teclado numérico en el celular; cualquier otro carácter se ignora).
 *  - Código de respaldo: letras, números y guiones, con su propio enlace para cambiar de modo.
 * El servidor sigue validando el código; esto evita confusiones y entradas raras.
 */
import { useState } from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  color: string;           // color de la organización para el foco
}

const SOLO_DIGITOS = /[^0-9]/g;
const RESPALDO = /[^0-9A-Za-z-]/g;

export function CampoCodigo2FA({ value, onChange, color }: Props) {
  const [respaldo, setRespaldo] = useState(false);

  const cambiarModo = () => {
    setRespaldo(!respaldo);
    onChange('');
  };

  return (
    <div className="mb-6">
      <label className="block text-sm font-medium mb-1.5" style={{ color: '#323130' }}>
        {respaldo ? 'Código de respaldo' : 'Código de verificación'}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(respaldo
          ? e.target.value.replace(RESPALDO, '').toUpperCase().slice(0, 39)
          : e.target.value.replace(SOLO_DIGITOS, '').slice(0, 6))}
        onBeforeInput={(e) => {
          // En el modo de la app no se dibuja nada que no sea un dígito (ni puntos ni letras).
          const dato = (e as unknown as InputEvent).data;
          if (!respaldo && dato && /[^0-9]/.test(dato)) e.preventDefault();
        }}
        inputMode={respaldo ? 'text' : 'numeric'}
        pattern={respaldo ? '[0-9A-Za-z-]{8,39}' : '[0-9]{6}'}
        placeholder={respaldo ? 'XXXX-XXXX' : '000000'}
        title={respaldo ? 'Uno de los códigos de respaldo que guardó al activar la verificación.' : 'Los 6 dígitos que muestra la app de autenticación en su celular.'}
        className="w-full px-3 py-2 rounded text-sm text-center font-mono text-lg tracking-[0.3em] outline-none transition-colors"
        style={{ borderColor: '#d2d0ce', borderWidth: '1px', color: '#323130' }}
        onFocus={(e) => { e.target.style.borderColor = color; e.target.style.boxShadow = `0 0 0 1px ${color}`; }}
        onBlur={(e) => { e.target.style.borderColor = '#d2d0ce'; e.target.style.boxShadow = 'none'; }}
        required
        autoFocus
        maxLength={respaldo ? 39 : 6}
        autoComplete="one-time-code"
      />
      <button type="button" onClick={cambiarModo} className="text-xs mt-1 hover:underline" style={{ color: '#605e5c' }}>
        {respaldo ? 'Volver al código de la app' : 'Usar un código de respaldo'}
      </button>
    </div>
  );
}
