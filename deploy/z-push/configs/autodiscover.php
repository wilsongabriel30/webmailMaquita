<?php
// Z-Push Autodiscover config - mail.example.org

define('TIMEZONE', 'America/Guayaquil');
define('BASE_PATH', dirname($_SERVER['SCRIPT_FILENAME']). '/');
define('USE_FULLEMAIL_FOR_LOGIN', true);
define('AUTODISCOVER_LOGIN_TYPE', AUTODISCOVER_LOGIN_EMAIL);
define('ZPUSH_HOST', 'mail.example.org');

// Logging
define('LOGBACKEND', 'filelog');
define('LOGFILEDIR', '/var/log/z-push/');
define('LOGFILE', LOGFILEDIR . 'autodiscover.log');
define('LOGERRORFILE', LOGFILEDIR . 'autodiscover-error.log');
define('LOGLEVEL', LOGLEVEL_INFO);
define('LOGUSERLEVEL', LOGLEVEL);
$specialLogUsers = array();

// Syslog
define('LOG_SYSLOG_HOST', false);
define('LOG_SYSLOG_PORT', 514);
define('LOG_SYSLOG_PROGRAM', 'z-push-autodiscover');
define('LOG_SYSLOG_FACILITY', LOG_LOCAL0);

// Backend
define('BACKEND_PROVIDER', '');
