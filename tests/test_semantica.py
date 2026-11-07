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
          garantia=None, nome="Regra", prio=None, quando='AROUND pass "TerrainPass"'):
    p = f" PRIORITY {prio}" if prio is not None else ""
    a = f" ASSERT {garantia}" if garantia else ""
    return f"RULE {nome}{p} GIVEN {given} WHEN {quando} THEN {acoes}{a} END\n"


def diagnosticos(fonte, modelo=MODELO):
    prog, sintaticos = analisar(fonte)
    assert sintaticos == []          # todos os casos são sintaticamente corretos
    return verificar(prog, modelo)


def codigos(fonte, modelo=MODELO):
    return [d.codigo for d in diagnosticos(fonte, modelo)]


def test_listagem_3_sem_diagnosticos():
    assert diagnosticos(EXEMPLO.read_text(encoding="utf-8-sig")) == []


def test_regra_base_dos_testes_e_valida():
    assert codigos(POLITICA + regra()) == []


# ----- V1-V3 em GIVEN ----------------------------------------------------

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


# ----- V1-V4 em ações ----------------------------------------------------

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
])
def test_acoes(acoes, codigo):
    assert codigos(POLITICA + regra(acoes=acoes)) == [codigo]


@pytest.mark.parametrize("acoes", [
    'SET view "FPV".enabled = true;', 'SET view "FPV".scale = 0.5;'])
def test_v4_so_bloqueia_desativar_superficie_critica(acoes):
    assert codigos(POLITICA + regra(acoes=acoes)) == []


# ----- V5: ponto de junção -----------------------------------------------

@pytest.mark.parametrize("quando,acoes", [
    ('AROUND pass "SuitabilityPass"',
     'INJECT pass "SuitabilityPass" AFTER "TerrainPass";'),
    ('AROUND pass "TerrainPass"', 'SUPPRESS pass "TerrainPass";'),
    ('AFTER pass "TerrainPass"', 'SUPPRESS pass "TerrainPass";'),
    ('AROUND pass "CropInstancesPass"',
     'INJECT pass "TerrainPass" AFTER "TerrainPass";'),
    ('AROUND pass "TerrainPass"',
     'INJECT pass "SuitabilityPass" AFTER "CropInstancesPass"; '
     'SUPPRESS pass "CropInstancesPass";'),
    ('AROUND pass "TerrainPass"',
     'INJECT pass "SuitabilityPass" AFTER "TerrainPass"; '
     'INJECT pass "CropInstancesPass" AFTER "TerrainPass";'),
])
def test_v5_juncao_invalida_ou_ambigua(quando, acoes):
    assert codigos(POLITICA + regra(quando=quando, acoes=acoes)) == ["V5"]


def test_v5_suppress_antes_do_proprio_passo_e_valido():
    fonte = POLITICA + regra(quando='BEFORE pass "TerrainPass"',
                             acoes='SUPPRESS pass "TerrainPass";')
    assert codigos(fonte) == []


# ----- V6: conflito de escrita -------------------------------------------

def test_v6_enumerado_mesma_prioridade_condicoes_compativeis():
    fonte = (POLITICA + regra(nome="Uma")
             + regra(nome="Outra", acoes='SET view "MAP".mode = NOMINAL;'))
    [d] = diagnosticos(fonte)
    assert (d.codigo, d.nivel) == ("V6", "erro")


def test_v6_condicoes_mutuamente_exclusivas_nao_conflitam():
    fonte = (POLITICA + regra(nome="Uma")
             + regra(nome="Outra", given="drone.battery >= 18 %",
                     acoes='SET view "MAP".mode = NOMINAL;'))
    assert codigos(fonte) == []


def test_v6_atributo_numerico_e_resolvido_pelo_minimo():
    fonte = (POLITICA + regra(nome="Uma", acoes='SET view "AGRO".hz = 2 Hz;')
             + regra(nome="Outra", acoes='SET view "AGRO".hz = 5 Hz;'))
    assert codigos(fonte) == []


def test_v6_prioridades_diferentes_nao_conflitam():
    fonte = (POLITICA + regra(nome="Uma", prio=10)
             + regra(nome="Outra", prio=20, acoes='SET view "MAP".mode = NOMINAL;'))
    assert codigos(fonte) == []


def test_v6_mesma_regra_dois_valores():
    acoes = 'SET view "MAP".mode = NOMINAL; SET view "MAP".mode = SUITABILITY;'
    assert codigos(POLITICA + regra(acoes=acoes)) == ["V6"]


# ----- V7: regra inalcançável --------------------------------------------

@pytest.mark.parametrize("given", [
    "drone.battery < 10 % AND drone.battery > 20 %",
    "drone.battery < 0 %",                          # limite min do modelo
    "terrain.below IN { WATER } AND terrain.below == BARE_SOIL",
    "NOT terrain.below IN { WATER, STANDING_CROP, BARE_SOIL }",
])
def test_v7_regra_inalcancavel(given):
    assert codigos(POLITICA + regra(given=given)) == ["V7"]


@pytest.mark.parametrize("given", [
    "drone.battery < 10 % OR drone.battery > 20 %",
    "drone.battery <= 0 %",
    "NOT terrain.below IN { WATER } AND drone.battery < 18 %",
])
def test_v7_condicoes_satisfaziveis(given):
    assert codigos(POLITICA + regra(given=given)) == []


# ----- V8: instrumento de medição ----------------------------------------

def test_v8_assert_sobre_entrada_de_telemetria():
    assert codigos(POLITICA + regra(garantia="drone.battery > 5 %")) == ["V8"]


def test_v8_listagem_3_depende_do_instrumento_de_frame_budget():
    with open(MODELO_PADRAO, "rb") as f:
        dados = tomllib.load(f)
    del dados["telemetria"]["frame_budget"]["instrumento"]
    fonte = EXEMPLO.read_text(encoding="utf-8-sig")
    assert codigos(fonte, construir(dados)) == ["V8"]


# ----- C1 e C2 (complementares) ------------------------------------------

def test_c1_set_contradiz_o_proprio_assert():
    fonte = POLITICA + regra(acoes='SET view "FPV".scale = 0.5;',
                             garantia='view "FPV".scale >= 0.75')
    assert codigos(fonte) == ["C1"]


def test_c1_nao_decide_garantia_com_or():
    fonte = POLITICA + regra(
        acoes='SET view "FPV".scale = 0.5;',
        garantia='view "FPV".scale >= 0.75 OR frame_budget <= 16.67 ms')
    assert codigos(fonte) == []


@pytest.mark.parametrize("politica,esperado", [
    ("POLICY Politica { budget = 2 ms; reserve = 2 ms; }", ["V3"]),
    ("POLICY Politica { budget = 0 ms; }", ["V3"]),
    ("POLICY Politica { budget = 16.67 ms; cooldown = 2.5 frames; }", ["V3"]),
    ("POLICY Politica { budget = 16 frames; }", ["V2"]),
    ("POLICY Politica { cooldown = 10 frames; }", ["C2"]),
    ("POLICY Politica { budget = 16.67 ms; budget = 10 ms; }", ["C2"]),
    (POLITICA + POLITICA, ["C2"]),
])
def test_politica(politica, esperado):
    assert codigos(politica + "\n" + regra()) == esperado


def test_c2_nome_de_regra_duplicado():
    assert codigos(POLITICA + regra() + regra()) == ["C2"]


# ----- formato e modelo --------------------------------------------------

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