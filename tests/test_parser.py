from pathlib import Path

import pytest

from dressgl.gramatica_ll1 import G
from dressgl.lexer import (OPERADORES_DUPLOS, OPERADORES_SIMPLES,
                           PALAVRAS_RESERVADAS, PONTUACAO)
from dressgl.parser import (E, Nao, Ou, Comparacao, Pertinencia, Politica,
                            Regra, analisar)

EXEMPLO = Path(__file__).parent.parent / "examples" / "safe_setdown.dgl"


def regra(given="a.x < 1", acoes='SUPPRESS pass "P";', nome="Regra"):
    return (f'RULE {nome} GIVEN {given} WHEN AROUND pass "P" '
            f'THEN {acoes} END\n')


def sem_erros(fonte):
    prog, diags = analisar(fonte)
    assert diags == []
    return prog


def test_terminais_da_gramatica_coincidem_com_o_lexer():
    classes = {"IDENT", "NUM", "STRING", "ENUM", "BOOL"}
    terminais = {s for ps in G.values() for p in ps for s in p if s not in G}
    assert terminais - classes == (PALAVRAS_RESERVADAS | OPERADORES_DUPLOS
                                   | OPERADORES_SIMPLES | PONTUACAO)


def test_listagem_3_estrutura():
    prog = sem_erros(EXEMPLO.read_text(encoding="utf-8-sig"))
    pol, reg = prog.declaracoes
    assert isinstance(pol, Politica)
    assert [a.param for a in pol.atribs] == ["budget", "reserve", "cooldown"]
    assert (pol.atribs[0].valor.valor, pol.atribs[0].valor.unidade) == (16.67, "ms")
    assert isinstance(reg, Regra)
    assert (reg.nome, reg.prioridade) == ("SafeSetdownAssist", 90)
    assert isinstance(reg.dado, E)
    assert isinstance(reg.dado.esq, Comparacao)
    assert reg.dado.dir.valores == ("WATER", "STANDING_CROP")
    assert (reg.quando.fase, reg.quando.passo) == ("AROUND", "TerrainPass")
    assert [type(a).__name__ for a in reg.entao] == [
        "AcaoInject", "AcaoSet", "AcaoHighlight", "AcaoSet", "AcaoScale"]
    budget, fpv = reg.garantia.esq.ref, reg.garantia.dir.ref
    assert (budget.alvo, budget.nome, budget.campo) == (None, "frame_budget", None)
    assert (fpv.alvo, fpv.nome, fpv.campo) == ("view", "FPV", "scale")


def test_and_tem_precedencia_sobre_or():
    reg = sem_erros(regra("a.x < 1 OR b.y < 2 AND c.z < 3")).declaracoes[0]
    assert isinstance(reg.dado, Ou) and isinstance(reg.dado.dir, E)


def test_parenteses_alteram_agrupamento():
    reg = sem_erros(regra("(a.x < 1 OR b.y < 2) AND c.z < 3")).declaracoes[0]
    assert isinstance(reg.dado, E) and isinstance(reg.dado.esq, Ou)


def test_not_sobre_pertinencia():
    reg = sem_erros(regra("NOT a.x IN { WATER }")).declaracoes[0]
    assert isinstance(reg.dado, Nao) and isinstance(reg.dado.expr, Pertinencia)


def test_erro_com_posicao_e_esperado():
    fonte = 'RULE Regra GIVEN a.x < 1 WHEN AROUND pass "P" SUPPRESS pass "P"; END'
    _, diags = analisar(fonte)
    col = fonte.index("SUPPRESS") + 1
    assert diags == [
        f"1:{col}: erro sintático: esperado 'THEN', encontrado 'SUPPRESS'"]


def test_recupera_e_analisa_a_regra_seguinte():
    prog, diags = analisar(regra("a.x <", nome="Quebrada") + regra(nome="Boa"))
    assert len(diags) == 1
    assert [r.nome for r in prog.declaracoes] == ["Boa"]


def test_end_ausente_nao_engole_a_proxima_regra():
    fonte = regra(nome="Primeira").replace(" END", "") + regra(nome="Segunda")
    prog, diags = analisar(fonte)
    assert len(diags) == 1 and "'END'" in diags[0]
    assert [r.nome for r in prog.declaracoes] == ["Segunda"]


@pytest.mark.parametrize("prio", ["9.5", "90 ms"])
def test_prioridade_inteira_sem_unidade(prio):
    _, diags = analisar(regra().replace("Regra", f"Regra PRIORITY {prio}"))
    assert len(diags) == 1 and "PRIORITY" in diags[0]


def test_lixo_no_topo_termina_com_um_erro():
    _, diags = analisar("x y z")
    assert len(diags) == 1


def test_campo_com_nome_reservado_e_rejeitado():
    # Limitação documentada: 'resolution' é palavra reservada.
    _, diags = analisar(regra(acoes='SET view "FPV".resolution = 0.5;'))
    assert len(diags) == 1


def test_nome_de_regra_em_caixa_alta_e_enum():
    # Convenção documentada: nomes de regra em PascalCase.
    _, diags = analisar(regra(nome="GPS_LOSS"))
    assert diags and "encontrado 'GPS_LOSS'" in diags[0]