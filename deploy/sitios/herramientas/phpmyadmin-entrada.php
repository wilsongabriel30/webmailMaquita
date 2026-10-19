<?php
// Segundo servidor de phpMyAdmin: el mismo MariaDB, con entrada directa desde el panel (entrar.php deja el
// usuario temporal en la sesión «MaquitaEntradaPMA»). El primero sigue pidiendo usuario y contraseña.
// Número fijo (9), no «$i++»: la configuración de Debian deja el contador en un valor que no es el último.
$i = 9;
$cfg['Servers'][$i]['verbose'] = 'MariaDB (entrada desde el panel)';
$cfg['Servers'][$i]['auth_type'] = 'signon';
$cfg['Servers'][$i]['host'] = 'localhost';
$cfg['Servers'][$i]['SignonSession'] = 'MaquitaEntradaPMA';
$cfg['Servers'][$i]['SignonCookieParams'] = ['lifetime' => 0, 'path' => '/herramientas/phpmyadmin/', 'domain' => '',
                                            'secure' => true, 'httponly' => true, 'samesite' => 'Strict'];
$cfg['Servers'][$i]['SignonURL'] = '/herramientas/phpmyadmin/index.php?server=1';
$cfg['Servers'][$i]['LogoutURL'] = '/herramientas/phpmyadmin/index.php?server=1';
$cfg['ServerDefault'] = 1;
