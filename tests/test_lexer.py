from pathlib import Path

import pytest

from dressgl.lexer import TipoToken as T, erros_lexicos, tokenizar


def test_numero_com_unidade():
    t = tokenizar("16.67 ms")[0]
    assert (t.tipo, t.valor, t.unidade) == (T.NUM, 16.67, "ms")


@pytest.mark.parametrize("src,unidade", [
    ("2 Hz", "Hz"), ("18 %", "%"), ("400 m", "m"), ("3 m/s", "m/s"),
    ("10 frames", "frames"), ("0.25", None), ("5ms", "ms"),
])
def test_unidades(src, unidade):
    assert tokenizar(src)[0].unidade == unidade


def test_identificador_apos_numero_nao_vira_unidade():
    toks = tokenizar("10 mode")
    assert toks[0].unidade is None
    assert (toks[1].tipo, toks[1].lexema) == (T.IDENT, "mode")


def test_classificacao_de_palavras():
    toks = tokenizar("RULE SafeSetdownAssist WATER view true")
    assert [t.tipo for t in toks] == [
        T.PALAVRA_RESERVADA, T.IDENT, T.ENUM, T.PALAVRA_RESERVADA, T.BOOL, T.EOF]


def test_operadores_casamento_mais_longo():
    lexemas = [t.lexema for t in tokenizar("<= < >= > == != =")][:-1]
    assert lexemas == ["<=", "<", ">=", ">", "==", "!=", "="]


def test_linha_e_coluna():
    toks = tokenizar("POLICY AgroViewSC {\n  budget = 16.67 ms;\n}")
    assert (toks[3].lexema, toks[3].linha, toks[3].coluna) == ("budget", 2, 3)


def test_comentario_ignorado():
    assert [t.tipo for t in tokenizar("# nada\nEND")] == [T.PALAVRA_RESERVADA, T.EOF]


def test_cadeia():
    t = tokenizar('pass "TerrainPass"')[1]
    assert (t.tipo, t.valor) == (T.CADEIA, "TerrainPass")


@pytest.mark.parametrize("src,linha,coluna", [
    ('"aberta', 1, 1), ("RULE @", 1, 6), ("x\n  !", 2, 3),
])
def test_erros_lexicos_com_posicao(src, linha, coluna):
    erros = [t for t in tokenizar(src) if t.tipo is T.ERRO]
    assert [(e.linha, e.coluna) for e in erros] == [(linha, coluna)]


def test_varredura_continua_apos_erro():
    toks = tokenizar('RULE @ x $ END "aberta\nEND')
    assert [t.tipo for t in toks] == [
        T.PALAVRA_RESERVADA, T.ERRO, T.IDENT, T.ERRO,
        T.PALAVRA_RESERVADA, T.ERRO, T.PALAVRA_RESERVADA, T.EOF]


def test_formato_do_diagnostico():
    assert erros_lexicos(tokenizar("RULE @")) == [
        "1:6: erro léxico: caractere inesperado '@'"]


def test_identificador_nao_ascii_gera_erro():
    # Limitação documentada: identificadores aceitam apenas letras ASCII.
    toks = tokenizar("bateria_mínima")
    assert [(t.tipo, t.lexema) for t in toks] == [
        (T.IDENT, "bateria_m"), (T.ERRO, "í"), (T.IDENT, "nima"), (T.EOF, "")]


def test_listagem_3_do_artigo():
    arquivo = Path(__file__).parent.parent / "examples" / "safe_setdown.dgl"
    # utf-8-sig tolera o BOM que alguns editores do Windows gravam no início.
    toks = tokenizar(arquivo.read_text(encoding="utf-8-sig"))
    assert erros_lexicos(toks) == []
    numeros = [(t.valor, t.unidade) for t in toks if t.tipo is T.NUM]
    assert numeros == [
        (16.67, "ms"), (2.0, "ms"), (10, "frames"), (90, None), (18, "%"),
        (400, "m"), (2, "Hz"), (0.25, None), (16.67, "ms"), (0.75, None)]