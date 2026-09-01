"""
Motor de Consultas - Ejecuta agregaciones y filtros
Compila consultas del dashboard en planes ejecutables optimizados
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class OperadorFiltro(Enum):
    """Operadores de filtro soportados"""
    IGUAL = "eq"
    DIFERENTE = "ne"
    MAYOR_QUE = "gt"
    MAYOR_IGUAL = "gte"
    MENOR_QUE = "lt"
    MENOR_IGUAL = "lte"
    CONTIENE = "contains"
    EMPIEZA_CON = "startswith"
    TERMINA_EN = "endswith"
    EN_LISTA = "in"
    NO_EN_LISTA = "not_in"
    ES_NULO = "is_null"
    NO_ES_NULO = "is_not_null"
    ENTRE = "between"

class TipoAgregacion(Enum):
    """Tipos de agregación optimizados"""
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    PERCENTIL_25 = "percentile_25"
    PERCENTIL_75 = "percentile_75"
    STD_DEV = "std"

class Filtro:
    """Filtro aplicable a consultas"""
    def __init__(
        self,
        campo: str,
        operador: OperadorFiltro,
        valor: Any = None,
        valor2: Any = None  # Para operadores como 'entre'
    ):
        self.campo = campo
        self.operador = operador
        self.valor = valor
        self.valor2 = valor2
        self.aplicado = False

    def aplicar(self, datos: pd.DataFrame) -> pd.DataFrame:
        """Aplicar filtro a DataFrame"""
        if self.campo not in datos.columns:
            logger.warning(f"Campo '{self.campo}' no encontrado en datos")
            return datos

        if self.operador == OperadorFiltro.IGUAL:
            resultado = datos[datos[self.campo] == self.valor]
        elif self.operador == OperadorFiltro.DIFERENTE:
            resultado = datos[datos[self.campo] != self.valor]
        elif self.operador == OperadorFiltro.MAYOR_QUE:
            resultado = datos[datos[self.campo] > self.valor]
        elif self.operador == OperadorFiltro.MAYOR_IGUAL:
            resultado = datos[datos[self.campo] >= self.valor]
        elif self.operador == OperadorFiltro.MENOR_QUE:
            resultado = datos[datos[self.campo] < self.valor]
        elif self.operador == OperadorFiltro.MENOR_IGUAL:
            resultado = datos[datos[self.campo] <= self.valor]
        elif self.operador == OperadorFiltro.CONTIENE:
            resultado = datos[datos[self.campo].astype(str).str.contains(str(self.valor), na=False)]
        elif self.operador == OperadorFiltro.EMPIEZA_CON:
            resultado = datos[datos[self.campo].astype(str).str.startswith(str(self.valor), na=False)]
        elif self.operador == OperadorFiltro.TERMINA_EN:
            resultado = datos[datos[self.campo].astype(str).str.endswith(str(self.valor), na=False)]
        elif self.operador == OperadorFiltro.EN_LISTA:
            resultado = datos[datos[self.campo].isin(self.valor)]
        elif self.operador == OperadorFiltro.NO_EN_LISTA:
            resultado = datos[~datos[self.campo].isin(self.valor)]
        elif self.operador == OperadorFiltro.ES_NULO:
            resultado = datos[datos[self.campo].isna()]
        elif self.operador == OperadorFiltro.NO_ES_NULO:
            resultado = datos[datos[self.campo].notna()]
        elif self.operador == OperadorFiltro.ENTRE:
            resultado = datos[(datos[self.campo] >= self.valor) & (datos[self.campo] <= self.valor2)]
        else:
            logger.warning(f"Operador no implementado: {self.operador}")
            resultado = datos

        self.aplicado = True
        return resultado

class Medida:
    """Medida con agregación y configuración"""
    def __init__(
        self,
        nombre: str,
        campo: str,
        tipo_agregacion: TipoAgregacion,
        alias: str = None,
        condiciones: List[Filtro] = None
    ):
        self.nombre = nombre
        self.campo = campo
        self.tipo_agregacion = tipo_agregacion
        self.alias = alias or nombre
        self.condiciones = condiciones or []
        self.resultado = None

    def ejecutar(self, datos: pd.DataFrame, grupo_por: Optional[List[str]] = None) -> Any:
        """Ejecutar medida sobre datos"""
        datos_filtrados = datos.copy()
        
        # Aplicar filtros específicos de la medida
        for filtro in self.condiciones:
            datos_filtrados = filtro.aplicar(datos_filtrados)

        columna = datos_filtrados[self.campo]
        
        # Convertir a numérico si es necesario
        if self.tipo_agregacion in [TipoAgregacion.SUM, TipoAgregacion.AVG, 
                                   TipoAgregacion.MEDIAN, TipoAgregacion.STD_DEV]:
            columna = pd.to_numeric(columna, errors='coerce')

        if grupo_por:
            # Agregación con grupo
            if self.tipo_agregacion == TipoAgregacion.SUM:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].sum()
            elif self.tipo_agregacion == TipoAgregacion.AVG:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].mean()
            elif self.tipo_agregacion == TipoAgregacion.COUNT:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].count()
            elif self.tipo_agregacion == TipoAgregacion.DISTINCT_COUNT:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].nunique()
            elif self.tipo_agregacion == TipoAgregacion.MIN:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].min()
            elif self.tipo_agregacion == TipoAgregacion.MAX:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].max()
            elif self.tipo_agregacion == TipoAgregacion.MEDIAN:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].median()
            elif self.tipo_agregacion == TipoAgregacion.STD_DEV:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].std()
            else:
                resultado = datos_filtrados.groupby(grupo_por)[columna.name].sum()
        else:
            # Agregación simple
            if self.tipo_agregacion == TipoAgregacion.SUM:
                resultado = columna.sum()
            elif self.tipo_agregacion == TipoAgregacion.AVG:
                resultado = columna.mean()
            elif self.tipo_agregacion == TipoAgregacion.COUNT:
                resultado = columna.count()
            elif self.tipo_agregacion == TipoAgregacion.DISTINCT_COUNT:
                resultado = columna.nunique()
            elif self.tipo_agregacion == TipoAgregacion.MIN:
                resultado = columna.min()
            elif self.tipo_agregacion == TipoAgregacion.MAX:
                resultado = columna.max()
            elif self.tipo_agregacion == TipoAgregacion.MEDIAN:
                resultado = columna.median()
            elif self.tipo_agregacion == TipoAgregacion.STD_DEV:
                resultado = columna.std()
            else:
                resultado = columna.sum()

        self.resultado = resultado
        return resultado

class Consulta:
    """Consulta completa con filtros, medidas y agrupación"""
    def __init__(
        self,
        nombre: str,
        tablas: List[str],
        medidas: List[Medida],
        grupo_por: Optional[List[str]] = None,
        filtros: Optional[List[Filtro]] = None,
        orden_por: Optional[List[Tuple[str, bool]]] = None,
        limite: Optional[int] = None,
        offset: Optional[int] = None
    ):
        self.nombre = nombre
        self.tablas = tablas
        self.medidas = medidas
        self.grupo_por = grupo_por or []
        self.filtros = filtros or []
        self.orden_por = orden_por or []  # (campo, ascendente)
        self.limite = limite
        self.offset = offset
        self.resultados = {}
        self.datos_filtrados = None
        self.ejecutada = False
        self.tiempo_ejecucion = None

    def ejecutar(self, datos: pd.DataFrame) -> Dict[str, Any]:
        """Ejecutar consulta completa"""
        tiempo_inicio = datetime.now()
        
        try:
            # Aplicar filtros
            self.datos_filtrados = datos.copy()
            for filtro in self.filtros:
                self.datos_filtrados = filtro.aplicar(self.datos_filtrados)

            # Verificar que hay datos después de filtros
            if self.datos_filtrados.empty:
                logger.warning(f"Consulta '{self.nombre}' no retornó datos después de aplicar filtros")
                self.ejecutada = True
                self.tiempo_ejecucion = (datetime.now() - tiempo_inicio).total_seconds()
                return {
                    'consulta': self.nombre,
                    'resultados': {},
                    'total_filas': 0,
                    'tiempo_ejecucion': self.tiempo_ejecucion,
                    'exitosa': True,
                    'mensaje': 'Sin resultados después de aplicar filtros'
                }

            # Ejecutar medidas
            for medida in self.medidas:
                try:
                    resultado = medida.ejecutar(self.datos_filtrados, self.grupo_por if self.grupo_por else None)
                    self.resultados[medida.alias] = resultado
                except Exception as e:
                    logger.error(f"Error ejecutando medida '{medida.nombre}': {e}")
                    self.resultados[medida.alias] = None

            # Construir DataFrame de resultados
            if self.grupo_por and any(self.resultados.values()):
                # Hay agrupación - combinar resultados
                dfs_combinados = []
                
                for medida_alias, resultado in self.resultados.items():
                    if resultado is not None and hasattr(resultado, 'index'):
                        df_temp = resultado.reset_index()
                        df_temp = df_temp.rename(columns={df_temp.columns[-1]: medida_alias})
                        dfs_combinados.append(df_temp)

                if dfs_combinados:
                    from functools import reduce
                    df_final = reduce(
                        lambda left, right: pd.merge(left, right, on=self.grupo_por, how='outer'),
                        dfs_combinados
                    )
                else:
                    df_final = pd.DataFrame()
            else:
                # Sin agrupación
                df_final = pd.DataFrame([self.resultados])

            # Aplicar ordenamiento
            if self.orden_por and not df_final.empty:
                orden_columnas = []
                ascendente = []
                
                for campo, asc in self.orden_por:
                    if campo in df_final.columns:
                        orden_columnas.append(campo)
                        ascendente.append(asc)
                
                if orden_columnas:
                    df_final = df_final.sort_values(by=orden_columnas, ascending=ascendente)

            # Aplicar límites
            if self.limite:
                if self.offset:
                    df_final = df_final.iloc[self.offset:self.offset + self.limite]
                else:
                    df_final = df_final.head(self.limite)

            self.tiempo_ejecucion = (datetime.now() - tiempo_inicio).total_seconds()
            self.ejecutada = True

            return {
                'consulta': self.nombre,
                'resultados': self.resultados,
                'datos': df_final,
                'total_filas': len(df_final),
                'tiempo_ejecucion': self.tiempo_ejecucion,
                'exitosa': True,
                'mensaje': 'Consulta ejecutada exitosamente'
            }

        except Exception as e:
            logger.error(f"Error ejecutando consulta '{self.nombre}': {e}")
            self.tiempo_ejecucion = (datetime.now() - tiempo_inicio).total_seconds()
            self.ejecutada = True
            
            return {
                'consulta': self.nombre,
                'resultados': self.resultados,
                'datos': pd.DataFrame(),
                'total_filas': 0,
                'tiempo_ejecucion': self.tiempo_ejecucion,
                'exitosa': False,
                'error': str(e)
            }

class MotorConsultas:
    """Motor de consultas optimizado para BI"""
    
    def __init__(self):
        self.consultas_cache = {}
        self.estadisticas_ejecucion = {}
        
    def crear_consulta(
        self,
        nombre: str,
        campo_valor: str,
        campo_categoria: Optional[str] = None,
        tipo_agregacion: TipoAgregacion = TipoAgregacion.SUM,
        filtros: Optional[List[Filtro]] = None,
        limite: Optional[int] = None
    ) -> Consulta:
        """Crear consulta simple (método conveniente)"""
        
        # Medida principal
        medida = Medida(
            nombre=f"{campo_valor}_{tipo_agregacion.value}",
            campo=campo_valor,
            tipo_agregacion=tipo_agregacion,
            alias="valor"
        )
        
        # Construir grupo por
        grupo_por = [campo_categoria] if campo_categoria else None
        
        # Crear consulta
        consulta = Consulta(
            nombre=nombre,
            tablas=["principal"],
            medidas=[medida],
            grupo_por=grupo_por,
            filtros=filtros,
            limite=limite
        )
        
        return consulta
    
    def ejecutar_consulta(self, consulta: Consulta, datos: pd.DataFrame, usar_cache: bool = True) -> Dict[str, Any]:
        """Ejecutar consulta con caché opcional"""
        
        # Verificar caché
        if usar_cache:
            cache_key = self._generar_cache_key(consulta, datos.shape)
            if cache_key in self.consultas_cache:
                logger.info(f"Usando resultado cacheado para consulta: {consulta.nombre}")
                return self.consultas_cache[cache_key]
        
        # Ejecutar consulta
        resultado = consulta.ejecutar(datos)
        
        # Guardar en caché
        if usar_cache and resultado['exitosa']:
            cache_key = self._generar_cache_key(consulta, datos.shape)
            self.consultas_cache[cache_key] = resultado
            
            # Actualizar estadísticas
            if consulta.nombre not in self.estadisticas_ejecucion:
                self.estadisticas_ejecucion[consulta.nombre] = {
                    'veces_ejecutada': 0,
                    'tiempo_total': 0,
                    'tiempo_promedio': 0,
                    'exitosas': 0,
                    'fallidas': 0
                }
            
            stats = self.estadisticas_ejecucion[consulta.nombre]
            stats['veces_ejecutada'] += 1
            stats['tiempo_total'] += resultado['tiempo_ejecucion']
            stats['tiempo_promedio'] = stats['tiempo_total'] / stats['veces_ejecutada']
            
            if resultado['exitosa']:
                stats['exitosas'] += 1
            else:
                stats['fallidas'] += 1
        
        return resultado
    
    def ejecutar_consultas_multiples(
        self, 
        consultas: List[Consulta], 
        datos: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Ejecutar múltiples consultas en paralelo cuando sea posible"""
        
        resultados = []
        
        for consulta in consultas:
            resultado = self.ejecutar_consulta(consulta, datos)
            resultados.append(resultado)
        
        return resultados
    
    def crear_consulta_kpi(
        self,
        campo_valor: str,
        tipo_agregacion: TipoAgregacion = TipoAgregacion.SUM,
        filtros: Optional[List[Filtro]] = None
    ) -> Consulta:
        """Crear consulta específica para KPIs"""
        
        medida = Medida(
            nombre=f"kpi_{campo_valor}",
            campo=campo_valor,
            tipo_agregacion=tipo_agregacion,
            alias="kpi"
        )
        
        return Consulta(
            nombre=f"KPI_{campo_valor}",
            tablas=["principal"],
            medidas=[medida],
            filtros=filtros
        )
    
    def crear_consulta_tendencia(
        self,
        campo_valor: str,
        campo_fecha: str,
        tipo_agregacion: TipoAgregacion = TipoAgregacion.SUM,
        periodo: str = "mes",  # dia, semana, mes, año
        filtros: Optional[List[Filtro]] = None
    ) -> Consulta:
        """Crear consulta para análisis de tendencias temporales"""
        
        # Para tendencias temporales, el campo_fecha se usa como grupo
        medida = Medida(
            nombre=f"tendencia_{campo_valor}",
            campo=campo_valor,
            tipo_agregacion=tipo_agregacion,
            alias="valor"
        )
        
        return Consulta(
            nombre=f"Tendencia_{campo_valor}_por_{periodo}",
            tablas=["principal"],
            medidas=[medida],
            grupo_por=[campo_fecha],
            filtros=filtros,
            orden_por=[(campo_fecha, True)]
        )
    
    def crear_consulta_ranking(
        self,
        campo_valor: str,
        campo_categoria: str,
        tipo_agregacion: TipoAgregacion = TipoAgregacion.SUM,
        limite: int = 10,
        descendente: bool = True
    ) -> Consulta:
        """Crear consulta para rankings Top N"""
        
        medida = Medida(
            nombre=f"ranking_{campo_valor}",
            campo=campo_valor,
            tipo_agregacion=tipo_agregacion,
            alias="valor"
        )
        
        return Consulta(
            nombre=f"Ranking_{campo_categoria}",
            tablas=["principal"],
            medidas=[medida],
            grupo_por=[campo_categoria],
            orden_por=[("valor", descendente)],
            limite=limite
        )
    
    def limpiar_cache(self):
        """Limpiar caché de consultas"""
        self.consultas_cache.clear()
        logger.info("Caché de consultas limpiado")
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtener estadísticas de ejecución de consultas"""
        return {
            'consultas_cacheadas': len(self.consultas_cache),
            'estadisticas_por_consulta': self.estadisticas_ejecucion,
            'total_ejecuciones': sum(
                stats['veces_ejecutada'] 
                for stats in self.estadisticas_ejecucion.values()
            )
        }
    
    def _generar_cache_key(self, consulta: Consulta, forma_datos: Tuple[int, int]) -> str:
        """Generar clave única para caché"""
        # Simplificado - en producción podría ser más sofisticado
        campos_hash = str(sorted([f.campo for f in consulta.filtros]))
        grupo_hash = str(sorted(consulta.grupo_por))
        datos_hash = f"{forma_datos[0]}x{forma_datos[1]}"
        
        import hashlib
        return hashlib.md5(f"{consulta.nombre}_{campos_hash}_{grupo_hash}_{datos_hash}".encode()).hexdigest()
    
    def optimizar_consulta(self, consulta: Consulta, datos: pd.DataFrame) -> Consulta:
        """Optimizar consulta basada en estadísticas anteriores"""
        
        # Optimizaciones básicas
        optimizaciones = []
        
        # Si hay filtros muy restrictivos, aplicarlos primero
        if len(consulta.filtros) > 3:
            optimizaciones.append("Considerar usar índices para campos de filtro")
        
        # Si el resultado es muy grande, sugerir paginación
        if consulta.nombre in self.estadisticas_ejecucion:
            stats = self.estadisticas_ejecucion[consulta.nombre]
            if stats['tiempo_promedio'] > 5.0:  # Más de 5 segundos
                optimizaciones.append("Considerar agregar límite o paginación")
                optimizaciones.append("Considerar pre-agregaciones")
        
        # Aplicar optimizaciones
        if optimizaciones:
            logger.info(f"Optimizaciones sugeridas para {consulta.nombre}: {optimizaciones}")
        
        return consulta