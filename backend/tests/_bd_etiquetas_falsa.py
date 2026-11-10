"""Base de datos falsa mínima para las pruebas de etiquetas (sin PostgreSQL).

Guarda `message_labels` como lista de dicts e interpreta las pocas sentencias que usan los servicios.
"""

import re


class BDEtiquetasFalsa:
    def __init__(self, filas=None):
        self.filas = [dict(f) for f in (filas or [])]
        self._id = max([f["id"] for f in self.filas], default=0)
        self.sql = []

    # helpers
    def _nuevo_id(self):
        self._id += 1
        return self._id

    def vigentes(self):
        return [f for f in self.filas if f.get("faltante_desde") is None]

    async def fetch(self, sql, *args):
        self.sql.append(sql)
        s = " ".join(sql.split())
        if s.startswith("SELECT DISTINCT message_uid FROM message_labels"):
            owner, folder, uids = args
            vistos = sorted({f["message_uid"] for f in self.filas if f["owner"] == owner and f["folder"] == folder and f["message_uid"] in uids})
            return [{"message_uid": u} for u in vistos]
        if s.startswith("SELECT id, label_id FROM message_labels"):
            owner, folder, uid = args
            return [{"id": f["id"], "label_id": f["label_id"]} for f in self.filas if f["owner"] == owner and f["folder"] == folder and f["message_uid"] == uid]
        if "GROUP BY owner" in s:  # purga: conteo por owner
            (dias,) = args
            import datetime as dt

            limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)
            conteo = {}
            for f in self.filas:
                if f.get("faltante_desde") and f["faltante_desde"] < limite:
                    conteo[f["owner"]] = conteo.get(f["owner"], 0) + 1
            return [{"owner": o, "n": n} for o, n in conteo.items()]
        if "GROUP BY label_id" in s:
            (owner,) = args
            conteo = {}
            for f in self.vigentes():
                if f["owner"] == owner:
                    conteo[f["label_id"]] = conteo.get(f["label_id"], 0) + 1
            return [{"label_id": k, "n": v} for k, v in conteo.items()]
        raise AssertionError(f"SQL no previsto en fetch: {s}")

    async def fetchval(self, sql, *args):
        self.sql.append(sql)
        s = " ".join(sql.split())
        if "COUNT(*) FROM message_labels WHERE label_id" in s:
            label_id, owner = args
            return len([f for f in self.vigentes() if f["label_id"] == label_id and f["owner"] == owner])
        raise AssertionError(f"SQL no previsto en fetchval: {s}")

    async def execute(self, sql, *args):
        self.sql.append(sql)
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO message_labels"):
            owner, folder, uid, label_id = args
            if any(f["owner"] == owner and f["folder"] == folder and f["message_uid"] == uid and f["label_id"] == label_id for f in self.filas):
                return "INSERT 0 0"
            self.filas.append({"id": self._nuevo_id(), "owner": owner, "folder": folder, "message_uid": uid, "label_id": label_id, "faltante_desde": None})
            return "INSERT 0 1"
        if s.startswith("DELETE FROM message_labels WHERE id = $1"):
            (id_,) = args
            antes = len(self.filas)
            self.filas = [f for f in self.filas if f["id"] != id_]
            return f"DELETE {antes - len(self.filas)}"
        if s.startswith("DELETE FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = ANY"):
            owner, folder, uids = args
            antes = len(self.filas)
            self.filas = [f for f in self.filas if not (f["owner"] == owner and f["folder"] == folder and f["message_uid"] in uids)]
            return f"DELETE {antes - len(self.filas)}"
        if s.startswith("DELETE FROM message_labels WHERE owner = $1 AND folder = $2"):
            owner, folder = args
            antes = len(self.filas)
            self.filas = [f for f in self.filas if not (f["owner"] == owner and f["folder"] == folder)]
            return f"DELETE {antes - len(self.filas)}"
        if s.startswith("DELETE FROM message_labels WHERE faltante_desde IS NOT NULL"):
            import datetime as dt

            (dias,) = args
            limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)
            antes = len(self.filas)
            self.filas = [f for f in self.filas if not (f.get("faltante_desde") and f["faltante_desde"] < limite)]
            return f"DELETE {antes - len(self.filas)}"
        if s.startswith("UPDATE message_labels SET faltante_desde = now()"):
            import datetime as dt

            owner, label_id, folder, uid = args
            n = 0
            for f in self.filas:
                if f["owner"] == owner and f["label_id"] == label_id and f["folder"] == folder and f["message_uid"] == uid and f.get("faltante_desde") is None:
                    f["faltante_desde"] = dt.datetime.now(dt.timezone.utc)
                    n += 1
            return f"UPDATE {n}"
        if s.startswith("UPDATE message_labels SET faltante_desde = NULL"):
            owner, folder, uids = args
            n = 0
            for f in self.filas:
                if f["owner"] == owner and f["folder"] == folder and f["message_uid"] in uids and f.get("faltante_desde") is not None:
                    f["faltante_desde"] = None
                    n += 1
            return f"UPDATE {n}"
        raise AssertionError(f"SQL no previsto en execute: {s}")


def fila(id_, owner, folder, uid, label_id, faltante=None):
    return {"id": id_, "owner": owner, "folder": folder, "message_uid": uid, "label_id": label_id, "faltante_desde": faltante}


_ = re  # silencia aviso de import no usado en algunos linters
