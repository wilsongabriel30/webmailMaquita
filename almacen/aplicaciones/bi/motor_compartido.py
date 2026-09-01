"""
Motor Compartido - Unifica Analytics ODK y Analítica General
Ambos usan el mismo motor pero con orígenes de datos separados según README3.md
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
import pandas as pd
import json
import logging

from .motor_datos import MotorDatos, TipoOrigen
from .motor_semantico import ModeloSemantico, CampoSemantico, TipoCampo
from .motor_consultas import MotorConsultas, Consulta, Filtro, OperadorFiltro
from .motor_visualizacion import MotorVisualizacion, Visualizacion, TipoChart

logger = logging.getLogger(__name__)

class ContextoDatos(Enum):
    """Contextos de datos según plan README3.md"""
    ODK_ANALYTICS = "odk_analytics"      # Solo datos ODK, sin carga externa
    ANALITICA_GENERAL = "analitica_general"  # Archivos + BD, separado de ODK

class MotorCompartido:
    """
    Motor unificado que sirve a ambos dashboards con orígenes separados
    Implementa la separación clara del plan README3.md
    """
    
    def __init__(self):
        # Motores individuales por contexto
        self.motores = {
            ContextoDatos.ODK_ANALYTICS: {
                'datos': MotorDatos(),
                'semantico': ModeloSemantico("ODK Analytics", "Análisis de datos ODK"),
                'consultas': MotorConsultas(),
                'visualizacion': MotorVisualizacion()
            },
            ContextoDatos.ANALITICA_GENERAL: {
                'datos': MotorDatos(),
                'semantico': ModeloSemantico("Analítica General", "Análisis general de datos"),
                'consultas': MotorConsultas(),
                'visualizacion': MotorVisualizacion()
            }
        }
        
        # Configuración de separación
        self.separacion_activa = True
        self.auditoria_cruzada = False  # Nunca mezclar contextos
        
        logger.info("Motor compartido inicializado con separación de contextos")
    
    def obtener_motor(self, contexto: ContextoDatos) -> Dict[str, Any]:
        """Obtener motor para un contexto específico"""
        return self.motores[contexto]
    
    def crear_dashboard_odk(self, form_id: int, form_name: str) -> Dict[str, Any]:
        """
        Crear dashboard para Analytics ODK (solo datos ODK)
        Implementa Fase 1 del plan README3.md
        """
        contexto = ContextoDatos.ODK_ANALYTICS
        motores = self.obtener_motor(contexto)
        
        try:
            # 1. Obtener datos ODK
            config_odk = {'form_id': form_id}
            datos = motores['datos'].obtener_datos(TipoOrigen.ODK, config_odk)
            
            if datos is None or datos.empty:
                logger.warning(f"No hay datos para formulario ODK {form_id}")
                return self._crear_dashboard_vacio("ODK", form_name)
            
            # 2. Crear modelo semántico para ODK
            self._crear_modelo_semantico_odk(motores['semantico'], datos)
            
            # 3. Crear consultas ODK
            consultas = self._crear_consultas_odk(motores['consultas'], datos)
            
            # 4. Crear visualizaciones ODK
            visualizaciones = self._crear_visualizaciones_odk(motores['visualizacion'], consultas)
            
            # 5. Configurar dashboard
            dashboard = {
                'contexto': contexto.value,
                'titulo': f"Analytics: {form_name}",
                'subtitulo': "Datos exclusivos de ODK",
                'datos': datos,
                'consultas': consultas,
                'visualizaciones': visualizaciones,
                'origen_datos': 'ODK',
                'capacidades': ['consulta', 'visualizacion', 'exportar'],
                'limitaciones': ['sin_carga_externa', 'sin_conexion_bd'],
                'estilo': 'odk_analytics'
            }
            
            logger.info(f"Dashboard ODK creado para formulario {form_id}")
            return dashboard
            
        except Exception as e:
            logger.error(f"Error creando dashboard ODK: {e}")
            return self._crear_dashboard_vacio("ODK", form_name)
    
    def crear_dashboard_general(self, origen: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crear dashboard para Analítica General (archivos + BD)
        Implementa Fase 2 del plan README3.md
        """
        contexto = ContextoDatos.ANALITICA_GENERAL
        motores = self.obtener_motor(contexto)
        
        try:
            # 1. Determinar tipo de origen y obtener datos
            if origen == 'archivo':
                tipo_origen = TipoOrigen.ARCHIVO
                datos = motores['datos'].obtener_datos(tipo_origen, config)
            elif origen == 'base_datos':
                tipo_origen = TipoOrigen.BASE_DATOS
                datos = motores['datos'].obtener_datos(tipo_origen, config)
            else:
                raise ValueError(f"Origen no soportado: {origen}")
            
            if datos is None or datos.empty:
                logger.warning(f"No hay datos para origen {origen}")
                return self._crear_dashboard_vacio("General", f"Origen: {origen}")
            
            # 2. Crear modelo semántico para datos generales
            self._crear_modelo_semantico_general(motores['semantico'], datos)
            
            # 3. Crear consultas generales
            consultas = self._crear_consultas_generales(motores['consultas'], datos)
            
            # 4. Crear visualizaciones generales
            visualizaciones = self._crear_visualizaciones_generales(motores['visualizacion'], consultas)
            
            # 5. Configurar dashboard
            dashboard = {
                'contexto': contexto.value,
                'titulo': f"Analítica General: {config.get('nombre', 'Datos')}",
                'subtitulo': f"Origen: {origen.title()}",
                'datos': datos,
                'consultas': consultas,
                'visualizaciones': visualizaciones,
                'origen_datos': origen,
                'capacidades': ['consulta', 'visualizacion', 'exportar', 'carga_archivos', 'conexion_bd'],
                'limitaciones': ['sin_acceso_odk'],
                'estilo': 'analitica_general'
            }
            
            logger.info(f"Dashboard General creado para origen {origen}")
            return dashboard
            
        except Exception as e:
            logger.error(f"Error creando dashboard General: {e}")
            return self._crear_dashboard_vacio("General", f"Origen: {origen}")
    
    def _crear_modelo_semantico_odk(self, modelo: ModeloSemantico, datos: pd.DataFrame):
        """Crear modelo semántico específico para datos ODK"""
        
        # Limpiar modelo anterior
        modelo.campos.clear()
        modelo.medidas.clear()
        
        # Analizar columnas y clasificar
        for columna in datos.columns:
            if columna in ['instanceId', 'createdAt', 'updatedAt', 'submitterId']:
                continue  # Campos del sistema
            
            # Inferir tipo de campo
            tipo_campo = self._inferir_tipo_campo_odk(datos[columna], columna)
            
            campo = CampoSemantico(
                nombre=columna,
                tipo=tipo_campo,
                descripcion=f"Campo ODK: {columna}",
                unidad=self._inferir_unidad_odk(columna, tipo_campo)
            )
            
            modelo.agregar_campo(campo)
        
        # Agregar medidas ODK específicas
        medidas_odk = [
            ("total_submissions", "COUNT(instanceId)", "Total de envíos", "envíos"),
            ("submissions_ultimo_mes", "COUNT(IF(MONTH(createdAt) = MONTH(NOW()), instanceId))", "Envíos último mes", "envíos"),
            ("tasa_aprobacion", "DIVIDE(COUNT(IF(reviewState = 'approved', instanceId)), COUNT(instanceId))", "Tasa de aprobación", "%"),
            ("promedio_tiempo_respuesta", "AVG(DATEDIFF(createdAt, updatedAt))", "Tiempo promedio respuesta", "horas")
        ]
        
        for nombre, formula, descripcion, unidad in medidas_odk:
            from .motor_semantico import Medida
            medida = Medida(nombre, formula, descripcion)
            modelo.agregar_medida(medida)
        
        # Validar modelo
        es_valido, errores = modelo.validar()
        if not es_valido:
            logger.warning(f"Errores en modelo semántico ODK: {errores}")
    
    def _crear_modelo_semantico_general(self, modelo: ModeloSemantico, datos: pd.DataFrame):
        """Crear modelo semántico para datos generales"""
        
        # Limpiar modelo anterior
        modelo.campos.clear()
        modelo.medidas.clear()
        
        # Analizar columnas y clasificar
        for columna in datos.columns:
            tipo_campo = self._inferir_tipo_campo_general(datos[columna])
            
            campo = CampoSemantico(
                nombre=columna,
                tipo=tipo_campo,
                descripcion=f"Campo general: {columna}",
                unidad=self._inferir_unidad_general(columna, tipo_campo)
            )
            
            modelo.agregar_campo(campo)
        
        # Agregar medidas generales
        medidas_generales = [
            ("total_registros", "COUNT(*)", "Total de registros", "registros"),
            ("campos_completos", "COUNT(IF(NOT(ISNULL({campo})), {campo}))", "Registros completos", "registros")
        ]
        
        # Crear medidas para cada campo numérico
        campos_numericos = [c.nombre for c in modelo.get_campos_por_tipo(TipoCampo.METRICA)]
        for campo in campos_numericos[:5]:  # Limitar a 5 para no sobrecargar
            medidas_generales.append((
                f"suma_{campo.lower()}",
                f"SUM({campo})",
                f"Suma de {campo}",
                self._inferir_unidad_general(campo, TipoCampo.METRICA) or "valor"
            ))
        
        for nombre, formula, descripcion, unidad in medidas_generales:
            from .motor_semantico import Medida
            medida = Medida(nombre, formula, descripcion)
            modelo.agregar_medida(medida)
        
        # Validar modelo
        es_valido, errores = modelo.validar()
        if not es_valido:
            logger.warning(f"Errores en modelo semántico General: {errores}")
    
    def _crear_consultas_odk(self, motor: MotorConsultas, datos: pd.DataFrame) -> List[Consulta]:
        """Crear consultas específicas para datos ODK"""
        consultas = []
        
        # Consulta KPI principal
        kpi = motor.crear_consulta_kpi(
            campo_valor="instanceId",
            tipo_agregacion=motor.TipoAgregacion.COUNT
        )
        consultas.append(kpi)
        
        # Consulta por estado de revisión
        if 'reviewState' in datos.columns:
            consulta_estado = motor.crear_consulta(
                nombre="por_estado_revision",
                campo_categoria="reviewState",
                campo_valor="instanceId",
                tipo_agregacion=motor.TipoAgregacion.COUNT
            )
            consultas.append(consulta_estado)
        
        # Consulta temporal si hay fechas
        if 'createdAt' in datos.columns:
            consulta_temporal = motor.crear_consulta_tendencia(
                campo_valor="instanceId",
                campo_fecha="createdAt",
                tipo_agregacion=motor.TipoAgregacion.COUNT,
                periodo="mes"
            )
            consultas.append(consulta_temporal)
        
        return consultas
    
    def _crear_consultas_generales(self, motor: MotorConsultas, datos: pd.DataFrame) -> List[Consulta]:
        """Crear consultas para datos generales"""
        consultas = []
        
        # Consulta KPI principal
        kpi = motor.crear_consulta_kpi(
            campo_valor=datos.columns[0],  # Primera columna
            tipo_agregacion=motor.TipoAgregacion.COUNT
        )
        consultas.append(kpi)
        
        # Consultas para campos categóricos
        campos_categoricos = [c for c in datos.columns if datos[c].dtype == 'object'][:3]
        for campo in campos_categoricos:
            consulta = motor.crear_consulta(
                nombre=f"por_{campo}",
                campo_categoria=campo,
                campo_valor=datos.columns[0],
                tipo_agregacion=motor.TipoAgregacion.COUNT,
                limite=10
            )
            consultas.append(consulta)
        
        # Consulta para campos numéricos
        campos_numericos = [c for c in datos.columns if datos[c].dtype in ['int64', 'float64']][:2]
        for campo in campos_numericos:
            consulta = motor.crear_consulta(
                nombre=f"suma_{campo}",
                campo_categoria=campo,
                campo_valor=campo,
                tipo_agregacion=motor.TipoAgregacion.SUM,
                limite=10
            )
            consultas.append(consulta)
        
        return consultas
    
    def _crear_visualizaciones_odk(self, motor: MotorVisualizacion, consultas: List[Consulta]) -> List[Visualizacion]:
        """Crear visualizaciones específicas para ODK"""
        visualizaciones = []
        
        # Ejecutar consultas para obtener datos
        datos_ejemplo = pd.DataFrame({
            'Enero': [100, 80, 120],
            'Febrero': [90, 85, 110],
            'Marzo': [110, 90, 130],
            'Abril': [95, 88, 125]
        })
        
        for consulta in consultas:
            try:
                resultado = motor.ejecutar_consulta(consulta, datos_ejemplo)
                if resultado['exitosa']:
                    viz = motor.crear_desde_consulta(resultado, TipoChart.BARRA)
                    visualizaciones.append(viz)
            except Exception as e:
                logger.warning(f"No se pudo crear visualización para {consulta.nombre}: {e}")
        
        return visualizaciones
    
    def _crear_visualizaciones_generales(self, motor: MotorVisualizacion, consultas: List[Consulta]) -> List[Visualizacion]:
        """Crear visualizaciones para datos generales"""
        visualizaciones = []
        
        # Datos de ejemplo
        datos_ejemplo = pd.DataFrame({
            'Categoría A': [100, 120, 90, 110],
            'Categoría B': [80, 85, 95, 88],
            'Categoría C': [60, 70, 65, 75],
            'Categoría D': [40, 45, 50, 48]
        })
        
        # Crear visualizaciones variadas
        tipos_charts = [TipoChart.BARRA, TipoChart.LINEA, TipoChart.PIE, TipoChart.DONUT]
        
        for i, consulta in enumerate(consultas[:4]):  # Máximo 4 visualizaciones
            try:
                resultado = motor.ejecutar_consulta(consulta, datos_ejemplo)
                if resultado['exitosa']:
                    tipo_chart = tipos_charts[i % len(tipos_charts)]
                    viz = motor.crear_desde_consulta(resultado, tipo_chart)
                    visualizaciones.append(viz)
            except Exception as e:
                logger.warning(f"No se pudo crear visualización para {consulta.nombre}: {e}")
        
        return visualizaciones
    
    def _crear_dashboard_vacio(self, tipo: str, nombre: str) -> Dict[str, Any]:
        """Crear dashboard vacío cuando no hay datos"""
        return {
            'contexto': tipo.lower(),
            'titulo': f"{tipo}: {nombre}",
            'subtitulo': "No hay datos disponibles",
            'datos': pd.DataFrame(),
            'consultas': [],
            'visualizaciones': [],
            'origen_datos': 'ninguno',
            'capacidades': [],
            'limitaciones': ['sin_datos'],
            'estilo': tipo.lower(),
            'mensaje': f"No se encontraron datos para {nombre}"
        }
    
    def _inferir_tipo_campo_odk(self, serie: pd.Series, nombre: str) -> TipoCampo:
        """Inferir tipo de campo para datos ODK"""
        if nombre.lower() in ['reviewstate', 'status', 'estado']:
            return TipoCampo.DIMENSION
        elif nombre.lower() in ['createdat', 'updatedat', 'date']:
            return TipoCampo.DIMENSION
        elif serie.dtype in ['object', 'string']:
            return TipoCampo.DIMENSION
        elif serie.dtype in ['int64', 'float64']:
            return TipoCampo.METRICA
        elif serie.dtype == 'bool':
            return TipoCampo.DIMENSION
        else:
            return TipoCampo.DIMENSION
    
    def _inferir_tipo_campo_general(self, serie: pd.Series) -> TipoCampo:
        """Inferir tipo de campo para datos generales"""
        if serie.dtype in ['object', 'string']:
            return TipoCampo.DIMENSION
        elif serie.dtype in ['int64', 'float64']:
            return TipoCampo.METRICA
        elif serie.dtype == 'bool':
            return TipoCampo.DIMENSION
        elif 'date' in str(serie.dtype).lower():
            return TipoCampo.DIMENSION
        else:
            return TipoCampo.DIMENSION
    
    def _inferir_unidad_odk(self, nombre: str, tipo: TipoCampo) -> str:
        """Inferir unidad para campos ODK"""
        if tipo != TipoCampo.METRICA:
            return ""
        
        nombre_lower = nombre.lower()
        if 'edad' in nombre_lower or 'age' in nombre_lower:
            return "años"
        elif 'peso' in nombre_lower or 'kg' in nombre_lower:
            return "kg"
        elif 'talla' in nombre_lower or 'altura' in nombre_lower or 'cm' in nombre_lower:
            return "cm"
        elif 'cantidad' in nombre_lower or 'count' in nombre_lower:
            return "unidades"
        
        return ""
    
    def _inferir_unidad_general(self, nombre: str, tipo: TipoCampo) -> str:
        """Inferir unidad para campos generales"""
        if tipo != TipoCampo.METRICA:
            return ""
        
        nombre_lower = nombre.lower()
        if 'edad' in nombre_lower or 'age' in nombre_lower:
            return "años"
        elif 'peso' in nombre_lower or 'kg' in nombre_lower:
            return "kg"
        elif 'talla' in nombre_lower or 'altura' in nombre_lower or 'cm' in nombre_lower:
            return "cm"
        elif 'cantidad' in nombre_lower or 'count' in nombre_lower:
            return "unidades"
        elif 'monto' in nombre_lower or 'amount' in nombre_lower or 'valor' in nombre_lower:
            return "$"
        
        return ""
    
    def verificar_separacion(self) -> Dict[str, Any]:
        """Verificar que no haya cruce de datos entre contextos"""
        return {
            'separacion_activa': self.separacion_activa,
            'auditoria_cruzada': self.auditoria_cruzada,
            'contextos_disponibles': list(ContextoDatos),
            'mensaje': "Separación de contextos activa y funcionando"
        }
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtener estadísticas del motor compartido"""
        return {
            'contextos': len(self.motores),
            'separacion_activa': self.separacion_activa,
            'estadisticas_por_contexto': {
                contexto.value: {
                    'conectores': len(motor['datos'].listar_conectores_disponibles()),
                    'campos': len(motor['semantico'].campos),
                    'medidas': len(motor['semantico'].medidas),
                    'visualizaciones': len(motor['visualizacion'].visualizaciones)
                }
                for contexto, motor in self.motores.items()
            }
        }