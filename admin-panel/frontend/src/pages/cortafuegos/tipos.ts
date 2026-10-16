export type Origen = "todos" | "admin" | "cerrado";

export interface Extra { puertos: string; protocolo: "tcp" | "udp"; origen: "todos" | "admin"; descripcion: string }
export interface Bloqueo { red: string; motivo: string }
export interface Config { servicios: Record<string, Origen>; admin: string[]; extras: Extra[]; bloqueados: Bloqueo[] }
export interface Servicio { titulo: string; tcp?: string; udp?: string; origen: Origen }
export interface Jaula { jaula: string; bloqueadas: string[]; total: number }

export interface Estado {
  activo: boolean;
  configurado: boolean;
  config: Config;
  servicios: Record<string, Servicio>;
  pendiente_hasta: number | null;
  fail2ban: Jaula[];
  escuchando: { protocolo: string; puerto: number }[];
  su_ip: string;
}

export const NOMBRE_ORIGEN: Record<Origen, string> = { todos: "Todo Internet", admin: "Solo administración", cerrado: "Cerrado" };

/* Qué vigila cada jaula de fail2ban, en palabras simples. */
export const NOMBRE_JAULA: Record<string, string> = {
  sshd: "Contraseñas fallidas por SSH",
  dovecot: "Contraseñas fallidas del correo (IMAP/POP3)",
  "postfix-sasl": "Contraseñas fallidas al enviar correo",
  "nginx-http-auth": "Clave del panel fallida",
  vsftpd: "Contraseñas fallidas por FTP",
  "sitios-wp-login": "Fuerza bruta en WordPress",
  "sitios-escaneo": "Rastreadores de vulnerabilidades",
  "sitios-abuso": "Abusos en los sitios (bloqueos y límites)",
  recidive: "Reincidentes (una semana)",
};

/* ¿Este puerto escuchando queda abierto con la configuración actual? */
export function puertoCubierto(conf: Config, servicios: Record<string, Servicio>, proto: string, puerto: number): string | null {
  const dentro = (lista: string) => lista.split(",").some((p) => {
    const [a, b] = p.split(":").map(Number);
    return b ? puerto >= a && puerto <= b : puerto === a;
  });
  for (const [clave, s] of Object.entries(servicios)) {
    const lista = proto === "udp" ? s.udp : s.tcp;
    if (lista && dentro(lista) && conf.servicios[clave] !== "cerrado") return s.titulo;
  }
  for (const e of conf.extras) if (e.protocolo === proto && dentro(e.puertos)) return e.descripcion || "Puerto adicional";
  return null;
}
