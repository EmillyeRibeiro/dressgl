"""D56: ruído de percepção sobre uma gravação física.

A física não muda. Muda só a posição que a estação *percebe* e, por
consequência, terrain.below. O modelo é Gauss-Markov de 1ª ordem por eixo,
amostrado a hz_sensor e mantido (sample-and-hold) entre amostras nos
quadros a hz_quadros.
"""
from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Zona:
    nome: str
    classe: str
    x: tuple[float, float]
    y: tuple[float, float]

    def contem(self, px: float, py: float) -> bool:
        return self.x[0] <= px <= self.x[1] and self.y[0] <= py <= self.y[1]


@dataclass(frozen=True)
class Percepcao:
    erro_pos_m: float = 0.0
    tau_s: float = 0.0          # 0 = ruído branco (na taxa do sensor)
    hz_sensor: float = 10.0
    hz_quadros: float = 60.0
    semente: int = 1

    def __post_init__(self):
        if self.erro_pos_m < 0 or self.tau_s < 0:
            raise ValueError("erro_pos_m e tau_s devem ser >= 0")
        if self.hz_sensor <= 0 or self.hz_quadros <= 0:
            raise ValueError("hz_sensor e hz_quadros devem ser > 0")


# ---------- zonas ----------

_CAMPOS_CLASSE = ("terreno", "classe", "tipo", "solo", "terrain")
_NOME_ZONA = re.compile(r"^zona_(\d+)_(\w+)$")


def _faixa(t: dict, eixo: str):
    v = t.get(eixo)
    if isinstance(v, list) and len(v) == 2 and all(isinstance(e, (int, float)) for e in v):
        return tuple(sorted(map(float, v)))
    lo, hi = t.get(f"{eixo}min"), t.get(f"{eixo}max")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return tuple(sorted((float(lo), float(hi))))
    return None


def _norm(classe: str) -> str:
    return classe.strip().upper().replace(" ", "_").replace("-", "_")


def _coletar(no, chave: str, acc: list[Zona]):
    if isinstance(no, dict):
        fx, fy = _faixa(no, "x"), _faixa(no, "y")
        if fx and fy:
            nome = no.get("nome") or no.get("name") or chave
            classe = next((no[c] for c in _CAMPOS_CLASSE if isinstance(no.get(c), str)), None)
            m = _NOME_ZONA.match(str(nome))
            if classe is None and m:
                classe = m.group(2)
            if classe:
                if not m:
                    nome = f"zona_{len(acc)}_{_norm(classe).lower()}"
                acc.append(Zona(str(nome), _norm(classe), fx, fy))
                return
        for k, v in no.items():
            _coletar(v, str(k), acc)
    elif isinstance(no, list):
        for v in no:
            _coletar(v, chave, acc)


def zonas_da_missao(missao: dict) -> list[Zona]:
    """Zonas na ordem do documento; a última zona que contém o ponto vence."""
    acc: list[Zona] = []
    _coletar(missao, "", acc)
    if not acc:
        raise ValueError(f"nenhuma zona encontrada; chaves da missão: {list(missao)}")
    return acc


def classificar(x: float, y: float, zonas: list[Zona], fora: str = "UNKNOWN") -> str:
    classe = fora
    for z in zonas:
        if z.contem(x, y):
            classe = z.classe
    return classe


# ---------- ruído ----------

def ruido_posicao(n: int, p: Percepcao) -> list[tuple[float, float]]:
    rng = random.Random(p.semente)
    passo = max(1, round(p.hz_quadros / p.hz_sensor))
    dt = passo / p.hz_quadros
    a = math.exp(-dt / p.tau_s) if p.tau_s > 0 else 0.0
    b = p.erro_pos_m * math.sqrt(1.0 - a * a)
    ex, ey = rng.gauss(0.0, 1.0) * p.erro_pos_m, rng.gauss(0.0, 1.0) * p.erro_pos_m
    saida = []
    for k in range(n):
        if k and k % passo == 0:
            ex = a * ex + b * rng.gauss(0.0, 1.0)
            ey = a * ey + b * rng.gauss(0.0, 1.0)
        saida.append((ex, ey))
    return saida


def aplicar(registros: list[dict], zonas: list[Zona], p: Percepcao) -> list[dict]:
    saida = []
    for r, (ex, ey) in zip(registros, ruido_posicao(len(registros), p)):
        x, y, *resto = r["pos"]
        px, py = x + ex, y + ey
        novo = dict(r)
        novo["pos_real"] = list(r["pos"])
        novo["terrain.below_real"] = r["terrain.below"]
        novo["pos"] = [px, py, *resto]
        novo["terrain.below"] = classificar(px, py, zonas)
        saida.append(novo)
    return saida


def percepcao_da_missao(missao: dict) -> tuple[Percepcao, str]:
    b = missao.get("percepcao")
    if not isinstance(b, dict) or "gravacao_base" not in b:
        raise ValueError("a missão precisa de um bloco [percepcao] com gravacao_base")
    p = Percepcao(
        erro_pos_m=float(b.get("erro_pos_m", 0.0)),
        tau_s=float(b.get("tau_s", 0.0)),
        hz_sensor=float(b.get("hz_sensor", 10.0)),
        hz_quadros=float(b.get("hz_quadros", 60.0)),
        semente=int(b.get("semente", 1)),
    )
    return p, str(b["gravacao_base"])


# ---------- E/S ----------

def ler_jsonl(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


def escrever_jsonl(caminho: Path, registros: list[dict]) -> None:
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def contar_trocas(registros: list[dict], campo: str = "terrain.below") -> int:
    return sum(a[campo] != b[campo] for a, b in zip(registros, registros[1:]))