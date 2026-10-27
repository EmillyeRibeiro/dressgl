import tomllib

import pytest

from dressgl.modelo import MODELO_PADRAO, ErroModelo, carregar, construir
from dressgl.parser import analisar
from dressgl.semantica import verificar

MODELO = carregar(MODELO_PADRAO)
EXEMPLO = MODELO_PADRAO.parent.parent / "examples" / "safe_setdown.dgl"
POLITICA = ("POLICY Politica { budget = 16.67 ms; reserve = 2 ms; "
            "cooldown = 10 frames; }\n")


def regra(given="drone.battery < 18 %", acoes='SET view "MAP".mode = SUITABILITY;',
          garantia=None, nome="Regra", prio=None):
    p = f" PRIORITY {prio}" if prio is not None else ""
    a = f" ASSERT {garantia}" if garantia else ""
    return (f'RULE {nome}{p} GIVEN {given} WHEN AROUND pass "TerrainPass" '
            f"THEN {acoes}{a} END\n")


def diagnosticos(fonte):
    prog, sintaticos = analisar(fonte)
    assert sintaticos == []          # todos os casos são sintaticamente corretos
    return verificar(prog, MODELO)


def codigos(fonte):
    return [d.codigo for d in diagnosticos(fonte)]


def test_listagem_3_sem_diagnosticos():
    assert diagnosticos(EXEMPLO.read_text(encoding="utf-8-sig")) == []


def test_regra_base_dos_testes_e_valida():
    assert codigos(POLITICA + regra()) == []


@pytest.mark.parametrize("given,codigo", [
    ("drone.altitude < 10 m", "V1"),
    ("drone.battery < 18", "V2"),
    ("drone.battery < 18 ms", "V2"),
    ("drone.battery < 120 %", "V3"),
    ("terrain.below IN { WATER, LAVA }", "V3"),
    ("terrain.below < WATER", "V3"),
    ("terrain.suitability > 0.5", "V3"),
])
def test_given(given, codigo):
    assert codigos(POLITICA + regra(given=given)) == [codigo]


@pytest.mark.parametrize("acoes,codigo", [
    ('SET view "HUD".mode = NOMINAL;', "V1"),
    ('SET view "MAP".zoom = 2;', "V1"),
    ('SUPPRESS pass "ShadowPass";', "V1"),
    ('SCALE instances "trees" BY 0.5;', "V1"),
    ('SET view "AGRO".hz = 2;', "V2"),
    ('HIGHLIGHT ARGMAX terrain.suitability WITHIN 400 ms;', "V2"),
    ('SCALE instances "crops" BY 0.5 Hz;', "V2"),
    ('SET view "AGRO".hz = 3 Hz;', "V3"),
    ('SET view "MAP".mode = 2;', "V3"),
    ('HIGHLIGHT ARGMIN drone.battery;', "V3"),
    ('SCALE instances "crops" BY 1.5;', "V3"),
    ('SET view "FPV".enabled = false;', "V4"),
    ('INJECT pass "TerrainPass" AFTER "TerrainPass";', "V8"),
])
def test_acoes(acoes, codigo):
    assert codigos(POLITICA + regra(acoes=acoes)) == [codigo]


@pytest.mark.parametrize("acoes", [
    'SET view "FPV".enabled = true;', 'SET view "FPV".scale = 0.5;'])
def test_v4_so_bloqueia_desativar_superficie_critica(acoes):
    assert codigos(POLITICA + regra(acoes=acoes)) == []


def test_v5_set_contradiz_o_proprio_assert():
    fonte = POLITICA + regra(acoes='SET view "FPV".scale = 0.5;',
                             garantia='view "FPV".scale >= 0.75')
    assert codigos(fonte) == ["V5"]


def test_v5_nao_decide_garantia_com_or():
    fonte = POLITICA + regra(
        acoes='SET view "FPV".scale = 0.5;',
        garantia='view "FPV".scale >= 0.75 OR frame_budget <= 16.67 ms')
    assert codigos(fonte) == []


def test_v6_mesma_prioridade_e_valores_diferentes_gera_aviso():
    fonte = (POLITICA + regra(nome="Uma")
             + regra(nome="Outra", acoes='SET view "MAP".mode = NOMINAL;'))
    [d] = diagnosticos(fonte)
    assert (d.codigo, d.nivel) == ("V6", "aviso")


def test_v6_prioridades_diferentes_nao_conflitam():
    fonte = (POLITICA + regra(nome="Uma", prio=10)
             + regra(nome="Outra", prio=20, acoes='SET view "MAP".mode = NOMINAL;'))
    assert codigos(fonte) == []


@pytest.mark.parametrize("politica,esperado", [
    ("POLICY Politica { budget = 2 ms; reserve = 2 ms; }", ["V7"]),
    ("POLICY Politica { cooldown = 10 frames; }", ["V7"]),
    ("POLICY Politica { budget = 16 frames; }", ["V2"]),
    ("POLICY Politica { budget = 16.67 ms; budget = 10 ms; }", ["V7"]),
    (POLITICA + POLITICA, ["V7"]),
])
def test_politica(politica, esperado):
    assert codigos(politica + "\n" + regra()) == esperado


def test_v8_nome_de_regra_duplicado():
    assert codigos(POLITICA + regra() + regra()) == ["V8"]


def test_formato_do_diagnostico():
    [d] = diagnosticos(POLITICA + regra(given="drone.battery < 18"))
    assert str(d) == f"2:{d.pos[1]}: erro semântico [V2]: drone.battery exige unidade %"


def test_modelo_rejeita_instancia_de_passo_inexistente():
    toml = '[passos]\nnomes = ["A"]\n[instancias]\ncrops = { passo = "B" }\n'
    with pytest.raises(ErroModelo, match="passo"):
        construir(tomllib.loads(toml))


def test_modelo_rejeita_atributo_que_a_linguagem_nao_escreve():
    toml = ('[superficies.FPV]\ncriticidade = "CRITICA"\n'
            'atributos.resolution = { valores = [1.0] }\n')
    with pytest.raises(ErroModelo, match="resolution"):
        construir(tomllib.loads(toml))