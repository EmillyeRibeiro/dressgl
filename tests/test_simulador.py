import dataclasses

import pytest

from dressgl import trace
from dressgl.interpretador import EfeitoInject, compilar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.motor import compor
from dressgl.simulador import (PLANO_VAZIO, ErroCenario, HospedeiroSimulado,
                               carregar_cenario, executar)

RAIZ = MODELO_PADRAO.parent.parent
EXEMPLO = RAIZ / "examples" / "safe_setdown.dgl"
CENARIO = RAIZ / "examples" / "cenarios" / "listagem3.toml"
NOME = "SafeSetdownAssist"


@pytest.fixture(scope="module")
def programa():
    return compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), carregar(MODELO_PADRAO))


@pytest.fixture(scope="module")
def cenario():
    return carregar_cenario(CENARIO)


@pytest.fixture(scope="module")
def host(cenario):
    return HospedeiroSimulado(cenario)


@pytest.fixture(scope="module")
def linhas(programa, cenario):
    return executar(programa, cenario)


def test_cenario_interpola_e_sobrepoe(cenario):                  # D28
    assert cenario.quadros == 300
    assert cenario.entradas[0] == {"drone.battery": 40.0, "terrain.below": "BARE_SOIL"}
    assert cenario.entradas[299]["drone.battery"] == pytest.approx(10.0)
    assert cenario.entradas[180]["terrain.below"] == "WATER"
    assert cenario.entradas[260]["terrain.below"] == "BARE_SOIL"


def test_custo_nominal_e_com_regra(programa, host):              # D29
    assert host.custo_ms(PLANO_VAZIO) == pytest.approx(15.0)
    plano, _ = compor(programa.regras)
    assert host.custo_ms(plano) == pytest.approx(13.4)


def test_injecao_sem_compensacao_estoura(host):
    plano = dataclasses.replace(PLANO_VAZIO, injecoes=(
        EfeitoInject("SuitabilityPass", "AFTER", "TerrainPass"),))
    assert host.custo_ms(plano) == pytest.approx(18.0)


def test_scale_resolution_quadratico(host):                      # D23
    plano = dataclasses.replace(PLANO_VAZIO, escalas={("resolution", "FPV"): 0.5})
    assert host.custo_ms(plano) == pytest.approx(15.0 - 3.0 + 3.0 * 0.25)
    assert host.leituras(0, plano)["view:FPV.scale"] == 0.5


def test_views_seguem_plano_e_voltam_ao_padrao(programa, host):  # D32
    plano, _ = compor(programa.regras)
    com, sem = host.leituras(1, plano), host.leituras(1, PLANO_VAZIO)
    assert (com["view:MAP.mode"], com["view:AGRO.hz"]) == ("SUITABILITY", 2)
    assert (sem["view:MAP.mode"], sem["view:AGRO.hz"]) == ("NOMINAL", 10)
    assert com["view:FPV.scale"] == sem["view:FPV.scale"] == 1.0


def test_execucao_listagem_3(linhas):
    assert [l["quadro"] for l in linhas if l["ativadas"]] == [220]
    assert [l["quadro"] for l in linhas if l["desativadas"]] == [260]
    fb = lambda q: linhas[q]["leituras"]["frame_budget"]
    assert fb(220) == pytest.approx(15.0)      # ainda mede o plano vazio de 219
    assert fb(221) == pytest.approx(13.4)      # mede o plano de 220 (D25)
    assert fb(261) == pytest.approx(15.0)
    assert all(l["violacoes"] == [] and l["conflitos"] == [] for l in linhas)


def test_trace_serializa_plano(linhas):                          # D30
    p = linhas[220]["plano"]
    assert p["sets"] == {"MAP.mode": "SUITABILITY", "AGRO.hz": 2}
    assert p["escalas"] == {"instances.crops": 0.25}
    assert p["injecoes"][0]["passo"] == "SuitabilityPass" and p["supressoes"] == []
    assert linhas[220]["condicoes"] == {NOME: True}


def test_trace_ida_e_volta(linhas, tmp_path):
    caminho = tmp_path / "t.jsonl"
    trace.gravar(caminho, linhas)
    assert trace.ler(caminho) == linhas
    assert len(caminho.read_text(encoding="utf-8").splitlines()) == 300


def test_ruido_deterministico(programa, cenario):                # D28
    ruidoso = dataclasses.replace(cenario, ruido_ms=0.5, semente=7)
    a = executar(programa, ruidoso)
    assert a == executar(programa, ruidoso)
    assert a != executar(programa, cenario)


def test_metricas_listagem_3(linhas):                            # D31
    m = trace.metricas(linhas, 16.67)
    assert (m["quadros"], m["ativacoes"], m["desativacoes"]) == (300, 1, 1)
    assert m["retencoes"] == m["violacoes_assert"] == m["conflitos"] == 0
    assert m["acima_orcamento_pct"] == 0.0 and m["atraso_ativacao_max"] == 0


def test_metricas_atraso_e_retencao():
    def l(q, cond, ativadas=(), retidas=(), fb=10.0):
        return {"quadro": q, "condicoes": {"R": cond}, "ativadas": list(ativadas),
                "desativadas": [], "retidas": list(retidas), "conflitos": [],
                "violacoes": [], "leituras": {"frame_budget": fb}}
    linhas = [l(0, False), l(1, True, retidas=["R"], fb=20.0),
              l(2, True, retidas=["R"]), l(3, True, ativadas=["R"])]
    m = trace.metricas(linhas, 16.67)
    assert m["atraso_ativacao_max"] == 2 and m["retencoes"] == 2
    assert m["acima_orcamento_pct"] == 25.0 and m["pior_quadro_ms"] == 20.0


BASE = 'quadros = 3\n[[trechos]]\ninicio = 0\nfim = 2\n"drone.battery" = 50\n'
TRECHO = '[[trechos]]\ninicio = 0\nfim = {fim}\n"terrain.below" = "{solo}"\n'


@pytest.mark.parametrize("extra", [
    "",                                                      # falta terrain.below
    TRECHO.format(fim=2, solo="LAVA"),                       # enum inválido
    TRECHO.format(fim=2, solo="WATER") + '"drone.battery" = 150\n',   # > max
    TRECHO.format(fim=5, solo="WATER"),                      # fora dos quadros
    TRECHO.format(fim=2, solo="WATER") + "frame_budget = 10\n",       # é instrumento
])
def test_cenario_invalido(tmp_path, extra):
    arq = tmp_path / "c.toml"
    arq.write_text(BASE + extra, encoding="utf-8")
    with pytest.raises(ErroCenario):
        carregar_cenario(arq)

def test_scale_resolution_pelo_parser(host):                     # fecha a suposição de D23
    fonte = ('RULE R GIVEN drone.battery < 18 % WHEN AROUND pass "TerrainPass" '
             'THEN SCALE resolution "FPV" BY 0.5; END\n')
    plano, _ = compor(compilar_programa(fonte, carregar(MODELO_PADRAO)).regras)
    assert plano.escalas == {("resolution", "FPV"): 0.5}
    assert host.leituras(0, plano)["view:FPV.scale"] == 0.5