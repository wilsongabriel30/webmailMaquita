<?php
/*** Z-Push config.php - mail.example.org ***/

// Timezone & base
define("TIMEZONE", "America/Guayaquil");
define("BASE_PATH", dirname($_SERVER["SCRIPT_FILENAME"]). "/");
define("SCRIPT_TIMEOUT", 0);
define("USE_CUSTOM_REMOTE_IP_HEADER", "HTTP_X_REAL_IP");
define("CERTIFICATE_OWNER_PARAMETER", "SSL_CLIENT_S_DN_CN");
define("USE_FULLEMAIL_FOR_LOGIN", true);

// State machine
define("STATE_MACHINE", "FILE");
define("STATE_DIR", "/var/lib/z-push/");

// IPC
define("IPC_PROVIDER", "");

// Logging
define("LOGBACKEND", "filelog");
define("LOGFILEDIR", "/var/log/z-push/");
define("LOGFILE", LOGFILEDIR . "z-push.log");
define("LOGERRORFILE", LOGFILEDIR . "z-push-error.log");
define("LOGLEVEL", LOGLEVEL_INFO);
define("LOGUSERLEVEL", LOGLEVEL_DEVICEID);
define("LOGAUTHFAIL", true);

// Syslog (not used, but needed)
define("LOG_SYSLOG_HOST", "localhost");
define("LOG_SYSLOG_PORT", 514);
define("LOG_SYSLOG_PROGRAM", "z-push");
define("LOG_SYSLOG_FACILITY", LOG_USER);

// Backend
define("BACKEND_PROVIDER", "BackendCombined");

// Search
define("SEARCH_PROVIDER", "");
define("SEARCH_WAIT", 10);
define("SEARCH_MAXRESULTS", 10);

// Security
define("UNSET_UNDEFINED_PROPERTIES", true);

// Provisioning
define("PROVISIONING", true);
define("LOOSE_PROVISIONING", true);
define("PROVISIONING_PIN", false);
define("PROVISIONING_POLICYFILE", "policies.ini");

// Autodiscover
define("ZPUSH_HOST", "mail.example.org");

// Ping/push
define("PING_INTERVAL", 30);
define("PING_HIGHER_BOUND_LIFETIME", 300);
define("PING_LOWER_BOUND_LIFETIME", 60);

// Sync settings
define("SYNC_CONTACTS_MAXPICTURESIZE", 49152);
define("SYNC_FILTERTIME_MAX", 0);
define("SYNC_MAX_ITEMS", 512);
define("SYNC_CONFLICT_DEFAULT", SYNC_CONFLICT_OVERWRITE_PIM);
define("SYNC_TIMEOUT_LONG_DEVICETYPES", "");
define("SYNC_TIMEOUT_MEDIUM_DEVICETYPES", "");
define("USE_PARTIAL_FOLDERSYNC", false);

// WebService
define("ALLOW_WEBSERVICE_USERS_ACCESS", false);

// SSL CA
define("CAINFO", "");

// Contacts
define("FILEAS_ORDER", SYNC_FILEAS_LASTFIRST);

// Retry
define("RETRY_AFTER_DELAY", 300);

// Iconv
define("ICONV_OPTION", "");

// KOE (not used, but must be defined)
define("KOE_CAPABILITY_GAB", false);
define("KOE_CAPABILITY_RECEIVEFLAGS", false);
define("KOE_CAPABILITY_SENDFLAGS", false);
define("KOE_CAPABILITY_OOF", false);
define("KOE_CAPABILITY_OOFTIMES", false);
define("KOE_CAPABILITY_NOTES", false);
define("KOE_CAPABILITY_SHAREDFOLDER", false);
define("KOE_CAPABILITY_SENDAS", false);
define("KOE_CAPABILITY_SECONDARYCONTACTS", false);
define("KOE_CAPABILITY_SIGNATURES", false);
define("KOE_CAPABILITY_RECEIPTS", false);
define("KOE_CAPABILITY_IMPERSONATE", false);
define("KOE_GAB_STORE", "SYSTEM");
define("KOE_GAB_FOLDERID", "");
define("KOE_GAB_NAME", "Z-Push-KOE-GAB");

$specialLogUsers = array();
$additionalFolders = array();
