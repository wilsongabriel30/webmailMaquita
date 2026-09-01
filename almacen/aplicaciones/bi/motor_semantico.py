"""
Modelo Semántico - Dataset + Relaciones + Medidas
Diferencia claramente dimensiones, métricas y medidas para análisis profesional
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
from datetime import datetime, date
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class TipoCampo(Enum):
    """Tipos de campos en el modelo semántico"""
    DIMENSION = "dimension"      # Texto, fecha, categorías
    METRICA = "metrica"         # Numéricos agregables
    MEDIDA = "medida"           # Cálculos definidos por usuario

class TipoAgregacion(Enum):
    """Tipos de agregación soportados"""
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    MIN = "min"
    MAX = "max"

class ComparacionTemporal(Enum):
    """Tipos de comparaciones temporales"""
    MOM = "mom"           # Month over Month
    YOY = "yoy"           # Year over Year
    YTD = "ytd"           # Year to Date

class CampoSemantico:
    """Campo en el modelo semántico con metadata enriquecida"""
    def __init__(
        self,
        nombre: str,
        tipo: TipoCampo,
        descripcion: str = "",
        unidad: str = "",
        formato: str = "",
        agregacion_default: Optional[TipoAgregacion] = None
    ):
        self.nombre = nombre
        self.tipo = tipo
        self.descripcion = descripcion
        self.unidad = unidad
        self.formato = formato  # Formato de display: $#, %#, #,###
        self.agregacion_default = agregacion_default
        
        # Propiedades derivadas
        self.is_calculado = False
        self.formula = None
        self.es_tiempo = False
        self.jerarquia = None

class Medida:
    """Cálculo definido por usuario - DAX light"""
    def __init__(
        self,
        nombre: str,
        formula: str,
        descripcion: str = "",
        categoria: str = "Personalizada"
    ):
        self.nombre = nombre
        self.formula = formula
        self.descripcion = descripcion
        self.categoria = categoria
        self.es_valida = False
        self.dependencias = []  # Campos que depende
        
        # Analizar la fórmula para detectar dependencias
        self._analizar_formula()

    def _analizar_formula(self):
        """Analizar fórmula para extraer dependencias y validar sintaxis"""
        # Palabras reservadas
        palabras_reservadas = ['SUM', 'AVG', 'COUNT', 'DISTINCT', 'MIN', 'MAX', 
                               'DIVIDE', 'IF', 'AND', 'OR', 'ISBLANK', 'DATE', 'YEAR', 'MONTH']
        
        # Extraer identificadores (nombres de campos)
        import re
        identificadores = re.findall(r'\b[A-Z][A-Z0-9_]*\b', self.formula)
        
        # Filtrar palabras reservadas y dejar solo campos
        self.dependencias = [
            campo for campo in identificadores 
            if campo not in palabras_reservadas
        ]
        
        # Validación básica de sintaxis
        self.es_valida = self._validar_sintaxis()
        
    def _validar_sintaxis(self) -> bool:
        """Validación básica de sintaxis de la fórmula"""
        try:
            # Reemplazar funciones conocidas con equivalentes Python para prueba
            formula_prueba = self.formula
            formula_prueba = formula_prueba.replace('DIVIDE', '/')
            formula_prueba = formula_prueba.replace('ISBLANK', 'lambda x: x is None')
            
            # Simulación básica - no ejecutar, solo validar estructura
            return len(formula_prueba) > 0 and '(' in formula_prueba and ')' in formula_prueba
        except:
            return False

class Relacion:
    """Relación entre dos tablas/datasets"""
    def __init__(
        self,
        tabla_origen: str,
        campo_origen: str,
        tabla_destino: str,
        campo_destino: str,
        tipo: str = "uno_a_muchos"
    ):
        self.tabla_origen = tabla_origen
        self.campo_origen = campo_origen
        self.tabla_destino = tabla_destino
        self.campo_destino = campo_destino
        self.tipo = tipo  # uno_a_muchos, muchos_a_muchos, uno_a_uno

class ModeloSemantico:
    """Modelo semántico completo con dimensiones, métricas y medidas"""
    
    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre
        self.descripcion = descripcion
        self.campos: Dict[str, CampoSemantico] = {}
        self.medidas: Dict[str, Medida] = {}
        self.relaciones: List[Relacion] = []
        self.tablas_principales: Dict[str, str] = {}  # nombre -> descripcion
        
        # Configuración de análisis
        self.jerarquias: Dict[str, List[str]] = {}  # campo -> jerarquía
        self.categorias: Dict[str, List[str]] = {}   # campo -> valores únicos
        
        # Auditoría
        self.creado_en = datetime.now()
        self.creado_por = None
        self.actualizado_en = datetime.now()
        self.version = 1
        
    def agregar_campo(self, campo: CampoSemantico) -> 'ModeloSemantico':
        """Agregar campo al modelo"""
        self.campos[campo.nombre] = campo
        
        # Detectar automáticamente campos de tiempo
        if 'fecha' in campo.nombre.lower() or 'date' in campo.nombre.lower():
            campo.es_tiempo = True
            if not campo.agregacion_default:
                campo.agregacion_default = TipoAgregacion.COUNT
        
        return self
        
    def agregar_medida(self, medida: Medida) -> 'ModeloSemantico':
        """Agregar medida al modelo"""
        self.medidas[medida.nombre] = medida
        return self
        
    def agregar_relacion(self, relacion: Relacion) -> 'ModeloSemantico':
        """Agregar relación entre tablas"""
        self.relaciones.append(relacion)
        return self
        
    def definir_jerarquia(self, campo: str, niveles: List[str]) -> 'ModeloSemantico':
        """Definir jerarquía para drill-down"""
        self.jerarquias[campo] = niveles
        return self
        
    def get_campos_por_tipo(self, tipo: TipoCampo) -> List[CampoSemantico]:
        """Obtener campos por tipo"""
        return [c for c in self.campos.values() if c.tipo == tipo]
        
    def get_dimensiones(self) -> List[CampoSemantico]:
        """Obtener todas las dimensiones"""
        return self.get_campos_por_tipo(TipoCampo.DIMENSION)
        
    def get_metricas(self) -> List[CampoSemantico]:
        """Obtener todas las métricas"""
        return self.get_campos_por_tipo(TipoCampo.METRICA)
        
    def get_medidas(self) -> List[Medida]:
        """Obtener todas las medidas"""
        return list(self.medidas.values())
        
    def get_campo(self, nombre: str) -> Optional[CampoSemantico]:
        """Obtener campo por nombre"""
        return self.campos.get(nombre)
        
    def get_medida(self, nombre: str) -> Optional[Medida]:
        """Obtener medida por nombre"""
        return self.medidas.get(nombre)
        
    def get_relaciones_para_tabla(self, tabla: str) -> List[Relacion]:
        """Obtener relaciones que involucran una tabla"""
        return [
            r for r in self.relaciones 
            if r.tabla_origen == tabla or r.tabla_destino == tabla
        ]
        
    def validar(self) -> Tuple[bool, List[str]]:
        """Validar integridad del modelo"""
        errores = []
        
        # Validar que haya dimensiones y métricas
        if not self.get_dimensiones():
            errores.append("El modelo debe tener al menos una dimensión")
            
        if not self.get_metricas():
            errores.append("El modelo debe tener al menos una métrica")
        
        # Validar medidas
        for medida in self.get_medidas():
            if not medida.es_valida:
                errores.append(f"Medida '{medida.nombre}' tiene fórmula inválida")
                
            # Validar que las dependencias existan
            for dep in medida.dependencias:
                if dep not in self.campos:
                    errores.append(f"Medida '{medida.nombre}' depende de campo '{dep}' que no existe")
        
        # Validar relaciones
        for relacion in self.relaciones:
            if not relacion.campo_origen in self.campos:
                errores.append(f"Relación inválida: campo origen '{relacion.campo_origen}' no existe")
            if not relacion.campo_destino in self.campos:
                errores.append(f"Relación inválida: campo destino '{relacion.campo_destino}' no existe")
        
        return len(errores) == 0, errores

class MotorCalculo:
    """Motor de cálculo para medidas y agregaciones"""
    
    def __init__(self, modelo: ModeloSemantico):
        self.modelo = modelo
        self.cache_calculos = {}
        
    def ejecutar_agregacion(
        self,
        datos: pd.DataFrame,
        campo: str,
        tipo_agregacion: TipoAgregacion,
        grupo_por: Optional[List[str]] = None
    ) -> Union[pd.Series, pd.DataFrame]:
        """Ejecutar agregación sobre datos"""
        if campo not in datos.columns:
            raise ValueError(f"Campo '{campo}' no encontrado en datos")
        
        columna = datos[campo]
        
        if tipo_agregacion == TipoAgregacion.SUM:
            resultado = columna.sum()
        elif tipo_agregacion == TipoAgregacion.AVG:
            resultado = columna.mean()
        elif tipo_agregacion == TipoAgregacion.COUNT:
            resultado = columna.count()
        elif tipo_agregacion == TipoAgregacion.DISTINCT_COUNT:
            resultado = columna.nunique()
        elif tipo_agregacion == TipoAgregacion.MIN:
            resultado = columna.min()
        elif tipo_agregacion == TipoAgregacion.MAX:
            resultado = columna.max()
        else:
            raise ValueError(f"Tipo de agregación no soportado: {tipo_agregacion}")
        
        # Si hay agrupación
        if grupo_por:
            if tipo_agregacion == TipoAgregacion.SUM:
                resultado = datos.groupby(grupo_por)[campo].sum()
            elif tipo_agregacion == TipoAgregacion.AVG:
                resultado = datos.groupby(grupo_por)[campo].mean()
            elif tipo_agregacion == TipoAgregacion.COUNT:
                resultado = datos.groupby(grupo_por)[campo].count()
            elif tipo_agregacion == TipoAgregacion.DISTINCT_COUNT:
                resultado = datos.groupby(grupo_por)[campo].nunique()
            elif tipo_agregacion == TipoAgregacion.MIN:
                resultado = datos.groupby(grupo_por)[campo].min()
            elif tipo_agregacion == TipoAgregacion.MAX:
                resultado = datos.groupby(grupo_por)[campo].max()
                
            return resultado.reset_index()
        
        return resultado
    
    def ejecutar_medida(
        self,
        datos: pd.DataFrame,
        nombre_medida: str
    ) -> Union[float, int, pd.Series]:
        """Ejecutar medida definida en el modelo semántico"""
        medida = self.modelo.get_medida(nombre_medida)
        if not medida:
            raise ValueError(f"Medida '{nombre_medida}' no encontrada")
        
        # Verificar caché
        cache_key = f"{nombre_medida}_{hash(datos.to_string())}"
        if cache_key in self.cache_calculos:
            return self.cache_calculos[cache_key]
        
        # Ejecutar fórmula
        try:
            resultado = self._evaluar_formula(datos, medida.formula)
            self.cache_calculos[cache_key] = resultado
            return resultado
        except Exception as e:
            logger.error(f"Error ejecutando medida '{nombre_medida}': {e}")
            raise
    
    def _evaluar_formula(self, datos: pd.DataFrame, formula: str) -> Union[float, int, pd.Series]:
        """
        Evaluar fórmula de medida de forma segura.

        Usa un parser basado en AST que solo permite funciones
        de agregación whitelisted y operaciones aritméticas.
        """
        import ast
        import operator
        import re

        # Funciones permitidas (whitelist estricta)
        funciones_permitidas = {
            'SUM': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.SUM),
            'AVG': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.AVG),
            'COUNT': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.COUNT),
            'DISTINCT': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.DISTINCT_COUNT),
            'MIN': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.MIN),
            'MAX': lambda campo: self.ejecutar_agregacion(datos, campo, TipoAgregacion.MAX),
            'DIVIDE': lambda numerador, denominador: numerador / denominador if denominador != 0 else 0,
            'IF': lambda condicion, valor_verdadero, valor_falso: valor_verdadero if condicion else valor_falso,
            'AND': lambda *args: all(args),
            'OR': lambda *args: any(args),
            'ISBLANK': lambda x: pd.isna(x) or x is None,
        }

        # Campos de datos disponibles
        campos_datos = {campo: datos[campo] for campo in datos.columns}

        # Operadores permitidos
        ops_binarios = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }
        ops_unarios = {
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        ops_comparacion = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }

        def _eval_nodo(nodo):
            """Evaluador recursivo seguro basado en AST"""
            if isinstance(nodo, ast.Expression):
                return _eval_nodo(nodo.body)

            # Constantes numéricas y strings
            elif isinstance(nodo, ast.Constant):
                if isinstance(nodo.value, (int, float, str)):
                    return nodo.value
                raise ValueError(f"Constante no permitida: {type(nodo.value)}")

            # Operaciones binarias (+, -, *, /)
            elif isinstance(nodo, ast.BinOp) and type(nodo.op) in ops_binarios:
                return ops_binarios[type(nodo.op)](
                    _eval_nodo(nodo.left), _eval_nodo(nodo.right)
                )

            # Operaciones unarias (-, +)
            elif isinstance(nodo, ast.UnaryOp) and type(nodo.op) in ops_unarios:
                return ops_unarios[type(nodo.op)](_eval_nodo(nodo.operand))

            # Comparaciones (==, !=, <, >, <=, >=)
            elif isinstance(nodo, ast.Compare) and len(nodo.ops) == 1:
                op_type = type(nodo.ops[0])
                if op_type in ops_comparacion:
                    return ops_comparacion[op_type](
                        _eval_nodo(nodo.left), _eval_nodo(nodo.comparators[0])
                    )
                raise ValueError(f"Comparación no permitida: {op_type.__name__}")

            # Llamadas a funciones (solo whitelist)
            elif isinstance(nodo, ast.Call):
                if isinstance(nodo.func, ast.Name):
                    nombre_func = nodo.func.id
                    if nombre_func in funciones_permitidas:
                        args = [_eval_nodo(arg) for arg in nodo.args]
                        return funciones_permitidas[nombre_func](*args)
                    raise ValueError(f"Función no permitida: {nombre_func}")
                raise ValueError("Solo se permiten llamadas directas a funciones")

            # Variables (nombres de campos de datos)
            elif isinstance(nodo, ast.Name):
                nombre = nodo.id
                if nombre in campos_datos:
                    return campos_datos[nombre]
                if nombre in funciones_permitidas:
                    return funciones_permitidas[nombre]
                raise ValueError(f"Variable no encontrada: {nombre}")

            # Booleanos
            elif isinstance(nodo, ast.BoolOp):
                if isinstance(nodo.op, ast.And):
                    return all(_eval_nodo(v) for v in nodo.values)
                elif isinstance(nodo.op, ast.Or):
                    return any(_eval_nodo(v) for v in nodo.values)

            raise ValueError(f"Operación no permitida: {type(nodo).__name__}")

        # Validar que la fórmula no contenga patrones peligrosos
        patrones_prohibidos = ['__', 'import', 'exec', 'eval', 'compile', 'globals', 'locals', 'getattr', 'setattr']
        formula_lower = formula.lower()
        for patron in patrones_prohibidos:
            if patron in formula_lower:
                raise ValueError(f"Patrón prohibido en fórmula: {patron}")

        try:
            tree = ast.parse(formula, mode='eval')
            resultado = _eval_nodo(tree)
            return resultado
        except Exception as e:
            raise ValueError(f"Error evaluando fórmula: {e}")

class MotorComparacionTemporal:
    """Motor para comparaciones temporales: MoM, YoY, YTD"""
    
    def __init__(self, datos: pd.DataFrame, campo_fecha: str):
        self.datos = datos
        self.campo_fecha = campo_fecha
        
        # Asegurar que la fecha esté en formato datetime
        self.datos[campo_fecha] = pd.to_datetime(self.datos[campo_fecha])
        
        # Extraer componentes de tiempo
        self.datos['año'] = self.datos[campo_fecha].dt.year
        self.datos['mes'] = self.datos[campo_fecha].dt.month
        self.datos['periodo'] = self.datos['año'].astype(str) + '-' + self.datos['mes'].astype(str).str.zfill(2)
        
    def comparar_mom(self, campo_valor: str) -> pd.DataFrame:
        """Comparación Month over Month"""
        # Agrupar por período y año
        agg = self.datos.groupby(['año', 'mes'])[campo_valor].sum().reset_index()
        
        # Calcular período anterior
        agg['periodo_ordinal'] = agg['año'] * 12 + agg['mes']
        agg['valor_anterior'] = agg.groupby(['periodo_ordinal'])[campo_valor].shift(1)
        
        # Calcular cambio porcentual
        agg['cambio_pct'] = ((agg[campo_valor] - agg['valor_anterior']) / agg['valor_anterior'] * 100).round(2)
        
        return agg[['año', 'mes', campo_valor, 'cambio_pct']]
        
    def comparar_yoy(self, campo_valor: str) -> pd.DataFrame:
        """Comparación Year over Year"""
        # Agrupar por año
        agg = self.datos.groupby(['año'])[campo_valor].sum().reset_index()
        
        # Calcular año anterior
        agg['valor_anterior'] = agg.groupby(['año'])[campo_valor].shift(1)
        
        # Calcular cambio porcentual
        agg['cambio_pct'] = ((agg[campo_valor] - agg['valor_anterior']) / agg['valor_anterior'] * 100).round(2)
        
        return agg[['año', campo_valor, 'cambio_pct']]
        
    def ytd(self, campo_valor: str, año: int) -> float:
        """Year to Date - acumulado hasta la fecha actual del año especificado"""
        datos_año = self.datos[self.datos['año'] == año]
        fecha_actual = pd.to_datetime('today')
        
        # Filtrar hasta fecha actual
        datos_hasta_hoy = datos_año[datos_año[self.campo_fecha] <= fecha_actual]
        
        return datos_hasta_hoy[campo_valor].sum()

class MotorTopN:
    """Motor para cálculos de ranking y Top N"""
    
    def __init__(self, datos: pd.DataFrame):
        self.datos = datos
        
    def calcular_top_n(
        self,
        campo_valor: str,
        campo_categoria: str,
        n: int = 10,
        tipo_agregacion: TipoAgregacion = TipoAgregacion.SUM
    ) -> pd.DataFrame:
        """Calcular Top N por categoría"""
        # Agregar por categoría
        if tipo_agregacion == TipoAgregacion.SUM:
            agregado = self.datos.groupby(campo_categoria)[campo_valor].sum().reset_index()
        elif tipo_agregacion == TipoAgregacion.AVG:
            agregado = self.datos.groupby(campo_categoria)[campo_valor].mean().reset_index()
        elif tipo_agregacion == TipoAgregacion.COUNT:
            agregado = self.datos.groupby(campo_categoria)[campo_valor].count().reset_index()
        else:
            # Para otros tipos, sumar
            agregado = self.datos.groupby(campo_categoria)[campo_valor].sum().reset_index()
        
        # Ordenar y tomar Top N
        resultado = agregado.sort_values(campo_valor, ascending=False).head(n)
        
        # Agregar ranking
        resultado['ranking'] = range(1, len(resultado) + 1)
        
        return resultado
    
    def calcular_percentiles(self, campo_valor: str, percentiles: List[float] = None) -> Dict[str, float]:
        """Calcular percentiles de un campo numérico"""
        if percentiles is None:
            percentiles = [25, 50, 75, 90, 95]
            
        datos_numericos = pd.to_numeric(self.datos[campo_valor], errors='coerce').dropna()
        
        resultado = {}
        for p in percentiles:
            resultado[f'p{p}'] = datos_numericos.quantile(p / 100)
            
        resultado['mediana'] = datos_numericos.median()
        resultado['media'] = datos_numericos.mean()
        
        return resultado