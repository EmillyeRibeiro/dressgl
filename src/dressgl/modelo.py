"""Tabela de símbolos do sistema hospedeiro (P3), lida de modelo/agroview.toml.

O modelo é validado ao ser carregado: um atributo cujo nome a DRESS-GL não
consegue escrever (palavra reservada, CAIXA_ALTA) é rejeitado aqui, e não
quando alguém tentar usá-lo numa regra.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .lexer import UNIDADES, TipoToken as T, tokenizar

MODELO_PADRAO = Path(__file__).resolve().parents[2] / "modelo" / "agroview.toml"
CRITICIDADES = ("CRITICA", "ALTA", "MEDIA", "BAIXA")


class ErroModelo(Exception):
    pass


@dataclass(frozen=True)
class Dominio:
    tipo: str                    # "bool", "enum", "num" ou "campo"
    unidade: str | None = None
    valores: tuple = ()          # enumerados ou valores numéricos permitidos
    minimo: float | None = None
    maximo: float | None = None


@dataclass(frozen=True)
class Superficie:
    nome: str
    criticidade: str
    atributos: dict[str, Dominio]


@dataclass(frozen=True)
class Modelo:
    superficies: dict[str, Superficie]
    passos: frozenset[str]
    instancias: dict[str, str]   # nome -> passo que as desenha
    telemetria: dict[str, Dominio]


_CLASSE = {T.PALAVRA_RESERVADA: "palavra reservada", T.ENUM: "enumerado",
           T.BOOL: "booleano", T.NUM: "número"}


def _exigir_ident(onde: str, nome: str) -> None:
    toks = tokenizar(nome)
    if len(toks) == 2 and toks[0].tipo is T.IDENT:
        return
    tipo = _CLASSE.get(toks[0].tipo, "não é identificador") if len(toks) == 2 \
        else "não é um único identificador"
    raise ErroModelo(f"{onde}: {nome!r} não pode ser escrito na DRESS-GL "
                     f"({tipo}); use minúsculas e evite palavras reservadas")


def _dominio(onde: str, d) -> Dominio:
    if not isinstance(d, dict):
        raise ErroModelo(f"{onde}: esperada uma tabela")
    if "tipo" in d:
        if d["tipo"] != "bool":
            raise ErroModelo(f"{onde}: tipo desconhecido {d['tipo']!r}")
        return Dominio("bool")
    if "enum" in d:
        for v in d["enum"]:
            toks = tokenizar(v)
            if not (len(toks) == 2 and toks[0].tipo is T.ENUM):
                raise ErroModelo(f"{onde}: {v!r} não é enumerado (CAIXA_ALTA)")
        return Dominio("enum", valores=tuple(d["enum"]))
    if d.get("campo_escalar"):
        return Dominio("campo")
    unidade = d.get("unidade")
    if unidade is not None and unidade not in UNIDADES:
        raise ErroModelo(f"{onde}: unidade {unidade!r} não existe no léxico; "
                         f"use uma de {', '.join(UNIDADES)}")
    return Dominio("num", unidade, tuple(d.get("valores", ())),
                   d.get("min"), d.get("max"))


def construir(dados: dict) -> Modelo:
    superficies = {}
    for nome, s in dados.get("superficies", {}).items():
        crit = s.get("criticidade")
        if crit not in CRITICIDADES:
            raise ErroModelo(f"superficies.{nome}: criticidade {crit!r} inválida; "
                             f"use uma de {', '.join(CRITICIDADES)}")
        atribs = {}
        for a, d in s.get("atributos", {}).items():
            onde = f"superficies.{nome}.atributos.{a}"
            _exigir_ident(onde, a)
            atribs[a] = _dominio(onde, d)
        superficies[nome] = Superficie(nome, crit, atribs)

    passos = frozenset(dados.get("passos", {}).get("nomes", []))

    instancias = {}
    for nome, d in dados.get("instancias", {}).items():
        passo = d.get("passo")
        if passo not in passos:
            raise ErroModelo(f"instancias.{nome}: passo {passo!r} não declarado em [passos]")
        instancias[nome] = passo

    telemetria = {}
    for chave, d in dados.get("telemetria", {}).items():
        partes = chave.split(".")
        if len(partes) > 2:
            raise ErroModelo(f"telemetria.{chave}: no máximo um ponto (objeto.campo)")
        for p in partes:
            _exigir_ident(f"telemetria.{chave}", p)
        telemetria[chave] = _dominio(f"telemetria.{chave}", d)

    return Modelo(superficies, passos, instancias, telemetria)


def carregar(caminho=MODELO_PADRAO) -> Modelo:
    with open(caminho, "rb") as f:
        return construir(tomllib.load(f))