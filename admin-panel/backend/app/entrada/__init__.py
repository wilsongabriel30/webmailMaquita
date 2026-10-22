"""Formas de entrar al panel además de la contraseña: OpenID Connect y vales de un solo uso.

- cifrado.py         el client_secret del proveedor, cifrado con la llave de credenciales (Fernet).
- oidc_protocolo.py  descubrimiento, PKCE, canje del código y validación del id_token (sin base).
- oidc_config.py     configuración desde el panel (solo superadmin) y estado público del botón.
- oidc_rutas.py      /api/auth/oidc/inicio y /api/auth/oidc/vuelta (authorization code + PKCE).
- vales.py           vales de entrada de un solo uso (consola y vuelta del proveedor) y su canje.

Nada de esto toca backend/app/sso (SAML), que es la entrada de las personas al correo.
"""
