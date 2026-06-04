--
-- PostgreSQL database dump
--

\restrict KsJP9eERKumHRynhscLd7gbLcpaHJ7fsAEXlGNY6hdUuT2AmASstxlV6AToUOmh

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
-- Name: merge_quota(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.merge_quota() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            UPDATE quota SET current = NEW.current + current WHERE username = NEW.username AND path = NEW.path;
            IF found THEN
                RETURN NULL;
            ELSE
                RETURN NEW;
            END IF;
      END;
      $$;


--
-- Name: merge_quota2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.merge_quota2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.messages < 0 OR NEW.messages IS NULL THEN
                -- ugly kludge: we came here from this function, really do try to insert
                IF NEW.messages IS NULL THEN
                    NEW.messages = 0;
                ELSE
                    NEW.messages = -NEW.messages;
                END IF;
                return NEW;
            END IF;

            LOOP
                UPDATE quota2 SET bytes = bytes + NEW.bytes,
                    messages = messages + NEW.messages
                    WHERE username = NEW.username;
                IF found THEN
                    RETURN NULL;
                END IF;

                BEGIN
                    IF NEW.messages = 0 THEN
                    INSERT INTO quota2 (bytes, messages, username) VALUES (NEW.bytes, NULL, NEW.username);
                    ELSE
                        INSERT INTO quota2 (bytes, messages, username) VALUES (NEW.bytes, -NEW.messages, NEW.username);
                    END IF;
                    return NULL;
                    EXCEPTION WHEN unique_violation THEN
                    -- someone just inserted the record, update it
                END;
            END LOOP;
        END;
        $$;


--
-- Name: update_contacts_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_contacts_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.admin (
    username character varying(255) NOT NULL,
    password character varying(255) DEFAULT ''::character varying NOT NULL,
    created timestamp with time zone DEFAULT now(),
    modified timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    superadmin boolean DEFAULT false NOT NULL,
    phone character varying(30) DEFAULT ''::character varying NOT NULL,
    email_other character varying(255) DEFAULT ''::character varying NOT NULL,
    token character varying(255) DEFAULT ''::character varying NOT NULL,
    token_validity timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone
);


--
-- Name: admin_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.admin_audit (
    id integer NOT NULL,
    admin_id integer,
    admin_username character varying(255),
    action character varying(100) NOT NULL,
    target character varying(255),
    details jsonb,
    ip_address character varying(45),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: admin_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.admin_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_audit_id_seq OWNED BY public.admin_audit.id;


--
-- Name: admin_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.admin_sessions (
    id integer NOT NULL,
    user_id integer,
    token_hash character varying(512) NOT NULL,
    ip_address character varying(45),
    user_agent text,
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: admin_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.admin_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_sessions_id_seq OWNED BY public.admin_sessions.id;


--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.admin_users (
    id integer NOT NULL,
    username character varying(255) NOT NULL,
    password_hash character varying(512) NOT NULL,
    display_name character varying(255) DEFAULT ''::character varying NOT NULL,
    role character varying(50) DEFAULT 'admin'::character varying NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    last_login timestamp with time zone,
    failed_attempts integer DEFAULT 0,
    locked_until timestamp with time zone
);


--
-- Name: admin_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.admin_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_users_id_seq OWNED BY public.admin_users.id;


--
-- Name: alias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.alias (
    address character varying(255) NOT NULL,
    goto text NOT NULL,
    domain character varying(255) NOT NULL,
    created timestamp with time zone DEFAULT now(),
    modified timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL
);


--
-- Name: alias_domain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.alias_domain (
    alias_domain character varying(255) NOT NULL,
    target_domain character varying(255) NOT NULL,
    created timestamp with time zone DEFAULT now(),
    modified timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL
);


--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.api_keys (
    id integer NOT NULL,
    name text NOT NULL,
    key_hash text NOT NULL,
    prefix text NOT NULL,
    permissions text[] DEFAULT ARRAY['read'::text] NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    last_used_at timestamp without time zone,
    expires_at timestamp without time zone,
    user_email text
);


--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;


--
-- Name: approved_forwards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.approved_forwards (
    id integer NOT NULL,
    username text NOT NULL,
    forward_address text NOT NULL,
    approved_by text NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: approved_forwards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.approved_forwards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: approved_forwards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.approved_forwards_id_seq OWNED BY public.approved_forwards.id;


--
-- Name: attachment_scans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.attachment_scans (
    id integer NOT NULL,
    message_id text,
    filename text NOT NULL,
    content_type text,
    size integer,
    scan_result text DEFAULT 'clean'::text,
    threats_found jsonb DEFAULT '[]'::jsonb,
    scan_details jsonb DEFAULT '{}'::jsonb,
    scanned_at timestamp without time zone DEFAULT now(),
    scanned_by text DEFAULT 'oletools+clamav'::text
);


--
-- Name: attachment_scans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.attachment_scans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attachment_scans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attachment_scans_id_seq OWNED BY public.attachment_scans.id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.audit_log (
    id bigint NOT NULL,
    admin_user character varying(255) NOT NULL,
    action character varying(50) NOT NULL,
    target character varying(255),
    details jsonb,
    ip_address inet,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: branding_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.branding_settings (
    key character varying(100) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: calendar_event_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.calendar_event_attachments (
    id integer NOT NULL,
    event_id uuid NOT NULL,
    filename text NOT NULL,
    content_type text,
    size integer,
    storage_path text NOT NULL,
    uploaded_by text NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: calendar_event_attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.calendar_event_attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calendar_event_attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calendar_event_attachments_id_seq OWNED BY public.calendar_event_attachments.id;


--
-- Name: calendar_shares; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.calendar_shares (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    calendar_id uuid NOT NULL,
    owner_email text NOT NULL,
    shared_with text NOT NULL,
    permission character varying(20) DEFAULT 'read'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calendar_shares_permission_check CHECK (((permission)::text = ANY ((ARRAY['read'::character varying, 'read-write'::character varying])::text[])))
);


--
-- Name: calendars; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.calendars (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_email text NOT NULL,
    name text DEFAULT 'Calendario'::text NOT NULL,
    color text DEFAULT '#0078d4'::text NOT NULL,
    description text DEFAULT ''::text,
    timezone text DEFAULT 'America/Guayaquil'::text NOT NULL,
    radicale_path text DEFAULT ''::text NOT NULL,
    is_default boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: compliance_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.compliance_cases (
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


--
-- Name: compliance_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.compliance_cases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: compliance_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compliance_cases_id_seq OWNED BY public.compliance_cases.id;


--
-- Name: config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.config (
    id integer NOT NULL,
    name character varying(20) NOT NULL,
    value character varying(20) NOT NULL
);


--
-- Name: config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.config_id_seq OWNED BY public.config.id;


--
-- Name: contact_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_audit_log (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    contact_id integer,
    action character varying(30) NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    ip_address character varying(45) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_audit_log_id_seq OWNED BY public.contact_audit_log.id;


--
-- Name: contact_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_categories (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    name character varying(100) NOT NULL,
    color character varying(7) DEFAULT '#0078d4'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_categories_id_seq OWNED BY public.contact_categories.id;


--
-- Name: contact_category_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_category_assignments (
    contact_id integer NOT NULL,
    category_id integer NOT NULL
);


--
-- Name: contact_custom_fields; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_custom_fields (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    field_name character varying(100) NOT NULL,
    field_type character varying(20) DEFAULT 'text'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_custom_fields_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_custom_fields_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_custom_fields_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_custom_fields_id_seq OWNED BY public.contact_custom_fields.id;


--
-- Name: contact_custom_values; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_custom_values (
    id integer NOT NULL,
    contact_id integer NOT NULL,
    field_id integer NOT NULL,
    value text DEFAULT ''::text
);


--
-- Name: contact_custom_values_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_custom_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_custom_values_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_custom_values_id_seq OWNED BY public.contact_custom_values.id;


--
-- Name: contact_list_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_list_members (
    list_id integer NOT NULL,
    contact_id integer NOT NULL,
    added_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_lists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_lists (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    description text DEFAULT ''::text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_lists_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_lists_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_lists_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_lists_id_seq OWNED BY public.contact_lists.id;


--
-- Name: contact_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_relationships (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    from_contact_id integer NOT NULL,
    to_contact_id integer NOT NULL,
    relation_type character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_relationships_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_relationships_id_seq OWNED BY public.contact_relationships.id;


--
-- Name: contact_reminders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_reminders (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    contact_id integer,
    title character varying(255) NOT NULL,
    description text DEFAULT ''::text,
    due_date timestamp with time zone NOT NULL,
    completed boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_reminders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_reminders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_reminders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_reminders_id_seq OWNED BY public.contact_reminders.id;


--
-- Name: contact_shared_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_shared_notes (
    id integer NOT NULL,
    contact_id integer,
    org_contact_id integer,
    author character varying(255) NOT NULL,
    content text NOT NULL,
    tags text[] DEFAULT '{}'::text[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT contact_shared_notes_check CHECK (((contact_id IS NOT NULL) OR (org_contact_id IS NOT NULL)))
);


--
-- Name: contact_shared_notes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_shared_notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_shared_notes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_shared_notes_id_seq OWNED BY public.contact_shared_notes.id;


--
-- Name: contact_signature_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_signature_data (
    id integer NOT NULL,
    contact_id integer NOT NULL,
    field_name character varying(100) NOT NULL,
    field_value text NOT NULL,
    confidence double precision DEFAULT 0.5,
    source_message_id character varying(255) DEFAULT ''::character varying,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_signature_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_signature_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_signature_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_signature_data_id_seq OWNED BY public.contact_signature_data.id;


--
-- Name: contact_sync_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.contact_sync_state (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    contact_id integer NOT NULL,
    etag character varying(255) DEFAULT ''::character varying,
    vcard_uid character varying(255) DEFAULT ''::character varying,
    last_synced timestamp with time zone DEFAULT now(),
    sync_source character varying(50) DEFAULT 'local'::character varying
);


--
-- Name: contact_sync_state_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.contact_sync_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_sync_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_sync_state_id_seq OWNED BY public.contact_sync_state.id;


--
-- Name: corporate_disclaimer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.corporate_disclaimer (
    id integer NOT NULL,
    domain text NOT NULL,
    html_footer text DEFAULT ''::text NOT NULL,
    text_footer text DEFAULT ''::text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: corporate_disclaimer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.corporate_disclaimer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: corporate_disclaimer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.corporate_disclaimer_id_seq OWNED BY public.corporate_disclaimer.id;


--
-- Name: default_signatures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.default_signatures (
    id integer NOT NULL,
    domain character varying(255) NOT NULL,
    name character varying(255) DEFAULT ''::character varying NOT NULL,
    html_template text DEFAULT ''::text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    domain_pattern character varying(255) DEFAULT ''::character varying
);


--
-- Name: default_signatures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.default_signatures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: default_signatures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.default_signatures_id_seq OWNED BY public.default_signatures.id;


--
-- Name: domain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.domain (
    domain character varying(255) NOT NULL,
    description character varying(255) DEFAULT ''::character varying NOT NULL,
    aliases integer DEFAULT 0 NOT NULL,
    mailboxes integer DEFAULT 0 NOT NULL,
    maxquota bigint DEFAULT 0 NOT NULL,
    quota bigint DEFAULT 0 NOT NULL,
    transport character varying(255) DEFAULT NULL::character varying,
    backupmx boolean DEFAULT false NOT NULL,
    created timestamp with time zone DEFAULT now(),
    modified timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    password_expiry integer DEFAULT 0
);


--
-- Name: domain_admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.domain_admins (
    username character varying(255) NOT NULL,
    domain character varying(255) NOT NULL,
    created timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    id integer NOT NULL
);


--
-- Name: domain_admins_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.domain_admins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: domain_admins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.domain_admins_id_seq OWNED BY public.domain_admins.id;


--
-- Name: domains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.domains (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: domains_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: domains_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.domains_id_seq OWNED BY public.domains.id;


--
-- Name: ediscovery_exports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.ediscovery_exports (
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
    exported_at timestamp with time zone DEFAULT now() NOT NULL,
    gpg_signature text,
    timestamp_token text
);


--
-- Name: ediscovery_exports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.ediscovery_exports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ediscovery_exports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ediscovery_exports_id_seq OWNED BY public.ediscovery_exports.id;


--
-- Name: ediscovery_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.ediscovery_results (
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
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    matched_keywords text[]
);


--
-- Name: ediscovery_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.ediscovery_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ediscovery_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ediscovery_results_id_seq OWNED BY public.ediscovery_results.id;


--
-- Name: ediscovery_searches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.ediscovery_searches (
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
    error_message text,
    search_body boolean DEFAULT true,
    search_attachments boolean DEFAULT true
);


--
-- Name: ediscovery_searches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.ediscovery_searches_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ediscovery_searches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ediscovery_searches_id_seq OWNED BY public.ediscovery_searches.id;


--
-- Name: email_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.email_templates (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    category character varying(100) DEFAULT ''::character varying,
    subject character varying(500) DEFAULT ''::character varying,
    html_body text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: email_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.email_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.email_templates_id_seq OWNED BY public.email_templates.id;


--
-- Name: event_invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.event_invitations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    attendee_email text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    sent_at timestamp with time zone,
    responded_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT event_invitations_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'declined'::character varying, 'tentative'::character varying])::text[])))
);


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    calendar_id uuid NOT NULL,
    uid text NOT NULL,
    summary text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text,
    location text DEFAULT ''::text,
    dtstart timestamp with time zone NOT NULL,
    dtend timestamp with time zone NOT NULL,
    all_day boolean DEFAULT false,
    rrule text DEFAULT ''::text,
    status text DEFAULT 'CONFIRMED'::text,
    transparency text DEFAULT 'OPAQUE'::text,
    timezone text DEFAULT 'America/Guayaquil'::text,
    reminders jsonb DEFAULT '[]'::jsonb,
    attendees jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    external_uid text
);


--
-- Name: fetchmail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.fetchmail (
    id integer NOT NULL,
    mailbox character varying(255) DEFAULT ''::character varying NOT NULL,
    src_server character varying(255) DEFAULT ''::character varying NOT NULL,
    src_auth character varying(15) NOT NULL,
    src_user character varying(255) DEFAULT ''::character varying NOT NULL,
    src_password character varying(255) DEFAULT ''::character varying NOT NULL,
    src_folder character varying(255) DEFAULT ''::character varying NOT NULL,
    poll_time integer DEFAULT 10 NOT NULL,
    fetchall boolean DEFAULT false NOT NULL,
    keep boolean DEFAULT false NOT NULL,
    protocol character varying(15) NOT NULL,
    extra_options text,
    returned_text text,
    mda character varying(255) DEFAULT ''::character varying NOT NULL,
    date timestamp with time zone DEFAULT now(),
    usessl boolean DEFAULT false NOT NULL,
    sslcertck boolean DEFAULT false NOT NULL,
    sslcertpath character varying(255) DEFAULT ''::character varying,
    sslfingerprint character varying(255) DEFAULT ''::character varying,
    domain character varying(255) DEFAULT ''::character varying,
    active boolean DEFAULT false NOT NULL,
    created timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    modified timestamp with time zone DEFAULT now(),
    src_port integer DEFAULT 0 NOT NULL,
    CONSTRAINT fetchmail_protocol_check CHECK (((protocol)::text = ANY ((ARRAY['POP3'::character varying, 'IMAP'::character varying, 'POP2'::character varying, 'ETRN'::character varying, 'AUTO'::character varying])::text[]))),
    CONSTRAINT fetchmail_src_auth_check CHECK (((src_auth)::text = ANY ((ARRAY['password'::character varying, 'kerberos_v5'::character varying, 'kerberos'::character varying, 'kerberos_v4'::character varying, 'gssapi'::character varying, 'cram-md5'::character varying, 'otp'::character varying, 'ntlm'::character varying, 'msn'::character varying, 'ssh'::character varying, 'any'::character varying])::text[])))
);


--
-- Name: fetchmail_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.fetchmail_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fetchmail_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fetchmail_id_seq OWNED BY public.fetchmail.id;


--
-- Name: fraud_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.fraud_alerts (
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
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying,
    related_message_id character varying(500),
    related_case_id bigint,
    closed_by character varying(255),
    closed_at timestamp with time zone
);


--
-- Name: fraud_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.fraud_alerts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fraud_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fraud_alerts_id_seq OWNED BY public.fraud_alerts.id;


--
-- Name: import_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.import_jobs (
    id text NOT NULL,
    type text NOT NULL,
    status text DEFAULT 'pending'::text,
    total integer DEFAULT 0,
    processed integer DEFAULT 0,
    errors integer DEFAULT 0,
    error_details jsonb,
    started_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    user_email text
);


--
-- Name: legal_holds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.legal_holds (
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
    is_active boolean DEFAULT true,
    disable_reason text
);


--
-- Name: legal_holds_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.legal_holds_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legal_holds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legal_holds_id_seq OWNED BY public.legal_holds.id;


--
-- Name: log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.log (
    "timestamp" timestamp with time zone DEFAULT now(),
    username character varying(255) DEFAULT ''::character varying NOT NULL,
    domain character varying(255) DEFAULT ''::character varying NOT NULL,
    action character varying(255) DEFAULT ''::character varying NOT NULL,
    data text DEFAULT ''::text NOT NULL,
    id integer NOT NULL
);


--
-- Name: log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_id_seq OWNED BY public.log.id;


--
-- Name: mail_autoresponders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_autoresponders (
    id integer NOT NULL,
    username character varying(255) NOT NULL,
    active boolean DEFAULT false,
    subject character varying(500) DEFAULT 'Fuera de oficina'::character varying NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    start_date date,
    end_date date,
    reply_once_per_day boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    modified_at timestamp with time zone DEFAULT now()
);


--
-- Name: mail_autoresponders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_autoresponders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_autoresponders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_autoresponders_id_seq OWNED BY public.mail_autoresponders.id;


--
-- Name: mail_delegation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_delegation (
    id integer NOT NULL,
    mailbox character varying(255) NOT NULL,
    delegate character varying(255) NOT NULL,
    can_send_as boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: mail_delegation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_delegation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_delegation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_delegation_id_seq OWNED BY public.mail_delegation.id;


--
-- Name: mail_group_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_group_members (
    id integer NOT NULL,
    group_id integer,
    member_email character varying(255) NOT NULL,
    member_name character varying(255) DEFAULT ''::character varying,
    can_send boolean DEFAULT true,
    receive boolean DEFAULT true,
    added_at timestamp with time zone DEFAULT now()
);


--
-- Name: mail_group_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_group_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_group_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_group_members_id_seq OWNED BY public.mail_group_members.id;


--
-- Name: mail_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_groups (
    id integer NOT NULL,
    address character varying(255) NOT NULL,
    name character varying(255) DEFAULT ''::character varying NOT NULL,
    description text DEFAULT ''::text,
    domain character varying(255) NOT NULL,
    active boolean DEFAULT true,
    allow_external boolean DEFAULT false,
    allowed_senders text DEFAULT ''::text,
    created_at timestamp with time zone DEFAULT now(),
    modified_at timestamp with time zone DEFAULT now()
);


--
-- Name: mail_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_groups_id_seq OWNED BY public.mail_groups.id;


--
-- Name: mail_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_log (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    queue_id character varying(20),
    message_id character varying(255),
    from_address character varying(255),
    to_address character varying(255),
    status character varying(20),
    status_detail text,
    size_bytes bigint,
    relay character varying(255),
    delay_seconds double precision,
    source character varying(20),
    hostname character varying(64),
    program character varying(64),
    raw_line text
);


--
-- Name: mail_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_log_id_seq OWNED BY public.mail_log.id;


--
-- Name: mail_signatures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_signatures (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text DEFAULT ''::text,
    html_content text DEFAULT ''::text NOT NULL,
    text_content text DEFAULT ''::text NOT NULL,
    is_default boolean DEFAULT false,
    domain character varying(255) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now(),
    modified_at timestamp with time zone DEFAULT now()
);


--
-- Name: mail_signatures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_signatures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_signatures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_signatures_id_seq OWNED BY public.mail_signatures.id;


--
-- Name: mail_trace; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_trace (
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
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    dovecot_user character varying(255),
    dovecot_folder character varying(255),
    dovecot_event character varying(50),
    delivered_at timestamp with time zone
);


--
-- Name: mail_trace_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_trace_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_trace_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_trace_id_seq OWNED BY public.mail_trace.id;


--
-- Name: mail_user_signatures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mail_user_signatures (
    id integer NOT NULL,
    username character varying(255) NOT NULL,
    signature_id integer,
    custom_html text DEFAULT ''::text,
    custom_name character varying(255) DEFAULT ''::character varying,
    custom_title character varying(255) DEFAULT ''::character varying,
    custom_phone character varying(100) DEFAULT ''::character varying,
    active boolean DEFAULT true
);


--
-- Name: mail_user_signatures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mail_user_signatures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mail_user_signatures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mail_user_signatures_id_seq OWNED BY public.mail_user_signatures.id;


--
-- Name: mailbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mailbox (
    username character varying(255) NOT NULL,
    password character varying(255) DEFAULT ''::character varying NOT NULL,
    name character varying(255) DEFAULT ''::character varying NOT NULL,
    maildir character varying(255) DEFAULT ''::character varying NOT NULL,
    quota bigint DEFAULT 0 NOT NULL,
    created timestamp with time zone DEFAULT now(),
    modified timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    domain character varying(255),
    local_part character varying(255) NOT NULL,
    phone character varying(30) DEFAULT ''::character varying NOT NULL,
    email_other character varying(255) DEFAULT ''::character varying NOT NULL,
    token character varying(255) DEFAULT ''::character varying NOT NULL,
    token_validity timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    password_expiry timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone
);


--
-- Name: meeting_rooms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.meeting_rooms (
    id integer NOT NULL,
    name text NOT NULL,
    email text,
    capacity integer DEFAULT 10,
    location text,
    amenities text[] DEFAULT '{}'::text[],
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: meeting_rooms_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.meeting_rooms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meeting_rooms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meeting_rooms_id_seq OWNED BY public.meeting_rooms.id;


--
-- Name: meetings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.meetings (
    id integer NOT NULL,
    room_id text NOT NULL,
    title text NOT NULL,
    creator_email text NOT NULL,
    meeting_url text NOT NULL,
    start_time timestamp without time zone,
    attendees text[],
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: meetings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.meetings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meetings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meetings_id_seq OWNED BY public.meetings.id;


--
-- Name: message_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.message_labels (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    folder character varying(255) NOT NULL,
    message_uid integer NOT NULL,
    label_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: message_labels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.message_labels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: message_labels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.message_labels_id_seq OWNED BY public.message_labels.id;


--
-- Name: mobile_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.mobile_devices (
    id integer NOT NULL,
    user_email text NOT NULL,
    device_id text NOT NULL,
    device_name text,
    platform text,
    push_token text,
    last_sync timestamp without time zone,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: mobile_devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.mobile_devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mobile_devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mobile_devices_id_seq OWNED BY public.mobile_devices.id;


--
-- Name: nextcloud_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.nextcloud_accounts (
    id integer NOT NULL,
    mail_username character varying(255) NOT NULL,
    nc_userid character varying(255) NOT NULL,
    nc_password character varying(500) NOT NULL,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: nextcloud_accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.nextcloud_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nextcloud_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nextcloud_accounts_id_seq OWNED BY public.nextcloud_accounts.id;


--
-- Name: org_contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.org_contacts (
    id integer NOT NULL,
    domain character varying(255) NOT NULL,
    display_name character varying(255) DEFAULT ''::character varying NOT NULL,
    first_name character varying(100) DEFAULT ''::character varying,
    last_name character varying(100) DEFAULT ''::character varying,
    email character varying(255) NOT NULL,
    phone character varying(50) DEFAULT ''::character varying,
    phone_mobile character varying(50) DEFAULT ''::character varying,
    job_title character varying(200) DEFAULT ''::character varying,
    department character varying(200) DEFAULT ''::character varying,
    company character varying(255) DEFAULT ''::character varying,
    address_street text DEFAULT ''::text,
    address_city character varying(100) DEFAULT ''::character varying,
    address_state character varying(100) DEFAULT ''::character varying,
    address_zip character varying(20) DEFAULT ''::character varying,
    address_country character varying(100) DEFAULT ''::character varying,
    photo_url character varying(500) DEFAULT ''::character varying,
    notes text DEFAULT ''::text,
    created_by character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: org_contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.org_contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: org_contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.org_contacts_id_seq OWNED BY public.org_contacts.id;


--
-- Name: priority_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.priority_cache (
    id integer NOT NULL,
    owner text NOT NULL,
    folder text NOT NULL,
    message_uid integer NOT NULL,
    priority text DEFAULT 'normal'::text NOT NULL,
    category text DEFAULT 'other'::text NOT NULL,
    confidence real DEFAULT 0.5,
    reason text DEFAULT ''::text,
    classified_at timestamp with time zone DEFAULT now()
);


--
-- Name: priority_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.priority_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: priority_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.priority_cache_id_seq OWNED BY public.priority_cache.id;


--
-- Name: quota; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.quota (
    username character varying(255) NOT NULL,
    path character varying(100) NOT NULL,
    current bigint DEFAULT 0 NOT NULL
);


--
-- Name: quota2; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.quota2 (
    username character varying(100) NOT NULL,
    bytes bigint DEFAULT 0 NOT NULL,
    messages integer DEFAULT 0 NOT NULL
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.refresh_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying(255) NOT NULL,
    token_hash character varying(128) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    user_agent text,
    ip_address inet,
    is_revoked boolean DEFAULT false
);


--
-- Name: retention_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.retention_policies (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    target text DEFAULT 'all'::text NOT NULL,
    folder_pattern text DEFAULT '*'::text,
    max_age_days integer NOT NULL,
    action text DEFAULT 'delete'::text,
    move_to text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    last_run timestamp without time zone,
    messages_affected integer DEFAULT 0
);


--
-- Name: retention_policies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.retention_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: retention_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.retention_policies_id_seq OWNED BY public.retention_policies.id;


--
-- Name: room_bookings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.room_bookings (
    id integer NOT NULL,
    room_id integer,
    event_id integer,
    user_email text NOT NULL,
    title text NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    status text DEFAULT 'confirmed'::text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: room_bookings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.room_bookings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: room_bookings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.room_bookings_id_seq OWNED BY public.room_bookings.id;


--
-- Name: scheduled_emails; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.scheduled_emails (
    id integer NOT NULL,
    username text NOT NULL,
    to_list jsonb DEFAULT '[]'::jsonb NOT NULL,
    cc_list jsonb DEFAULT '[]'::jsonb NOT NULL,
    bcc_list jsonb DEFAULT '[]'::jsonb NOT NULL,
    subject text DEFAULT ''::text NOT NULL,
    html_body text DEFAULT ''::text NOT NULL,
    text_body text DEFAULT ''::text NOT NULL,
    in_reply_to text DEFAULT ''::text NOT NULL,
    "references" text DEFAULT ''::text NOT NULL,
    scheduled_at timestamp with time zone NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    request_read_receipt boolean DEFAULT false NOT NULL,
    request_delivery_receipt boolean DEFAULT false NOT NULL
);


--
-- Name: scheduled_emails_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.scheduled_emails_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scheduled_emails_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scheduled_emails_id_seq OWNED BY public.scheduled_emails.id;


--
-- Name: sent_recipients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.sent_recipients (
    id integer NOT NULL,
    sender character varying(255) NOT NULL,
    recipient_email character varying(255) NOT NULL,
    recipient_name character varying(255) DEFAULT ''::character varying,
    last_sent_at timestamp without time zone DEFAULT now()
);


--
-- Name: sent_recipients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.sent_recipients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sent_recipients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sent_recipients_id_seq OWNED BY public.sent_recipients.id;


--
-- Name: signature_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.signature_audit_log (
    id integer NOT NULL,
    username character varying(255) NOT NULL,
    action character varying(50) NOT NULL,
    signature_id integer,
    signature_name character varying(255),
    old_html text,
    new_html text,
    ip_address character varying(45),
    user_agent text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: signature_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.signature_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signature_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signature_audit_log_id_seq OWNED BY public.signature_audit_log.id;


--
-- Name: smime_certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.smime_certificates (
    id integer NOT NULL,
    user_email text NOT NULL,
    certificate_pem text NOT NULL,
    private_key_encrypted text,
    issuer text,
    subject text,
    serial_number text,
    valid_from timestamp without time zone,
    valid_to timestamp without time zone,
    fingerprint text,
    is_private boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: smime_certificates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.smime_certificates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: smime_certificates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.smime_certificates_id_seq OWNED BY public.smime_certificates.id;


--
-- Name: snoozed_emails; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.snoozed_emails (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    original_folder character varying(255) NOT NULL,
    original_uid integer NOT NULL,
    snoozed_uid integer,
    snooze_until timestamp without time zone NOT NULL,
    subject character varying(500),
    from_addr character varying(255),
    created_at timestamp without time zone DEFAULT now(),
    restored boolean DEFAULT false
);


--
-- Name: snoozed_emails_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.snoozed_emails_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: snoozed_emails_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.snoozed_emails_id_seq OWNED BY public.snoozed_emails.id;


--
-- Name: sogo_mailbox_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.sogo_mailbox_view AS
 SELECT username AS c_uid,
    username AS c_name,
    (replace((password)::text, '{SHA512-CRYPT}'::text, ''::text))::character varying(255) AS c_password,
    name AS c_cn,
    username AS mail,
    domain
   FROM public.mailbox
  WHERE (active = true);


--
-- Name: spam_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.spam_analysis (
    id integer NOT NULL,
    owner text NOT NULL,
    folder text NOT NULL,
    message_uid integer NOT NULL,
    is_spam boolean DEFAULT false NOT NULL,
    spam_score integer DEFAULT 0 NOT NULL,
    method text DEFAULT 'heuristic'::text NOT NULL,
    reasons text[] DEFAULT ARRAY[]::text[],
    analyzed_at timestamp with time zone DEFAULT now(),
    user_override text
);


--
-- Name: spam_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.spam_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: spam_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.spam_analysis_id_seq OWNED BY public.spam_analysis.id;


--
-- Name: sso_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.sso_config (
    id integer NOT NULL,
    provider text DEFAULT (((((chr(39) || chr(115)) || chr(97)) || chr(109)) || chr(108)) || chr(39)) NOT NULL,
    entity_id text,
    sso_url text,
    slo_url text,
    certificate text,
    is_active boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: sso_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.sso_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sso_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sso_config_id_seq OWNED BY public.sso_config.id;


--
-- Name: task_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_activity (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    board_id uuid NOT NULL,
    card_id uuid,
    user_email text NOT NULL,
    action text NOT NULL,
    details text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: task_board_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_board_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    board_id uuid NOT NULL,
    user_email text NOT NULL,
    role text DEFAULT 'member'::text NOT NULL,
    invited_by text NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT task_board_members_role_check CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text])))
);


--
-- Name: task_boards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_boards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "user" text NOT NULL,
    name text NOT NULL,
    color text DEFAULT '#0078d4'::text NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: task_cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_cards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    list_id uuid NOT NULL,
    title text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    due_date timestamp with time zone,
    priority text DEFAULT 'medium'::text NOT NULL,
    labels jsonb DEFAULT '[]'::jsonb NOT NULL,
    completed boolean DEFAULT false NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    assigned_to text,
    created_by text DEFAULT ''::text NOT NULL,
    completed_by text,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    important boolean DEFAULT false NOT NULL,
    my_day boolean DEFAULT false NOT NULL,
    reminder timestamp with time zone,
    note text DEFAULT ''::text NOT NULL,
    recurrence text,
    CONSTRAINT task_cards_priority_check CHECK ((priority = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'urgent'::text])))
);


--
-- Name: task_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_labels (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    board_id uuid NOT NULL,
    name text NOT NULL,
    color text DEFAULT '#0078d4'::text NOT NULL
);


--
-- Name: task_lists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_lists (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    board_id uuid NOT NULL,
    name text NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    color text DEFAULT '#e0e0e0'::text NOT NULL,
    list_type text DEFAULT 'custom'::text NOT NULL,
    icon text DEFAULT ''::text NOT NULL,
    owner text DEFAULT ''::text NOT NULL
);


--
-- Name: task_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.task_steps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    card_id uuid NOT NULL,
    title text NOT NULL,
    completed boolean DEFAULT false NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_activity_log (
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


--
-- Name: user_activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_activity_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_activity_log_id_seq OWNED BY public.user_activity_log.id;


--
-- Name: user_contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_contacts (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    display_name character varying(255) DEFAULT ''::character varying,
    email character varying(255) NOT NULL,
    phone character varying(50) DEFAULT ''::character varying,
    organization character varying(255) DEFAULT ''::character varying,
    notes text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    first_name character varying(100) DEFAULT ''::character varying,
    last_name character varying(100) DEFAULT ''::character varying,
    nickname character varying(100) DEFAULT ''::character varying,
    job_title character varying(200) DEFAULT ''::character varying,
    department character varying(200) DEFAULT ''::character varying,
    company character varying(255) DEFAULT ''::character varying,
    email2 character varying(255) DEFAULT ''::character varying,
    email3 character varying(255) DEFAULT ''::character varying,
    phone_mobile character varying(50) DEFAULT ''::character varying,
    phone_work character varying(50) DEFAULT ''::character varying,
    phone_home character varying(50) DEFAULT ''::character varying,
    fax character varying(50) DEFAULT ''::character varying,
    address_street text DEFAULT ''::text,
    address_city character varying(100) DEFAULT ''::character varying,
    address_state character varying(100) DEFAULT ''::character varying,
    address_zip character varying(20) DEFAULT ''::character varying,
    address_country character varying(100) DEFAULT ''::character varying,
    birthday date,
    website character varying(500) DEFAULT ''::character varying,
    im_address character varying(255) DEFAULT ''::character varying,
    photo_url character varying(500) DEFAULT ''::character varying,
    is_favorite boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    source character varying(20) DEFAULT 'manual'::character varying,
    last_contacted_at timestamp with time zone,
    usage_count integer DEFAULT 0 NOT NULL,
    contact_score integer DEFAULT 0
);


--
-- Name: user_contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_contacts_id_seq OWNED BY public.user_contacts.id;


--
-- Name: user_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_identities (
    id integer NOT NULL,
    username character varying(255) NOT NULL,
    display_name character varying(255) DEFAULT ''::character varying,
    email character varying(255) NOT NULL,
    signature_html text DEFAULT ''::text,
    is_default boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: user_identities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_identities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_identities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_identities_id_seq OWNED BY public.user_identities.id;


--
-- Name: user_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_labels (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    name character varying(100) NOT NULL,
    color character varying(7) DEFAULT '#0078d4'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: user_labels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_labels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_labels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_labels_id_seq OWNED BY public.user_labels.id;


--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_preferences (
    username character varying(255) NOT NULL,
    display_name character varying(255) DEFAULT ''::character varying,
    signature_html text DEFAULT ''::text,
    messages_per_page integer DEFAULT 50,
    theme character varying(20) DEFAULT 'light'::character varying,
    language character varying(10) DEFAULT 'es'::character varying,
    timezone character varying(50) DEFAULT 'America/Guayaquil'::character varying,
    date_format character varying(20) DEFAULT 'dd/MM/yyyy'::character varying,
    reading_pane character varying(10) DEFAULT 'right'::character varying,
    list_density character varying(10) DEFAULT 'normal'::character varying,
    block_remote_images boolean DEFAULT true,
    confirm_delete boolean DEFAULT true,
    auto_reply_enabled boolean DEFAULT false,
    auto_reply_subject character varying(255) DEFAULT ''::character varying,
    auto_reply_body text DEFAULT ''::text,
    auto_reply_start timestamp with time zone,
    auto_reply_end timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id integer NOT NULL,
    user_email text NOT NULL,
    display_name text,
    title text,
    department text,
    phone text,
    mobile text,
    office_location text,
    photo_url text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_profiles_id_seq OWNED BY public.user_profiles.id;


--
-- Name: user_signatures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_signatures (
    id integer NOT NULL,
    owner character varying(255) NOT NULL,
    name character varying(255) DEFAULT 'Principal'::character varying NOT NULL,
    html_content text DEFAULT ''::text,
    is_default boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: user_signatures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.user_signatures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_signatures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_signatures_id_seq OWNED BY public.user_signatures.id;


--
-- Name: user_totp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.user_totp (
    username text NOT NULL,
    secret text NOT NULL,
    enabled boolean DEFAULT false,
    backup_codes text[] DEFAULT '{}'::text[],
    created_at timestamp with time zone DEFAULT now(),
    verified_at timestamp with time zone
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.users (
    id integer NOT NULL,
    domain_id integer,
    email character varying(255) NOT NULL,
    password character varying(255) NOT NULL,
    name character varying(255),
    quota bigint DEFAULT 0,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vacation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.vacation (
    email character varying(255) NOT NULL,
    subject character varying(255) NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    created timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    domain character varying(255),
    modified timestamp with time zone DEFAULT now(),
    activefrom timestamp with time zone DEFAULT '2000-01-01 00:00:00+00'::timestamp with time zone,
    activeuntil timestamp with time zone DEFAULT '2038-01-18 00:00:00+00'::timestamp with time zone,
    interval_time integer DEFAULT 0 NOT NULL
);


--
-- Name: vacation_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.vacation_notification (
    on_vacation character varying(255) NOT NULL,
    notified character varying(255) NOT NULL,
    notified_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: webhook_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.webhook_logs (
    id integer NOT NULL,
    webhook_id integer,
    event text NOT NULL,
    payload jsonb,
    response_status integer,
    response_body text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: webhook_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.webhook_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhook_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_logs_id_seq OWNED BY public.webhook_logs.id;


--
-- Name: webhooks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.webhooks (
    id integer NOT NULL,
    url text NOT NULL,
    secret text NOT NULL,
    events text[] DEFAULT ARRAY[]::text[] NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    last_triggered_at timestamp without time zone,
    failure_count integer DEFAULT 0,
    user_email text
);


--
-- Name: webhooks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.webhooks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhooks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhooks_id_seq OWNED BY public.webhooks.id;


--
-- Name: admin_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit ALTER COLUMN id SET DEFAULT nextval('public.admin_audit_id_seq'::regclass);


--
-- Name: admin_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_sessions ALTER COLUMN id SET DEFAULT nextval('public.admin_sessions_id_seq'::regclass);


--
-- Name: admin_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users ALTER COLUMN id SET DEFAULT nextval('public.admin_users_id_seq'::regclass);


--
-- Name: api_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);


--
-- Name: approved_forwards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approved_forwards ALTER COLUMN id SET DEFAULT nextval('public.approved_forwards_id_seq'::regclass);


--
-- Name: attachment_scans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_scans ALTER COLUMN id SET DEFAULT nextval('public.attachment_scans_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: calendar_event_attachments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_event_attachments ALTER COLUMN id SET DEFAULT nextval('public.calendar_event_attachments_id_seq'::regclass);


--
-- Name: compliance_cases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_cases ALTER COLUMN id SET DEFAULT nextval('public.compliance_cases_id_seq'::regclass);


--
-- Name: config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config ALTER COLUMN id SET DEFAULT nextval('public.config_id_seq'::regclass);


--
-- Name: contact_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_audit_log ALTER COLUMN id SET DEFAULT nextval('public.contact_audit_log_id_seq'::regclass);


--
-- Name: contact_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_categories ALTER COLUMN id SET DEFAULT nextval('public.contact_categories_id_seq'::regclass);


--
-- Name: contact_custom_fields id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_fields ALTER COLUMN id SET DEFAULT nextval('public.contact_custom_fields_id_seq'::regclass);


--
-- Name: contact_custom_values id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_values ALTER COLUMN id SET DEFAULT nextval('public.contact_custom_values_id_seq'::regclass);


--
-- Name: contact_lists id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_lists ALTER COLUMN id SET DEFAULT nextval('public.contact_lists_id_seq'::regclass);


--
-- Name: contact_relationships id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_relationships ALTER COLUMN id SET DEFAULT nextval('public.contact_relationships_id_seq'::regclass);


--
-- Name: contact_reminders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_reminders ALTER COLUMN id SET DEFAULT nextval('public.contact_reminders_id_seq'::regclass);


--
-- Name: contact_shared_notes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_shared_notes ALTER COLUMN id SET DEFAULT nextval('public.contact_shared_notes_id_seq'::regclass);


--
-- Name: contact_signature_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_signature_data ALTER COLUMN id SET DEFAULT nextval('public.contact_signature_data_id_seq'::regclass);


--
-- Name: contact_sync_state id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_sync_state ALTER COLUMN id SET DEFAULT nextval('public.contact_sync_state_id_seq'::regclass);


--
-- Name: corporate_disclaimer id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_disclaimer ALTER COLUMN id SET DEFAULT nextval('public.corporate_disclaimer_id_seq'::regclass);


--
-- Name: default_signatures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.default_signatures ALTER COLUMN id SET DEFAULT nextval('public.default_signatures_id_seq'::regclass);


--
-- Name: domain_admins id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domain_admins ALTER COLUMN id SET DEFAULT nextval('public.domain_admins_id_seq'::regclass);


--
-- Name: domains id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains ALTER COLUMN id SET DEFAULT nextval('public.domains_id_seq'::regclass);


--
-- Name: ediscovery_exports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_exports ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_exports_id_seq'::regclass);


--
-- Name: ediscovery_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_results ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_results_id_seq'::regclass);


--
-- Name: ediscovery_searches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_searches ALTER COLUMN id SET DEFAULT nextval('public.ediscovery_searches_id_seq'::regclass);


--
-- Name: email_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_templates ALTER COLUMN id SET DEFAULT nextval('public.email_templates_id_seq'::regclass);


--
-- Name: fetchmail id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fetchmail ALTER COLUMN id SET DEFAULT nextval('public.fetchmail_id_seq'::regclass);


--
-- Name: fraud_alerts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_alerts ALTER COLUMN id SET DEFAULT nextval('public.fraud_alerts_id_seq'::regclass);


--
-- Name: legal_holds id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_holds ALTER COLUMN id SET DEFAULT nextval('public.legal_holds_id_seq'::regclass);


--
-- Name: log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log ALTER COLUMN id SET DEFAULT nextval('public.log_id_seq'::regclass);


--
-- Name: mail_autoresponders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_autoresponders ALTER COLUMN id SET DEFAULT nextval('public.mail_autoresponders_id_seq'::regclass);


--
-- Name: mail_delegation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_delegation ALTER COLUMN id SET DEFAULT nextval('public.mail_delegation_id_seq'::regclass);


--
-- Name: mail_group_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_group_members ALTER COLUMN id SET DEFAULT nextval('public.mail_group_members_id_seq'::regclass);


--
-- Name: mail_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_groups ALTER COLUMN id SET DEFAULT nextval('public.mail_groups_id_seq'::regclass);


--
-- Name: mail_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_log ALTER COLUMN id SET DEFAULT nextval('public.mail_log_id_seq'::regclass);


--
-- Name: mail_signatures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_signatures ALTER COLUMN id SET DEFAULT nextval('public.mail_signatures_id_seq'::regclass);


--
-- Name: mail_trace id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_trace ALTER COLUMN id SET DEFAULT nextval('public.mail_trace_id_seq'::regclass);


--
-- Name: mail_user_signatures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_user_signatures ALTER COLUMN id SET DEFAULT nextval('public.mail_user_signatures_id_seq'::regclass);


--
-- Name: meeting_rooms id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_rooms ALTER COLUMN id SET DEFAULT nextval('public.meeting_rooms_id_seq'::regclass);


--
-- Name: meetings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meetings ALTER COLUMN id SET DEFAULT nextval('public.meetings_id_seq'::regclass);


--
-- Name: message_labels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_labels ALTER COLUMN id SET DEFAULT nextval('public.message_labels_id_seq'::regclass);


--
-- Name: mobile_devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mobile_devices ALTER COLUMN id SET DEFAULT nextval('public.mobile_devices_id_seq'::regclass);


--
-- Name: nextcloud_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nextcloud_accounts ALTER COLUMN id SET DEFAULT nextval('public.nextcloud_accounts_id_seq'::regclass);


--
-- Name: org_contacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_contacts ALTER COLUMN id SET DEFAULT nextval('public.org_contacts_id_seq'::regclass);


--
-- Name: priority_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.priority_cache ALTER COLUMN id SET DEFAULT nextval('public.priority_cache_id_seq'::regclass);


--
-- Name: retention_policies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retention_policies ALTER COLUMN id SET DEFAULT nextval('public.retention_policies_id_seq'::regclass);


--
-- Name: room_bookings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_bookings ALTER COLUMN id SET DEFAULT nextval('public.room_bookings_id_seq'::regclass);


--
-- Name: scheduled_emails id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_emails ALTER COLUMN id SET DEFAULT nextval('public.scheduled_emails_id_seq'::regclass);


--
-- Name: sent_recipients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sent_recipients ALTER COLUMN id SET DEFAULT nextval('public.sent_recipients_id_seq'::regclass);


--
-- Name: signature_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log ALTER COLUMN id SET DEFAULT nextval('public.signature_audit_log_id_seq'::regclass);


--
-- Name: smime_certificates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.smime_certificates ALTER COLUMN id SET DEFAULT nextval('public.smime_certificates_id_seq'::regclass);


--
-- Name: snoozed_emails id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snoozed_emails ALTER COLUMN id SET DEFAULT nextval('public.snoozed_emails_id_seq'::regclass);


--
-- Name: spam_analysis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spam_analysis ALTER COLUMN id SET DEFAULT nextval('public.spam_analysis_id_seq'::regclass);


--
-- Name: sso_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_config ALTER COLUMN id SET DEFAULT nextval('public.sso_config_id_seq'::regclass);


--
-- Name: user_activity_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_activity_log ALTER COLUMN id SET DEFAULT nextval('public.user_activity_log_id_seq'::regclass);


--
-- Name: user_contacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_contacts ALTER COLUMN id SET DEFAULT nextval('public.user_contacts_id_seq'::regclass);


--
-- Name: user_identities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities ALTER COLUMN id SET DEFAULT nextval('public.user_identities_id_seq'::regclass);


--
-- Name: user_labels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_labels ALTER COLUMN id SET DEFAULT nextval('public.user_labels_id_seq'::regclass);


--
-- Name: user_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles ALTER COLUMN id SET DEFAULT nextval('public.user_profiles_id_seq'::regclass);


--
-- Name: user_signatures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_signatures ALTER COLUMN id SET DEFAULT nextval('public.user_signatures_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: webhook_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_logs ALTER COLUMN id SET DEFAULT nextval('public.webhook_logs_id_seq'::regclass);


--
-- Name: webhooks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhooks ALTER COLUMN id SET DEFAULT nextval('public.webhooks_id_seq'::regclass);


--
-- Name: admin_audit admin_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit
    ADD CONSTRAINT admin_audit_pkey PRIMARY KEY (id);


--
-- Name: admin admin_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin
    ADD CONSTRAINT admin_key PRIMARY KEY (username);


--
-- Name: admin_sessions admin_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_sessions
    ADD CONSTRAINT admin_sessions_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_username_key UNIQUE (username);


--
-- Name: alias_domain alias_domain_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alias_domain
    ADD CONSTRAINT alias_domain_pkey PRIMARY KEY (alias_domain);


--
-- Name: alias alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alias
    ADD CONSTRAINT alias_key PRIMARY KEY (address);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: approved_forwards approved_forwards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approved_forwards
    ADD CONSTRAINT approved_forwards_pkey PRIMARY KEY (id);


--
-- Name: approved_forwards approved_forwards_username_forward_address_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approved_forwards
    ADD CONSTRAINT approved_forwards_username_forward_address_key UNIQUE (username, forward_address);


--
-- Name: attachment_scans attachment_scans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_scans
    ADD CONSTRAINT attachment_scans_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: branding_settings branding_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branding_settings
    ADD CONSTRAINT branding_settings_pkey PRIMARY KEY (key);


--
-- Name: calendar_event_attachments calendar_event_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_event_attachments
    ADD CONSTRAINT calendar_event_attachments_pkey PRIMARY KEY (id);


--
-- Name: calendar_shares calendar_shares_calendar_id_shared_with_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_shares
    ADD CONSTRAINT calendar_shares_calendar_id_shared_with_key UNIQUE (calendar_id, shared_with);


--
-- Name: calendar_shares calendar_shares_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_shares
    ADD CONSTRAINT calendar_shares_pkey PRIMARY KEY (id);


--
-- Name: calendars calendars_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendars
    ADD CONSTRAINT calendars_pkey PRIMARY KEY (id);


--
-- Name: compliance_cases compliance_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_cases
    ADD CONSTRAINT compliance_cases_pkey PRIMARY KEY (id);


--
-- Name: config config_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config
    ADD CONSTRAINT config_name_key UNIQUE (name);


--
-- Name: config config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config
    ADD CONSTRAINT config_pkey PRIMARY KEY (id);


--
-- Name: contact_audit_log contact_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_audit_log
    ADD CONSTRAINT contact_audit_log_pkey PRIMARY KEY (id);


--
-- Name: contact_categories contact_categories_owner_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_categories
    ADD CONSTRAINT contact_categories_owner_name_key UNIQUE (owner, name);


--
-- Name: contact_categories contact_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_categories
    ADD CONSTRAINT contact_categories_pkey PRIMARY KEY (id);


--
-- Name: contact_category_assignments contact_category_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_category_assignments
    ADD CONSTRAINT contact_category_assignments_pkey PRIMARY KEY (contact_id, category_id);


--
-- Name: contact_custom_fields contact_custom_fields_owner_field_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_fields
    ADD CONSTRAINT contact_custom_fields_owner_field_name_key UNIQUE (owner, field_name);


--
-- Name: contact_custom_fields contact_custom_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_fields
    ADD CONSTRAINT contact_custom_fields_pkey PRIMARY KEY (id);


--
-- Name: contact_custom_values contact_custom_values_contact_id_field_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_values
    ADD CONSTRAINT contact_custom_values_contact_id_field_id_key UNIQUE (contact_id, field_id);


--
-- Name: contact_custom_values contact_custom_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_values
    ADD CONSTRAINT contact_custom_values_pkey PRIMARY KEY (id);


--
-- Name: contact_list_members contact_list_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_list_members
    ADD CONSTRAINT contact_list_members_pkey PRIMARY KEY (list_id, contact_id);


--
-- Name: contact_lists contact_lists_owner_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_lists
    ADD CONSTRAINT contact_lists_owner_name_key UNIQUE (owner, name);


--
-- Name: contact_lists contact_lists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_lists
    ADD CONSTRAINT contact_lists_pkey PRIMARY KEY (id);


--
-- Name: contact_relationships contact_relationships_from_contact_id_to_contact_id_relatio_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_relationships
    ADD CONSTRAINT contact_relationships_from_contact_id_to_contact_id_relatio_key UNIQUE (from_contact_id, to_contact_id, relation_type);


--
-- Name: contact_relationships contact_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_relationships
    ADD CONSTRAINT contact_relationships_pkey PRIMARY KEY (id);


--
-- Name: contact_reminders contact_reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_reminders
    ADD CONSTRAINT contact_reminders_pkey PRIMARY KEY (id);


--
-- Name: contact_shared_notes contact_shared_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_shared_notes
    ADD CONSTRAINT contact_shared_notes_pkey PRIMARY KEY (id);


--
-- Name: contact_signature_data contact_signature_data_contact_id_field_name_field_value_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_signature_data
    ADD CONSTRAINT contact_signature_data_contact_id_field_name_field_value_key UNIQUE (contact_id, field_name, field_value);


--
-- Name: contact_signature_data contact_signature_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_signature_data
    ADD CONSTRAINT contact_signature_data_pkey PRIMARY KEY (id);


--
-- Name: contact_sync_state contact_sync_state_owner_contact_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_sync_state
    ADD CONSTRAINT contact_sync_state_owner_contact_id_key UNIQUE (owner, contact_id);


--
-- Name: contact_sync_state contact_sync_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_sync_state
    ADD CONSTRAINT contact_sync_state_pkey PRIMARY KEY (id);


--
-- Name: corporate_disclaimer corporate_disclaimer_domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_disclaimer
    ADD CONSTRAINT corporate_disclaimer_domain_key UNIQUE (domain);


--
-- Name: corporate_disclaimer corporate_disclaimer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_disclaimer
    ADD CONSTRAINT corporate_disclaimer_pkey PRIMARY KEY (id);


--
-- Name: default_signatures default_signatures_domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.default_signatures
    ADD CONSTRAINT default_signatures_domain_key UNIQUE (domain);


--
-- Name: default_signatures default_signatures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.default_signatures
    ADD CONSTRAINT default_signatures_pkey PRIMARY KEY (id);


--
-- Name: domain_admins domain_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domain_admins
    ADD CONSTRAINT domain_admins_pkey PRIMARY KEY (id);


--
-- Name: domain domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domain
    ADD CONSTRAINT domain_key PRIMARY KEY (domain);


--
-- Name: domains domains_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_name_key UNIQUE (name);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (id);


--
-- Name: ediscovery_exports ediscovery_exports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_pkey PRIMARY KEY (id);


--
-- Name: ediscovery_results ediscovery_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_results
    ADD CONSTRAINT ediscovery_results_pkey PRIMARY KEY (id);


--
-- Name: ediscovery_searches ediscovery_searches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_searches
    ADD CONSTRAINT ediscovery_searches_pkey PRIMARY KEY (id);


--
-- Name: email_templates email_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_templates
    ADD CONSTRAINT email_templates_pkey PRIMARY KEY (id);


--
-- Name: event_invitations event_invitations_event_id_attendee_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_invitations
    ADD CONSTRAINT event_invitations_event_id_attendee_email_key UNIQUE (event_id, attendee_email);


--
-- Name: event_invitations event_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_invitations
    ADD CONSTRAINT event_invitations_pkey PRIMARY KEY (id);


--
-- Name: events events_calendar_id_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_calendar_id_uid_key UNIQUE (calendar_id, uid);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: fetchmail fetchmail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fetchmail
    ADD CONSTRAINT fetchmail_pkey PRIMARY KEY (id);


--
-- Name: fraud_alerts fraud_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_alerts
    ADD CONSTRAINT fraud_alerts_pkey PRIMARY KEY (id);


--
-- Name: import_jobs import_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_jobs
    ADD CONSTRAINT import_jobs_pkey PRIMARY KEY (id);


--
-- Name: legal_holds legal_holds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_holds
    ADD CONSTRAINT legal_holds_pkey PRIMARY KEY (id);


--
-- Name: log log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log
    ADD CONSTRAINT log_pkey PRIMARY KEY (id);


--
-- Name: mail_autoresponders mail_autoresponders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_autoresponders
    ADD CONSTRAINT mail_autoresponders_pkey PRIMARY KEY (id);


--
-- Name: mail_autoresponders mail_autoresponders_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_autoresponders
    ADD CONSTRAINT mail_autoresponders_username_key UNIQUE (username);


--
-- Name: mail_delegation mail_delegation_mailbox_delegate_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_delegation
    ADD CONSTRAINT mail_delegation_mailbox_delegate_key UNIQUE (mailbox, delegate);


--
-- Name: mail_delegation mail_delegation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_delegation
    ADD CONSTRAINT mail_delegation_pkey PRIMARY KEY (id);


--
-- Name: mail_group_members mail_group_members_group_id_member_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_group_members
    ADD CONSTRAINT mail_group_members_group_id_member_email_key UNIQUE (group_id, member_email);


--
-- Name: mail_group_members mail_group_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_group_members
    ADD CONSTRAINT mail_group_members_pkey PRIMARY KEY (id);


--
-- Name: mail_groups mail_groups_address_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_groups
    ADD CONSTRAINT mail_groups_address_key UNIQUE (address);


--
-- Name: mail_groups mail_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_groups
    ADD CONSTRAINT mail_groups_pkey PRIMARY KEY (id);


--
-- Name: mail_log mail_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_log
    ADD CONSTRAINT mail_log_pkey PRIMARY KEY (id);


--
-- Name: mail_signatures mail_signatures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_signatures
    ADD CONSTRAINT mail_signatures_pkey PRIMARY KEY (id);


--
-- Name: mail_trace mail_trace_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_trace
    ADD CONSTRAINT mail_trace_pkey PRIMARY KEY (id);


--
-- Name: mail_user_signatures mail_user_signatures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_user_signatures
    ADD CONSTRAINT mail_user_signatures_pkey PRIMARY KEY (id);


--
-- Name: mail_user_signatures mail_user_signatures_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_user_signatures
    ADD CONSTRAINT mail_user_signatures_username_key UNIQUE (username);


--
-- Name: mailbox mailbox_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mailbox
    ADD CONSTRAINT mailbox_key PRIMARY KEY (username);


--
-- Name: meeting_rooms meeting_rooms_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_rooms
    ADD CONSTRAINT meeting_rooms_email_key UNIQUE (email);


--
-- Name: meeting_rooms meeting_rooms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_rooms
    ADD CONSTRAINT meeting_rooms_pkey PRIMARY KEY (id);


--
-- Name: meetings meetings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT meetings_pkey PRIMARY KEY (id);


--
-- Name: message_labels message_labels_owner_folder_message_uid_label_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_labels
    ADD CONSTRAINT message_labels_owner_folder_message_uid_label_id_key UNIQUE (owner, folder, message_uid, label_id);


--
-- Name: message_labels message_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_labels
    ADD CONSTRAINT message_labels_pkey PRIMARY KEY (id);


--
-- Name: mobile_devices mobile_devices_device_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mobile_devices
    ADD CONSTRAINT mobile_devices_device_id_key UNIQUE (device_id);


--
-- Name: mobile_devices mobile_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mobile_devices
    ADD CONSTRAINT mobile_devices_pkey PRIMARY KEY (id);


--
-- Name: nextcloud_accounts nextcloud_accounts_mail_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nextcloud_accounts
    ADD CONSTRAINT nextcloud_accounts_mail_username_key UNIQUE (mail_username);


--
-- Name: nextcloud_accounts nextcloud_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nextcloud_accounts
    ADD CONSTRAINT nextcloud_accounts_pkey PRIMARY KEY (id);


--
-- Name: org_contacts org_contacts_domain_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_contacts
    ADD CONSTRAINT org_contacts_domain_email_key UNIQUE (domain, email);


--
-- Name: org_contacts org_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_contacts
    ADD CONSTRAINT org_contacts_pkey PRIMARY KEY (id);


--
-- Name: priority_cache priority_cache_owner_folder_message_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.priority_cache
    ADD CONSTRAINT priority_cache_owner_folder_message_uid_key UNIQUE (owner, folder, message_uid);


--
-- Name: priority_cache priority_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.priority_cache
    ADD CONSTRAINT priority_cache_pkey PRIMARY KEY (id);


--
-- Name: quota2 quota2_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota2
    ADD CONSTRAINT quota2_pkey PRIMARY KEY (username);


--
-- Name: quota quota_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota
    ADD CONSTRAINT quota_pkey PRIMARY KEY (username, path);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: retention_policies retention_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retention_policies
    ADD CONSTRAINT retention_policies_pkey PRIMARY KEY (id);


--
-- Name: room_bookings room_bookings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_bookings
    ADD CONSTRAINT room_bookings_pkey PRIMARY KEY (id);


--
-- Name: scheduled_emails scheduled_emails_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_emails
    ADD CONSTRAINT scheduled_emails_pkey PRIMARY KEY (id);


--
-- Name: sent_recipients sent_recipients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sent_recipients
    ADD CONSTRAINT sent_recipients_pkey PRIMARY KEY (id);


--
-- Name: signature_audit_log signature_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_pkey PRIMARY KEY (id);


--
-- Name: smime_certificates smime_certificates_fingerprint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.smime_certificates
    ADD CONSTRAINT smime_certificates_fingerprint_key UNIQUE (fingerprint);


--
-- Name: smime_certificates smime_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.smime_certificates
    ADD CONSTRAINT smime_certificates_pkey PRIMARY KEY (id);


--
-- Name: snoozed_emails snoozed_emails_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snoozed_emails
    ADD CONSTRAINT snoozed_emails_pkey PRIMARY KEY (id);


--
-- Name: spam_analysis spam_analysis_owner_folder_message_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spam_analysis
    ADD CONSTRAINT spam_analysis_owner_folder_message_uid_key UNIQUE (owner, folder, message_uid);


--
-- Name: spam_analysis spam_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spam_analysis
    ADD CONSTRAINT spam_analysis_pkey PRIMARY KEY (id);


--
-- Name: sso_config sso_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_config
    ADD CONSTRAINT sso_config_pkey PRIMARY KEY (id);


--
-- Name: task_activity task_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_activity
    ADD CONSTRAINT task_activity_pkey PRIMARY KEY (id);


--
-- Name: task_board_members task_board_members_board_id_user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_board_members
    ADD CONSTRAINT task_board_members_board_id_user_email_key UNIQUE (board_id, user_email);


--
-- Name: task_board_members task_board_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_board_members
    ADD CONSTRAINT task_board_members_pkey PRIMARY KEY (id);


--
-- Name: task_boards task_boards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_boards
    ADD CONSTRAINT task_boards_pkey PRIMARY KEY (id);


--
-- Name: task_cards task_cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_cards
    ADD CONSTRAINT task_cards_pkey PRIMARY KEY (id);


--
-- Name: task_labels task_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_labels
    ADD CONSTRAINT task_labels_pkey PRIMARY KEY (id);


--
-- Name: task_lists task_lists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_lists
    ADD CONSTRAINT task_lists_pkey PRIMARY KEY (id);


--
-- Name: task_steps task_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_steps
    ADD CONSTRAINT task_steps_pkey PRIMARY KEY (id);


--
-- Name: user_activity_log user_activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_activity_log
    ADD CONSTRAINT user_activity_log_pkey PRIMARY KEY (id);


--
-- Name: user_contacts user_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_contacts
    ADD CONSTRAINT user_contacts_pkey PRIMARY KEY (id);


--
-- Name: user_identities user_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities
    ADD CONSTRAINT user_identities_pkey PRIMARY KEY (id);


--
-- Name: user_labels user_labels_owner_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_labels
    ADD CONSTRAINT user_labels_owner_name_key UNIQUE (owner, name);


--
-- Name: user_labels user_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_labels
    ADD CONSTRAINT user_labels_pkey PRIMARY KEY (id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (username);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_email_key UNIQUE (user_email);


--
-- Name: user_signatures user_signatures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_signatures
    ADD CONSTRAINT user_signatures_pkey PRIMARY KEY (id);


--
-- Name: user_totp user_totp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_totp
    ADD CONSTRAINT user_totp_pkey PRIMARY KEY (username);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vacation_notification vacation_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation_notification
    ADD CONSTRAINT vacation_notification_pkey PRIMARY KEY (on_vacation, notified);


--
-- Name: vacation vacation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation
    ADD CONSTRAINT vacation_pkey PRIMARY KEY (email);


--
-- Name: webhook_logs webhook_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_logs
    ADD CONSTRAINT webhook_logs_pkey PRIMARY KEY (id);


--
-- Name: webhooks webhooks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhooks
    ADD CONSTRAINT webhooks_pkey PRIMARY KEY (id);


--
-- Name: alias_address_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS alias_address_active ON public.alias USING btree (address, active);


--
-- Name: alias_domain_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS alias_domain_active ON public.alias_domain USING btree (alias_domain, active);


--
-- Name: alias_domain_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS alias_domain_idx ON public.alias USING btree (domain);


--
-- Name: domain_domain_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS domain_domain_active ON public.domain USING btree (domain, active);


--
-- Name: idx_admin_audit_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_admin_audit_action ON public.admin_audit USING btree (action);


--
-- Name: idx_admin_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON public.admin_audit USING btree (created_at DESC);


--
-- Name: idx_attachment_scans_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_attachment_scans_message ON public.attachment_scans USING btree (message_id);


--
-- Name: idx_audit_log_admin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_audit_log_admin ON public.audit_log USING btree (admin_user);


--
-- Name: idx_audit_log_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_audit_log_date ON public.audit_log USING btree (created_at);


--
-- Name: idx_audit_log_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_audit_log_target ON public.audit_log USING btree (target);


--
-- Name: idx_cal_att_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_cal_att_event ON public.calendar_event_attachments USING btree (event_id);


--
-- Name: idx_calendar_shares_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_calendar_shares_owner ON public.calendar_shares USING btree (owner_email);


--
-- Name: idx_calendar_shares_shared_with; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_calendar_shares_shared_with ON public.calendar_shares USING btree (shared_with);


--
-- Name: idx_calendars_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_calendars_owner ON public.calendars USING btree (owner_email);


--
-- Name: idx_cc_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_cc_created_by ON public.compliance_cases USING btree (created_by);


--
-- Name: idx_cc_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_cc_status ON public.compliance_cases USING btree (status);


--
-- Name: idx_contact_audit_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_contact_audit_owner ON public.contact_audit_log USING btree (owner, created_at DESC);


--
-- Name: idx_contacts_dedup; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_dedup ON public.user_contacts USING btree (owner, email) WHERE ((deleted_at IS NULL) AND ((email)::text <> ''::text));


--
-- Name: idx_contacts_deleted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_contacts_deleted ON public.user_contacts USING btree (owner) WHERE (deleted_at IS NOT NULL);


--
-- Name: idx_contacts_favorite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_contacts_favorite ON public.user_contacts USING btree (owner, is_favorite) WHERE (deleted_at IS NULL);


--
-- Name: idx_domains_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_domains_name ON public.domains USING btree (name);


--
-- Name: idx_ee_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ee_case ON public.ediscovery_exports USING btree (case_id);


--
-- Name: idx_er_hold; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_er_hold ON public.ediscovery_results USING btree (hold_status);


--
-- Name: idx_er_mailbox; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_er_mailbox ON public.ediscovery_results USING btree (mailbox);


--
-- Name: idx_er_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_er_message_id ON public.ediscovery_results USING btree (message_id);


--
-- Name: idx_er_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_er_search ON public.ediscovery_results USING btree (search_id);


--
-- Name: idx_es_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_es_case ON public.ediscovery_searches USING btree (case_id);


--
-- Name: idx_es_executed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_es_executed_by ON public.ediscovery_searches USING btree (executed_by);


--
-- Name: idx_event_invitations_attendee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_event_invitations_attendee ON public.event_invitations USING btree (attendee_email);


--
-- Name: idx_event_invitations_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_event_invitations_event ON public.event_invitations USING btree (event_id);


--
-- Name: idx_events_calendar; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_events_calendar ON public.events USING btree (calendar_id);


--
-- Name: idx_events_range; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_events_range ON public.events USING btree (dtstart, dtend);


--
-- Name: idx_events_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_events_uid ON public.events USING btree (uid);


--
-- Name: idx_fa_ack; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_ack ON public.fraud_alerts USING btree (is_acknowledged);


--
-- Name: idx_fa_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_case ON public.fraud_alerts USING btree (related_case_id);


--
-- Name: idx_fa_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_created ON public.fraud_alerts USING btree (created_at);


--
-- Name: idx_fa_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_severity ON public.fraud_alerts USING btree (severity);


--
-- Name: idx_fa_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_status ON public.fraud_alerts USING btree (status);


--
-- Name: idx_fa_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_type ON public.fraud_alerts USING btree (alert_type);


--
-- Name: idx_fa_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_fa_username ON public.fraud_alerts USING btree (username);


--
-- Name: idx_labels_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_labels_owner ON public.user_labels USING btree (owner);


--
-- Name: idx_lh_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_lh_active ON public.legal_holds USING btree (is_active);


--
-- Name: idx_lh_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_lh_case ON public.legal_holds USING btree (case_id);


--
-- Name: idx_lh_mailbox; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_lh_mailbox ON public.legal_holds USING btree (mailbox);


--
-- Name: idx_mlabels_owner_folder; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mlabels_owner_folder ON public.message_labels USING btree (owner, folder);


--
-- Name: idx_mobile_devices_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mobile_devices_active ON public.mobile_devices USING btree (is_active);


--
-- Name: idx_mobile_devices_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mobile_devices_email ON public.mobile_devices USING btree (user_email);


--
-- Name: idx_mt_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_created ON public.mail_trace USING btree (created_at);


--
-- Name: idx_mt_delivered; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_delivered ON public.mail_trace USING btree (delivered_at);


--
-- Name: idx_mt_direction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_direction ON public.mail_trace USING btree (direction);


--
-- Name: idx_mt_dovecot_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_dovecot_user ON public.mail_trace USING btree (dovecot_user);


--
-- Name: idx_mt_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_message_id ON public.mail_trace USING btree (message_id);


--
-- Name: idx_mt_queue_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_queue_id ON public.mail_trace USING btree (queue_id);


--
-- Name: idx_mt_recipient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_recipient ON public.mail_trace USING btree (recipient);


--
-- Name: idx_mt_sender; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_sender ON public.mail_trace USING btree (sender);


--
-- Name: idx_mt_source_ip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_source_ip ON public.mail_trace USING btree (source_ip);


--
-- Name: idx_mt_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_mt_status ON public.mail_trace USING btree (status);


--
-- Name: idx_nc_accounts_mail; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_nc_accounts_mail ON public.nextcloud_accounts USING btree (mail_username);


--
-- Name: idx_org_contacts_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_org_contacts_domain ON public.org_contacts USING btree (domain);


--
-- Name: idx_priority_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_priority_owner ON public.priority_cache USING btree (owner, folder);


--
-- Name: idx_public_mlog_from; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_public_mlog_from ON public.mail_log USING btree (from_address);


--
-- Name: idx_public_mlog_msgid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_public_mlog_msgid ON public.mail_log USING btree (message_id);


--
-- Name: idx_public_mlog_qid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_public_mlog_qid ON public.mail_log USING btree (queue_id);


--
-- Name: idx_public_mlog_to; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_public_mlog_to ON public.mail_log USING btree (to_address);


--
-- Name: idx_public_mlog_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_public_mlog_ts ON public.mail_log USING btree ("timestamp");


--
-- Name: idx_room_bookings_room_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_room_bookings_room_time ON public.room_bookings USING btree (room_id, start_time, end_time);


--
-- Name: idx_rt_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_rt_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: idx_sent_recipients_sender; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_sent_recipients_sender ON public.sent_recipients USING btree (sender);


--
-- Name: idx_sent_recipients_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX IF NOT EXISTS idx_sent_recipients_unique ON public.sent_recipients USING btree (sender, recipient_email);


--
-- Name: idx_shared_notes_contact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_shared_notes_contact ON public.contact_shared_notes USING btree (contact_id);


--
-- Name: idx_shared_notes_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_shared_notes_org ON public.contact_shared_notes USING btree (org_contact_id);


--
-- Name: idx_sig_data_contact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_sig_data_contact ON public.contact_signature_data USING btree (contact_id);


--
-- Name: idx_sig_data_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_sig_data_status ON public.contact_signature_data USING btree (status);


--
-- Name: idx_signatures_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_signatures_owner ON public.user_signatures USING btree (owner);


--
-- Name: idx_smime_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_smime_user ON public.smime_certificates USING btree (user_email);


--
-- Name: idx_snooze_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_snooze_owner ON public.snoozed_emails USING btree (owner);


--
-- Name: idx_snooze_until; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_snooze_until ON public.snoozed_emails USING btree (snooze_until) WHERE (restored = false);


--
-- Name: idx_spam_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_spam_owner ON public.spam_analysis USING btree (owner, folder);


--
-- Name: idx_sync_state_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_sync_state_owner ON public.contact_sync_state USING btree (owner);


--
-- Name: idx_task_activity_board; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_activity_board ON public.task_activity USING btree (board_id);


--
-- Name: idx_task_activity_card; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_activity_card ON public.task_activity USING btree (card_id);


--
-- Name: idx_task_board_members_board; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_board_members_board ON public.task_board_members USING btree (board_id);


--
-- Name: idx_task_board_members_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_board_members_user ON public.task_board_members USING btree (user_email);


--
-- Name: idx_task_boards_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_boards_user ON public.task_boards USING btree ("user");


--
-- Name: idx_task_cards_assigned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_cards_assigned ON public.task_cards USING btree (assigned_to);


--
-- Name: idx_task_cards_due_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_cards_due_date ON public.task_cards USING btree (due_date);


--
-- Name: idx_task_cards_important; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_cards_important ON public.task_cards USING btree (important);


--
-- Name: idx_task_cards_list; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_cards_list ON public.task_cards USING btree (list_id);


--
-- Name: idx_task_cards_my_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_cards_my_day ON public.task_cards USING btree (my_day);


--
-- Name: idx_task_labels_board; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_labels_board ON public.task_labels USING btree (board_id);


--
-- Name: idx_task_lists_board; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_task_lists_board ON public.task_lists USING btree (board_id);


--
-- Name: idx_templates_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_templates_owner ON public.email_templates USING btree (owner);


--
-- Name: idx_ual_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_action ON public.user_activity_log USING btree (action);


--
-- Name: idx_ual_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_category ON public.user_activity_log USING btree (category);


--
-- Name: idx_ual_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_created ON public.user_activity_log USING btree (created_at);


--
-- Name: idx_ual_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_message_id ON public.user_activity_log USING btree (message_id);


--
-- Name: idx_ual_risk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_risk ON public.user_activity_log USING btree (risk_level);


--
-- Name: idx_ual_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_ual_username ON public.user_activity_log USING btree (username);


--
-- Name: idx_user_contacts_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_contacts_email ON public.user_contacts USING btree (lower((email)::text));


--
-- Name: idx_user_contacts_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_contacts_owner ON public.user_contacts USING btree (owner);


--
-- Name: idx_user_identities_default; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_identities_default ON public.user_identities USING btree (username, is_default) WHERE (is_default = true);


--
-- Name: idx_user_identities_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_identities_username ON public.user_identities USING btree (username);


--
-- Name: idx_user_profiles_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles USING btree (user_email);


--
-- Name: idx_user_profiles_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_user_profiles_search ON public.user_profiles USING gin (to_tsvector('spanish'::regconfig, ((((COALESCE(display_name, ''::text) || ' '::text) || COALESCE(title, ''::text)) || ' '::text) || COALESCE(department, ''::text))));


--
-- Name: idx_users_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_users_domain ON public.users USING btree (domain_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users USING btree (email);


--
-- Name: log_domain_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS log_domain_timestamp_idx ON public.log USING btree (domain, "timestamp");


--
-- Name: mailbox_domain_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS mailbox_domain_idx ON public.mailbox USING btree (domain);


--
-- Name: mailbox_username_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS mailbox_username_active ON public.mailbox USING btree (username, active);


--
-- Name: vacation_email_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS vacation_email_active ON public.vacation USING btree (email, active);


--
-- Name: quota mergequota; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER mergequota BEFORE INSERT ON public.quota FOR EACH ROW EXECUTE FUNCTION public.merge_quota();


--
-- Name: quota2 mergequota2; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER mergequota2 BEFORE INSERT ON public.quota2 FOR EACH ROW EXECUTE FUNCTION public.merge_quota2();


--
-- Name: user_contacts trg_contacts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_contacts_updated_at BEFORE UPDATE ON public.user_contacts FOR EACH ROW EXECUTE FUNCTION public.update_contacts_updated_at();


--
-- Name: admin_audit admin_audit_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit
    ADD CONSTRAINT admin_audit_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admin_users(id);


--
-- Name: admin_sessions admin_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_sessions
    ADD CONSTRAINT admin_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.admin_users(id) ON DELETE CASCADE;


--
-- Name: alias_domain alias_domain_alias_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alias_domain
    ADD CONSTRAINT alias_domain_alias_domain_fkey FOREIGN KEY (alias_domain) REFERENCES public.domain(domain) ON DELETE CASCADE;


--
-- Name: alias alias_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alias
    ADD CONSTRAINT alias_domain_fkey FOREIGN KEY (domain) REFERENCES public.domain(domain);


--
-- Name: alias_domain alias_domain_target_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alias_domain
    ADD CONSTRAINT alias_domain_target_domain_fkey FOREIGN KEY (target_domain) REFERENCES public.domain(domain) ON DELETE CASCADE;


--
-- Name: calendar_shares calendar_shares_calendar_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_shares
    ADD CONSTRAINT calendar_shares_calendar_id_fkey FOREIGN KEY (calendar_id) REFERENCES public.calendars(id) ON DELETE CASCADE;


--
-- Name: contact_category_assignments contact_category_assignments_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_category_assignments
    ADD CONSTRAINT contact_category_assignments_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.contact_categories(id) ON DELETE CASCADE;


--
-- Name: contact_category_assignments contact_category_assignments_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_category_assignments
    ADD CONSTRAINT contact_category_assignments_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_custom_values contact_custom_values_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_values
    ADD CONSTRAINT contact_custom_values_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_custom_values contact_custom_values_field_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_custom_values
    ADD CONSTRAINT contact_custom_values_field_id_fkey FOREIGN KEY (field_id) REFERENCES public.contact_custom_fields(id) ON DELETE CASCADE;


--
-- Name: contact_list_members contact_list_members_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_list_members
    ADD CONSTRAINT contact_list_members_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_list_members contact_list_members_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_list_members
    ADD CONSTRAINT contact_list_members_list_id_fkey FOREIGN KEY (list_id) REFERENCES public.contact_lists(id) ON DELETE CASCADE;


--
-- Name: contact_relationships contact_relationships_from_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_relationships
    ADD CONSTRAINT contact_relationships_from_contact_id_fkey FOREIGN KEY (from_contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_relationships contact_relationships_to_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_relationships
    ADD CONSTRAINT contact_relationships_to_contact_id_fkey FOREIGN KEY (to_contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_reminders contact_reminders_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_reminders
    ADD CONSTRAINT contact_reminders_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_shared_notes contact_shared_notes_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_shared_notes
    ADD CONSTRAINT contact_shared_notes_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_shared_notes contact_shared_notes_org_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_shared_notes
    ADD CONSTRAINT contact_shared_notes_org_contact_id_fkey FOREIGN KEY (org_contact_id) REFERENCES public.org_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_signature_data contact_signature_data_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_signature_data
    ADD CONSTRAINT contact_signature_data_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: contact_sync_state contact_sync_state_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_sync_state
    ADD CONSTRAINT contact_sync_state_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.user_contacts(id) ON DELETE CASCADE;


--
-- Name: domain_admins domain_admins_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domain_admins
    ADD CONSTRAINT domain_admins_domain_fkey FOREIGN KEY (domain) REFERENCES public.domain(domain);


--
-- Name: ediscovery_exports ediscovery_exports_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: ediscovery_exports ediscovery_exports_search_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_exports
    ADD CONSTRAINT ediscovery_exports_search_id_fkey FOREIGN KEY (search_id) REFERENCES public.ediscovery_searches(id);


--
-- Name: ediscovery_results ediscovery_results_search_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_results
    ADD CONSTRAINT ediscovery_results_search_id_fkey FOREIGN KEY (search_id) REFERENCES public.ediscovery_searches(id);


--
-- Name: ediscovery_searches ediscovery_searches_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ediscovery_searches
    ADD CONSTRAINT ediscovery_searches_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: event_invitations event_invitations_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_invitations
    ADD CONSTRAINT event_invitations_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: events events_calendar_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_calendar_id_fkey FOREIGN KEY (calendar_id) REFERENCES public.calendars(id) ON DELETE CASCADE;


--
-- Name: fraud_alerts fraud_alerts_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_alerts
    ADD CONSTRAINT fraud_alerts_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: legal_holds legal_holds_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_holds
    ADD CONSTRAINT legal_holds_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.compliance_cases(id);


--
-- Name: mail_group_members mail_group_members_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_group_members
    ADD CONSTRAINT mail_group_members_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.mail_groups(id) ON DELETE CASCADE;


--
-- Name: mail_user_signatures mail_user_signatures_signature_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_user_signatures
    ADD CONSTRAINT mail_user_signatures_signature_id_fkey FOREIGN KEY (signature_id) REFERENCES public.mail_signatures(id) ON DELETE SET NULL;


--
-- Name: mailbox mailbox_domain_fkey1; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mailbox
    ADD CONSTRAINT mailbox_domain_fkey1 FOREIGN KEY (domain) REFERENCES public.domain(domain);


--
-- Name: message_labels message_labels_label_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_labels
    ADD CONSTRAINT message_labels_label_id_fkey FOREIGN KEY (label_id) REFERENCES public.user_labels(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_username_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_username_fkey FOREIGN KEY (username) REFERENCES public.mailbox(username) ON DELETE CASCADE;


--
-- Name: room_bookings room_bookings_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_bookings
    ADD CONSTRAINT room_bookings_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.meeting_rooms(id) ON DELETE CASCADE;


--
-- Name: task_activity task_activity_board_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_activity
    ADD CONSTRAINT task_activity_board_id_fkey FOREIGN KEY (board_id) REFERENCES public.task_boards(id) ON DELETE CASCADE;


--
-- Name: task_activity task_activity_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_activity
    ADD CONSTRAINT task_activity_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.task_cards(id) ON DELETE SET NULL;


--
-- Name: task_board_members task_board_members_board_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_board_members
    ADD CONSTRAINT task_board_members_board_id_fkey FOREIGN KEY (board_id) REFERENCES public.task_boards(id) ON DELETE CASCADE;


--
-- Name: task_cards task_cards_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_cards
    ADD CONSTRAINT task_cards_list_id_fkey FOREIGN KEY (list_id) REFERENCES public.task_lists(id) ON DELETE CASCADE;


--
-- Name: task_labels task_labels_board_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_labels
    ADD CONSTRAINT task_labels_board_id_fkey FOREIGN KEY (board_id) REFERENCES public.task_boards(id) ON DELETE CASCADE;


--
-- Name: task_lists task_lists_board_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_lists
    ADD CONSTRAINT task_lists_board_id_fkey FOREIGN KEY (board_id) REFERENCES public.task_boards(id) ON DELETE CASCADE;


--
-- Name: task_steps task_steps_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_steps
    ADD CONSTRAINT task_steps_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.task_cards(id) ON DELETE CASCADE;


--
-- Name: users users_domain_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_domain_id_fkey FOREIGN KEY (domain_id) REFERENCES public.domains(id) ON DELETE CASCADE;


--
-- Name: vacation vacation_domain_fkey1; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation
    ADD CONSTRAINT vacation_domain_fkey1 FOREIGN KEY (domain) REFERENCES public.domain(domain);


--
-- Name: vacation_notification vacation_notification_on_vacation_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation_notification
    ADD CONSTRAINT vacation_notification_on_vacation_fkey FOREIGN KEY (on_vacation) REFERENCES public.vacation(email) ON DELETE CASCADE;


--
-- Name: webhook_logs webhook_logs_webhook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_logs
    ADD CONSTRAINT webhook_logs_webhook_id_fkey FOREIGN KEY (webhook_id) REFERENCES public.webhooks(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict KsJP9eERKumHRynhscLd7gbLcpaHJ7fsAEXlGNY6hdUuT2AmASstxlV6AToUOmh

