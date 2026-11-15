from types import SimpleNamespace as N

import pytest

pytest.importorskip("numpy")

from agroview.calibracao import carregar_calibracao
from agroview.hospedeiro import HospedeiroAgroView
from dressgl.simulador import PLANO_VAZIO

ENTRADA = {"drone.battery": 50.0, "terrain.below": "BARE_SOIL"}
COEF = {"TerrainPass": 5e-5, "CropInstancesPass": 9e-5, "SuitabilityPass": 1.5e-6}


def _h(coef, n=61):
    return HospedeiroAgroView(N(entradas=[ENTRADA] * n), relogio="carga", ms_por_carga=coef)


def test_frame_budget_soma_carga_vezes_coeficiente_do_passo():
    h = _h(COEF)
    for q in range(61):
        l = h.leituras(q, PLANO_VAZIO)
    nomes = {e.nome for e in h.ultimo.execucoes}
    assert "SuitabilityPass" in nomes            # o quadro 60 tem AGRO
    esperado = sum(e.carga * COEF[e.nome] for e in h.ultimo.execucoes)
    assert l["frame_budget"] == pytest.approx(esperado)


def test_passo_sem_coeficiente_e_erro():
    h = _h({"TerrainPass": 5e-5})                # falta CropInstancesPass
    with pytest.raises(ValueError, match="D48"):
        h.leituras(0, PLANO_VAZIO)


@pytest.mark.parametrize("coef", [None, 0, -1.0, {}, {"TerrainPass": 0.0}])
def test_coeficiente_invalido_e_recusado(coef):
    with pytest.raises(ValueError):
        _h(coef)


def test_carregar_calibracao(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[ms_por_carga]\n"TerrainPass" = 5.0e-05  # n=10\n', encoding="utf-8")
    assert carregar_calibracao(p) == {"TerrainPass": 5e-05}