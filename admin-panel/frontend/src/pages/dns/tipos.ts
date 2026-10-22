export interface Registro {
  id: string;
  nombre: string;
  tipo: string;
  valor: string;
  ttl: number;
  prioridad: number | null;
  sistema: boolean;
}

export interface Prueba {
  clave: string;
  titulo: string;
  ok: boolean;
  obtenido: string;
  que_hacer: string;
}

export interface Comprobacion {
  zona: string;
  lista: boolean;
  pruebas: Prueba[];
}

export interface ServidorDns {
  ip_correo?: string;
  ip_web?: string;
  ns?: { nombre: string; ip: string }[];
  aviso?: string;
}

export interface TransferenciasDns {
  transferencias: {
    transferir_a: string[];
    notificar_a: string[];
    maestro_oculto: boolean;
    tsig: { nombre: string; algoritmo: string; clave_presente?: boolean; para_el_secundario?: string } | null;
  };
  zonas_con_ajuste_propio: Record<string, unknown>;
  aviso?: string;
}

export const TIPOS =["A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA", "NS"];

/* Qué es cada registro, en palabras de quien no es técnico. */
export const AYUDA_TIPO: Record<string, string> = {
  A: "Dirección IPv4 a la que apunta el nombre.",
  AAAA: "Dirección IPv6 a la que apunta el nombre.",
  CNAME: "Alias: este nombre es igual que otro (escriba el destino).",
  MX: "Servidor que recibe el correo del dominio.",
  TXT: "Texto: SPF, DKIM, DMARC, verificaciones de Google y otros.",
  SRV: "Servicio: «peso puerto destino» (p. ej. 1 993 mail).",
  CAA: "Qué entidad puede emitir certificados (p. ej. issue letsencrypt.org).",
  NS: "Servidor de nombres (delegar una subzona).",
};
