import importlib

import pytest

pytest.importorskip("numpy")

from dressgl.simulador import configuracao
from dressgl.trace import para_json
from visualizador.fonte import GRAVACOES, PROGRAMAS, _linhas, caminho_trace
from visualizador.render_trace import CALIBRACAO, ReprodutorAgroView, plano_de

CASOS = [(g, p) for g in GRAVACOES for p in PROGRAMAS
         if caminho_trace(g, p, "agroview").exists()]


def _trace(g, p):
    return list(_linhas(caminho_trace(g, p, "agroview")))


@pytest.fixture(scope="module")
def rep():
    if not CALIBRACAO.exists():
        pytest.skip(f"sem {CALIBRACAO}")
    return ReprodutorAgroView()


@pytest.mark.parametrize("g,p", CASOS)
def test_plano_ida_e_volta(g, p):
    """plano_de é o inverso de para_json em todos os quadros."""
    for r in _trace(g, p):
        assert para_json(plano_de(r["plano"])) == para_json(plano_de(para_json(plano_de(r["plano"]))))
        if r["plano"]:
            assert para_json(plano_de(r["plano"])) == r["plano"], r["quadro"]


@pytest.mark.parametrize("g,p", CASOS)
def test_reconstrucao_bate_com_o_trace(rep, g, p):
    """Com o plano de q-1 (D40): view:* e frame_budget do quadro q batem com o gravado."""
    linhas = _trace(g, p)
    assert [int(r["quadro"]) for r in linhas] == list(range(len(linhas)))
    anterior = {}
    for r in linhas:
        q, plano = r["quadro"], plano_de(anterior)
        conf = para_json(configuracao(rep.h.superficies, plano))
        assert {k: r["leituras"][k] for k in conf} == conf, q
        imagens, ms = rep.quadro(q, plano)
        assert ms == pytest.approx(r["leituras"]["frame_budget"], rel=1e-9), q
        assert "FPV" in imagens or r["leituras"].get("view:FPV.enabled") is False, q
        anterior = r["plano"]


def test_main_importa():
    """Pega erros de sintaxe/indentação no __main__ (o if __name__ evita abrir a janela)."""
    importlib.import_module("visualizador.__main__")