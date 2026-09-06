# -*- coding: utf-8 -*-
"""
Configuración centralizada del Sistema FARO
Migrado de INTRANET para compatibilidad con módulos legacy

Fundación Maquita Cushunchic (MCCH)
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """Configuración base de la aplicación"""

    # Configuración de Flask
    SECRET_KEY = os.getenv('SECRET_KEY')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Información de la aplicación
    APP_NAME = os.getenv('APP_NAME', 'Sistema FARO')
    APP_VERSION = os.getenv('APP_VERSION', '4.1.0')
    FARO_PUBLIC_URL = os.getenv('FARO_PUBLIC_URL', 'https://datos.maquita.com.ec')
    # URL interna para que OnlyOffice Document Server pueda descargar archivos
    # (OnlyOffice DS puede no tener acceso al dominio público)
    FARO_INTERNAL_URL = os.getenv('FARO_INTERNAL_URL', 'http://localhost')

    # Configuración de base de datos principal (Nómina)
    NOMINA_DB_CONFIG = {
        'host': os.getenv('NOMINA_DB_HOST', 'localhost'),
        'port': int(os.getenv('NOMINA_DB_PORT', 5432)),
        'database': os.getenv('NOMINA_DB_NAME', 'nomina'),
        'username': os.getenv('NOMINA_DB_USER', 'sistemas'),
        'password': os.getenv('NOMINA_DB_PASSWORD')
    }

    # URI de conexión SQLAlchemy para BD de Nómina
    NOMINA_DATABASE_URI = (
        f"postgresql://{NOMINA_DB_CONFIG['username']}:{NOMINA_DB_CONFIG['password']}"
        f"@{NOMINA_DB_CONFIG['host']}:{NOMINA_DB_CONFIG['port']}/{NOMINA_DB_CONFIG['database']}"
    )

    # Alias para compatibilidad con código legacy
    SQLALCHEMY_DATABASE_URI = NOMINA_DATABASE_URI
    AUTH_DATABASE_URI = NOMINA_DATABASE_URI

    # Configuración de base de datos Nube (Nextcloud/archivos)
    NUBE_DB_CONFIG = {
        'host': os.getenv('NUBE_DB_HOST', 'localhost'),
        'port': int(os.getenv('NUBE_DB_PORT', 5432)),
        'database': os.getenv('NUBE_DB_NAME', 'nube'),
        'username': os.getenv('NUBE_DB_USER', 'sistemas'),
        'password': os.getenv('NUBE_DB_PASSWORD')
    }

    NUBE_DATABASE_URI = (
        f"postgresql://{NUBE_DB_CONFIG['username']}:{NUBE_DB_CONFIG['password']}"
        f"@{NUBE_DB_CONFIG['host']}:{NUBE_DB_CONFIG['port']}/{NUBE_DB_CONFIG['database']}"
    )

    # Configuración de base de datos ODK
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'odk'),
        'username': os.getenv('DB_USER', 'analytics_readonly'),
        'password': os.getenv('DB_PASSWORD')
    }

    # Configuración de base de datos de Tecnología (TI)
    TI_DB_CONFIG = {
        'host': os.getenv('TI_DB_HOST', 'localhost'),
        'port': int(os.getenv('TI_DB_PORT', 5432)),
        'database': os.getenv('TI_DB_NAME', 'tecnologia'),
        'username': os.getenv('TI_DB_USER', 'sistemas'),
        'password': os.getenv('TI_DB_PASSWORD')
    }

    TI_DATABASE_URI = (
        f"postgresql://{TI_DB_CONFIG['username']}:{TI_DB_CONFIG['password']}"
        f"@{TI_DB_CONFIG['host']}:{TI_DB_CONFIG['port']}/{TI_DB_CONFIG['database']}"
    )

    # Configuración de base de datos de Finanzas
    FINANZAS_DB_CONFIG = {
        'host': os.getenv('FINANZAS_DB_HOST', 'localhost'),
        'port': int(os.getenv('FINANZAS_DB_PORT', 5432)),
        'database': os.getenv('FINANZAS_DB_NAME', 'finanzas'),
        'username': os.getenv('FINANZAS_DB_USER', 'sistemas'),
        'password': os.getenv('FINANZAS_DB_PASSWORD')
    }

    FINANZAS_DATABASE_URI = (
        f"postgresql://{FINANZAS_DB_CONFIG['username']}:{FINANZAS_DB_CONFIG['password']}"
        f"@{FINANZAS_DB_CONFIG['host']}:{FINANZAS_DB_CONFIG['port']}/{FINANZAS_DB_CONFIG['database']}"
    )

    # Configuración de base de datos de Herramientas (Transcripciones, etc.)
    HERRAMIENTAS_DB_CONFIG = {
        'host': os.getenv('HERRAMIENTAS_DB_HOST', 'localhost'),
        'port': int(os.getenv('HERRAMIENTAS_DB_PORT', 5432)),
        'database': os.getenv('HERRAMIENTAS_DB_NAME', 'herramientas'),
        'username': os.getenv('HERRAMIENTAS_DB_USER', 'sistemas'),
        'password': os.getenv('HERRAMIENTAS_DB_PASSWORD')
    }

    HERRAMIENTAS_DATABASE_URI = (
        f"postgresql://{HERRAMIENTAS_DB_CONFIG['username']}:{HERRAMIENTAS_DB_CONFIG['password']}"
        f"@{HERRAMIENTAS_DB_CONFIG['host']}:{HERRAMIENTAS_DB_CONFIG['port']}/{HERRAMIENTAS_DB_CONFIG['database']}"
    )

    # Configuración de base de datos IA Maquita (Conversaciones, Documentos, Entrenamiento)
    IA_MAQUITA_DB_CONFIG = {
        'host': os.getenv('IA_MAQUITA_DB_HOST', 'localhost'),
        'port': int(os.getenv('IA_MAQUITA_DB_PORT', 5432)),
        'database': os.getenv('IA_MAQUITA_DB_NAME', 'ia_maquita'),
        'username': os.getenv('IA_MAQUITA_DB_USER', 'sistemas'),
        'password': os.getenv('IA_MAQUITA_DB_PASSWORD')
    }

    IA_MAQUITA_DATABASE_URI = (
        f"postgresql://{IA_MAQUITA_DB_CONFIG['username']}:{IA_MAQUITA_DB_CONFIG['password']}"
        f"@{IA_MAQUITA_DB_CONFIG['host']}:{IA_MAQUITA_DB_CONFIG['port']}/{IA_MAQUITA_DB_CONFIG['database']}"
    )

    # Configuración de base de datos Trazabilidad (CRM - Alimentos, Artesanías, Agro, Turismo)
    TRAZABILIDAD_DB_CONFIG = {
        'host': os.getenv('TRAZABILIDAD_DB_HOST', 'localhost'),
        'port': int(os.getenv('TRAZABILIDAD_DB_PORT', 5432)),
        'database': os.getenv('TRAZABILIDAD_DB_NAME', 'trazabilidad'),
        'username': os.getenv('TRAZABILIDAD_DB_USER', 'sistemas'),
        'password': os.getenv('TRAZABILIDAD_DB_PASSWORD')
    }

    TRAZABILIDAD_DATABASE_URI = (
        f"postgresql://{TRAZABILIDAD_DB_CONFIG['username']}:{TRAZABILIDAD_DB_CONFIG['password']}"
        f"@{TRAZABILIDAD_DB_CONFIG['host']}:{TRAZABILIDAD_DB_CONFIG['port']}/{TRAZABILIDAD_DB_CONFIG['database']}"
    )

    # Configuración de base de datos Evaluaciones de Desempeño (perfil de cargo, pruebas, malla 360/270/180)
    EVALUACIONES_DB_CONFIG = {
        'host': os.getenv('EVALUACIONES_DB_HOST', 'localhost'),
        'port': int(os.getenv('EVALUACIONES_DB_PORT', 5432)),
        'database': os.getenv('EVALUACIONES_DB_NAME', 'evaluaciones'),
        'username': os.getenv('EVALUACIONES_DB_USER', 'sistemas'),
        'password': os.getenv('EVALUACIONES_DB_PASSWORD')
    }

    EVALUACIONES_DATABASE_URI = (
        f"postgresql://{EVALUACIONES_DB_CONFIG['username']}:{EVALUACIONES_DB_CONFIG['password']}"
        f"@{EVALUACIONES_DB_CONFIG['host']}:{EVALUACIONES_DB_CONFIG['port']}/{EVALUACIONES_DB_CONFIG['database']}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Pool de conexiones optimizado para 24 workers gunicorn (actualizado 2026-01-26)
    # Cálculo: 24 workers × 7 bases de datos × (pool_size + max_overflow) = conexiones máximas
    # Con pool_size=2, max_overflow=3: 24 × 7 × 5 = 840 conexiones potenciales
    # PostgreSQL max_connections = 700 (configurado en VM 110)
    # Ver: documentacion/13-INFRAESTRUCTURA/POSTGRESQL_OPTIMIZACION_CONEXIONES.md
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 2,           # Conexiones base por engine
        'pool_recycle': 1800,     # Reciclar conexiones cada 30 min
        'pool_pre_ping': True,    # Verificar conexión antes de usar
        'max_overflow': 3,        # Conexiones adicionales bajo demanda
        'pool_timeout': 5,        # Timeout para obtener conexión del pool (bajado de 30: fallar rapido en corte de BD)
        'connect_args': {
            'connect_timeout': 3,                       # Falla rapido si BD inalcanzable (3s)
            'tcp_user_timeout': 3000,                   # Mata conexion stale sin ACK en 3s (ms): pre_ping no se cuelga en corte de red
            'keepalives': 1,                            # TCP keepalive: detecta conexiones muertas
            'keepalives_idle': 30,                      # Primer probe tras 30s de inactividad
            'keepalives_interval': 10,                  # Probes cada 10s
            'keepalives_count': 3,                      # 3 probes fallidos = conexion muerta
            'options': '-c statement_timeout=30000'     # Mata queries >30 segundos
        }
    }

    # Configuración de autenticación
    SKIP_EMAIL_VERIFICATION_IN_DEV = os.getenv('SKIP_EMAIL_VERIFICATION_IN_DEV', 'True').lower() == 'true'
    ALLOW_WEAK_PASSWORDS_IN_DEV = os.getenv('ALLOW_WEAK_PASSWORDS_IN_DEV', 'False').lower() == 'true'
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
    ACCOUNT_LOCK_DURATION_MINUTES = int(os.getenv('ACCOUNT_LOCK_MINUTES', 30))

    # Configuración de sesión
    # 7 días por defecto (antes 2h). Sesión permanente y deslizante:
    # sobrevive reinicios del servidor y no expira mientras el usuario la usa.
    SESSION_HOURS = int(os.getenv('SESSION_HOURS', 168))
    REMEMBER_COOKIE_DURATION = timedelta(hours=SESSION_HOURS)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_HOURS)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_PROTECTION = 'strong'

    # Validación de contraseñas
    PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', 12))
    PASSWORD_REQUIRE_UPPERCASE = os.getenv('PASSWORD_REQUIRE_UPPERCASE', 'True').lower() == 'true'
    PASSWORD_REQUIRE_LOWERCASE = os.getenv('PASSWORD_REQUIRE_LOWERCASE', 'True').lower() == 'true'
    PASSWORD_REQUIRE_NUMBERS = os.getenv('PASSWORD_REQUIRE_NUMBERS', 'True').lower() == 'true'
    PASSWORD_REQUIRE_SPECIAL = os.getenv('PASSWORD_REQUIRE_SPECIAL', 'True').lower() == 'true'

    # Roles disponibles
    AVAILABLE_ROLES = ['master', 'admin', 'user']

    # Branding por defecto
    DEFAULT_LOGO_MAIN = 'maquita.jpg'
    DEFAULT_THEME = 'default'

    # Auditoría
    AUDIT_LOG_ENABLED = os.getenv('AUDIT_LOG_ENABLED', 'True').lower() == 'true'

    # Configuración de paginación y límites
    PAGINATION_SIZE = int(os.getenv('PAGINATION_SIZE', 100))
    MAX_EXPORT_ROWS = int(os.getenv('MAX_EXPORT_ROWS', 50000))

    # Configuración de archivos
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    EXPORT_FOLDER = os.getenv('EXPORT_FOLDER', 'exports')
    REPORTS_FOLDER = os.getenv('REPORTS_FOLDER', 'reports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 * 1024  # 16GB

    # Configuración de cache
    CACHE_TYPE = 'simple'
    CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_TIMEOUT', 3600))

    # Configuración de logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', '/var/log/maquita/faro_app.log')
    LOG_MAX_SIZE = os.getenv('LOG_MAX_SIZE', '10MB')
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # Logs específicos para BI
    BI_UPLOAD_LOG_FILE = os.getenv('BI_UPLOAD_LOG_FILE', '/var/log/maquita/bi_upload.log')
    BI_ERROR_LOG_FILE = os.getenv('BI_ERROR_LOG_FILE', '/var/log/maquita/bi_error.log')

    # =====================================================
    # AI Worker - Servidor de IA con GPU
    # =====================================================
    AI_WORKER_HOST = os.getenv('AI_WORKER_HOST', 'localhost')

    # Whisper API - Transcripción de Audio
    WHISPER_API_URL = os.getenv('WHISPER_API_URL', 'http://localhost:8765')
    WHISPER_API_KEY = os.getenv('WHISPER_API_KEY')
    WHISPER_MAX_FILE_SIZE_MB = int(os.getenv('WHISPER_MAX_FILE_SIZE_MB', 500))
    WHISPER_TIMEOUT = int(os.getenv('WHISPER_TIMEOUT', 300))

    # Ollama LLM - Chat e IA
    OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
    OLLAMA_DEFAULT_MODEL = os.getenv('OLLAMA_DEFAULT_MODEL', 'llama3.2:3b')
    OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', 120))

    # Document API - Análisis de Documentos
    DOCUMENT_API_URL = os.getenv('DOCUMENT_API_URL', 'http://localhost:8766')
    DOCUMENT_API_KEY = os.getenv('DOCUMENT_API_KEY')
    DOCUMENT_MAX_FILE_SIZE_MB = int(os.getenv('DOCUMENT_MAX_FILE_SIZE_MB', 100))
    DOCUMENT_TIMEOUT = int(os.getenv('DOCUMENT_TIMEOUT', 120))

    # Configuración de email (Zimbra)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'mail.maquita.com.ec')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'gestiontecnologia@maquita.com.ec')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@maquita.com.ec')

    # =========================================================================
    # NEXTCLOUD - Integración Nube Maquita
    # =========================================================================
    NEXTCLOUD_URL = os.getenv('NEXTCLOUD_URL', 'http://localhost')
    NEXTCLOUD_ADMIN_USER = os.getenv('NEXTCLOUD_ADMIN_USER', 'gestiontecnologia@maquita.com.ec')
    NEXTCLOUD_ADMIN_PASSWORD = os.getenv('NEXTCLOUD_ADMIN_PASSWORD')
    NEXTCLOUD_ONLYOFFICE_SECRET = os.getenv('NEXTCLOUD_ONLYOFFICE_SECRET')
    # URL publica para el navegador (edicion OnlyOffice)
    NEXTCLOUD_PUBLIC_URL = os.getenv("NEXTCLOUD_PUBLIC_URL", "https://nube.maquita.com.ec")
    ONLYOFFICE_PUBLIC_URL = os.getenv("ONLYOFFICE_PUBLIC_URL", "https://office.maquita.com.ec")

    # =========================================================================
    # JITSI MEET - Videoconferencias
    # =========================================================================
    JITSI_URL = os.getenv('JITSI_URL', 'https://meet.maquita.com.ec')
    JITSI_DOMAIN = os.getenv('JITSI_DOMAIN', 'meet.maquita.com.ec')
    JITSI_APP_ID = os.getenv('JITSI_APP_ID', 'maquita_meet')
    JITSI_APP_SECRET = os.getenv('JITSI_APP_SECRET')

    # =========================================================================
    # KEYCLOAK SSO - Integración dual (FARO local + Keycloak)
    # =========================================================================
    # [M-05] Sin valor por defecto para el secreto: el que traia el codigo quedo publicado.
    # Deshabilitado salvo que se pida; si se habilita sin secreto, el servicio no arranca.
    KEYCLOAK_ENABLED = os.getenv("KEYCLOAK_ENABLED", "false").lower() == "true"
    KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "https://auth.maquita.org")
    KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "maquita")
    KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "faro-backend")
    KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    if KEYCLOAK_ENABLED and len(KEYCLOAK_CLIENT_SECRET.strip()) < 16:
        raise RuntimeError(
            "KEYCLOAK_ENABLED=true pero falta KEYCLOAK_CLIENT_SECRET (o es demasiado corto). "
            "Definelo en el entorno con el secreto real del cliente en Keycloak."
        )

    # Tipos de gráficos disponibles
    CHART_TYPES = {
        'bar': 'Gráfico de Barras',
        'line': 'Gráfico de Líneas',
        'pie': 'Gráfico Circular',
        'scatter': 'Diagrama de Dispersión',
        'histogram': 'Histograma',
        'box': 'Diagrama de Caja',
        'heatmap': 'Mapa de Calor'
    }

    # Tipos de agregación disponibles
    AGGREGATION_TYPES = {
        'count': 'Contar',
        'sum': 'Sumar',
        'mean': 'Promedio',
        'median': 'Mediana',
        'min': 'Mínimo',
        'max': 'Máximo'
    }

    # Configuración de exportación
    EXPORT_FORMATS = {
        'excel': {
            'extension': '.xlsx',
            'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        },
        'csv': {
            'extension': '.csv',
            'mime_type': 'text/csv'
        },
        'pdf': {
            'extension': '.pdf',
            'mime_type': 'application/pdf'
        },
        'json': {
            'extension': '.json',
            'mime_type': 'application/json'
        }
    }

    @staticmethod
    def init_app(app):
        """Inicializa la configuración en la aplicación Flask"""
        for folder in [Config.UPLOAD_FOLDER, Config.EXPORT_FOLDER,
                      Config.REPORTS_FOLDER, 'logs']:
            os.makedirs(folder, exist_ok=True)


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    SKIP_EMAIL_VERIFICATION_IN_DEV = True
    ALLOW_WEAK_PASSWORDS_IN_DEV = True


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SKIP_EMAIL_VERIFICATION_IN_DEV = False
    ALLOW_WEAK_PASSWORDS_IN_DEV = False
    CACHE_TYPE = 'redis'


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Mapeo de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
