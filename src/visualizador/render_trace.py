"""Reconstrói as superfícies do AgroView a partir dos planos gravados (D40, D62 plano B).

O quadro q é desenhado com o plano do quadro q-1, e o quadro 0 com o PLANO_VAZIO (D40).
O render não tem estado entre quadros: a imagem de uma superfície depende só da
lista de Passo dela. Por isso cada lista distinta é renderizada uma única vez (cache).
"""
from __future__ import annotations

import dataclasses
import enum
import typing
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from dressgl.interpretador import EfeitoHighlight, EfeitoInject, EfeitoMark
from dressgl.motor import Plano
from dressgl.simulador import PLANO_VAZIO

RAIZ = Path(__file__).resolve().parents[2]
CALIBRACAO = RAIZ / "results" / "calibracao.toml"   # o mesmo de ponte_coppelia.experimentos


def _chave(s: str) -> tuple[str, str]:
    a, b = s.split(".", 1)
    return a, b


def _enum_de(t) -> type[enum.Enum] | None:
    for c in (t, *typing.get_args(t)):
        if isinstance(c, type) and issubclass(c, enum.Enum):
            return c
    return None


def _efeito(cls, d: Mapping[str, Any]):
    """Inverso do para_json para um efeito: enum pelo nome, lista vira tupla."""
    try:
        dicas = typing.get_type_hints(cls)
    except Exception:
        dicas = {}
    kw = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            continue                                 # campo com default
        v = d[f.name]
        e = _enum_de(dicas.get(f.name))
        if e is not None and isinstance(v, str):
            v = e[v]
        elif isinstance(v, list):
            v = tuple(v)
        kw[f.name] = v
    return cls(**kw)


def plano_de(d: Mapping[str, Any] | None) -> Plano:
    """Plano a partir do dicionário gravado no trace."""
    if not d:
        return PLANO_VAZIO
    return Plano(
        sets={_chave(k): v for k, v in d.get("sets", {}).items()},
        escalas={_chave(k): v for k, v in d.get("escalas", {}).items()},
        injecoes=tuple(_efeito(EfeitoInject, e) for e in d.get("injecoes", ())),
        supressoes=frozenset(d.get("supressoes", ())),
        destaques=tuple(_efeito(EfeitoHighlight, e) for e in d.get("destaques", ())),
        marcas=tuple(_efeito(EfeitoMark, e) for e in d.get("marcas", ())),
    )


class ReprodutorAgroView:
    def __init__(self, calibracao: Path = CALIBRACAO, semente: int = 0):
        from agroview.calibracao import carregar_calibracao   # extra [render]
        from agroview.hospedeiro import HospedeiroAgroView
        # O cenário só é usado em leituras(); passos() não precisa dele.
        self.h = HospedeiroAgroView(None, relogio="carga", semente=semente,
                                    ms_por_carga=carregar_calibracao(calibracao))
        self._cache: dict[tuple, tuple[Any, tuple]] = {}

    def quadro(self, indice: int, plano: Plano) -> tuple[dict[str, Any], float]:
        """(imagens das superfícies desenhadas neste quadro, frame_budget recalculado)."""
        por_sup: dict[str, list] = {}
        for p in self.h.passos(indice, plano):
            por_sup.setdefault(p.superficie, []).append(p)
        imagens, execucoes = {}, []
        for sup, lista in por_sup.items():
            k = tuple(lista)
            if k not in self._cache:
                q = self.h.render.quadro(lista)
                self._cache[k] = (q.imagens[sup], tuple(q.execucoes))
            img, ex = self._cache[k]
            imagens[sup] = img
            execucoes.extend(ex)
        return imagens, self.h._tempo_por_carga(execucoes)


@lru_cache(maxsize=None)
def reprodutor(semente: int = 0) -> ReprodutorAgroView:
    """Um por semente: o 'reiniciar' da janela não perde o cache."""
    return ReprodutorAgroView(semente=semente)