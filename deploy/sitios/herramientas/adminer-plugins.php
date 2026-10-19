<?php
// Adminer del panel (Hospedaje → Bases de datos): solo las bases de ESTE servidor. Sin esto, Adminer
// deja escribir cualquier servidor en el formulario y serviría de puente hacia otras máquinas.
include_once __DIR__ . "/adminer-plugins/login-servers.php";

return array(
    new AdminerLoginServers(array(
        "MariaDB (este servidor)" => array("server" => "localhost", "driver" => "server"),
        "PostgreSQL (este servidor)" => array("server" => "127.0.0.1", "driver" => "pgsql"),
    )),
);
