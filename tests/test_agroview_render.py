import pytest

np = pytest.importorskip("numpy")
from agroview import render as r  # noqa: E402


@pytest.fixture(scope="module")
def mapa():
    return r.mapa_altura(7, 64)


@pytest.fixture(scope="module")
def rend():
    return r.Renderizador(semente=7, lado_mapa=64)


def _passos(escala=1.0, instancias=100, sem_aptidao=False):
    lado = r.resolucao(64, escala)
    ps = [
        r.Passo("TerrainPass", "FPV", lado, lado),
        r.Passo("CropInstancesPass", "FPV", lado, lado, instancias=instancias),
    ]
    if not sem_aptidao:
        ps.append(r.Passo("SuitabilityPass", "AGRO", lado, lado, raio=2))
    return ps


def test_mapa_deterministico_e_normalizado(mapa):
    assert mapa.shape == (64, 64)
    assert np.array_equal(mapa, r.mapa_altura(7, 64))
    assert not np.array_equal(mapa, r.mapa_altura(8, 64))
    assert mapa.min() == 0.0 and mapa.max() == 1.0


def test_solo_em(mapa):
    assert r.solo_em(mapa, 0.5, 0.5) in r.SOLOS
    with pytest.raises(ValueError):
        r.solo_em(mapa, 1.5, 0.0)


def test_resolucao():
    assert r.resolucao(320, 1.0) == 320
    assert r.resolucao(320, 0.5) == 160
    assert r.resolucao(3, 0.01) == 1
    with pytest.raises(ValueError):
        r.resolucao(320, 0)


def test_terreno_forma_e_tipo(mapa):
    img = r.terreno(mapa, 30, 40)
    assert img.shape == (30, 40, 3) and img.dtype == np.uint8


def test_culturas_nao_altera_entrada():
    base = np.zeros((32, 32, 3), np.uint8)
    assert np.array_equal(r.culturas(base, 0, 1), base)
    out = r.culturas(base, 20, 1)
    assert out.any() and not base.any()


def test_aptidao_no_intervalo(mapa):
    c = r.aptidao(mapa, 20, 24, 2)
    assert c.shape == (20, 24)
    assert c.min() >= -1e-12 and c.max() <= 1 + 1e-12


def test_ordem_respeitada(rend):
    ps = list(reversed(_passos()))
    q = rend.quadro(ps)
    assert q.ordem == [(p.nome, p.superficie) for p in ps]
    assert all(e.tempo_ms >= 0 for e in q.execucoes)
    assert set(q.imagens) == {"FPV", "AGRO"}


def test_ordem_altera_resultado(rend):
    normal = rend.quadro(_passos()).imagens["FPV"]
    invertida = rend.quadro(_passos()[1::-1]).imagens["FPV"]  # culturas, depois terreno
    assert np.array_equal(invertida, r.terreno(rend.mapa, 64, 64))
    assert not np.array_equal(normal, invertida)


def test_escala_reduz_carga_quadraticamente(rend):
    cheia = rend.quadro(_passos(1.0, instancias=0)).carga_total
    meia = rend.quadro(_passos(0.5, instancias=0)).carga_total
    assert meia * 4 == cheia


def test_supressao_e_instancias_reduzem_carga(rend):
    base = rend.quadro(_passos()).carga_total
    assert rend.quadro(_passos(sem_aptidao=True)).carga_total < base
    assert rend.quadro(_passos(instancias=10)).carga_total < base


def test_sobreposicao_exige_mesma_resolucao():
    with pytest.raises(ValueError):
        r.sobrepor(np.zeros((4, 4, 3), np.uint8), np.zeros((5, 5)))


def test_passo_invalido():
    with pytest.raises(ValueError):
        r.Passo("BloomPass", "FPV", 8, 8)