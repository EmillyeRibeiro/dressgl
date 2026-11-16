import json
import math
import statistics as st
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from ponte_coppelia.percepcao import (Percepcao, Zona, aplicar, classificar,
                                      percepcao_da_missao, ruido_posicao, zonas_da_missao)

RAIZ = Path(__file__).resolve().parents[1]
MISSOES = RAIZ / "examples" / "missoes"
ZONAS = [
    Zona("zona_0_bare_soil", "BARE_SOIL", (-2.5, 2.5), (-2.5, 2.5)),
    Zona("zona_1_standing_crop", "STANDING_CROP", (-2.5, -0.5), (-2.5, 2.5)),
    Zona("zona_2_water", "WATER", (0.8, 2.2), (-0.8, 0.8)),
]


def _missao(nome):
    return tomllib.loads((MISSOES / f"{nome}.toml").read_text(encoding="utf-8"))


def _registros(xs):
    return [{"quadro": k, "pos": [x, 0.0, 1.0], "terrain.below": classificar(x, 0.0, ZONAS)}
            for k, x in enumerate(xs)]


def test_classificar_ultima_zona_vence():
    assert classificar(0.0, 0.0, ZONAS) == "BARE_SOIL"
    assert classificar(-1.0, 0.0, ZONAS) == "STANDING_CROP"
    assert classificar(1.5, 0.0, ZONAS) == "WATER"
    assert classificar(3.0, 3.0, ZONAS) == "UNKNOWN"


def test_zonas_de_pouso_agua_batem_com_desenhar_zonas():
    z = zonas_da_missao(_missao("pouso_agua"))
    assert [(q.classe, q.x, q.y) for q in z] == [(c.classe, c.x, c.y) for c in ZONAS]


@pytest.mark.parametrize("nome", ["pouso_agua", "borda_agua"])
def test_zonas_reproduzem_gravacao_fisica(nome):
    g = RAIZ / "results" / f"gravacao_{nome}.jsonl"
    if not g.exists():
        pytest.skip(f"{g.name} ausente")
    zonas = zonas_da_missao(_missao(nome))
    R = [json.loads(s) for s in g.open(encoding="utf-8") if s.strip()]
    dif = [r["quadro"] for r in R
           if classificar(r["pos"][0], r["pos"][1], zonas) != r["terrain.below"]]
    assert not dif, f"{len(dif)} quadros divergem; primeiro: {dif[0]}"


def test_erro_zero_e_identidade():
    R = _registros([0.5 + 0.001 * k for k in range(600)])
    S = aplicar(R, ZONAS, Percepcao())
    for r, s in zip(R, S):
        assert s["pos"] == r["pos"] and s["pos_real"] == r["pos"]
        assert s["terrain.below"] == r["terrain.below"] == s["terrain.below_real"]


def test_nao_altera_a_entrada():
    R = _registros([0.79] * 120)
    copia = json.loads(json.dumps(R))
    aplicar(R, ZONAS, Percepcao(erro_pos_m=0.05, tau_s=0.5))
    assert R == copia


def test_determinismo_por_semente():
    p = Percepcao(erro_pos_m=0.05, tau_s=0.5, semente=3)
    assert ruido_posicao(600, p) == ruido_posicao(600, p)
    assert ruido_posicao(600, p) != ruido_posicao(600, replace(p, semente=4))


def test_amostra_e_retencao_a_10_hz():
    r = ruido_posicao(600, Percepcao(erro_pos_m=0.05, tau_s=0.5, hz_sensor=10))
    assert all(r[k] == r[k - k % 6] for k in range(600))


def test_desvio_estacionario():
    r = ruido_posicao(50_000, Percepcao(erro_pos_m=0.05, hz_sensor=60))
    assert abs(st.pstdev(e[0] for e in r) - 0.05) < 0.0025


def test_correlacao_gauss_markov():
    r = ruido_posicao(120_000, Percepcao(erro_pos_m=0.05, tau_s=0.5, hz_sensor=10))
    xs = [r[k][0] for k in range(0, len(r), 6)]
    m = st.fmean(xs)
    rho = (sum((a - m) * (b - m) for a, b in zip(xs, xs[1:]))
           / sum((a - m) ** 2 for a in xs))
    assert abs(rho - math.exp(-0.1 / 0.5)) < 0.03


def test_ruido_gera_trocas_perto_da_margem():
    R = _registros([0.79] * 600)          # 1 cm fora da água
    limpo = {s["terrain.below"] for s in aplicar(R, ZONAS, Percepcao())}
    ruido = {s["terrain.below"] for s in aplicar(R, ZONAS, Percepcao(erro_pos_m=0.05, tau_s=0.5))}
    assert limpo == {"BARE_SOIL"}
    assert ruido == {"BARE_SOIL", "WATER"}


def test_bloco_percepcao_de_margem_ruido():
    p, base = percepcao_da_missao(_missao("margem_ruido"))
    assert base == "borda_agua"
    assert (p.erro_pos_m, p.tau_s, p.hz_sensor, p.semente) == (0.05, 0.5, 10.0, 1)