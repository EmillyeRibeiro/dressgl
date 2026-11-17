import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
from visualizador.fonte import (GRAVACOES, HOSPEDEIROS, PROGRAMAS, RESULTADOS,
                                QuadroVisual, caminho_trace, carregar_missao, quadros)
from visualizador.imagem import ampliar, para_ppm

SRC = Path(__file__).resolve().parents[1] / "src"
CSV = RESULTADOS / "metricas_coppelia.csv"
ORCAMENTO_MS = 16.67   # o mesmo de janela.ORCAMENTO_MS (aqui sem importar tkinter)


def _linhas_csv():
    if not CSV.exists():
        return []
    with CSV.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f)
                if r["gravacao"] in GRAVACOES and r["programa"] in PROGRAMAS
                and r["hospedeiro"] in HOSPEDEIROS]


def test_ppm_cabecalho_e_tamanho():
    ppm = para_ppm(np.zeros((2, 3, 3), dtype=np.uint8))
    assert ppm.startswith(b"P6 3 2 255\n") and len(ppm) == len(b"P6 3 2 255\n") + 18


def test_ampliar_vizinho_mais_proximo():
    a = ampliar(np.arange(4, dtype=np.uint8).reshape(2, 2), 2)
    assert a.shape == (4, 4)
    assert (a[:2, :2] == 0).all() and (a[2:, 2:] == 3).all()


def test_nucleo_nao_importa_tkinter():
    """D61: nenhum módulo de dressgl pode puxar tkinter."""
    cod = (
        "import sys, pkgutil, importlib, dressgl\n"
        "for m in pkgutil.walk_packages(dressgl.__path__, 'dressgl.'):\n"
        "    try:\n"
        "        importlib.import_module(m.name)\n"
        "    except ModuleNotFoundError:\n"
        "        pass  # extra opcional não instalado\n"
        "assert 'tkinter' not in sys.modules, 'núcleo importou tkinter'\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    subprocess.run([sys.executable, "-c", cod], check=True, env=env)


def test_fonte_nao_importa_tkinter():
    cod = "import sys, visualizador.fonte; assert 'tkinter' not in sys.modules"
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    subprocess.run([sys.executable, "-c", cod], check=True, env=env)


def test_missao_borda_agua():
    m = carregar_missao("borda_agua")
    assert m["quadros"] == 720
    assert any(z["solo"] == "WATER" for z in m["zonas"])


def test_fonte_reproduz_tabela_xi():
    if not caminho_trace("borda_agua", "dsl", "agroview").exists():
        pytest.skip("trace ausente")
    qs = list(quadros("borda_agua", "dsl", "agroview"))
    assert len(qs) == 720
    assert [q.indice for q in qs] == list(range(720))
    assert max(q.leituras["frame_budget"] for q in qs) == pytest.approx(14.22, abs=0.005)
    assert sum(q.violacoes for q in qs) == 0
    assert all(q.pos_real is not None for q in qs)


@pytest.mark.parametrize(
    "linha", _linhas_csv(),
    ids=lambda r: f"{r['programa']}-{r['gravacao']}-{r['hospedeiro']}")
def test_fonte_bate_com_metricas_csv(linha):
    """A janela mostra os mesmos números do metricas_coppelia.csv."""
    if not caminho_trace(linha["gravacao"], linha["programa"], linha["hospedeiro"]).exists():
        pytest.skip("trace ausente")
    qs = list(quadros(linha["gravacao"], linha["programa"], linha["hospedeiro"]))
    budgets = [float(q.leituras["frame_budget"]) for q in qs]
    assert len(qs) == int(linha["quadros"])
    assert max(budgets) == pytest.approx(float(linha["pior_quadro_ms"]), abs=0.005)
    acima = 100 * sum(b > ORCAMENTO_MS for b in budgets) / len(budgets)
    assert acima == pytest.approx(float(linha["acima_orcamento_pct"]), abs=0.006)
    assert sum(q.violacoes for q in qs) == int(linha["violacoes_assert"])


def test_erro_pos_ainda_nao_suportado():
    with pytest.raises(NotImplementedError):
        quadros("borda_agua", "dsl", "agroview", erro_pos_m=0.05)


def test_janela_fumaca():
    tk = pytest.importorskip("tkinter")
    try:
        raiz = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")
    raiz.withdraw()
    from visualizador.janela import Janela

    zonas = [{"solo": "WATER", "x": [0.8, 2.2], "y": [-0.8, 0.8]}]
    falsos = lambda: (
        QuadroVisual(i, {"frame_budget": 10.0 + i}, (), (), 0, 0, {},
                     {"AGRO": np.zeros((96, 96, 3), np.uint8)},
                     pos_real=(0.1 * i, 0.0), pos_percebida=(0.1 * i, 0.05))
        for i in range(5)
    )
    j = Janela(raiz, falsos, 5, "teste", zonas=zonas)
    assert j._avancar(5) and not j._avancar(1)
    j._mostrar()
    assert j.pior == 14.0 and j.n == 5 and j.n_acima == 0
    assert len(j.campo.find_withtag("rastro")) == 4
    j._reiniciar()
    assert j.n == 0 and not j.campo.find_withtag("rastro")
    j.fechar()