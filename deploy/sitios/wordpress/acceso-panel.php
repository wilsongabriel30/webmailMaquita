<?php
/**
 * Acceso desde el panel de administración del servidor (complemento obligatorio, mu-plugin).
 *
 * El panel genera un vale aleatorio de un solo uso y guarda en WordPress solo su huella SHA-256,
 * como transitorio de 60 segundos asociado a un usuario administrador. Al abrir
 * /?acceso_panel=<vale> este complemento comprueba la huella, borra el transitorio (no se puede
 * reutilizar), inicia la sesión de ese usuario y lo lleva al escritorio.
 *
 * Licencia: GPLv2 o posterior (igual que WordPress).
 */

defined('ABSPATH') || exit;

add_action('init', function () {
    if (empty($_GET['acceso_panel']) || !is_string($_GET['acceso_panel'])) {
        return;
    }
    $vale = $_GET['acceso_panel'];
    nocache_headers();
    header('Referrer-Policy: no-referrer');
    if (!preg_match('/^[A-Za-z0-9_-]{40,64}$/', $vale)) {
        wp_die('Enlace de acceso no válido.', 'Acceso', array('response' => 403));
    }
    $clave = 'acceso_panel_' . hash('sha256', $vale);
    $usuario_id = (int) get_transient($clave);
    delete_transient($clave);
    $usuario = $usuario_id ? get_user_by('id', $usuario_id) : false;
    if (!$usuario || !user_can($usuario, 'manage_options')) {
        wp_die('El enlace de acceso venció o ya se usó. Vuelva a pedirlo desde el panel.', 'Acceso', array('response' => 403));
    }
    wp_clear_auth_cookie();
    wp_set_current_user($usuario->ID);
    wp_set_auth_cookie($usuario->ID, false, is_ssl());
    do_action('wp_login', $usuario->user_login, $usuario);
    wp_safe_redirect(admin_url());
    exit;
}, 1);
