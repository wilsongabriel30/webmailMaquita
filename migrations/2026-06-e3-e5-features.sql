-- ============================================================
-- Migracion: features E3 + E5 (DLP, cifrado OME, Safe Links,
-- simulacion phishing, panel amenazas, comm-compliance,
-- insider-risk, eDiscovery custodios). Generada 2026-06-09.
-- Idempotente donde es posible. Ejecutar como mailserver en maildb.
-- ============================================================

-- 1) Estructura de tablas nuevas
--
-- PostgreSQL database dump
--

\restrict w3e437vnpOlF0ES2qW7X2bsz3fGy4GRQqe7KXZeiLxhXwGtr2pZP1xBquJdolrO

-- Dumped from database version 17.10 (Debian 17.10-0+deb13u1)
-- Dumped by pg_dump version 17.10 (Debian 17.10-0+deb13u1)

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
-- Name: blocked_senders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.blocked_senders (
    id integer NOT NULL,
    pattern character varying(255) NOT NULL,
    note character varying(255) DEFAULT ''::character varying NOT NULL,
    created_by character varying(120) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: blocked_senders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.blocked_senders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: blocked_senders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.blocked_senders_id_seq OWNED BY public.blocked_senders.id;


--
-- Name: case_custodians; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_custodians (
    id bigint NOT NULL,
    case_id bigint NOT NULL,
    email character varying(255) NOT NULL,
    role character varying(40) DEFAULT 'custodio'::character varying NOT NULL,
    hold_id bigint,
    ack_token character varying(48) NOT NULL,
    notified_at timestamp with time zone,
    acknowledged_at timestamp with time zone,
    created_by character varying(120) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: case_custodians_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.case_custodians_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: case_custodians_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.case_custodians_id_seq OWNED BY public.case_custodians.id;


--
-- Name: comm_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comm_flags (
    id bigint NOT NULL,
    policy_id integer,
    policy_name character varying(120) DEFAULT ''::character varying NOT NULL,
    username character varying(255) NOT NULL,
    direction character varying(12) DEFAULT 'outbound'::character varying NOT NULL,
    recipients jsonb DEFAULT '[]'::jsonb NOT NULL,
    subject text DEFAULT ''::text NOT NULL,
    snippet text DEFAULT ''::text NOT NULL,
    matched_terms jsonb DEFAULT '[]'::jsonb NOT NULL,
    severity character varying(10) DEFAULT 'media'::character varying NOT NULL,
    status character varying(12) DEFAULT 'open'::character varying NOT NULL,
    reviewed_by character varying(120) DEFAULT ''::character varying NOT NULL,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: comm_flags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comm_flags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comm_flags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comm_flags_id_seq OWNED BY public.comm_flags.id;


--
-- Name: comm_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comm_policies (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    description character varying(255) DEFAULT ''::character varying NOT NULL,
    terms jsonb DEFAULT '[]'::jsonb NOT NULL,
    scope character varying(12) DEFAULT 'outbound'::character varying NOT NULL,
    severity character varying(10) DEFAULT 'media'::character varying NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: comm_policies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comm_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comm_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comm_policies_id_seq OWNED BY public.comm_policies.id;


--
-- Name: dlp_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dlp_config (
    id integer DEFAULT 1 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    default_action character varying(10) DEFAULT 'warn'::character varying NOT NULL,
    rules jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT dlp_config_singleton CHECK ((id = 1))
);


--
-- Name: dlp_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dlp_keywords (
    id integer NOT NULL,
    term character varying(120) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: dlp_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dlp_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dlp_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dlp_keywords_id_seq OWNED BY public.dlp_keywords.id;


--
-- Name: dlp_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dlp_violations (
    id bigint NOT NULL,
    username character varying(255) NOT NULL,
    recipients jsonb DEFAULT '[]'::jsonb NOT NULL,
    subject text DEFAULT ''::text NOT NULL,
    data_types jsonb DEFAULT '[]'::jsonb NOT NULL,
    action character varying(10) NOT NULL,
    overridden boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: dlp_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dlp_violations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dlp_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dlp_violations_id_seq OWNED BY public.dlp_violations.id;


--
-- Name: phish_campaigns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.phish_campaigns (
    id integer NOT NULL,
    name character varying(160) NOT NULL,
    template_id integer NOT NULL,
    created_by character varying(120) DEFAULT ''::character varying NOT NULL,
    status character varying(12) DEFAULT 'borrador'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    sent_at timestamp with time zone
);


--
-- Name: phish_campaigns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.phish_campaigns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: phish_campaigns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.phish_campaigns_id_seq OWNED BY public.phish_campaigns.id;


--
-- Name: phish_targets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.phish_targets (
    id bigint NOT NULL,
    campaign_id integer NOT NULL,
    email character varying(255) NOT NULL,
    token character varying(48) NOT NULL,
    sent boolean DEFAULT false NOT NULL,
    opened boolean DEFAULT false NOT NULL,
    opened_at timestamp with time zone,
    clicked boolean DEFAULT false NOT NULL,
    clicked_at timestamp with time zone,
    submitted boolean DEFAULT false NOT NULL,
    submitted_at timestamp with time zone,
    reported boolean DEFAULT false NOT NULL,
    reported_at timestamp with time zone
);


--
-- Name: phish_targets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.phish_targets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: phish_targets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.phish_targets_id_seq OWNED BY public.phish_targets.id;


--
-- Name: phish_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.phish_templates (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    subject character varying(255) NOT NULL,
    html text NOT NULL,
    sender_name character varying(120) DEFAULT 'Soporte TI'::character varying NOT NULL,
    sender_email character varying(255) DEFAULT 'no-reply@maquita.org'::character varying NOT NULL,
    difficulty character varying(10) DEFAULT 'media'::character varying NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: phish_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.phish_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: phish_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.phish_templates_id_seq OWNED BY public.phish_templates.id;


--
-- Name: safelinks_blocklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safelinks_blocklist (
    id integer NOT NULL,
    pattern character varying(255) NOT NULL,
    kind character varying(10) DEFAULT 'domain'::character varying NOT NULL,
    note character varying(255) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: safelinks_blocklist_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.safelinks_blocklist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: safelinks_blocklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.safelinks_blocklist_id_seq OWNED BY public.safelinks_blocklist.id;


--
-- Name: safelinks_clicks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safelinks_clicks (
    id bigint NOT NULL,
    username character varying(255) DEFAULT ''::character varying NOT NULL,
    url text NOT NULL,
    host character varying(255) DEFAULT ''::character varying NOT NULL,
    verdict character varying(12) NOT NULL,
    proceeded boolean DEFAULT false NOT NULL,
    ip character varying(64) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: safelinks_clicks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.safelinks_clicks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: safelinks_clicks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.safelinks_clicks_id_seq OWNED BY public.safelinks_clicks.id;


--
-- Name: safelinks_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.safelinks_config (
    id integer DEFAULT 1 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    rewrite_enabled boolean DEFAULT true NOT NULL,
    warn_suspicious boolean DEFAULT true NOT NULL,
    block_listed boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT safelinks_config_singleton CHECK ((id = 1))
);


--
-- Name: secure_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secure_config (
    id integer DEFAULT 1 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    expire_days integer DEFAULT 7 NOT NULL,
    max_views integer DEFAULT 0 NOT NULL,
    intro_text text DEFAULT ''::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT secure_config_singleton CHECK ((id = 1))
);


--
-- Name: secure_message_access; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secure_message_access (
    id bigint NOT NULL,
    token character varying(48) NOT NULL,
    email character varying(255) DEFAULT ''::character varying NOT NULL,
    action character varying(20) NOT NULL,
    ip character varying(64) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: secure_message_access_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secure_message_access_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secure_message_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secure_message_access_id_seq OWNED BY public.secure_message_access.id;


--
-- Name: secure_message_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secure_message_files (
    id bigint NOT NULL,
    token character varying(48) NOT NULL,
    filename text NOT NULL,
    content_type character varying(150) DEFAULT 'application/octet-stream'::character varying NOT NULL,
    body_ct text NOT NULL,
    nonce text NOT NULL
);


--
-- Name: secure_message_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secure_message_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secure_message_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secure_message_files_id_seq OWNED BY public.secure_message_files.id;


--
-- Name: secure_message_otps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secure_message_otps (
    id bigint NOT NULL,
    token character varying(48) NOT NULL,
    email character varying(255) NOT NULL,
    code_hash character varying(128) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: secure_message_otps_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secure_message_otps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secure_message_otps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secure_message_otps_id_seq OWNED BY public.secure_message_otps.id;


--
-- Name: secure_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secure_messages (
    token character varying(48) NOT NULL,
    sender character varying(255) NOT NULL,
    sender_name character varying(255) DEFAULT ''::character varying NOT NULL,
    subject text DEFAULT ''::text NOT NULL,
    recipients jsonb DEFAULT '[]'::jsonb NOT NULL,
    body_ct text NOT NULL,
    nonce text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    revoked boolean DEFAULT false NOT NULL,
    max_views integer DEFAULT 0 NOT NULL,
    view_count integer DEFAULT 0 NOT NULL
);


--
-- Name: threat_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threat_actions (
    id bigint NOT NULL,
    action character varying(30) NOT NULL,
    target character varying(255) DEFAULT ''::character varying NOT NULL,
    detail text DEFAULT ''::text NOT NULL,
    actor character varying(120) DEFAULT ''::character varying NOT NULL,
    auto boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: threat_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.threat_actions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: threat_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.threat_actions_id_seq OWNED BY public.threat_actions.id;


--
-- Name: threat_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threat_config (
    id integer DEFAULT 1 NOT NULL,
    auto_disable_on_compromise boolean DEFAULT false NOT NULL,
    auto_block_dmarc_reject boolean DEFAULT false NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT threat_config_singleton CHECK ((id = 1))
);


--
-- Name: blocked_senders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.blocked_senders ALTER COLUMN id SET DEFAULT nextval('public.blocked_senders_id_seq'::regclass);


--
-- Name: case_custodians id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians ALTER COLUMN id SET DEFAULT nextval('public.case_custodians_id_seq'::regclass);


--
-- Name: comm_flags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comm_flags ALTER COLUMN id SET DEFAULT nextval('public.comm_flags_id_seq'::regclass);


--
-- Name: comm_policies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comm_policies ALTER COLUMN id SET DEFAULT nextval('public.comm_policies_id_seq'::regclass);


--
-- Name: dlp_keywords id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_keywords ALTER COLUMN id SET DEFAULT nextval('public.dlp_keywords_id_seq'::regclass);


--
-- Name: dlp_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_violations ALTER COLUMN id SET DEFAULT nextval('public.dlp_violations_id_seq'::regclass);


--
-- Name: phish_campaigns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_campaigns ALTER COLUMN id SET DEFAULT nextval('public.phish_campaigns_id_seq'::regclass);


--
-- Name: phish_targets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_targets ALTER COLUMN id SET DEFAULT nextval('public.phish_targets_id_seq'::regclass);


--
-- Name: phish_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_templates ALTER COLUMN id SET DEFAULT nextval('public.phish_templates_id_seq'::regclass);


--
-- Name: safelinks_blocklist id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_blocklist ALTER COLUMN id SET DEFAULT nextval('public.safelinks_blocklist_id_seq'::regclass);


--
-- Name: safelinks_clicks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_clicks ALTER COLUMN id SET DEFAULT nextval('public.safelinks_clicks_id_seq'::regclass);


--
-- Name: secure_message_access id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_access ALTER COLUMN id SET DEFAULT nextval('public.secure_message_access_id_seq'::regclass);


--
-- Name: secure_message_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_files ALTER COLUMN id SET DEFAULT nextval('public.secure_message_files_id_seq'::regclass);


--
-- Name: secure_message_otps id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_otps ALTER COLUMN id SET DEFAULT nextval('public.secure_message_otps_id_seq'::regclass);


--
-- Name: threat_actions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_actions ALTER COLUMN id SET DEFAULT nextval('public.threat_actions_id_seq'::regclass);


--
-- Name: blocked_senders blocked_senders_pattern_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.blocked_senders
    ADD CONSTRAINT blocked_senders_pattern_key UNIQUE (pattern);


--
-- Name: blocked_senders blocked_senders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.blocked_senders
    ADD CONSTRAINT blocked_senders_pkey PRIMARY KEY (id);


--
-- Name: case_custodians case_custodians_ack_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians
    ADD CONSTRAINT case_custodians_ack_token_key UNIQUE (ack_token);


--
-- Name: case_custodians case_custodians_case_id_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians
    ADD CONSTRAINT case_custodians_case_id_email_key UNIQUE (case_id, email);


--
-- Name: case_custodians case_custodians_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians
    ADD CONSTRAINT case_custodians_pkey PRIMARY KEY (id);


--
-- Name: comm_flags comm_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comm_flags
    ADD CONSTRAINT comm_flags_pkey PRIMARY KEY (id);


--
-- Name: comm_policies comm_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comm_policies
    ADD CONSTRAINT comm_policies_pkey PRIMARY KEY (id);


--
-- Name: dlp_config dlp_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_config
    ADD CONSTRAINT dlp_config_pkey PRIMARY KEY (id);


--
-- Name: dlp_keywords dlp_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_keywords
    ADD CONSTRAINT dlp_keywords_pkey PRIMARY KEY (id);


--
-- Name: dlp_keywords dlp_keywords_term_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_keywords
    ADD CONSTRAINT dlp_keywords_term_key UNIQUE (term);


--
-- Name: dlp_violations dlp_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dlp_violations
    ADD CONSTRAINT dlp_violations_pkey PRIMARY KEY (id);


--
-- Name: phish_campaigns phish_campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_campaigns
    ADD CONSTRAINT phish_campaigns_pkey PRIMARY KEY (id);


--
-- Name: phish_targets phish_targets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_targets
    ADD CONSTRAINT phish_targets_pkey PRIMARY KEY (id);


--
-- Name: phish_targets phish_targets_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_targets
    ADD CONSTRAINT phish_targets_token_key UNIQUE (token);


--
-- Name: phish_templates phish_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_templates
    ADD CONSTRAINT phish_templates_pkey PRIMARY KEY (id);


--
-- Name: safelinks_blocklist safelinks_blocklist_pattern_kind_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_blocklist
    ADD CONSTRAINT safelinks_blocklist_pattern_kind_key UNIQUE (pattern, kind);


--
-- Name: safelinks_blocklist safelinks_blocklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_blocklist
    ADD CONSTRAINT safelinks_blocklist_pkey PRIMARY KEY (id);


--
-- Name: safelinks_clicks safelinks_clicks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_clicks
    ADD CONSTRAINT safelinks_clicks_pkey PRIMARY KEY (id);


--
-- Name: safelinks_config safelinks_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.safelinks_config
    ADD CONSTRAINT safelinks_config_pkey PRIMARY KEY (id);


--
-- Name: secure_config secure_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_config
    ADD CONSTRAINT secure_config_pkey PRIMARY KEY (id);


--
-- Name: secure_message_access secure_message_access_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_access
    ADD CONSTRAINT secure_message_access_pkey PRIMARY KEY (id);


--
-- Name: secure_message_files secure_message_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_files
    ADD CONSTRAINT secure_message_files_pkey PRIMARY KEY (id);


--
-- Name: secure_message_otps secure_message_otps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_otps
    ADD CONSTRAINT secure_message_otps_pkey PRIMARY KEY (id);


--
-- Name: secure_messages secure_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_messages
    ADD CONSTRAINT secure_messages_pkey PRIMARY KEY (token);


--
-- Name: threat_actions threat_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_actions
    ADD CONSTRAINT threat_actions_pkey PRIMARY KEY (id);


--
-- Name: threat_config threat_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_config
    ADD CONSTRAINT threat_config_pkey PRIMARY KEY (id);


--
-- Name: idx_comm_flags_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comm_flags_status ON public.comm_flags USING btree (status, created_at DESC);


--
-- Name: idx_custodians_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_custodians_case ON public.case_custodians USING btree (case_id);


--
-- Name: idx_dlp_violations_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dlp_violations_created ON public.dlp_violations USING btree (created_at DESC);


--
-- Name: idx_phish_targets_campaign; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_phish_targets_campaign ON public.phish_targets USING btree (campaign_id);


--
-- Name: idx_safelinks_clicks_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_safelinks_clicks_created ON public.safelinks_clicks USING btree (created_at DESC);


--
-- Name: idx_secure_otp_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_secure_otp_token ON public.secure_message_otps USING btree (token, email);


--
-- Name: idx_threat_actions_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_threat_actions_created ON public.threat_actions USING btree (created_at DESC);


--
-- Name: case_custodians case_custodians_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians
    ADD CONSTRAINT case_custodians_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id) ON DELETE CASCADE;


--
-- Name: case_custodians case_custodians_hold_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_custodians
    ADD CONSTRAINT case_custodians_hold_id_fkey FOREIGN KEY (hold_id) REFERENCES public.legal_holds(id) ON DELETE SET NULL;


--
-- Name: comm_flags comm_flags_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comm_flags
    ADD CONSTRAINT comm_flags_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.comm_policies(id) ON DELETE SET NULL;


--
-- Name: phish_campaigns phish_campaigns_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_campaigns
    ADD CONSTRAINT phish_campaigns_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.phish_templates(id);


--
-- Name: phish_targets phish_targets_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.phish_targets
    ADD CONSTRAINT phish_targets_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.phish_campaigns(id) ON DELETE CASCADE;


--
-- Name: secure_message_files secure_message_files_token_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secure_message_files
    ADD CONSTRAINT secure_message_files_token_fkey FOREIGN KEY (token) REFERENCES public.secure_messages(token) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict w3e437vnpOlF0ES2qW7X2bsz3fGy4GRQqe7KXZeiLxhXwGtr2pZP1xBquJdolrO


-- 2) Datos semilla (plantillas phishing, politicas, configs singleton)
--
-- PostgreSQL database dump
--

\restrict ggALrjgBXAiScojZCERGNF36fXrobE3Dm3R5oAPqY9IzSgYaiTIeVweb0mbdhnb

-- Dumped from database version 17.10 (Debian 17.10-0+deb13u1)
-- Dumped by pg_dump version 17.10 (Debian 17.10-0+deb13u1)

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

--
-- Data for Name: comm_policies; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.comm_policies VALUES (1, 'Lenguaje ofensivo', 'Detecta insultos o lenguaje inapropiado', '["insulto", "estafa", "amenaza"]', 'all', 'alta', false, '2026-06-10 00:09:55.071748+00');
INSERT INTO public.comm_policies VALUES (2, 'Informacion confidencial', 'Terminos marcados como confidenciales por la organizacion', '["confidencial", "no divulgar", "secreto"]', 'outbound', 'media', false, '2026-06-10 00:09:55.175584+00');


--
-- Data for Name: dlp_config; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.dlp_config VALUES (1, true, 'warn', '{"ruc": {"action": null, "enabled": true}, "iban": {"action": null, "enabled": true}, "cedula": {"action": null, "enabled": true}, "cuenta": {"action": null, "enabled": true}, "keyword": {"action": null, "enabled": true}, "tarjeta": {"action": null, "enabled": true}}', '2026-06-09 17:00:34.364302+00');


--
-- Data for Name: phish_templates; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.phish_templates VALUES (1, 'Restablecer contraseña (TI)', '⚠️ Acción requerida: tu contraseña vence hoy', '<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#222">
  <p>Estimado usuario,</p>
  <p>Nuestro sistema detectó que tu contraseña de correo <b>vence hoy</b>. Para evitar la
  suspensión de tu cuenta, debes restablecerla en las próximas 2 horas.</p>
  <p style="text-align:center;margin:24px 0">
    <a href="{{LINK}}" style="background:#0078d4;color:#fff;text-decoration:none;padding:12px 26px;border-radius:5px">Restablecer mi contraseña</a>
  </p>
  <p style="color:#666;font-size:13px">Si no realizas esta acción, tu cuenta será bloqueada.</p>
  <p style="color:#666;font-size:13px">Departamento de Tecnología</p>
  <img src="{{PIXEL}}" width="1" height="1" alt="" />
</div>', 'Soporte TI Maquita', 'soporte-ti@maquita.org', 'media', true, '2026-06-09 19:33:51.974979+00');
INSERT INTO public.phish_templates VALUES (2, 'Documento compartido', 'Te compartieron un documento: «Presupuesto 2026.xlsx»', '<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#222">
  <p>Hola,</p>
  <p>Un compañero compartió contigo un documento a través de la nube de Maquita:</p>
  <p style="background:#f3f3f3;border-radius:6px;padding:12px"><b>📄 Presupuesto 2026.xlsx</b><br>
  <span style="color:#666;font-size:13px">Necesitas iniciar sesión para verlo.</span></p>
  <p style="text-align:center;margin:24px 0">
    <a href="{{LINK}}" style="background:#107c10;color:#fff;text-decoration:none;padding:12px 26px;border-radius:5px">Abrir documento</a>
  </p>
  <p style="color:#666;font-size:13px">Este enlace caduca en 24 horas.</p>
  <img src="{{PIXEL}}" width="1" height="1" alt="" />
</div>', 'Documentos Maquita', 'no-reply@maquita.org', 'alta', true, '2026-06-09 19:33:51.979929+00');
INSERT INTO public.phish_templates VALUES (3, 'Buzón casi lleno', 'Tu buzón está al 98% — libera espacio ahora', '<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#222">
  <p>Estimado usuario,</p>
  <p>Tu buzón de correo está al <b>98% de su capacidad</b>. Cuando llegue al 100% dejarás
  de recibir mensajes. Aumenta tu cuota de forma gratuita:</p>
  <p style="text-align:center;margin:24px 0">
    <a href="{{LINK}}" style="background:#d13438;color:#fff;text-decoration:none;padding:12px 26px;border-radius:5px">Aumentar mi cuota</a>
  </p>
  <p style="color:#666;font-size:13px">Servicio automático de correo. No responder.</p>
  <img src="{{PIXEL}}" width="1" height="1" alt="" />
</div>', 'Sistema de Correo', 'postmaster@maquita.org', 'baja', true, '2026-06-09 19:33:51.98182+00');


--
-- Data for Name: safelinks_config; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.safelinks_config VALUES (1, true, true, true, true, '2026-06-09 17:36:54.31627+00');


--
-- Data for Name: secure_config; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.secure_config VALUES (1, true, 7, 0, '', '2026-06-09 17:13:37.679552+00');


--
-- Data for Name: threat_config; Type: TABLE DATA; Schema: public; Owner: mailserver
--

INSERT INTO public.threat_config VALUES (1, false, false, '2026-06-09 20:21:49.087499+00');


--
-- Name: comm_policies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mailserver
--

SELECT pg_catalog.setval('public.comm_policies_id_seq', 2, true);


--
-- Name: phish_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mailserver
--

SELECT pg_catalog.setval('public.phish_templates_id_seq', 3, true);


--
-- PostgreSQL database dump complete
--

\unrestrict ggALrjgBXAiScojZCERGNF36fXrobE3Dm3R5oAPqY9IzSgYaiTIeVweb0mbdhnb


-- El volcado de arriba deja search_path vacio (linea 1071), asi que todo lo que sigue
-- se ejecutaba sin esquema y fallaba en una instalacion nueva. Se restablece aqui. [C4]
SET search_path TO public;

-- 3) ALTER de tabla existente (firma GPG de exports) — correr como superusuario/postgres
ALTER TABLE ediscovery_exports
  ADD COLUMN IF NOT EXISTS gpg_signature_path TEXT,
  ADD COLUMN IF NOT EXISTS manifest_hash VARCHAR(64),
  ADD COLUMN IF NOT EXISTS timestamp_seal TEXT,
  ADD COLUMN IF NOT EXISTS signed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS gpg_fingerprint VARCHAR(80),
  ADD COLUMN IF NOT EXISTS verified BOOLEAN;
GRANT SELECT, INSERT, UPDATE, DELETE ON ediscovery_exports TO mailserver;

-- 4) Auditoria avanzada: tabla de configuracion de retencion
CREATE TABLE IF NOT EXISTS audit_retention_config (
    id INT PRIMARY KEY DEFAULT 1,
    retention_days INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT audit_retention_singleton CHECK (id = 1)
);
INSERT INTO audit_retention_config (id, retention_days) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;

-- 5) Detección de inicios de sesión riesgosos (cuenta comprometida)
CREATE TABLE IF NOT EXISTS login_events (
    id BIGSERIAL PRIMARY KEY, username VARCHAR(255) NOT NULL, ip VARCHAR(64) NOT NULL DEFAULT '',
    is_internal BOOLEAN NOT NULL DEFAULT false, country VARCHAR(80) NOT NULL DEFAULT '',
    city VARCHAR(120) NOT NULL DEFAULT '', lat REAL, lon REAL, user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_login_events_user ON login_events(username, created_at DESC);
CREATE TABLE IF NOT EXISTS risky_logins (
    id BIGSERIAL PRIMARY KEY, username VARCHAR(255) NOT NULL, ip VARCHAR(64) NOT NULL DEFAULT '',
    country VARCHAR(80) NOT NULL DEFAULT '', city VARCHAR(120) NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '', risk VARCHAR(10) NOT NULL DEFAULT 'medium', distance_km INT,
    status VARCHAR(12) NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risky_logins_created ON risky_logins(created_at DESC);
CREATE TABLE IF NOT EXISTS risky_login_config (
    id INT PRIMARY KEY DEFAULT 1, enabled BOOLEAN NOT NULL DEFAULT true, auto_block BOOLEAN NOT NULL DEFAULT false,
    trusted_countries JSONB NOT NULL DEFAULT '["Ecuador"]'::jsonb,
    occasional_countries JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(), CONSTRAINT risky_login_singleton CHECK (id = 1)
);
INSERT INTO risky_login_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- 6) Inteligencia de amenazas (Safe Links): metadatos de feeds
CREATE TABLE IF NOT EXISTS threat_feed_meta (
    id INT PRIMARY KEY DEFAULT 1, malware_count INT NOT NULL DEFAULT 0, phish_count INT NOT NULL DEFAULT 0,
    sources JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ,
    CONSTRAINT threat_feed_meta_singleton CHECK (id = 1)
);
INSERT INTO threat_feed_meta (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
