-- Migración: Compliance/eDiscovery Module
-- Fecha: 2026-05-13
-- Descripción: Tablas para compliance, eDiscovery, auditoría, legal holds, fraud alerts
-- Base de datos: maildb (PostgreSQL)
-- Ejecutar como: mailserver o postgres


-- ==============================
-- Table: user_activity_log
-- ==============================
--
-- PostgreSQL database dump
--

\restrict LGVXDuozKeu4fUOwVic4Xz8MLKGhYKkH3AaSTT05GAxnOwboU5kX1WEMgIi2qHH

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: user_activity_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_activity_log (
    id bigint NOT NULL,
    username character varying(255) NOT NULL,
    action character varying(50) NOT NULL,
    category character varying(30) DEFAULT 'general'::character varying NOT NULL,
    message_id character varying(255),
    mailbox character varying(255),
    folder character varying(255),
    target character varying(500),
    ip_address inet,
    user_agent text,
    details jsonb,
    risk_level character varying(10) DEFAULT 'low'::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_activity_log OWNER TO postgres;

--
-- Name: TABLE user_activity_log; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.user_activity_log IS 'Auditoría de actividad de usuarios — acciones críticas para compliance/antifraude';


--
-- Name: COLUMN user_activity_log.action; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_activity_log.action IS 'login_success, login_failed, password_change, totp_setup, totp_disable, sieve_create, sieve_modify, forward_create, email_send, email_delete, email_expunge, email_export, attachment_download, impersonate, ediscovery_search';


--
-- Name: COLUMN user_activity_log.category; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_activity_log.category IS 'auth, email, sieve, security, compliance, admin';


--
-- Name: COLUMN user_activity_log.risk_level; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_activity_log.risk_level IS 'low, medium, high, critical';


--
-- Name: user_activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_activity_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_activity_log_id_seq OWNER TO postgres;

--
-- Name: user_activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_activity_log_id_seq OWNED BY public.user_activity_log.id;


--
-- Name: user_activity_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_activity_log ALTER COLUMN id SET DEFAULT nextval('public.user_activity_log_id_seq'::regclass);


--
-- Name: user_activity_log user_activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_activity_log
    ADD CONSTRAINT user_activity_log_pkey PRIMARY KEY (id);


--
-- Name: idx_ual_action; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_action ON public.user_activity_log USING btree (action);


--
-- Name: idx_ual_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_category ON public.user_activity_log USING btree (category);


--
-- Name: idx_ual_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_created ON public.user_activity_log USING btree (created_at);


--
-- Name: idx_ual_message_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_message_id ON public.user_activity_log USING btree (message_id);


--
-- Name: idx_ual_risk; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_risk ON public.user_activity_log USING btree (risk_level);


--
-- Name: idx_ual_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_username ON public.user_activity_log USING btree (username);


--
-- Name: TABLE user_activity_log; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_activity_log TO mailserver;


--
-- Name: SEQUENCE user_activity_log_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_activity_log_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict LGVXDuozKeu4fUOwVic4Xz8MLKGhYKkH3AaSTT05GAxnOwboU5kX1WEMgIi2qHH

-- ==============================
-- Table: mail_trace
-- ==============================
--
-- PostgreSQL database dump
--

\restrict dKKso8mKacElu29QJNhgU94omTLp6QlMwLLZuh9T57iPgLPNXU3uaLD8cslH33O

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: mail_trace; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mail_trace (
    id bigint NOT NULL,
    queue_id character varying(20),
    message_id character varying(500),
    direction character varying(10) DEFAULT 'inbound'::character varying NOT NULL,
    sender character varying(255),
    recipient character varying(255),
    subject_hash character varying(64),
    source_ip inet,
    destination_mx character varying(255),
    helo_name character varying(255),
    size_bytes bigint,
    spf_result character varying(20),
    dkim_result character varying(20),
    dmarc_result character varying(20),
    rspamd_score real,
    rspamd_action character varying(30),
    status character varying(20) DEFAULT 'unknown'::character varying NOT NULL,
    dsn character varying(10),
    delay_seconds real,
    relay character varying(255),
    tls_version character varying(20),
    tls_cipher character varying(100),
    raw_log text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.mail_trace OWNER TO postgres;

--
-- Name: TABLE mail_trace; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.mail_trace IS 'Trazabilidad completa de correos — ingestado desde Postfix/Rspamd/Dovecot logs';


--
-- Name: mail_trace_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mail_trace_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mail_trace_id_seq OWNER TO postgres;

--
-- Name: mail_trace_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mail_trace_id_seq OWNED BY public.mail_trace.id;


--
-- Name: mail_trace id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mail_trace ALTER COLUMN id SET DEFAULT nextval('public.mail_trace_id_seq'::regclass);


--
-- Name: mail_trace mail_trace_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mail_trace
    ADD CONSTRAINT mail_trace_pkey PRIMARY KEY (id);


--
-- Name: idx_mt_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_created ON public.mail_trace USING btree (created_at);


--
-- Name: idx_mt_direction; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_direction ON public.mail_trace USING btree (direction);


--
-- Name: idx_mt_message_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_message_id ON public.mail_trace USING btree (message_id);


--
-- Name: idx_mt_queue_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_queue_id ON public.mail_trace USING btree (queue_id);


--
-- Name: idx_mt_recipient; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_recipient ON public.mail_trace USING btree (recipient);


--
-- Name: idx_mt_sender; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_sender ON public.mail_trace USING btree (sender);


--
-- Name: idx_mt_source_ip; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_source_ip ON public.mail_trace USING btree (source_ip);


--
-- Name: idx_mt_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mt_status ON public.mail_trace USING btree (status);


--
-- Name: TABLE mail_trace; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mail_trace TO mailserver;


--
-- Name: SEQUENCE mail_trace_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.mail_trace_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict dKKso8mKacElu29QJNhgU94omTLp6QlMwLLZuh9T57iPgLPNXU3uaLD8cslH33O

-- ==============================
-- Table: compliance_cases
-- ==============================
--
-- PostgreSQL database dump
--

\restrict OZF7F1EZkQjVpZd9cwJYf1B0pRVN00jbeYbpG1tYoaUdlCHsZOCGJHtb20ercYh

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: compliance_cases; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.compliance_cases (
    id bigint NOT NULL,
    title character varying(500) NOT NULL,
    description text,
    reason text NOT NULL,
    case_type character varying(30) DEFAULT 'investigation'::character varying,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    priority character varying(10) DEFAULT 'normal'::character varying,
    created_by character varying(255) NOT NULL,
    approved_by character varying(255),
    approved_at timestamp with time zone,
    assigned_to character varying(255),
    closed_by character varying(255),
    closed_at timestamp with time zone,
    close_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.compliance_cases OWNER TO postgres;

--
-- Name: TABLE compliance_cases; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.compliance_cases IS 'Casos de compliance/eDiscovery — investigaciones formales con autorización y trazabilidad';


--
-- Name: COLUMN compliance_cases.case_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_cases.case_type IS 'investigation, fraud, compliance, legal, hr, security';


--
-- Name: COLUMN compliance_cases.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_cases.status IS 'open, approved, in_progress, closed, archived';


--
-- Name: compliance_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.compliance_cases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.compliance_cases_id_seq OWNER TO postgres;

--
-- Name: compliance_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.compliance_cases_id_seq OWNED BY public.compliance_cases.id;


--
-- Name: compliance_cases id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_cases ALTER COLUMN id SET DEFAULT nextval('public.compliance_cases_id_seq'::regclass);


--
-- Name: compliance_cases compliance_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_cases
    ADD CONSTRAINT compliance_cases_pkey PRIMARY KEY (id);


--
-- Name: idx_cc_created_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cc_created_by ON public.compliance_cases USING btree (created_by);


--
-- Name: idx_cc_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cc_status ON public.compliance_cases USING btree (status);


--
-- Name: TABLE compliance_cases; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.compliance_cases TO mailserver;


--
-- Name: SEQUENCE compliance_cases_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.compliance_cases_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict OZF7F1EZkQjVpZd9cwJYf1B0pRVN00jbeYbpG1tYoaUdlCHsZOCGJHtb20ercYh

-- ==============================
-- Table: ediscovery_searches
-- ==============================
--
-- PostgreSQL database dump
--

\restrict vMJJ4WE0pe5jyLthavF6IkcXSSERdkox8OhrghlAaQFFuRLjfY6eAeP33ubpOPa

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ediscovery_searches; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ediscovery_searches (
    id bigint NOT NULL,
    case_id bigint NOT NULL,
    query_text text,
    mailboxes_scope text[],
    folders_scope text[],
    senders_filter text[],
    recipients_filter text[],
    date_from timestamp with time zone,
    date_to timestamp with time zone,
    keywords text[],
    has_attachments boolean,
    min_size bigint,
    max_size bigint,
    executed_by character varying(255) NOT NULL,
    executed_at timestamp with time zone DEFAULT now() NOT NULL,
    duration_ms integer,
    result_count integer DEFAULT 0,
    status character varying(20) DEFAULT 'pending'::character varying,
    error_message text
);


ALTER TABLE public.ediscovery_searches OWNER TO postgres;

--
-- Name: ediscovery_searches_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ediscovery_searches_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ediscovery_searches_id_seq OWNER TO postgres;

--
-- Name: ediscovery_searches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ediscovery_searches_id_seq OWNED BY public.ediscovery_searches.id;


--
-- Name: ediscovery_searches id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_searches ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_searches_id_seq'::regclass);


--
-- Name: ediscovery_searches ediscovery_searches_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_searches
    ADD CONSTRAINT ediscovery_searches_pkey PRIMARY KEY (id);


--
-- Name: idx_es_case; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_es_case ON public.ediscovery_searches USING btree (case_id);


--
-- Name: idx_es_executed_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_es_executed_by ON public.ediscovery_searches USING btree (executed_by);


--
-- Name: ediscovery_searches ediscovery_searches_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_searches
    ADD CONSTRAINT ediscovery_searches_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: TABLE ediscovery_searches; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.ediscovery_searches TO mailserver;


--
-- Name: SEQUENCE ediscovery_searches_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.ediscovery_searches_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict vMJJ4WE0pe5jyLthavF6IkcXSSERdkox8OhrghlAaQFFuRLjfY6eAeP33ubpOPa

-- ==============================
-- Table: ediscovery_results
-- ==============================
--
-- PostgreSQL database dump
--

\restrict ZRZfrkwVfbHbCgftXzvna5PAwQUgka5p9kob0zL3jrBG3sGOonu0xHq2E9SXxiG

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ediscovery_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ediscovery_results (
    id bigint NOT NULL,
    search_id bigint NOT NULL,
    mailbox character varying(255) NOT NULL,
    folder character varying(255),
    uid integer,
    message_id character varying(500),
    subject text,
    sender character varying(255),
    recipients text,
    sent_at timestamp with time zone,
    size_bytes bigint,
    has_attachments boolean DEFAULT false,
    attachment_names text[],
    snippet text,
    hash_sha256 character varying(64),
    storage_path text,
    hold_status character varying(20) DEFAULT 'none'::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ediscovery_results OWNER TO postgres;

--
-- Name: ediscovery_results_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ediscovery_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ediscovery_results_id_seq OWNER TO postgres;

--
-- Name: ediscovery_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ediscovery_results_id_seq OWNED BY public.ediscovery_results.id;


--
-- Name: ediscovery_results id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_results ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_results_id_seq'::regclass);


--
-- Name: ediscovery_results ediscovery_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_results
    ADD CONSTRAINT ediscovery_results_pkey PRIMARY KEY (id);


--
-- Name: idx_er_hold; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_er_hold ON public.ediscovery_results USING btree (hold_status);


--
-- Name: idx_er_mailbox; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_er_mailbox ON public.ediscovery_results USING btree (mailbox);


--
-- Name: idx_er_message_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_er_message_id ON public.ediscovery_results USING btree (message_id);


--
-- Name: idx_er_search; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_er_search ON public.ediscovery_results USING btree (search_id);


--
-- Name: ediscovery_results ediscovery_results_search_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_results
    ADD CONSTRAINT ediscovery_results_search_id_fkey FOREIGN KEY (search_id) REFERENCES public.ediscovery_searches(id);


--
-- Name: TABLE ediscovery_results; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.ediscovery_results TO mailserver;


--
-- Name: SEQUENCE ediscovery_results_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.ediscovery_results_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict ZRZfrkwVfbHbCgftXzvna5PAwQUgka5p9kob0zL3jrBG3sGOonu0xHq2E9SXxiG

-- ==============================
-- Table: ediscovery_exports
-- ==============================
--
-- PostgreSQL database dump
--

\restrict E6FJFBYpmGs39Fy9Pmf4ACmPWQEgRxpYPoui6jkGn3PdxzBvdrMdQ1pg59hQc17

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ediscovery_exports; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ediscovery_exports (
    id bigint NOT NULL,
    case_id bigint NOT NULL,
    search_id bigint,
    export_format character varying(10) DEFAULT 'eml'::character varying NOT NULL,
    result_ids bigint[],
    total_messages integer DEFAULT 0,
    file_path text,
    file_hash_sha256 character varying(64),
    file_size bigint,
    exported_by character varying(255) NOT NULL,
    reason text NOT NULL,
    authorized_by text,
    exported_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ediscovery_exports OWNER TO postgres;

--
-- Name: ediscovery_exports_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ediscovery_exports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ediscovery_exports_id_seq OWNER TO postgres;

--
-- Name: ediscovery_exports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ediscovery_exports_id_seq OWNED BY public.ediscovery_exports.id;


--
-- Name: ediscovery_exports id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_exports ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_exports_id_seq'::regclass);


--
-- Name: ediscovery_exports ediscovery_exports_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_pkey PRIMARY KEY (id);


--
-- Name: idx_ee_case; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ee_case ON public.ediscovery_exports USING btree (case_id);


--
-- Name: ediscovery_exports ediscovery_exports_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: ediscovery_exports ediscovery_exports_search_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_search_id_fkey FOREIGN KEY (search_id) REFERENCES public.ediscovery_searches(id);


--
-- Name: TABLE ediscovery_exports; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.ediscovery_exports TO mailserver;


--
-- Name: SEQUENCE ediscovery_exports_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.ediscovery_exports_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict E6FJFBYpmGs39Fy9Pmf4ACmPWQEgRxpYPoui6jkGn3PdxzBvdrMdQ1pg59hQc17

-- ==============================
-- Table: legal_holds
-- ==============================
--
-- PostgreSQL database dump
--

\restrict 8DnBByCSYthVcnRVpI9qNk5Md5JVxntRTS59rrcofIVkPL7FkDhfbA5vZDnZkcc

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: legal_holds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_holds (
    id bigint NOT NULL,
    case_id bigint NOT NULL,
    mailbox character varying(255) NOT NULL,
    scope character varying(20) DEFAULT 'all'::character varying,
    folder_pattern character varying(255),
    date_from timestamp with time zone,
    date_to timestamp with time zone,
    reason text NOT NULL,
    enabled_by character varying(255) NOT NULL,
    enabled_at timestamp with time zone DEFAULT now() NOT NULL,
    released_by character varying(255),
    released_at timestamp with time zone,
    is_active boolean DEFAULT true
);


ALTER TABLE public.legal_holds OWNER TO postgres;

--
-- Name: TABLE legal_holds; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.legal_holds IS 'Retención legal — impide purga/eliminación de correos durante investigación';


--
-- Name: legal_holds_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.legal_holds_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_holds_id_seq OWNER TO postgres;

--
-- Name: legal_holds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.legal_holds_id_seq OWNED BY public.legal_holds.id;


--
-- Name: legal_holds id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_holds ALTER COLUMN id SET DEFAULT nextval('public.legal_holds_id_seq'::regclass);


--
-- Name: legal_holds legal_holds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_holds
    ADD CONSTRAINT legal_holds_pkey PRIMARY KEY (id);


--
-- Name: idx_lh_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lh_active ON public.legal_holds USING btree (is_active);


--
-- Name: idx_lh_case; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lh_case ON public.legal_holds USING btree (case_id);


--
-- Name: idx_lh_mailbox; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lh_mailbox ON public.legal_holds USING btree (mailbox);


--
-- Name: legal_holds legal_holds_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_holds
    ADD CONSTRAINT legal_holds_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: TABLE legal_holds; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.legal_holds TO mailserver;


--
-- Name: SEQUENCE legal_holds_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.legal_holds_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict 8DnBByCSYthVcnRVpI9qNk5Md5JVxntRTS59rrcofIVkPL7FkDhfbA5vZDnZkcc

-- ==============================
-- Table: fraud_alerts
-- ==============================
--
-- PostgreSQL database dump
--

\restrict CM4KetWgLsPLwqU4adNBxt6nwVpuzrhhPeQqwe8YGZJawcK00nN5NlJfKS7NvLg

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: fraud_alerts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fraud_alerts (
    id bigint NOT NULL,
    alert_type character varying(50) NOT NULL,
    severity character varying(10) DEFAULT 'medium'::character varying NOT NULL,
    username character varying(255),
    description text NOT NULL,
    details jsonb,
    source_ip inet,
    is_acknowledged boolean DEFAULT false,
    acknowledged_by character varying(255),
    acknowledged_at timestamp with time zone,
    case_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.fraud_alerts OWNER TO postgres;

--
-- Name: TABLE fraud_alerts; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.fraud_alerts IS 'Alertas antifraude automatizadas — reenvío externo, envío masivo, eliminación masiva, etc';


--
-- Name: COLUMN fraud_alerts.alert_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.fraud_alerts.alert_type IS 'external_forward, suspicious_sieve, unusual_login, mass_send, mass_delete, mass_download, bank_change_keywords, spoofing, evidence_destruction';


--
-- Name: fraud_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fraud_alerts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fraud_alerts_id_seq OWNER TO postgres;

--
-- Name: fraud_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fraud_alerts_id_seq OWNED BY public.fraud_alerts.id;


--
-- Name: fraud_alerts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fraud_alerts ALTER COLUMN id SET DEFAULT nextval('public.fraud_alerts_id_seq'::regclass);


--
-- Name: fraud_alerts fraud_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fraud_alerts
    ADD CONSTRAINT fraud_alerts_pkey PRIMARY KEY (id);


--
-- Name: idx_fa_ack; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fa_ack ON public.fraud_alerts USING btree (is_acknowledged);


--
-- Name: idx_fa_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fa_created ON public.fraud_alerts USING btree (created_at);


--
-- Name: idx_fa_severity; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fa_severity ON public.fraud_alerts USING btree (severity);


--
-- Name: idx_fa_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fa_type ON public.fraud_alerts USING btree (alert_type);


--
-- Name: idx_fa_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fa_username ON public.fraud_alerts USING btree (username);


--
-- Name: fraud_alerts fraud_alerts_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fraud_alerts
    ADD CONSTRAINT fraud_alerts_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: TABLE fraud_alerts; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fraud_alerts TO mailserver;


--
-- Name: SEQUENCE fraud_alerts_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.fraud_alerts_id_seq TO mailserver;


--
-- PostgreSQL database dump complete
--

\unrestrict CM4KetWgLsPLwqU4adNBxt6nwVpuzrhhPeQqwe8YGZJawcK00nN5NlJfKS7NvLg


