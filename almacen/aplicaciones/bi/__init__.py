"""
BI Engine - Motor de Inteligencia de Negocios Hexagonal
Implementación modular y extensible con arquitectura limpia
"""

from .motor_datos import (
    MotorDatos,
    TipoOrigen,
    IConectorDatos,
    ConectorODK,
    ConectorArchivos
)

from .motor_semantico import (
    ModeloSemantico,
    CampoSemantico,
    Medida,
    MotorCalculo,
    MotorComparacionTemporal,
    MotorTopN,
    TipoCampo,
    TipoAgregacion
)

from .motor_consultas import (
    MotorConsultas,
    Consulta,
    Medida as MedidaConsulta,
    Filtro,
    OperadorFiltro,
    TipoAgregacion as TipoAgregacionConsulta
)

from .motor_visualizacion import (
    MotorVisualizacion,
    Visualizacion,
    TipoChart,
    ColorScheme,
    SeriesConfig,
    EjeConfig
)

__version__ = "1.0.0"
__author__ = "Maquita BI Team"

# Exportaciones principales para facilitar uso
__all__ = [
    # Motores principales
    'MotorDatos',
    'ModeloSemantico', 
    'MotorConsultas',
    'MotorVisualizacion',
    
    # Tipos y enums
    'TipoOrigen',
    'TipoCampo',
    'TipoAgregacion',
    'OperadorFiltro',
    'TipoChart',
    
    # Entidades del dominio
    'CampoSemantico',
    'Medida',
    'Filtro',
    'Consulta',
    'Visualizacion',
    'SeriesConfig',
    'ColorScheme',
    
    # Componentes técnicos
    'IConectorDatos',
    'ConectorODK',
    'ConectorArchivos',
    'MotorCalculo',
    'MotorComparacionTemporal',
    'MotorTopN',
    'EjeConfig'
]

logger = logging.getLogger(__name__)
logger.info(f"BI Engine v{__version__} cargado - Arquitectura Hexagonal implementada")