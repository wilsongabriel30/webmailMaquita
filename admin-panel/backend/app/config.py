import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "maildb")
DB_USER = os.getenv("DB_USER", "mailserver")
DB_PASS = os.getenv("DB_PASS", "")

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480  # 8 horas

RSPAMD_URL = os.getenv("RSPAMD_URL", "http://localhost:11334")
RSPAMD_PASSWORD = os.getenv("RSPAMD_PASSWORD", "")

MAIL_LOG_PATH = "/var/log/mail.log"
POSTFIX_LOG_PATH = "/var/log/mail.log"

VMAIL_PATH = "/var/vmail"