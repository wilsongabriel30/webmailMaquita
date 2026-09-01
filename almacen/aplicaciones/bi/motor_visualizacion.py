"""
Motor de Visualización - Configuración de charts y layout
Transforma datos de consultas en configuraciones para Chart.js, D3.js y otras librerías
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
from datetime import datetime
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

class TipoChart(Enum):
    """Tipos de gráficos soportados"""
    BARRA = "bar"
    LINEA = "line"
    AREA = "area"
    PIE = "pie"
    DONUT = "doughnut"
    RADAR = "radar"
    POLAR = "polarArea"
    DISPERSION = "scatter"
    BURBUJA = "bubble"
    MAPA_CALOR = "heatmap"
    GAUGE = "gauge"
    TABLA = "table"
    KPI = "kpi"

class TipoVisualizacion(Enum):
    """Tipos de visualización según la naturaleza de los datos"""
    COMPARACION = "comparacion"      # Comparar categorías
    TENDENCIA = "tendencia"        # Evolución en tiempo
    DISTRIBUCION = "distribucion"    # Partes de un todo
    CORRELACION = "correlacion"      # Relación entre variables
    GEOGRAFICO = "geografico"        # Datos espaciales
    JERARQUIA = "jerarquia"        # Estructuras jerárquicas

class ColorScheme:
    """Esquemas de color predefinidos"""
    
    # Esquemas institucionales
    MAQUITA_BLUE = [
        "#0061a1", "#004d80", "#003366", "#00274d", "#001a33",
        "#66b3ff", "#80c0ff", "#99ccff", "#b3d9ff", "#cce6ff"
    ]
    
    MAQUITA_GREEN = [
        "#28a745", "#218838", "#1e7e34", "#19692c", "#155724",
        "#66d98f", "#80e1a3", "#99d9b8", "#b3d1cc", "#cce9d6"
    ]
    
    MAQUITA_ORANGE = [
        "#fd7e14", "#e85d0b", "#d63384", "#c02434", "#a01e2d",
        "#ffb366", "#ffc085", "#ffcc99", "#ffd699", "#ffe6cc"
    ]
    
    # Esquemas temáticos
    CATEGORICAL = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9"
    ]
    
    SEQUENTIAL = [
        "#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6",
        "#4292c6", "#2171b5", "#08519c", "#08306b", "#081d58"
    ]
    
    DIVERGING = [
        "#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7",
        "#f7f7f7", "#d1e5f0", "#92c5de", "#4393c3", "#2166ac"
    ]

class EjeConfig:
    """Configuración de ejes"""
    def __init__(
        self,
        titulo: str = "",
        mostrar: bool = True,
        escala: str = "linear",  # linear, logarithmic, time
        minimo: Optional[float] = None,
        maximo: Optional[float] = None,
        formato: str = "",  # Formato de números
        angulo: Optional[int] = None  # Para gráficos polares
    ):
        self.titulo = titulo
        self.mostrar = mostrar
        self.escala = escala
        self.minimo = minimo
        self.maximo = maximo
        self.formato = formato
        self.angulo = angulo

class SeriesConfig:
    """Configuración de series de datos"""
    def __init__(
        self,
        nombre: str,
        datos: List[float],
        color: str = None,
        tipo: str = "line",  # line, bar, area, etc.
        tipo_relleno: str = "solid",  # solid, dotted, dashed
        ancho_linea: int = 2,
        opacidad: float = 1.0,
        mostrar_puntos: bool = True,
        relleno_area: bool = False,
        label_visible: bool = True,
        etiqueta_personalizada: Optional[str] = None
    ):
        self.nombre = nombre
        self.datos = datos
        self.color = color
        self.tipo = tipo
        self.tipo_relleno = tipo_relleno
        self.ancho_linea = ancho_linea
        self.opacidad = opacidad
        self.mostrar_puntos = mostrar_puntos
        self.relleno_area = relleno_area
        self.label_visible = label_visible
        self.etiqueta_personalizada = etiqueta_personalizada

class TooltipConfig:
    """Configuración de tooltips"""
    def __init__(
        self,
        activado: bool = True,
        modo: str = "single",  # single, multi, index
        formato: str = "auto",
        campos_adicionales: List[str] = None,
        template_personalizado: Optional[str] = None
    ):
        self.activado = activado
        self.modo = modo
        self.formato = formato
        self.campos_adicionales = campos_adicionales or []
        self.template_personalizado = template_personalizado

class LegendConfig:
    """Configuración de leyendas"""
    def __init__(
        self,
        mostrar: bool = True,
        posicion: str = "top",  # top, bottom, left, right, center
        orientacion: str = "horizontal",  # horizontal, vertical
        estilo: str = "default",  # default, compact, expanded
        texto_personalizado: Optional[Dict[str, str]] = None
    ):
        self.mostrar = mostrar
        self.posicion = posicion
        self.orientacion = orientacion
        self.estilo = estilo
        self.texto_personalizado = texto_personalizado or {}

class Visualizacion:
    """Visualización completa con toda su configuración"""
    def __init__(
        self,
        id: str,
        titulo: str,
        tipo: TipoChart,
        datos: Dict[str, Any],
        categoria: str = "General",
        descripcion: str = "",
        ancho: int = 400,
        alto: int = 300,
        responsive: bool = True,
        animacion: bool = True,
        tema: str = "light",
        esquema_colores: str = "MAQUITA_BLUE",
        eje_x: EjeConfig = None,
        eje_y: EjeConfig = None,
        tooltip: TooltipConfig = None,
        leyenda: LegendConfig = None
    ):
        self.id = id
        self.titulo = titulo
        self.tipo = tipo
        self.datos = datos
        self.categoria = categoria
        self.descripcion = descripcion
        self.ancho = ancho
        self.alto = alto
        self.responsive = responsive
        self.animacion = animacion
        self.tema = tema
        self.esquema_colores = esquema_colores
        self.eje_x = eje_x or EjeConfig()
        self.eje_y = eje_y or EjeConfig()
        self.tooltip = tooltip or TooltipConfig()
        self.leyenda = leyenda or LegendConfig()
        
        # Configuración interna
        self.series: List[SeriesConfig] = []
        self.filtros_interactivos: List[str] = []
        self.drill_down: Optional[Dict[str, Any]] = None
        self.exportacion_habilitada: bool = True
        self.configuracion_personalizada: Dict[str, Any] = {}
        
    def agregar_serie(self, serie: SeriesConfig) -> 'Visualizacion':
        """Agregar serie de datos"""
        self.series.append(serie)
        return self
        
    def configurar_filtro_interactivo(self, campo: str) -> 'Visualizacion':
        """Configurar filtro interactivo para cross-filtering"""
        self.filtros_interactivos.append(campo)
        return self
        
    def configurar_drill_down(self, campo: str, niveles: List[str]) -> 'Visualizacion':
        """Configurar drill-down jerárquico"""
        self.drill_down = {
            'campo': campo,
            'niveles': niveles,
            'nivel_actual': 0
        }
        return self
        
    def obtener_colores(self) -> List[str]:
        """Obtener esquema de colores"""
        esquemas = {
            'MAQUITA_BLUE': ColorScheme.MAQUITA_BLUE,
            'MAQUITA_GREEN': ColorScheme.MAQUITA_GREEN,
            'MAQUITA_ORANGE': ColorScheme.MAQUITA_ORANGE,
            'CATEGORICAL': ColorScheme.CATEGORICAL,
            'SEQUENTIAL': ColorScheme.SEQUENTIAL,
            'DIVERGING': ColorScheme.DIVERGING
        }
        return esquemas.get(self.esquema_colores, ColorScheme.MAQUITA_BLUE)
    
    def to_chartjs(self) -> Dict[str, Any]:
        """Convertir a configuración Chart.js"""
        config = {
            'type': self.tipo.value if self.tipo != TipoChart.AREA else 'line',
            'data': {
                'labels': self.datos.get('labels', []),
                'datasets': []
            },
            'options': {
                'responsive': self.responsive,
                'maintainAspectRatio': False,
                'plugins': {
                    'title': {
                        'display': bool(self.titulo),
                        'text': self.titulo,
                        'font': {'size': 16, 'weight': 'bold'}
                    },
                    'legend': {
                        'display': self.leyenda.mostrar,
                        'position': self.leyenda.posicion,
                        'labels': {'usePointStyle': True}
                    },
                    'tooltip': {
                        'enabled': self.tooltip.activado,
                        'mode': self.tooltip.modo,
                        'intersect': False
                    }
                },
                'animation': {
                    'duration': 1000 if self.animacion else 0
                }
            }
        }
        
        # Configurar ejes
        if self.tipo not in [TipoChart.PIE, TipoChart.DONUT, TipoChart.RADAR, TipoChart.POLAR]:
            config['options']['scales'] = {
                'x': {
                    'display': self.eje_x.mostrar,
                    'title': {'display': bool(self.eje_x.titulo), 'text': self.eje_x.titulo},
                    'type': self.eje_x.escala if self.eje_x.escala != 'linear' else 'category'
                },
                'y': {
                    'display': self.eje_y.mostrar,
                    'title': {'display': bool(self.eje_y.titulo), 'text': self.eje_y.titulo},
                    'type': self.eje_y.escala,
                    'min': self.eje_y.minimo,
                    'max': self.eje_y.maximo
                }
            }
        
        # Agregar series
        colores = self.obtener_colores()
        for i, serie in enumerate(self.series):
            dataset = {
                'label': serie.etiqueta_personalizada or serie.nombre,
                'data': serie.datos,
                'borderColor': colores[i % len(colores)],
                'backgroundColor': colores[i % len(colores)],
                'fill': serie.relleno_area,
                'borderWidth': serie.ancho_linea,
                'pointRadius': 4 if serie.mostrar_puntos else 0,
                'tension': 0.4 if serie.tipo == 'line' else 0
            }
            
            if self.tipo == TipoChart.AREA:
                dataset['fill'] = True
                dataset['backgroundColor'] = colores[i % len(colores)] + '40'  # Add transparency
            
            config['data']['datasets'].append(dataset)
        
        return config
    
    def to_d3(self) -> Dict[str, Any]:
        """Convertir a configuración D3.js (para visualizaciones avanzadas)"""
        return {
            'id': self.id,
            'type': self.tipo.value,
            'data': self.datos,
            'config': {
                'width': self.ancho,
                'height': self.alto,
                'colors': self.obtener_colores(),
                'margins': {'top': 20, 'right': 20, 'bottom': 40, 'left': 60}
            },
            'interactions': {
                'crossFilter': self.filtros_interactivos,
                'drillDown': self.drill_down
            },
            'series': [
                {
                    'name': serie.nombre,
                    'data': serie.datos,
                    'color': serie.color,
                    'type': serie.tipo
                } for serie in self.series
            ]
        }
    
    def to_kpi(self) -> Dict[str, Any]:
        """Convertir a configuración KPI específica"""
        valor = self.series[0].datos[-1] if self.series else 0
        
        return {
            'id': self.id,
            'title': self.titulo,
            'value': valor,
            'format': self.eje_y.formato or ',.0f',
            'color': self.obtener_colores()[0],
            'icon': self.configuracion_personalizada.get('icono', 'trending-up'),
            'change': self.configuracion_personalizada.get('cambio', 0),
            'changeType': self.configuracion_personalizada.get('tipo_cambio', 'porcentaje'),
            'description': self.descripcion,
            'subtitle': self.configuracion_personalizada.get('subtitulo', ''),
            'trend': self.configuracion_personalizada.get('tendencia', 'neutral')
        }
    
    def exportar_configuracion(self) -> Dict[str, Any]:
        """Exportar configuración completa para guardar/restaurar"""
        return {
            'id': self.id,
            'titulo': self.titulo,
            'tipo': self.tipo.value,
            'categoria': self.categoria,
            'descripcion': self.descripcion,
            'ancho': self.ancho,
            'alto': self.alto,
            'responsive': self.responsive,
            'animacion': self.animacion,
            'tema': self.tema,
            'esquema_colores': self.esquema_colores,
            'eje_x': {
                'titulo': self.eje_x.titulo,
                'mostrar': self.eje_x.mostrar,
                'escala': self.eje_x.escala,
                'minimo': self.eje_x.minimo,
                'maximo': self.eje_y.maximo,
                'formato': self.eje_x.formato
            },
            'eje_y': {
                'titulo': self.eje_y.titulo,
                'mostrar': self.eje_y.mostrar,
                'escala': self.eje_y.escala,
                'minimo': self.eje_y.minimo,
                'maximo': self.eje_y.maximo,
                'formato': self.eje_y.formato
            },
            'tooltip': {
                'activado': self.tooltip.activado,
                'modo': self.tooltip.modo,
                'formato': self.tooltip.formato
            },
            'leyenda': {
                'mostrar': self.leyenda.mostrar,
                'posicion': self.leyenda.posicion,
                'orientacion': self.leyenda.orientacion
            },
            'series': [
                {
                    'nombre': s.nombre,
                    'color': s.color,
                    'tipo': s.tipo,
                    'ancho_linea': s.ancho_linea,
                    'opacidad': s.opacidad,
                    'mostrar_puntos': s.mostrar_puntos,
                    'relleno_area': s.relleno_area
                } for s in self.series
            ],
            'filtros_interactivos': self.filtros_interactivos,
            'drill_down': self.drill_down,
            'configuracion_personalizada': self.configuracion_personalizada
        }

class MotorVisualizacion:
    """Motor principal de visualizaciones"""
    
    def __init__(self):
        self.visualizaciones: Dict[str, Visualizacion] = {}
        self.plantillas: Dict[str, Visualizacion] = {}
        self.estadisticas_rendimiento = {}
        
        # Inicializar plantillas comunes
        self._inicializar_plantillas()
    
    def crear_visualizacion(
        self,
        id: str,
        titulo: str,
        tipo: TipoChart,
        datos: Dict[str, Any],
        **kwargs
    ) -> Visualizacion:
        """Crear nueva visualización"""
        
        viz = Visualizacion(
            id=id,
            titulo=titulo,
            tipo=tipo,
            datos=datos,
            **kwargs
        )
        
        self.visualizaciones[id] = viz
        logger.info(f"Visualización '{id}' creada: {tipo.value}")
        
        return viz
    
    def crear_desde_consulta(
        self,
        consulta_resultado: Dict[str, Any],
        tipo_chart: TipoChart,
        config_personalizada: Optional[Dict[str, Any]] = None
    ) -> Visualizacion:
        """Crear visualización a partir de resultado de consulta"""
        
        if not consulta_resultado['exitosa']:
            raise ValueError("No se puede crear visualización de consulta fallida")
        
        datos_df = consulta_resultado['datos']
        consulta_id = consulta_resultado['consulta']
        
        # Determinar configuración automática
        if datos_df.empty:
            raise ValueError("Sin datos para crear visualización")
        
        # Extraer etiquetas y valores
        if len(datos_df.columns) >= 2:
            etiquetas = datos_df.iloc[:, 0].tolist()
            columnas_valores = datos_df.columns[1:]
            
            # Crear visualización
            viz = self.crear_visualizacion(
                id=f"{consulta_id}_{tipo_chart.value}",
                titulo=f"Gráfico de {consulta_id}",
                tipo=tipo_chart,
                datos={
                    'labels': etiquetas,
                    'datasets': {}
                }
            )
            
            # Agregar series
            colores = viz.obtener_colores()
            for i, columna in enumerate(columnas_valores):
                serie = SeriesConfig(
                    nombre=str(columna),
                    datos=datos_df[columna].tolist(),
                    color=colores[i % len(colores)]
                )
                viz.agregar_serie(serie)
            
            # Aplicar configuración personalizada
            if config_personalizada:
                viz.configuracion_personalizada.update(config_personalizada)
            
            return viz
        
        raise ValueError("Se necesitan al menos 2 columnas para crear visualización")
    
    def crear_dashboard(
        self,
        consultas_resultados: List[Dict[str, Any]],
        tipos_charts: List[TipoChart] = None
    ) -> List[Visualizacion]:
        """Crear dashboard múltiple a partir de múltiples consultas"""
        
        if tipos_charts is None:
            tipos_charts = [TipoChart.BARRA, TipoChart.LINEA, TipoChart.PIE]
        
        visualizaciones = []
        
        for i, resultado in enumerate(consultas_resultados):
            if resultado['exitosa']:
                tipo_chart = tipos_charts[i % len(tipos_charts)]
                viz = self.crear_desde_consulta(resultado, tipo_chart)
                visualizaciones.append(viz)
        
        return visualizaciones
    
    def get_visualizacion(self, id: str) -> Optional[Visualizacion]:
        """Obtener visualización por ID"""
        return self.visualizaciones.get(id)
    
    def actualizar_visualizacion(
        self,
        id: str,
        nuevos_datos: Dict[str, Any]
    ) -> bool:
        """Actualizar datos de una visualización"""
        viz = self.get_visualizacion(id)
        if viz:
            viz.datos = nuevos_datos
            logger.info(f"Visualización '{id}' actualizada")
            return True
        return False
    
    def optimizar_visualizacion(self, id: str, tipo_dispositivo: str = "desktop") -> Visualizacion:
        """Optimizar visualización según tipo de dispositivo"""
        viz = self.get_visualizacion(id)
        if not viz:
            raise ValueError(f"Visualización '{id}' no encontrada")
        
        # Optimizaciones según dispositivo
        if tipo_dispositivo == "mobile":
            viz.ancho = min(viz.ancho, 300)
            viz.alto = min(viz.alto, 200)
            viz.leyenda.posicion = "bottom"
            viz.leyenda.orientacion = "horizontal"
            viz.tooltip.modo = "single"
        elif tipo_dispositivo == "tablet":
            viz.ancho = min(viz.ancho, 600)
            viz.alto = min(viz.alto, 400)
        
        return viz
    
    def exportar_visualizacion(self, id: str, formato: str = "chartjs") -> Dict[str, Any]:
        """Exportar visualización en formato específico"""
        viz = self.get_visualizacion(id)
        if not viz:
            raise ValueError(f"Visualización '{id}' no encontrada")
        
        if formato == "chartjs":
            return viz.to_chartjs()
        elif formato == "d3":
            return viz.to_d3()
        elif formato == "kpi" and viz.tipo == TipoChart.KPI:
            return viz.to_kpi()
        elif formato == "config":
            return viz.exportar_configuracion()
        else:
            raise ValueError(f"Formato no soportado: {formato}")
    
    def _inicializar_plantillas(self):
        """Inicializar plantillas comunes"""
        
        # Plantilla KPI simple
        self.plantillas['kpi_simple'] = Visualizacion(
            id='kpi_simple_template',
            titulo='KPI',
            tipo=TipoChart.KPI,
            datos={'valor': 0},
            ancho=200,
            alto=150
        )
        
        # Plantilla gráfico de barras
        self.plantillas['barra_simple'] = Visualizacion(
            id='barra_template',
            titulo='Gráfico de Barras',
            tipo=TipoChart.BARRA,
            datos={'labels': [], 'datasets': {}},
            ancho=400,
            alto=300
        )
        
        # Plantilla línea de tiempo
        self.plantillas['linea_temporal'] = Visualizacion(
            id='linea_template',
            titulo='Tendencia Temporal',
            tipo=TipoChart.LINEA,
            datos={'labels': [], 'datasets': {}},
            ancho=600,
            alto=300,
            eje_x=EjeConfig(titulo="Período", mostrar=True),
            eje_y=EjeConfig(titulo="Valor", mostrar=True)
        )
    
    def get_plantilla(self, nombre: str) -> Optional[Visualizacion]:
        """Obtener plantilla por nombre"""
        return self.plantillas.get(nombre)
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtener estadísticas de uso del motor"""
        return {
            'total_visualizaciones': len(self.visualizaciones),
            'plantillas_disponibles': len(self.plantillas),
            'tipos_charts': list(TipoChart),
            'tipos_visualizacion': list(TipoVisualizacion),
            'esquemas_colores': [
                'MAQUITA_BLUE', 'MAQUITA_GREEN', 'MAQUITA_ORANGE',
                'CATEGORICAL', 'SEQUENTIAL', 'DIVERGING'
            ]
        }