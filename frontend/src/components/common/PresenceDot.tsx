interface Props {
  status?: 'online' | 'busy' | 'away' | 'offline';
  size?: number;
  className?: string;
}

const COLORS: Record<string, string> = {
  online: '#10b981',
  busy: '#ef4444',
  away: '#f59e0b',
  offline: '#94a3b8',
};

export function PresenceDot({ status = 'offline', size = 10, className = '' }: Props) {
  return (
    <span
      className={`inline-block rounded-full border-2 border-white ${className}`}
      style={{
        width: size,
        height: size,
        backgroundColor: COLORS[status] || COLORS.offline,
      }}
      title={status === 'online' ? 'En línea' : status === 'busy' ? 'Ocupado' : status === 'away' ? 'Ausente' : 'Desconectado'}
    />
  );
}
