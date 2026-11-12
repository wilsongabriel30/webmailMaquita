#!/usr/bin/env python3
"""Convierte conjuntos de nftables (JSON de «nft -j list set …», uno o varios seguidos) en la lista
que nginx usa para el filtro por país del puerto 443 (deploy/webmail/nginx/filtro-pais.conf).

Entrada: por stdin, la salida concatenada de «nft -j list set inet filter <conjunto>».
Salida:  líneas «RED 1;» para el bloque «geo» de nginx.
Sin ningún conjunto (la instalación no filtra por país) la lista deja pasar a todos (las dos mitades de IPv4).
Con conjuntos pero casi vacíos se niega a escribir (código 3): mejor conservar la lista anterior.
"""

import ipaddress
import json
import sys

MINIMO_REDES = 5
# Las dos mitades de IPv4, y no «0.0.0.0/0», que nginx avisa como duplicado del «default» del bloque geo.
ABIERTA = "# Esta instalación no filtra por país: se deja pasar a todos.\n0.0.0.0/1 1;\n128.0.0.0/1 1;\n"


def documentos(texto: str):
    """Los objetos JSON que vienen uno detrás de otro en el texto."""
    decodificador, pos = json.JSONDecoder(), 0
    while pos < len(texto):
        while pos < len(texto) and texto[pos].isspace():
            pos += 1
        if pos >= len(texto):
            break
        documento, pos = decodificador.raw_decode(texto, pos)
        yield documento


def redes(texto: str):
    """(hay_conjuntos, redes IPv4 ordenadas y sin repetir)."""
    hay, lista = False, []
    for documento in documentos(texto):
        for objeto in documento.get("nftables", []):
            conjunto = objeto.get("set")
            if conjunto is None:
                continue
            hay = True
            for e in conjunto.get("elem") or []:
                if isinstance(e, str):
                    lista.append(ipaddress.ip_network(e, strict=False))
                elif "prefix" in e:
                    lista.append(
                        ipaddress.ip_network(
                            f'{e["prefix"]["addr"]}/{e["prefix"]["len"]}', strict=False
                        )
                    )
                elif "range" in e:
                    a, b = (ipaddress.ip_address(x) for x in e["range"])
                    lista += list(ipaddress.summarize_address_range(a, b))
    v4 = sorted(
        {r for r in lista if r.version == 4},
        key=lambda r: (int(r.network_address), r.prefixlen),
    )
    return hay, v4


def lista_nginx(texto: str) -> str:
    hay, v4 = redes(texto)
    if not hay:
        return ABIERTA
    if len(v4) < MINIMO_REDES:
        raise ValueError("conjunto vacío o casi vacío: no se toca la lista de nginx")
    cabecera = "# Generado por geo-nginx-rebuild.sh a partir de los conjuntos de nftables. No editar a mano.\n"
    return cabecera + "".join(f"{r} 1;\n" for r in v4)


if __name__ == "__main__":
    try:
        sys.stdout.write(lista_nginx(sys.stdin.read()))
    except ValueError as error:
        sys.stderr.write(f"geo-nginx-lista: {error}\n")
        sys.exit(3)
