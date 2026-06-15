#!/bin/bash
# ===== EDITAR =====
COUNTRIES="ec es co mx"   # codigos ISO de paises permitidos (minuscula)
LAN_NETS="127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"   # redes internas
# ==================
cd /tmp
for c in $COUNTRIES; do curl -sfo ${c}.zone "https://www.ipdeny.com/ipblocks/data/countries/${c}.zone"; done
nft flush set inet filter paises_permitidos
for net in $LAN_NETS; do nft add element inet filter paises_permitidos "{ $net }"; done
for c in $COUNTRIES; do while read cidr; do nft add element inet filter paises_permitidos "{ $cidr }" 2>/dev/null; done < /tmp/${c}.zone; done
nft list ruleset > /etc/nftables.conf
logger "GeoIP actualizado"
