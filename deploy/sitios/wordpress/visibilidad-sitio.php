<?php
/**
 * Visibilidad en buscadores y asistentes de IA (complemento obligatorio, mu-plugin, del panel).
 *
 * - Datos estructurados schema.org «Organization» en la portada, con la identidad de la institución
 *   que pone el panel (opción «identidad_institucion»); si no la hay, el nombre y la descripción del sitio.
 * - Descripción para buscadores (<meta name="description">) en la portada si el tema no la pone.
 * - IndexNow: al publicar o actualizar una entrada o página pública, avisa a los buscadores
 *   compatibles (Bing, Yandex, Seznam, Naver…). La clave la crea el panel (opción «indexnow_clave»,
 *   con su archivo <clave>.txt en la raíz). Google no admite avisos: usa el mapa del sitio de
 *   WordPress (/wp-sitemap.xml), que se envía una vez desde Search Console.
 *
 * Licencia: GPLv2 o posterior (igual que WordPress).
 */

defined('ABSPATH') || exit;

function visibilidad_identidad() {
    $guardada = json_decode((string) get_option('identidad_institucion', ''), true);
    return is_array($guardada) ? $guardada : array();
}

add_action('wp_head', function () {
    if (!is_front_page()) {
        return;
    }
    $ide = visibilidad_identidad();
    $nombre = !empty($ide['nombre']) ? $ide['nombre'] : get_bloginfo('name');
    $descripcion = !empty($ide['descripcion']) ? $ide['descripcion'] : get_bloginfo('description');
    $org = array('@context' => 'https://schema.org', '@type' => 'Organization', 'name' => $nombre, 'url' => home_url('/'));
    if ($descripcion) {
        $org['description'] = $descripcion;
    }
    foreach (array('correo' => 'email', 'telefono' => 'telephone') as $clave => $propiedad) {
        if (!empty($ide[$clave])) {
            $org[$propiedad] = $ide[$clave];
        }
    }
    $logo = get_theme_mod('custom_logo') ? wp_get_attachment_image_url(get_theme_mod('custom_logo'), 'full') : (!empty($ide['logo']) ? $ide['logo'] : '');
    if ($logo) {
        $org['logo'] = $logo;
    }
    if (!empty($ide['redes']) && is_array($ide['redes'])) {
        $org['sameAs'] = array_values(array_filter($ide['redes'], function ($u) { return strpos($u, 'https://') === 0; }));
    }
    echo '<script type="application/ld+json">' . wp_json_encode($org, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "</script>\n";
    if ($descripcion && !has_action('wp_head', 'wpseo_head')) {
        echo '<meta name="description" content="' . esc_attr(wp_strip_all_tags($descripcion)) . "\">\n";
    }
}, 5);

add_action('transition_post_status', function ($nuevo, $anterior, $post) {
    $clave = get_option('indexnow_clave');
    if ($nuevo !== 'publish' || !$clave || !preg_match('/^[0-9a-f]{32}$/', $clave)) {
        return;
    }
    $tipo = get_post_type_object($post->post_type);
    if (!$tipo || !$tipo->public || wp_is_post_revision($post)) {
        return;
    }
    $url = get_permalink($post);
    if (!$url) {
        return;
    }
    $host = wp_parse_url(home_url(), PHP_URL_HOST);
    wp_remote_post('https://api.indexnow.org/indexnow', array(
        'blocking' => false,
        'timeout' => 5,
        'headers' => array('Content-Type' => 'application/json; charset=utf-8'),
        'body' => wp_json_encode(array(
            'host' => $host,
            'key' => $clave,
            'keyLocation' => home_url('/' . $clave . '.txt'),
            'urlList' => array($url, home_url('/')),
        )),
    ));
}, 10, 3);
