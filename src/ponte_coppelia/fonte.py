"""Entradas vindas do CoppeliaSim (D49, D50) e gravação/repetição (D52)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dressgl.simulador import Cenario

from .missao import HZ_QUADRO, ErroMissao, Missao

ENTRADAS = ("drone.battery", "terrain.below")


class Sessao(Protocol):
    dt: float                                    # passo da física, em s
    def mover_alvo(self, xyz) -> None: ...
    def passo(self) -> None: ...
    def estado(self) -> tuple[float, tuple[float, float, float]]: ...   # (t, posição)


class EntradasCoppelia:
    """entradas[q] avança a simulação até o quadro q (acesso em ordem).
    Um passo da física a cada `quadros_por_passo` quadros; entre passos,
    vale a última leitura (amostra e retém, D50)."""

    def __init__(self, sessao: Sessao, missao: Missao):
        if abs(sessao.dt - 1 / missao.hz_sim) > 1e-6:
            raise ErroMissao(f"passo da cena = {sessao.dt * 1000:.1f} ms, mas a missão "
                             f"pede {1000 / missao.hz_sim:.1f} ms (hz_sim)")
        self.s, self.m = sessao, missao
        self.k = missao.quadros_por_passo
        self.registros: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return self.m.quadros

    def __getitem__(self, q: int) -> dict:
        if q == len(self.registros) - 1:          # mesmo quadro de novo
            return self._entrada(self.registros[q])
        if q != len(self.registros):
            raise ErroMissao(f"quadro {q} fora de ordem; esperado {len(self.registros)}")
        if q == 0:
            alvo = self.m.alvo_em(0.0)
            self.s.mover_alvo(alvo)
            t, pos = self.s.estado()
        elif q % self.k == 0:
            alvo = self.m.alvo_em(self.registros[-1]["t"] + self.s.dt)
            self.s.mover_alvo(alvo)
            self.s.passo()
            t, pos = self.s.estado()
        else:
            ant = self.registros[-1]
            t, pos, alvo = ant["t"], tuple(ant["pos"]), tuple(ant["alvo"])
        reg = {"quadro": q, "t": t, "pos": list(pos), "alvo": list(alvo),
               "solo_alvo": self.m.solo_em(alvo[0], alvo[1]),          # D53
               "drone.battery": self.m.bateria_em(t),
               "terrain.below": self.m.solo_em(pos[0], pos[1])}
        self.registros.append(reg)
        return self._entrada(reg)

    @staticmethod
    def _entrada(reg: dict) -> dict:
        return {k: reg[k] for k in ENTRADAS}


@dataclass
class CenarioCoppelia:
    """Tem os atributos que executar e os hospedeiros usam de um Cenario."""
    nome: str
    quadros: int
    entradas: EntradasCoppelia
    semente: int = 0
    ruido_ms: float = 0.0


def gravar(caminho, registros) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def carregar_gravacao(caminho) -> Cenario:
    """D52: a gravação vira um Cenario comum, que roda sem o CoppeliaSim."""
    caminho = Path(caminho)
    with open(caminho, encoding="utf-8") as f:
        regs = [json.loads(s) for s in f if s.strip()]
    for i, r in enumerate(regs):
        if r["quadro"] != i:
            raise ErroMissao(f"{caminho}: quadro {r['quadro']} na linha {i + 1}")
    entradas = tuple({k: r[k] for k in ENTRADAS} for r in regs)
    return Cenario(caminho.stem.removeprefix("gravacao_"), len(regs), entradas)