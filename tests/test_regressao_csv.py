"""Regressão: os CSVs versionados em results/ são reproduzíveis a partir do código."""
import pytest
import csv
import importlib.util
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _carregar_tool(nome):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "tools" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ler(arq):
    with open(arq, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _comparar(esperado, obtido):
    assert len(obtido) == len(esperado), f"{len(obtido)} linhas, esperado {len(esperado)}"
    difs = [(i, e, o) for i, (e, o) in enumerate(zip(esperado, obtido)) if e != o]
    if difs:
        i, e, o = difs[0]
        raise AssertionError(f"{len(difs)} linha(s) diferente(s); primeira na linha {i + 2} do CSV\n"
                             f"esperado: {e}\nobtido:   {o}")


def test_varredura_ruido_reproduz_csv(tmp_path):
    vr = _carregar_tool("varredura_ruido")
    missao = tomllib.loads((RAIZ / "examples" / "missoes" / "margem_ruido.toml")
                           .read_text(encoding="utf-8"))
    linhas, _ = vr.varrer(missao, RAIZ / "results", tmp_path / "percepcao")
    novo = tmp_path / "varredura_ruido.csv"
    vr.escrever_csv(novo, linhas)

    esperado = _ler(RAIZ / "results" / "varredura_ruido.csv")
    assert len(esperado) == len(vr.ERROS) * len(vr.SEMENTES) * len(vr.PROGRAMAS)  # 80
    _comparar(esperado, _ler(novo))

@pytest.mark.lento
def test_metricas_coppelia_reproduz_csv(tmp_path):
    pytest.importorskip("numpy")
    from ponte_coppelia import experimentos as ex
    esperado = _ler(RAIZ / "results" / "metricas_coppelia.csv")
    # mesmos hospedeiros do CSV versionado, na ordem em que aparecem nele
    hosp = list(dict.fromkeys(l["hospedeiro"] for l in esperado))
    ex.main(["--gravacoes", str(RAIZ / "results"), "--saida", str(tmp_path),
             "--hospedeiros", *hosp])
    _comparar(esperado, _ler(tmp_path / "metricas_coppelia.csv"))

    md = RAIZ / "results" / "metricas_coppelia.md"
    if md.exists():
        assert ((tmp_path / "metricas_coppelia.md").read_text(encoding="utf-8").splitlines()
                == md.read_text(encoding="utf-8").splitlines())
