import pytest

from dressgl.interpretador import (EfeitoHighlight, EfeitoInject, EfeitoScale,
                                   EfeitoSet, ErroCompilacao, ErroExecucao,
                                   compilar_programa)
from dressgl.modelo import MODELO_PADRAO, carregar

MODELO = carregar(MODELO_PADRAO)
EXEMPLO = MODELO_PADRAO.parent.parent / "examples" / "safe_setdown.dgl"
# Nomes em PascalCase (D11): "P" ou "R" seriam lidos como ENUM.
POLITICA = "POLICY Politica { budget = 16.67 ms; }\n"
REGRA = ('RULE Regra GIVEN drone.battery < 18 % WHEN AROUND pass "TerrainPass" '
         'THEN SET view "MAP".mode = SUITABILITY; END\n')


@pytest.fixture(scope="module")
def listagem3():
    return compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), MODELO)


def test_politica_compilada(listagem3):
    p = listagem3.politica
    assert (p.nome, p.budget_ms, p.reserve_ms, p.cooldown_frames) == (
        "AgroViewSC", 16.67, 2.0, 10)


def test_regra_e_efeitos_da_listagem_3(listagem3):
    [r] = listagem3.regras
    assert (r.nome, r.prioridade, r.juncao, r.linha) == (
        "SafeSetdownAssist", 90, ("AROUND", "TerrainPass"), 7)
    assert r.efeitos == (
        EfeitoInject("SuitabilityPass", "AFTER", "TerrainPass"),
        EfeitoSet("MAP", "mode", "SUITABILITY"),
        EfeitoHighlight("ARGMAX", "terrain.suitability", 400),
        EfeitoSet("AGRO", "hz", 2),
        EfeitoScale("instances", "crops", 0.25),
    )
    assert [ef.linha for ef in r.efeitos] == [11, 12, 13, 14, 15]


def test_leituras_exigidas(listagem3):
    [r] = listagem3.regras
    assert r.variaveis == {"drone.battery", "terrain.below"}
    assert r.variaveis_garantia == {"frame_budget", "view:FPV.scale"}


@pytest.mark.parametrize("bateria,solo,esperado", [
    (10, "WATER", True), (10, "STANDING_CROP", True), (10, "BARE_SOIL", False),
    (18, "WATER", False), (50, "WATER", False),
])
def test_predicado(listagem3, bateria, solo, esperado):
    [r] = listagem3.regras
    assert r.predicado({"drone.battery": bateria, "terrain.below": solo}) is esperado


def test_garantia(listagem3):
    [r] = listagem3.regras
    assert r.garantia({"frame_budget": 15.0, "view:FPV.scale": 1.0}) is True
    assert r.garantia({"frame_budget": 17.0, "view:FPV.scale": 1.0}) is False
    assert r.garantia({"frame_budget": 15.0, "view:FPV.scale": 0.5}) is False


def test_leitura_ausente(listagem3):
    [r] = listagem3.regras
    with pytest.raises(ErroExecucao, match="drone.battery"):
        r.predicado({"terrain.below": "WATER"})


def test_sem_assert_e_sem_prioridade():
    [r] = compilar_programa(POLITICA + REGRA, MODELO).regras
    assert r.prioridade is None and r.garantia({}) is None


def test_programa_sem_policy():
    assert compilar_programa(REGRA, MODELO).politica is None


def test_recusa_erro_semantico():
    with pytest.raises(ErroCompilacao) as e:
        compilar_programa(POLITICA + REGRA.replace("SUITABILITY", "LAVA"), MODELO)
    assert len(e.value.diagnosticos) == 1 and "[V3]" in e.value.diagnosticos[0]


def test_recusa_erro_sintatico_sem_rodar_semantica():
    with pytest.raises(ErroCompilacao) as e:
        compilar_programa(POLITICA + REGRA.replace("THEN", ""), MODELO)
    assert len(e.value.diagnosticos) == 1
    assert "erro sintático" in e.value.diagnosticos[0]