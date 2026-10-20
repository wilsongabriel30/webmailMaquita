<?php
// Entrada directa desde el panel (Hospedaje → Sitios web → Bases → Entrar): lee el vale de un solo uso que dejó
// maquita-sitios (usuario temporal de la base, 60 s), lo borra y abre phpMyAdmin o Adminer ya conectados.
// La contraseña temporal no pasa por el panel: solo por esta página, que la usa al momento.
declare(strict_types=1);

const VALES = '/var/lib/herramientas-bd/vales';

function fallar(string $motivo): never {
    http_response_code(403);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><meta charset="utf-8"><title>Entrada no válida</title>',
         '<p style="font-family:sans-serif">', htmlspecialchars($motivo), ' Vuelva al panel y pulse «Entrar» otra vez.</p>';
    exit;
}

$vale = (string)($_GET['vale'] ?? '');
if (!preg_match('/^[A-Za-z0-9_-]{20,64}$/', $vale)) {
    fallar('Vale no válido.');
}
$ruta = VALES . '/' . $vale;
$texto = @file_get_contents($ruta);
@unlink($ruta);  // un solo uso, salga bien o no
$d = $texto ? json_decode($texto, true) : null;
if (!is_array($d) || ($d['vence'] ?? 0) < time()) {
    fallar('El vale ya se usó o venció.');
}
header('Cache-Control: no-store');
header('Referrer-Policy: no-referrer');

if ($d['herramienta'] === 'phpmyadmin') {
    // Autenticación «signon» de phpMyAdmin (servidor 9 de conf.d/maquita-entrada.php).
    session_name('MaquitaEntradaPMA');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/herramientas/phpmyadmin/', 'secure' => true,
                               'httponly' => true, 'samesite' => 'Strict']);
    session_start();
    $_SESSION['PMA_single_signon_user'] = $d['usuario'];
    $_SESSION['PMA_single_signon_password'] = $d['clave'];
    $_SESSION['PMA_single_signon_host'] = $d['servidor'];
    session_write_close();
    header('Location: /herramientas/phpmyadmin/index.php?server=9&db=' . rawurlencode($d['base']));
    exit;
}

// Adminer: su formulario de entrada, enviado solo. Un segundo vale le dice al complemento que esta entrada viene
// del panel (Adminer exige si no su ficha de sesión, que aquí todavía no existe).
$segundo = bin2hex(random_bytes(16));
file_put_contents(VALES . '/adminer-' . $segundo, (string)time());
$nonce = base64_encode(random_bytes(16));
header("Content-Security-Policy: default-src 'none'; script-src 'nonce-$nonce'; form-action 'self'; base-uri 'none'");
$campos = [
    // El complemento de servidores fijos (adminer-plugins.php) recibe el nombre de la lista y pone él la dirección.
    'auth[server]' => $d['motor'] === 'postgresql' ? 'PostgreSQL (este servidor)' : 'MariaDB (este servidor)',
    'auth[username]' => $d['usuario'],
    'auth[password]' => $d['clave'],
    'auth[db]' => $d['base'],
    'entrada_panel' => $segundo,
];
echo '<!doctype html><meta charset="utf-8"><title>Abriendo Adminer…</title>',
     '<form id="f" method="post" action="/herramientas/adminer/">';
foreach ($campos as $k => $v) {
    echo '<input type="hidden" name="', htmlspecialchars($k), '" value="', htmlspecialchars((string)$v), '">';
}
echo '<noscript><button>Entrar en Adminer</button></noscript></form>',
     '<script nonce="', $nonce, '">document.getElementById("f").submit();</script>';
