<?php
// Adminer del panel (Hospedaje → Bases de datos): solo las bases de ESTE servidor. Sin esto, Adminer
// deja escribir cualquier servidor en el formulario y serviría de puente hacia otras máquinas.
include_once __DIR__ . "/adminer-plugins/login-servers.php";

// Entrada directa desde el panel (entrar.php): si el formulario trae un vale válido, no se pide la ficha de
// sesión de Adminer (que aún no existe). El vale es de un solo uso y vence a los 60 s.
class AdminerEntradaPanel {
	function verifyLoginToken() {
		$vale = (string)($_POST["entrada_panel"] ?? "");
		if (!preg_match('/^[0-9a-f]{32}$/', $vale)) {
			return null;
		}
		$ruta = "/var/lib/herramientas-bd/vales/adminer-" . $vale;
		$hecho = @file_get_contents($ruta);
		@unlink($ruta);
		return ($hecho !== false && time() - (int)$hecho < 60) ? false : null;
	}
}

return array(
    new AdminerEntradaPanel(),
    new AdminerLoginServers(array(
        "MariaDB (este servidor)" => array("server" => "localhost", "driver" => "server"),
        "PostgreSQL (este servidor)" => array("server" => "127.0.0.1", "driver" => "pgsql"),
    )),
);
