import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Props {
  /** Correo del remitente (solo la dirección, ej: juan@empresa.com). */
  email: string;
  /** Nombre visible del remitente, para guardarlo como contacto. */
  nombre?: string;
}

/**
 * Aviso discreto de "remitente externo" (fuera de la organización). NO es una alerta
 * de peligro: usa el azul informativo, porque una contraparte externa puede ser
 * perfectamente legítima. Si es un remitente frecuente con el que sí nos comunicamos,
 * el usuario lo "marca como conocido": se agrega a sus contactos y el aviso ya no
 * vuelve a salir para esa dirección.
 */
export default function RemitenteExternoAviso({ email, nombre }: Props) {
  const [externo, setExterno] = useState(false);
  const [conocido, setConocido] = useState(false);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    let vivo = true;
    setExterno(false);
    setConocido(false);
    if (!email || !email.includes('@')) return;
    api
      .get<{ externo: boolean; conocido: boolean }>(
        `/mail/remitente-estado?email=${encodeURIComponent(email)}`
      )
      .then((r) => {
        if (!vivo) return;
        setExterno(!!r.externo);
        setConocido(!!r.conocido);
      })
      .catch(() => {
        /* si falla la consulta, no mostramos nada: el aviso es opcional */
      });
    return () => {
      vivo = false;
    };
  }, [email]);

  // No se muestra si es interno, si ya es conocido, o mientras no sabemos.
  if (!externo || conocido) return null;

  const marcarConocido = async () => {
    setGuardando(true);
    try {
      await api.post('/mail/remitente-conocido', { email, nombre: nombre || email });
      setConocido(true); // oculta el aviso de inmediato
    } catch {
      setGuardando(false);
    }
  };

  return (
    <div
      style={{
        marginTop: 12,
        padding: '8px 12px',
        background: '#eff6fc',
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 13,
        color: '#323130',
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="#0078d4" style={{ flexShrink: 0 }}>
        <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4v5h-1.5V4h1.5z" />
      </svg>

      <span>
        Remitente externo — este correo viene de fuera de la organización.
      </span>

      <button
        onClick={marcarConocido}
        disabled={guardando}
        title="Agregar a contactos: el aviso no volverá a salir para este remitente"
        style={{
          background: 'transparent',
          color: '#0078d4',
          border: '1px solid #0078d4',
          borderRadius: 4,
          padding: '4px 12px',
          fontSize: 12,
          cursor: guardando ? 'default' : 'pointer',
          fontWeight: 600,
          marginLeft: 'auto',
          opacity: guardando ? 0.6 : 1,
          whiteSpace: 'nowrap',
        }}
      >
        {guardando ? 'Guardando...' : 'Marcar como conocido'}
      </button>
    </div>
  );
}
