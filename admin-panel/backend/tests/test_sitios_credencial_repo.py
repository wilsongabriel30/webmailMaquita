"""Autenticación de git de un sitio en el panel general: el secreto va a maquita-sitios en un archivo 0600 de
subidas/ (nunca en los argumentos de sudo), el archivo no se queda si la orden falla y a la auditoría va solo el
método. El ayudante y la base son dobles; los valores son ficticios evidentes."""

import json
import os
import stat

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios import git_credencial as gcr

ADMIN = {"id": 1, "username": "ana", "role": "superadmin", "session_id": 1, "totp": True}
TOKEN = "token-ficticio-de-prueba-0000"


class Base:
    def __init__(self):
        self.ejecutado = []

    async def execute(self, sql, *args):
        self.ejecutado.append(args)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(gcr, "SUBIDAS", str(tmp_path))
    llamadas = []

    async def ayudante(*args, tiempo=60):
        visto = None
        if args[0] == "git-credencial-guardar":
            ruta = os.path.join(str(tmp_path), args[2])
            visto = (json.load(open(ruta)), stat.S_IMODE(os.stat(ruta).st_mode))
        llamadas.append((args, visto))
        if mundo_.error:
            raise HTTPException(400, mundo_.error)
        return {"metodo": "token-https", "configurada": True}

    monkeypatch.setattr(gcr, "_ayudante", ayudante)
    app = FastAPI()
    app.include_router(gcr.router)
    app.dependency_overrides[get_current_admin] = lambda: ADMIN
    app.dependency_overrides[require_superadmin] = lambda: ADMIN
    app.state.db = Base()

    class Mundo:
        error = None

    mundo_ = Mundo()
    mundo_.cliente, mundo_.llamadas, mundo_.app, mundo_.tmp = TestClient(app), llamadas, app, tmp_path
    return mundo_


def test_guardar_por_archivo(mundo):
    r = mundo.cliente.put("/api/sitios/example.org/git/credencial",
                          json={"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN})
    assert r.status_code == 200, r.text
    (orden, dominio, nombre), (datos, modo) = mundo.llamadas[-1]
    assert (orden, dominio) == ("git-credencial-guardar", "example.org") and nombre.endswith(".cred")
    assert datos == {"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN, "regenerar": False}
    assert modo == 0o600 and os.listdir(mundo.tmp) == []
    auditado = json.dumps([list(map(str, a)) for a in mundo.app.state.db.ejecutado])
    assert TOKEN not in auditado and "token-https" in auditado


def test_si_falla_no_queda_el_archivo(mundo):
    mundo.error = "credencial rechazada por el servidor de git"
    r = mundo.cliente.put("/api/sitios/example.org/git/credencial",
                          json={"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN})
    assert r.status_code == 400 and os.listdir(mundo.tmp) == [] and mundo.app.state.db.ejecutado == []


def test_metodo_no_valido(mundo):
    assert mundo.cliente.put("/api/sitios/example.org/git/credencial", json={"metodo": "otro"}).status_code == 400
    assert mundo.llamadas == []


def test_ver_y_borrar(mundo):
    assert mundo.cliente.get("/api/sitios/example.org/git/credencial").status_code == 200
    assert mundo.cliente.delete("/api/sitios/example.org/git/credencial").status_code == 200
    assert [a[0] for a, _ in mundo.llamadas] == ["git-credencial", "git-credencial-borrar"]
