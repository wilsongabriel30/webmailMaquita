"""
Motor de Datos - Ingresa + Conectores
Primario del sistema BI: Gestiona todas las fuentes de datos sin que el dominio sepa de donde vienen
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Iterator
from enum import Enum
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TipoOrigen(Enum):
    """Tipos de origen de datos soportados"""
    ODK = "odk"
    ARCHIVO = "archivo" 
    BASE_DATOS = "base_datos"
    API = "api"

class SchemaCampo:
    """Definición de un campo en el esquema de datos"""
    def __init__(self, nombre: str, tipo: str, descripcion: str = "", unidad: str = "", nullable: bool = True):
        self.nombre = nombre
        self.tipo = tipo  # texto, numero, fecha, booleano
        self.descripcion = descripcion
        self.unidad = unidad
        self.nullable = nullable
        self.valor_min = None
        self.valor_max = None
        self.valores_unicos = None  # Para campos con baja cardinalidad

class DatasetSchema:
    """Esquema completo de un dataset"""
    def __init__(self, campos: List[SchemaCampo], relaciones: Optional[Dict] = None):
        self.campos = campos
        self.relaciones = relaciones or {}
        self.filas_total = 0
        self.columnas = len(campos)
        self.tamano_mb = 0
        
    def get_campos_por_tipo(self, tipo: str) -> List[SchemaCampo]:
        return [c for c in self.campos if c.tipo == tipo]
        
    def get_campo(self, nombre: str) -> Optional[SchemaCampo]:
        for campo in self.campos:
            if campo.nombre == nombre:
                return campo
        return None

class IConectorDatos(ABC):
    """Interfaz para todos los conectores de datos"""
    
    @abstractmethod
    def obtener_esquema(self, config: Dict[str, Any]) -> DatasetSchema:
        """Obtener esquema de la fuente de datos"""
        pass
        
    @abstractmethod
    def obtener_datos(self, config: Dict[str, Any], limit: Optional[int] = None) -> pd.DataFrame:
        """Obtener datos de la fuente"""
        pass
        
    @abstractmethod
    def test_conexion(self, config: Dict[str, Any]) -> bool:
        """Probar conexión"""
        pass

class ConectorODK(IConectorDatos):
    """Conector específico para datos ODK"""
    
    def __init__(self, odk_service):
        self.odk_service = odk_service
        
    def obtener_esquema(self, config: Dict[str, Any]) -> DatasetSchema:
        """Obtener esquema desde ODK"""
        try:
            form_id = config['form_id']
            
            # Obtener muestra de datos para inferir esquema
            datos_muestra = self.odk_service.obtener_datos_formulario(form_id, limit=100)
            
            campos = []
            for columna, valores in datos_muestra.items():
                if columna in ['instanceId', 'createdAt', 'updatedAt', 'submitterId']:
                    continue  # Campos del sistema
                    
                # Inferir tipo
                tipo = self._inferir_tipo_columna(valores)
                campos.append(SchemaCampo(
                    nombre=columna,
                    tipo=tipo,
                    descripcion=f"Campo de formulario ODK: {columna}",
                    unidad=self._inferir_unidad(columna, tipo)
                ))
            
            return DatasetSchema(campos)
            
        except Exception as e:
            logger.error(f"Error obteniendo esquema ODK: {e}")
            raise
            
    def obtener_datos(self, config: Dict[str, Any], limit: Optional[int] = None) -> pd.DataFrame:
        """Obtener datos desde ODK"""
        form_id = config['form_id']
        return self.odk_service.obtener_datos_formulario(form_id, limit=limit)
        
    def test_conexion(self, config: Dict[str, Any]) -> bool:
        """Probar conexión con ODK"""
        try:
            # Probar obteniendo solo 1 registro
            self.odk_service.obtener_datos_formulario(config['form_id'], limit=1)
            return True
        except:
            return False
            
    def _inferir_tipo_columna(self, valores) -> str:
        """Inferir tipo de columna a partir de valores"""
        if valores.empty:
            return "texto"
            
        # Remover nulos para análisis
        valores_no_nulos = valores.dropna()
        if valores_no_nulos.empty:
            return "texto"
            
        # Analizar primeros valores
        muestra = valores_no_nulos.head(10)
        
        # Detectar fechas
        try:
            pd.to_datetime(muestra, errors='raise')
            return "fecha"
        except:
            pass
            
        # Detectar números
        try:
            pd.to_numeric(muestra, errors='raise')
            return "numero"
        except:
            pass
            
        # Detectar booleanos
        valores_unicos = set(str(v).lower() for v in muestra)
        if valores_unicos.issubset({'true', 'false', '1', '0', 'si', 'no', 'sí', 's', 'n'}):
            return "booleano"
            
        # Por defecto es texto
        return "texto"
        
    def _inferir_unidad(self, columna: str, tipo: str) -> str:
        """Inferir unidad de medida basada en nombre de columna y tipo"""
        if tipo != "numero":
            return ""
            
        columna_lower = columna.lower()
        
        if any(pal in columna_lower for pal in ['edad', 'anos', 'ano', 'age']):
            return "años"
        if any(pal in columna_lower for pal in ['peso', 'kg', 'kilos']):
            return "kg"
        if any(pal in columna_lower for pal in ['talla', 'altura', 'cm']):
            return "cm"
        if any(pal in columna_lower for pal in ['cant', 'cantidad', 'count', 'numero']):
            return "unidades"
            
        return ""

class ConectorArchivos(IConectorDatos):
    """Conector para archivos CSV, Excel, ODS"""
    
    def __init__(self):
        self.formatos_soportados = {
            '.csv': self._leer_csv,
            '.xlsx': self._leer_excel,
            '.xls': self._leer_excel,
            '.ods': self._leer_ods
        }
        
    def obtener_esquema(self, config: Dict[str, Any]) -> DatasetSchema:
        """Obtener esquema desde archivo"""
        try:
            archivo_path = config['archivo_path']
            datos_muestra = self._leer_archivo_muestra(archivo_path, 100)
            
            campos = []
            for columna in datos_muestra.columns:
                valores = datos_muestra[columna]
                tipo = self._inferir_tipo_columna(valores)
                
                campos.append(SchemaCampo(
                    nombre=columna,
                    tipo=tipo,
                    descripcion=f"Columna del archivo: {columna}",
                    unidad=self._inferir_unidad(columna, tipo)
                ))
            
            return DatasetSchema(campos)
            
        except Exception as e:
            logger.error(f"Error obteniendo esquema de archivo: {e}")
            raise
            
    def obtener_datos(self, config: Dict[str, Any], limit: Optional[int] = None) -> pd.DataFrame:
        """Obtener datos desde archivo"""
        archivo_path = config['archivo_path']
        df = self._leer_archivo_completo(archivo_path)
        
        if limit:
            df = df.head(limit)
            
        return df
        
    def test_conexion(self, config: Dict[str, Any]) -> bool:
        """Probar que el archivo existe y es legible"""
        try:
            archivo_path = config['archivo_path']
            self._leer_archivo_muestra(archivo_path, 5)
            return True
        except:
            return False
            
    def _leer_archivo_muestra(self, path: str, n_filas: int) -> pd.DataFrame:
        """Leer primeras n filas para inferir esquema"""
        import os
        extension = os.path.splitext(path)[1].lower()
        
        if extension not in self.formatos_soportados:
            raise ValueError(f"Formato no soportado: {extension}")
            
        return self.formatos_soportados[extension](path, nrows=n_filas)
        
    def _leer_archivo_completo(self, path: str) -> pd.DataFrame:
        """Leer archivo completo"""
        import os
        extension = os.path.splitext(path)[1].lower()
        
        if extension not in self.formatos_soportados:
            raise ValueError(f"Formato no soportado: {extension}")
            
        return self.formatos_soportados[extension](path)
        
    def _leer_csv(self, path: str, nrows: Optional[int] = None) -> pd.DataFrame:
        """Leer archivo CSV con detección automática de encoding y separador"""
        import chardet
        
        # Detectar encoding
        with open(path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
        
        # Detectar separador
        with open(path, 'r', encoding=encoding) as f:
            primera_linea = f.readline()
            
        if '\t' in primera_linea:
            sep = '\t'
        elif ';' in primera_linea:
            sep = ';'
        else:
            sep = ','
        
        return pd.read_csv(path, encoding=encoding, sep=sep, nrows=nrows)
        
    def _leer_excel(self, path: str, nrows: Optional[int] = None) -> pd.DataFrame:
        """Leer archivo Excel"""
        df = pd.read_excel(path, nrows=nrows)
        
        # Limpiar nombres de columna
        df.columns = [str(col).strip() for col in df.columns]
        return df
        
    def _leer_ods(self, path: str, nrows: Optional[int] = None) -> pd.DataFrame:
        """Leer archivo ODS usando openpyxl"""
        try:
            # Primero intentar con pandas directamente
            df = pd.read_excel(path, nrows=nrows, engine='odf')
            df.columns = [str(col).strip() for col in df.columns]
            return df
        except ImportError:
            # Si no está disponible, usar fallback
            try:
                from odf.opendocument import load
                from odf.table import Table, TableRow, TableCell
                from odf.text import P
                
                doc = load(path)
                table = doc.spreadsheets[0]
                
                rows = []
                for i, row in enumerate(table.getElementsByType(TableRow)):
                    if nrows and i >= nrows:
                        break
                        
                    cells = []
                    for cell in row.getElementsByType(TableCell):
                        text = ' '.join(str(p) for p in cell.getElementsByType(P))
                        cells.append(text)
                    
                    if cells:
                        rows.append(cells)
                
                # Detectar encabezado
                if rows:
                    columns = rows[0]
                    data = rows[1:] if len(rows) > 1 else []
                    
                    df = pd.DataFrame(data, columns=columns)
                    df.columns = [str(col).strip() for col in df.columns]
                    return df
                    
            except ImportError:
                raise ImportError("Instale 'odfpy' para archivos ODS: pip install odfpy")
                
    def _inferir_tipo_columna(self, valores) -> str:
        """Mismo método que ConectorODK - podríamos extraer a clase base"""
        if valores.empty:
            return "texto"
            
        valores_no_nulos = valores.dropna()
        if valores_no_nulos.empty:
            return "texto"
            
        muestra = valores_no_nulos.head(10)
        
        # Detectar fechas
        try:
            pd.to_datetime(muestra, errors='raise')
            return "fecha"
        except:
            pass
            
        # Detectar números
        try:
            pd.to_numeric(muestra, errors='raise')
            return "numero"
        except:
            pass
            
        # Detectar booleanos
        valores_unicos = set(str(v).lower() for v in muestra)
        if valores_unicos.issubset({'true', 'false', '1', '0', 'si', 'no', 'sí', 's', 'n'}):
            return "booleano"
            
        return "texto"
        
    def _inferir_unidad(self, columna: str, tipo: str) -> str:
        """Mismo método que ConectorODK"""
        if tipo != "numero":
            return ""
            
        columna_lower = columna.lower()
        
        if any(pal in columna_lower for pal in ['edad', 'anos', 'ano', 'age']):
            return "años"
        if any(pal in columna_lower for pal in ['peso', 'kg', 'kilos']):
            return "kg"
        if any(pal in columna_lower for pal in ['talla', 'altura', 'cm']):
            return "cm"
        if any(pal in columna_lower for pal in ['cant', 'cantidad', 'count', 'numero']):
            return "unidades"
            
        return ""

class MotorDatos:
    """Motor principal de datos - orquesta todos los conectores"""
    
    def __init__(self):
        self.conectores = {}
        self._registrar_conectores_base()
        
    def _registrar_conectores_base(self):
        """Registrar conectores básicos"""
        # Registrar conector de archivos (siempre disponible)
        self.conectores[TipoOrigen.ARCHIVO] = ConectorArchivos()
        
        # Registrar conector ODK si está disponible
        try:
            from modulos.social_cooperacion.aplicacion.servicios.servicio_social_cooperacion import SocialCooperacionService
            odk_service = SocialCooperacionService()
            self.conectores[TipoOrigen.ODK] = ConectorODK(odk_service)
            logger.info("Conector ODK registrado exitosamente")
        except ImportError:
            logger.warning("Conector ODK no disponible")
        
    def registrar_conector(self, tipo: TipoOrigen, conector: IConectorDatos):
        """Registrar un nuevo conector"""
        self.conectores[tipo] = conector
        logger.info(f"Conector {tipo.value} registrado")
        
    def obtener_conector(self, tipo: TipoOrigen) -> Optional[IConectorDatos]:
        """Obtener conector por tipo"""
        return self.conectores.get(tipo)
        
    def listar_conectores_disponibles(self) -> List[TipoOrigen]:
        """Listar todos los conectores disponibles"""
        return list(self.conectores.keys())
        
    def obtener_esquema(self, tipo: TipoOrigen, config: Dict[str, Any]) -> Optional[DatasetSchema]:
        """Obtener esquema usando conector apropiado"""
        conector = self.obtener_conector(tipo)
        if not conector:
            logger.error(f"No hay conector para tipo: {tipo}")
            return None
            
        try:
            return conector.obtener_esquema(config)
        except Exception as e:
            logger.error(f"Error obteniendo esquema: {e}")
            return None
            
    def obtener_datos(self, tipo: TipoOrigen, config: Dict[str, Any], limit: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Obtener datos usando conector apropiado"""
        conector = self.obtener_conector(tipo)
        if not conector:
            logger.error(f"No hay conector para tipo: {tipo}")
            return None
            
        try:
            return conector.obtener_datos(config, limit)
        except Exception as e:
            logger.error(f"Error obteniendo datos: {e}")
            return None
            
    def test_conexion(self, tipo: TipoOrigen, config: Dict[str, Any]) -> bool:
        """Probar conexión usando conector apropiado"""
        conector = self.obtener_conector(tipo)
        if not conector:
            return False
            
        try:
            return conector.test_conexion(config)
        except:
            return False