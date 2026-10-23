/* Tipos del Drive (contrato en almacen/docs/CONTRATO-API.md). Sacados de FilesView.tsx
   para que los compartan sus componentes sin engordarlo. */

export interface Item {
  id: string;
  nombre: string;
  ruta: string;
  es_carpeta: boolean;
  extension?: string;
  tamano_humano: string;
  modificado_at?: string;
  es_editable?: boolean;
  es_favorito?: boolean;
  eliminado_en?: string;
}

export interface Unidad {
  id: number;
  nombre: string;
  mi_rol: string;
  miembros: number;
  ruta: string;
}

export interface Miembro { usuario_id: number; rol: string; nombre: string; username: string; }
export interface Conmigo {
  id: number; nombre: string; extension?: string; tamano_bytes?: number;
  token: string; de: string; puede_editar: boolean; abre_en_linea: boolean;
  permite_descarga: boolean; requiere_clave: boolean; expira_en?: string; creado_en: string;
}
export interface UsuarioDir { id: number | string; usuario_id?: number; nombre: string; email?: string; }

export const ROL_ETIQUETA: Record<string, string> = { manager: 'Administrador', editor: 'Editor', viewer: 'Lector' };

export interface Share {
  id: number;
  ruta: string;
  tipo: number;
  con_quien?: string;
  url?: string;
  creado_en?: string;
}

export interface Cuota { usado_humano: string; total_humano: string; porcentaje: number; }
export interface Version { version_id: string; tamano_humano: string; creado_en: string; guardar_siempre?: boolean; }

export type Vista = 'archivos' | 'papelera' | 'favoritos' | 'unidades' | 'conmigo';
