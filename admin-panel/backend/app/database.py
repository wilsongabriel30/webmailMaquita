import asyncpg
from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS,
        min_size=2, max_size=10,
    )


async def init_admin_tables(pool: asyncpg.Pool):
    """Create admin-specific tables if they dont exist."""
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(512) NOT NULL,
            display_name VARCHAR(255) NOT NULL DEFAULT '',
            role VARCHAR(50) NOT NULL DEFAULT 'admin',
            active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login TIMESTAMP WITH TIME ZONE,
            failed_attempts INT DEFAULT 0,
            locked_until TIMESTAMP WITH TIME ZONE
        );

        CREATE TABLE IF NOT EXISTS admin_sessions (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES admin_users(id) ON DELETE CASCADE,
            token_hash VARCHAR(512) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_audit (
            id SERIAL PRIMARY KEY,
            admin_id INT REFERENCES admin_users(id),
            admin_username VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            target VARCHAR(255),
            details JSONB,
            ip_address VARCHAR(45),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_admin_audit_action ON admin_audit(action);

        CREATE TABLE IF NOT EXISTS ai_config (
            id INT PRIMARY KEY DEFAULT 1,
            provider VARCHAR(50) NOT NULL DEFAULT 'ollama',
            base_url VARCHAR(500) NOT NULL DEFAULT '',
            api_key VARCHAR(500) NOT NULL DEFAULT '',
            model VARCHAR(100) NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT false,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT ai_config_singleton CHECK (id = 1)
        );
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS office_config (
            id INT PRIMARY KEY DEFAULT 1,
            onlyoffice_url VARCHAR(500) NOT NULL DEFAULT '',
            onlyoffice_secret VARCHAR(500) NOT NULL DEFAULT '',
            nc_base_url VARCHAR(500) NOT NULL DEFAULT '',
            nc_public_url VARCHAR(500) NOT NULL DEFAULT '',
            nc_admin_user VARCHAR(200) NOT NULL DEFAULT '',
            nc_admin_pass VARCHAR(500) NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT false,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT office_config_singleton CHECK (id = 1)
        );
    """)
