# -*- coding: utf-8 -*-
"""
Configuración específica para la base de datos de Nómina
Fundación Maquita - Sistema FARO

Migrado de INTRANET para compatibilidad con módulos legacy
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class NominaDBConfig:
    """Configuración específica para la base de datos de Nómina"""

    # Detectar si estamos usando PgBouncer
    USE_PGBOUNCER = os.getenv('USE_PGBOUNCER', 'false').lower() == 'true'

    # Configuración de base de datos de Nómina
    NOMINA_DB_CONFIG = {
        'host': os.getenv('NOMINA_DB_HOST', '193.16.0.132'),
        'port': int(os.getenv('NOMINA_DB_PORT', 6432 if USE_PGBOUNCER else 5432)),
        'database': os.getenv('NOMINA_DB_NAME', 'nomina'),
        'username': os.getenv('NOMINA_DB_USER', 'sistemas'),
        'password': os.getenv('NOMINA_DB_PASSWORD')
    }

    # URI de conexión SQLAlchemy para BD de Nómina
    NOMINA_DATABASE_URI = (
        f"postgresql://{NOMINA_DB_CONFIG['username']}:{NOMINA_DB_CONFIG['password']}"
        f"@{NOMINA_DB_CONFIG['host']}:{NOMINA_DB_CONFIG['port']}/{NOMINA_DB_CONFIG['database']}"
    )

    # Configuraciones para SQLAlchemy binds
    SQLALCHEMY_NOMINA_BINDS = {
        'nomina': NOMINA_DATABASE_URI
    }

    SQLALCHEMY_BINDS = {
        'nomina': NOMINA_DATABASE_URI
    }

    @staticmethod
    def get_nomina_config():
        """Retorna la configuración de la base de datos de nómina"""
        return {
            'host': NominaDBConfig.NOMINA_DB_CONFIG['host'],
            'port': NominaDBConfig.NOMINA_DB_CONFIG['port'],
            'database': NominaDBConfig.NOMINA_DB_CONFIG['database'],
            'username': NominaDBConfig.NOMINA_DB_CONFIG['username'],
            'password': NominaDBConfig.NOMINA_DB_CONFIG['password'],
            'uri': NominaDBConfig.NOMINA_DATABASE_URI
        }
