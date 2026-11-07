from dressgl.gramatica_ll1 import conflitos_ll1, nao_alcancaveis


def test_gramatica_e_ll1():
    assert conflitos_ll1() == []


def test_todos_nao_terminais_alcancaveis():
    assert nao_alcancaveis() == set()