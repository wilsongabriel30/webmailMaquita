// Tipos de las funciones «para desarrolladores» de un sitio (v1.11): lo que devuelve maquita-sitios.

export type Motor = "mariadb" | "postgresql";
export type Perfil = "lectura" | "escritura" | "estructura" | "todo" | "medida";

export interface Permisos { perfil: Perfil; lista?: string[] }

export interface UsuarioBase {
  usuario: string;
  base: string;
  motor: Motor;
  permisos: Permisos;
  remoto: string[];
  creado?: string;
}

export interface EstadoRemoto {
  host: string | null;
  mariadb: { activo: boolean; puerto: number };
  postgresql: { activo: boolean; puerto: number };
}

export interface ListadoUsuarios {
  dominio: string;
  maximo: number;
  bases: { nombre: string; motor: Motor }[];
  usuarios: UsuarioBase[];
  privilegios: Record<Motor, string[]>;
  remoto: EstadoRemoto;
  maximo_redes: number;
  creado?: Conexion;
  cortafuegos?: string;
}

export interface Conexion {
  usuario: string;
  base: string;
  motor: Motor;
  servidor: string;
  puerto: number;
  servidor_remoto?: string;
  tls?: string;
  clave?: string;
}

export interface Exclusion { regla: number; ruta: string | null }
export type ModoWaf = "apagado" | "detectar" | "bloquear";

export interface EstadoWaf {
  dominio: string;
  perfil: string;
  modo: ModoWaf;
  paranoia: 1 | 2;
  exclusiones: Exclusion[];
  maximo: number;
}

export interface Suceso {
  fecha: string;
  ip: string;
  metodo: string;
  ruta: string;
  codigo: number | null;
  accion: "bloqueado" | "detectado";
  reglas: { id: number; mensaje: string }[];
}

export interface ClaveSsh {
  id: string;
  cuenta: string;
  usuario: string | null;
  tipo: string;
  bits: number;
  huella: string;
  comentario: string;
  creada?: string;
  activa: boolean;
}

export interface ListadoClaves {
  dominio: string;
  maximo: number;
  cuentas: { cuenta: string; usuario: string; activa: boolean }[];
  claves: ClaveSsh[];
}

export const MOTOR: Record<Motor, string> = { mariadb: "MariaDB", postgresql: "PostgreSQL" };

export const PERFILES: { id: Perfil; nombre: string; ayuda: string }[] = [
  { id: "lectura", nombre: "Lectura", ayuda: "Solo ver datos." },
  { id: "escritura", nombre: "Lectura y escritura", ayuda: "Ver, añadir, cambiar y borrar filas." },
  { id: "estructura", nombre: "Estructura", ayuda: "Lo anterior y crear, cambiar y borrar tablas, índices y vistas." },
  { id: "todo", nombre: "Todo", ayuda: "Todos los permisos sobre esa base (y solo sobre esa)." },
  { id: "medida", nombre: "A medida", ayuda: "Elegir uno por uno." },
];

export const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

export type Hacer = (texto: string, fn: () => Promise<unknown>) => Promise<boolean>;
