# red_neuronal.py — MLP minimo (Python puro, sin numpy): sigmoid + retropropagacion.
import random, json, os, math


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-60, min(60, z))))


def _dsig(s):
    return s * (1.0 - s)


class RedNeuronal:
    def __init__(self, capas, lr=0.5, seed=42):
        rnd = random.Random(seed)
        self.lr = lr
        self.capas = []
        for i in range(len(capas) - 1):
            n_in, n_out = capas[i], capas[i + 1]
            self.capas.append([
                {"w": [rnd.uniform(-1, 1) for _ in range(n_in)], "b": rnd.uniform(-1, 1)}
                for _ in range(n_out)
            ])

    def _fwd_full(self, x):
        acts = [list(x)]
        a = list(x)
        for capa in self.capas:
            a = [_sigmoid(sum(wi * ai for wi, ai in zip(n["w"], a)) + n["b"]) for n in capa]
            acts.append(a)
        return acts

    def forward(self, x):
        return self._fwd_full(x)[-1]

    def entrenar(self, X, Y, epocas=4000):
        for _ in range(epocas):
            for x, y in zip(X, Y):
                y = y if isinstance(y, (list, tuple)) else [y]
                acts = self._fwd_full(x)
                sal = acts[-1]
                deltas = [[(sal[k] - y[k]) * _dsig(sal[k]) for k in range(len(sal))]]
                for li in range(len(self.capas) - 1, 0, -1):
                    post, dpost, apre = self.capas[li], deltas[0], acts[li]
                    dpre = [sum(post[k]["w"][j] * dpost[k] for k in range(len(post))) * _dsig(apre[j])
                            for j in range(len(apre))]
                    deltas.insert(0, dpre)
                for li, capa in enumerate(self.capas):
                    ain = acts[li]
                    for k, n in enumerate(capa):
                        d = deltas[li][k]
                        for i in range(len(n["w"])):
                            n["w"][i] -= self.lr * d * ain[i]
                        n["b"] -= self.lr * d
        return self

    def guardar(self, ruta):
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        json.dump({"lr": self.lr, "capas": self.capas}, open(ruta, "w"))

    @classmethod
    def cargar(cls, ruta):
        d = json.load(open(ruta))
        r = cls([1, 1])
        r.lr = d["lr"]
        r.capas = d["capas"]
        return r
