"""H-02: llave dedicada y versionada."""

from app.core import cifrado


def test_cifra_y_descifra_con_la_llave_dedicada():
    t = cifrado.cifrar("secreto")
    assert cifrado.esta_cifrado(t) and cifrado.descifrar(t) == "secreto"


def test_lo_cifrado_con_la_llave_heredada_no_abre_con_la_dedicada():
    import pytest
    from cryptography.fernet import InvalidToken

    viejo = cifrado.fernet_heredado_de_secret_key().encrypt(b"secreto").decode()
    with pytest.raises(InvalidToken):
        cifrado.descifrar(viejo)
