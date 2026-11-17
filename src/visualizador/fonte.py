"""Adaptador entre os traces gravados e a janela (D62, plano B). Não importa tkinter.

A janela reproduz results/trace_coppelia_<hospedeiro>__<programa>__<gravacao>.jsonl,
os mesmos arquivos que geraram metricas_coppelia.csv. A posição real vem de
results/gravacao_<gravacao>.jsonl, casada pelo número do quadro.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

# src/visualizador/fonte.py -> raiz do repositório
RAIZ = Path(__file__).resolve().parents[2]
MISSOES = RAIZ / "examples" / "missoes"
RESULTADOS = RAIZ / "results"
GRAVACOES = ("borda_agua", "pouso_agua")
PROGRAMAS = ("dsl", "baseline", "dsl_sem_cooldown", "multiplas")
HOSPEDEIROS = ("agroview", "simulado")


def carregar_missao(nome: str) -> dict[str, Any]:
    """Lê examples/missoes/<nome>.toml (quadros, zonas, waypoints)."""
    caminho = MISSOES / f"{nome}.toml"
    with caminho.open("rb") as f:
        return tomllib.load(f)


def caminho_trace(gravacao: str, programa: str, hospedeiro: str) -> Path:
    return RESULTADOS / f"trace_coppelia_{hospedeiro}__{programa}__{gravacao}.jsonl"


def caminho_gravacao(gravacao: str) -> Path:
    return RESULTADOS / f"gravacao_{gravacao}.jsonl"


@dataclass(frozen=True)
class QuadroVisual:
    indice: int
    leituras: Mapping[str, object]          # inclui frame_budget, drone.battery, terrain.below
    ativas: tuple[str, ...]
    retidas: tuple[str, ...]
    conflitos: int
    violacoes: int
    plano: Mapping[str, object]             # para HIGHLIGHT/MARK (D64)
    imagens: Mapping[str, object] = field(default_factory=dict)  # só as superfícies redesenhadas
    pos_real: tuple[float, ...] | None = None        # (x, y) ou (x, y, z) em metros
    pos_percebida: tuple[float, ...] | None = None


def _linhas(caminho: Path) -> Iterator[dict[str, Any]]:
    with caminho.open(encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                yield json.loads(linha)
            except json.JSONDecodeError as e:
                raise ValueError(f"{caminho.name}, linha {n}: {e}") from None


def _posicoes(gravacao: str) -> dict[int, tuple[float, ...]]:
    caminho = caminho_gravacao(gravacao)
    if not caminho.exists():
        return {}                       # sem gravação: o mapa fica sem o ponto preto
    return {int(r["quadro"]): tuple(float(v) for v in r["pos"])
            for r in _linhas(caminho) if "pos" in r}


def quadros(gravacao: str, programa: str, hospedeiro: str = "agroview",
            erro_pos_m: float = 0.0, semente: int = 0) -> Iterator[QuadroVisual]:
    """Valida na chamada (e não no primeiro next) e devolve o gerador de quadros."""
    if erro_pos_m:
        raise NotImplementedError(
            "erro_pos_m > 0 exige o laço ao vivo (D62); os traces gravados são sem ruído")
    caminho = caminho_trace(gravacao, programa, hospedeiro)
    if not caminho.exists():
        raise FileNotFoundError(f"trace não encontrado: {caminho}")
    return _gerar(caminho, _posicoes(gravacao))


def _gerar(caminho: Path, pos: dict[int, tuple[float, ...]]) -> Iterator[QuadroVisual]:
    for r in _linhas(caminho):
        i = int(r["quadro"])
        yield QuadroVisual(
            indice=i,
            leituras=r["leituras"],
            ativas=tuple(str(a) for a in r.get("ativas", ())),
            retidas=tuple(str(a) for a in r.get("retidas", ())),
            conflitos=len(r.get("conflitos", ())),
            violacoes=len(r.get("violacoes", ())),
            plano=r.get("plano", {}),
            pos_real=pos.get(i),
        )