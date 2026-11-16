"""Missão do drone (D50, D51): trajeto do alvo, zonas de solo e bateria modelada.

Puro Python: testável sem o CoppeliaSim e sem NumPy.
"""
from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dressgl.modelo import MODELO_PADRAO, carregar

HZ_QUADRO = 60


class ErroMissao(Exception):
    pass


@dataclass(frozen=True)
class Zona:
    solo: str
    x: tuple[float, float]
    y: tuple[float, float]

    def contem(self, px: float, py: float) -> bool:
        return self.x[0] <= px <= self.x[1] and self.y[0] <= py <= self.y[1]


@dataclass(frozen=True)
class Missao:
    nome: str
    quadros: int
    hz_sim: float
    velocidade_ms: float
    bateria_inicial: float
    consumo_pct_s: float
    zonas: tuple[Zona, ...]
    waypoints: tuple[tuple[float, float, float], ...]

    @property
    def quadros_por_passo(self) -> int:
        return round(HZ_QUADRO / self.hz_sim)

    def solo_em(self, x: float, y: float) -> str:
        """A última zona que contém o ponto vence (como os trechos da D28)."""
        for z in reversed(self.zonas):
            if z.contem(x, y):
                return z.solo
        raise ErroMissao(f"posição ({x:.2f}, {y:.2f}) fora de todas as zonas")

    def bateria_em(self, t: float) -> float:
        return min(100.0, max(0.0, self.bateria_inicial - self.consumo_pct_s * t))

    def alvo_em(self, t: float) -> tuple[float, float, float]:
        """Percorre os waypoints com velocidade constante e para no último."""
        restante = self.velocidade_ms * max(t, 0.0)
        for a, b in zip(self.waypoints, self.waypoints[1:]):
            d = math.dist(a, b)
            if d > 0 and restante <= d:
                f = restante / d
                return tuple(ai + (bi - ai) * f for ai, bi in zip(a, b))
            restante -= d
        return self.waypoints[-1]


def carregar_missao(caminho, modelo_toml=MODELO_PADRAO) -> Missao:
    caminho = Path(caminho)
    with open(caminho, "rb") as f:
        d = tomllib.load(f)
    solos = carregar(modelo_toml).telemetria["terrain.below"].valores

    hz = float(d.get("hz_sim", 20))
    if hz <= 0 or abs(HZ_QUADRO / hz - round(HZ_QUADRO / hz)) > 1e-9:
        raise ErroMissao(f"hz_sim = {hz} não divide {HZ_QUADRO} Hz")

    zonas = []
    for i, z in enumerate(d.get("zonas", ()), 1):
        if z.get("solo") not in solos:
            raise ErroMissao(f"zona {i}: solo {z.get('solo')!r} fora de {list(solos)}")
        x, y = tuple(map(float, z["x"])), tuple(map(float, z["y"]))
        if len(x) != 2 or len(y) != 2 or x[0] > x[1] or y[0] > y[1]:
            raise ErroMissao(f"zona {i}: intervalos inválidos")
        zonas.append(Zona(z["solo"], x, y))
    if not zonas:
        raise ErroMissao("a missão precisa de pelo menos uma zona")

    wps = tuple(tuple(map(float, w["pos"])) for w in d.get("waypoints", ()))
    if not wps or any(len(w) != 3 for w in wps):
        raise ErroMissao("waypoints precisam de pos = [x, y, z]")

    b = d.get("bateria", {})
    ini = float(b.get("inicial", 100.0))
    if not 0 <= ini <= 100:
        raise ErroMissao(f"bateria inicial {ini} fora de [0, 100]")

    return Missao(d.get("nome", caminho.stem), int(d["quadros"]), hz,
                  float(d.get("velocidade_ms", 0.5)), ini,
                  float(b.get("consumo_pct_s", 0.0)), tuple(zonas), wps)