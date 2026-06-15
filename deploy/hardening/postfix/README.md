# Hardening Postfix — anti fuerza bruta SASL

## Deshabilitar AUTH en el puerto 25 (OBLIGATORIO)
El puerto 25 (SMTP entrante) NO debe anunciar AUTH: ningún cliente legítimo
autentica ahí (usan 587/465). Si lo anuncia, los bots hacen fuerza bruta SASL
por el 25 (ataques low-and-slow que evaden fail2ban).

    postconf -e 'smtpd_sasl_auth_enable = no'   # global -> afecta solo al 25
    systemctl reload postfix

Los servicios submission(587) y smtps(465) deben mantener su override en
master.cf:  -o smtpd_sasl_auth_enable=yes
Verificar:  postconf -P | grep sasl_auth_enable   (587 y 465 = yes)
Test 25:    openssl s_client -connect 127.0.0.1:25 -starttls smtp -quiet
            (EHLO no debe listar AUTH)

## Estrategia geo (NO geo-bloquear el puerto 25)
- Puertos autenticados (443/465/587/143/993/4190): geo-block estricto por país
  (nftables set paises_permitidos). Solo países donde hay usuarios reales.
- Puerto 25: recepcion mundial OBLIGATORIA (Gmail/Outlook/Microsoft estan en USA).
  NUNCA bloquear USA/paises por país en el 25 -> se perdería correo legítimo.
  Defensa del 25 por capas: AUTH off + postscreen+DNSBL + blacklist de subredes
  de hosting malicioso + fail2ban (journald).
