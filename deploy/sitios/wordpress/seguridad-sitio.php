<?php
/**
 * Endurecimiento de WordPress (complemento obligatorio, mu-plugin, instalado por el panel).
 *
 * Cierra los puntos que más se atacan en WordPress y que nginx no puede cerrar solo:
 * - Enumeración de usuarios (?author=N, /wp-json/wp/v2/users y el mapa del sitio de usuarios).
 * - Versión de WordPress a la vista (meta generator, ?ver= de estilos y scripts, feeds).
 * - Mensajes de error del inicio de sesión que confirman si un usuario existe.
 * - XML-RPC, pingbacks y contraseñas de aplicación (vías de fuerza bruta y amplificación).
 * - Actualizaciones automáticas del núcleo, complementos, temas y traducciones.
 *
 * Licencia: GPLv2 o posterior (igual que WordPress).
 */

defined('ABSPATH') || exit;

// --- XML-RPC y pingbacks ---
add_filter('xmlrpc_enabled', '__return_false');
add_filter('pings_open', '__return_false', 20);
add_filter('xmlrpc_methods', function ($m) { unset($m['pingback.ping'], $m['pingback.extensions.getPingbacks']); return $m; });
add_filter('wp_headers', function ($h) { unset($h['X-Pingback']); return $h; });

// --- Contraseñas de aplicación (acceso por API con contraseña): apagadas ---
add_filter('wp_is_application_passwords_available', '__return_false');

// --- Versión oculta ---
remove_action('wp_head', 'wp_generator');
add_filter('the_generator', '__return_empty_string');
$quitar_version = function ($src) {
    return (is_string($src) && strpos($src, 'ver=') !== false) ? remove_query_arg('ver', $src) : $src;
};
add_filter('style_loader_src', $quitar_version, 9999);
add_filter('script_loader_src', $quitar_version, 9999);
remove_action('wp_head', 'rsd_link');
remove_action('wp_head', 'wlwmanifest_link');

// --- Enumeración de usuarios ---
add_action('template_redirect', function () {
    if (!is_user_logged_in() && (isset($_GET['author']) || is_author())) {
        wp_safe_redirect(home_url('/'), 301);
        exit;
    }
});
add_filter('rest_endpoints', function ($e) {
    if (!is_user_logged_in()) {
        foreach (array_keys($e) as $ruta) {
            if (strpos($ruta, '/wp/v2/users') === 0) {
                unset($e[$ruta]);
            }
        }
    }
    return $e;
});
add_filter('wp_sitemaps_add_provider', function ($proveedor, $nombre) {
    return $nombre === 'users' ? false : $proveedor;
}, 10, 2);
add_filter('oembed_response_data', function ($datos) {
    unset($datos['author_name'], $datos['author_url']);
    return $datos;
});

// --- Inicio de sesión: un único mensaje, sin pistas ---
add_filter('login_errors', function () {
    return 'Usuario o contraseña incorrectos.';
});

// --- Actualizaciones automáticas (núcleo, complementos, temas, traducciones) ---
add_filter('allow_major_auto_core_updates', '__return_true');
add_filter('allow_minor_auto_core_updates', '__return_true');
add_filter('auto_update_plugin', '__return_true');
add_filter('auto_update_theme', '__return_true');
add_filter('auto_update_translation', '__return_true');

// --- Cabeceras ---
add_action('send_headers', function () {
    header_remove('X-Powered-By');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
});
