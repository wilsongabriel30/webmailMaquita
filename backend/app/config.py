from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


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
    # cookie_domain: dominio de la cookie de sesion. Para SSO entre subdominios
    # (webmail y drive), poner el dominio PADRE con punto inicial, p.ej. ".suorg.tld".
    # Para construir URLs publicas se usa public_base_url, NO este valor.
    cookie_domain: str = "mail.example.com"
    cors_origins: str = "https://mail.example.com"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7
    # SOGo DAV
    sogo_dav_url: str = "http://127.0.0.1:20000/SOGo/dav"
    # Limits
    max_attachment_size_mb: int = Field(
        25, validation_alias=AliasChoices("MAX_ATTACHMENT_MB", "MAX_ATTACHMENT_SIZE_MB")
    )
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
    secure_msg_key: str = ""
    admin_jwt_secret: str = ""
    # Llave DEDICADA de cifrado de credenciales (H-02): formato de llave Fernet. Cifra la
    # credencial IMAP cacheada, las cuentas de Nextcloud y el secreto TOTP. La «anterior»
    # solo sirve para rotar (se descifra con ambas, se cifra con la actual).
    credential_encryption_key: str = ""
    credential_encryption_key_anterior: str = ""
    ia_api_key: str = ""
    # --- IA enchufable (config central; todas las features la leen) ---
    ia_provider: str = "gateway"  # openai | ollama | anthropic | gateway
    ia_base_url: str = ""  # vacio -> usa ollama_url
    ia_model: str = ""  # sin hardcode; definir en .env o panel
    ia_timeout: int = 60
    ia_embed_model: str = "nomic-embed-text"
    ia_embed_url: str = ""  # endpoint de embeddings; vacio -> usa ia_base_url
    ollama_url: str = "http://127.0.0.1:11434"
    nc_base_url: str = "http://nextcloud-server"
    nc_admin_user: str = ""
    nc_admin_pass: str = ""
    nc_public_url: str = "https://nube.ejemplo.com"
    public_base_url: str = "https://mail.maquita.org"
    # SSO / OIDC (Keycloak)
    kc_oidc_enabled: bool = False
    kc_base: str = "https://auth.maquita.org"
    kc_realm: str = "maquita"
    kc_client_id: str = "webmail-maquita"
    kc_client_secret: str = ""
    onlyoffice_url: str = (
        "http://nextcloud-server:8080"  # URL de OnlyOffice (configurar en .env)
    )
    onlyoffice_secret: str = ""
    onlyoffice_download_secret: str = ""
    # Security logging
    security_log_path: str = "/var/log/webmail/security.log"
    # Redes confiables (LAN/VPN): los logins desde aquí NO generan alerta de "IP no habitual".
    # Coma-separadas (CIDR). Por defecto las privadas RFC1918 + loopback.
    trusted_networks: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"
    # Rate limiting por usuario (peticiones por minuto). 0 = deshabilitar ese tier.
    rate_limit_read_per_min: int = 300
    rate_limit_write_per_min: int = 60
    rate_limit_send_per_min: int = 10

    environment: str = "production"  # "development"/"dev"/"local" habilita /docs

    model_config = {"env_file": ".env", "extra": "ignore"}


def _validar_secretos_obligatorios(s: Settings) -> None:
    """Aborta el arranque si falta un secreto obligatorio o tiene valor de ejemplo.
    NUNCA muestra el valor del secreto: el error solo nombra las variables."""
    _PLACEHOLDER = (
        "change",
        "example",
        "placeholder",
        "tu-secreto",
        "your-secret",
        "changeme",
    )
    obligatorios = {
        "SECRET_KEY": s.secret_key,
        "ADMIN_JWT_SECRET": s.admin_jwt_secret,
        "MASTER_PASSWORD": s.master_password,
    }
    malos = [
        n
        for n, v in obligatorios.items()
        if not (v or "").strip() or any(p in (v or "").lower() for p in _PLACEHOLDER)
    ]
    if malos:
        raise RuntimeError(
            "Secretos obligatorios faltantes o con valor de ejemplo: "
            + ", ".join(malos)
            + ". Definelos en .env con valores reales (no los del .env.example)."
        )
    # H-02: la llave de credenciales es obligatoria y tiene que ser una llave Fernet válida.
    try:
        from cryptography.fernet import Fernet

        Fernet((s.credential_encryption_key or "").strip().encode())
    except Exception:
        raise RuntimeError(
            "Falta CREDENTIAL_ENCRYPTION_KEY o no es una llave Fernet valida. Generala con: "
            "python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    _validar_secretos_obligatorios(s)
    return s
