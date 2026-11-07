"""Procedimento de decisão para expressões da DRESS-GL (V6, V7) e avaliador
reutilizável pelo interpretador (P5/P6).

Cada átomo compara UMA variável com UMA constante (a Listagem 2 não tem
aritmética nem comparação entre variáveis). O valor-verdade de um átomo só
muda nas constantes da expressão; basta testar um representante por região:
  - booleano e enumerado: o domínio inteiro (finito);
  - número com lista de valores: a própria lista (Seção II-C, vi);
  - número contínuo: cada constante, o ponto médio entre constantes
    consecutivas, um ponto além de cada extremo e os limites min/max.
Avaliar a expressão em todas as combinações decide a satisfatibilidade de
forma exata. O custo cresce exponencialmente com o número de variáveis
distintas, que é pequeno numa regra; acima de LIMITE a resposta é None.
"""

from __future__ import annotations

import operator
from itertools import product
from math import prod

from .parser import Comparacao, E, Nao, Ou, Pertinencia, Referencia

OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
       ">=": operator.ge, "==": operator.eq, "!=": operator.ne}
LIMITE = 100_000


def chave(ref: Referencia) -> tuple:
    return (ref.alvo, ref.nome, ref.campo)


def atomos(e):
    """Comparações e pertinências de uma expressão, da esquerda para a direita."""
    if isinstance(e, (Ou, E)):
        yield from atomos(e.esq)
        yield from atomos(e.dir)
    elif isinstance(e, Nao):
        yield from atomos(e.expr)
    else:
        yield e


def avaliar(e, valores: dict) -> bool:
    """Valor-verdade de e; valores mapeia chave(ref) -> valor corrente."""
    if isinstance(e, Ou):
        return avaliar(e.esq, valores) or avaliar(e.dir, valores)
    if isinstance(e, E):
        return avaliar(e.esq, valores) and avaliar(e.dir, valores)
    if isinstance(e, Nao):
        return not avaliar(e.expr, valores)
    v = valores[chave(e.ref)]
    if isinstance(e, Pertinencia):
        return v in e.valores
    return OPS[e.op](v, e.valor.valor)


def _representantes(dom, constantes) -> list:
    if dom.tipo == "bool":
        return [False, True]
    if dom.tipo == "enum":
        return list(dom.valores)
    if dom.tipo != "num":
        return []
    if dom.valores:
        return sorted(set(dom.valores))
    pts = sorted(set(constantes))
    reps = set(pts)
    reps.update((a + b) / 2 for a, b in zip(pts, pts[1:]))
    if pts:
        reps.update((pts[0] - 1, pts[-1] + 1))
    lo, hi = dom.minimo, dom.maximo
    reps.update(x for x in (lo, hi) if x is not None)
    return sorted(x for x in reps
                  if (lo is None or x >= lo) and (hi is None or x <= hi))


def satisfazivel(e, dominio) -> bool | None:
    """True/False exatos; None se o espaço passar de LIMITE combinações.
    dominio(ref) devolve o Dominio de uma referência já validada."""
    doms, consts = {}, {}
    for a in atomos(e):
        k = chave(a.ref)
        d = dominio(a.ref)
        if d is None:
            return None
        doms[k] = d
        if isinstance(a, Comparacao) and a.valor.tipo == "NUM":
            consts.setdefault(k, set()).add(a.valor.valor)
    chaves = list(doms)
    reps = [_representantes(doms[k], consts.get(k, ())) for k in chaves]
    if prod(len(r) for r in reps) > LIMITE:
        return None
    return any(avaliar(e, dict(zip(chaves, c))) for c in product(*reps))