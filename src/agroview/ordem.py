"""Ordem dos passos (D44) e decimação por hz (D43) no hospedeiro AgroView.

Não importa numpy: testável sem o extra [render].
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


class ErroOrdem(Exception):
    """INJECT cuja âncora não está entre os passos executados."""


def ordem_passos(padrao: Sequence[str], supressoes: Iterable[str],
                 injecoes: Iterable) -> list[str]:
    """D44: passos padrão na ordem do modelo, menos os SUPPRESS; cada INJECT
    entra junto à âncora. Uma injeção pode ancorar em outra injeção. Com
    várias injeções na mesma âncora, a de maior prioridade fica mais perto
    dela (plano.injecoes vem de compor, em ordem de prioridade)."""
    sup = set(supressoes)
    ordem = [p for p in padrao if p not in sup]
    pendentes = list(reversed(list(injecoes)))
    while pendentes:
        resto = []
        for inj in pendentes:
            if inj.ancora not in ordem:
                resto.append(inj)
                continue
            i = ordem.index(inj.ancora)
            ordem.insert(i + 1 if inj.fase == "AFTER" else i, inj.passo)
        if len(resto) == len(pendentes):
            faltam = "; ".join(f"{j.passo} {j.fase} {j.ancora}" for j in resto)
            raise ErroOrdem(f"âncora fora dos passos executados: {faltam}")
        pendentes = resto
    return ordem


def periodo(hz: float, hz_tela: int = 60) -> int:
    """D43: a superfície é desenhada a cada `periodo` quadros."""
    if hz <= 0:
        raise ValueError(f"hz deve ser positivo: {hz}")
    return max(1, round(hz_tela / hz))


def desenha(quadro: int, hz: float, hz_tela: int = 60) -> bool:
    """D43: decimação real. Fase fixa em q = 0, determinística."""
    return quadro % periodo(hz, hz_tela) == 0