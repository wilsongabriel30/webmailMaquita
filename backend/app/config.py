from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = ""
    redis_url: str = ""
    secret_key: str = ""
    imap_host: str = "127.0.0.1"
    imap_port: int = 143
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 587
    sieve_host: str = "127.0.0.1"
    sieve_port: int = 4190
    mail_domain: str = "example.com"
    cookie_domain: str = "mail.example.com"
    cors_origins: str = "https://mail.example.com"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7
    # SOGo DAV
    sogo_dav_url: str = "http://127.0.0.1:20000/SOGo/dav"
    # Limits
    max_attachment_size_mb: int = 25
    # Cache TTLs (seconds)
    cache_messages_ttl: int = 45
    cache_autocomplete_ttl: int = 90
    cache_directory_ttl: int = 600
    cache_preferences_ttl: int = 3600
    cache_calendars_ttl: int = 300
    # Drafts
    draft_autosave_interval_s: int = 30
    # Secrets centralizados (Fase 3)
    master_password: str = ""
    admin_jwt_secret: str = ""
    ia_api_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    nc_base_url: str = "http://nextcloud-server"
    nc_admin_user: str = ""
    nc_admin_pass: str = ""
    nc_public_url: str = "https://nube.ejemplo.com"
    onlyoffice_url: str = "http://nextcloud-server:8080"  # URL de OnlyOffice (configurar en .env)
    onlyoffice_secret: str = ""
    onlyoffice_download_secret: str = ""
    # Security logging
    security_log_path: str = "/var/log/webmail/security.log"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
