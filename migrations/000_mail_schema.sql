-- =============================================================================
-- 000_mail_schema.sql — Esquema de correo (estilo Postfix Admin)
-- Tablas que Postfix y Dovecot consultan para dominios, buzones y alias virtuales.
-- Idempotente: se puede aplicar varias veces sin error.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.domain (
    domain          character varying(255) NOT NULL,
    description     character varying(255) DEFAULT ''::character varying NOT NULL,
    aliases         integer DEFAULT 0 NOT NULL,
    mailboxes       integer DEFAULT 0 NOT NULL,
    maxquota        bigint  DEFAULT 0 NOT NULL,
    quota           bigint  DEFAULT 0 NOT NULL,
    transport       character varying(255) DEFAULT NULL::character varying,
    backupmx        boolean DEFAULT false NOT NULL,
    created         timestamp with time zone DEFAULT now(),
    modified        timestamp with time zone DEFAULT now(),
    active          boolean DEFAULT true NOT NULL,
    password_expiry integer DEFAULT 0,
    CONSTRAINT domain_key PRIMARY KEY (domain)
);
COMMENT ON TABLE public.domain IS 'Postfix Admin - Virtual Domains';

CREATE TABLE IF NOT EXISTS public.mailbox (
    username        character varying(255) NOT NULL,
    password        character varying(255) DEFAULT ''::character varying NOT NULL,
    name            character varying(255) DEFAULT ''::character varying NOT NULL,
    maildir         character varying(255) DEFAULT ''::character varying NOT NULL,
    quota           bigint DEFAULT 0 NOT NULL,
    created         timestamp with time zone DEFAULT now(),
    modified        timestamp with time zone DEFAULT now(),
    active          boolean DEFAULT true NOT NULL,
    domain          character varying(255),
    local_part      character varying(255) NOT NULL,
    phone           character varying(30)  DEFAULT ''::character varying NOT NULL,
    email_other     character varying(255) DEFAULT ''::character varying NOT NULL,
    token           character varying(255) DEFAULT ''::character varying NOT NULL,
    token_validity  timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    password_expiry timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    CONSTRAINT mailbox_key PRIMARY KEY (username)
);
COMMENT ON TABLE public.mailbox IS 'Postfix Admin - Virtual Mailboxes';

CREATE TABLE IF NOT EXISTS public.alias (
    address         character varying(255) NOT NULL,
    goto            text NOT NULL,
    domain          character varying(255) NOT NULL,
    created         timestamp with time zone DEFAULT now(),
    modified        timestamp with time zone DEFAULT now(),
    active          boolean DEFAULT true NOT NULL,
    CONSTRAINT alias_key PRIMARY KEY (address)
);
COMMENT ON TABLE public.alias IS 'Postfix Admin - Virtual Aliases';

CREATE INDEX IF NOT EXISTS domain_domain_active   ON public.domain  USING btree (domain, active);
CREATE INDEX IF NOT EXISTS mailbox_domain_idx     ON public.mailbox USING btree (domain);
CREATE INDEX IF NOT EXISTS mailbox_username_active ON public.mailbox USING btree (username, active);
CREATE INDEX IF NOT EXISTS alias_address_active   ON public.alias   USING btree (address, active);
CREATE INDEX IF NOT EXISTS alias_domain_idx       ON public.alias   USING btree (domain);

-- Claves foráneas (idempotentes)
DO $$ BEGIN
    ALTER TABLE public.mailbox
        ADD CONSTRAINT mailbox_domain_fkey1 FOREIGN KEY (domain) REFERENCES public.domain(domain);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE public.alias
        ADD CONSTRAINT alias_domain_fkey FOREIGN KEY (domain) REFERENCES public.domain(domain);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Administradores del panel del webmail. El backend concede acceso a /admin
-- con: SELECT superadmin FROM admin WHERE username=... AND active=true.
-- El login se hace con el buzón normal (IMAP); esta tabla solo marca quién es admin.
CREATE TABLE IF NOT EXISTS public.admin (
    username        character varying(255) NOT NULL,
    password        character varying(255) DEFAULT ''::character varying NOT NULL,
    created         timestamp with time zone DEFAULT now(),
    modified        timestamp with time zone DEFAULT now(),
    active          boolean DEFAULT true NOT NULL,
    superadmin      boolean DEFAULT false NOT NULL,
    phone           character varying(30)  DEFAULT ''::character varying NOT NULL,
    email_other     character varying(255) DEFAULT ''::character varying NOT NULL,
    token           character varying(255) DEFAULT ''::character varying NOT NULL,
    token_validity  timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    CONSTRAINT admin_key PRIMARY KEY (username)
);
COMMENT ON TABLE public.admin IS 'Postfix Admin - Virtual Admins';
