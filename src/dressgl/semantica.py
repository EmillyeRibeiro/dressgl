"""Análise semântica da DRESS-GL (P4) sobre a tabela de símbolos (P3).

Percorre a AST de parser.py e confere referências, unidades e valores
contra o modelo do hospedeiro. Nenhuma verificação interrompe as demais:
todos os problemas são relatados de uma vez, como no léxico e no sintático.
"""

from __future__ import annotations

import argparse
import operator
from dataclasses import dataclass

from .modelo import MODELO_PADRAO, Dominio, ErroModelo, Modelo, Superficie, carregar
from .parser import (AcaoHighlight, AcaoInject, AcaoMark, AcaoScale, AcaoSet,
                     AcaoSuppress, Comparacao, E, Literal, Nao, Ou, Pertinencia,
                     Politica, Pos, Programa, Referencia, Regra, analisar)

PARAMS_POLITICA = {"budget": "ms", "reserve": "ms", "cooldown": "frames"}
UNIDADE_RAIO = "m"
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
       ">=": operator.ge, "==": operator.eq, "!=": operator.ne}
IGUALDADE = ("==", "!=")


@dataclass(frozen=True)
class Diagnostico:
    pos: Pos
    codigo: str
    mensagem: str
    nivel: str = "erro"

    def __str__(self) -> str:
        return (f"{self.pos[0]}:{self.pos[1]}: {self.nivel} semântico "
                f"[{self.codigo}]: {self.mensagem}")


def _txt(lit: Literal) -> str:
    if lit.tipo == "BOOL":
        return "true" if lit.valor else "false"
    if lit.tipo == "STRING":
        return f'"{lit.valor}"'
    return f"{lit.valor} {lit.unidade}" if lit.unidade else str(lit.valor)


def _lista(itens) -> str:
    return ", ".join(map(str, itens)) or "nenhum"


def _conjuncoes(e):
    """Termos ligados por AND no nível externo; OR e NOT ficam inteiros."""
    if isinstance(e, E):
        yield from _conjuncoes(e.esq)
        yield from _conjuncoes(e.dir)
    else:
        yield e


class Verificador:
    def __init__(self, modelo: Modelo):
        self.m = modelo
        self.diags: list[Diagnostico] = []

    def _erro(self, pos, codigo, msg):
        self.diags.append(Diagnostico(pos, codigo, msg))

    def _aviso(self, pos, codigo, msg):
        self.diags.append(Diagnostico(pos, codigo, msg, "aviso"))

    # ----- programa -------------------------------------------------------

    def verificar(self, prog: Programa) -> list[Diagnostico]:
        politicas = [d for d in prog.declaracoes if isinstance(d, Politica)]
        regras = [d for d in prog.declaracoes if isinstance(d, Regra)]
        for p in politicas[1:]:
            self._erro(p.pos, "V7", "só pode haver uma POLICY por programa "
                       f"(a primeira está na linha {politicas[0].pos[0]})")
        for p in politicas:
            self._politica(p)
        nomes: dict[str, Pos] = {}
        for r in regras:
            if r.nome in nomes:
                self._erro(r.pos, "V8", f"regra {r.nome} já declarada "
                           f"na linha {nomes[r.nome][0]}")
            nomes.setdefault(r.nome, r.pos)
            self._regra(r)
        self._conflitos(regras)
        return sorted(self.diags, key=lambda d: d.pos)

    def _politica(self, p: Politica) -> None:
        presentes: set[str] = set()
        validos: dict[str, Literal] = {}
        for a in p.atribs:
            if a.param in presentes:
                self._erro(a.pos, "V7", f"{a.param} definido mais de uma vez")
                continue
            presentes.add(a.param)
            if a.valor.tipo != "NUM":
                self._erro(a.valor.pos, "V3", f"{a.param} espera um número")
            elif self._unidade(a.valor, PARAMS_POLITICA[a.param], a.param):
                validos[a.param] = a.valor
        if "budget" not in presentes:
            self._erro(p.pos, "V7", "POLICY sem budget (orçamento de quadro)")
        b, r = validos.get("budget"), validos.get("reserve")
        if b is not None and r is not None and r.valor >= b.valor:
            self._erro(r.pos, "V7", f"reserve ({_txt(r)}) deve ser menor "
                       f"que budget ({_txt(b)})")

    def _regra(self, r: Regra) -> None:
        self._expr(r.dado)
        self._passo(r.quando.passo, r.quando.pos)
        for a in r.entao:
            self._acao(a)
        if r.garantia is not None:
            self._expr(r.garantia)
            self._garantia(r)

    # ----- resolução de nomes (V1) ----------------------------------------

    def _passo(self, nome: str, pos: Pos) -> bool:
        if nome in self.m.passos:
            return True
        self._erro(pos, "V1", f'passo "{nome}" não existe no modelo; '
                   f"disponíveis: {_lista(sorted(self.m.passos))}")
        return False

    def _superficie(self, nome: str, pos: Pos) -> Superficie | None:
        s = self.m.superficies.get(nome)
        if s is None:
            self._erro(pos, "V1", f'superfície "{nome}" não existe no modelo; '
                       f"disponíveis: {_lista(sorted(self.m.superficies))}")
        return s

    def _resolver(self, ref: Referencia) -> tuple[Dominio, str] | None:
        if ref.alvo == "view":
            s = self._superficie(ref.nome, ref.pos)
            if s is None:
                return None
            nome = f'view "{ref.nome}".{ref.campo}'
            dom = s.atributos.get(ref.campo)
            if dom is None:
                self._erro(ref.pos, "V1", f'superfície "{ref.nome}" não tem '
                           f"atributo {ref.campo}; disponíveis: "
                           f"{_lista(sorted(s.atributos))}")
                return None
            return dom, nome
        if ref.alvo == "pass":
            if self._passo(ref.nome, ref.pos):
                self._erro(ref.pos, "V1", "o modelo não declara atributos de passos")
            return None
        chave = ref.nome if ref.campo is None else f"{ref.nome}.{ref.campo}"
        dom = self.m.telemetria.get(chave)
        if dom is None:
            self._erro(ref.pos, "V1", f"telemetria {chave} não existe no modelo; "
                       f"disponíveis: {_lista(sorted(self.m.telemetria))}")
            return None
        return dom, chave

    # ----- unidades (V2) e domínios (V3) ----------------------------------

    def _unidade(self, lit: Literal, esperada: str | None, nome: str) -> bool:
        if lit.unidade == esperada:
            return True
        if esperada is None:
            msg = f"{nome} é adimensional, mas o valor está em {lit.unidade}"
        elif lit.unidade is None:
            msg = f"{nome} exige unidade {esperada}"
        else:
            msg = f"{nome} está em {esperada}, não em {lit.unidade}"
        self._erro(lit.pos, "V2", msg)
        return False

    def _valor(self, lit: Literal, dom: Dominio, nome: str, op: str = "=") -> None:
        """Confere um literal atribuído a (op '=') ou comparado com (op) nome."""
        if dom.tipo == "campo":
            self._erro(lit.pos, "V3", f"{nome} é um campo escalar; só pode "
                       "aparecer em HIGHLIGHT ARGMAX/ARGMIN")
            return
        if dom.tipo in ("bool", "enum") and op not in ("=", *IGUALDADE):
            self._erro(lit.pos, "V3", f"{nome} não é numérico; use == ou != "
                       f"em vez de {op}")
            return
        if dom.tipo == "bool":
            if lit.tipo != "BOOL":
                self._erro(lit.pos, "V3", f"{nome} espera true ou false, não {_txt(lit)}")
            return
        if dom.tipo == "enum":
            if lit.tipo != "ENUM" or lit.valor not in dom.valores:
                self._erro(lit.pos, "V3", f"{nome} espera um de "
                           f"{{{_lista(dom.valores)}}}, não {_txt(lit)}")
            return
        if lit.tipo != "NUM":
            self._erro(lit.pos, "V3", f"{nome} espera um número, não {_txt(lit)}")
            return
        if not self._unidade(lit, dom.unidade, nome):
            return
        v = lit.valor
        if (dom.minimo is not None and v < dom.minimo) or \
           (dom.maximo is not None and v > dom.maximo):
            lo = "-∞" if dom.minimo is None else dom.minimo
            hi = "+∞" if dom.maximo is None else dom.maximo
            self._erro(lit.pos, "V3", f"{_txt(lit)} fora do intervalo "
                       f"[{lo}, {hi}] de {nome}")
        elif op == "=" and dom.valores and v not in dom.valores:
            self._erro(lit.pos, "V3", f"{nome} aceita apenas "
                       f"{_lista(dom.valores)}, não {_txt(lit)}")

    def _expr(self, e) -> None:
        if isinstance(e, (Ou, E)):
            self._expr(e.esq)
            self._expr(e.dir)
        elif isinstance(e, Nao):
            self._expr(e.expr)
        elif isinstance(e, Comparacao):
            r = self._resolver(e.ref)
            if r is not None:
                self._valor(e.valor, r[0], r[1], e.op)
        elif isinstance(e, Pertinencia):
            r = self._resolver(e.ref)
            if r is None:
                return
            dom, nome = r
            if dom.tipo != "enum":
                self._erro(e.pos, "V3", f"IN exige atributo enumerado; {nome} não é")
                return
            for v in e.valores:
                if v not in dom.valores:
                    self._erro(e.pos, "V3", f"{v} não é valor de {nome}; "
                               f"esperado um de {{{_lista(dom.valores)}}}")

    # ----- ações (V1–V4, V8) ----------------------------------------------

    def _acao(self, a) -> None:
        if isinstance(a, AcaoSet):
            if a.alvo.tipo == "pass":
                self._erro(a.pos, "V1", "SET só se aplica a superfícies (view)")
                return
            r = self._resolver(Referencia(a.alvo.pos, "view", a.alvo.nome, a.atributo))
            if r is None:
                return
            dom, nome = r
            self._valor(a.valor, dom, nome)
            sup = self.m.superficies[a.alvo.nome]
            if (sup.criticidade == "CRITICA" and a.atributo == "enabled"
                    and a.valor.valor is False):
                self._erro(a.pos, "V4", f'a superfície "{sup.nome}" é CRITICA '
                           "e não pode ser desativada")
        elif isinstance(a, AcaoScale):
            if a.recurso == "instances":
                if a.nome not in self.m.instancias:
                    self._erro(a.pos, "V1", f'instâncias "{a.nome}" não existem no '
                               f"modelo; disponíveis: {_lista(sorted(self.m.instancias))}")
            else:
                self._superficie(a.nome, a.pos)
            f = a.fator
            if f.unidade is not None:
                self._erro(f.pos, "V2", f"o fator de SCALE é adimensional, "
                           f"não {f.unidade}")
            elif not 0 < f.valor <= 1:
                self._erro(f.pos, "V3", f"o fator de SCALE deve estar em (0, 1], "
                           f"não {f.valor}")
        elif isinstance(a, AcaoInject):
            self._passo(a.passo, a.pos)
            self._passo(a.ancora, a.pos)
            if a.passo == a.ancora:
                self._erro(a.pos, "V8", f'INJECT de "{a.passo}" relativo a ele mesmo')
        elif isinstance(a, AcaoSuppress):
            self._passo(a.passo, a.pos)
        elif isinstance(a, AcaoHighlight):
            r = self._resolver(a.ref)
            if r is not None and r[0].tipo != "campo":
                self._erro(a.pos, "V3", f"{a.extremo} exige um campo escalar; "
                           f"{r[1]} não é")
            if a.raio is not None:
                if a.raio.tipo != "NUM":
                    self._erro(a.raio.pos, "V3", "o raio de WITHIN deve ser numérico")
                elif self._unidade(a.raio, UNIDADE_RAIO, "o raio de WITHIN") \
                        and a.raio.valor == 0:
                    self._erro(a.raio.pos, "V3", "o raio de WITHIN deve ser positivo")
        elif isinstance(a, AcaoMark):
            if a.alvo.tipo == "view":
                self._superficie(a.alvo.nome, a.alvo.pos)
            else:
                self._passo(a.alvo.nome, a.alvo.pos)

    # ----- coerência entre ações e garantias (V5, V6) ---------------------

    def _garantia(self, r: Regra) -> None:
        sets = {(a.alvo.nome, a.atributo): a for a in r.entao
                if isinstance(a, AcaoSet) and a.alvo.tipo == "view"}
        for c in _conjuncoes(r.garantia):
            if not (isinstance(c, Comparacao) and c.ref.alvo == "view"):
                continue
            a = sets.get((c.ref.nome, c.ref.campo))
            if a is None:
                continue
            v, lim = a.valor, c.valor
            if v.tipo != lim.tipo or v.unidade != lim.unidade:
                continue                         # já relatado como V2/V3
            if lim.tipo != "NUM" and c.op not in IGUALDADE:
                continue
            if not OPS[c.op](v.valor, lim.valor):
                self._erro(a.pos, "V5", f'SET view "{c.ref.nome}".{c.ref.campo} = '
                           f"{_txt(v)} viola o ASSERT da própria regra "
                           f"({c.op} {_txt(lim)}, linha {c.pos[0]})")

    def _conflitos(self, regras: list[Regra]) -> None:
        escritas: dict[tuple[str, str], list] = {}
        for r in regras:
            for a in r.entao:
                if isinstance(a, AcaoSet) and a.alvo.tipo == "view":
                    escritas.setdefault((a.alvo.nome, a.atributo), []).append((r, a))
        for (sup, attr), lst in escritas.items():
            for i, (r1, a1) in enumerate(lst):
                for r2, a2 in lst[i + 1:]:
                    if a1.valor.valor == a2.valor.valor:
                        continue
                    if r1 is r2:
                        self._erro(a2.pos, "V6", f'view "{sup}".{attr} recebe dois '
                                   f"valores na regra {r1.nome}")
                    elif r1.prioridade == r2.prioridade:
                        self._aviso(a2.pos, "V6", f"{r1.nome} e {r2.nome} têm a mesma "
                                    f'prioridade e atribuem valores diferentes a view '
                                    f'"{sup}".{attr}; a ordem de aplicação fica indefinida')


def verificar(prog: Programa, modelo: Modelo) -> list[Diagnostico]:
    return Verificador(modelo).verificar(prog)


def compilar(fonte: str, modelo: Modelo) -> tuple[Programa, list[str]]:
    """Léxico, sintático e semântico; diagnósticos nessa ordem."""
    prog, diags = analisar(fonte)
    return prog, diags + [str(d) for d in verificar(prog, modelo)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dressgl.semantica")
    ap.add_argument("arquivo")
    ap.add_argument("--modelo", default=str(MODELO_PADRAO))
    args = ap.parse_args(argv)
    try:
        modelo = carregar(args.modelo)
    except ErroModelo as e:
        print(f"{args.modelo}: erro no modelo: {e}")
        return 2
    with open(args.arquivo, encoding="utf-8-sig") as f:
        _, diags = compilar(f.read(), modelo)
    for d in diags:
        print(f"{args.arquivo}:{d}")
    n_avisos = sum("aviso semântico" in d for d in diags)
    print(f"{len(diags) - n_avisos} erro(s), {n_avisos} aviso(s)")
    return 1 if len(diags) > n_avisos else 0


if __name__ == "__main__":
    raise SystemExit(main())