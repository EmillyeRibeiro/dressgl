"""Analisador léxico da DRESS-GL, escrito à mão (sem gerador).

Cada método _ler_* corresponde a um ramo do autômato finito determinístico:
o primeiro caractere escolhe o ramo e o laço consome a maior cadeia aceita
(regra do lexema mais longo). Palavras reservadas têm prioridade sobre
identificadores.

Erros léxicos não interrompem a varredura: um caractere inválido ou uma
cadeia não terminada vira um token ERRO com linha e coluna, e a análise
continua. Assim o usuário vê todos os erros de uma vez.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TipoToken(Enum):
    PALAVRA_RESERVADA = auto()
    IDENT = auto()
    ENUM = auto()
    NUM = auto()
    CADEIA = auto()
    BOOL = auto()
    OPERADOR = auto()
    PONTUACAO = auto()
    ERRO = auto()
    EOF = auto()


PALAVRAS_RESERVADAS = frozenset({
    "POLICY", "RULE", "PRIORITY", "GIVEN", "WHEN", "THEN", "ASSERT", "END",
    "AND", "OR", "NOT", "IN",
    "BEFORE", "AFTER", "AROUND",
    "SET", "SCALE", "BY", "INJECT", "SUPPRESS", "HIGHLIGHT", "WITHIN",
    "MARK", "STALE", "ARGMAX", "ARGMIN",
    "view", "pass", "instances", "resolution", "budget", "reserve", "cooldown",
})

BOOLEANOS = {"true": True, "false": False}

# A ordem importa: "m/s" e "ms" precisam ser testadas antes de "m".
UNIDADES = ("frames", "m/s", "ms", "Hz", "m", "%")

OPERADORES_DUPLOS = frozenset({"<=", ">=", "==", "!="})
OPERADORES_SIMPLES = frozenset("<>=")
PONTUACAO = frozenset(";,.{}()")
DIGITOS = frozenset("0123456789")
ESPACOS = frozenset(" \t\r\n")
ESPACOS_ANTES_DA_UNIDADE = frozenset(" \t")  # ws da regra NUM (ws? UNIDADE)?


def _letra(c: str) -> bool:
    """Apenas letras ASCII e sublinhado (limitação documentada)."""
    return c == "_" or "a" <= c <= "z" or "A" <= c <= "Z"


def _eh_enum(lexema: str) -> bool:
    """Convenção: valores enumerados são escritos em CAIXA_ALTA."""
    return lexema[0].isupper() and all(
        c.isupper() or c.isdigit() or c == "_" for c in lexema
    )


@dataclass(frozen=True)
class Token:
    tipo: TipoToken
    lexema: str
    linha: int
    coluna: int
    valor: object = None
    unidade: str | None = None


class _Scanner:
    def __init__(self, fonte: str):
        self.src = fonte
        self.i = 0
        self.linha = 1
        self.coluna = 1

    # ----- navegação ---------------------------------------------------

    def _ver(self, k: int = 0) -> str:
        j = self.i + k
        return self.src[j] if j < len(self.src) else ""

    def _avancar(self) -> str:
        c = self.src[self.i]
        self.i += 1
        if c == "\n":
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1
        return c

    # ----- laço principal ----------------------------------------------

    def tokens(self) -> list[Token]:
        saida: list[Token] = []
        while True:
            self._pular_espacos_e_comentarios()
            if self.i >= len(self.src):
                saida.append(Token(TipoToken.EOF, "", self.linha, self.coluna))
                return saida
            saida.append(self._proximo())

    def _pular_espacos_e_comentarios(self) -> None:
        while self.i < len(self.src):
            c = self._ver()
            if c in ESPACOS:
                self._avancar()
            elif c == "#":
                while self.i < len(self.src) and self._ver() != "\n":
                    self._avancar()
            else:
                return

    def _proximo(self) -> Token:
        lin, col = self.linha, self.coluna
        c = self._ver()
        if _letra(c):
            return self._ler_palavra(lin, col)
        if c in DIGITOS:
            return self._ler_numero(lin, col)
        if c == '"':
            return self._ler_cadeia(lin, col)
        duplo = c + self._ver(1)
        if duplo in OPERADORES_DUPLOS:
            self._avancar()
            self._avancar()
            return Token(TipoToken.OPERADOR, duplo, lin, col)
        if c in OPERADORES_SIMPLES:
            self._avancar()
            return Token(TipoToken.OPERADOR, c, lin, col)
        if c in PONTUACAO:
            self._avancar()
            return Token(TipoToken.PONTUACAO, c, lin, col)
        # Nenhum ramo do AFD aceita c: registra o erro e segue a varredura.
        self._avancar()
        return Token(TipoToken.ERRO, c, lin, col,
                     valor=f"caractere inesperado {c!r}")

    # ----- ramos do autômato -------------------------------------------

    def _ler_palavra(self, lin: int, col: int) -> Token:
        inicio = self.i
        while _letra(self._ver()) or self._ver() in DIGITOS:
            self._avancar()
        lex = self.src[inicio:self.i]
        if lex in PALAVRAS_RESERVADAS:
            return Token(TipoToken.PALAVRA_RESERVADA, lex, lin, col)
        if lex in BOOLEANOS:
            return Token(TipoToken.BOOL, lex, lin, col, valor=BOOLEANOS[lex])
        if _eh_enum(lex):
            return Token(TipoToken.ENUM, lex, lin, col, valor=lex)
        return Token(TipoToken.IDENT, lex, lin, col, valor=lex)

    def _ler_numero(self, lin: int, col: int) -> Token:
        inicio = self.i
        while self._ver() in DIGITOS:
            self._avancar()
        if self._ver() == "." and self._ver(1) in DIGITOS:
            self._avancar()
            while self._ver() in DIGITOS:
                self._avancar()
        lex = self.src[inicio:self.i]
        valor = float(lex) if "." in lex else int(lex)
        unidade = self._ler_unidade()
        return Token(TipoToken.NUM, lex, lin, col, valor=valor, unidade=unidade)

    def _ler_unidade(self) -> str | None:
        """Anota a unidade no número (P1). Aceita espaços/tab antes dela."""
        j = self.i
        while j < len(self.src) and self.src[j] in ESPACOS_ANTES_DA_UNIDADE:
            j += 1
        for u in UNIDADES:
            if self.src.startswith(u, j):
                k = j + len(u)
                prox = self.src[k] if k < len(self.src) else ""
                if not (_letra(prox) or prox in DIGITOS):  # "10 mode" não é unidade
                    while self.i < k:
                        self._avancar()
                    return u
        return None

    def _ler_cadeia(self, lin: int, col: int) -> Token:
        self._avancar()  # aspas de abertura
        inicio = self.i
        while self._ver() not in ('"', "", "\n"):
            self._avancar()
        valor = self.src[inicio:self.i]
        if self._ver() != '"':  # recupera no fim da linha
            return Token(TipoToken.ERRO, '"' + valor, lin, col,
                         valor="cadeia não terminada")
        self._avancar()  # aspas de fechamento
        return Token(TipoToken.CADEIA, f'"{valor}"', lin, col, valor=valor)


def tokenizar(fonte: str) -> list[Token]:
    return _Scanner(fonte).tokens()


def erros_lexicos(tokens: list[Token]) -> list[str]:
    """Diagnósticos no formato linha:coluna: mensagem."""
    return [f"{t.linha}:{t.coluna}: erro léxico: {t.valor}"
            for t in tokens if t.tipo is TipoToken.ERRO]