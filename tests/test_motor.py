import dataclasses

import pytest

from dressgl.interpretador import (EfeitoInject, EfeitoScale, EfeitoSet,
                                   EfeitoSuppress, ErroExecucao,
                                   PoliticaExecutavel, ProgramaExecutavel,
                                   compilar_programa)
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.motor import Conflito, Motor, Violacao, compor

MODELO = carregar(MODELO_PADRAO)
EXEMPLO = MODELO_PADRAO.parent.parent / "examples" / "safe_setdown.dgl"
REGRA = ('RULE Regra GIVEN drone.battery < 18 % WHEN AROUND pass "TerrainPass" '
         'THEN SET view "MAP".mode = SUITABILITY; END\n')
[BASE] = compilar_programa(REGRA, MODELO).regras
NOME = "SafeSetdownAssist"


def regra(nome, prioridade, linha, *efeitos):
    return dataclasses.replace(BASE, nome=nome, prioridade=prioridade,
                               linha=linha, efeitos=efeitos)


def programa(*regras, cooldown=None):
    return ProgramaExecutavel(PoliticaExecutavel("Politica", 16.67, None, cooldown),
                              regras)


def leit(bateria, solo="WATER", fb=15.0, escala=1.0):
    return {"drone.battery": bateria, "terrain.below": solo,
            "frame_budget": fb, "view:FPV.scale": escala}


@pytest.fixture
def motor_l3():
    return Motor(compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), MODELO))


def test_cenario_listagem_3(motor_l3):
    r0 = motor_l3.passo(leit(50))
    assert r0.ativas == () and r0.plano.sets == {}
    r1 = motor_l3.passo(leit(10))
    assert r1.ativadas == (NOME,) and r1.ativas == (NOME,)
    assert r1.plano.sets == {("MAP", "mode"): "SUITABILITY", ("AGRO", "hz"): 2}
    assert r1.plano.escalas == {("instances", "crops"): 0.25}
    assert r1.plano.injecoes == (EfeitoInject("SuitabilityPass", "AFTER", "TerrainPass"),)
    assert r1.conflitos == () and r1.violacoes == ()


def test_cooldown_da_politica(motor_l3):          # cooldown = 10 na Listagem 3
    assert motor_l3.passo(leit(10)).ativadas == (NOME,)          # quadro 0
    for _ in range(1, 10):
        r = motor_l3.passo(leit(50))
        assert r.retidas == (NOME,) and r.ativas == (NOME,)
    r = motor_l3.passo(leit(50))
    assert r.quadro == 10 and r.desativadas == (NOME,) and r.ativas == ()


def test_assert_verifica_plano_do_quadro_anterior(motor_l3):
    assert motor_l3.passo(leit(10, fb=17.0)).violacoes == ()     # nada aplicado antes
    assert motor_l3.passo(leit(10, fb=17.0)).violacoes == (Violacao(NOME, 0),)
    assert motor_l3.passo(leit(10, fb=15.0)).violacoes == ()


def test_conflito_set_vence_maior_prioridade():
    alta = regra("Alta", 80, 2, EfeitoSet("MAP", "mode", "A"))
    baixa = regra("Baixa", 20, 1, EfeitoSet("MAP", "mode", "B"))
    r = Motor(programa(baixa, alta)).passo({"drone.battery": 10})
    assert r.ativas == ("Alta", "Baixa")
    assert r.plano.sets == {("MAP", "mode"): "A"}
    assert r.conflitos == (Conflito("MAP.mode", "Alta", "Baixa"),)


def test_empate_decide_pela_linha():
    a = regra("Primeira", None, 1, EfeitoSet("MAP", "mode", "A"))
    b = regra("Segunda", None, 2, EfeitoSet("MAP", "mode", "B"))
    plano, conflitos = compor((b, a))
    assert plano.sets == {("MAP", "mode"): "A"}
    assert conflitos == (Conflito("MAP.mode", "Primeira", "Segunda"),)


def test_scale_usa_menor_fator_em_qualquer_ordem():
    a = regra("A", 80, 1, EfeitoScale("instances", "crops", 0.5))
    b = regra("B", 20, 2, EfeitoScale("instances", "crops", 0.25))
    for regras in ((a, b), (b, a)):
        plano, conflitos = compor(regras)
        assert plano.escalas == {("instances", "crops"): 0.25} and conflitos == ()


def test_inject_contra_suppress():
    inj = regra("Injeta", 80, 1, EfeitoInject("SuitabilityPass", "AFTER", "TerrainPass"))
    sup = regra("Suprime", 20, 2, EfeitoSuppress("SuitabilityPass"))
    plano, conflitos = compor((sup, inj))
    assert len(plano.injecoes) == 1 and plano.supressoes == frozenset()
    assert conflitos == (Conflito("pass SuitabilityPass", "Injeta", "Suprime"),)


def test_compor_idempotente(motor_l3):
    [r] = motor_l3.regras
    assert compor((r, r)) == compor((r,))


def test_leitura_ausente_nao_avanca_estado(motor_l3):
    with pytest.raises(ErroExecucao):
        motor_l3.passo({"drone.battery": 10})
    assert motor_l3.quadro == -1
    assert motor_l3.passo(leit(10)).quadro == 0

def test_set_numerico_compoe_pelo_minimo():                     # D17
    a = regra("A", 80, 1, EfeitoSet("AGRO", "hz", 5))
    b = regra("B", 20, 2, EfeitoSet("AGRO", "hz", 2))
    for regras in ((a, b), (b, a)):
        plano, conflitos = compor(regras)
        assert plano.sets == {("AGRO", "hz"): 2} and conflitos == ()


def test_set_booleano_compoe_por_conjuncao():                   # D17
    a = regra("A", 80, 1, EfeitoSet("FPV", "overlay", True))
    b = regra("B", 20, 2, EfeitoSet("FPV", "overlay", False))
    for regras in ((a, b), (b, a)):
        plano, conflitos = compor(regras)
        assert plano.sets == {("FPV", "overlay"): False} and conflitos == ()