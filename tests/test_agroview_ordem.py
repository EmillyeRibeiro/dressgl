import pytest

from agroview.ordem import ErroOrdem, desenha, ordem_passos, periodo
from dressgl.interpretador import EfeitoInject as I

P = ["A", "B", "C"]


def test_sem_efeitos():
    assert ordem_passos(P, (), ()) == P


def test_suppress():
    assert ordem_passos(P, {"B"}, ()) == ["A", "C"]


def test_after_e_before():
    assert ordem_passos(P, (), [I("X", "AFTER", "A")]) == ["A", "X", "B", "C"]
    assert ordem_passos(P, (), [I("X", "BEFORE", "A")]) == ["X", "A", "B", "C"]


def test_ancora_em_passo_injetado():
    inj = [I("Y", "AFTER", "X"), I("X", "AFTER", "A")]
    assert ordem_passos(P, (), inj) == ["A", "X", "Y", "B", "C"]


def test_maior_prioridade_mais_perto_da_ancora():
    assert ordem_passos(P, (), [I("X", "AFTER", "A"), I("Y", "AFTER", "A")]) \
        == ["A", "X", "Y", "B", "C"]
    assert ordem_passos(P, (), [I("X", "BEFORE", "C"), I("Y", "BEFORE", "C")]) \
        == ["A", "B", "Y", "X", "C"]


def test_ancora_suprimida_e_erro():
    with pytest.raises(ErroOrdem):
        ordem_passos(P, {"A"}, [I("X", "AFTER", "A")])


def test_periodo():
    assert (periodo(60), periodo(10), periodo(2)) == (1, 6, 30)


def test_decimacao():
    assert [q for q in range(61) if desenha(q, 2)] == [0, 30, 60]