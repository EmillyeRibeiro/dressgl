"""Back end da DRESS-GL (P5): compila um programa validado em regras
executáveis, cada uma um par condição/efeitos (D19).

Só gera código para programas sem erros (D20): diagnósticos léxicos ou
sintáticos interrompem antes da semântica, evitando erros em cascata sobre
uma AST parcial; erros semânticos interrompem antes da geração. Avisos não
bloqueiam.

Os efeitos são dados imutáveis: compilar não altera o hospedeiro. Aplicá-los
e compor regras ativas ao mesmo tempo é papel do motor (P6).
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass, field

from .decisao import atomos, avaliar, chave
from .modelo import MODELO_PADRAO, ErroModelo, carregar
from .modelo import Modelo
from .parser import (AcaoHighlight, AcaoInject, AcaoMark, AcaoScale, AcaoSet,
                     AcaoSuppress, Politica, Programa, Referencia, Regra, analisar)
from .semantica import verificar


class ErroCompilacao(Exception):
    def __init__(self, diagnosticos: list[str]):
        self.diagnosticos = list(diagnosticos)
        super().__init__(f"{len(self.diagnosticos)} erro(s); nada foi gerado:\n"
                         + "\n".join(self.diagnosticos))


class ErroExecucao(Exception):
    pass


def variavel(ref: Referencia) -> str:
    """Nome da leitura que o hospedeiro fornece para uma referência (D21).
    drone.battery -> "drone.battery"; frame_budget -> "frame_budget";
    view "FPV".scale -> "view:FPV.scale"."""
    if ref.alvo == "view":
        return f"view:{ref.nome}.{ref.campo}"
    return ref.nome if ref.campo is None else f"{ref.nome}.{ref.campo}"


# ----- efeitos (representação intermediária) ------------------------------
# linha não participa da igualdade: dois efeitos iguais em linhas diferentes
# são o mesmo efeito para o motor; a linha serve à rastreabilidade (P7).

@dataclass(frozen=True)
class EfeitoSet:
    superficie: str
    atributo: str
    valor: object
    linha: int = field(default=0, compare=False)

@dataclass(frozen=True)
class EfeitoScale:
    recurso: str           # "instances" ou "resolution"
    nome: str
    fator: float
    linha: int = field(default=0, compare=False)

@dataclass(frozen=True)
class EfeitoInject:
    passo: str
    fase: str              # "BEFORE" ou "AFTER"
    ancora: str
    linha: int = field(default=0, compare=False)

@dataclass(frozen=True)
class EfeitoSuppress:
    passo: str
    linha: int = field(default=0, compare=False)

@dataclass(frozen=True)
class EfeitoHighlight:
    extremo: str           # "ARGMAX" ou "ARGMIN"
    campo: str             # nome da leitura do campo escalar
    raio_m: float | None
    linha: int = field(default=0, compare=False)

@dataclass(frozen=True)
class EfeitoMark:
    tipo: str              # "view" ou "pass"
    nome: str
    linha: int = field(default=0, compare=False)


# ----- condições ----------------------------------------------------------

@dataclass(frozen=True)
class Condicao:
    """Expressão GIVEN/ASSERT ligada às leituras de que depende."""
    expr: object = field(repr=False)
    mapa: tuple                    # ((chave da AST, nome da leitura), ...)

    @property
    def variaveis(self) -> frozenset[str]:
        return frozenset(nome for _, nome in self.mapa)

    def __call__(self, leituras: Mapping[str, object]) -> bool:
        valores = {}
        for k, nome in self.mapa:
            if nome not in leituras:
                raise ErroExecucao(f"leitura ausente: {nome}")
            valores[k] = leituras[nome]
        return avaliar(self.expr, valores)


def _condicao(expr) -> Condicao:
    mapa: dict[tuple, str] = {}
    for a in atomos(expr):
        mapa.setdefault(chave(a.ref), variavel(a.ref))
    return Condicao(expr, tuple(mapa.items()))


# ----- programa executável ------------------------------------------------

@dataclass(frozen=True)
class RegraExecutavel:
    nome: str
    prioridade: int | None
    juncao: tuple[str, str]        # (fase, passo)
    efeitos: tuple
    linha: int
    condicao: Condicao
    contrato: Condicao | None

    @property
    def variaveis(self) -> frozenset[str]:
        return self.condicao.variaveis

    @property
    def variaveis_garantia(self) -> frozenset[str]:
        return self.contrato.variaveis if self.contrato else frozenset()

    def predicado(self, leituras: Mapping[str, object]) -> bool:
        return self.condicao(leituras)

    def garantia(self, leituras: Mapping[str, object]) -> bool | None:
        """None se a regra não tem ASSERT."""
        return None if self.contrato is None else self.contrato(leituras)


@dataclass(frozen=True)
class PoliticaExecutavel:
    nome: str
    budget_ms: float
    reserve_ms: float | None
    cooldown_frames: int | None


@dataclass(frozen=True)
class ProgramaExecutavel:
    politica: PoliticaExecutavel | None
    regras: tuple[RegraExecutavel, ...]


def _efeito(a):
    lin = a.pos[0]
    if isinstance(a, AcaoSet):
        return EfeitoSet(a.alvo.nome, a.atributo, a.valor.valor, lin)
    if isinstance(a, AcaoScale):
        return EfeitoScale(a.recurso, a.nome, a.fator.valor, lin)
    if isinstance(a, AcaoInject):
        return EfeitoInject(a.passo, a.fase, a.ancora, lin)
    if isinstance(a, AcaoSuppress):
        return EfeitoSuppress(a.passo, lin)
    if isinstance(a, AcaoHighlight):
        raio = None if a.raio is None else a.raio.valor
        return EfeitoHighlight(a.extremo, variavel(a.ref), raio, lin)
    if isinstance(a, AcaoMark):
        return EfeitoMark(a.alvo.tipo, a.alvo.nome, lin)
    raise TypeError(f"ação desconhecida: {type(a).__name__}")


def _politica(p: Politica) -> PoliticaExecutavel:
    v = {a.param: a.valor.valor for a in p.atribs}   # budget garantido por C2
    return PoliticaExecutavel(p.nome, v["budget"], v.get("reserve"), v.get("cooldown"))


def _regra(r: Regra) -> RegraExecutavel:
    return RegraExecutavel(
        nome=r.nome, prioridade=r.prioridade,
        juncao=(r.quando.fase, r.quando.passo),
        efeitos=tuple(_efeito(a) for a in r.entao), linha=r.pos[0],
        condicao=_condicao(r.dado),
        contrato=None if r.garantia is None else _condicao(r.garantia))


def gerar(prog: Programa) -> ProgramaExecutavel:
    """Supõe programa já validado; use compilar_programa."""
    politicas = [d for d in prog.declaracoes if isinstance(d, Politica)]
    regras = [d for d in prog.declaracoes if isinstance(d, Regra)]
    return ProgramaExecutavel(_politica(politicas[0]) if politicas else None,
                              tuple(_regra(r) for r in regras))


def compilar_programa(fonte: str, modelo: Modelo) -> ProgramaExecutavel:
    prog, diags = analisar(fonte)
    if diags:
        raise ErroCompilacao(diags)
    erros = [str(d) for d in verificar(prog, modelo) if d.nivel == "erro"]
    if erros:
        raise ErroCompilacao(erros)
    return gerar(prog)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dressgl.interpretador")
    ap.add_argument("arquivo")
    ap.add_argument("--modelo", default=str(MODELO_PADRAO))
    args = ap.parse_args(argv)
    try:
        modelo = carregar(args.modelo)
    except ErroModelo as e:
        print(f"{args.modelo}: erro no modelo: {e}")
        return 2
    with open(args.arquivo, encoding="utf-8-sig") as f:
        fonte = f.read()
    try:
        prog = compilar_programa(fonte, modelo)
    except ErroCompilacao as e:
        for d in e.diagnosticos:
            print(f"{args.arquivo}:{d}")
        return 1
    for r in prog.regras:
        fase, passo = r.juncao
        print(f'RULE {r.nome} (linha {r.linha}, prioridade {r.prioridade}) '
              f'{fase} pass "{passo}"')
        print(f"  GIVEN lê: {', '.join(sorted(r.variaveis))}")
        for ef in r.efeitos:
            print(f"  {ef}")
        if r.contrato is not None:
            print(f"  ASSERT lê: {', '.join(sorted(r.variaveis_garantia))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())