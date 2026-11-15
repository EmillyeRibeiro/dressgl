import dataclasses
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")

from agroview.hospedeiro import HospedeiroAgroView
from agroview.ordem import ErroOrdem
from dressgl.hospedeiro import Hospedeiro
from dressgl.simulador import PLANO_VAZIO, HospedeiroSimulado

ENTRADAS = {"drone.battery": 50.0, "terrain.below": "BARE_SOIL"}
PEQ = {"FPV": (36, 64), "MAP": (32, 32), "AGRO": (24, 24)}   # testes rápidos


def cenario(n=130):
    return SimpleNamespace(entradas=[dict(ENTRADAS) for _ in range(n)],
                           ruido_ms=0.0, semente=0)


def hosp(**kw):
    return HospedeiroAgroView(cenario(), relogio="carga", ms_por_carga=1e-4,
                              resolucoes=PEQ, instancias_base=20, **kw)


def plano(**campos):
    return dataclasses.replace(PLANO_VAZIO, **campos)


def inj(passo, fase, ancora):
    return SimpleNamespace(passo=passo, fase=fase, ancora=ancora)


def execs(h):
    return [(e.nome, e.superficie) for e in h.ultimo.execucoes]


def media(h, p, n=60):                                   # D46: janela de 60
    return sum(h.leituras(q, p)["frame_budget"] for q in range(n)) / n


DEGRADADO = dict(sets={("AGRO", "hz"): 1},
                 escalas={("resolution", "FPV"): 0.5, ("instances", "crops"): 0.5})


def test_cumpre_protocolo():
    assert isinstance(hosp(), Hospedeiro)


def test_carga_exige_calibracao():
    with pytest.raises(ValueError):
        HospedeiroAgroView(cenario(), relogio="carga")


def test_mesmas_chaves_e_configuracao_que_o_simulado():
    p = plano(sets={("MAP", "mode"): "SUITABILITY", ("AGRO", "hz"): 1},
              escalas={("resolution", "FPV"): 0.5})
    a = hosp().leituras(0, p)
    s = HospedeiroSimulado(cenario()).leituras(0, p)
    assert set(a) == set(s)
    assert {k: v for k, v in a.items() if k != "frame_budget"} == \
           {k: v for k, v in s.items() if k != "frame_budget"}


def test_nominal_no_quadro_0():
    h = hosp()
    h.leituras(0, PLANO_VAZIO)
    assert execs(h) == [("TerrainPass", "FPV"), ("CropInstancesPass", "FPV"),
                        ("TerrainPass", "MAP"), ("SuitabilityPass", "AGRO")]


def test_decimacao_do_agro():                            # D43: 10 Hz -> período 6
    h = hosp()
    quadros = []
    for q in range(12):
        h.leituras(q, PLANO_VAZIO)
        if ("SuitabilityPass", "AGRO") in execs(h):
            quadros.append(q)
    assert quadros == [0, 6]


def test_map_suitability_sobrepoe_ao_terreno():          # D45
    h = hosp()
    h.leituras(1, plano(sets={("MAP", "mode"): "SUITABILITY"}))
    assert [e for e in execs(h) if e[1] == "MAP"] == \
           [("TerrainPass", "MAP"), ("SuitabilityPass", "MAP")]


def test_suppress_e_inject_no_fpv():                     # D44, D47
    p = plano(supressoes=frozenset({"CropInstancesPass"}),
              injecoes=(inj("SuitabilityPass", "AFTER", "TerrainPass"),))
    h = hosp()
    h.leituras(1, p)
    assert [n for n, s in execs(h) if s == "FPV"] == ["TerrainPass", "SuitabilityPass"]


def test_ancora_suprimida_e_erro_do_hospedeiro():        # D44
    p = plano(supressoes=frozenset({"TerrainPass"}),
              injecoes=(inj("SuitabilityPass", "AFTER", "TerrainPass"),))
    with pytest.raises(ErroOrdem):
        hosp().leituras(0, p)


def test_carga_e_deterministica():
    assert hosp().leituras(3, PLANO_VAZIO) == hosp().leituras(3, PLANO_VAZIO)


def test_pico_da_decimacao():                            # D46: sem média
    h = hosp()
    p = plano(sets={("AGRO", "hz"): 1})                  # período 60
    fb = [h.leituras(q, p)["frame_budget"] for q in range(61)]
    assert fb[0] == fb[60] > fb[1] == fb[59]


def test_janela_60_mesma_direcao_que_o_simulado():       # D46
    for novo in (hosp, lambda: HospedeiroSimulado(cenario())):
        assert media(novo(), plano(**DEGRADADO)) < media(novo(), PLANO_VAZIO)


def test_relogio_tempo_mede_algo():
    h = HospedeiroAgroView(cenario(), resolucoes=PEQ, instancias_base=20)
    assert h.leituras(0, PLANO_VAZIO)["frame_budget"] > 0