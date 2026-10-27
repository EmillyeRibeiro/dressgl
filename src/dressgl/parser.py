"""Analisador sintático descendente recursivo da DRESS-GL (P2).

Uma função por não terminal da gramática de gramatica_ll1.py. A produção é
escolhida apenas pelo token atual, conforme os conjuntos SELECT verificados
naquele módulo (LL(1), sem retrocesso).

Recuperação em modo pânico: um erro descarta a declaração corrente e a
análise recomeça no próximo POLICY ou RULE (FIRST(declaracao)).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from .lexer import TipoToken as T, Token, erros_lexicos, tokenizar

Pos = tuple[int, int]  # (linha, coluna)


# ----- árvore sintática abstrata ------------------------------------------

@dataclass(frozen=True)
class Literal:
    pos: Pos
    tipo: str              # "NUM", "ENUM", "BOOL" ou "STRING"
    valor: object
    unidade: str | None = None

@dataclass(frozen=True)
class Atrib:
    pos: Pos
    param: str
    valor: Literal

@dataclass(frozen=True)
class Politica:
    pos: Pos
    nome: str
    atribs: tuple[Atrib, ...]

@dataclass(frozen=True)
class Alvo:
    pos: Pos
    tipo: str              # "view" ou "pass"
    nome: str

@dataclass(frozen=True)
class Referencia:
    """frame_budget       -> (None, "frame_budget", None)
       drone.battery      -> (None, "drone", "battery")
       view "FPV".scale   -> ("view", "FPV", "scale")"""
    pos: Pos
    alvo: str | None
    nome: str
    campo: str | None

@dataclass(frozen=True)
class Ou:
    pos: Pos
    esq: object
    dir: object

@dataclass(frozen=True)
class E:
    pos: Pos
    esq: object
    dir: object

@dataclass(frozen=True)
class Nao:
    pos: Pos
    expr: object

@dataclass(frozen=True)
class Comparacao:
    pos: Pos
    ref: Referencia
    op: str
    valor: Literal

@dataclass(frozen=True)
class Pertinencia:
    pos: Pos
    ref: Referencia
    valores: tuple[str, ...]

@dataclass(frozen=True)
class Juncao:
    pos: Pos
    fase: str
    passo: str

@dataclass(frozen=True)
class AcaoSet:
    pos: Pos
    alvo: Alvo
    atributo: str
    valor: Literal

@dataclass(frozen=True)
class AcaoScale:
    pos: Pos
    recurso: str
    nome: str
    fator: Literal

@dataclass(frozen=True)
class AcaoInject:
    pos: Pos
    passo: str
    fase: str
    ancora: str

@dataclass(frozen=True)
class AcaoSuppress:
    pos: Pos
    passo: str

@dataclass(frozen=True)
class AcaoHighlight:
    pos: Pos
    extremo: str
    ref: Referencia
    raio: Literal | None

@dataclass(frozen=True)
class AcaoMark:
    pos: Pos
    alvo: Alvo

@dataclass(frozen=True)
class Regra:
    pos: Pos
    nome: str
    prioridade: int | None
    dado: object
    quando: Juncao
    entao: tuple
    garantia: object | None

@dataclass(frozen=True)
class Programa:
    declaracoes: tuple


# ----- tokens como terminais da gramática ---------------------------------

_CLASSE = {T.IDENT: "IDENT", T.NUM: "NUM", T.CADEIA: "STRING",
           T.ENUM: "ENUM", T.BOOL: "BOOL", T.EOF: "$"}


def terminal(t: Token) -> str:
    """Nome do terminal na gramática: a classe ou o próprio lexema."""
    return _CLASSE.get(t.tipo, t.lexema)


def _pos(t: Token) -> Pos:
    return (t.linha, t.coluna)


def _nome(term: str) -> str:
    return "fim do arquivo" if term == "$" else f"'{term}'"


class ErroSintatico(Exception):
    def __init__(self, tok: Token, esperado=(), mensagem: str | None = None):
        if mensagem is None:
            esp = " ou ".join(_nome(e) for e in sorted(esperado))
            enc = "fim do arquivo" if tok.tipo is T.EOF else f"'{tok.lexema}'"
            mensagem = f"esperado {esp}, encontrado {enc}"
        self.linha, self.coluna = tok.linha, tok.coluna
        super().__init__(f"{tok.linha}:{tok.coluna}: erro sintático: {mensagem}")


OP_REL = ("<", "<=", ">", ">=", "==", "!=")
PARAMS = ("budget", "reserve", "cooldown")
FASES = ("BEFORE", "AFTER", "AROUND")
FIRST_ACAO = ("SET", "SCALE", "INJECT", "SUPPRESS", "HIGHLIGHT", "MARK")


class Parser:
    def __init__(self, tokens: list[Token]):
        # Erros léxicos já foram relatados pelo lexer; aqui são ignorados.
        self.toks = [t for t in tokens if t.tipo is not T.ERRO]
        self.k = 0
        self.erros: list[ErroSintatico] = []

    # ----- utilitários ----------------------------------------------------

    @property
    def atual(self) -> Token:
        return self.toks[self.k]

    def ve(self, *terms: str) -> bool:
        return terminal(self.atual) in terms

    def consome(self, *terms: str) -> Token:
        t = self.atual
        if terminal(t) not in terms:
            raise ErroSintatico(t, terms)
        if t.tipo is not T.EOF:
            self.k += 1
        return t

    def _sincronizar(self, inicio: int) -> None:
        if self.k == inicio:          # garante progresso
            self.k += 1
        while not self.ve("POLICY", "RULE", "$"):
            self.k += 1

    # ----- programa e declarações -----------------------------------------

    def programa(self) -> Programa:
        decls = []
        while not self.ve("$"):
            inicio = self.k
            try:
                if self.ve("POLICY"):
                    decls.append(self.politica())
                elif self.ve("RULE"):
                    decls.append(self.regra())
                else:
                    raise ErroSintatico(self.atual, ("POLICY", "RULE", "$"))
            except ErroSintatico as e:
                self.erros.append(e)
                self._sincronizar(inicio)
        return Programa(tuple(decls))

    def politica(self) -> Politica:
        t = self.consome("POLICY")
        nome = self.consome("IDENT").lexema
        self.consome("{")
        atribs = []
        while self.ve(*PARAMS):
            p = self.consome(*PARAMS)
            self.consome("=")
            valor = self.literal()
            self.consome(";")
            atribs.append(Atrib(_pos(p), p.lexema, valor))
        self.consome("}")
        return Politica(_pos(t), nome, tuple(atribs))

    def regra(self) -> Regra:
        t = self.consome("RULE")
        nome = self.consome("IDENT").lexema
        prioridade = None
        if self.ve("PRIORITY"):
            self.consome("PRIORITY")
            n = self.consome("NUM")
            if isinstance(n.valor, int) and n.unidade is None:
                prioridade = n.valor
            else:  # erro registrado sem abortar a regra
                self.erros.append(ErroSintatico(
                    n, mensagem="PRIORITY exige inteiro sem unidade"))
        self.consome("GIVEN")
        dado = self.expr()
        self.consome("WHEN")
        quando = self.juncao()
        self.consome("THEN")
        entao = self.acoes()
        garantia = None
        if self.ve("ASSERT"):
            self.consome("ASSERT")
            garantia = self.expr()
        self.consome("END")
        return Regra(_pos(t), nome, prioridade, dado, quando, entao, garantia)

    # ----- expressões: OR < AND < NOT, associação à esquerda --------------

    def expr(self):
        e = self.conj()
        while self.ve("OR"):
            t = self.consome("OR")
            e = Ou(_pos(t), e, self.conj())
        return e

    def conj(self):
        e = self.neg()
        while self.ve("AND"):
            t = self.consome("AND")
            e = E(_pos(t), e, self.neg())
        return e

    def neg(self):
        if self.ve("NOT"):
            t = self.consome("NOT")
            return Nao(_pos(t), self.atomo())
        return self.atomo()

    def atomo(self):
        if self.ve("("):
            self.consome("(")
            e = self.expr()
            self.consome(")")
            return e
        if self.ve("IDENT", "view", "pass"):
            return self.resto(self.referencia())
        raise ErroSintatico(self.atual, ("(", "IDENT", "view", "pass", "NOT"))

    def resto(self, ref: Referencia):
        if self.ve(*OP_REL):
            op = self.consome(*OP_REL).lexema
            return Comparacao(ref.pos, ref, op, self.literal())
        if self.ve("IN"):
            self.consome("IN")
            return Pertinencia(ref.pos, ref, self.conjunto())
        raise ErroSintatico(self.atual, (*OP_REL, "IN"))

    def conjunto(self) -> tuple[str, ...]:
        self.consome("{")
        valores = [self.consome("ENUM").lexema]
        while self.ve(","):
            self.consome(",")
            valores.append(self.consome("ENUM").lexema)
        self.consome("}")
        return tuple(valores)

    def referencia(self) -> Referencia:
        if self.ve("IDENT"):
            t = self.consome("IDENT")
            campo = None
            if self.ve("."):
                self.consome(".")
                campo = self.consome("IDENT").lexema
            return Referencia(_pos(t), None, t.lexema, campo)
        if not self.ve("view", "pass"):
            raise ErroSintatico(self.atual, ("IDENT", "view", "pass"))
        alvo = self.alvo()
        self.consome(".")
        campo = self.consome("IDENT").lexema
        return Referencia(alvo.pos, alvo.tipo, alvo.nome, campo)

    def alvo(self) -> Alvo:
        t = self.consome("view", "pass")
        return Alvo(_pos(t), t.lexema, self.consome("STRING").valor)

    def juncao(self) -> Juncao:
        f = self.consome(*FASES)
        self.consome("pass")
        return Juncao(_pos(f), f.lexema, self.consome("STRING").valor)

    # ----- ações ----------------------------------------------------------

    def acoes(self) -> tuple:
        lista = [self.acao()]
        self.consome(";")
        while self.ve(*FIRST_ACAO):
            lista.append(self.acao())
            self.consome(";")
        return tuple(lista)

    def acao(self):
        t = self.consome(*FIRST_ACAO)
        p, kw = _pos(t), t.lexema
        if kw == "SET":
            alvo = self.alvo()
            self.consome(".")
            atributo = self.consome("IDENT").lexema
            self.consome("=")
            return AcaoSet(p, alvo, atributo, self.literal())
        if kw == "SCALE":
            recurso = self.consome("instances", "resolution").lexema
            nome = self.consome("STRING").valor
            self.consome("BY")
            return AcaoScale(p, recurso, nome, _literal(self.consome("NUM")))
        if kw == "INJECT":
            self.consome("pass")
            passo = self.consome("STRING").valor
            fase = self.consome("BEFORE", "AFTER").lexema
            return AcaoInject(p, passo, fase, self.consome("STRING").valor)
        if kw == "SUPPRESS":
            self.consome("pass")
            return AcaoSuppress(p, self.consome("STRING").valor)
        if kw == "HIGHLIGHT":
            extremo = self.consome("ARGMAX", "ARGMIN").lexema
            ref = self.referencia()
            raio = None
            if self.ve("WITHIN"):
                self.consome("WITHIN")
                raio = self.literal()
            return AcaoHighlight(p, extremo, ref, raio)
        alvo = self.alvo()            # MARK
        self.consome("STALE")
        return AcaoMark(p, alvo)

    def literal(self) -> Literal:
        return _literal(self.consome("NUM", "ENUM", "BOOL", "STRING"))


def _literal(t: Token) -> Literal:
    return Literal(_pos(t), terminal(t), t.valor, t.unidade)


def analisar(fonte: str) -> tuple[Programa, list[str]]:
    """Retorna a AST e todos os diagnósticos (léxicos, depois sintáticos)."""
    toks = tokenizar(fonte)
    p = Parser(toks)
    prog = p.programa()
    return prog, erros_lexicos(toks) + [str(e) for e in p.erros]


if __name__ == "__main__":
    caminho = sys.argv[1]
    with open(caminho, encoding="utf-8-sig") as f:
        prog, diags = analisar(f.read())
    for d in diags:
        print(f"{caminho}:{d}")
    if not diags:
        n_pol = sum(isinstance(d, Politica) for d in prog.declaracoes)
        n_reg = sum(isinstance(d, Regra) for d in prog.declaracoes)
        print(f"OK: {n_pol} política(s), {n_reg} regra(s)")
    raise SystemExit(1 if diags else 0)