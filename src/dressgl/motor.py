"""Motor de regras da DRESS-GL (P6).

A cada quadro o hospedeiro entrega as leituras (D21). O motor decide quais
regras ficam ativas (com cooldown, D24), compõe os efeitos delas num plano
(D22) e verifica os ASSERTs das regras aplicadas no quadro anterior (D25).

O motor é síncrono e não conhece o hospedeiro: recebe dicionários e devolve
dados imutáveis. Aplicar o plano é papel do hospedeiro (D26, D27).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .interpretador import (EfeitoHighlight, EfeitoInject, EfeitoMark,
                            EfeitoScale, EfeitoSet, EfeitoSuppress,
                            ProgramaExecutavel, RegraExecutavel)


def ordem(r: RegraExecutavel):
    """Maior prioridade primeiro; sem prioridade por último; empate pela
    linha no fonte (D22)."""
    return (r.prioridade is None, -(r.prioridade or 0), r.linha)

def _combinar(atual, novo):
    """D17: mínimo para números, conjunção para booleanos.
    Devolve None quando não há composição (enumerados ou tipos mistos)."""
    if isinstance(atual, bool) and isinstance(novo, bool):
        return atual and novo
    numero = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if numero(atual) and numero(novo):
        return min(atual, novo)
    return None

@dataclass(frozen=True)
class Conflito:
    alvo: str
    vencedora: str
    perdedora: str


@dataclass(frozen=True)
class Violacao:
    regra: str
    quadro: int            # quadro cujo plano violou o ASSERT


@dataclass(frozen=True)
class Plano:
    sets: dict             # (superfície, atributo) -> valor
    escalas: dict          # (recurso, nome) -> fator
    injecoes: tuple        # EfeitoInject
    supressoes: frozenset  # nomes de passos
    destaques: tuple       # EfeitoHighlight
    marcas: tuple          # EfeitoMark


def compor(regras: Iterable[RegraExecutavel]) -> tuple[Plano, tuple[Conflito, ...]]:
    sets, dono_set, escalas = {}, {}, {}
    passos = {}            # passo -> (efeito, regra dona)
    destaques, marcas, conflitos = [], [], []
    for r in sorted(regras, key=ordem):
        for ef in r.efeitos:
            if isinstance(ef, EfeitoSet):
                k = (ef.superficie, ef.atributo)
                if k not in sets:
                    sets[k], dono_set[k] = ef.valor, r.nome
                elif sets[k] != ef.valor:
                    combinado = _combinar(sets[k], ef.valor)
                    if combinado is None:
                        conflitos.append(Conflito(f"{k[0]}.{k[1]}", dono_set[k], r.nome))
                    else:
                        sets[k] = combinado
            elif isinstance(ef, EfeitoScale):
                k = (ef.recurso, ef.nome)
                escalas[k] = min(escalas[k], ef.fator) if k in escalas else ef.fator
            elif isinstance(ef, (EfeitoInject, EfeitoSuppress)):
                if ef.passo not in passos:
                    passos[ef.passo] = (ef, r.nome)
                elif passos[ef.passo][0] != ef:
                    conflitos.append(Conflito(f"pass {ef.passo}",
                                              passos[ef.passo][1], r.nome))
            elif isinstance(ef, EfeitoHighlight):
                if ef not in destaques:
                    destaques.append(ef)
            elif isinstance(ef, EfeitoMark):
                if ef not in marcas:
                    marcas.append(ef)
            else:
                raise TypeError(f"efeito desconhecido: {type(ef).__name__}")
    plano = Plano(
        sets, escalas,
        tuple(e for e, _ in passos.values() if isinstance(e, EfeitoInject)),
        frozenset(p for p, (e, _) in passos.items() if isinstance(e, EfeitoSuppress)),
        tuple(destaques), tuple(marcas))
    return plano, tuple(conflitos)


@dataclass(frozen=True)
class Registro:
    """Uma linha do trace (P7)."""
    quadro: int
    ativas: tuple[str, ...]
    ativadas: tuple[str, ...]
    desativadas: tuple[str, ...]
    retidas: tuple[str, ...]          # mudança adiada pelo cooldown
    conflitos: tuple[Conflito, ...]
    violacoes: tuple[Violacao, ...]
    plano: Plano


class Motor:
    def __init__(self, programa: ProgramaExecutavel):
        pol = programa.politica
        self.cooldown = (pol.cooldown_frames or 0) if pol else 0
        self.regras = tuple(sorted(programa.regras, key=ordem))
        self._ativa = [False] * len(self.regras)
        self._troca: list[int | None] = [None] * len(self.regras)
        self._aplicadas: tuple[RegraExecutavel, ...] = ()
        self.quadro = -1

    def passo(self, leituras: Mapping[str, object]) -> Registro:
        # Avalia tudo antes de alterar o estado: se faltar uma leitura
        # (ErroExecucao), o motor fica como estava.
        q = self.quadro + 1
        violacoes = tuple(Violacao(r.nome, q - 1) for r in self._aplicadas
                          if r.garantia(leituras) is False)
        desejos = [r.predicado(leituras) for r in self.regras]

        ativadas, desativadas, retidas = [], [], []
        for i, (r, desejado) in enumerate(zip(self.regras, desejos)):
            if desejado == self._ativa[i]:
                continue
            t = self._troca[i]
            if t is not None and q - t < self.cooldown:
                retidas.append(r.nome)
                continue
            self._ativa[i], self._troca[i] = desejado, q
            (ativadas if desejado else desativadas).append(r.nome)

        ativas = tuple(r for i, r in enumerate(self.regras) if self._ativa[i])
        plano, conflitos = compor(ativas)
        self._aplicadas, self.quadro = ativas, q
        return Registro(q, tuple(r.nome for r in ativas), tuple(ativadas),
                        tuple(desativadas), tuple(retidas), conflitos,
                        violacoes, plano)